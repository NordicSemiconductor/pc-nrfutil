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

# Importing libusb1 library
import os
working_dir = os.getcwd()
file_dir = os.path.dirname(__file__)
os.chdir(file_dir)
os.chdir("../../libusb")
import usb1
os.chdir(working_dir)


from pc_ble_driver_py.exceptions    import NordicSemiException

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

ReqTypeInterfaceClass = LIBUSB_REQUEST_TYPE_CLASS | LIBUSB_RECIPIENT_INTERFACE;
ReqTypeIN = ReqTypeInterfaceClass | LIBUSB_ENDPOINT_IN;
ReqTypeOUT = ReqTypeInterfaceClass | LIBUSB_ENDPOINT_OUT;
NORDIC_SEM_VER_REQUEST = 8;
NORDIC_DFU_INFO_REQUEST = 7;
DFU_DETACH_REQUEST = 0;

class DFUTrigger:
    def __init__(self):
        self.context = usb1.USBContext()

    def clean(self):
        self.context.close()

    def select_device(self, listed_device):
        allDevices = self.context.getDeviceList()
        filteredDevices = [dev for dev in allDevices\
        if hex(dev.getVendorID())[2:].lower() == listed_device.vendor_id.lower() and \
        hex(dev.getProductID())[2:].lower() == listed_device.product_id.lower()]

        access_error = False

        for nordicDevice in filteredDevices:
            try:
                handle = nordicDevice.open()
                SNO = handle.getSerialNumber()
                handle.close()
                if (SNO.lower() == listed_device.serial_number.lower()):
                    return nordicDevice

            except usb1.USBErrorNotFound as err:
                pass
            except Exception as err: # LIBUSB_ERROR_NOT_SUPPORTED
                if "LIBUSB_ERROR_ACCESS" in str(err):
                    access_error = True
        if access_error:
            raise NordicSemiException("LIBUSB_ERROR_ACCESS: Unable to connect to trigger interface.")

    def get_dfu_interface_num(self, libusb_device):
        for cfg in libusb_device.iterConfigurations():
            for iface in cfg.iterInterfaces():
                for setting in iface.iterSettings():
                    if setting.getClass() == 255 and \
                    setting.getSubClass() == 1 and \
                    setting.getProtocol() == 1:
                        # TODO: set configuration
                        return setting.getNumber()

    def no_trigger_exception(self, device):
        return NordicSemiException("No trigger interface found for device with serial number {}, product id 0x{} and vendor id 0x{}\n"\
        .format(device.serial_number, device.product_id, device.vendor_id))

    def enter_bootloader_mode(self, listed_device):
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
        raise NordicSemiException("Device did not exit application mode after dfu was triggered. Serial number: {}, product id 0x{}, vendor id: 0x{}\n\n"\
        .format(listed_device.serial_number, listed_device.product_id, listed_device.vendor_id))
