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
    from constants import DIGCF_PRESENT, DEVPKEY, DIGCF_DEVICEINTERFACE
    from structures import GUID, DeviceInfoData, ctypesInternalGUID

    import ctypes
    from ctypes.wintypes import *
    import winreg
    setup_api = ctypes.windll.setupapi

# constants
DICS_FLAG_GLOBAL = 1
DIREG_DEV = 1
INVALID_HANDLE_VALUE = -1
MAX_BUFSIZE = 1000




def get_serial_serial_no(vendorId, productId, hDevInfo, deviceInfoData):
    prop_type = ctypes.c_ulong()
    required_size = ctypes.c_ulong()

    instance_id_buffer = ctypes.create_string_buffer(MAX_BUFSIZE)

    res = setup_api.SetupDiGetDevicePropertyW(hDevInfo, ctypes.byref(deviceInfoData), ctypes.byref(DEVPKEY.Device.ContainerId), ctypes.byref(prop_type), ctypes.byref(instance_id_buffer),
                                                           MAX_BUFSIZE, ctypes.byref(required_size), 0)

    wantedGUID = GUID(ctypesInternalGUID(instance_id_buffer))

    hKeyPath = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{}&PID_{}".format(vendorId, productId)
    try:
        vendorProductHKey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hKeyPath)
    except EnvironmentError as err:
        return

    serialNumbersCount = winreg.QueryInfoKey(vendorProductHKey)[0]

    for serialNumberIdx in range(serialNumbersCount):
        try:
            serialNumber = winreg.EnumKey(vendorProductHKey, serialNumberIdx)
        except EnvironmentError as err:
            continue

        hKeyPath = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{}&PID_{}\\{}".format(vendorId, productId,serialNumber)
        try:
            deviceHKey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hKeyPath)
        except EnvironmentError as err:
            continue

        try:
            queriedContainerId = winreg.QueryValueEx(deviceHKey, "ContainerID")[0]
        except EnvironmentError as err:
            winreg.CloseKey(deviceHKey)
            continue

        winreg.CloseKey(deviceHKey)

        if queriedContainerId.lower() == str(wantedGUID).lower():
            winreg.CloseKey(vendorProductHKey)
            return serialNumber

    winreg.CloseKey(vendorProductHKey)

def com_port_is_open(port):
    hKeyPath = "HARDWARE\\DEVICEMAP\\SERIALCOMM"
    try:
        deviceHKey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hKeyPath)
    except EnvironmentError as err:
        return True # Unable to check enumerated serialports. Assume all are open.
    nextKey = 0
    while True:
        try:
            value = winreg.EnumValue(deviceHKey, nextKey)[1]
            nextKey += 1
            if port == value:
                winreg.CloseKey(deviceHKey)
                return True
        except WindowsError:
            break
    winreg.CloseKey(deviceHKey)
    return False


def list_all_com_ports(vendorId, productId, serialNumber):
    ports = []

    hKeyPath = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{}&PID_{}\\{}".format(vendorId, productId,serialNumber)
    try:
        deviceHKey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hKeyPath)
    except EnvironmentError as err:
        return ports

    try:
        parentId = winreg.QueryValueEx(deviceHKey, "ParentIdPrefix")[0]
    except EnvironmentError as err:
        winreg.CloseKey(deviceHKey)
        return ports

    winreg.CloseKey(deviceHKey)

    hKeyPath = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{}&PID_{}\\{}\\Device Parameters".format(vendorId, productId, serialNumber)
    try:
        deviceHKey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hKeyPath)
        try:
            COMPort = winreg.QueryValueEx(deviceHKey, "PortName")[0]
            ports.append(COMPort)
        except EnvironmentError as err:
            pass # No COM port for root device.
        winreg.CloseKey(deviceHKey)
    except EnvironmentError as err:
        pass # Root device has no device parameters

    iFaceId = 0
    while True:
        hKeyPath = "SYSTEM\\CurrentControlSet\\Enum\\USB\\VID_{vid_val}&PID_{pid_val}&MI_{mi_val}\\{parent_val}&{parent_iface}\\Device Parameters"\
        .format(vid_val= vendorId, pid_val = productId, mi_val = str(iFaceId).zfill(2), parent_val = parentId, parent_iface = str(iFaceId).zfill(4))
        iFaceId += 1
        try:
            deviceHKey = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, hKeyPath)
        except EnvironmentError as err:
            break

        try:
            portName = winreg.QueryValueEx(deviceHKey, "PortName")[0]
        except EnvironmentError as err:
            winreg.CloseKey(deviceHKey)
            continue

        winreg.CloseKey(deviceHKey)
        if com_port_is_open(portName):
            ports.append(portName)

    return ports

class Win32Lister(AbstractLister):
    def __init__(self):
        self.GUID_DEVINTERFACE_USB_DEVICE = GUID("{A5DCBF10-6530-11D2-901F-00C04FB951ED}")

    def _failedEnumeration(self):
        return {};

    def enumerate(self):
        enumeratedDevices = []
        devInfoData = DeviceInfoData()
        hDevInfo = setup_api.SetupDiGetClassDevsW(ctypes.byref(self.GUID_DEVINTERFACE_USB_DEVICE._guid), None, None, DIGCF_PRESENT|DIGCF_DEVICEINTERFACE)
        if hDevInfo == -1:
            return enumeratedDevices

        nextEnum = 0
        while True:
            res = setup_api.SetupDiEnumDeviceInfo(hDevInfo, nextEnum, ctypes.byref(devInfoData))
            nextEnum += 1
            if res == False:
                return enumeratedDevices

            szBuffer = ctypes.create_string_buffer(MAX_BUFSIZE)
            dwSize = ctypes.c_ulong()
            res = setup_api.SetupDiGetDeviceInstanceIdA(hDevInfo, ctypes.byref(devInfoData), ctypes.byref(szBuffer), MAX_BUFSIZE, ctypes.byref(dwSize))
            if res == False:
                continue # failed to fetch pid vid
            vendorId = szBuffer.raw[8:12]
            productId =szBuffer.raw[17:21]

            serialNumber = get_serial_serial_no(vendorId, productId, hDevInfo, devInfoData)
            if not serialNumber:
                continue

            COMPorts = list_all_com_ports(vendorId, productId, serialNumber)

            if len(COMPorts) > 0:
                device = EnumeratedDevice(vendorId, productId, serialNumber, COMPorts)
                enumeratedDevices.append(device)

        return enumeratedDevices
