# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

import json
import unittest
from nordicsemi.bluetooth.hci.slip import Slip
from nordicsemi.bluetooth.hci import codec


class TestInitPacket(unittest.TestCase):
    def setUp(self):
        pass

    def test_decode_packet(self):
        # TODO: extend this test, this tests only a small portion of the slip/hci decoding
        # These are packets read from Device Monitoring Studio
        # during communication between serializer application and firmware
        read_packets = [
            " C0 10 00 00 F0 C0 C0 D1 6E 00 C1 01 86 00 00 00 00 17 63 C0",
            " C0 D2 DE 02 4E 02 1B 00 FF FF 01 17 FE B4 9A 9D E1 B0 F8 02"
            " 01 06 11 07 1B C5 D5 A5 02 00 A9 B7 E2 11 A4 C6 00 FE E7 74"
            " 09 09 49 44 54 57 32 31 38 48 5A BB C0",
            " C0 D3 EE 00 3F 02 1B 00 FF FF 01 17 FE B4 9A 9D E1 AF 01 F1 62 C0",
            " C0 D4 DE 02 4C 02 1B 00 FF FF 01 17 FE B4 9A 9D E1 B1 F8 02 01 06"
            " 11 07 1B C5 D5 A5 02 00 A9 B7 E2 11 A4 C6 00 FE E7 74 09 09 49 44 54 57 32 31 38 48 6E C8 C0"
        ]

        slip = Slip()
        output = list()

        for uart_packet in read_packets:
            hex_string = uart_packet.replace(" ", "")
            hex_data = hex_string.decode("hex")
            slip.append(hex_data)

        packets = slip.decode()

        for packet in packets:
            output.append(codec.ThreeWireUartPacket.decode(packet))

        self.assertEqual(len(output), 5)

        packet_index = 0
        self.assertEqual(output[packet_index].seq, 0)

        packet_index += 1
        self.assertEqual(output[packet_index].seq, 1)

        packet_index += 1
        self.assertEqual(output[packet_index].seq, 2)

        packet_index += 1
        self.assertEqual(output[packet_index].seq, 3)

        packet_index += 1
        self.assertEqual(output[packet_index].seq, 4)
