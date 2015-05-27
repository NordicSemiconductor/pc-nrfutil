# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

from enum import Enum
import struct


class PacketField(Enum):
    PACKET_VERSION = 1
    COMPRESSION_TYPE = 2
    DEVICE_TYPE = 3
    DEVICE_REVISION = 4
    APP_VERSION = 5
    REQUIRED_SOFTDEVICES_ARRAY = 6
    OPT_DATA = 7
    NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_HASH = 8
    NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_CRC16 = 9


class Packet(object):
    """
    Class that implements the INIT packet format.
    http://developer.nordicsemi.com/nRF51_SDK/doc/7.1.0/s110/html/a00065.html
    """

    UNSIGNED_SHORT = "H"
    UNSIGNED_INT = "I"
    UNSIGNED_CHAR = "B"
    CHAR_ARRAY = "s"

    def __init__(self, init_packet_fields):
        """

            :param init_packet_fields: Dictionary with packet fields
        """
        self.init_packet_fields = init_packet_fields

    def generate_packet(self):
        """
        Generates a binary packet from provided init_packet_fields provided in constructor.

        :return str: Returns a string representing the init_packet (in binary)

        """
        # Create struct format string based on keys that are
        # present in self.init_packet_fields
        format_string = self.__generate_struct_format_string()
        args = []

        for key in sorted(self.init_packet_fields.keys(), key=lambda x: x.value):
            # Add length to fields that required that
            if key in [PacketField.REQUIRED_SOFTDEVICES_ARRAY,
                       PacketField.OPT_DATA]:
                args.append(len(self.init_packet_fields[key]))
                args.extend(self.init_packet_fields[key])
            elif key in [PacketField.NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_HASH]:
                hash_length = len(self.init_packet_fields[key])
                args.append(hash_length + 1)  # Optional data length
                args.append(hash_length)  # Firmware hash length
                args.append(self.init_packet_fields[key])  # Firmware hash
            else:
                args.append(self.init_packet_fields[key])

        return struct.pack(format_string, *args)

    def __generate_struct_format_string(self):
        format_string = "<"  # Use little endian format with standard sizes for python,
        # see https://docs.python.org/2/library/struct.html

        for key in sorted(self.init_packet_fields.keys(), key=lambda x: x.value):
            if key in [PacketField.PACKET_VERSION,
                       PacketField.COMPRESSION_TYPE,
                       PacketField.DEVICE_TYPE,
                       PacketField.DEVICE_REVISION,
                       ]:
                format_string += Packet.UNSIGNED_SHORT

            elif key in [PacketField.APP_VERSION]:
                format_string += Packet.UNSIGNED_INT
            elif key in [PacketField.REQUIRED_SOFTDEVICES_ARRAY]:
                array_elements = self.init_packet_fields[key]
                format_string += Packet.UNSIGNED_SHORT  # Add length field to format packet

                for _ in range(len(array_elements)):
                    format_string += Packet.UNSIGNED_SHORT
            elif key in [PacketField.OPT_DATA]:
                format_string += Packet.UNSIGNED_SHORT  # Add length field to optional data
                format_string += "{0}{1}".format(len(self.init_packet_fields[key]), Packet.CHAR_ARRAY)
            elif key == PacketField.NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_HASH:
                format_string += Packet.UNSIGNED_SHORT  # Add length field to optional data
                format_string += Packet.UNSIGNED_CHAR  # Add firmware hash length
                format_string += "32{0}".format(Packet.CHAR_ARRAY)  # SHA-256 requires 32 bytes
            elif key == PacketField.NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_CRC16:
                format_string += Packet.UNSIGNED_SHORT

        return format_string
