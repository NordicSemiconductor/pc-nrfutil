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
import sys
import threading
import logging
import time
import binascii
import struct
import tqdm

from ipaddress import ip_address
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python.failure import Failure

import txthings.resource as resource
import txthings.coap as coap
import math

logger = logging.getLogger(__name__)

class FileResource(resource.CoAPResource):
    def __init__(self, file_path):
        resource.CoAPResource.__init__(self)
        with open(file_path, 'rb') as f:
            self._content = f.read()

    def length(self):
        return len(self._content)

    def crc(self):
        return binascii.crc32(self._content) & 0xffffffff

    def render_GET(self, request):
        response = coap.Message(code=coap.CONTENT, payload=self._content)
        return defer.succeed(response)

class TriggerResource(resource.CoAPResource):
    VERSION = 0

    def __init__(self, init, image):
        resource.CoAPResource.__init__(self)
        self.init = init
        self.image = image

    def payload(self):
        # Structure format:
        # flags:      uint8_t
        # init size:  uint32_t
        # init crc:   uint32_t
        # image size: uint32_t
        # image crc:  uint32_t
        # prefix:     var len max 16 bytes
        flags = ((TriggerResource.VERSION << 4) & 0x03)
        return struct.pack(">BIIII",
                           flags,
                           self.init.length(),
                           self.init.crc(),
                           self.image.length(),
                           self.image.crc())

    def render_GET(self, request):
        response = coap.Message(code=coap.CONTENT, payload = self.payload())
        return defer.succeed(response)

class DfuServer():
    def __init__(self, transport_factory, init_file, image_file, uri_prefix):
        self.progress = {}

        self.init_resource = FileResource(init_file)
        self.image_resource = FileResource(image_file)
        self.trig_resource = TriggerResource(self.init_resource , self.image_resource)
        self.uri_prefix = uri_prefix

        root = resource.CoAPResource()
        prefix = resource.CoAPResource()
        root.putChild(self.uri_prefix, prefix)

        prefix.putChild('trig', self.trig_resource)
        prefix.putChild('init', self.init_resource)
        prefix.putChild('image', self.image_resource)

        self.endpoint = resource.Endpoint(root)
        self.protocol = coap.Coap(self.endpoint, None, self._response_callback)
        self.transport = transport_factory(self.protocol)

    def _response_callback(self, request, response):
        request.prepath = []
        request.postpath = request.opt.uri_path
        res = self.endpoint.getResourceFor(request)

        if (res and (res == self.image_resource) and response.opt.block2):
            remote_addr = request.remote[0]
            block_num = response.opt.block2.block_number
            block_size = response.opt.block2.size_exponent

            if (remote_addr not in self.progress):
                pbar = tqdm.tqdm(desc = str(remote_addr),
                                 position = len(self.progress),
                                 initial = block_num,
                                 total = int(res.length() / (2 ** (block_size + 4)) + 0.5))
                last_block = None
                self.progress[remote_addr] = (pbar, block_num)
            else:
                pbar, last_block = self.progress[remote_addr]

            if (last_block is not None and (block_num > last_block)):
                pbar.update(block_num - last_block)
                self.progress[remote_addr] = (pbar, block_num)

            if (not response.opt.block2.more):
                pbar.close()

    def _main(self):
        try:
            logger.debug("Starting transport")
            self.transport.startListening()
            logger.debug("Starting reactor")
            reactor.run(installSignalHandlers=False)
            logger.debug("Stopping transport")
            self.transport.stopListening()
        except Exception as e:
            logger.error(e.args[0])

    def _handle_trigger_response(self, response):
        logger.info('Response Code: ' + coap.responses[response.code])
        logger.info('Payload: ' + response.payload)

    def _handle_trigger_error(self, failure, request, num_of_requests):
        if (num_of_requests - 1 > 0):
            request.timeout = 2*request.timeout
            d = self.protocol.request(request)
            d.addCallback(self._handle_trigger_response)
            d.addErrback(self._handle_trigger_error, request, num_of_requests - 1)
        else:
            logger.info("All triggers sent")
        return Failure

    def _trigger(self, address, num_of_requests):
        logger.info('Triggering DFU on {}\r'.format(address))
        request = coap.Message(mtype = coap.NON, code=coap.POST)
        request.opt.uri_path = (self.uri_prefix, "trig",)
        request.remote = (ip_address(address), coap.COAP_PORT)
        request.timeout = coap.ACK_TIMEOUT
        request.payload = self.trig_resource.payload()
        d = self.protocol.request(request)
        d.addCallback(self._handle_trigger_response)
        d.addErrback(self._handle_trigger_error, request, num_of_requests)

    def trigger(self, address, num_of_requests):
        reactor.callFromThread(self._trigger, address, num_of_requests)

    def start(self):
        logger.debug("Starting DfuServer")
        self.thread = threading.Thread(target = self._main)
        self.thread.start()

        while not self.thread.isAlive():
            time.sleep(0.1)

        while not self.transport.isConnected():
            logger.debug("Waiting for server...")
            time.sleep(0.1)
            if (not self.thread.isAlive()):
                raise Exception('DfuServer thread terminated')

        logger.debug("Server ready")

    def stop(self):
        logger.debug("Stopping reactor")
        reactor.callFromThread(reactor.stop)
        logger.debug("Waiting for thread exit")
        self.thread.join()
        logger.debug("Thread done")
