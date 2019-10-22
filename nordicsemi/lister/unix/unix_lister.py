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

if 'linux' in sys.platform or sys.platform == 'darwin':
    import serial.tools.list_ports
    from nordicsemi.lister.enumerated_device import EnumeratedDevice


def create_id_string(sno, PID, VID):
    return "{}-{}-{}".format(sno, PID, VID)


class UnixLister(AbstractLister):

    def enumerate(self):
        device_identities = {}
        available_ports = serial.tools.list_ports.comports()

        for port in available_ports:
            if port.pid is None or port.vid is None or port.serial_number is None:
                continue

            serial_number = port.serial_number
            product_id = hex(port.pid).upper()[2:]
            vendor_id = hex(port.vid).upper()[2:]
            com_port = port.device

            id = create_id_string(serial_number, product_id, vendor_id)
            if id in device_identities:
                device_identities[id].add_com_port(com_port)
            else:
                device_identities[id] = EnumeratedDevice(vendor_id, product_id, serial_number, [com_port])

        return [device for device in list(device_identities.values())]
