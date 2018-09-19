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

import os

import unittest
from nordicsemi.dfu.bl_dfu_sett import BLDFUSettings
from nordicsemi.dfu.nrfhex import *


class TestBLDFUSettings(unittest.TestCase):
    def setUp(self):
        script_abspath = os.path.abspath(__file__)
        script_dirname = os.path.dirname(script_abspath)
        os.chdir(script_dirname)

    def test_fromhexfile(self):
        settings = BLDFUSettings()
        settings.fromhexfile('firmwares/bl_settings_nrf52.hex')

        self.assertEqual(nRFArch.NRF52, settings.arch)
        self.assertEqual('nRF52', settings.arch_str)
        self.assertEqual(0x0007F000, settings.bl_sett_addr)
        self.assertEqual(0xF6744851, settings.crc)
        self.assertEqual(0x00000001, settings.bl_sett_ver)
        self.assertEqual(0x00000003, settings.app_ver)
        self.assertEqual(0x00000003, settings.bl_ver)
        self.assertEqual(0x00000000, settings.bank_layout)
        self.assertEqual(0x00000000, settings.bank_current)
        self.assertEqual(0x0002C160, settings.app_sz)
        self.assertEqual(0x62C83F81, settings.app_crc)
        self.assertEqual(0x00000001, settings.bank0_bank_code)

    def test_generate_without_application_file(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None)

        self.assertEqual(nRFArch.NRF52, settings.arch)
        self.assertEqual('nRF52', settings.arch_str)
        self.assertEqual(0x0007F000, settings.bl_sett_addr)
        self.assertEqual(0xEAA3288E, settings.crc)
        self.assertEqual(0x00000001, settings.bl_sett_ver)
        self.assertEqual(0x00000001, settings.app_ver)
        self.assertEqual(0x00000001, settings.bl_ver)
        self.assertEqual(0x00000000, settings.bank_layout)
        self.assertEqual(0x00000000, settings.bank_current)
        self.assertEqual(0x00000000, settings.app_sz)
        self.assertEqual(0x00000000, settings.app_crc)
        self.assertEqual(0x00000000, settings.bank0_bank_code)

    def test_generate_with_application_file(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file='firmwares/s132_nrf52_mini.hex',
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None)

        self.assertEqual(nRFArch.NRF52, settings.arch)
        self.assertEqual('nRF52', settings.arch_str)
        self.assertEqual(0x0007F000, settings.bl_sett_addr)
        self.assertEqual(0xEB5917FB, settings.crc)
        self.assertEqual(0x00000001, settings.bl_sett_ver)
        self.assertEqual(0x00000001, settings.app_ver)
        self.assertEqual(0x00000001, settings.bl_ver)
        self.assertEqual(0x00000000, settings.bank_layout)
        self.assertEqual(0x00000000, settings.bank_current)
        self.assertEqual(0x00003000, settings.app_sz)
        self.assertEqual(0x5F045729, settings.app_crc)
        self.assertEqual(0x00000001, settings.bank0_bank_code)

    def test_generate_with_custom_start_address(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=0x0006F000,
                          no_backup=False,
                          backup_address=None)

        self.assertEqual(settings.bl_sett_addr, 0x0006F000)

    def test_generate_with_backup_page_check_size(self):
        settings_raw = BLDFUSettings()
        settings_raw.generate(arch='NRF52',
                             app_file=None,
                             app_ver=1,
                             bl_ver=1,
                             bl_sett_ver=1,
                             custom_bl_sett_addr=None,
                             no_backup=True,
                             backup_address=None)

        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None)

        self.assertEqual(len(settings.ihex.todict().keys()), len(settings_raw.ihex.todict().keys()) * 2)

    def test_generate_with_backup_page_check_values(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None)

        backup_dict = {(k + settings.bl_sett_backup_offset): v for k, v in settings.ihex.todict().items() if k < settings.bl_sett_addr}
        settings_dict = {k: v for k, v in settings.ihex.todict().items() if k >= settings.bl_sett_addr}
        self.assertEqual(backup_dict, settings_dict)

    def test_generate_with_backup_page_custom_address(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=0x0006F000)

        self.assertEqual(settings.backup_address, 0x0006F000)
        self.assertTrue(0x0006F000 in settings.ihex.todict().keys())

    def test_generate_with_backup_page_default_address(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=0x0006F000,
                          no_backup=False,
                          backup_address=None)

        self.assertEqual(settings.backup_address, (0x0006F000 - settings.bl_sett_backup_offset))
        self.assertTrue((0x0006F000 - settings.bl_sett_backup_offset) in settings.ihex.todict().keys())


if __name__ == '__main__':
    unittest.main()
