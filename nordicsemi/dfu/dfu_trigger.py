import usb1

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
                pass

    def get_dfu_interface_num(self, libusb_device):
        for cfg in libusb_device.iterConfigurations():
            for iface in cfg.iterInterfaces():
                for setting in iface.iterSettings():
                    if setting.getClass() == 255 and \
                    setting.getSubClass == 1 and \
                    setting.getProtocol == 1:
                        # TODO: set configuration
                        return setting.getNumber()
        return 0

    def enter_bootloader_mode(self, listed_device):
        libusb_device = self.select_device(listed_device)
        device_handle = libusb_device.open()
        dfu_iface = self.get_dfu_interface_num(libusb_device)
        with device_handle.claimInterface(dfu_iface):
            arr = bytearray("0", 'utf-8')
            try:
                written = device_handle.controlWrite(ReqTypeOUT, DFU_DETACH_REQUEST, 0, dfu_iface, arr)
            except Exception as err:
                if "LIBUSB_ERROR_PIPE" in err:
                    return
        # throw exception indicating that the device didn't exit application mode
