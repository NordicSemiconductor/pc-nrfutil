
import unittest
import os, sys

sys.path.append(
    os.path.normpath(
        os.path.join(
            os.path.dirname(__file__), '..', '..'
        )
    )
)

from nordicsemi.dfu.init_packet_pb import InitPacketPB, HashTypes, DFUType, SigningTypes

class TestStringMethods(unittest.TestCase):

    def test_construct_from_empty_string(self):
        """
        Raises an error when trying to construct a init packet from an
        empty buffer
        """

        self.assertRaisesRegex(
            RuntimeError,
            "app_size is not set. It must be set when type is APPLICATION",
            InitPacketPB,
            from_bytes = "")


    def test_construct_from_params(self):
        """
        Gracefully constructs an init packet protobuffer from parameters without bytes
        """

        i = InitPacketPB(
            from_bytes = None,

            hash_bytes = b"",
            hash_type = HashTypes.SHA256,
            dfu_type = DFUType.APPLICATION,
            is_debug=False,
            fw_version=0xffffffff,
            hw_version=0xffffffff,
            sd_size=0,
            app_size=1234,
            bl_size=0,
            sd_req=[0xffffffff]
            )

        protobuf_bytes = i.get_init_command_bytes() # bytes only for the InitCommand
        hex_bytes = protobuf_bytes.encode('hex_codec')

        self.assertEqual(hex_bytes, "08ffffffff0f10ffffffff0f1a05ffffffff0f20002800"
                         "300038d2094204080312004800")


    def test_construct_from_params_and_sign(self):
        """
        Gracefully constructs an init packet protobuffer from parameters without bytes,
        then signs it
        """

        i = InitPacketPB(
            from_bytes = None,

            hash_bytes = b"",
            hash_type = HashTypes.SHA256,
            dfu_type = DFUType.APPLICATION,
            is_debug=False,
            fw_version=0xffffffff,
            hw_version=0xffffffff,
            sd_size=0,
            app_size=1234,
            bl_size=0,
            sd_req=[0xffffffff]
            )

        i.set_signature(b"signature bytes go here", SigningTypes.ECDSA_P256_SHA256)

        protobuf_bytes = i.get_init_packet_pb_bytes() # Bytes for the whole Packet
        hex_bytes = protobuf_bytes.encode('hex_codec')

        self.assertEqual(hex_bytes, "12450a280801122408ffffffff0f10ffffffff0f1a"
        "05ffffffff0f20002800300038d209420408031200480010001a177369676e61747572"
        "6520627974657320676f2068657265")


    def test_construct_from_params_and_not_sign(self):
        """
        Gracefully constructs an init packet protobuffer from parameters without bytes,
        skipping the signature process
        """

        i = InitPacketPB(
            from_bytes = None,

            hash_bytes = b"",
            hash_type = HashTypes.SHA256,
            dfu_type = DFUType.APPLICATION,
            is_debug=False,
            fw_version=0xffffffff,
            hw_version=0xffffffff,
            sd_size=0,
            app_size=1234,
            bl_size=0,
            sd_req=[0xffffffff]
            )

        protobuf_bytes = i.get_init_packet_pb_bytes() # Bytes for the whole Packet
        hex_bytes = protobuf_bytes.encode('hex_codec')

        self.assertEqual(hex_bytes, "0a280801122408ffffffff0f10ffffffff0f1a"
        "05ffffffff0f20002800300038d2094204080312004800")



if __name__ == '__main__':
    unittest.main()

