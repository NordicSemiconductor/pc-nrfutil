import sys
from nordicsemi.lister.windows.lister_win32 import Win32Lister
from nordicsemi.lister.linux.linux_lister import LinuxLister

class DeviceLister(object):
    def __init__(self):
        if sys.platform == 'win32':
            self.lister_backend = Win32Lister()
        elif 'linux' in sys.platform:
            self.lister_backend = LinuxLister()
        else:
            self.lister_backend = None

    def enumerate(self):
        return self.lister_backend.enumerate()
    def get_device(self, get_all = False, **kwargs):
        devices = self.enumerate()
        matching_devices = []
        for dev in devices:
            if "vendor_id" in kwargs and kwargs["vendor_id"].lower() != dev.vendor_id.lower():
                continue
            if "product_id" in kwargs and kwargs["product_id"].lower() != dev.product_id.lower():
                continue
            if "serial_number" in kwargs and kwargs["serial_number"].lower() != dev.serial_number.lower():
                continue
            if "com" in kwargs and not dev.has_com_port(kwargs["com"]):
                continue

            matching_devices.append(dev)

        if not get_all:
            if len(matching_devices) == 0:
                return
            return matching_devices[0]
        return matching_devices
