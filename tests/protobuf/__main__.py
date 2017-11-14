
import unittest

import os, sys

sys.path.append(os.path.join('..', '..', 'nordicsemi'))

from nordicsemi.dfu.init_packet_pb import InitPacketPB, HashTypes, DFUType


class TestStringMethods(unittest.TestCase):

    #def test_upper(self):
        #self.assertEqual('foo'.upper(), 'FOO')

    #def test_isupper(self):
        #self.assertTrue('FOO'.isupper())
        #self.assertFalse('Foo'.isupper())

    #def test_split(self):
        #s = 'hello world'
        #self.assertEqual(s.split(), ['hello', 'world'])
        ## check that s.split fails when the separator is not a string
        #with self.assertRaises(TypeError):
            #s.split(2)



    def test_construct_from_empty_string(self):
        """
        Raises an error when the trying to construct a init packet from a
        string that does not contain "app_size"
        """

        self.assertRaisesRegexp(
            RuntimeError,
            "app_size is not set. It must be set when type is APPLICATION",
            InitPacketPB,
            from_bytes = "");


    def test_construct_from_params(self):
        """
        Raises an error when the trying to construct a init packet from a
        string that does not contain "app_size"
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



if __name__ == '__main__':
    unittest.main()

