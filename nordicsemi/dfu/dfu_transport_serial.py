#
# Copyright (c) 2016 Nordic Semiconductor ASA
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

# Python imports
import time
from datetime import datetime, timedelta
import binascii
import logging

# Python 3rd party imports
from serial import Serial
from serial.serialutil import SerialException

# Local imports
from nordicsemi.dfu.dfu_transport import (
    OP_CODE,
    DfuTransport,
    DfuEvent,
    TRANSPORT_LOGGING_LEVEL,
    ValidationException,
    NordicSemiException,
    operation_rxd_unpack,
    OperationResCodeError,
    OperationResponseTimeoutError,
)
from nordicsemi.lister.device_lister import DeviceLister
from nordicsemi.dfu.dfu_trigger import DFUTrigger

logger = logging.getLogger(__name__)


class Slip:
    """
    Serial Line Internet Protocol (SLIP) encode and decode
    """

    # fmt: off
    BYTE_END             = 0o300
    BYTE_ESC             = 0o333
    BYTE_ESC_END         = 0o334
    BYTE_ESC_ESC         = 0o335

    STATE_DECODING                 = 1
    STATE_ESC_RECEIVED             = 2
    STATE_CLEARING_INVALID_PACKET  = 3
    # fmt: on

    def __init__(self):
        self._state = self.STATE_DECODING
        self._decoded = bytearray()

    def reset_decoder(self):
        self._state = self.STATE_DECODING
        self._decoded = bytearray()

    @property
    def decoded(self):
        return self._decoded

    def encode(self, data):
        newData = bytearray()
        for elem in data:
            if elem == self.BYTE_END:
                newData.append(self.BYTE_ESC)
                newData.append(self.BYTE_ESC_END)
            elif elem == self.BYTE_ESC:
                newData.append(self.BYTE_ESC)
                newData.append(self.BYTE_ESC_ESC)
            else:
                newData.append(elem)
        newData.append(self.BYTE_END)
        return newData

    def decode_byte(self, c):
        finished = False
        if self._state == self.STATE_DECODING:
            if c == self.BYTE_END:
                finished = True
            elif c == self.BYTE_ESC:
                self._state = self.STATE_ESC_RECEIVED
            else:
                self._decoded.append(c)
        elif self._state == self.STATE_ESC_RECEIVED:
            if c == self.BYTE_ESC_END:
                self._decoded.append(self.BYTE_END)
                self._state = self.STATE_DECODING
            elif c == self.BYTE_ESC_ESC:
                self._decoded.append(self.BYTE_ESC)
                self._state = self.STATE_DECODING
            else:
                logger.warning("SLIP: Invalid package ignored")
                self._state = self.STATE_CLEARING_INVALID_PACKET
        elif self._state == self.STATE_CLEARING_INVALID_PACKET:
            if c == self.BYTE_END:
                self._state = self.STATE_DECODING
                self._decoded = bytearray()

        return finished


class DfuTransportSerial(DfuTransport):

    DEFAULT_BAUD_RATE = 115200
    DEFAULT_FLOW_CONTROL = True
    DEFAULT_TIMEOUT = 30.0  # Timeout time for board response
    DEFAULT_PRN = 0
    DEFAULT_DO_PING = True

    def __init__(
        self,
        com_port,
        baud_rate=DEFAULT_BAUD_RATE,
        flow_control=DEFAULT_FLOW_CONTROL,
        timeout=DEFAULT_TIMEOUT,
        prn=DEFAULT_PRN,
        do_ping=DEFAULT_DO_PING,
    ):

        super().__init__(name="SERIAL")
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.flow_control = flow_control
        self.timeout = timeout
        self.prn = prn
        self.mtu = 0
        self.do_ping = do_ping
        self._slip = Slip()
        self._serial = None

    def open(self):
        super().open()
        try:
            self.__ensure_bootloader()
            self._serial = Serial(
                port=self.com_port,
                baudrate=self.baud_rate,
                rtscts=1 if self.flow_control else 0,
                timeout=self.timeout,
            )
        except Exception as e:
            raise NordicSemiException(
                "Serial port could not be opened on {0}"
                ". Reason: {1}".format(self.com_port, str(e))
            )

        if self.do_ping:
            ping_success = False
            start = datetime.now()
            while (
                datetime.now() - start < timedelta(seconds=self.timeout)
                and ping_success == False
            ):
                if self._ping() == True:
                    ping_success = True

            if ping_success == False:
                raise NordicSemiException("No ping response after opening COM port")

        self._operation_cmd(OP_CODE.PRN_SET, prn=self.prn)
        self.mtu = self._operation_cmd(OP_CODE.MTU_GET)

    def close(self):
        super().close()
        self._serial.close()

    def _operation_message_send(self, data):
        """ Required by super(). Encode SLIP message and send/write it """
        encoded = self._slip.encode(data)
        logger.log(TRANSPORT_LOGGING_LEVEL, "SLIP: --> " + str(data))
        try:
            self._serial.write(encoded)
        except SerialException as e:
            raise NordicSemiException(
                "Writing to serial port failed: " + str(e) + ". "
                "If MSD is enabled on the target device, try to disable it ref. "
                "https://wiki.segger.com/index.php?title=J-Link-OB_SAM3U"
            )

    def _operation_message_recv(self):
        """ Required by super(). Receive/read SLIP message and decode it """
        decoded = None
        self._slip.reset_decoder()
        # TODO add timeout if slip package dropped otherwise stuck in loop
        while True:
            rxdata = self._serial.read(1)
            if not rxdata:
                raise OperationResponseTimeoutError("Serial read timeout")

            have_packet = self._slip.decode_byte(rxdata[0])
            if have_packet:
                decoded = self._slip.decoded
                break

        logger.log(TRANSPORT_LOGGING_LEVEL, "SLIP: <-- " + str(decoded))
        return decoded

    def _operation_recv(self, opcode):
        """ Required by super() """
        # TODO is this OK? (how it was from first commit but was not obvious)
        try:
            rxdata = self._operation_message_recv()
        except OperationResponseTimeoutError as e:
            if opcode == OP_CODE.OBJ_CREATE:
                logger.warning("Ignoring response timeout as OP_CODE.OBJ_CREATE")
                return None
            else:
                raise e  # re-raise
        return operation_rxd_unpack(opcode, rxdata)

    @property
    def _packet_size(self):
        """ Required by super() """
        # maximum data size is self.mtu/2,
        # due to the slip encoding which at maximum doubles the size
        # -1 for leading OP_CODE byte
        return (self.mtu - 1) // 2 - 1

    def _stream_packet(self, txdata):
        """ Required by super() """
        return self._operation_send(OP_CODE.OBJ_WRITE, data=txdata)

    def __ensure_bootloader(self):
        lister = DeviceLister()

        device = None
        start = datetime.now()
        while not device and datetime.now() - start < timedelta(seconds=self.timeout):
            time.sleep(0.5)
            device = lister.get_device(com=self.com_port)

        if device:
            device_serial_number = device.serial_number

            if not self.__is_device_in_bootloader_mode(device):
                retry_count = 10
                wait_time_ms = 500

                trigger = DFUTrigger()
                try:
                    trigger.enter_bootloader_mode(device)
                    logger.info("Serial: DFU bootloader was triggered")
                except NordicSemiException as err:
                    logger.error(err)

                for checks in range(retry_count):
                    logger.info(
                        "Serial: Waiting {} ms for device to enter bootloader {}/{} time".format(
                            500, checks + 1, retry_count
                        )
                    )

                    time.sleep(wait_time_ms / 1000.0)

                    device = lister.get_device(serial_number=device_serial_number)
                    if self.__is_device_in_bootloader_mode(device):
                        self.com_port = device.get_first_available_com_port()
                        break

                trigger.clean()
            if not self.__is_device_in_bootloader_mode(device):
                logger.info(
                    "Serial: Device is either not in bootloader mode, or using an unsupported bootloader."
                )

    def __is_device_in_bootloader_mode(self, device):
        if not device:
            return False

        #  Return true if nrf bootloader or Jlink interface detected.
        vendor_id = device.vendor_id.lower()
        product_id = device.product_id.lower()

        # nRF52 SDFU USB
        if vendor_id == "1915" and product_id == "521f":
            return True

        # JLink CDC UART Port
        if vendor_id == "1366" and product_id == "0105":
            return True

        # JLink CDC UART Port (MSD)
        if vendor_id == "1366" and product_id == "1015":
            return True

        return False

