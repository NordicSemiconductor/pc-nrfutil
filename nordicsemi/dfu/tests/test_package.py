# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

import json
import os
import tempfile
import unittest
from zipfile import ZipFile
import shutil

from nordicsemi.dfu.package import Package


class TestPackage(unittest.TestCase):
    def setUp(self):
        self.work_directory = tempfile.mkdtemp(prefix="nrf_dfu_tests_")

    def tearDown(self):
        shutil.rmtree(self.work_directory, ignore_errors=True)

    def test_generate_package_application(self):
        self.p = Package(
            dev_type=1,
            dev_rev=2,
            app_version=100,
            sd_req=[0x1000, 0xfffe],
            app_fw="bar.hex"
        )

        pkg_name = "mypackage.zip"

        self.p.generate_package(pkg_name, preserve_work_directory=False)
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
                self.assertEqual(u'bar.bin', _json['manifest']['application']['bin_file'])
                self.assertEqual(u'bar.dat', _json['manifest']['application']['dat_file'])
                self.assertTrue(u'softdevice' not in _json['manifest'])
                self.assertTrue(u'softdevice_bootloader' not in _json['manifest'])
                self.assertTrue(u'bootloader' not in _json['manifest'])

    def test_generate_package_sd_bl(self):
        self.p = Package(dev_type=1,
                         dev_rev=2,
                         app_version=100,
                         sd_req=[0x1000, 0xfffe],
                         softdevice_fw="foo.hex",
                         bootloader_fw="bar.hex")

        pkg_name = "mypackage.zip"

        self.p.generate_package(pkg_name, preserve_work_directory=False)

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
                self.assertEqual(u'sd_bl.bin', _json['manifest']['softdevice_bootloader']['bin_file'])
                self.assertEqual(u'sd_bl.dat', _json['manifest']['softdevice_bootloader']['dat_file'])

    def test_unpack_package_a(self):
        self.p = Package(dev_type=1,
                         dev_rev=2,
                         app_version=100,
                         sd_req=[0x1000, 0xffff],
                         softdevice_fw="bar.hex")
        pkg_name = os.path.join(self.work_directory, "mypackage.zip")
        self.p.generate_package(pkg_name, preserve_work_directory=False)

        unpacked_dir = os.path.join(self.work_directory, "unpacked")
        manifest = self.p.unpack_package(os.path.join(self.work_directory, pkg_name), unpacked_dir)
        self.assertIsNotNone(manifest)
        self.assertEqual(u'bar.bin', manifest.softdevice.bin_file)
        self.assertIsNotNone(manifest.softdevice.init_packet_data.firmware_crc16)
        self.assertIsNone(manifest.softdevice.init_packet_data.firmware_hash)

    def test_unpack_package_b(self):
        self.p = Package(dev_type=1,
                         dev_rev=2,
                         app_version=100,
                         sd_req=[0x1000, 0xffff],
                         softdevice_fw="bar.hex", dfu_ver=0.7)
        pkg_name = os.path.join(self.work_directory, "mypackage.zip")
        self.p.generate_package(pkg_name, preserve_work_directory=False)

        unpacked_dir = os.path.join(self.work_directory, "unpacked")
        manifest = self.p.unpack_package(os.path.join(self.work_directory, pkg_name), unpacked_dir)
        self.assertIsNotNone(manifest)
        self.assertEqual(u'bar.bin', manifest.softdevice.bin_file)
        self.assertIsNone(manifest.softdevice.init_packet_data.firmware_crc16)
        self.assertIsNotNone(manifest.softdevice.init_packet_data.firmware_hash)
        self.assertEqual(manifest.dfu_version, 0.7)


if __name__ == '__main__':
    unittest.main()
