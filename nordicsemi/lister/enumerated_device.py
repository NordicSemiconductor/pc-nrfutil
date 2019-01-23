class EnumeratedDevice:
    def __init__(self, vendor_id, product_id, serial_number, com_ports):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.serial_number = serial_number
        self.com_ports = com_ports

    def has_com_port(self, checkPort):
        for port in self.com_ports:
            if port.lower() == checkPort.lower():
                return True
        return False

    def get_first_available_com_port(self):
        return self.com_ports[0]

    def __repr__(self):
        return "{{\nvendor_id: {}\nproduct_id: {}\nserial_number: {}\nCOM: {}\n}}".format(self.vendor_id, self.product_id, self.serial_number, self.com_ports)
