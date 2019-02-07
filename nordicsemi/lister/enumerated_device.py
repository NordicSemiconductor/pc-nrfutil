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


class EnumeratedDevice:
    def __init__(self, vendor_id, product_id, serial_number, com_ports):
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.serial_number = serial_number
        self.com_ports = []
        for port in com_ports:
            self.add_com_port(port)

    def add_com_port(self, port):
        if sys.platform == 'darwin':
            #  Ports are sometimes listed under /dev/cu on MacOS,
            #  but pyserial can only open /dev/tty* ports.
            port = port.replace('/dev/cu.', '/dev/tty.')
        self.com_ports.append(port)

    def has_com_port(self, checkPort):
        for port in self.com_ports:
            if port.lower() == checkPort.lower():
                return True
        return False

    def get_first_available_com_port(self):
        return self.com_ports[0]

    def __repr__(self):
        return "{{\nvendor_id: {}\nproduct_id: {}\nserial_number: {}\nCOM: {}\n}}"\
                .format(self.vendor_id, self.product_id, self.serial_number, self.com_ports)
