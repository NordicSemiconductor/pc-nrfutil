# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.


def calc_crc16(binary_data, crc=0xffff):
    """
    Calculates CRC16 on binary_data

    :param int crc: CRC value to start calculation with
    :param bytearray binary_data: Array with data to run CRC16 calculation on
    :return int: Calculated CRC value of binary_data
    """

    for b in binary_data:
        crc = (crc >> 8 & 0x00FF) | (crc << 8 & 0xFF00)
        crc ^= ord(b)
        crc ^= (crc & 0x00FF) >> 4
        crc ^= (crc << 8) << 4
        crc ^= ((crc & 0x00FF) << 4) << 1
    return crc & 0xFFFF
