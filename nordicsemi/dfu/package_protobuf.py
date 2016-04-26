import dfu_init_pb2 as dpb

'''
    Why have this wrapper?

        - No need to modify package.py when .proto is updated
        - Easier to reflect changes when .proto is updated
        - Perform validation, since this is not done using the 'required' feature of the .proto
        - Ease of testing
        - Minimize changes done to package.py
'''


class PBPackage(object):
    def __init__(self, op_code):
        self.command = dpb.command()
        if op_code == dpb.command.INIT:
            self.init = self.command.init_packet

    def set_fw_version(self, version):
        self.init.fw_version = version

    def set_hw_version(self, version):
        self.init.hw_version = version

    def extend_sd_req(self, sd_req_list):
        self.init.sd_req.extend(list(set(sd_req_list)))  # Removes duplicates

    def set_fw_type(self, fw_type):
        self.init.type = fw_type

    def set_size(self, size):
        if self.init.type == dpb.init.SOFTDEVICE:
            self.init.sd_size = size
        elif self.init.type == dpb.init.BOOTLOADER:
            self.init.bl_size = size
        elif self.init.type == dpb.init.SOFTDEVICE_BOOTLOADER:
            self.init.sd_bl_size = size
        elif self.init.type == dpb.init.APPLICATION:
            self.init.app_size = size
        else:
            raise RuntimeError("Size has been set without type of packet being specified correctly")

    def set_hash_type(self, hash_type):
        self.init.hash_type = hash_type

    def set_hash(self, hash_bytes):
        self.init.hash = hash_bytes

    def set_sign_type(self, sign_type):
        self.init.signature_type = sign_type

    def set_sign(self, sign_bytes):
        self.init.signature = sign_bytes

    def is_valid(self):
        return self.command is not None and self.init is not None

    def get_bytes(self):
        if not self.is_valid():
            raise RuntimeError("Incorrect state when trying to get bytes")
        return self.command.SerializeToString()

    def __str__(self):
        return str(self.command)


def test_pb_package():
    p = PBPackage(dpb.command.INIT)
    p.set_fw_type(dpb.init.APPLICATION)
    p.set_hash(b'123')
    p.set_hash_type(dpb.init.SHA128)
    p.set_fw_version(666)
    p.set_hw_version(333)
    p.extend_sd_req([123, 123, 123])
    assert len(p.init.sd_req) == 1
    assert p.init.sd_req == [123]
    assert p.init.hw_version == 333
    assert p.init.fw_version == 666
    assert p.init.hash == b'123'
    assert p.init.hash_type == dpb.init.SHA128
    print "SUCCESS"


test_pb_package()

