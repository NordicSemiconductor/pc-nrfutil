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


class HexType(object):
    SOFTDEVICE = 1
    BOOTLOADER = 2
    SD_BL = 3
    APPLICATION = 4


class FirmwareKeys(Enum):
    ENCRYPT = 1
    FIRMWARE_FILENAME = 2
    BIN_FILENAME = 3
    DAT_FILENAME = 4
    INIT_PACKET_DATA = 5
    SD_SIZE = 6
    BL_SIZE = 7
