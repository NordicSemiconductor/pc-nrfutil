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

import binascii
import os
import shutil
import tempfile
import unittest

from nordicsemi.dfu.signing import Signing


class TestSinging(unittest.TestCase):
    def setUp(self):
        script_abspath = os.path.abspath(__file__)
        script_dirname = os.path.dirname(script_abspath)
        os.chdir(script_dirname)

    def test_gen_key(self):
        self.work_directory = tempfile.mkdtemp(prefix="nrf_signing_tests_")

        key_file_name = 'key.pem'
        key_file_path = os.path.join(self.work_directory, key_file_name)

        signing = Signing()
        signing.gen_key(key_file_path)

        self.assertTrue(os.path.exists(key_file_path))

        shutil.rmtree(self.work_directory, ignore_errors=True)

    def test_load_key(self):
        key_file_name = 'key.pem'

        signing = Signing()
        signing.load_key(key_file_name)

        self.assertEqual(64, len(binascii.hexlify(signing.sk.to_string())))

    def test_get_vk(self):
        key_file_name = 'key.pem'

        signing = Signing()
        signing.load_key(key_file_name)

        vk_str = signing.get_vk('hex')
        vk_hex = signing.get_vk_hex()
        self.assertEqual(vk_hex, vk_str)

        vk_str = signing.get_vk('code')
        vk_code = signing.get_vk_code()
        self.assertEqual(vk_code, vk_str)

        vk_str = signing.get_vk('pem')
        vk_pem = signing.get_vk_pem()
        self.assertEqual(vk_pem, vk_str)

    def test_get_vk_hex(self):
        key_file_name = 'key.pem'
        expected_vk_hex = "Verification key pk: 60f417aabb6bb5b9058aec0570b83fedab1782d62072ae7d691f98dbeda28d654c1d98"\
                          "6cadcd593ad8901084900c1bbdcc4fff62b612b604c22672adcdae9b90"

        signing = Signing()
        signing.load_key(key_file_name)

        vk_hex = signing.get_vk_hex()

        self.assertEqual(expected_vk_hex, vk_hex)

    def test_get_sk_hex(self):
        key_file_name = 'key.pem'
        expected_vk_hex = "Verification key pk: 60f417aabb6bb5b9058aec0570b83fedab1782d62072ae7d691f98dbeda28d654c1d98"\
                          "6cadcd593ad8901084900c1bbdcc4fff62b612b604c22672adcdae9b90"

        signing = Signing()
        signing.load_key(key_file_name)

        sk_hex = signing.get_sk_hex()

        self.assertEqual(expected_vk_hex, sk_hex)



    def test_get_vk_code(self):
        key_file_name = 'key.pem'

        expected_vk_code = "static const uint8_t pk[] = { 0x60, 0xf4, 0x17, 0xaa, 0xbb, 0x6b, 0xb5, 0xb9, 0x05, " \
                           "0x8a, 0xec, 0x05, 0x70, 0xb8, 0x3f, 0xed, 0xab, 0x17, 0x82, 0xd6, 0x20, 0x72, " \
                           "0xae, 0x7d, 0x69, 0x1f, 0x98, 0xdb, 0xed, 0xa2, 0x8d, 0x65, 0x4c, 0x1d, 0x98, " \
                           "0x6c, 0xad, 0xcd, 0x59, 0x3a, 0xd8, 0x90, 0x10, 0x84, 0x90, 0x0c, 0x1b, 0xbd, " \
                           "0xcc, 0x4f, 0xff, 0x62, 0xb6, 0x12, 0xb6, 0x04, 0xc2, 0x26, 0x72, 0xad, 0xcd, " \
                           "0xae, 0x9b, 0x90 };\n"\
                           "static const nrf_crypto_key_t crypto_key_pk = { .p_le_data = pk, .len = sizeof(pk) };"

        signing = Signing()
        signing.load_key(key_file_name)

        vk_code = signing.get_vk_code()

        self.assertEqual(expected_vk_code, vk_code)

    def test_get_vk_pem(self):
        key_file_name = 'key.pem'
        expected_vk_pem = "-----BEGIN PUBLIC KEY-----\n" \
                          "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEZY2i7duYH2l9rnIg1oIXq+0/uHAF\n" \
                          "7IoFubVru6oX9GCQm67NrXImwgS2ErZi/0/MvRsMkIQQkNg6Wc2tbJgdTA==\n" \
                          "-----END PUBLIC KEY-----\n"

        signing = Signing()
        signing.load_key(key_file_name)

        vk_pem = signing.get_vk_pem()

        self.assertEqual(expected_vk_pem, vk_pem)
