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

import sys
from nordicsemi.lister.lister_backend import AbstractLister
from nordicsemi.lister.enumerated_device import EnumeratedDevice

if sys.platform == 'win32':
    from .constants import DIGCF_PRESENT, DEVPKEY, DIGCF_DEVICEINTERFACE
    from .structures import (GUID, DeviceInfoData, ctypesInternalGUID, _GUID,
                             ValidHandle)

    import ctypes
    import winreg
    setup_api = ctypes.windll.setupapi

    SetupDiGetClassDevs = setup_api.SetupDiGetClassDevsW
    SetupDiGetClassDevs.argtypes = [ctypes.POINTER(_GUID), ctypes.c_wchar_p,
                                    ctypes.c_void_p, ctypes.c_uint32]
    SetupDiGetClassDevs.restype = ctypes.c_void_p
    SetupDiGetClassDevs.errcheck = ValidHandle

    SetupDiEnumDeviceInfo = setup_api.SetupDiEnumDeviceInfo
    SetupDiEnumDeviceInfo.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                      ctypes.POINTER(DeviceInfoData)]
    SetupDiEnumDeviceInfo.restype = ctypes.c_bool

    SetupDiGetDeviceInstanceId = setup_api.SetupDiGetDeviceInstanceIdW
    SetupDiGetDeviceInstanceId.argtypes = [ctypes.c_void_p,
                                           ctypes.POINTER(DeviceInfoData),
                                           ctypes.c_wchar_p, ctypes.c_uint32,
                                           ctypes.POINTER(ctypes.c_uint32)]
    SetupDiGetDeviceInstanceId.restype = ctypes.c_bool

    SetupDiGetDeviceProperty = setup_api.SetupDiGetDevicePropertyW
    SetupDiGetDeviceProperty.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.c_uint,
                                         ctypes.c_void_p, ctypes.c_uint]
    SetupDiGetDeviceProperty.restype = ctypes.c_bool

#  constants
DICS_FLAG_GLOBAL = 1
DIREG_DEV = 1
INVALID_HANDLE_VALUE = -1
MAX_BUFSIZE = 1000


def get_serial_serial_no(vendor_id, product_id, h_dev_info, device_info_data):
    prop_type = ctypes.c_ulong()
    required_size = ctypes.c_ulong()

    instance_id_buffer = ctypes.create_unicode_buffer(MAX_BUFSIZE)
    res = SetupDiGetDeviceProperty(h_dev_info, ctypes.byref(device_info_data),
                                   ctypes.byref(DEVPKEY.Device.ContainerId),
                                   ctypes.byref(prop_type), instance_id_buffer,
                                   MAX_BUFSIZE, ctypes.byref(required_size), 0)

    wanted_GUID = GUID(ctypesInternalGUID(instance_id_buffer))

    hkey_path = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{}&PID_{}".format(vendor_id, product_id)
    try:
        vendor_product_hkey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hkey_path)
    except EnvironmentError as err:
        return

    serial_numbers_count = winreg.QueryInfoKey(vendor_product_hkey)[0]

    for serial_number_idx in range(serial_numbers_count):
        try:
            serial_number = winreg.EnumKey(vendor_product_hkey, serial_number_idx)
        except EnvironmentError as err:
            continue

        hkey_path = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{}&PID_{}\\{}"\
                    .format(vendor_id, product_id, serial_number)

        try:
            device_hkey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hkey_path)
        except EnvironmentError as err:
            continue

        try:
            queried_container_id = winreg.QueryValueEx(device_hkey, "ContainerID")[0]
        except EnvironmentError as err:
            winreg.CloseKey(device_hkey)
            continue

        winreg.CloseKey(device_hkey)

        if queried_container_id.lower() == str(wanted_GUID).lower():
            winreg.CloseKey(vendor_product_hkey)
            return serial_number

    winreg.CloseKey(vendor_product_hkey)


def com_port_is_open(port):
    hkey_path = "HARDWARE\\DEVICEMAP\\SERIALCOMM"
    try:
        device_hkey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hkey_path)
    except EnvironmentError as err:
        #  Unable to check enumerated serialports. Assume open.
        return True
    next_key = 0
    while True:
        try:
            value = winreg.EnumValue(device_hkey, next_key)[1]
            next_key += 1
            if port == value:
                winreg.CloseKey(device_hkey)
                return True
        except WindowsError:
            break
    winreg.CloseKey(device_hkey)
    return False


def list_all_com_ports(vendor_id, product_id, serial_number):
    ports = []

    hkey_path = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{}&PID_{}\\{}"\
                .format(vendor_id, product_id, serial_number)

    try:
        device_hkey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hkey_path)
    except EnvironmentError as err:
        return ports

    try:
        parent_id = winreg.QueryValueEx(device_hkey, "ParentIdPrefix")[0]
    except EnvironmentError as err:
        winreg.CloseKey(device_hkey)
        return ports

    winreg.CloseKey(device_hkey)

    hkey_path = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{}&PID_{}\\{}\\Device Parameters"\
                .format(vendor_id, product_id, serial_number)
    try:
        device_hkey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hkey_path)
        try:
            COM_port = winreg.QueryValueEx(device_hkey, "PortName")[0]
            ports.append(COM_port)
        except EnvironmentError as err:
            #  No COM port for root device.
            pass
        winreg.CloseKey(device_hkey)
    except EnvironmentError as err:
        #  Root device has no device parameters
        pass

    iface_id = 0
    while True:
        hkey_path = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{vid_val}&PID_{pid_val}&"\
        "MI_{mi_val}\\{parent_val}&{parent_iface}\\Device Parameters"\
        .format(vid_val=vendor_id, pid_val=product_id, mi_val=str(iface_id).zfill(2),
                parent_val=parent_id, parent_iface=str(iface_id).zfill(4))
        iface_id += 1
        try:
            device_hkey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hkey_path)
        except EnvironmentError as err:
            break

        try:
            port_name = winreg.QueryValueEx(device_hkey, "PortName")[0]
        except EnvironmentError as err:
            winreg.CloseKey(device_hkey)
            continue

        winreg.CloseKey(device_hkey)
        if com_port_is_open(port_name):
            ports.append(port_name)

    return ports


class Win32Lister(AbstractLister):
    def __init__(self):
        self.GUID_DEVINTERFACE_USB_DEVICE = GUID("{A5DCBF10-6530-11D2-901F-00C04FB951ED}")

    def enumerate(self):
        enumerated_devices = []
        h_dev_info = SetupDiGetClassDevs(ctypes.byref(self.GUID_DEVINTERFACE_USB_DEVICE._guid),
                                         None, 0, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
        dev_info_data = DeviceInfoData()
        if h_dev_info == -1:
            return enumerated_devices

        next_enum = 0
        while SetupDiEnumDeviceInfo(h_dev_info, next_enum, ctypes.byref(dev_info_data)):
            next_enum += 1

            sz_buffer = ctypes.create_unicode_buffer(MAX_BUFSIZE)
            dw_size = ctypes.c_ulong()
            res = SetupDiGetDeviceInstanceId(h_dev_info, ctypes.byref(dev_info_data),
                                             sz_buffer, MAX_BUFSIZE,
                                             ctypes.byref(dw_size))
            if not res:
                #  failed to fetch pid vid
                continue
            vendor_id = sz_buffer.value[8:12]
            product_id = sz_buffer.value[17:21]

            serial_number = get_serial_serial_no(vendor_id, product_id, h_dev_info, dev_info_data)
            if not serial_number:
                continue

            COM_ports = list_all_com_ports(vendor_id, product_id, serial_number)

            if len(COM_ports) > 0:
                device = EnumeratedDevice(vendor_id, product_id, serial_number, COM_ports)
                enumerated_devices.append(device)

        return enumerated_devices
