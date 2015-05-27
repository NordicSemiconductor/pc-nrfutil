# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

import unittest
from nordicsemi.dfu.init_packet import *


class TestInitPacket(unittest.TestCase):
    def setUp(self):
        pass

    def test_generate_packet_a(self):
        init_packet_vars = {
            PacketField.PACKET_VERSION: 5,
            PacketField.DEVICE_TYPE: 1,
            PacketField.DEVICE_REVISION: 2,
            PacketField.APP_VERSION: 3,
            PacketField.REQUIRED_SOFTDEVICES_ARRAY: [1111, 2222, 3333, 4444]
        }

        ip = Packet(init_packet_vars)
        data = ip.generate_packet()
        self.assertEqual(data, ("\x05\x00"  # Packet version
                                "\x01\x00"  # Device type
                                "\x02\x00"  # Device revision
                                "\x03\x00\x00\x00"  # App version
                                "\x04\x00"  # Softdevice array length
                                "\x57\x04"  # Softdevice entry #1
                                "\xae\x08"  # Softdevice entry #2
                                "\x05\x0d"  # Softdevice entry #3
                                "\x5c\x11"  # Softdevice entry #4
                                )
                         )

    def test_generate_packet_b(self):
        init_packet_vars = {
            PacketField.PACKET_VERSION: 7,
            PacketField.DEVICE_TYPE: 1,
            PacketField.DEVICE_REVISION: 2,
            PacketField.APP_VERSION: 0xffeeffee,
            PacketField.REQUIRED_SOFTDEVICES_ARRAY: [1111, 2222, 3333],
            PacketField.NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_HASH:
                "\xc9\xd3\xbfi\xf2\x1e\x88\xa01\x1e\r\xd2BSa\x12\xf8BW\x9b\xef&Z$\xbd\x02U\xfdD?u\x9e"
        }

        ip = Packet(init_packet_vars)
        data = ip.generate_packet()
        self.assertEqual(data, ("\x07\x00"  # Packet version
                                "\x01\x00"  # Device type
                                "\x02\x00"  # Device revision
                                "\xee\xff\xee\xff"  # App version
                                "\x03\x00"  # Softdevice array length
                                "\x57\x04"  # Softdevice entry #1
                                "\xae\x08"  # Softdevice entry #2
                                "\x05\x0d"  # Softdevice entry #3
                                "\x21\x00"  # Optional data length
                                "\x20"  # Firmware hash length
                                "\xc9\xd3\xbfi\xf2\x1e\x88\xa01\x1e\r\xd2BSa\x12"  # Firmware hash, part one
                                "\xf8BW\x9b\xef&Z$\xbd\x02U\xfdD?u\x9e"  # Firmware hash, part two
                                )
                         )

    def test_generate_packet_c(self):
        init_packet_vars = {
            PacketField.DEVICE_TYPE: 1,
            PacketField.DEVICE_REVISION: 2,
            PacketField.APP_VERSION: 0xffeeffee,
            PacketField.REQUIRED_SOFTDEVICES_ARRAY: [1111, 2222, 3333],
            PacketField.NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_CRC16: 0xfaae
        }

        ip = Packet(init_packet_vars)
        data = ip.generate_packet()
        self.assertEqual(data, ("\x01\x00"  # Device type
                                "\x02\x00"  # Device revision
                                "\xee\xff\xee\xff"  # App version
                                "\x03\x00"  # Softdevice array length
                                "\x57\x04"  # Softdevice entry #1
                                "\xae\x08"  # Softdevice entry #2
                                "\x05\x0d"  # Softdevice entry #3
                                "\xae\xfa"  # CRC-16 checksum for firmware
                                )
                         )


if __name__ == '__main__':
    unittest.main()
