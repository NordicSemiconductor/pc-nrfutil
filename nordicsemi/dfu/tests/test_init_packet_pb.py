# Copyright (c) 2015, Nordic Semiconductor
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of Nordic Semiconductor ASA nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import tempfile
import unittest
import shutil

from nordicsemi.dfu.model import HexType
from nordicsemi.dfu.init_packet_pb import *
from google.protobuf.message import EncodeError
import nordicsemi.dfu.dfu_cc_pb2 as pb


HASH_BYTES_A = b'123123123123'
HASH_TYPE = 'sha256'
SIGNATURE_BYTES_A = b'234827364872634876234'
SIGNATURE_TYPE = PACKET_SIGN_TYPE_ECDSA


class TestPackage(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_init_command(self):
        init_command_serialized = InitPacketPB(hash_bytes=HASH_BYTES_A,
                                               dfu_type=HexType.APPLICATION).get_init_command_bytes()

        init_command = pb.InitCommand()
        init_command.ParseFromString(init_command_serialized)

        self.assertEqual(init_command.hash.hash, HASH_BYTES_A)

    def test_init_packet(self):
        failed = False
        init_packet = InitPacketPB(hash_bytes=HASH_BYTES_A, dfu_type=HexType.APPLICATION)
        try:
            init_packet.get_init_packet_pb_bytes()
        except EncodeError:
            # Fails since we are missing signature
            failed = True

        self.assertTrue(failed)

        init_packet.set_signature(signature=SIGNATURE_BYTES_A, signature_type=SIGNATURE_TYPE)
        init_packet_serialized = init_packet.get_init_packet_pb_bytes()

        init_packet = pb.Packet()
        init_packet.ParseFromString(init_packet_serialized)
        self.assertEqual(init_packet.signed_command.command.init.hash.hash, HASH_BYTES_A)
        self.assertEqual(init_packet.signed_command.command.op_code, pb.INIT)

if __name__ == '__main__':
    unittest.main()
