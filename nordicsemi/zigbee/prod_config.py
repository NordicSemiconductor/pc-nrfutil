#
# Copyright (c) 2018 Nordic Semiconductor ASA
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

import crcmod.predefined
import struct
import intelhex
import yaml


class ProductionConfigWrongException(Exception):
    pass


class ProductionConfigTooLargeException(Exception):
    def __init__(self, length):
        self.length = length


class ProductionConfig:
    SIZE_MAX = 128
    MAGIC_NUMBER = 0xF6DD37E7
    VERSION = 1
    HEADER_FORMAT = '<HHLQ16s16sH'
    OFFSETS = {
        "SDK 3.x": {
            "nRF52840": 0xFC000,
        },
        "SDK 4.x": {
            "nRF52840": 0xFF000,
            "nRF52833": 0x7F000,
        }
    }
    DEFAULT_OFFSET_SDK = "SDK 3.x"
    DEFAULT_OFFSET_CHIP = "nRF52840"
    DEFAULT_OFFSET = OFFSETS[DEFAULT_OFFSET_SDK][DEFAULT_OFFSET_CHIP]
    DEFAULT_CHANNEL = 0x07FFF800

    @classmethod
    def offset_help(cls):
        return format_offsets(cls.OFFSETS)

    def __init__(self, path):
        self._parsed_values = {}
        self._crc16 = crcmod.predefined.mkPredefinedCrcFun('x-25')

        try:
            # Open the YAML file
            with open(path, 'r') as f:
                self._yaml = yaml.load(f, Loader=yaml.FullLoader)

        except yaml.YAMLError as e:
            raise ProductionConfigWrongException

        try:
            # Handle the channel mask
            if "channel_mask" not in self._yaml:
                self._parsed_values["channel_mask"] = self.DEFAULT_CHANNEL
            else:
                self._parsed_values["channel_mask"] = self._yaml["channel_mask"]

            # Handle the EUI64 extended address
            if "extended_address" not in self._yaml:
                self._parsed_values["extended_address"] = 0  # int('0000000000000000', 16)
            else:
                self._parsed_values["extended_address"] = int(self._yaml["extended_address"], 16)

            # Handle the Install code
            if "install_code" not in self._yaml:
                self._parsed_values["install_code"] = bytes(16)
                self._ic_crc = 0
            else:
                self._parsed_values["install_code"] = bytes.fromhex(self._yaml["install_code"])
                self._ic_crc = self._crc16(self._parsed_values["install_code"])

            # Handle the Transmission Power
            if "tx_power" not in self._yaml:
                self._parsed_values["tx_power"] = bytes(16)
            else:
                self._parsed_values["tx_power"] = bytes([self._yaml["tx_power"]] * 16)

            # Handle Application Data (optional)
            if "app_data" not in self._yaml:
                self._parsed_values["app_data"] = b''
                self._ad_len = 0
            else:
                self._parsed_values["app_data"] = bytes.fromhex(self._yaml["app_data"])
                self._ad_len = len(self._parsed_values["app_data"])

        except (TypeError, ValueError) as e:
            raise ProductionConfigWrongException

    def _custom_crc32(self, data):
        '''
            Adapted from C routine inside the Zigbee stack - custom CRC32 that guards the Production Config
        '''
        ZB_CRC32_POLY = 0x04C11DB7
        crc = 0
        for d in data:
            c  = ((( crc ^ d ) & 0xff) << 24)
            for j in range(8):
                if c & 0x80000000:
                    c = (c << 1) ^ ZB_CRC32_POLY
                else:
                    c = (c << 1)
            crc = (0xFFFFFFFF & ((crc >> 8) ^ c))
        return (~crc & 0xFFFFFFFF)

    def generate(self, path, offset=DEFAULT_OFFSET):
        # Calculate the CRC-16 of the install code
        self._struct = (struct.pack(self.HEADER_FORMAT,
                                    struct.calcsize(self.HEADER_FORMAT) + 4 + self._ad_len,  # Plus the CRC-32; plus the app_data
                                    self.VERSION,
                                    self._parsed_values["channel_mask"],
                                    self._parsed_values["extended_address"],
                                    self._parsed_values["tx_power"],
                                    self._parsed_values["install_code"],
                                    self._ic_crc) +
                                   self._parsed_values["app_data"])

        crc32 = self._custom_crc32(self._struct)

        output = struct.pack('<L', self.MAGIC_NUMBER) + struct.pack('<L', crc32) + self._struct

        if len(output) > self.SIZE_MAX + 4: # 4 is for Magic Number
            raise ProductionConfigTooLargeException(len(output))

        ih = intelhex.IntelHex()
        ih.puts(offset, output)
        ih.write_hex_file(path)


def format_offsets(offset_dict: dict):
    result = ""
    for sdk, boards in offset_dict.items():
        result += f"{sdk}:\n"
        for board, offset in boards.items():
            result += f"- {board}: {hex(offset)}\n"
    return result
