#
# Copyright (c) 2018 Nordic Semiconductor ASA
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
import tempfile
import shutil
import os
import filecmp

from nordicsemi.zigbee.prod_config import ProductionConfig, ProductionConfigTooLargeException, ProductionConfigWrongException

class TestProductionConfig(unittest.TestCase):
    PRODUCTION_CONFIG_EXAMPLES_PATH = 'configs'
    PRODUCTION_CONFIG_GOLDEN_DATA_PATH = 'golden_data'

    def setUp(self):
        ''' Switch to a directory of the file and create a temporary directory to work in. '''
        script_abspath = os.path.abspath(__file__)
        script_dirname = os.path.dirname(script_abspath)
        os.chdir(script_dirname)

        self.work_directory = tempfile.mkdtemp(prefix="nrf_zigbee_production_config_tests_")

    def tearDown(self):
        ''' Remove a temporary directory. '''
        shutil.rmtree(self.work_directory, ignore_errors=True)

    def process_yaml_config(self, name):
        ''' Process the YAML config and generate an output hex file. '''
        input = os.path.join(self.PRODUCTION_CONFIG_EXAMPLES_PATH, name + '.yaml')
        output = os.path.join(self.work_directory, name + '.hex')

        try:
            pc = ProductionConfig(input)
        except ProductionConfigWrongException:
            self.fail("Error: Input YAML file format wrong.")

        try:
            pc.generate(output)
        except ProductionConfigTooLargeException as e:
            self.fail("Error: Production Config is too large.")

    def compare_hex_with_golden_data(self, name):
        ''' Compare the generated hex file with the golden vector. '''
        test = os.path.join(self.work_directory, name + '.hex')
        gold = os.path.join(self.PRODUCTION_CONFIG_GOLDEN_DATA_PATH, name + '.hex')

        return filecmp.cmp(test, gold)

    def generate_and_verify_production_config(self, name):
        ''' Generate and verify the production config. '''
        self.process_yaml_config(name)
        return self.compare_hex_with_golden_data(name)

    def test_channel_install_ieee_power_config(self):
        ''' Test config which contains 802.15.4 channel,
            install code, IEEE address and maximum Tx power.
        '''
        self.assertTrue(self.generate_and_verify_production_config('channel_install_ieee_power'))

    def test_install_ieee_power_config(self):
        ''' Test config which contains install code,
            IEEE address and maximum Tx power.
        '''
        self.assertTrue(self.generate_and_verify_production_config('install_ieee_power'))

    def test_install_ieee_config(self):
        self.assertTrue(self.generate_and_verify_production_config('install_ieee'))

    def test_install_config(self):
        self.assertTrue(self.generate_and_verify_production_config('install'))

    def test_empty_config(self):
        input = os.path.join(self.PRODUCTION_CONFIG_EXAMPLES_PATH, 'empty.yaml')
        self.assertRaises(ProductionConfigWrongException, ProductionConfig, input)

    def test_corrupt_config(self):
        input = os.path.join(self.PRODUCTION_CONFIG_EXAMPLES_PATH, 'corrupt.yaml')
        self.assertRaises(ProductionConfigWrongException, ProductionConfig, input)


if __name__ == '__main__':
    unittest.main()
