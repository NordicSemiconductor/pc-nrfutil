"""
MIT License

Copyright (c) 2016 gwangyi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import enum
from .structures import DevicePropertyKey


# noinspection SpellCheckingInspection
class DiOpenDeviceInfo(enum.IntEnum):
    """DIOD_xxx constants
    """
    InheritClassDrvs = 2
    CancelRemove = 4


# noinspection SpellCheckingInspection
class DiGetClassDevsFlags(enum.IntEnum):
    """DIGCF_xxx constants
    """
    Default = 0x00000001
    Present = 0x00000002,
    AllClasses = 0x00000004,
    Profile = 0x00000008,
    DeviceInterface = 0x00000010,


# noinspection SpellCheckingInspection
class DevicePropertyKeys:
    """DEVPKEY_xxx constants"""
    NAME = DevicePropertyKey('{b725f130-47ef-101a-a5f1-02608c9eebac}', 10, 'DEVPKEY_NAME')
    Numa_Proximity_Domain = DevicePropertyKey('{540b947e-8b40-45bc-a8a2-6a0b894cbda2}', 1,
                                              'DEVPKEY_Numa_Proximity_Domain')

    # noinspection SpellCheckingInspection
    class Device:
        """DEVPKEY_Device_xxx constants"""
        ContainerId = DevicePropertyKey('{8c7ed206-3f8a-4827-b3ab-ae9e1faefc6c}', 2,
                                        'DEVPKEY_Device_ContainerId')

# noinspection SpellCheckingInspection
DIGCF_DEFAULT = DiGetClassDevsFlags.Default
# noinspection SpellCheckingInspection
DIGCF_PRESENT = DiGetClassDevsFlags.Present
# noinspection SpellCheckingInspection
DIGCF_ALLCLASSES = DiGetClassDevsFlags.AllClasses
# noinspection SpellCheckingInspection
DIGCF_PROFILE = DiGetClassDevsFlags.Profile
# noinspection SpellCheckingInspection
DIGCF_DEVICEINTERFACE = DiGetClassDevsFlags.DeviceInterface

# noinspection SpellCheckingInspection
DIOD_INHERIT_CLASSDRVS = DiOpenDeviceInfo.InheritClassDrvs
# noinspection SpellCheckingInspection
DIOD_CANCEL_REMOVE = DiOpenDeviceInfo.CancelRemove

# noinspection SpellCheckingInspection
DEVPKEY = DevicePropertyKeys
DEVPKEY_Device_ContainerId = DevicePropertyKeys.Device.ContainerId
