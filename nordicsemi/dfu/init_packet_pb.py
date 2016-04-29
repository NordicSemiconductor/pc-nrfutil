import dfu_cc_pb2 as pb
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
    PACKET_SIGN_TYPE_ED25519: pb.ED25519,
    PACKET_SIGN_TYPE_ECDSA: pb.ECDSA_P256_SHA256
}

HASH_TYPE_MAP = {
    'sha256': pb.SHA256,
    'sha512': pb.SHA512,
}

HEX_TYPE_TO_FW_TYPE_MAP = {
    HexType.APPLICATION:    pb.APPLICATION,
    HexType.SOFTDEVICE:     pb.SOFTDEVICE,
    HexType.BOOTLOADER:     pb.BOOTLOADER,
    HexType.SD_BL:          pb.SOFTDEVICE_BOOTLOADER
}


class InitPacketPB(object):
    def __init__(self,
                 hash_bytes,
                 dfu_type,
                 fw_version="0xffff",
                 hw_version="0xffff",
                 hash_type=pb.SHA256,
                 sd_size=None,
                 app_size=None,
                 bl_size=None,
                 sd_req=None
                 ):

        self.packet = pb.Packet()
        self.signed_command = self.packet.signed_command
        self.init_command = self.signed_command.command.init

        self.init_command.type = HEX_TYPE_TO_FW_TYPE_MAP[dfu_type]
        self.init_command.hash.hash = hash_bytes
        self.init_command.fw_version = fw_version
        self.init_command.hw_version = hw_version
        self.init_command.sd_req.extend(list(set(sd_req)))
        self.init_command.hash.hash_type = HASH_TYPE_MAP[hash_type]

        if sd_size:
            self.init_command.sd_size = sd_size
        if bl_size:
            self.init_command.bl_size = bl_size
        if app_size:
            self.init_command.app_size = app_size
        if not sd_req:
            self.init_command.sd_req = ["0xfffe"]  # Set to default value

    def _is_valid(self):
        return self.init_command.hash is not None  # TODO NRFFOSDK-6505 add checks for required fields

    def get_init_packet_pb_bytes(self):
        if self.signed_command.signature is not None:
            return self.packet.SerializeToString()
        else:
            raise RuntimeError("Did not set signature")

    def get_init_command_bytes(self):
        return self.init_command.SerializeToString()

    def set_signature(self, signature, signature_type):
        self.signed_command.signature = signature
        self.signed_command.signature_type = SIGN_TYPE_MAP[signature_type]

    def __str__(self):
        return str(self.init_command)