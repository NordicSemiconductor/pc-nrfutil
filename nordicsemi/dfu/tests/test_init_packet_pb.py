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
import unittest
from nordicsemi.dfu.init_packet_pb import InitPacketPB, DFUType, SigningTypes, HashTypes
import nordicsemi.dfu.dfu_cc_pb2 as pb

HASH_BYTES_A = b'123123123123'
HASH_BYTES_B = b'434343434343'
HASH_TYPE = HashTypes.SHA256
DFU_TYPE = DFUType.APPLICATION
SIGNATURE_BYTES_A = b'234827364872634876234'
SIGNATURE_TYPE = SigningTypes.ECDSA_P256_SHA256
SD_REQ_A = [1, 2, 3, 4]
FIRMWARE_VERSION_A = 0xaaaa
HARDWARE_VERSION_A = 0xbbbb
ILLEGAL_VERSION = 0xaaaaaaaa1
SD_SIZE = 0x11
APP_SIZE = 0x233
BL_SIZE = 0x324


class TestPackage(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_init_command(self):
        init_command_serialized = InitPacketPB(hash_bytes=HASH_BYTES_B, hash_type=HASH_TYPE,
                                               dfu_type=DFU_TYPE, sd_req=SD_REQ_A, fw_version=FIRMWARE_VERSION_A,
                                               hw_version=HARDWARE_VERSION_A, sd_size=SD_SIZE, app_size=APP_SIZE,
                                               bl_size=BL_SIZE).get_init_command_bytes()

        init_command = pb.InitCommand()
        init_command.ParseFromString(init_command_serialized)

        self.assertEqual(init_command.hash.hash, HASH_BYTES_B)
        self.assertEqual(init_command.hash.hash_type, pb.SHA256)
        self.assertEqual(init_command.type, pb.APPLICATION)
        self.assertEqual(init_command.fw_version, FIRMWARE_VERSION_A)
        self.assertEqual(init_command.hw_version, HARDWARE_VERSION_A)
        self.assertEqual(init_command.app_size, APP_SIZE)
        self.assertEqual(init_command.sd_size, SD_SIZE)
        self.assertEqual(init_command.bl_size, BL_SIZE)
        self.assertEqual(init_command.sd_req, SD_REQ_A)

    def test_init_command_wrong_size(self):
        def test_size(dfu_type, sd_size, app_size, bl_size, expect_failed):
            failed = False
            try:
                InitPacketPB(hash_bytes=HASH_BYTES_B, hash_type=HASH_TYPE,
                             dfu_type=dfu_type,
                             sd_size=sd_size,
                             app_size=app_size,
                             bl_size=bl_size)
            except RuntimeError:
                failed = True

            self.assertEqual(failed, expect_failed)

        test_size(DFUType.APPLICATION, sd_size=SD_SIZE, app_size=0, bl_size=BL_SIZE, expect_failed=True)
        test_size(DFUType.APPLICATION, sd_size=SD_SIZE, app_size=APP_SIZE, bl_size=BL_SIZE, expect_failed=False)
        test_size(DFUType.BOOTLOADER, sd_size=SD_SIZE, app_size=APP_SIZE, bl_size=0, expect_failed=True)
        test_size(DFUType.BOOTLOADER, sd_size=SD_SIZE, app_size=APP_SIZE, bl_size=BL_SIZE, expect_failed=False)
        test_size(DFUType.SOFTDEVICE, sd_size=0, app_size=APP_SIZE, bl_size=BL_SIZE, expect_failed=True)
        test_size(DFUType.SOFTDEVICE, sd_size=SD_SIZE, app_size=APP_SIZE, bl_size=BL_SIZE, expect_failed=False)
        test_size(DFUType.SOFTDEVICE_BOOTLOADER, sd_size=0, app_size=APP_SIZE, bl_size=BL_SIZE, expect_failed=True)
        test_size(DFUType.SOFTDEVICE_BOOTLOADER, sd_size=SD_SIZE, app_size=APP_SIZE, bl_size=0, expect_failed=True)
        test_size(DFUType.SOFTDEVICE_BOOTLOADER, sd_size=SD_SIZE, app_size=APP_SIZE, bl_size=BL_SIZE,
                  expect_failed=False)

    def test_init_packet(self):
        failed = False
        init_packet = InitPacketPB(hash_bytes=HASH_BYTES_A, hash_type=HASH_TYPE, dfu_type=DFU_TYPE, app_size=APP_SIZE)

        init_packet.set_signature(signature=SIGNATURE_BYTES_A, signature_type=SIGNATURE_TYPE)
        init_packet_serialized = init_packet.get_init_packet_pb_bytes()

        init_packet = pb.Packet()
        init_packet.ParseFromString(init_packet_serialized)
        self.assertEqual(init_packet.signed_command.command.init.hash.hash, HASH_BYTES_A)
        self.assertEqual(init_packet.signed_command.command.op_code, pb.INIT)


if __name__ == '__main__':
    unittest.main()
