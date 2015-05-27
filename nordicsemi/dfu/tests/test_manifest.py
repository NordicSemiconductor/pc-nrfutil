# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

import copy
import json
import unittest

from nordicsemi.dfu.init_packet import PacketField
from nordicsemi.dfu.manifest import ManifestGenerator, Manifest
from nordicsemi.dfu.model import HexType
from nordicsemi.dfu.package import FirmwareKeys


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.firmwares_data_a = {}

        init_packet_data_a = {
            PacketField.DEVICE_TYPE: 1,
            PacketField.DEVICE_REVISION: 2,
            PacketField.APP_VERSION: 1000,
            PacketField.REQUIRED_SOFTDEVICES_ARRAY: [22, 11],
            PacketField.COMPRESSION_TYPE: 10,
            PacketField.NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_HASH:
                '\xc9\xd3\xbfi\xf2\x1e\x88\xa01\x1e\r\xd2BSa\x12\xf8BW\x9b\xef&Z$\xbd\x02U\xfdD?u\x9e'
        }

        self.firmwares_data_a[HexType.APPLICATION] = {
            FirmwareKeys.BIN_FILENAME: "app_fw.bin",
            FirmwareKeys.DAT_FILENAME: "app_fw.dat",
            FirmwareKeys.INIT_PACKET_DATA: init_packet_data_a,
            FirmwareKeys.ENCRYPT: False}

        self.firmwares_data_a[HexType.SD_BL] = {
            FirmwareKeys.BIN_FILENAME: "sd_bl_fw.bin",
            FirmwareKeys.DAT_FILENAME: "sd_bl_fw.dat",
            FirmwareKeys.INIT_PACKET_DATA: copy.copy(init_packet_data_a),  # Fake the hash
            FirmwareKeys.BL_SIZE: 50,
            FirmwareKeys.SD_SIZE: 90
        }

        self.firmwares_data_b = {}

        init_packet_data_b = {
            PacketField.DEVICE_TYPE: 1,
            PacketField.DEVICE_REVISION: 2,
            PacketField.APP_VERSION: 1000,
            PacketField.REQUIRED_SOFTDEVICES_ARRAY: [22, 11],
            PacketField.NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_CRC16: 0xfaae
        }

        self.firmwares_data_b[HexType.APPLICATION] = {
            FirmwareKeys.BIN_FILENAME: "app_fw.bin",
            FirmwareKeys.DAT_FILENAME: "app_fw.dat",
            FirmwareKeys.INIT_PACKET_DATA: init_packet_data_b
        }

        self.firmwares_data_b[HexType.SD_BL] = {
            FirmwareKeys.BIN_FILENAME: "sd_bl_fw.bin",
            FirmwareKeys.DAT_FILENAME: "sd_bl_fw.dat",
            FirmwareKeys.INIT_PACKET_DATA: copy.copy(init_packet_data_b),  # Fake the hash
            FirmwareKeys.BL_SIZE: 50,
            FirmwareKeys.SD_SIZE: 90
        }

        self.firmwares_data_c = {}

        init_packet_data_c = {
            PacketField.DEVICE_TYPE: 1,
            PacketField.DEVICE_REVISION: 2,
            PacketField.APP_VERSION: 1000,
            PacketField.REQUIRED_SOFTDEVICES_ARRAY: [22, 11],
            PacketField.NORDIC_PROPRIETARY_OPT_DATA_FIRMWARE_CRC16: 0xfaae
        }

        self.firmwares_data_c[HexType.APPLICATION] = {
            FirmwareKeys.BIN_FILENAME: "app_fw.bin",
            FirmwareKeys.DAT_FILENAME: "app_fw.dat",
            FirmwareKeys.INIT_PACKET_DATA: init_packet_data_c
        }

    def test_generate_manifest(self):
        r = ManifestGenerator(0.5, self.firmwares_data_a)

        _json = json.loads(r.generate_manifest())

        # Test for presence of attributes in document
        self.assertIn('manifest', _json)

        manifest = _json['manifest']
        self.assertIn('application', manifest)

        application = manifest['application']
        self.assertIn('init_packet_data', application)
        self.assertIn('dat_file', application)
        self.assertIn('bin_file', application)

        init_packet_data = application['init_packet_data']
        self.assertNotIn('packet_version', init_packet_data)
        self.assertIn('firmware_hash', init_packet_data)
        self.assertIn('softdevice_req', init_packet_data)
        self.assertIn('device_revision', init_packet_data)
        self.assertIn('device_type', init_packet_data)
        self.assertIn('application_version', init_packet_data)
        self.assertIn('compression_type', init_packet_data)

        # Test for values in document
        self.assertEqual("app_fw.bin", application['bin_file'])
        self.assertEqual("app_fw.dat", application['dat_file'])

        self.assertNotIn('packet_version', init_packet_data)
        self.assertEqual('c9d3bf69f21e88a0311e0dd242536112f842579bef265a24bd0255fd443f759e',
                         init_packet_data['firmware_hash'])
        self.assertEqual(10, init_packet_data['compression_type'])
        self.assertEqual(1000, init_packet_data['application_version'])
        self.assertEqual(1, init_packet_data['device_type'])
        self.assertEqual(2, init_packet_data['device_revision'])
        self.assertEqual([22, 11], init_packet_data['softdevice_req'])

        # Test softdevice_bootloader
        bl_sd = manifest['softdevice_bootloader']
        self.assertIsNotNone(bl_sd)
        self.assertEqual(90, bl_sd['sd_size'])
        self.assertEqual(50, bl_sd['bl_size'])

        # Test for values in document
        self.assertEqual("sd_bl_fw.bin", bl_sd['bin_file'])
        self.assertEqual("sd_bl_fw.dat", bl_sd['dat_file'])

    def test_manifest_a(self):
        r = ManifestGenerator(0.5, self.firmwares_data_a)
        m = Manifest.from_json(r.generate_manifest())
        self.assertIsNotNone(m)
        self.assertIsNotNone(m.application)
        self.assertEqual("app_fw.bin", m.application.bin_file)
        self.assertEqual("app_fw.dat", m.application.dat_file)
        self.assertIsNone(m.bootloader)
        self.assertIsNone(m.softdevice)
        self.assertIsNotNone(m.softdevice_bootloader)
        self.assertEqual(90, m.softdevice_bootloader.sd_size)
        self.assertEqual(50, m.softdevice_bootloader.bl_size)
        self.assertEqual("sd_bl_fw.bin", m.softdevice_bootloader.bin_file)
        self.assertEqual("sd_bl_fw.dat", m.softdevice_bootloader.dat_file)

    def test_manifest_b(self):
        r = ManifestGenerator("0.5", self.firmwares_data_b)
        m = Manifest.from_json(r.generate_manifest())
        self.assertIsNotNone(m)
        self.assertIsNotNone(m.application)
        self.assertEqual("app_fw.bin", m.application.bin_file)
        self.assertEqual("app_fw.dat", m.application.dat_file)
        self.assertIsNone(m.bootloader)
        self.assertIsNone(m.softdevice)
        self.assertIsNotNone(m.softdevice_bootloader)
        self.assertEqual(90, m.softdevice_bootloader.sd_size)
        self.assertEqual(50, m.softdevice_bootloader.bl_size)
        self.assertEqual("sd_bl_fw.bin", m.softdevice_bootloader.bin_file)
        self.assertEqual("sd_bl_fw.dat", m.softdevice_bootloader.dat_file)
        self.assertEqual(0xfaae, m.application.init_packet_data.firmware_crc16)
        self.assertEqual(0xfaae, m.softdevice_bootloader.init_packet_data.firmware_crc16)

    def test_manifest_c(self):
        r = ManifestGenerator("0.5", self.firmwares_data_c)
        m = Manifest.from_json(r.generate_manifest())
        self.assertIsNotNone(m)
        self.assertIsNotNone(m.application)
        self.assertEqual('app_fw.bin', m.application.bin_file)
        self.assertEqual('app_fw.dat', m.application.dat_file)
        self.assertIsNone(m.bootloader)
        self.assertIsNone(m.softdevice)
        self.assertIsNone(m.softdevice_bootloader)
        self.assertEqual(0xfaae, m.application.init_packet_data.firmware_crc16)

if __name__ == '__main__':
    unittest.main()
