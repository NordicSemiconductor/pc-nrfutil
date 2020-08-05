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
import os
import tempfile
import unittest
from zipfile import ZipFile
import shutil

from nordicsemi.dfu.package import Package
from nordicsemi.dfu.signing import Signing


class TestPackage(unittest.TestCase):
    def setUp(self):
        self.work_directory = tempfile.mkdtemp(prefix="nrf_dfu_tests_")

    def tearDown(self):
        shutil.rmtree(self.work_directory, ignore_errors=True)

    def test_generate_package_application(self):
        signer = Signing()
        signer.load_key('key.pem')

        self.p = Package(app_version=100,
            sd_req=[0x1000, 0xfffe],
            app_fw="firmwares/bar.hex",
            signer=signer
        )

        pkg_name = "mypackage.zip"

        self.p.generate_package(pkg_name, preserve_work_dir=False)
        expected_zip_content = ["manifest.json", "bar.bin", "bar.dat"]

        with ZipFile(pkg_name, 'r') as pkg:
            infolist = pkg.infolist()

            for file_information in infolist:
                self.assertTrue(file_information.filename in expected_zip_content)
                self.assertGreater(file_information.file_size, 0)

            # Extract all and load json document to see if it is correct regarding to paths
            pkg.extractall(self.work_directory)

            with open(os.path.join(self.work_directory, 'manifest.json'), 'r') as f:
                _json = json.load(f)
                self.assertEqual('bar.bin', _json['manifest']['application']['bin_file'])
                self.assertEqual('bar.dat', _json['manifest']['application']['dat_file'])
                self.assertTrue('softdevice' not in _json['manifest'])
                self.assertTrue('softdevice_bootloader' not in _json['manifest'])
                self.assertTrue('bootloader' not in _json['manifest'])

    def test_generate_package_sd_bl(self):
        signer = Signing()
        signer.load_key('key.pem')

        self.p = Package(app_version=100,
                         sd_req=[0x1000, 0xfffe],
                         softdevice_fw="firmwares/foo.hex",
                         bootloader_fw="firmwares/bar.hex",
                         signer=signer)


        pkg_name = "mypackage.zip"

        self.p.generate_package(pkg_name, preserve_work_dir=False)

        expected_zip_content = ["manifest.json", "sd_bl.bin", "sd_bl.dat"]

        with ZipFile(pkg_name, 'r') as pkg:
            infolist = pkg.infolist()

            for file_information in infolist:
                self.assertTrue(file_information.filename in expected_zip_content)
                self.assertGreater(file_information.file_size, 0)

            # Extract all and load json document to see if it is correct regarding to paths
            pkg.extractall(self.work_directory)

            with open(os.path.join(self.work_directory, 'manifest.json'), 'r') as f:
                _json = json.load(f)
                self.assertEqual('sd_bl.bin', _json['manifest']['softdevice_bootloader']['bin_file'])
                self.assertEqual('sd_bl.dat', _json['manifest']['softdevice_bootloader']['dat_file'])

    def test_unpack_package_a(self):
        signer = Signing()
        signer.load_key('key.pem')

        self.p = Package(app_version=100,
                         sd_req=[0x1000, 0xffff],
                         softdevice_fw="firmwares/bar.hex",
                         signer=signer)
        pkg_name = os.path.join(self.work_directory, "mypackage.zip")
        self.p.generate_package(pkg_name, preserve_work_dir=False)

        unpacked_dir = os.path.join(self.work_directory, "unpacked")
        manifest = self.p.unpack_package(os.path.join(self.work_directory, pkg_name), unpacked_dir)
        self.assertIsNotNone(manifest)
        self.assertEqual('bar.bin', manifest.softdevice.bin_file)
#         self.assertEqual(0, manifest.softdevice.init_packet_data.ext_packet_id)
#         self.assertIsNotNone(manifest.softdevice.init_packet_data.firmware_crc16)

    def test_unpack_package_b(self):
        signer = Signing()
        signer.load_key('key.pem')

        self.p = Package(app_version=100,
                         sd_req=[0x1000, 0xffff],
                         softdevice_fw="firmwares/bar.hex",
                         signer=signer)
        pkg_name = os.path.join(self.work_directory, "mypackage.zip")
        self.p.generate_package(pkg_name, preserve_work_dir=False)

        unpacked_dir = os.path.join(self.work_directory, "unpacked")
        manifest = self.p.unpack_package(os.path.join(self.work_directory, pkg_name), unpacked_dir)
        self.assertIsNotNone(manifest)
        self.assertEqual('bar.bin', manifest.softdevice.bin_file)

    def test_unpack_package_c(self):
        signer = Signing()
        signer.load_key('key.pem')

        self.p = Package(app_version=100,
                         sd_req=[0x1000, 0xffff],
                         softdevice_fw="firmwares/bar.hex",
                         signer=signer)
        pkg_name = os.path.join(self.work_directory, "mypackage.zip")
        self.p.generate_package(pkg_name, preserve_work_dir=False)

        unpacked_dir = os.path.join(self.work_directory, "unpacked")
        manifest = self.p.unpack_package(os.path.join(self.work_directory, pkg_name), unpacked_dir)
        self.assertIsNotNone(manifest)
        self.assertEqual('bar.bin', manifest.softdevice.bin_file)


if __name__ == '__main__':
    unittest.main()
