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
from nordicsemi.lister.windows.lister_win32 import Win32Lister
from nordicsemi.lister.unix.unix_lister import UnixLister


class DeviceLister:
    def __init__(self):
        if sys.platform == 'win32':
            self.lister_backend = Win32Lister()
        elif 'linux' in sys.platform:
            self.lister_backend = UnixLister()
        elif sys.platform == 'darwin':
            self.lister_backend = UnixLister()
        else:
            self.lister_backend = None

    def enumerate(self):
        if self.lister_backend:
            return self.lister_backend.enumerate()
        return []

    def get_device(self, get_all=False, **kwargs):
        devices = self.enumerate()
        matching_devices = []
        for dev in devices:
            if "vendor_id" in kwargs and kwargs["vendor_id"].lower() != dev.vendor_id.lower():
                continue
            if "product_id" in kwargs and kwargs["product_id"].lower() != dev.product_id.lower():
                continue
            if "serial_number" in kwargs and (kwargs["serial_number"].lower().lstrip('0') !=
                                              dev.serial_number.lower().lstrip('0')):
                continue
            if "com" in kwargs and not dev.has_com_port(kwargs["com"]):
                continue

            matching_devices.append(dev)

        if not get_all:
            if len(matching_devices) == 0:
                return
            return matching_devices[0]
        return matching_devices
