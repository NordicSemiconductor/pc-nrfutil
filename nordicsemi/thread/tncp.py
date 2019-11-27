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
import struct

import io
import spinel.common
import spinel.ipv6

from spinel.stream import StreamOpen
from spinel.codec import WpanApi
from spinel.const import SPINEL
import collections
import spinel.util as util

logger = logging.getLogger(__name__)

class NCPTransport:
    '''A CoAP Toolkit compatible transport'''
    CFG_KEY_CHANNEL = 'channel'
    CFG_KEY_PANID = 'panid'
    CFG_KEY_RESET = 'reset'
    CFG_KEY_MASTERKEY = 'masterkey'

    def __init__(self, port, stream_descriptor, config = None):
        self._port = port
        self._stream_descriptor = stream_descriptor.split(":")
        self._config = config if config is not None else self.get_default_config()
        self._attached = False

        self._udp6_parser = spinel.ipv6.IPv6PacketFactory(
                            ulpf = {
                                17: spinel.ipv6.UDPDatagramFactory(
                                    udp_header_factory = spinel.ipv6.UDPHeaderFactory(),
                                    dst_port_factories = {
                                        port: spinel.ipv6.UDPBytesPayloadFactory()
                                        }
                                    ),
                            })

        self._receivers = []

    @staticmethod
    def _propid_to_str(propid):
        for name, value in SPINEL.__dict__.items():
            if (name.startswith('PROP_') and value == propid):
                return name

    def _set_property(self, *args):
        for propid, value, py_format in args:
            logger.debug("Setting property %s to %s", self.__class__._propid_to_str(propid), str(value))
            result = self._wpan.prop_set_value(propid, value, py_format)
            if (result is None):
                raise Exception("Failed to set property {}".format(self.__class__._propid_to_str(propid)))
            else:
                logger.debug("Done")

    def _get_property(self, *args):
        return self._wpan.prop_get_value(SPINEL.PROP_LAST_STATUS)

    def _attach_to_network(self):
        props = [
            (SPINEL.PROP_IPv6_ICMP_PING_OFFLOAD, 1, 'B'),
            (SPINEL.PROP_THREAD_RLOC16_DEBUG_PASSTHRU, 1, 'B'),
            (SPINEL.PROP_PHY_CHAN, self._config[self.CFG_KEY_CHANNEL], 'H'),
            (SPINEL.PROP_MAC_15_4_PANID, self._config[self.CFG_KEY_PANID], 'H'),
            (SPINEL.PROP_NET_MASTER_KEY, self._config[self.CFG_KEY_MASTERKEY], '16s'),
            (SPINEL.PROP_NET_IF_UP, 1, 'B'),
            (SPINEL.PROP_NET_STACK_UP, 1, 'B'),
        ]
        self._set_property(*props)

        while True:
            role = self._wpan.prop_get_value(SPINEL.PROP_NET_ROLE)
            if (role != 0):
                self._attached = True
                return True
            time.sleep(1)

        return False

    def _wpan_receive(self, prop, value, tid):
        consumed = False
        if prop == SPINEL.PROP_STREAM_NET:
            consumed = True
            try:
                pkt = self._udp6_parser.parse(io.BytesIO(value),
                                              spinel.common.MessageInfo())
                endpoint = collections.namedtuple('endpoint', 'addr port')
                payload = pkt.upper_layer_protocol.payload.to_bytes()
                src = endpoint(pkt.ipv6_header.source_address,
                               pkt.upper_layer_protocol.header.src_port)
                dst = endpoint(pkt.ipv6_header.destination_address,
                               pkt.upper_layer_protocol.header.dst_port)

                for receiver in self._receivers:
                    receiver.receive(payload, src, dst)

            except RuntimeError:
                pass
            except Exception as e:
                logging.exception(e)
        else:
            logger.warning("Unexpected property received (PROP_ID: {})".format(prop))

        return consumed

    def _build_udp_datagram(self, saddr, sport, daddr, dport, payload):
        return spinel.ipv6.IPv6Packet(spinel.ipv6.IPv6Header(saddr, daddr),
                                      spinel.ipv6.UDPDatagram(
                                          spinel.ipv6.UDPHeader(sport, dport),
                                          spinel.ipv6.UDPBytesPayload(payload)))

    @classmethod
    def get_default_config(cls):
        return {cls.CFG_KEY_CHANNEL:     11,
                cls.CFG_KEY_PANID:       0xabcd,
                cls.CFG_KEY_RESET:       True,
                cls.CFG_KEY_MASTERKEY:   util.hex_to_bytes("00112233445566778899aabbccddeeff")}

    def add_ip_address(self, ipaddr):
        valid = 1
        preferred = 1
        flags = 0
        prefix_len = 64

        prefix = ipaddress.IPv6Interface(str(ipaddr))
        arr = prefix.ip.packed
        arr += self._wpan.encode_fields('CLLC',
                                           prefix_len,
                                           valid,
                                           preferred,
                                           flags)

        self._wpan.prop_insert_value(SPINEL.PROP_IPV6_ADDRESS_TABLE, arr, str(len(arr)) + 's')
        logger.debug("Added")

    def print_addresses(self):
        logger.info("NCP Thread IPv6 addresses:")
        for addr in self._wpan.get_ipaddrs():
            logger.info(str(addr))

    def send(self, payload, dest):
        if (dest.addr.is_multicast):
            rloc16 = self._wpan.prop_get_value(SPINEL.PROP_THREAD_RLOC16)

            # Create an IPv6 Thread RLOC address from mesh-local prefix and RLOC16 MAC address.
            src_addr = ipaddress.ip_address(self._ml_prefix + b'\x00\x00\x00\xff\xfe\x00' + struct.pack('>H', rloc16))

        else:
            src_addr = self._ml_eid

        logger.debug("Sending datagram {} {} {} {}".format(src_addr,
                                                           self._port,
                                                           dest.addr,
                                                           dest.port))
        try:
            datagram = self._build_udp_datagram(src_addr,
                                                self._port,
                                                dest.addr,
                                                dest.port,
                                                payload)
        except Exception as e:
            logging.exception(e)

        self._wpan.ip_send(datagram.to_bytes())

    def register_receiver(self, callback):
        '''Registers a receiver, that will get all the data received from the transport.
           The callback function shall be in format:
           receive_callback(src_addr, src_port, dest_port, dest_addr, payload)'''
        self._receivers.append(callback)

    def remove_receiver(self, callback):
        '''Remove a receiver callback'''
        self._receivers.remove(callback)

    def open(self):
        '''Opens transport for communication.'''
        self._stream = StreamOpen(self._stream_descriptor[0], self._stream_descriptor[1], False)
        # FIXME: remove node id from constructor after WpanAPI is refactored
        self._wpan = WpanApi(self._stream, 666)
        self._wpan.queue_register(SPINEL.HEADER_DEFAULT)
        self._wpan.queue_register(SPINEL.HEADER_ASYNC)
        self._wpan.callback_register(SPINEL.PROP_STREAM_NET, self._wpan_receive)

        if (self._config[NCPTransport.CFG_KEY_RESET]) and not self._wpan.cmd_reset():
            raise Exception('Failed to reset NCP. Please flash connectivity firmware.')

        logger.info('Attaching to the network')
        if (not self._attach_to_network()):
            logger.error("Failed to attach to the network")
            raise Exception('Unable to attach')

        self._ml_eid = ipaddress.ip_address(self._wpan.prop_get_value(SPINEL.PROP_IPV6_ML_ADDR))
        self._ml_prefix = self._wpan.prop_get_value(SPINEL.PROP_IPV6_ML_PREFIX)

        logger.info("Done")

        self.print_addresses()

    def close(self):
        '''Closes transport for communication.'''
        self._wpan.cmd_reset()
        self._stream.close()
