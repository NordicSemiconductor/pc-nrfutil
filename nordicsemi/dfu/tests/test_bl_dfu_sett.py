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
import struct

import unittest
from nordicsemi.dfu.bl_dfu_sett import BLDFUSettings
from nordicsemi.dfu.nrfhex import nRFArch
from nordicsemi.dfu.signing import Signing


class TestBLDFUSettingsV1(unittest.TestCase):
    def setUp(self):
        script_abspath = os.path.abspath(__file__)
        script_dirname = os.path.dirname(script_abspath)
        os.chdir(script_dirname)

    def test_fromhexfile(self):
        settings = BLDFUSettings()
        settings.fromhexfile('firmwares/bl_settings_v1_nrf52.hex')

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
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

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
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

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
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

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
                             backup_address=None,
                             app_boot_validation_type=None,
                             sd_boot_validation_type=None,
                             sd_file=None,
                             signer=None)

        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(len(list(settings.ihex.todict().keys())), len(list(settings_raw.ihex.todict().keys())) * 2)

    def test_generate_with_backup_page_check_values(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        backup_dict = {(k + settings.bl_sett_backup_offset): v for k, v in list(settings.ihex.todict().items()) if k < settings.bl_sett_addr}
        settings_dict = {k: v for k, v in list(settings.ihex.todict().items()) if k >= settings.bl_sett_addr}
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
                          backup_address=0x0006F000,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(settings.backup_address, 0x0006F000)
        self.assertTrue(0x0006F000 in list(settings.ihex.todict().keys()))

    def test_generate_with_backup_page_default_address(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=1,
                          custom_bl_sett_addr=0x0006F000,
                          no_backup=False,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(settings.backup_address, (0x0006F000 - settings.bl_sett_backup_offset))
        self.assertTrue((0x0006F000 - settings.bl_sett_backup_offset) in list(settings.ihex.todict().keys()))

class TestBLDFUSettingsV2(unittest.TestCase):
    def setUp(self):
        script_abspath = os.path.abspath(__file__)
        script_dirname = os.path.dirname(script_abspath)
        os.chdir(script_dirname)

    def test_fromhexfile(self):
        settings = BLDFUSettings()
        settings.fromhexfile('firmwares/bl_settings_v2_nrf52.hex')

        self.assertEqual(nRFArch.NRF52, settings.arch)
        self.assertEqual('nRF52', settings.arch_str)
        self.assertEqual(0x0007F000, settings.bl_sett_addr)
        self.assertEqual(0x2914E4A9, settings.crc)
        self.assertEqual(0x00000002, settings.bl_sett_ver)
        self.assertEqual(0x00000001, settings.app_ver)
        self.assertEqual(0x00000001, settings.bl_ver)
        self.assertEqual(0x00000000, settings.bank_layout)
        self.assertEqual(0x00000000, settings.bank_current)
        self.assertEqual(0x000148B4, settings.app_sz)
        self.assertEqual(0xF272EEBF, settings.app_crc)
        self.assertEqual(0x00000001, settings.bank0_bank_code)
        self.assertEqual(0x00024150, settings.sd_sz)
        self.assertEqual(0x467B5555, settings.boot_validation_crc)
        self.assertEqual(0x01,       settings.sd_boot_validation_type)
        #self.assertEqual(0x5B00BDCE, settings.sd_boot_validation_bytes)
        self.assertEqual(0x01,       settings.app_boot_validation_type)
        #self.assertEqual(0xF272EEBF, settings.app_boot_validation_bytes)

    def test_generate_without_application_or_sd_file(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(nRFArch.NRF52, settings.arch)
        self.assertEqual('nRF52', settings.arch_str)
        self.assertEqual(0x0007F000, settings.bl_sett_addr)
        self.assertEqual(0x12ECF0A5, settings.crc)
        self.assertEqual(0x00000002, settings.bl_sett_ver)
        self.assertEqual(0x00000001, settings.app_ver)
        self.assertEqual(0x00000001, settings.bl_ver)
        self.assertEqual(0x00000000, settings.bank_layout)
        self.assertEqual(0x00000000, settings.bank_current)
        self.assertEqual(0x00000000, settings.app_sz)
        self.assertEqual(0x00000000, settings.app_crc)
        self.assertEqual(0x00000000, settings.bank0_bank_code)
        self.assertEqual(0x00000000, settings.sd_sz)
        self.assertEqual(0xACDA1BA2, settings.boot_validation_crc)
        self.assertEqual(0x00, settings.sd_boot_validation_type)
        # self.assertEqual(0x5B00BDCE, settings.sd_boot_validation_bytes)
        self.assertEqual(0x00, settings.app_boot_validation_type)
        # self.assertEqual(0xF272EEBF, settings.app_boot_validation_bytes)

    def test_generate_with_application_and_sd_file(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file='firmwares/s132_nrf52_mini.hex',
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file='firmwares/s132_nrf52_mini.hex',
                          signer=None)

        self.assertEqual(nRFArch.NRF52, settings.arch)
        self.assertEqual('nRF52', settings.arch_str)
        self.assertEqual(0x0007F000, settings.bl_sett_addr)
        self.assertEqual(0x47CD3EEA, settings.crc)
        self.assertEqual(0x00000002, settings.bl_sett_ver)
        self.assertEqual(0x00000001, settings.app_ver)
        self.assertEqual(0x00000001, settings.bl_ver)
        self.assertEqual(0x00000000, settings.bank_layout)
        self.assertEqual(0x00000000, settings.bank_current)
        self.assertEqual(0x00003000, settings.app_sz)
        self.assertEqual(0x5F045729, settings.app_crc)
        self.assertEqual(0x00000001, settings.bank0_bank_code)
        self.assertEqual(0x00003000, settings.sd_sz)
        self.assertEqual(0xACDA1BA2, settings.boot_validation_crc)
        self.assertEqual(0x00, settings.sd_boot_validation_type)
        # self.assertEqual(0x5B00BDCE, settings.sd_boot_validation_bytes)
        self.assertEqual(0x00, settings.app_boot_validation_type)
        # self.assertEqual(0xF272EEBF, settings.app_boot_validation_bytes)

    def test_generate_with_custom_start_address(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=0x0006F000,
                          no_backup=False,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(settings.bl_sett_addr, 0x0006F000)

    def test_generate_with_backup_page_check_size(self):
        settings_raw = BLDFUSettings()
        settings_raw.generate(arch='NRF52',
                             app_file=None,
                             app_ver=1,
                             bl_ver=1,
                             bl_sett_ver=2,
                             custom_bl_sett_addr=None,
                             no_backup=True,
                             backup_address=None,
                             app_boot_validation_type=None,
                             sd_boot_validation_type=None,
                             sd_file=None,
                             signer=None)

        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(len(list(settings.ihex.todict().keys())), len(list(settings_raw.ihex.todict().keys())) * 2)

    def test_generate_with_backup_page_check_values(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        backup_dict = {(k + settings.bl_sett_backup_offset): v for k, v in list(settings.ihex.todict().items()) if k < settings.bl_sett_addr}
        settings_dict = {k: v for k, v in list(settings.ihex.todict().items()) if k >= settings.bl_sett_addr}
        self.assertEqual(backup_dict, settings_dict)

    def test_generate_with_backup_page_custom_address(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=False,
                          backup_address=0x0006F000,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(settings.backup_address, 0x0006F000)
        self.assertTrue(0x0006F000 in list(settings.ihex.todict().keys()))

    def test_generate_with_backup_page_default_address(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=0x0006F000,
                          no_backup=False,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(settings.backup_address, (0x0006F000 - settings.bl_sett_backup_offset))
        self.assertTrue((0x0006F000 - settings.bl_sett_backup_offset) in list(settings.ihex.todict().keys()))

    def test_generate_with_app_boot_validation_crc(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file='firmwares/s132_nrf52_mini.hex',
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=True,
                          backup_address=None,
                          app_boot_validation_type='VALIDATE_GENERATED_CRC',
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(0x1316CFD0, settings.crc)
        self.assertEqual(0x49A0F45A, settings.boot_validation_crc)
        self.assertEqual(0x01,       settings.app_boot_validation_type)
        self.assertEqual(0x5F045729, struct.unpack('<I', settings.app_boot_validation_bytes)[0])

    def test_generate_with_app_boot_validation_sha256(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file='firmwares/s132_nrf52_mini.hex',
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=True,
                          backup_address=None,
                          app_boot_validation_type='VALIDATE_GENERATED_SHA256',
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=None)

        self.assertEqual(0x1316CFD0, settings.crc)
        self.assertEqual(0xF78E451E, settings.boot_validation_crc)
        self.assertEqual(0x02, settings.app_boot_validation_type)
        self.assertEqual(bytes.fromhex('036F52C9EBB53819D6E2B6FB57803823E864783B04D7331B46C0B5897CA9F1C7'),
                         settings.app_boot_validation_bytes)

    def test_generate_with_app_boot_validation_ecdsa(self):
        settings = BLDFUSettings()

        signer = Signing()
        signer.load_key('key.pem')

        settings.generate(arch='NRF52',
                          app_file='firmwares/s132_nrf52_mini.hex',
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=True,
                          backup_address=None,
                          app_boot_validation_type='VALIDATE_ECDSA_P256_SHA256',
                          sd_boot_validation_type=None,
                          sd_file=None,
                          signer=signer)

        # Since ECDSA contains a random component the signature will be different every time
        # it is generated. Therefore only overall structure of the boot validation will be checked.
        self.assertEqual(0x03, settings.app_boot_validation_type)
        self.assertEqual(64, len(settings.app_boot_validation_bytes))

    def test_generate_with_sd_boot_validation_crc(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=True,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type='VALIDATE_GENERATED_CRC',
                          sd_file='firmwares/s132_nrf52_mini.hex',
                          signer=None)

        self.assertEqual(0x4637019F, settings.crc)
        self.assertEqual(0xCB5F90FB, settings.boot_validation_crc)
        self.assertEqual(0x01,       settings.sd_boot_validation_type)
        self.assertEqual(0x5F045729, struct.unpack('<I', settings.sd_boot_validation_bytes)[0])

    def test_generate_with_sd_boot_validation_sha256(self):
        settings = BLDFUSettings()
        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=True,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type='VALIDATE_GENERATED_SHA256',
                          sd_file='firmwares/s132_nrf52_mini.hex',
                          signer=None)

        self.assertEqual(0x4637019F, settings.crc)
        self.assertEqual(0x9C761426, settings.boot_validation_crc)
        self.assertEqual(0x02, settings.sd_boot_validation_type)
        self.assertEqual(bytes.fromhex('036F52C9EBB53819D6E2B6FB57803823E864783B04D7331B46C0B5897CA9F1C7'),
                         settings.sd_boot_validation_bytes)

    def test_generate_with_sd_boot_validation_ecdsa(self):
        settings = BLDFUSettings()

        signer = Signing()
        signer.load_key('key.pem')

        settings.generate(arch='NRF52',
                          app_file=None,
                          app_ver=1,
                          bl_ver=1,
                          bl_sett_ver=2,
                          custom_bl_sett_addr=None,
                          no_backup=True,
                          backup_address=None,
                          app_boot_validation_type=None,
                          sd_boot_validation_type='VALIDATE_ECDSA_P256_SHA256',
                          sd_file='firmwares/s132_nrf52_mini.hex',
                          signer=signer)

        # Since ECDSA contains a random component the signature will be different every time
        # it is generated. Therefore only overall structure of the boot validation will be checked.
        self.assertEqual(0x03, settings.sd_boot_validation_type)
        self.assertEqual(64, len(settings.sd_boot_validation_bytes))

if __name__ == '__main__':
    unittest.main()
