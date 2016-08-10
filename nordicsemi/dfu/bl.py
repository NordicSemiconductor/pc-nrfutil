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

# Python standard library
import os
import time
import shutil
import logging
import tempfile
import struct
import binascii
from enum import Enum


# Nordic libraries
from nordicsemi.dfu import intelhex
from nordicsemi.dfu.nrfhex import *
from nordicsemi.dfu.package import Package

logger = logging.getLogger(__name__)

class BLSettingsStructV1(object):

    def __init__(self):
        self.uint32_count = (5 + (3 * 2) + 2 + 8 + 1)
        self.offs_crc = 0
        self.offs_blsettv = 0
        self.offs_appv = 1
        self.offs_blv = 2
        self.offs_bank_layout = 3
        self.offs_bank_current = 4
        self.offs_bank0_img_sz = 5
        self.offs_bank0_img_crc = 6
        self.offs_bank0_bank_code = 7


class BootloaderSettings(object):
    """ Class to abstract a bootloader and its settings """

    flash_page_51_sz = 0x400
    flash_page_52_sz = 0x1000
    bl_sett_51_addr= 0x0003FC00
    bl_sett_52_addr= 0x0007F000


    def __init__(self, arch, app_file, app_ver, bl_ver, bl_sett_ver):
        """
        """

        if arch == 'NRF51':
            arch = nRFArch.NRF51
            flash_page_sz = BootloaderSettings.flash_page_51_sz 
            bl_sett_addr = BootloaderSettings.bl_sett_51_addr
        elif arch == 'NRF52':
            arch = nRFArch.NRF52
            flash_page_sz = BootloaderSettings.flash_page_52_sz 
            bl_sett_addr = BootloaderSettings.bl_sett_52_addr
        else:
            raise NordicSemiException("Unknown architecture")

        if bl_sett_ver == 1:
            settstruct = BLSettingsStructV1()
        else:
            raise NordicSemiException("Unknown bootloader settings version")
        
        format_str = '<' + ('I' * settstruct.uint32_count) 

        # load application to find out size and CRC
        self.temp_dir = tempfile.mkdtemp(prefix="nrf_dfu_bl_sett_")

        app_bin = Package.normalize_firmware_to_bin(self.temp_dir, app_file)
        app_sz = int(Package.calculate_file_size(app_bin))
        app_crc = int(Package.calculate_crc(32, app_bin))

        print "app_bin: {0}".format(app_bin)
        print "app_sz: {0}".format(app_sz)
        print "app_crc: %08X" % (app_crc & 0xffffffff)


        # build the uint32_t array
        arr = [0x0] * settstruct.uint32_count

        # fill in the settings
        #arr[offs_blsettv] = bl_sett_ver
        arr[settstruct.offs_appv] = app_ver & 0xffffffff
        arr[settstruct.offs_blv] = bl_ver & 0xffffffff
        arr[settstruct.offs_bank_layout] = 0x1 & 0xffffffff
        arr[settstruct.offs_bank_current] = 0x0 & 0xffffffff
        arr[settstruct.offs_bank0_img_sz] = app_sz & 0xffffffff
        arr[settstruct.offs_bank0_img_crc] = app_crc & 0xffffffff
        arr[settstruct.offs_bank0_bank_code] = 0x1 & 0xffffffff

        # calculate the CRC32 from the filled-in settings
        crc_format_str = '<' + ('I' * (settstruct.uint32_count - 1)) 
        crc_arr = arr[1:]
        crc_data = struct.pack(crc_format_str, *crc_arr)
        crc = binascii.crc32(crc_data, 0xffffffff)
        print "crc: %08X" % (crc & 0xffffffff)

        # fill in the calculated CRC32
        arr[settstruct.offs_crc] = crc & 0xffffffff

        print arr

        # Get the packed data to insert into the hex instance
        data = struct.pack(format_str, *arr)
        
        # instantiate a hex object
        self.ihex = intelhex.IntelHex()
        # insert the data at the correct address
        self.ihex.puts(bl_sett_addr, data)

    def __del__(self):
        """
        Destructor removes the temporary directory
        :return:
        """
        shutil.rmtree(self.temp_dir)


    def tohexfile(self, f):
        self.ihex.tofile(f, format='hex')

