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
import time
import shutil
import logging
import tempfile


# Nordic libraries
from nordicsemi.dfu.package         import Package

logger = logging.getLogger(__name__)


class Dfu:
    """ Class to handle upload of a new hex image to the device. """

    def __init__(self, zip_file_path, dfu_transport, connect_delay):
        """
        Initializes the dfu upgrade, unpacks zip and registers callbacks.

        @param zip_file_path: Path to the zip file with the firmware to upgrade
        @type zip_file_path: str
        @param dfu_transport: Transport backend to use to upgrade
        @type dfu_transport: nordicsemi.dfu.dfu_transport.DfuTransport
        @param connect_delay: Delay in seconds before each connection to the DFU target
        @type connect_delay: int
        @return
        """
        self.temp_dir           = tempfile.mkdtemp(prefix="nrf_dfu_")
        self.unpacked_zip_path  = os.path.join(self.temp_dir, 'unpacked_zip')
        self.manifest           = Package.unpack_package(zip_file_path, self.unpacked_zip_path)

        self.dfu_transport      = dfu_transport

        if connect_delay is not None:
            self.connect_delay = connect_delay
        else:
            self.connect_delay = 3

    def __del__(self):
        """
        Destructor removes the temporary directory for the unpacked zip
        :return:
        """
        shutil.rmtree(self.temp_dir)


    def _dfu_send_image(self, firmware):
        time.sleep(self.connect_delay)
        self.dfu_transport.open()

        start_time = time.time()

        logger.info("Sending init packet...")
        with open(os.path.join(self.unpacked_zip_path, firmware.dat_file), 'rb') as f:
            data    = f.read()
            self.dfu_transport.send_init_packet(data)

        logger.info("Sending firmware file...")
        with open(os.path.join(self.unpacked_zip_path, firmware.bin_file), 'rb') as f:
            data    = f.read()
            self.dfu_transport.send_firmware(data)

        end_time = time.time()
        logger.info("Image sent in {0}s".format(end_time - start_time))

        self.dfu_transport.close()


    def dfu_send_images(self):
        """
        Does DFU for all firmware images in the stored manifest.
        :return:
        """
        if self.manifest.softdevice_bootloader:
            logger.info("Sending SoftDevice+Bootloader image.")
            self._dfu_send_image(self.manifest.softdevice_bootloader)

        if self.manifest.softdevice:
            logger.info("Sending SoftDevice image...")
            self._dfu_send_image(self.manifest.softdevice)

        if self.manifest.bootloader:
            logger.info("Sending Bootloader image.")
            self._dfu_send_image(self.manifest.bootloader)

        if self.manifest.application:
            logger.info("Sending Application image.")
            self._dfu_send_image(self.manifest.application)


    def dfu_get_total_size(self):
        total_size = 0

        if self.manifest.softdevice_bootloader:
            total_size += os.path.getsize(os.path.join(self.unpacked_zip_path,
                                                       self.manifest.softdevice_bootloader.bin_file))

        if self.manifest.softdevice:
            total_size += os.path.getsize(os.path.join(self.unpacked_zip_path,
                                                       self.manifest.softdevice.bin_file))

        if self.manifest.bootloader:
            total_size += os.path.getsize(os.path.join(self.unpacked_zip_path,
                                                       self.manifest.bootloader.bin_file))

        if self.manifest.application:
            total_size += os.path.getsize(os.path.join(self.unpacked_zip_path,
                                                       self.manifest.application.bin_file))

        return total_size
