"""
:mod:`pysetupdi.constants`

Pre-defined constants from windows SDK

https://github.com/gwangyi/pysetupdi
"""

import enum
from structures import DevicePropertyKey


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
class DevicePropertyKeys(object):
    """DEVPKEY_xxx constants"""
    NAME = DevicePropertyKey('{b725f130-47ef-101a-a5f1-02608c9eebac}', 10, 'DEVPKEY_NAME')
    Numa_Proximity_Domain = DevicePropertyKey('{540b947e-8b40-45bc-a8a2-6a0b894cbda2}', 1,
                                              'DEVPKEY_Numa_Proximity_Domain')

    # noinspection SpellCheckingInspection
    class Device(object):
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
