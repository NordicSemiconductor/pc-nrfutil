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
import threading

import piccata.core
import piccata.block_transfer
from piccata.block_transfer import extract_block
from piccata.message import Message
from piccata import constants
from ipaddress import ip_address
from collections import namedtuple
import click
import time
import math

logger = logging.getLogger(__name__)

def _make_trigger(init_data, image_data, mcast_mode = False, reset_suppress = 0):
    '''Create a trigger payload from given init and image data'''

    TRIGGER_VERSION    = 1
    MCAST_MODE_BIT     = 0x08
    RESET_SUPPRESS_BIT = 0x04

    def crc(payload):
        return binascii.crc32(payload) & 0xffffffff
    # Structure format:
    # flags:      uint8_t
    #
    #    |V3|V2|V1|V0|M|R|R1|R0|
    #
    #    V3-V0: version
    #    M:     mcast mode
    #    R:     reset suppress
    #    R1-R0: reserved bits
    #
    # init size:  uint32_t
    # init crc:   uint32_t
    # image size: uint32_t
    # image crc:  uint32_t
    flags = (TRIGGER_VERSION << 4)
    if (mcast_mode):
        flags |= MCAST_MODE_BIT
    if (reset_suppress != 0):
        flags |= RESET_SUPPRESS_BIT

    return struct.pack(">BIIII",
                       flags,
                       len(init_data),
                       crc(init_data),
                       len(image_data),
                       crc(image_data))

def _make_bitmap(resource):
    return [(resource, i) for i in range(0, _block_count(len(resource.data), ThreadDfuServer.BLOCK_SZX))]

def _block_count(length, block_size):
    '''Return number of blocks of a given size for the total length of data.'''
    return math.ceil(length / (2 ** (block_size + 4)))

def _bmp_to_str(bitmap):
    '''Convert binary data into a bit string'''
    s = ''
    for i in range(8):
        s = s + '{:08b} '.format((bitmap >> 64 - 8*(i + 1)) & 0xff)
    return s[:len(s) - 1]

def _get_block_opt(request):
    if (request.opt.block1):
        return request.opt.block1
    elif (request.opt.block2):
        return request.opt.block2
    else:
        return (0, False, constants.DEFAULT_BLOCK_SIZE_EXP)

class ThreadDfuClient:
    def __init__(self):
        '''Stores a reference to a progress bar object.'''
        self.progress_bar = None
        '''The number of a block most recently requested by a node.'''
        self.last_block = None

Resource = namedtuple('Resource', ['path', 'data'])

class ThreadDfuServer:
    REALM_LOCAL_ADDR  = ip_address('FF03::1')

    SPBLK_SIZE        = 64      # number of CoAP blocks of BLOCK_SZX size each
    SPBLK_UPLOAD_RATE = 1       # in blocks / seconds
    SPBLK_BMP_TIMEOUT = 2       # in seconds
    BLOCK_SZX         = 2       # 64 bytes
    ERASE_DELAY       = 0.5     # in seconds
    SPBLK_FLUSH_DELAY = 1.0     # delay between superblocks
    POST_UPLOAD_DELAY = 5.0     # delay after uploading the last block, in seconds

    IMAGE_URI = b'f'
    INIT_URI = b'i'
    TRIGGER_URI = b't'
    BITMAP_URI = b'b'

    def __init__(self, protocol, init_data, image_data, opts):
        assert(protocol is not None)
        assert(init_data is not None)
        assert(image_data is not None)

        self.opts = opts
        if (not opts or not opts.rate):
            self.opts.rate = self.SPBLK_UPLOAD_RATE
        if (not opts or not opts.mcast_dfu):
            self.opts.mcast_dfu = False
        if (not opts or not opts.reset_suppress):
            self.opts.reset_suppress = 0

        self.protocol = protocol
        self.protocol.register_request_handler(self)

        self.progress_bar = None

        self.missing_blocks = []
        self.bmp_received_event = threading.Event()
        self.upload_done_event = threading.Event()
        self.upload_done_event.set()
        self.trig_done_event = threading.Event()

        self.init_resource = Resource((ThreadDfuServer.INIT_URI,), init_data)
        self.image_resource = Resource((ThreadDfuServer.IMAGE_URI,), image_data)

        self.clients = {}
        self.upload_thread = None

    def _draw_token(self):
        return piccata.message.random_token(2)

    def _update_progress_bar(self, address, client, block_count, total_block_count):
        # If node didn't request any blocks yet then create a new progress
        # bar for it. Update otherwise.
        if (client.progress_bar is None):
            client.progress_bar = tqdm.tqdm(desc = str(address),
                                            position = len(self.clients) - 1,
                                            initial = block_count,
                                            total = total_block_count)
        elif (block_count > client.last_block):
            client.progress_bar.update(block_count - client.last_block)

        if (block_count == total_block_count - 1):
            # One last update to fill the progress bar (block_count is indexed from 0)
            client.progress_bar.update()
            client.progress_bar.close()
            client.progress_bar = None

    def _handle_image_request(self, request):
        if (request.remote not in self.clients):
            self.clients[request.remote] = ThreadDfuClient()

        block_num, _, block_szx = _get_block_opt(request)

        total_block_count = _block_count(len(self.image_resource.data), block_szx)

        self._update_progress_bar(request.remote.addr,
                                  self.clients[request.remote],
                                  block_num,
                                  total_block_count)

        if (self.clients[request.remote].last_block is None) or (self.clients[request.remote].last_block < block_num):
                self.clients[request.remote].last_block = block_num

        if block_num == total_block_count - 1:
            self.clients[request.remote].last_block = None
            click.echo() # New line after progress bar
            click.echo("Thread DFU upload complete")

        return piccata.block_transfer.create_block_2_response(self.image_resource.data, request)

    def _handle_init_request(self, request):
        # Add remote to the list of prospective DFU clients
        if (request.remote not in self.clients):
            self.clients[request.remote] = ThreadDfuClient()
            logger.debug("Added {} to clients".format(request.remote.addr))

        return piccata.block_transfer.create_block_2_response(self.init_resource.data, request)

    def _handle_trigger_response(self, result, request, response, num_of_requests):
        assert (result == piccata.constants.RESULT_TIMEOUT)

        if (num_of_requests - 1 > 0):
            self.protocol.request(request,
                                  self._handle_trigger_response,
                                  (num_of_requests - 1,))
            return

        self.trig_done_event.set()

    def _handle_trigger_request(self, request):
        response = None
        if request.mtype == piccata.constants.CON:
            response = Message.AckMessage(request,
                                          constants.CONTENT,
                                          _make_trigger(self.init_resource.data,
                                                        self.image_resource.data,
                                                        False,
                                                        self.opts.reset_suppress))
        else:
            if self.opts.mcast_dfu:
                address = self.REALM_LOCAL_ADDR
            else:
                address = request.remote.addr

            self.trigger(address, 3)

        return response

    def _send_block(self, remote, path, num, more, szx, payload):
        '''
        Send a single block.
        :param remote: An address of the remote endpoint.
        :param path: An URI path to the block resource.
        :param num: A block number. Part of the CoAP block option.
        :param more: An information if more blocks are pending. Part of the CoAP block option.
        :param szx: A block size, encoded in CoAP block option format. Part of the CoAP block option.
        :param payload: A block payload.
        '''
        logger.info('Sending block {} to {}'.format(num, remote.addr))

        request = piccata.message.Message(mtype = piccata.constants.NON,
                                          code = piccata.constants.PUT)

        request.opt.uri_path = path
        request.opt.block1 = (num, more, szx)
        request.remote = remote
        request.payload = payload

        self.protocol.request(request)

    def _upload(self, remote, bitmap):
        while True:
            # Bitmap holds (resource, num) tuples. Sort them using path and block num.
            bitmap.sort(key = lambda item : (item[0].path[0] == ThreadDfuServer.IMAGE_URI, item[1]))
            resource, num = bitmap.pop(0)

            payload, more = extract_block(resource.data,
                                          num,
                                          ThreadDfuServer.BLOCK_SZX)

            logger.debug("Uploading resource {} block {} to {}".format(resource.path, num, remote.addr))

            total_block_count = _block_count(len(resource.data), ThreadDfuServer.BLOCK_SZX)

            self._update_progress_bar(remote.addr,
                                      self.clients[remote],
                                      num,
                                      total_block_count)

            self._send_block(remote,
                             resource.path,
                             num,
                             more,
                             ThreadDfuServer.BLOCK_SZX,
                             payload)

            if (self.clients[remote].last_block is None) or (self.clients[remote].last_block < num):
                self.clients[remote].last_block = num

            if num == total_block_count - 1:
                self.clients[remote].last_block = None

            self.bmp_received_event.clear()
            if len(bitmap):
                if (num % ThreadDfuServer.SPBLK_SIZE == 0) or (((num + 1) % ThreadDfuServer.SPBLK_SIZE) == 0):
                    delay = ThreadDfuServer.ERASE_DELAY
                else:
                    delay = 1.0/self.opts.rate

                time.sleep(delay)

            else:
                self.upload_done_event.set()
                self.bmp_received_event.wait()

    def _handle_reset_response(self, result, request, response, num_of_requests, delay):
        assert (result == piccata.constants.RESULT_TIMEOUT)

        if (num_of_requests - 1 > 0):
            self.protocol.request(request,
                                  self._handle_reset_response,
                                  (num_of_requests - 1, delay))

    def _send_reset_request(self, remote, num_of_requests, delay):
        logger.info('Sending reset request to {}'.format(remote))

        request = piccata.message.Message(mtype = piccata.constants.NON,
                                          code = piccata.constants.PUT,
                                          token = self._draw_token())

        request.opt.uri_path = (b"r",)
        request.remote = remote
        request.timeout = ThreadDfuServer.SPBLK_BMP_TIMEOUT
        request.payload = struct.pack(">I", delay)

        self.protocol.request(request,
                              self._handle_reset_response,
                              (num_of_requests, delay))

    def _handle_bitmap_request(self, request):
        payload = struct.unpack('!HQ', request.payload)
        num = payload[0]
        bmp = payload[1]
        path = request.opt.uri_path[1]
        logger.debug("Device {} returned path {} num {} bmp {}".format(request.remote.addr,
                                                                       path,
                                                                       num,
                                                                       _bmp_to_str(bmp)))

        if (path == ThreadDfuServer.INIT_URI):
            resource = self.init_resource
        elif (path == ThreadDfuServer.IMAGE_URI):
            resource = self.image_resource

        for i in range(ThreadDfuServer.SPBLK_SIZE):
            item = (resource, num + i)
            if (bmp & (1 << (ThreadDfuServer.SPBLK_SIZE - 1 - i)) and item not in self.missing_blocks):
                self.missing_blocks.append(item)
                logger.debug("Added {} block {} to missing list".format(item[0].path, item[1]))

        self.bmp_received_event.set()
        return None

    def receive_request(self, request):
        '''Request callback called by the CoAP toolkit. Note that the function
           signature (name, args) is expected by the CoAP toolkit.'''

        # TODO: consider a case where there is a mcast DFU in progress
        #       but a request is received. How this should be handled?

        handlers = {
            ThreadDfuServer.IMAGE_URI : self._handle_image_request,
            ThreadDfuServer.INIT_URI : self._handle_init_request,
            ThreadDfuServer.TRIGGER_URI : self._handle_trigger_request,
            ThreadDfuServer.BITMAP_URI : self._handle_bitmap_request,
        }

        for uri, handler in list(handlers.items()):
            if b'/'.join(request.opt.uri_path).startswith(uri):
                return handler(request)

        return piccata.message.Message.AckMessage(request, piccata.constants.NOT_FOUND)

    def _multicast_upload(self, remote, num_of_requests):
        self.upload_done_event.clear()

        click.echo("Waiting 20s before starting multicast DFU procedure")
        time.sleep(20)

        self.missing_blocks.extend(_make_bitmap(self.init_resource))
        self.missing_blocks.extend(_make_bitmap(self.image_resource))

        self.clients[remote] = ThreadDfuClient()

        self.bmp_received_event.set()

        self._send_trigger(remote, num_of_requests)
        self.trig_done_event.wait()

        if self.upload_thread is None or self.upload_thread.is_alive() is False:
            self.upload_thread = threading.Thread(target = self._upload,
                                                  name = "Upload thread",
                                                  args = (remote, self.missing_blocks))
            self.upload_thread.setDaemon(True)
            self.upload_thread.start()

        time.sleep(15)
        self.upload_done_event.wait()

        if (self.opts.reset_suppress > 0):
            self._send_reset_request(remote, num_of_requests, self.opts.reset_suppress)

        click.echo() # New line after progress bar
        click.echo("Thread DFU upload complete")

    def _send_trigger(self, remote, num_of_requests):
        logger.info('Triggering DFU on {}'.format(remote))
        request = piccata.message.Message(mtype = piccata.constants.NON,
                                          code = piccata.constants.POST,
                                          token = self._draw_token())

        request.opt.uri_path = (ThreadDfuServer.TRIGGER_URI,)
        request.remote = remote
        request.timeout = ThreadDfuServer.SPBLK_BMP_TIMEOUT
        request.payload = _make_trigger(self.init_resource.data,
                                        self.image_resource.data,
                                        self.opts.mcast_dfu,
                                        self.opts.reset_suppress)
        self.protocol.request(request,
                              self._handle_trigger_response,
                              (num_of_requests,))

    def trigger(self, address, num_of_requests):
        remote = piccata.types.Endpoint(address, piccata.constants.COAP_PORT)

        if self.opts.mcast_dfu:
            if self.upload_done_event.is_set():
                thread = threading.Thread(target = self._multicast_upload,
                                          args = (remote, num_of_requests, ))
                thread.setDaemon(True)
                thread.start()
        else:
            self._send_trigger(remote, num_of_requests)
