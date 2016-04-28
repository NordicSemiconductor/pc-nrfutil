from dfu_init_pb2 import *
from init_packet import PacketField
from protobuf_to_dict import protobuf_to_dict
from model import HexType
'''
    Why have this wrapper?

        - No need to modify package.py when .proto is updated
        - Easier to reflect changes when .proto is updated
        - Perform validation, since this is not done using the 'required' feature of the .proto
        - Ease of testing
        - Minimize changes done to package.py
'''

PACKET_SIGN_TYPE_ECDSA = "ECDSA_P256_SHA256"
PACKET_SIGN_TYPE_ED25519 = "ED25519"

SIGN_TYPE_MAP = {
    PACKET_SIGN_TYPE_ED25519: signed_command_t.ED25519,
    PACKET_SIGN_TYPE_ECDSA: signed_command_t.ECDSA_P256_SHA256
}

HASH_TYPE_MAP = {
    'sha256': SHA256,
    'sha512': SHA512,
}

HEX_TYPE_TO_FW_TYPE_MAP = {
    HexType.APPLICATION:    APPLICATION,
    HexType.SOFTDEVICE:     SOFTDEVICE,
    HexType.BOOTLOADER:     BOOTLOADER,
    HexType.SD_BL:          SOFTDEVICE_BOOTLOADER
}


class PBPacket(object):
    def __init__(self, init_packet_fields):
        # Build dictionary structure used to represent the PB data
        self.signed_command = signed_command_t()
        self.init_command = self.signed_command.command.init_command

        for key, value in init_packet_fields.iteritems():
            if key == 'fw_version':
                self._set_fw_version(value)
            elif key == 'hw_version':
                self._set_hw_version(value)
            elif key == 'sd_req':
                self._set_sd_req(value)
            elif key == 'hash':
                self._set_hash(value)
            elif key == 'hash_type':
                self._set_hash_type(HASH_TYPE_MAP[value])
            elif key == 'sd_size':
                self._set_sd_size(value)
            elif key == 'app_size':
                self._set_app_size(value)
            elif key == 'bl_size':
                self._set_bl_size(value)
            elif key == 'fw_type':
                self._set_fw_type(HEX_TYPE_TO_FW_TYPE_MAP[value])

    def _set_fw_version(self, version):
        self.init_command.fw_version = version

    def _set_hw_version(self, version):
        self.init_command.hw_version = version

    def _set_sd_req(self, sd_req_list):
        self.init_command.sd_req.extend(list(set(sd_req_list)))

    def _set_fw_type(self, fw_type):
        self.init_command.type = fw_type

    def _set_sd_size(self, sd_size):
        self.init_command.sd_size = sd_size

    def _set_bl_size(self, bl_size):
        self.init_command.bl_size = bl_size

    def _set_app_size(self, app_size):
        self.init_command.app_size = app_size

    def _set_hash_type(self, hash_type):
        self.init_command.hash.hash_type = hash_type

    def _set_hash(self, hash_bytes):
        self.init_command.hash.hash = hash_bytes

    def set_sign_type(self, sign_type):
        self.signed_command.signature_type = SIGN_TYPE_MAP[sign_type]

    def set_sign(self, sign_bytes):
        self.signed_command.signature = sign_bytes

    def _is_valid(self):
        return self.signed_command.signature is not None

    def get_init_command_bytes(self):
        return self.init_command.SerializeToString()

    def get_init_command_dict(self):
        return protobuf_to_dict(self.init_command)

    def get_signed_command_bytes(self):
        return self.signed_command.SerializeToString()

    def generate_init_packet(self):
        return self.get_init_command_bytes()

    def __str__(self):
        return str(self.signed_command)


def test_pb_package():

    print "SUCCESS"


test_pb_package()

