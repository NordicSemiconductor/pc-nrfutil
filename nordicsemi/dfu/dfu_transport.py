# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

# Python specific imports
import abc
import logging

# Nordic Semiconductor imports
from nordicsemi.dfu.util import int32_to_bytes

logger = logging.getLogger(__name__)


class DfuEvent:
    PROGRESS_EVENT = 1
    TIMEOUT_EVENT = 2
    ERROR_EVENT = 3


class DfuTransport(object):
    """
    This class as an abstract base class inherited from when implementing transports.

    The class is generic in nature, the underlying implementation may have missing semantic
    than this class describes. But the intent is that the implementer shall follow the semantic as
    best as she can.
    """
    __metaclass__ = abc.ABCMeta

    @staticmethod
    def create_image_size_packet(softdevice_size=0, bootloader_size=0, app_size=0):
        """
        Creates an image size packet necessary for sending start dfu.

        @param softdevice_size: Size of SoftDevice firmware
        @type softdevice_size: int
        @param bootloader_size: Size of bootloader firmware
        @type softdevice_size: int
        @param app_size: Size of application firmware
        :return: The image size packet
        :rtype: str
        """
        softdevice_size_packet = int32_to_bytes(softdevice_size)
        bootloader_size_packet = int32_to_bytes(bootloader_size)
        app_size_packet = int32_to_bytes(app_size)
        image_size_packet = softdevice_size_packet + bootloader_size_packet + app_size_packet
        return image_size_packet

    @abc.abstractmethod
    def __init__(self):
        self.callbacks = {}

    @abc.abstractmethod
    def open(self):
        """
        Open a port if appropriate for the transport.
        :return:
        """
        pass

    @abc.abstractmethod
    def close(self):
        """
        Close a port if appropriate for the transport.
        :return:
        """
        pass

    @abc.abstractmethod
    def is_open(self):
        """
        Returns if transport is open.

        :return bool: True if transport is open, False if not
        """
        pass

    @abc.abstractmethod
    def send_start_dfu(self, program_mode, softdevice_size=0, bootloader_size=0, app_size=0):
        """
        Send packet to initiate DFU communication. Returns when packet is sent or timeout occurs.

        This call will block until packet is sent.
        If timeout or errors occurs exception is thrown.

        :param nordicsemi.dfu.model.HexType program_mode: Type of firmware to upgrade
        :param int softdevice_size: Size of softdevice firmware
        :param int bootloader_size: Size of bootloader firmware
        :param int app_size: Size of application firmware
        :return:
        """
        pass

    @abc.abstractmethod
    def send_init_packet(self, init_packet):
        """
        Send init_packet to device.

        This call will block until init_packet is sent and transfer of packet is complete.
        If timeout or errors occurs exception is thrown.

        :param str init_packet: Init packet as a str.
        :return:
        """
        pass

    @abc.abstractmethod
    def send_firmware(self, firmware):
        """
        Start sending firmware to device.

        This call will block until transfer of firmware is complete.
        If timeout or errors occurs exception is thrown.

        :param str firmware:
        :return:
        """
        pass

    @abc.abstractmethod
    def send_validate_firmware(self):
        """
        Send request to device to verify that firmware has been correctly transferred.

        This call will block until validation is sent and validation is complete.
        If timeout or errors occurs exception is thrown.

        :return bool: True if firmware validated successfully.
        """
        pass

    @abc.abstractmethod
    def send_activate_firmware(self):
        """
        Send command to device to activate new firmware and restart the device.
        The device will start up with the new firmware.

        Raises an nRFException if anything fails.

        :return:
        """
        pass

    def register_events_callback(self, event_type, callback):
        """
        Register a callback.

        :param DfuEvent callback:
        :return: None
        """
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []

        self.callbacks[event_type].append(callback)

    def unregister_events_callback(self, callback):
        """
        Unregister a callback.

        :param callback: # TODO: add documentation for callback
        :return: None
        """
        for event_type in self.callbacks.keys():
            if callback in self.callbacks[event_type]:
                self.callbacks[event_type].remove(callback)

    def _send_event(self, event_type, **kwargs):
        """
        Method for sending events to registered callbacks.

        If callbacks throws exceptions event propagation will stop and this method be part of the track trace.

        :param DfuEvent event_type:
        :param args: Arguments to callback function
        :return:
        """
        if event_type in self.callbacks.keys():
            for callback in self.callbacks[event_type]:
                callback(**kwargs)
