# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

import os

import unittest
import nordicsemi.dfu.nrfhex as nrfhex
import nordicsemi.dfu.intelhex as intelhex

class TestnRFHex(unittest.TestCase):
    def setUp(self):
        script_abspath = os.path.abspath(__file__)
        script_dirname = os.path.dirname(script_abspath)
        os.chdir(script_dirname)

    def comparefiles(self, actual, wanted):
        actualfile = intelhex.IntelHex()
        actualfile.loadfile(actual, format="bin")

        wantedfile = intelhex.IntelHex()
        wantedfile.loadfile(wanted, format="bin")

        self.assertEqual(actualfile.minaddr(), wantedfile.minaddr())
        self.assertEqual(actualfile.maxaddr(), wantedfile.maxaddr())

        minaddress = actualfile.minaddr()
        maxaddress = actualfile.maxaddr()

        length = maxaddress - minaddress

        actualfile_data = actualfile.gets(minaddress, length)
        wantedfile_data = wantedfile.gets(minaddress, length)

        self.assertEqual(actualfile_data, wantedfile_data)

    def test_tobinfile_single_file_without_uicr_content(self):
        nrf = nrfhex.nRFHex("bar.hex")
        nrf.tobinfile("bar.bin")

        self.comparefiles("bar.bin", "bar_wanted.bin")

    def test_tobinfile_single_file_with_uicr_content(self):
        nrf = nrfhex.nRFHex("foo.hex")
        nrf.tobinfile("foo.bin")

        self.comparefiles("foo.bin", "foo_wanted.bin")

    def test_tobinfile_single_bin_file(self):
        nrf = nrfhex.nRFHex("bar_wanted.bin")
        nrf.tobinfile("bar.bin")

        self.comparefiles("bar.bin", "bar_wanted.bin")

    def test_tobinfile_two_hex_files(self):
        nrf = nrfhex.nRFHex("foo.hex", "bar.hex")
        nrf.tobinfile("foobar.bin")

        self.comparefiles("foobar.bin", "foobar_wanted.bin")

    def test_tobinfile_one_hex_one_bin(self):
        nrf = nrfhex.nRFHex("foo_wanted.bin", "bar.hex")
        nrf.tobinfile("foobar.bin")

        self.comparefiles("foobar.bin", "foobar_wanted.bin")

    def test_tobinfile_one_bin_one_hex(self):
        nrf = nrfhex.nRFHex("foo.hex", "bar_wanted.bin")
        nrf.tobinfile("foobar.bin")

        self.comparefiles("foobar.bin", "foobar_wanted.bin")

    def test_tobinfile_two_bin(self):
        nrf = nrfhex.nRFHex("foo_wanted.bin", "bar_wanted.bin")
        nrf.tobinfile("foobar.bin")

        self.comparefiles("foobar.bin", "foobar_wanted.bin")

    def test_sizes(self):
        nrf = nrfhex.nRFHex("foo.hex", "bar.hex")

        self.assertEqual(nrf.size(), 73152)
        self.assertEqual(nrf.bootloadersize(), 13192)


if __name__ == '__main__':
    unittest.main()
