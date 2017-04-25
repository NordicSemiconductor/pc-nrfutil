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
import time
import logging
import ipaddress

import io
import spinel.common
import spinel.ipv6

from spinel.stream import StreamOpen
from spinel.codec import WpanApi
from spinel.const import SPINEL

logger = logging.getLogger(__name__)

class Proxy:
    CFG_KEY_CHANNEL = 'channel'
    CFG_KEY_PANID = 'panid'
    CFG_KEY_RESET = 'reset'
    
    udp6_parser = spinel.ipv6.IPv6PacketFactory(
        ulpf = {
            17: spinel.ipv6.UDPDatagramFactory(
                udp_header_factory = spinel.ipv6.UDPHeaderFactory(),
                dst_port_factories = {
                    5683: spinel.ipv6.UDPBytesPayloadFactory()
                }
            ),
        }
    )
    
    def __init__(self, stream_descriptor, config = None, recv_callback = None):
        assert recv_callback is not None
        self._stream_descriptor = stream_descriptor.split(":")
        self._receive_callback = recv_callback
        self._attached = False
        self._config = config if config is not None else self.get_default_config()
        
    @staticmethod
    def _propid_to_str(propid):
        for name, value in SPINEL.__dict__.iteritems():
            if (name.startswith('PROP_') and value == propid):
                return name

    def _set_property(self, *args):
        for propid, value, py_format in args:
            logger.debug("Setting property %s to %s", Proxy._propid_to_str(propid), str(value))
            result = self._wpan.prop_set_value(propid, value, py_format)
            if (result is None):
                raise Exception("Failed to set property {}".format(Proxy._propid_to_str(propid)))
            else:
                logger.debug("Done")

    def _get_property(self, *args):
        return self._wpan.prop_get_value(SPINEL.PROP_LAST_STATUS)

    def _attach_to_network(self):
        props = [
            (SPINEL.PROP_IPv6_ICMP_PING_OFFLOAD, 1, 'B'),
            (SPINEL.PROP_PHY_CHAN, self._config[Proxy.CFG_KEY_CHANNEL], 'H'),
            (SPINEL.PROP_MAC_15_4_PANID, self._config[Proxy.CFG_KEY_PANID], 'H'),
            (SPINEL.PROP_NET_IF_UP, 1, 'B'),
            (SPINEL.PROP_NET_STACK_UP, 2, 'B'),
        ]
        self._set_property(*props)

        while True:
            role = self._wpan.prop_get_value(SPINEL.PROP_NET_ROLE)
            if (role != 0):
                self._attached = True
                return True
            time.sleep(1)

        return False

    def _receive(self, prop, value, tid):
        consumed = False

        if prop == SPINEL.PROP_STREAM_NET:
            consumed = True
            try:
                pkt = self.udp6_parser.parse(io.BytesIO(value[2:]),
                                             spinel.common.MessageInfo())
                
                #TODO: Remove conversion from IPV6 to string once twisted
                #      is removed.
                self._receive_callback(str(pkt.ipv6_header.source_address),
                                       pkt.upper_layer_protocol.header.src_port,
                                       str(pkt.ipv6_header.destination_address),
                                       pkt.upper_layer_protocol.header.dst_port,
                                       str(pkt.upper_layer_protocol.payload.to_bytes()))
            except RuntimeError:
                pass
            except Exception as e:
                logging.exception(e)

        return consumed

    def _build_udp_datagram(self, saddr, sport, daddr, dport, payload):
        return spinel.ipv6.IPv6Packet(spinel.ipv6.IPv6Header(saddr, daddr), 
                                      spinel.ipv6.UDPDatagram(
                                          spinel.ipv6.UDPHeader(sport, dport),
                                          spinel.ipv6.UDPBytesPayload(payload)))

    @staticmethod
    def get_default_config():
        return {Proxy.CFG_KEY_CHANNEL: 11,
                Proxy.CFG_KEY_PANID:   0xabcd,
                Proxy.CFG_KEY_RESET:   True}

    def add_ip_address(self, ipaddr):
        valid = 1
        preferred = 1
        flags = 0
        prefix_len = 64

        prefix = ipaddress.IPv6Interface(unicode(ipaddr))
        arr = prefix.ip.packed
        arr += self._wpan.encode_fields('CLLC',
                                           prefix_len,
                                           valid,
                                           preferred,
                                           flags)

        self._wpan.prop_insert_value(SPINEL.PROP_IPV6_ADDRESS_TABLE, arr, str(len(arr)) + 's')
        logger.debug("Added")

    def send(self, src, sport, dst, dport, payload):
        logger.debug("Sending datagram {} {} {} {}".format(src, sport, dst, dport))
        if (src is None):
            src = self._src_addr
        try:
            datagram = self._build_udp_datagram(src, sport, dst, dport, payload)
        except Exception as e:
            logging.exception('Sending failed')          
        
        self._wpan.ip_send(str(datagram.to_bytes()))

    def print_addresses(self):
        for addr in self._wpan.get_ipaddrs():
            logger.info(unicode(addr))

    def connect(self):
        self._stream = StreamOpen(self._stream_descriptor[0], self._stream_descriptor[1])
        # FIXME: remove node id from constructor after WpanAPI is refactored
        self._wpan = WpanApi(self._stream, 666)
        self._wpan.queue_register(SPINEL.HEADER_DEFAULT)
        self._wpan.queue_register(SPINEL.HEADER_ASYNC)
        self._wpan.callback_register(SPINEL.PROP_STREAM_NET, self._receive)


        if (self._config[Proxy.CFG_KEY_RESET]) and not self._wpan.cmd_reset():
            raise Exception('Failed to reset NCP. Please flash connectvity firmware.')

        logger.info('Attaching to the network')
        if (not self._attach_to_network()):
            logger.error("Failed to attach to the network")
            raise Exception('Unable to attach')

        self._src_addr = str(ipaddress.IPv6Address(self._wpan.prop_get_value(SPINEL.PROP_IPV6_ML_ADDR)))

        logger.info("Done")

        self.print_addresses()

    def disconnect(self):
        self._wpan.cmd_reset()
        self._stream.close()