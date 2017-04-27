#
# Copyright (c) 2016 Nordic Semiconductor ASA
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#   1. Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
#   2. Redistributions in binary form must reproduce the above copyright notice, this
#   list of conditions and the following disclaimer in the documentation and/or
#   other materials provided with the distribution.
#
#   3. Neither the name of Nordic Semiconductor ASA nor the names of other
#   contributors to this software may be used to endorse or promote products
#   derived from this software without specific prior written permission.
#
#   4. This software must only be used in or with a processor manufactured by Nordic
#   Semiconductor ASA, or in or with a processor manufactured by a third party that
#   is used in combination with a processor manufactured by Nordic Semiconductor.
#
#   5. Any software provided in binary or object form under this license must not be
#   reverse engineered, decompiled, modified and/or disassembled.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
import logging
import binascii
import struct
import tqdm
import piccata.core
import piccata.block_transfer

from ipaddress import ip_address
from piccata.message import Message
from piccata import constants


logger = logging.getLogger(__name__)

def _make_trigger(init_data, image_data):
    '''Create a trigger payload from given init and image data'''

    TRIGGER_VERSION = 0
    
    def crc(payload):
        return binascii.crc32(payload) & 0xffffffff
    # Structure format:
    # flags:      uint8_t
    # init size:  uint32_t
    # init crc:   uint32_t
    # image size: uint32_t
    # image crc:  uint32_t
    # prefix:     var len max 16 bytes
    flags = ((TRIGGER_VERSION << 4) & 0x03)
    return struct.pack(">BIIII",
                       flags,
                       len(init_data),
                       crc(init_data),
                       len(image_data),
                       crc(image_data))

def _uri_string_to_list(uri):
    '''Converts a URI string into a list of URI path elements. 
    
        Example: '/dfu/image' -> ['dfu', 'image']
    '''
    return uri.lstrip('/').split('/')

def _block_count(length, block_size):
    '''Return number of blocks of a given size for total length of data'''
    return int(length / (2 ** (block_size + 4)) + 0.5)

def _get_block_opt(request):
    if (request.opt.block1):
        return request.opt.block1
    elif (request.opt.block2):
        return request.opt.block2
    else:
        return (0, False, constants.DEFAULT_BLOCK_SIZE_EXP)

class ThreadDfuServer():
    
    def __init__(self, transport, init_data, image_data, uri_prefix):
        assert(init_data != None)
        assert(image_data != None)
               
        self.protocol = piccata.core.Coap(transport)       
        self.protocol.register_request_handler(self)
        
        self.transport = transport
        self.transport.register_receiver(self.protocol)
        
        self.trigger_payload = _make_trigger(init_data, image_data)
        self.init_data = init_data
        self.image_data = image_data
        
        self.uri_prefix = uri_prefix

        self.progress = {}
        
    def _update_progress_bar(self, remote_address, block_num, block_szx):
            block_count = _block_count(len(self.image_data), block_szx)
            
            if (remote_address not in self.progress):
                pbar = tqdm.tqdm(desc = str(remote_address),
                                 position = len(self.progress),
                                 initial = block_num,
                                 total = block_count)
                last_block = None
                self.progress[remote_address] = (pbar, block_num)
            else:
                pbar, last_block = self.progress[remote_address]
                
            if (last_block is not None and (block_num > last_block)):
                pbar.update(block_num - last_block)
                self.progress[remote_address] = (pbar, block_num)
                
            if (block_num == block_count):
                pbar.close()
        
    def _handle_image_request(self, request):
        block_num, _, block_szx = _get_block_opt(request)
        self._update_progress_bar(request.remote.addr, block_num, block_szx)
        return piccata.block_transfer.create_block_2_response(self.image_data, request)

    def _handle_init_request(self, request):
        return piccata.block_transfer.create_block_2_response(self.init_data, request)      
    
    def _handle_trigger_response(self, result, request, response, num_of_requests):
        if (response == piccata.constants.RESULT_SUCCESS):
            logger.info('Response Code: ' + piccata.constants.responses[response.code])
            logger.info('Payload: ' + response.payload)
        elif (num_of_requests - 1 > 0):
            request.timeout = 2*request.timeout
            self.protocol.request(request, self._handle_trigger_response, (num_of_requests - 1,))
        else:
            logger.info("All triggers sent")

    def receive_request(self, request):
        '''Request callback called by the CoAP toolkit. Note that the function
           signature (name, args) is expected by the CoAP toolkit.'''
        
        # TODO: remove hardcoded URIs
        handlers = {
            'image' : self._handle_image_request,
            'init'  : self._handle_init_request,
            'trig'  : lambda request : Message.AckMessage(request, 
                                                          constants.CONTENT,
                                                          self.trigger_payload)
        }
        
        for uri, handler in handlers.items():
            if request.opt.uri_path == _uri_string_to_list(self.uri_prefix + '/' + uri):
                response = handler(request)
        
        return response  
    
    def trigger(self, address, num_of_requests):
        logger.info('Triggering DFU on {}\r'.format(address))
        
        request = piccata.message.Message(mtype = piccata.constants.NON, code=piccata.constants.POST)
        request.opt.uri_path = (self.uri_prefix, "trig",)
        request.remote = (ip_address(address), piccata.constants.COAP_PORT)
        request.timeout = piccata.constants.ACK_TIMEOUT
        request.payload = self.trigger_payload
        
        self.protocol.request(request, self._handle_trigger_response, (num_of_requests,))

    def start(self):
        logger.debug("Starting DFU Server")
        self.transport.open()
        logger.debug("Server ready")

    def stop(self):
        logger.debug("Stopping DFU Server")
        self.transport.close()
        logger.debug("Server stopped")
