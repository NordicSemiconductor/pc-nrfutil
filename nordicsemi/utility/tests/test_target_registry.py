# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

import os
import unittest
from nordicsemi.utility.target_registry import TargetRegistry, EnvTargetDatabase
from nordicsemi.utility.target_registry import FileTargetDatabase


class TestTargetRegistry(unittest.TestCase):
    def setUp(self):
        script_abspath = os.path.abspath(__file__)
        script_dirname = os.path.dirname(script_abspath)
        os.chdir(script_dirname)

        # Setup the environment variables
        os.environ["NORDICSEMI_TARGET_1_SERIAL_PORT"] = "COM1"
        os.environ["NORDICSEMI_TARGET_1_PCA"] = "PCA10028"
        os.environ["NORDICSEMI_TARGET_1_DRIVE"] = "D:\\"
        os.environ["NORDICSEMI_TARGET_1_SEGGER_SN"] = "1231233333"

        os.environ["NORDICSEMI_TARGET_2_SERIAL_PORT"] = "COM2"
        os.environ["NORDICSEMI_TARGET_2_PCA"] = "PCA10028"
        os.environ["NORDICSEMI_TARGET_2_DRIVE"] = "E:\\"
        os.environ["NORDICSEMI_TARGET_2_SEGGER_SN"] = "3332222111"

    def test_get_targets_from_file(self):
        target_database = FileTargetDatabase("test_targets.json")
        target_repository = TargetRegistry(target_db=target_database)

        target = target_repository.find_one(target_id=1)
        assert target is not None
        assert target["drive"] == "d:\\"
        assert target["serial_port"] == "COM7"
        assert target["pca"] == "PCA10028"
        assert target["segger_sn"] == "123123123123"

        target = target_repository.find_one(target_id=2)
        assert target is not None
        assert target["drive"] == "e:\\"
        assert target["serial_port"] == "COM8"
        assert target["pca"] == "PCA10028"
        assert target["segger_sn"] == "321321321312"

    def test_get_targets_from_environment(self):
        target_database = EnvTargetDatabase()
        target_repository = TargetRegistry(target_db=target_database)

        target = target_repository.find_one(target_id=1)
        assert target is not None
        assert target["drive"] == "D:\\"
        assert target["serial_port"] == "COM1"
        assert target["pca"] == "PCA10028"
        assert target["segger_sn"] == "1231233333"

        target = target_repository.find_one(target_id=2)
        assert target is not None
        assert target["drive"] == "E:\\"
        assert target["serial_port"] == "COM2"
        assert target["pca"] == "PCA10028"
        assert target["segger_sn"] == "3332222111"


if __name__ == '__main__':
    unittest.main()
