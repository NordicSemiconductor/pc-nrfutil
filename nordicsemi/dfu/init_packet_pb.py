import dfu_cc_pb2 as pb
from enum import Enum


class SigningTypes(Enum):
    ED25519 = pb.ED25519
    ECDSA_P256_SHA256 = pb.ECDSA_P256_SHA256


class HashTypes(Enum):
    SHA256 = pb.SHA256
    SHA512 = pb.SHA512


class DFUType(Enum):
    APPLICATION = pb.APPLICATION
    SOFTDEVICE = pb.SOFTDEVICE
    SOFTDEVICE_BOOTLOADER = pb.SOFTDEVICE_BOOTLOADER
    BOOTLOADER = pb.BOOTLOADER


class InitPacketPB(object):
    def __init__(self,
                 hash_bytes,
                 hash_type,
                 dfu_type,
                 fw_version=0xffffffff,
                 hw_version=0xffffffff,
                 sd_size=0,
                 app_size=0,
                 bl_size=0,
                 sd_req=None
                 ):

        if not sd_req:
            sd_req = [0xfffe]  # Set to default value
        self.packet = pb.Packet()
        self.signed_command = self.packet.signed_command
        self.init_command = self.signed_command.command.init
        self.init_command.hash.hash_type = hash_type.value
        self.init_command.type = dfu_type.value
        self.init_command.hash.hash = hash_bytes
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
