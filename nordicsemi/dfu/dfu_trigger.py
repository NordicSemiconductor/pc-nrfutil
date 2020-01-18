#
# Copyright (c) 2019 Nordic Semiconductor ASA
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
import sys
import ctypes
from importlib import import_module
import logging

from pc_ble_driver_py.exceptions import NordicSemiException


LIBUSB_ENDPOINT_IN = 0x80
LIBUSB_ENDPOINT_OUT = 0x00
LIBUSB_REQUEST_TYPE_STANDARD = 0x00 << 5
LIBUSB_REQUEST_TYPE_CLASS = 0x01 << 5
LIBUSB_REQUEST_TYPE_VENDOR = 0x02 << 5
LIBUSB_REQUEST_TYPE_RESERVED = 0x03 << 5
LIBUSB_RECIPIENT_DEVICE = 0x00
LIBUSB_RECIPIENT_INTERFACE = 0x01
LIBUSB_RECIPIENT_ENDPOINT = 0x02
LIBUSB_RECIPIENT_OTHER = 0x03

ReqTypeInterfaceClass = LIBUSB_REQUEST_TYPE_CLASS | LIBUSB_RECIPIENT_INTERFACE
ReqTypeIN = ReqTypeInterfaceClass | LIBUSB_ENDPOINT_IN
ReqTypeOUT = ReqTypeInterfaceClass | LIBUSB_ENDPOINT_OUT
NORDIC_SEM_VER_REQUEST = 8
NORDIC_DFU_INFO_REQUEST = 7
DFU_DETACH_REQUEST = 0

logger = logging.getLogger(__name__)

is_32_bit = ctypes.sizeof(ctypes.c_void_p) == 4
abs_file_dir = os.path.dirname(os.path.abspath(__file__))
rel_import_dir = ""

dfu_path = os.path.join("nordicsemi", "dfu")
if is_32_bit:
    libusb_path = os.path.join("libusb", "x86")
    abs_file_dir = abs_file_dir.replace(dfu_path, libusb_path)
    rel_import_dir = os.path.join(".", libusb_path)
else:
    libusb_path = os.path.join("libusb", "x64")
    abs_file_dir = abs_file_dir.replace(dfu_path, libusb_path)
    rel_import_dir = os.path.join(".", libusb_path)

for path in ['PATH', 'LD_LIBRARY_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FALLBACK_LIBRARY_PATH']:
    if path not in os.environ:
        os.environ[path] = ""
    os.environ[path] = rel_import_dir + os.pathsep + abs_file_dir + os.pathsep + os.environ[path]

class DFUTrigger:
    def __init__(self):
        self.context = None

        if sys.platform == 'win32':
            try:
                # Load the libusb dll in advance so that libusb1 module is better able to load it
                ctypes.CDLL(os.path.join(abs_file_dir, "libusb-1.0.dll"));
            except OSError as err:
                logger.info(err)

        try:
            self.usb1 = import_module('usb1')
            self.context = self.usb1.USBContext()
        except OSError as err:
            if "libusb" in str(err):
                if sys.platform == 'win32' or sys.platform == 'darwin':
                    show_msg = "Libusb1 binaries are bundled with nrfutil for Windows and MacOS. " \
                               "Python is unable to locate or load the binaries. "
                elif 'linux' in sys.platform:
                    show_msg = "Libusb1 binaries are bundled with some linux distributions. " \
                                    "If you see this message, they are probably not installed on your system. "\
                                    "If you want to use DFU trigger, please install 'libusb1' using your package manager. "\
                                    "E.g: 'sudo apt-get install libusb-dev'."
                else:
                    show_msg = "Libusb1 is not compatible with your operating system."

                logger.warning("Could not load libusb1-0 library, which is a requirement to use DFU trigger. "\
                            "This is not a problem unless you intend to use this functionality. "\
                            "{}".format(show_msg))
    def clean(self):
        self.usb1 = None
        if self.context:
            self.context.close()

    def select_device(self, listed_device):
        all_devices = self.context.getDeviceList()
        filtered_devices = [dev for dev in all_devices
            if hex(dev.getVendorID())[2:].lower() == listed_device.vendor_id.lower() and
            hex(dev.getProductID())[2:].lower() == listed_device.product_id.lower()]

        access_error = False
        triggerless_devices = 0

        for nordic_device in filtered_devices:
            try:
                handle = nordic_device.open()
                SNO = handle.getSerialNumber()
                handle.close()
                if (SNO.lower() == listed_device.serial_number.lower()):
                    return nordic_device

            except self.usb1.USBErrorNotFound as err:
                #  Devices with matching VID and PID as target, but without a trigger iface.
                triggerless_devices += 1
            except self.usb1.USBErrorAccess as err:
                access_error = True
            except self.usb1.USBErrorNotSupported as err:
                pass #  Unsupported device. Moving on

        if triggerless_devices > 0:
            logger.debug("DFU trigger: Could not find trigger interface for device with serial number {}. "\
            "{}/{} devices with same VID/PID were missing a trigger interface."\
            .format(listed_device.serial_number, triggerless_devices, len(filtered_devices)))

        if access_error:
            raise NordicSemiException("LIBUSB_ERROR_ACCESS: Unable to connect to trigger interface.")

    def get_dfu_interface_num(self, libusb_device):
        for setting in libusb_device.iterSettings():
            if setting.getClass() == 255 and \
            setting.getSubClass() == 1 and \
            setting.getProtocol() == 1:
                return setting.getNumber()

    def no_trigger_exception(self, device):
        return NordicSemiException("No trigger interface found for device with serial number: {}, Product ID: 0x{} and Vendor ID: 0x{}\n"
        .format(device.serial_number, device.product_id, device.vendor_id))

    def enter_bootloader_mode(self, listed_device):
        if self.context is None:
            raise NordicSemiException("No Libusb1 context found, but is required to use DFU trigger. " \
                                    "This likely happens because the libusb1-0 binaries are missing from your system, "\
                                    "or Python is unable to locate them.")
        libusb_device = self.select_device(listed_device)
        if libusb_device is None:
            raise self.no_trigger_exception(listed_device)
        device_handle = libusb_device.open()
        dfu_iface = self.get_dfu_interface_num(libusb_device)

        if dfu_iface is None:
            raise self.no_trigger_exception(listed_device)

        with device_handle.claimInterface(dfu_iface):
            arr = bytearray("0", 'utf-8')
            try:
                device_handle.controlWrite(ReqTypeOUT, DFU_DETACH_REQUEST, 0, dfu_iface, arr)
            except Exception as err:
                if "LIBUSB_ERROR_PIPE" in str(err):
                    return
        raise NordicSemiException("A diconnection event from libusb is expected when the usb device restarts after triggering bootloder. "\
        "The event was not received. This can be an indication that the device was unable to leave application mode. "\
        "Serial number: {}, Product ID: 0x{}, Vendor ID: 0x{}\n\n"
        .format(listed_device.serial_number, listed_device.product_id, listed_device.vendor_id))
