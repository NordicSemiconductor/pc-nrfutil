# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

import logging

logger = logging.getLogger(__name__)


class Slip(object):
    def __init__(self):
        self.SLIP_END = '\xc0'
        self.SLIP_ESC = '\xdb'
        self.SLIP_ESC_END = '\xdc'
        self.SLIP_ESC_ESC = '\xdd'

        self.started = False
        self.escaped = False
        self.stream = ''
        self.packet = ''

    def append(self, data):
        """
        Append a new
        :param data: Append a new block of data to do decoding on when calling decode.
        The developer may add more than one SLIP packet before calling decode.
        :return:
        """
        self.stream += data

    def decode(self):
        """
        Decodes a package according to http://en.wikipedia.org/wiki/Serial_Line_Internet_Protocol
        :return Slip: A list of decoded slip packets
        """
        packet_list = list()

        for char in self.stream:
            if char == self.SLIP_END:
                if self.started:
                    if len(self.packet) > 0:
                        self.started = False
                        packet_list.append(self.packet)
                        self.packet = ''
                else:
                    self.started = True
                    self.packet = ''
            elif char == self.SLIP_ESC:
                self.escaped = True
            elif char == self.SLIP_ESC_END:
                if self.escaped:
                    self.packet += self.SLIP_END
                    self.escaped = False
                else:
                    self.packet += char
            elif char == self.SLIP_ESC_ESC:
                if self.escaped:
                    self.packet += self.SLIP_ESC
                    self.escaped = False
                else:
                    self.packet += char
            else:
                if self.escaped:
                    logging.error("Error in SLIP packet, ignoring error.")
                    self.packet = ''
                    self.escaped = False
                else:
                    self.packet += char

        self.stream = ''

        return packet_list

    def encode(self, packet):
        """
        Encode a packet according to SLIP.
        :param packet: A str array that represents the package
        :return: str array with an encoded SLIP packet
        """
        encoded = self.SLIP_END

        for char in packet:
            if char == self.SLIP_END:
                encoded += self.SLIP_ESC + self.SLIP_ESC_END
            elif char == self.SLIP_ESC:
                encoded += self.SLIP_ESC + self.SLIP_ESC_ESC
            else:
                encoded += char
        encoded += self.SLIP_END

        return encoded
