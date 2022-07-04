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

import os
import re
import subprocess
import time
import uuid
from intelhex import IntelHex
from serial import Serial
from pc_ble_driver_py.ble_driver import Flasher

class OTAFlasher(Flasher):
    ERROR_CODE_VERIFY_ERROR = 55
    # Address in flash memory, where the Zigbee image will be placed. This value has to be synced with UPGRADE_IMAGE_OFFSET constant inside Zigbee OTA server source code.
    OTA_UPDATE_OFFSET = 0x80000
    OTA_EUI64_PREFIX = '07A07A'

    def __init__(self, fw, channel = 16, serial_port = None, snr = None):
        '''
           Ininitialises the OTA Flasher class which handles flashing the devboard
           with the needed OTA Server firmware and the update file for the OTA Client.
           The said devboard shall become the OTA Server which shall propagate the
           image on the Zigbee network.

           Keyword arguments:
           fw -- path to the update file for the OTA Client
           channel -- a 802.15.4 channel number, on which the OTA Server shall operate (default 16)
           serial_port -- a serial port of the connected devboard which shall be flashed with OTA Server
           snr -- a JLink serial number of the connected devboard which shall be flashed with OTA Server

           Note: only one parameter out of (serial_port, snr) must be provided, since the superclass
                 constructor shall handle resolving the rest.

        '''
        # Call the superclass constructor
        super().__init__(serial_port, snr)
        # Create a Intel Hex out of the Zigbee Update file
        ih = IntelHex()
        update = open(fw, 'rb').read()
        ih.puts(OTAFlasher.OTA_UPDATE_OFFSET, update)
        self.update_firmware_hex = fw + '.hex'
        ih.write_hex_file(self.update_firmware_hex)
        # Open the serial channel to the devboard and save the 802.15.4 channel
        self.ser = Serial(self.serial_port, 115200)
        self.channel = channel

    def __get_hex_path(self):
        '''Return the absolute path to the firmware of the OTA Server'''
        return os.path.join(os.path.dirname(__file__), 'hex', 'ota.hex')

    def verify(self, path):
        '''Run the verify command'''
        args = ['--verify', path]
        return self.call_cmd(args)

    def _fw_check(self, path_to_file):
        '''Check if the path_to_file hexfile was flashed correctly'''
        try:
            result = self.verify(path_to_file)
        except subprocess.CalledProcessError as e:  # for pc-ble-driver <= 0.14.2, can be removed when requirements
            # will be updated to >= 0.15.0
            if e.returncode == OTAFlasher.ERROR_CODE_VERIFY_ERROR:
                return False
            else:
                raise
        except RuntimeError:  # for pc-ble-driver >= 0.15.0
            return False

        return (re.search(b'^Verified OK.$', result, re.MULTILINE) is not None)

    def fw_check(self):
        '''Check if all the hex files (OTA Server firmware and Zigbee Update file) were flashed correctly'''
        if self._fw_check(self.__get_hex_path()) and self._fw_check(self.update_firmware_hex):
            return True
        else:
            return False

    def fw_flash(self):
        '''Flash all the hex files (OTA Server firmware and Zigbee Update file) to the board'''
        self.erase()
        self.program(self.update_firmware_hex)
        self.program(self.__get_hex_path())
        # Remove the generated file
        os.remove(self.update_firmware_hex)

    def randomize_eui64(self):
        '''Randomize the EUI64 address used by the board'''
        random_eui64 = uuid.uuid4().int >> 88 # Generate 128-bit UUID and take 40 upper bits
        self.ser.write(f'zdo eui64 {OTAFlasher.OTA_EUI64_PREFIX}{random_eui64:010x}\r\n'.encode())

    def setup_channel(self):
        '''Setup to the channel of the flashed board through the serial CLI; and start the internal stack'''
        self.ser.write(f'bdb channel {self.channel}\r\n'.encode())
        time.sleep(1.0)
        self.ser.write('bdb start\r\n'.encode())
