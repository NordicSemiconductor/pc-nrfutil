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

import json
import unittest

from nordicsemi.dfu.manifest import ManifestGenerator, Manifest
from nordicsemi.dfu.model import HexType
from nordicsemi.dfu.package import FirmwareKeys


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.firmwares_data_a = {}

        self.firmwares_data_a[HexType.APPLICATION] = {
            FirmwareKeys.BIN_FILENAME: "app_fw.bin",
            FirmwareKeys.DAT_FILENAME: "app_fw.dat",
            FirmwareKeys.ENCRYPT: False}

        self.firmwares_data_a[HexType.SD_BL] = {
            FirmwareKeys.BIN_FILENAME: "sd_bl_fw.bin",
            FirmwareKeys.DAT_FILENAME: "sd_bl_fw.dat",
            FirmwareKeys.BL_SIZE: 50,
            FirmwareKeys.SD_SIZE: 90
        }

        self.firmwares_data_b = {}

        self.firmwares_data_b[HexType.APPLICATION] = {
            FirmwareKeys.BIN_FILENAME: "app_fw.bin",
            FirmwareKeys.DAT_FILENAME: "app_fw.dat"
        }

        self.firmwares_data_b[HexType.BOOTLOADER] = {
            FirmwareKeys.BIN_FILENAME: "bootloader_fw.bin",
            FirmwareKeys.DAT_FILENAME: "bootloader_fw.dat"
        }

        self.firmwares_data_c = {}

        self.firmwares_data_c[HexType.SOFTDEVICE] = {
            FirmwareKeys.BIN_FILENAME: "softdevice_fw.bin",
            FirmwareKeys.DAT_FILENAME: "softdevice_fw.dat",
        }

    def test_generate_manifest(self):
        r = ManifestGenerator(self.firmwares_data_a)

        _json = json.loads(r.generate_manifest())

        # Test for presence of attributes in document
        self.assertIn('manifest', _json)

        manifest = _json['manifest']
        self.assertIn('application', manifest)

        application = manifest['application']
        self.assertIn('dat_file', application)
        self.assertIn('bin_file', application)

        # Test for values in document
        self.assertEqual("app_fw.bin", application['bin_file'])
        self.assertEqual("app_fw.dat", application['dat_file'])

        # Test softdevice_bootloader
        bl_sd = manifest['softdevice_bootloader']
        self.assertIsNotNone(bl_sd)
        self.assertEqual(90, bl_sd['info_read_only_metadata']['sd_size'])
        self.assertEqual(50, bl_sd['info_read_only_metadata']['bl_size'])

        # Test for values in document
        self.assertEqual("sd_bl_fw.bin", bl_sd['bin_file'])
        self.assertEqual("sd_bl_fw.dat", bl_sd['dat_file'])

    def test_manifest_a(self):
        r = ManifestGenerator(self.firmwares_data_a)
        m = Manifest.from_json(r.generate_manifest())
        self.assertIsNotNone(m)
        self.assertIsNotNone(m.application)
        self.assertEqual("app_fw.bin", m.application.bin_file)
        self.assertEqual("app_fw.dat", m.application.dat_file)
        self.assertIsNone(m.bootloader)
        self.assertIsNone(m.softdevice)
        self.assertIsNotNone(m.softdevice_bootloader)
        self.assertEqual(90, m.softdevice_bootloader.info_read_only_metadata.sd_size)
        self.assertEqual(50, m.softdevice_bootloader.info_read_only_metadata.bl_size)
        self.assertEqual("sd_bl_fw.bin", m.softdevice_bootloader.bin_file)
        self.assertEqual("sd_bl_fw.dat", m.softdevice_bootloader.dat_file)

    def test_manifest_b(self):
        r = ManifestGenerator(self.firmwares_data_b)
        m = Manifest.from_json(r.generate_manifest())
        self.assertIsNotNone(m)
        self.assertIsNotNone(m.application)
        self.assertEqual("app_fw.bin", m.application.bin_file)
        self.assertEqual("app_fw.dat", m.application.dat_file)
        self.assertIsNotNone(m.bootloader)
        self.assertEqual("bootloader_fw.bin", m.bootloader.bin_file)
        self.assertEqual("bootloader_fw.dat", m.bootloader.dat_file)
        self.assertIsNone(m.softdevice)
        self.assertIsNone(m.softdevice_bootloader)


    def test_manifest_c(self):
        r = ManifestGenerator(self.firmwares_data_c)
        m = Manifest.from_json(r.generate_manifest())
        self.assertIsNotNone(m)
        self.assertIsNone(m.application)
        self.assertIsNone(m.bootloader)
        self.assertIsNotNone(m.softdevice)
        self.assertEqual('softdevice_fw.bin', m.softdevice.bin_file)
        self.assertEqual('softdevice_fw.dat', m.softdevice.dat_file)
        self.assertIsNone(m.softdevice_bootloader)

if __name__ == '__main__':
    unittest.main()
