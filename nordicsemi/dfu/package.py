#
# Copyright (c) 2016 Nordic Semiconductor ASA
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

# Python standard library
import os
import tempfile
import shutil
import binascii
from enum import Enum

# 3rd party libraries
from zipfile import ZipFile
import hashlib


# Nordic libraries
from pc_ble_driver_py.exceptions import NordicSemiException
from nordicsemi.dfu.nrfhex import *
from nordicsemi.dfu.init_packet_pb import *
from nordicsemi.dfu.manifest import ManifestGenerator, Manifest
from nordicsemi.dfu.model import HexType, FirmwareKeys
from nordicsemi.dfu.crc16 import *

from signing import Signing

HexTypeToInitPacketFwTypemap = {
    HexType.APPLICATION: DFUType.APPLICATION,
    HexType.BOOTLOADER: DFUType.BOOTLOADER,
    HexType.SOFTDEVICE: DFUType.SOFTDEVICE,
    HexType.SD_BL: DFUType.SOFTDEVICE_BOOTLOADER
}


class PacketField(Enum):
    DEBUG_MODE = 1
    HW_VERSION = 2
    FW_VERSION = 3
    REQUIRED_SOFTDEVICES_ARRAY = 4

class Package(object):
    """
        Packages and unpacks Nordic DFU packages. Nordic DFU packages are zip files that contains firmware and meta-information
        necessary for utilities to perform a DFU on nRF5X devices.

        The internal data model used in Package is a dictionary. The dictionary is expressed like this in
         json format:

         {
            "manifest": {
                "bootloader": {
                    "bin_file": "asdf.bin",
                    "dat_file": "asdf.dat",
                    "init_packet_data": {
                        "application_version": null,
                        "device_revision": null,
                        "device_type": 5,
                        "firmware_hash": "asdfasdkfjhasdkfjashfkjasfhaskjfhkjsdfhasjkhf",
                        "softdevice_req": [
                            17,
                            18
                        ]
                    }
                }
        }

        Attributes application, bootloader, softdevice, softdevice_bootloader shall not be put into the manifest if they are null

    """

    DEFAULT_DEBUG_MODE = False
    DEFAULT_HW_VERSION = 0xFFFFFFFF
    DEFAULT_APP_VERSION = 0xFFFFFFFF
    DEFAULT_BL_VERSION = 0xFFFFFFFF
    DEFAULT_SD_REQ = [0xFFFE]
    DEFAULT_DFU_VER = 0.5
    MANIFEST_FILENAME = "manifest.json"

    def __init__(self,
                 debug_mode=DEFAULT_DEBUG_MODE,
                 hw_version=DEFAULT_HW_VERSION,
                 app_version=DEFAULT_APP_VERSION,
                 bl_version=DEFAULT_BL_VERSION,
                 sd_req=DEFAULT_SD_REQ,
                 app_fw=None,
                 bootloader_fw=None,
                 softdevice_fw=None,
                 key_file=None):
        """
        Constructor that requires values used for generating a Nordic DFU package.

        :param int debug_mode: Debug init-packet field
        :param int hw_version: Hardware version init-packet field
        :param int app_version: App version init-packet field
        :param int bl_version: Bootloader version init-packet field
        :param list sd_req: Softdevice Requirement init-packet field
        :param str app_fw: Path to application firmware file
        :param str bootloader_fw: Path to bootloader firmware file
        :param str softdevice_fw: Path to softdevice firmware file
        :param str key_file: Path to Signing key file (PEM)
        :return: None
        """

        init_packet_vars = {}
        if debug_mode is not None:
            init_packet_vars[PacketField.DEBUG_MODE] = debug_mode

        if hw_version is not None:
            init_packet_vars[PacketField.HW_VERSION] = hw_version

        if sd_req is not None:
            init_packet_vars[PacketField.REQUIRED_SOFTDEVICES_ARRAY] = sd_req

        self.firmwares_data = {}

        if app_fw:
            self.__add_firmware_info(firmware_type=HexType.APPLICATION,
                                     firmware_version=app_version,
                                     filename=app_fw,
                                     init_packet_data=init_packet_vars)

        if bootloader_fw:
            self.__add_firmware_info(firmware_type=HexType.BOOTLOADER,
                                     firmware_version=bl_version,
                                     filename=bootloader_fw,
                                     init_packet_data=init_packet_vars)

        if softdevice_fw:
            self.__add_firmware_info(firmware_type=HexType.SOFTDEVICE,
                                     firmware_version=0xFFFFFFFF,
                                     filename=softdevice_fw,
                                     init_packet_data=init_packet_vars)

        if key_file:
            self.key_file = key_file

        self.work_dir = None
        self.manifest = None

    def __del__(self):
        """
        Destructor removes the temporary working directory
        :return:
        """
        if self.work_dir is not None:
            shutil.rmtree(self.work_dir)
        self.work_dir = None

    def rm_work_dir(self, preserve):
        # Delete the temporary directory
        if self.work_dir is not None:
            if not preserve:
                shutil.rmtree(self.work_dir)

        self.work_dir = None

    def parse_package(self, filename, preserve_work_dir=False):
        self.work_dir = self.__create_temp_workspace()

        self.zip_file = filename
        self.zip_dir  = os.path.join(self.work_dir, 'unpacked_zip')
        self.manifest = Package.unpack_package(filename, self.zip_dir)
        
        self.rm_work_dir(preserve_work_dir)

    def image_str(self, index, hex_type, img):
        type_strs = {HexType.SD_BL : "sd_bl", 
                    HexType.SOFTDEVICE : "softdevice",
                    HexType.BOOTLOADER : "bootloader",
                    HexType.APPLICATION : "application" }

        # parse init packet
        with open(os.path.join(self.zip_dir, img.dat_file), "rb") as imgf:
            initp_bytes = imgf.read()

        initp = InitPacketPB(from_bytes=initp_bytes)

        sd_req = ""
        for x in initp.init_command.sd_req:
            sd_req = sd_req + "0x{0:02X}, ".format(x)

        if len(sd_req) != 0:
            sd_req = sd_req[:-2]

        s = """|
|- Image #{0}:
   |- Type: {1}
   |- Image file: {2}
   |- Init packet file: {3}
      |
      |- op_code: {4}
      |- signature_type: {5}
      |- signature (little-endian): {6}
      |
      |- fw_version: 0x{7:08X} ({7})
      |- hw_version 0x{8:08X} ({8})
      |- sd_req: {9}
      |- type: {10}
      |- sd_size: {11}
      |- bl_size: {12}
      |- app_size: {13}
      |
      |- hash_type: {14}
      |- hash (little-endian): {15}
      |
      |- is_debug: {16}

""".format(index,
        type_strs[hex_type],
        img.bin_file,
        img.dat_file,
        CommandTypes(initp.signed_command.command.op_code).name,
        SigningTypes(initp.signed_command.signature_type).name,
        binascii.hexlify(initp.signed_command.signature),
        initp.init_command.fw_version,
        initp.init_command.hw_version,
        sd_req,
        DFUType(initp.init_command.type).name,
        initp.init_command.sd_size,
        initp.init_command.bl_size,
        initp.init_command.app_size,
        HashTypes(initp.init_command.hash.hash_type).name,
        binascii.hexlify(initp.init_command.hash.hash),
        initp.init_command.is_debug,
        )

        return s

    def __str__(self):
        
        imgs = ""
        i = 0
        if self.manifest.softdevice_bootloader:
            imgs = imgs + self.image_str(i, HexType.SD_BL, self.manifest.softdevice_bootloader)
            i = i + 1

        if self.manifest.softdevice:
            imgs = imgs + self.image_str(i, HexType.SOFTDEVICE, self.manifest.softdevice)
            i = i + 1

        if self.manifest.bootloader:
            imgs = imgs + self.image_str(i, HexType.BOOTLOADER, self.manifest.bootloader)
            i = i + 1

        if self.manifest.application:
            imgs = imgs + self.image_str(i, HexType.APPLICATION, self.manifest.application)
            i = i + 1

        s = """
DFU Package: <{0}>:
|
|- Image count: {1}
""".format(self.zip_file, i)

        s = s + imgs
        return s

    def generate_package(self, filename, preserve_work_dir=False):
        """
        Generates a Nordic DFU package. The package is a zip file containing firmware(s) and metadata required
        for Nordic DFU applications to perform DFU onn nRF5X devices.

        :param str filename: Filename for generated package.
        :param bool preserve_work_dir: True to preserve the temporary working directory.
        Useful for debugging of a package, and if the user wants to look at the generated package without having to
        unzip it.
        :return: None
        """
        self.zip_file = filename
        self.work_dir = self.__create_temp_workspace()

        if Package._is_bootloader_softdevice_combination(self.firmwares_data):
            # Removing softdevice and bootloader data from dictionary and adding the combined later
            softdevice_fw_data = self.firmwares_data.pop(HexType.SOFTDEVICE)
            bootloader_fw_data = self.firmwares_data.pop(HexType.BOOTLOADER)

            softdevice_fw_name = softdevice_fw_data[FirmwareKeys.FIRMWARE_FILENAME]
            bootloader_fw_name = bootloader_fw_data[FirmwareKeys.FIRMWARE_FILENAME]

            new_filename = "sd_bl.bin"
            sd_bl_file_path = os.path.join(self.work_dir, new_filename)

            nrf_hex = nRFHex(softdevice_fw_name, bootloader_fw_name)
            nrf_hex.tobinfile(sd_bl_file_path)

            softdevice_size = nrf_hex.size()
            bootloader_size = nrf_hex.bootloadersize()

            self.__add_firmware_info(firmware_type=HexType.SD_BL,
                                     firmware_version=bootloader_fw_data[FirmwareKeys.INIT_PACKET_DATA][PacketField.FW_VERSION],  # use bootloader version in combination with SD
                                     filename=sd_bl_file_path,
                                     init_packet_data=softdevice_fw_data[FirmwareKeys.INIT_PACKET_DATA],
                                     sd_size=softdevice_size,
                                     bl_size=bootloader_size)

        for key, firmware_data in self.firmwares_data.iteritems():

            # Normalize the firmware file and store it in the work directory
            firmware_data[FirmwareKeys.BIN_FILENAME] = \
                Package.normalize_firmware_to_bin(self.work_dir, firmware_data[FirmwareKeys.FIRMWARE_FILENAME])

            # Calculate the hash for the .bin file located in the work directory
            bin_file_path = os.path.join(self.work_dir, firmware_data[FirmwareKeys.BIN_FILENAME])
            firmware_hash = Package.calculate_sha256_hash(bin_file_path)
            bin_length = int(Package.calculate_file_size(bin_file_path))

            sd_size = 0
            bl_size = 0
            app_size = 0
            if key == HexType.APPLICATION:
                app_size = bin_length
            elif key == HexType.SOFTDEVICE:
                sd_size = bin_length
            elif key == HexType.BOOTLOADER:
                bl_size = bin_length
            elif key == HexType.SD_BL:
                bl_size = firmware_data[FirmwareKeys.BL_SIZE]
                sd_size = firmware_data[FirmwareKeys.SD_SIZE]

            init_packet = InitPacketPB(
                            from_bytes = None,
                            hash_bytes=firmware_hash,
                            hash_type=HashTypes.SHA256,
                            dfu_type=HexTypeToInitPacketFwTypemap[key],
                            is_debug=firmware_data[FirmwareKeys.INIT_PACKET_DATA][PacketField.DEBUG_MODE],
                            fw_version=firmware_data[FirmwareKeys.INIT_PACKET_DATA][PacketField.FW_VERSION],
                            hw_version=firmware_data[FirmwareKeys.INIT_PACKET_DATA][PacketField.HW_VERSION],
                            sd_size=sd_size,
                            app_size=app_size,
                            bl_size=bl_size,
                            sd_req=firmware_data[FirmwareKeys.INIT_PACKET_DATA][PacketField.REQUIRED_SOFTDEVICES_ARRAY])

            signer = Signing()
            signer.load_key(self.key_file)
            signature = signer.sign(init_packet.get_init_command_bytes())
            init_packet.set_signature(signature, SigningTypes.ECDSA_P256_SHA256)

            # Store the .dat file in the work directory
            init_packet_filename = firmware_data[FirmwareKeys.BIN_FILENAME].replace(".bin", ".dat")

            with open(os.path.join(self.work_dir, init_packet_filename), 'wb') as init_packet_file:
                init_packet_file.write(init_packet.get_init_packet_pb_bytes())

            firmware_data[FirmwareKeys.DAT_FILENAME] = \
                init_packet_filename

        # Store the manifest to manifest.json
        manifest = self.create_manifest()

        with open(os.path.join(self.work_dir, Package.MANIFEST_FILENAME), "w") as manifest_file:
            manifest_file.write(manifest)

        # Package the work_dir to a zip file
        Package.create_zip_package(self.work_dir, filename)

        # Delete the temporary directory
        self.rm_work_dir(preserve_work_dir)

    @staticmethod
    def __create_temp_workspace():
        return tempfile.mkdtemp(prefix="nrf_dfu_pkg_")

    @staticmethod
    def create_zip_package(work_dir, filename):
        files = os.listdir(work_dir)

        with ZipFile(filename, 'w') as package:
            for _file in files:
                file_path = os.path.join(work_dir, _file)
                package.write(file_path, _file)

    @staticmethod
    def calculate_file_size(firmware_filename):
        b = os.path.getsize(firmware_filename)
        return b

    @staticmethod
    def calculate_sha256_hash(firmware_filename):
        read_buffer = 4096

        digest = hashlib.sha256()

        with open(firmware_filename, 'rb') as firmware_file:
            while True:
                data = firmware_file.read(read_buffer)

                if data:
                    digest.update(data)
                else:
                    break

        # return hash in little endian
        sha256 = digest.digest()
        return sha256[31::-1]

    @staticmethod
    def calculate_crc(crc, firmware_filename):
        """
        Calculates CRC16 has on provided firmware filename

        :type str firmware_filename:
        """
        data_buffer = b''
        read_size = 4096

        with open(firmware_filename, 'rb') as firmware_file:
            while True:
                data = firmware_file.read(read_size)

                if data:
                    data_buffer += data
                else:
                    break
        if crc == 16:
            return calc_crc16(data_buffer, 0xffff)
        elif crc == 32:
            return binascii.crc32(data_buffer)
        else:
            raise NordicSemiException("Invalid CRC type")

    def create_manifest(self):
        manifest = ManifestGenerator(self.firmwares_data)
        return manifest.generate_manifest()

    @staticmethod
    def _is_bootloader_softdevice_combination(firmwares):
        return (HexType.BOOTLOADER in firmwares) and (HexType.SOFTDEVICE in firmwares)

    def __add_firmware_info(self, firmware_type, firmware_version, filename, init_packet_data, sd_size=None, bl_size=None):
        self.firmwares_data[firmware_type] = {
            FirmwareKeys.FIRMWARE_FILENAME: filename,
            FirmwareKeys.INIT_PACKET_DATA: init_packet_data.copy(),
            # Copying init packet to avoid using the same for all firmware
            }

        if firmware_type == HexType.SD_BL:
            self.firmwares_data[firmware_type][FirmwareKeys.SD_SIZE] = sd_size
            self.firmwares_data[firmware_type][FirmwareKeys.BL_SIZE] = bl_size
        
        if firmware_version is not None:
            self.firmwares_data[firmware_type][FirmwareKeys.INIT_PACKET_DATA][PacketField.FW_VERSION] = firmware_version

    @staticmethod
    def normalize_firmware_to_bin(work_dir, firmware_path):
        firmware_filename = os.path.basename(firmware_path)
        new_filename = firmware_filename.replace(".hex", ".bin")
        new_filepath = os.path.join(work_dir, new_filename)

        if not os.path.exists(new_filepath):
            temp = nRFHex(firmware_path)
            temp.tobinfile(new_filepath)

        return new_filepath

    @staticmethod
    def unpack_package(package_path, target_dir):
        """
        Unpacks a Nordic DFU package.

        :param str package_path: Path to the package
        :param str target_dir: Target directory to unpack the package to
        :return: Manifest Manifest: Returns a manifest back to the user. The manifest is a parse datamodel
        of the manifest found in the Nordic DFU package.
        """

        if not os.path.isfile(package_path):
            raise NordicSemiException("Package {0} not found.".format(package_path))

        target_dir = os.path.abspath(target_dir)
        target_base_path = os.path.dirname(target_dir)

        if not os.path.exists(target_base_path):
            raise NordicSemiException("Base path to target directory {0} does not exist.".format(target_base_path))

        if not os.path.isdir(target_base_path):
            raise NordicSemiException("Base path to target directory {0} is not a directory.".format(target_base_path))

        if os.path.exists(target_dir):
            raise NordicSemiException(
                "Target directory {0} exists, not able to unpack to that directory.",
                target_dir)

        with ZipFile(package_path, 'r') as pkg:
            pkg.extractall(target_dir)

            with open(os.path.join(target_dir, Package.MANIFEST_FILENAME), 'r') as f:
                _json = f.read()
                """:type :str """

                return Manifest.from_json(_json)
