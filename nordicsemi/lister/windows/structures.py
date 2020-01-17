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

import ctypes
from ctypes.wintypes import DWORD, BYTE, WORD
from serial.win32 import ULONG_PTR

_ole32 = ctypes.WinDLL('ole32')


class _GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', DWORD),
        ('Data2', WORD),
        ('Data3', WORD),
        ('Data4', BYTE * 8),
    ]

    def __init__(self, guid="{00000000-0000-0000-0000-000000000000}"):
        super().__init__()
        if isinstance(guid, str):
            ret = _ole32.CLSIDFromString(ctypes.create_unicode_buffer(guid), ctypes.byref(self))
            if ret < 0:
                err_no = ctypes.GetLastError()
                raise WindowsError(err_no, ctypes.FormatError(err_no), guid)
        else:
            ctypes.memmove(ctypes.byref(self), bytes(guid), ctypes.sizeof(self))

    def __str__(self):
        s = ctypes.c_wchar_p()
        ret = _ole32.StringFromCLSID(ctypes.byref(self), ctypes.byref(s))
        if ret < 0:
            err_no = ctypes.GetLastError()
            raise WindowsError(err_no, ctypes.FormatError(err_no))
        ret = str(s.value)
        _ole32.CoTaskMemFree(s)
        return ret

    def __repr__(self):
        return "<GUID: {}>".format(str(self))


assert ctypes.sizeof(_GUID) == 16


class GUID:
    def __init__(self, guid="{00000000-0000-0000-0000-000000000000}"):
        self._guid = _GUID(guid)

    def __bytes__(self):
        return bytes(self._guid)

    def __str__(self):
        return str(self._guid)

    def __repr__(self):
        return repr(self._guid)


class DevicePropertyKey(ctypes.Structure):
    # noinspection SpellCheckingInspection
    _fields_ = [
        ('fmtid', _GUID),
        ('pid', ctypes.c_ulong)
    ]

    def __init__(self, guid, pid, name=None):
        super().__init__()
        self.fmtid.__init__(guid)
        self.pid = pid
        self.name = name
        self.__doc__ = str(self)

    def __repr__(self):
        return "<DevPropKey: {}>".format(str(self))

    def __str__(self):
        if not hasattr(self, 'name') or self.name is None:
            # noinspection SpellCheckingInspection
            return "{} {}".format(self.fmtid, self.pid)
        else:
            # noinspection SpellCheckingInspection
            return "{}, {} {}".format(self.name, self.fmtid, self.pid)

    def __eq__(self, key):
        if not isinstance(key, DevicePropertyKey):
            return False
        return bytes(self) == bytes(key)


class DeviceInfoData(ctypes.Structure):
    _fields_ = [
        ('cbSize', DWORD),
        ('ClassGuid', _GUID),
        ('DevInst', DWORD),
        ('Reserved', ULONG_PTR),
    ]

    def __init__(self):
        super().__init__()
        self.cbSize = ctypes.sizeof(self)

    def __str__(self):
        return "ClassGuid:{} DevInst:{}".format(self.ClassGuid, self.DevInst)


class ctypesInternalGUID:
    def __init__(self, bytes):
        self._internal = bytes

    def __bytes__(self):
        return bytes(self._internal)


def ValidHandle(value, func, arguments):
    if value == 0:
        raise ctypes.WinError()
    return value


DeviceInfoData.size = DeviceInfoData.cbSize
DeviceInfoData.dev_inst = DeviceInfoData.DevInst
DeviceInfoData.class_guid = DeviceInfoData.ClassGuid
# noinspection SpellCheckingInspection
SP_DEVINFO_DATA = DeviceInfoData
# noinspection SpellCheckingInspection
DEVPROPKEY = DevicePropertyKey
