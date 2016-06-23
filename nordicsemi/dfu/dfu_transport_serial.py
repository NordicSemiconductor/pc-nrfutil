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

# Nordic Semiconductor imports
from nordicsemi.dfu.util import slip_parts_to_four_bytes, slip_encode_esc_chars, int16_to_bytes, int32_to_bytes
from nordicsemi.dfu import crc16
from pc_ble_driver_py.exceptions import NordicSemiException
from nordicsemi.dfu.dfu_transport import DfuTransport, DfuEvent


logger = logging.getLogger(__name__)


class DfuTransportSerial(DfuTransport):

    DEFAULT_BAUD_RATE = 38400
    DEFAULT_FLOW_CONTROL = False
    DEFAULT_SERIAL_PORT_TIMEOUT = 1.0  # Timeout time on serial port read
    ACK_PACKET_TIMEOUT = 1.0  # Timeout time for for ACK packet received before reporting timeout through event system
    SEND_INIT_PACKET_WAIT_TIME = 1.0  # Time to wait before communicating with bootloader after init packet is sent
    SEND_START_DFU_WAIT_TIME = 10.0  # Time to wait before communicating with bootloader after start DFU packet is sent
    DFU_PACKET_MAX_SIZE = 512  # The DFU packet max size

    def __init__(self, com_port, baud_rate=DEFAULT_BAUD_RATE, flow_control=DEFAULT_FLOW_CONTROL, timeout=DEFAULT_SERIAL_PORT_TIMEOUT):
        super(DfuTransportSerial, self).__init__()
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.flow_control = 1 if flow_control else 0
        self.timeout = timeout
        self.serial_port = None
        """:type: serial.Serial """

    def open(self):
        super(DfuTransportSerial, self).open()

        try:
            self.serial_port = Serial(port=self.com_port, baudrate=self.baud_rate, rtscts=self.flow_control, timeout=self.timeout)
        except Exception, e:
            raise NordicSemiException("Serial port could not be opened on {0}. Reason: {1}".format(self.com_port, e.message))

    def close(self):
        super(DfuTransportSerial, self).close()
        self.serial_port.close()

    def is_open(self):
        super(DfuTransportSerial, self).is_open()

        if self.serial_port is None:
            return False

        return self.serial_port.isOpen()

    def send_validate_firmware(self):
        super(DfuTransportSerial, self).send_validate_firmware()
        return True

    def send_init_packet(self, init_packet):
        super(DfuTransportSerial, self).send_init_packet(init_packet)

        frame = int32_to_bytes(DFU_INIT_PACKET)
        frame += init_packet
        frame += int16_to_bytes(0x0000)  # Padding required

        packet = HciPacket(frame)
        self.send_packet(packet)
        time.sleep(DfuTransportSerial.SEND_INIT_PACKET_WAIT_TIME)

    def send_start_dfu(self, mode, softdevice_size=None, bootloader_size=None, app_size=None):
        super(DfuTransportSerial, self).send_start_dfu(mode, softdevice_size, bootloader_size, app_size)

        frame = int32_to_bytes(DFU_START_PACKET)
        frame += int32_to_bytes(mode)
        frame += DfuTransport.create_image_size_packet(softdevice_size, bootloader_size, app_size)

        packet = HciPacket(frame)
        self.send_packet(packet)
        time.sleep(DfuTransportSerial.SEND_START_DFU_WAIT_TIME)

    def send_activate_firmware(self):
        super(DfuTransportSerial, self).send_activate_firmware()

    def send_firmware(self, firmware):
        super(DfuTransportSerial, self).send_firmware(firmware)

        def progress_percentage(part, whole):
            return int(100 * float(part)/float(whole))

        frames = []
        self._send_event(DfuEvent.PROGRESS_EVENT, progress=0, done=False, log_message="")

        for i in range(0, len(firmware), DfuTransportSerial.DFU_PACKET_MAX_SIZE):
            data_packet = HciPacket(int32_to_bytes(DFU_DATA_PACKET) + firmware[i:i + DfuTransportSerial.DFU_PACKET_MAX_SIZE])
            frames.append(data_packet)

        frames_count = len(frames)

        # Send firmware packets
        for count, pkt in enumerate(frames):
            self.send_packet(pkt)
            self._send_event(DfuEvent.PROGRESS_EVENT,
                             log_message="",
                             progress=progress_percentage(count, frames_count),
                             done=False)

        # Send data stop packet
        frame = int32_to_bytes(DFU_STOP_DATA_PACKET)
        packet = HciPacket(frame)
        self.send_packet(packet)

        self._send_event(DfuEvent.PROGRESS_EVENT, progress=100, done=False, log_message="")

    def send_packet(self, pkt):
        attempts = 0
        last_ack = None
        packet_sent = False

        logger.debug("PC -> target: {0}".format(pkt))

        while not packet_sent:
            self.serial_port.write(pkt.data)
            attempts += 1
            ack = self.get_ack_nr()

            if last_ack is None:
                break

            if ack == (last_ack + 1) % 8:
                last_ack = ack
                packet_sent = True

                if attempts > 3:
                    raise Exception("Three failed tx attempts encountered on packet {0}".format(pkt.sequence_number))

    def get_ack_nr(self):
        def is_timeout(start_time, timeout_sec):
            return not (datetime.now() - start_time <= timedelta(0, timeout_sec))

        uart_buffer = ''
        start = datetime.now()

        while uart_buffer.count('\xC0') < 2:
            # Disregard first of the two C0
            temp = self.serial_port.read(6)

            if temp:
                uart_buffer += temp

            if is_timeout(start, DfuTransportSerial.ACK_PACKET_TIMEOUT):
                # reset HciPacket numbering back to 0
                HciPacket.sequence_number = 0
                self._send_event(DfuEvent.TIMEOUT_EVENT,
                                 log_message="Timed out waiting for acknowledgement from device.")

                # quit loop
                break

                # read until you get a new C0
                # RESUME_WORK

        if len(uart_buffer) < 2:
            raise NordicSemiException("No data received on serial port. Not able to proceed.")

        logger.debug("PC <- target: {0}".format(binascii.hexlify(uart_buffer)))
        data = self.decode_esc_chars(uart_buffer)

        # Remove 0xC0 at start and beginning
        data = data[1:-1]

        # Extract ACK number from header
        return (data[0] >> 3) & 0x07

    @staticmethod
    def decode_esc_chars(data):
        """Replace 0xDBDC with 0xCO and 0xDBDD with 0xDB"""
        result = []

        data = bytearray(data)

        while len(data):
            char = data.pop(0)

            if char == 0xDB:
                char2 = data.pop(0)

                if char2 == 0xDC:
                    result.append(0xC0)
                elif char2 == 0xDD:
                    result.append(0xDB)
                else:
                    raise Exception('Char 0xDB NOT followed by 0xDC or 0xDD')
            else:
                result.append(char)

        return result

DATA_INTEGRITY_CHECK_PRESENT = 1
RELIABLE_PACKET = 1
HCI_PACKET_TYPE = 14

DFU_INIT_PACKET = 1
DFU_START_PACKET = 3
DFU_DATA_PACKET = 4
DFU_STOP_DATA_PACKET = 5

DFU_UPDATE_MODE_NONE = 0
DFU_UPDATE_MODE_SD = 1
DFU_UPDATE_MODE_BL = 2
DFU_UPDATE_MODE_APP = 4


class HciPacket(object):
    """Class representing a single HCI packet"""

    sequence_number = 0

    def __init__(self, data=''):
        HciPacket.sequence_number = (HciPacket.sequence_number + 1) % 8
        self.temp_data = ''
        self.temp_data += slip_parts_to_four_bytes(HciPacket.sequence_number,
                                                   DATA_INTEGRITY_CHECK_PRESENT,
                                                   RELIABLE_PACKET,
                                                   HCI_PACKET_TYPE,
                                                   len(data))
        self.temp_data += data
        # Add escape characters
        crc = crc16.calc_crc16(self.temp_data, crc=0xffff)

        self.temp_data += chr(crc & 0xFF)
        self.temp_data += chr((crc & 0xFF00) >> 8)

        self.temp_data = slip_encode_esc_chars(self.temp_data)

        self.data = chr(0xc0)
        self.data += self.temp_data
        self.data += chr(0xc0)

    def __str__(self):
        return binascii.hexlify(self.data)
