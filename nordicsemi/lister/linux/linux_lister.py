import sys
from nordicsemi.lister.lister_backend import AbstractLister

if 'linux' in sys.platform:
    from serial import Serial
    import serial.tools.list_ports
    from nordicsemi.lister.enumerated_device import EnumeratedDevice

def create_id_string(sno, PID, VID):
    return "{}-{}-{}".format(sno, PID, VID)

class LinuxLister(AbstractLister):
    def __init__(self):
        pass

    def enumerate(self):
        device_identities = {}
        available_ports = serial.tools.list_ports.comports()

        for port in available_ports:
            if port.pid == None or port.vid == None or port.serial_number == None:
                continue

            serial_number = port.serial_number
            product_id = hex(port.pid).upper()[2:]
            vendor_id = hex(port.vid).upper()[2:]
            com_port = port.device

            id = create_id_string(serial_number, product_id, vendor_id)
            if id in device_identities:
                device_identities[id].com_ports.append(com_port)
            else:
                device_identities[id] = EnumeratedDevice(vendor_id, product_id, serial_number, [com_port])

        return [device for device in device_identities.values()]
