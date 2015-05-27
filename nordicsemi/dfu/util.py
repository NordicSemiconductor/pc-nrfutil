# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

# Nordic libraries
from nordicsemi.exceptions import NordicSemiException


def convert_uint16_to_array(value):
    """
    Converts a int to an array of 2 bytes (little endian)

    :param int value: int value to convert to list
    :return list[int]: list with 2 bytes
    """
    byte0 = value & 0xFF
    byte1 = (value >> 8) & 0xFF
    return [byte0, byte1]


def convert_uint32_to_array(value):
    """
    Converts a int to an array of 4 bytes (little endian)

    :param int value: int value to convert to list
    :return list[int]: list with 4 bytes
    """
    byte0 = value & 0xFF
    byte1 = (value >> 8) & 0xFF
    byte2 = (value >> 16) & 0xFF
    byte3 = (value >> 24) & 0xFF
    return [byte0, byte1, byte2, byte3]


def slip_parts_to_four_bytes(seq, dip, rp, pkt_type, pkt_len):
    """
    Creates a SLIP header.

    For a description of the SLIP header go to:
    http://developer.nordicsemi.com/nRF51_SDK/doc/7.2.0/s110/html/a00093.html

    :param int seq: Packet sequence number
    :param int dip: Data integrity check
    :param int rp: Reliable packet
    :param pkt_type: Payload packet
    :param pkt_len: Packet length
    :return: str with SLIP header
    """
    ints = [0, 0, 0, 0]
    ints[0] = seq | (((seq + 1) % 8) << 3) | (dip << 6) | (rp << 7)
    ints[1] = pkt_type | ((pkt_len & 0x000F) << 4)
    ints[2] = (pkt_len & 0x0FF0) >> 4
    ints[3] = (~(sum(ints[0:3])) + 1) & 0xFF

    return ''.join(chr(b) for b in ints)


def int32_to_bytes(value):
    """
    Converts a int to a str with 4 bytes

    :param value: int value to convert
    :return: str with 4 bytes
    """
    ints = [0, 0, 0, 0]
    ints[0] = (value & 0x000000FF)
    ints[1] = (value & 0x0000FF00) >> 8
    ints[2] = (value & 0x00FF0000) >> 16
    ints[3] = (value & 0xFF000000) >> 24
    return ''.join(chr(b) for b in ints)


def int16_to_bytes(value):
    """
    Converts a int to a str with 4 bytes

    :param value: int value to convert
    :return: str with 4 bytes
    """

    ints = [0, 0]
    ints[0] = (value & 0x00FF)
    ints[1] = (value & 0xFF00) >> 8
    return ''.join(chr(b) for b in ints)


def slip_decode_esc_chars(data):
    """Decode esc characters in a SLIP package.

    Replaces 0xDBDC with 0xCO and 0xDBDD with 0xDB.

    :return: str decoded data
    :type str data: data to decode
    """
    result = []
    while len(data):
        char = data.pop(0)
        if char == 0xDB:
            char2 = data.pop(0)
            if char2 == 0xDC:
                result.append(0xC0)
            elif char2 == 0xDD:
                result.append(0xDB)
            else:
                raise NordicSemiException('Char 0xDB NOT followed by 0xDC or 0xDD')
        else:
            result.append(char)
    return result


def slip_encode_esc_chars(data_in):
    """Encode esc characters in a SLIP package.

    Replace 0xCO  with 0xDBDC and 0xDB with 0xDBDD.

     :type str data_in: str to encode
     :return: str with encoded packet
    """
    result = []
    data = []
    for i in data_in:
        data.append(ord(i))

    while len(data):
        char = data.pop(0)
        if char == 0xC0:
            result.extend([0xDB, 0xDC])
        elif char == 0xDB:
            result.extend([0xDB, 0xDD])
        else:
            result.append(char)
    return ''.join(chr(i) for i in result)
