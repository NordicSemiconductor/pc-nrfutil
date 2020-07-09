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
import shutil
import logging
import tempfile
import struct
import binascii

# 3rd party libraries
import intelhex

# Nordic libraries
from nordicsemi.dfu.nrfhex import nRFArch
from nordicsemi.dfu.package import Package
from pc_ble_driver_py.exceptions import NordicSemiException

logger = logging.getLogger(__name__)

class BLDFUSettingsStructV1:

    def __init__(self, settings_address):
        self.bytes_count = 92
        self.crc               = settings_address + 0x0
        self.sett_ver          = settings_address + 0x4
        self.app_ver           = settings_address + 0x8
        self.bl_ver            = settings_address + 0xC
        self.bank_layout       = settings_address + 0x10
        self.bank_current      = settings_address + 0x14
        self.bank0_img_sz      = settings_address + 0x18
        self.bank0_img_crc     = settings_address + 0x1C
        self.bank0_bank_code   = settings_address + 0x20
        self.sd_sz             = settings_address + 0x34

        self.init_cmd          = settings_address + 0x5C
        self.last_addr         = settings_address + 0x5C


class BLDFUSettingsStructV2:

    def __init__(self, settings_address):
        self.bytes_count = 803 # Entire settings page
        self.crc                  = settings_address + 0x0
        self.sett_ver             = settings_address + 0x4
        self.app_ver              = settings_address + 0x8
        self.bl_ver               = settings_address + 0xC
        self.bank_layout          = settings_address + 0x10
        self.bank_current         = settings_address + 0x14
        self.bank0_img_sz         = settings_address + 0x18
        self.bank0_img_crc        = settings_address + 0x1C
        self.bank0_bank_code      = settings_address + 0x20
        self.sd_sz                = settings_address + 0x34
        self.init_cmd             = settings_address + 0x5C

        self.boot_validataion_crc = settings_address + 0x25C
        self.sd_validation_type   = settings_address + 0x260
        self.sd_validation_bytes  = settings_address + 0x261
        self.app_validation_type  = settings_address + 0x2A1
        self.app_validation_bytes = settings_address + 0x2A2

        self.last_addr            = settings_address + 0x322


class BLDFUSettings:
    """ Class to abstract a bootloader and its settings """

    flash_page_51_sz      = 0x400
    flash_page_52_sz      = 0x1000
    bl_sett_51_addr       = 0x0003FC00
    bl_sett_52_addr       = 0x0007F000
    bl_sett_52_qfab_addr  = 0x0003F000
    bl_sett_52810_addr    = 0x0002F000
    bl_sett_52840_addr    = 0x000FF000
    bl_sett_backup_offset = 0x1000

    def __init__(self):
        """
        """
        # instantiate a hex object
        self.ihex = intelhex.IntelHex()
        self.temp_dir = None
        self.hex_file = ""

    def __del__(self):
        """
        Destructor removes the temporary directory
        :return:
        """
        if self.temp_dir is not None:
            shutil.rmtree(self.temp_dir)

    def set_arch(self, arch):
        if arch == 'NRF51':
            self.arch = nRFArch.NRF51
            self.arch_str = 'nRF51'
            self.flash_page_sz = BLDFUSettings.flash_page_51_sz
            self.bl_sett_addr = BLDFUSettings.bl_sett_51_addr
        elif arch == 'NRF52':
            self.arch = nRFArch.NRF52
            self.arch_str = 'nRF52'
            self.flash_page_sz = BLDFUSettings.flash_page_52_sz
            self.bl_sett_addr = BLDFUSettings.bl_sett_52_addr
        elif arch == 'NRF52QFAB':
            self.arch = nRFArch.NRF52
            self.arch_str = 'nRF52QFAB'
            self.flash_page_sz = BLDFUSettings.flash_page_52_sz
            self.bl_sett_addr = BLDFUSettings.bl_sett_52_qfab_addr
        elif arch == 'NRF52810':
            self.arch = nRFArch.NRF52
            self.arch_str = 'NRF52810'
            self.flash_page_sz = BLDFUSettings.flash_page_52_sz
            self.bl_sett_addr = BLDFUSettings.bl_sett_52810_addr
        elif arch == 'NRF52840':
            self.arch = nRFArch.NRF52840
            self.arch_str = 'NRF52840'
            self.flash_page_sz = BLDFUSettings.flash_page_52_sz
            self.bl_sett_addr = BLDFUSettings.bl_sett_52840_addr
        else:
            raise RuntimeError("Unknown architecture")

    def _add_value_tohex(self, addr, value, format='<I'):
        self.ihex.puts(addr, struct.pack(format, value))

    def _get_value_fromhex(self, addr, size=4, format='<I'):
        return struct.unpack(format, self.ihex.gets(addr, size))[0] & 0xffffffff

    def _calculate_crc32_from_hex(self, ih_object, start_addr=None, end_addr=None):
        list = []
        if start_addr is None and end_addr is None:
            hex_dict = ih_object.todict()
            for addr, byte in list(hex_dict.items()):
                list.append(byte)
        else:
            for addr in range(start_addr, end_addr + 1):
                list.append(ih_object[addr])

        return binascii.crc32(bytearray(list)) & 0xFFFFFFFF

    def generate(self, arch, app_file, app_ver, bl_ver, bl_sett_ver, custom_bl_sett_addr, no_backup,
                 backup_address, app_boot_validation_type, sd_boot_validation_type, sd_file, signer):

        self.set_arch(arch)

        if custom_bl_sett_addr is not None:
            self.bl_sett_addr = custom_bl_sett_addr

        if bl_sett_ver == 1:
            self.setts = BLDFUSettingsStructV1(self.bl_sett_addr)
        elif bl_sett_ver == 2:
            self.setts = BLDFUSettingsStructV2(self.bl_sett_addr)
        else:
            raise NordicSemiException("Unknown bootloader settings version")

        self.bl_sett_ver = bl_sett_ver & 0xffffffff
        self.bl_ver = bl_ver & 0xffffffff

        if app_ver is not None:
            self.app_ver = app_ver & 0xffffffff
        else:
            self.app_ver = 0x0 & 0xffffffff

        if app_file is not None:
            # load application to find out size and CRC
            self.temp_dir = tempfile.mkdtemp(prefix="nrf_dfu_bl_sett_")
            self.app_bin = Package.normalize_firmware_to_bin(self.temp_dir, app_file)

            # calculate application size and CRC32
            self.app_sz = int(Package.calculate_file_size(self.app_bin)) & 0xffffffff
            self.app_crc = int(Package.calculate_crc(32, self.app_bin)) & 0xffffffff
            self.bank0_bank_code = 0x1 & 0xffffffff

            # Calculate Boot validation fields for app
            if app_boot_validation_type == 'VALIDATE_GENERATED_CRC':
                self.app_boot_validation_type = 1 & 0xffffffff
                self.app_boot_validation_bytes = struct.pack('<I', self.app_crc)
            elif app_boot_validation_type == 'VALIDATE_GENERATED_SHA256':
                self.app_boot_validation_type = 2 & 0xffffffff
                # Package.calculate_sha256_hash gives a reversed
                # digest. It need to be reversed back to a normal
                # sha256 digest.
                self.app_boot_validation_bytes = Package.calculate_sha256_hash(self.app_bin)[::-1]
            elif app_boot_validation_type == 'VALIDATE_ECDSA_P256_SHA256':
                self.app_boot_validation_type = 3 & 0xffffffff
                self.app_boot_validation_bytes = Package.sign_firmware(signer, self.app_bin)
            else:  # This also covers 'NO_VALIDATION' case
                self.app_boot_validation_type = 0 & 0xffffffff
                self.app_boot_validation_bytes = bytes(0)
        else:
            self.app_sz = 0x0 & 0xffffffff
            self.app_crc = 0x0 & 0xffffffff
            self.bank0_bank_code = 0x0 & 0xffffffff
            self.app_boot_validation_type = 0x0 & 0xffffffff
            self.app_boot_validation_bytes = bytes(0)

        if sd_file is not None:
            # Load SD to calculate CRC
            self.temp_dir = tempfile.mkdtemp(prefix="nrf_dfu_bl_sett")
            temp_sd_file = os.path.join(os.getcwd(), 'temp_sd_file.hex')

            # Load SD hex file and remove MBR before calculating keys
            ih_sd = intelhex.IntelHex(sd_file)
            ih_sd_no_mbr = intelhex.IntelHex()
            ih_sd_no_mbr.merge(ih_sd[0x1000:], overlap='error')
            ih_sd_no_mbr.write_hex_file(temp_sd_file)

            self.sd_bin = Package.normalize_firmware_to_bin(self.temp_dir, temp_sd_file)
            os.remove(temp_sd_file)

            self.sd_sz = int(Package.calculate_file_size(self.sd_bin)) & 0xffffffff

            # Calculate Boot validation fields for SD
            if sd_boot_validation_type == 'VALIDATE_GENERATED_CRC':
                self.sd_boot_validation_type = 1 & 0xffffffff
                sd_crc = int(Package.calculate_crc(32, self.sd_bin)) & 0xffffffff
                self.sd_boot_validation_bytes = struct.pack('<I', sd_crc)
            elif sd_boot_validation_type == 'VALIDATE_GENERATED_SHA256':
                self.sd_boot_validation_type = 2 & 0xffffffff
                # Package.calculate_sha256_hash gives a reversed
                # digest. It need to be reversed back to a normal
                # sha256 digest.
                self.sd_boot_validation_bytes = Package.calculate_sha256_hash(self.sd_bin)[::-1]
            elif sd_boot_validation_type == 'VALIDATE_ECDSA_P256_SHA256':
                self.sd_boot_validation_type = 3 & 0xffffffff
                self.sd_boot_validation_bytes = Package.sign_firmware(signer, self.sd_bin)
            else:  # This also covers 'NO_VALIDATION_CASE'
                self.sd_boot_validation_type = 0 & 0xffffffff
                self.sd_boot_validation_bytes = bytes(0)
        else:
            self.sd_sz = 0x0 & 0xffffffff
            self.sd_boot_validation_type = 0 & 0xffffffff
            self.sd_boot_validation_bytes = bytes(0)

        # additional hardcoded values
        self.bank_layout = 0x0 & 0xffffffff
        self.bank_current = 0x0 & 0xffffffff

        # Fill the entire settings page with 0's
        for offset in range(0, self.setts.bytes_count):
            self.ihex[self.bl_sett_addr + offset] = 0x00
            
        # Make sure the hex-file is 32bit-word-aligned
        fill_bytes = ((self.setts.bytes_count + 4 - 1) & ~(4 - 1)) - self.setts.bytes_count
        for offset in range(self.setts.bytes_count, self.setts.bytes_count + fill_bytes):
            self.ihex[self.bl_sett_addr + offset] = 0xFF
        
        self._add_value_tohex(self.setts.sett_ver, self.bl_sett_ver)
        self._add_value_tohex(self.setts.app_ver, self.app_ver)
        self._add_value_tohex(self.setts.bl_ver, self.bl_ver)
        self._add_value_tohex(self.setts.bank_layout, self.bank_layout)
        self._add_value_tohex(self.setts.bank_current, self.bank_current)
        self._add_value_tohex(self.setts.bank0_img_sz, self.app_sz)
        self._add_value_tohex(self.setts.bank0_img_crc, self.app_crc)
        self._add_value_tohex(self.setts.bank0_bank_code, self.bank0_bank_code)
        self._add_value_tohex(self.setts.sd_sz, self.sd_sz)

        self.boot_validation_crc = 0x0 & 0xffffffff
        if self.bl_sett_ver == 2:
            self._add_value_tohex(self.setts.sd_validation_type, self.sd_boot_validation_type, '<b')
            self.ihex.puts(self.setts.sd_validation_bytes, self.sd_boot_validation_bytes)

            self._add_value_tohex(self.setts.app_validation_type, self.app_boot_validation_type, '<b')
            self.ihex.puts(self.setts.app_validation_bytes, self.app_boot_validation_bytes)

            self.boot_validation_crc = self._calculate_crc32_from_hex(self.ihex,
                                                                      start_addr=self.setts.sd_validation_type,
                                                                      end_addr=self.setts.last_addr) & 0xffffffff
            self._add_value_tohex(self.setts.boot_validataion_crc, self.boot_validation_crc)

        self.crc = self._calculate_crc32_from_hex(self.ihex,
                                                  start_addr=self.bl_sett_addr+4,
                                                  end_addr=self.setts.init_cmd - 1) & 0xffffffff
        self._add_value_tohex(self.setts.crc, self.crc)

        if backup_address is None:
            self.backup_address = self.bl_sett_addr - self.bl_sett_backup_offset
        else:
            self.backup_address = backup_address

        if not no_backup:
            for offset in range(0, self.setts.bytes_count):
                self.ihex[self.backup_address + offset] = self.ihex[self.bl_sett_addr + offset]
            for offset in range(self.setts.bytes_count, self.setts.bytes_count + fill_bytes):
                self.ihex[self.backup_address + offset] = 0xFF

    def probe_settings(self, base):
        # Unpack CRC and version
        fmt = '<I'
        crc = struct.unpack(fmt, self.ihex.gets(base + 0, 4))[0] & 0xffffffff
        ver = struct.unpack(fmt, self.ihex.gets(base + 4, 4))[0] & 0xffffffff

        if ver == 1:
            self.setts = BLDFUSettingsStructV1(base)
        elif ver == 2:
            self.setts = BLDFUSettingsStructV2(base)
        else:
            raise RuntimeError("Unknown Bootloader DFU settings version: {0}".format(ver))

        # calculate the CRC32 over the data
        _crc = self._calculate_crc32_from_hex(self.ihex,
                                              start_addr=base + 4,
                                              end_addr=self.setts.init_cmd - 1) & 0xffffffff

        if _crc != crc:
            raise RuntimeError("CRC32 mismtach: flash: {0} calculated: {1}".format(hex(crc), hex(_crc)))

        self.crc = crc
        self.bl_sett_ver     = self._get_value_fromhex(self.setts.sett_ver)
        self.app_ver         = self._get_value_fromhex(self.setts.app_ver)
        self.bl_ver          = self._get_value_fromhex(self.setts.bl_ver)
        self.bank_layout     = self._get_value_fromhex(self.setts.bank_layout)
        self.bank_current    = self._get_value_fromhex(self.setts.bank_current)
        self.app_sz          = self._get_value_fromhex(self.setts.bank0_img_sz)
        self.app_crc         = self._get_value_fromhex(self.setts.bank0_img_crc)
        self.bank0_bank_code = self._get_value_fromhex(self.setts.bank0_bank_code)

        if self.bl_sett_ver == 2:
            self.sd_sz                    = self._get_value_fromhex(self.setts.sd_sz)
            self.boot_validation_crc      = self._get_value_fromhex(self.setts.boot_validataion_crc)
            self.sd_boot_validation_type  = self._get_value_fromhex(self.setts.sd_validation_type, size=1, format='<b')
            self.app_boot_validation_type = self._get_value_fromhex(self.setts.app_validation_type, size=1, format='<b')
        else:
            self.sd_sz                    = 0x0 & 0xffffffff
            self.boot_validation_crc      = 0x0 & 0xffffffff
            self.sd_boot_validation_type  = 0x0 & 0xffffffff
            self.app_boot_validation_type = 0x0 & 0xffffffff

    def fromhexfile(self, f, arch=None):
        self.hex_file = f
        self.ihex.fromfile(f, format='hex')

        # check the 3 possible addresses for CRC matches
        try:
            self.probe_settings(BLDFUSettings.bl_sett_51_addr)
            self.set_arch('NRF51')
        except Exception as e:
            try:
                self.probe_settings(BLDFUSettings.bl_sett_52_addr)
                self.set_arch('NRF52')
            except Exception as e:
                print(e)
                try:
                    self.probe_settings(BLDFUSettings.bl_sett_52_qfab_addr)
                    self.set_arch('NRF52QFAB')
                except Exception as e:
                    try:
                        self.probe_settings(BLDFUSettings.bl_sett_52810_addr)
                        self.set_arch('NRF52810')
                    except Exception as e:
                        try:
                            self.probe_settings(BLDFUSettings.bl_sett_52840_addr)
                            self.set_arch('NRF52840')
                        except Exception as e:
                            raise NordicSemiException("Failed to parse .hex file: {0}".format(e))

        self.bl_sett_addr = self.ihex.minaddr()

    def __str__(self):
        s = """
Bootloader DFU Settings:
* File:                     {0}
* Family:                   {1}
* Start Address:            0x{2:08X}
* CRC:                      0x{3:08X}
* Settings Version:         0x{4:08X} ({4})
* App Version:              0x{5:08X} ({5})
* Bootloader Version:       0x{6:08X} ({6})
* Bank Layout:              0x{7:08X}
* Current Bank:             0x{8:08X}
* Application Size:         0x{9:08X} ({9} bytes)
* Application CRC:          0x{10:08X}
* Bank0 Bank Code:          0x{11:08X}
* Softdevice Size:          0x{12:08X} ({12} bytes)
* Boot Validation CRC:      0x{13:08X}
* SD Boot Validation Type:  0x{14:08X} ({14})
* App Boot Validation Type: 0x{15:08X} ({15})
""".format(self.hex_file, self.arch_str, self.bl_sett_addr, self.crc, self.bl_sett_ver, self.app_ver,
           self.bl_ver, self.bank_layout, self.bank_current, self.app_sz, self.app_crc, self.bank0_bank_code,
           self.sd_sz, self.boot_validation_crc, self.sd_boot_validation_type, self.app_boot_validation_type)
        return s

    def tohexfile(self, f):
        self.hex_file = f
        self.ihex.tofile(f, format='hex')
