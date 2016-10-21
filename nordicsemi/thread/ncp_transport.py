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
from __future__ import division, absolute_import

import ncp
import ipaddress

class NcpTransport():
    def __init__(self, port, proto, stream_descriptor = '', config = None):
        """
        @param port: A port number on which to listen.
        @type port: L{int}

        @param proto: A C{DatagramProtocol} instance which will be
            connected to the given C{port}.
        @type proto: L{twisted.internet.protocol.DatagramProtocol}

        @param reactor: A reactor which will notify this C{Port} when
            its socket is ready for reading or writing. Defaults to
            L{None}, ie the default global reactor.
        @type reactor: L{interfaces.IReactorFDSet}
        """
        self.port = port
        self.protocol = proto
        self.ncp = ncp.Proxy(stream_descriptor, config, self._recv_callback)

    def _recv_callback(self, src_addr, src_port, dest_addr, dest_port, payload):
        if (dest_port == self.port):
            self.protocol.datagramReceived(payload, (src_addr.decode('utf-8'), src_port))

    def write(self, datagram, addr = None):
      """
      Write a datagram.

      @type datagram: L{bytes}
      @param datagram: The datagram to be sent.

      @type addr: L{tuple} containing L{str} as first element and L{int} as
        second element, or L{None}
      @param addr: A tuple of (I{stringified IPv4 or IPv6 address},
        I{integer port number}); can be L{None} in connected mode.
      """
      dst = str(ipaddress.IPv6Address(addr[0].decode('utf-8')))
      #TODO: src address provided in ctor as listening interface
      self.ncp.send(None, self.port, dst, addr[1], datagram)

    def startListening(self):
        self.ncp.connect()
        self.protocol.makeConnection(self)

    def stopListening(self):
        self.protocol.doStop()
        self.ncp.disconnect()

    def isConnected(self):
        return self.ncp._attached
