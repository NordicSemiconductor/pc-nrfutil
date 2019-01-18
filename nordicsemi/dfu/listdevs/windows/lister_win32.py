from constants import DevicePropertyKeys, DIOD_INHERIT_CLASSDRVS, DIGCF_PRESENT, DIGCF_PROFILE, DEVPKEY, DIGCF_ALLCLASSES, DIGCF_DEVICEINTERFACE
from structures import GUID, DeviceInfoData, DevicePropertyKey, ctypesInternalGUID

import ctypes
from ctypes.wintypes import *
import winreg

# constants
DICS_FLAG_GLOBAL = 1
DIREG_DEV = 1
INVALID_HANDLE_VALUE = -1
MAX_BUFSIZE = 1000

setup_api = ctypes.windll.setupapi


def getSerialSerialNo(vendorId, productId, hDevInfo, deviceInfoData):
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

def comPortIsOpen(port):
    return True


def listAllCOMPorts(vendorId, productId, serialNumber):
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
        if comPortIsOpen(portName):
            ports.append(portName)

    return ports

class enumeratedDevice:
    def __init__(self, vendor_id, product_id, serial_number, com_ports):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.serial_number = serial_number
        self.com_ports = com_ports

    def hasCOMPort(self, checkPort):
        for port in self.com_ports:
            if port.lower() == checkPort.lower():
                return True
        return False

    def getFirstAvailableCOMPort(self):
        return self.com_ports[0]

    def __repr__(self):
        return "{{\nvendor_id: {}\nproduct_id: {}\nserial_number: {}\nCOM: {}\n}}".format(self.vendor_id, self.product_id, self.serial_number, self.com_ports)



class Win32Lister:
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

            serialNumber = getSerialSerialNo(vendorId, productId, hDevInfo, devInfoData)
            if not serialNumber:
                continue

            COMPorts = listAllCOMPorts(vendorId, productId, serialNumber)

            if len(COMPorts) > 0:
                device = enumeratedDevice(vendorId, productId, serialNumber, COMPorts)
                enumeratedDevices.append(device)

        return enumeratedDevices
