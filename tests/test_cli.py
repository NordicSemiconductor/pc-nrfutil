""" 
The tests seems to work with `python -m unittest`, but not by being called directly from the CLI 
The setUp is called twice, and crashes when being asked to  do a `cd ./tests` for a second time 
Look into a cleanup function 

The behavior is inconsistent between 3.9 and 3.7 (3.7 fails)
"""
import os
import unittest
from click.testing import CliRunner
from nordicsemi import __main__


class TestManifest(unittest.TestCase):
    runner = CliRunner()
    cli = __main__.cli
    original_path = os.path.abspath(os.path.curdir)

    def setUp(self):
        script_abspath = os.path.abspath(__file__)
        script_dirname = os.path.dirname(script_abspath)
        self.original_path = os.path.abspath(os.path.curdir) # Make it possible to go back 
        os.chdir(script_dirname)

    def tearDown(self) -> None:
        """ 
        Go back to the old dir
        """
        os.chdir(self.original_path)
    def test_pkg_gen(self):
        result = self.runner.invoke(self.cli,
                                    ['pkg', 'generate',
                                     '--application', 'resources/dfu_test_app_hrm_s130.hex',
                                     '--hw-version', '52', '--sd-req', '0', '--application-version',
                                     '0', '--sd-id', '0x008C', 'test.zip'])
        self.assertIsNone(result.exception)

    def test_dfu_ble_address(self):
        argumentList = ['dfu', 'ble', '-ic', 'NRF52', '-p', 'port', '-pkg',
                        'resources/test_package.zip', '--address']

        address = 'AABBCC112233'
        result = self.runner.invoke(self.cli, argumentList + [address])
        self.assertTrue('Error: Invalid value for address' not in result.output)
        self.assertTrue('Board not found' in str(result.exception))

        address = 'AA:BB:CC:11:22:33'
        result = self.runner.invoke(self.cli, argumentList + [address])
        self.assertTrue('Error: Invalid value for address' not in result.output)
        self.assertTrue('Board not found' in str(result.exception))

        address = 'AABBCC11223'
        result = self.runner.invoke(self.cli, argumentList + [address])
        self.assertTrue('Error: Invalid value for address' in result.output)
        self.assertIsInstance(result.exception, SystemExit)
        self.assertEqual(result.exception.code, SystemExit(2).code)

        address = 'AABBCC1122334'
        result = self.runner.invoke(self.cli, argumentList + [address])
        self.assertTrue('Error: Invalid value for address' in result.output)
        self.assertIsInstance(result.exception, SystemExit)
        self.assertEqual(result.exception.code, SystemExit(2).code)


if __name__ == '__main__':
    unittest.main()
