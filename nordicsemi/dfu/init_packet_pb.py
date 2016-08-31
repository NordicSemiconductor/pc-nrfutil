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
import dfu_cc_pb2 as pb
from enum import Enum

class SigningTypes(Enum):
    ECDSA_P256_SHA256 = pb.ECDSA_P256_SHA256
    ED25519 = pb.ED25519

class CommandTypes(Enum):
    RESET = pb.RESET
    INIT = pb.INIT

class HashTypes(Enum):
    NONE = pb.NO_HASH
    CRC = pb.CRC
    SHA128 = pb.SHA128
    SHA256 = pb.SHA256
    SHA512 = pb.SHA512


class DFUType(Enum):
    APPLICATION = pb.APPLICATION
    SOFTDEVICE = pb.SOFTDEVICE
    BOOTLOADER = pb.BOOTLOADER
    SOFTDEVICE_BOOTLOADER = pb.SOFTDEVICE_BOOTLOADER


class InitPacketPB(object):
    def __init__(self,
                 from_bytes = None,
                 hash_bytes = None,
                 hash_type = None,
                 dfu_type = None,
                 is_debug=False,
                 fw_version=0xffffffff,
                 hw_version=0xffffffff,
                 sd_size=0,
                 app_size=0,
                 bl_size=0,
                 sd_req=None
                 ):

        if from_bytes is not None:
            # construct from a stream
            self.packet = pb.Packet()
            self.packet.ParseFromString(from_bytes)
            self.signed_command = self.packet.signed_command
            self.init_command = self.signed_command.command.init
        else:
            # construct from input variables
            if not sd_req:
                sd_req = [0xfffe]  # Set to default value
            self.packet = pb.Packet()
            self.signed_command = self.packet.signed_command
            self.init_command = self.signed_command.command.init
            self.init_command.hash.hash_type = hash_type.value
            self.init_command.type = dfu_type.value
            self.init_command.hash.hash = hash_bytes
            self.init_command.is_debug = is_debug
            self.init_command.fw_version = fw_version
            self.init_command.hw_version = hw_version
            self.init_command.sd_req.extend(list(set(sd_req)))
            self.init_command.sd_size = sd_size
            self.init_command.bl_size = bl_size
            self.init_command.app_size = app_size
            self.signed_command.command.op_code = pb.INIT

        self._validate()

    def _validate(self):
        if self.init_command.type == pb.APPLICATION and self.init_command.app_size == 0:
            raise RuntimeError("app_size is not set. It must be set when type is APPLICATION")
        elif self.init_command.type == pb.SOFTDEVICE and self.init_command.sd_size == 0:
            raise RuntimeError("sd_size is not set. It must be set when type is SOFTDEVICE")
        elif self.init_command.type == pb.BOOTLOADER and self.init_command.bl_size == 0:
            raise RuntimeError("bl_size is not set. It must be set when type is BOOTLOADER")
        elif self.init_command.type == pb.SOFTDEVICE_BOOTLOADER and \
                (self.init_command.sd_size == 0 or self.init_command.bl_size == 0):
            raise RuntimeError("Either sd_size or bl_size is not set. Both must be set when type "
                               "is SOFTDEVICE_BOOTLOADER")

        if self.init_command.fw_version < 0 or self.init_command.fw_version > 0xffffffff or \
           self.init_command.hw_version < 0 or self.init_command.hw_version > 0xffffffff:
            raise RuntimeError("Invalid range of firmware argument. [0 - 0xffffff] is valid range")

    def _is_valid(self):
        try:
            self._validate()
        except RuntimeError:
            return False

        return self.signed_command.signature is not None

    def get_init_packet_pb_bytes(self):
        if self.signed_command.signature is not None:
            return self.packet.SerializeToString()
        else:
            raise RuntimeError("Did not set signature")

    def get_init_command_bytes(self):
        return self.init_command.SerializeToString()

    def set_signature(self, signature, signature_type):
        self.signed_command.signature = signature
        self.signed_command.signature_type = signature_type.value

    def __str__(self):
        return str(self.init_command)
