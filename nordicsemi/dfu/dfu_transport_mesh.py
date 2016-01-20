# Copyright (c) 2015, Nordic Semiconductor
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of Nordic Semiconductor ASA nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Python imports
import time
from datetime import datetime, timedelta
import binascii
import logging
from threading import Thread, Lock
import struct
import random

# Python 3rd party imports
from serial import Serial

# Nordic Semiconductor imports
from nordicsemi.dfu.util import int16_to_bytes, int32_to_bytes, bytes_to_int32
from nordicsemi.exceptions import NordicSemiException
from nordicsemi.dfu.dfu_transport import DfuTransport, DfuEvent

MESH_DFU_PACKET_FWID = 0xFFFE
MESH_DFU_PACKET_STATE = 0xFFFD
MESH_DFU_PACKET_DATA = 0xFFFC
MESH_DFU_PACKET_DATA_REQ = 0xFFFB
MESH_DFU_PACKET_DATA_RSP = 0xFFFA

DFU_UPDATE_MODE_NONE = 0
DFU_UPDATE_MODE_SD = 1
DFU_UPDATE_MODE_BL = 2
DFU_UPDATE_MODE_APP = 4

logger = logging.getLogger(__name__)

class DfuVersion:

    def __init__(self, sd=None, bl_id=None, bl_ver=None, company_id=None, app_id=None, app_ver=None):
        self.sd = sd
        self.bl_id = bl_id
        self.bl_ver = bl_ver
        self.company_id = company_id
        self.app_id = app_id
        self.app_ver = app_ver

    def get_number(self, dfu_type):
        if dfu_type == DFU_UPDATE_MODE_SD:
            if not self.sd:
                raise ValueError("sd can't be None if type is SD")
            return int16_to_bytes(self.sd)
        elif dfu_type == DFU_UPDATE_MODE_BL:
            if not self.bl_id:
                raise ValueError("bl_id can't be None if type is BL")
            if not self.bl_ver:
                raise ValueError("bl_ver can't be None if type is BL")
            number = ''
            number += chr(self.bl_id)
            number += chr(self.bl_ver)
            return number
        elif dfu_type == DFU_UPDATE_MODE_APP:
            if not self.company_id:
                raise ValueError("company_id can't be None if type is APP")
            if not self.app_id:
                raise ValueError("app_id can't be None if type is APP")
            if not self.app_ver:
                raise ValueError("app_ver can't be None if type is APP")
            number = ''
            number += int32_to_bytes(self.company_id)
            number += int16_to_bytes(self.app_id)
            number += int32_to_bytes(self.app_ver)
            return number
        else:
            print "UNABLE TO GET DFU NUMBER WITH TYPE {0}".format(ord(dfu_type))
            return None


    def is_larger_than(self, other, dfu_type):
        if dfu_type == DFU_UPDATE_MODE_SD:
            return False
        elif dfu_type == DFU_UPDATE_MODE_BL:
            if self.bl_id != other.bl_id or self.bl_ver <= other.bl_ver:
                return False
        elif dfu_type == DFU_UPDATE_MODE_APP:
            if self.company_id != other.company_id or self.app_id != other.app_id or self.app_ver <= other.app_ver:
                return False
        else:
            return False

        return True

    def __str__(self):
        number = ''
        number += self.get_number(DFU_UPDATE_MODE_SD)
        number += self.get_number(DFU_UPDATE_MODE_BL)
        number += self.get_number(DFU_UPDATE_MODE_APP)
        return binascii.hexlify(number)

class DfuInfoMesh:

    def __init__(self, data):
        self.dfu_type = ord(data[0])
        self.start_addr = bytes_to_int32(data[1:5])
        self.fw_len = bytes_to_int32(data[5:9])
        if len(data) > 64:
            self.sign_len = ord(data[9])
            self.signature = data[10:10 + self.sign_len]
        else:
            self.sign_len = 0
        raw_ver = data[10 + self.sign_len:]
        self.ver = DfuVersion(
            sd = bytes_to_int32(raw_ver[0:2]),
            bl_id = ord(raw_ver[0]),
            bl_ver = ord(raw_ver[1]),
            company_id = bytes_to_int32(raw_ver[0:4]),
            app_id = bytes_to_int32(raw_ver[4:6]),
            app_ver = bytes_to_int32(raw_ver[6:10]))



class DfuTransportMesh(DfuTransport):

    DEFAULT_BAUD_RATE = 1000000
    DEFAULT_FLOW_CONTROL = True
    DEFAULT_SERIAL_PORT_TIMEOUT = 1.0  # Timeout time on serial port read
    ACK_PACKET_TIMEOUT = 1.0  # Timeout time for for ACK packet received before reporting timeout through event system
    SEND_INIT_PACKET_WAIT_TIME = 0.1  # Time to wait before communicating with bootloader after init packet is sent
    SEND_START_DFU_WAIT_TIME = 0.2  # Time to wait before communicating with bootloader after start DFU packet is sent
    SEND_DATA_PACKET_WAIT_TIME = 0.5 # Time between each data packet
    RETRY_WAIT_TIME = 0.5 # Time to wait before attempting to retransmit a packet
    DFU_PACKET_MAX_SIZE = 16  # The DFU packet max size

    def __init__(self, com_port, baud_rate=DEFAULT_BAUD_RATE, flow_control=DEFAULT_FLOW_CONTROL, timeout=DEFAULT_SERIAL_PORT_TIMEOUT, interval=SEND_DATA_PACKET_WAIT_TIME):
        super(DfuTransportMesh, self).__init__()
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.flow_control = 1 if flow_control else 0
        self.timeout = timeout
        self.write_lock = Lock()
        self.serial_port = None
        """:type: serial.Serial """

        self.pending_packets = []
        self.packet_handlers = {}
        self.packet_handlers['\x78'] = self._handle_dfu
        self.packet_handlers['\x81'] = self._handle_started
        self.packet_handlers['\x82'] = self._handle_echo
        self.packet_handlers['\x84'] = self._handle_ack
        self.info = None
        self.tid = 0
        self.firmware = None
        self.device_started = False
        self.interval = interval


    def open(self):
        super(DfuTransportMesh, self).open()

        try:
            self.serial_port = Serial(port=self.com_port, baudrate=self.baud_rate, rtscts=self.flow_control, timeout=self.timeout)
        except Exception, e:
            raise NordicSemiException("Serial port could not be opened on {0}. Reason: {1}".format(self.com_port, e.message))

        logger.info("Opened com-port")
        Thread(target=self.receive_thread).start()

    def close(self):
        super(DfuTransportMesh, self).close()
        self.serial_port.close()

    def is_open(self):
        super(DfuTransportMesh, self).is_open()

        if self.serial_port is None:
            return False

        return self.serial_port.isOpen()

    def send_validate_firmware(self):
        super(DfuTransportMesh, self).send_validate_firmware()
        return True

    def send_start_dfu(self, mode, softdevice_size=None, bootloader_size=None, app_size=None):
        super(DfuTransportMesh, self).send_start_dfu(mode, softdevice_size, bootloader_size, app_size)

        # reset device
        self.send_bytes('\x01\x0E')
        logger.info("Sent reset-command")
        while not self.device_started:
            time.sleep(0.01)
        time.sleep(0.2)


    def send_init_packet(self, init_packet):
        # send all init packets with reasonable delay
        super(DfuTransportMesh, self).send_init_packet(init_packet)
        self.info = DfuInfoMesh(init_packet)
        self.tid = random.randint(0, 0xFFFFFFFF)
        ready = ''
        ready += int16_to_bytes(MESH_DFU_PACKET_STATE)
        ready += chr(self.info.dfu_type)
        ready += chr(0x0F)
        ready += int32_to_bytes(self.tid)
        ready += self.info.ver.get_number(self.info.dfu_type)

        ready_packet = SerialPacket(self, ready)
        self.send_packet(ready_packet)
        time.sleep(DfuTransportMesh.SEND_START_DFU_WAIT_TIME)

        start = ''
        start += int16_to_bytes(MESH_DFU_PACKET_DATA)
        start += '\x00\x00'
        start += int32_to_bytes(self.tid)
        start += int32_to_bytes(self.info.start_addr)
        start += int32_to_bytes(self.info.fw_len / 4)
        start += int16_to_bytes(self.info.sign_len)
        start += '\x0C'

        start_packet = SerialPacket(self, start)
        self.send_packet(start_packet)
        time.sleep(self.interval)

    def send_activate_firmware(self):
        super(DfuTransportMesh, self).send_activate_firmware()

    def send_firmware(self, firmware):
        super(DfuTransportMesh, self).send_firmware(firmware)

        self.firmware = firmware
        frames = []
        self._send_event(DfuEvent.PROGRESS_EVENT, progress=0, done=False, log_message="")

        fw_segments = len(firmware) / DfuTransportMesh.DFU_PACKET_MAX_SIZE

        if len(firmware) % DfuTransportMesh.DFU_PACKET_MAX_SIZE > 0:
            fw_segments += 1

        for segment in range(1, 1 + fw_segments):
            data_packet = ''
            data_packet += int16_to_bytes(MESH_DFU_PACKET_DATA)
            data_packet += int16_to_bytes(segment)
            data_packet += int32_to_bytes(self.tid)
            data_packet += self.get_fw_segment(segment)
            frames.append(data_packet)

        # add signature at the end
        for (segment, i) in enumerate(range(0, self.info.sign_len, DfuTransportMesh.DFU_PACKET_MAX_SIZE)):
            sign_packet = ''
            sign_packet += int16_to_bytes(MESH_DFU_PACKET_DATA)
            sign_packet += int16_to_bytes(segment + fw_segments + 1)
            sign_packet += int32_to_bytes(self.tid)
            if i >= self.info.sign_len:
                sign_packet += self.info.signature[i:]
            else:
                sign_packet += self.info.signature[i:i + DfuTransportMesh.DFU_PACKET_MAX_SIZE]
            frames.append(sign_packet)

        frames_count = len(frames)

        # Send firmware packets
        temp_progress = 0.0
        for (count, pkt) in enumerate(frames):
            self.send_packet(SerialPacket(self, pkt))
            temp_progress += 100.0 / float(frames_count)
            if temp_progress > 1.0:
                self._send_event(DfuEvent.PROGRESS_EVENT,
                                 log_message="",
                                 progress= temp_progress,
                                 done=False)
                temp_progress = 0.0
            time.sleep(self.interval)


        while len(self.pending_packets) > 0:
            time.sleep(0.01)

        self._send_event(DfuEvent.PROGRESS_EVENT, progress=100, done=False, log_message="")

    def get_fw_segment(self, segment):
        i = (segment - 1) * DfuTransportMesh.DFU_PACKET_MAX_SIZE
        if segment is 1 and self.info.start_addr != 0xFFFFFFFF:
            # first packet must normalize 16-byte alignment
            return self.firmware[i:i + 16 - (self.info.start_addr % 16)]
        elif i >= len(self.firmware):
            return None
        elif i + DfuTransportMesh.DFU_PACKET_MAX_SIZE > len(self.firmware):
            return self.firmware[i:]
        else:
            return self.firmware[i:i + DfuTransportMesh.DFU_PACKET_MAX_SIZE]

    def send_packet(self, pkt):
        logger.info("PC -> target: {0}".format(pkt))
        self.pending_packets.append(pkt)
        pkt.send()
        pkt.wait_for_ack()

    def receive_packet(self):
        if self.serial_port and self.serial_port.isOpen():
            packet_len = self.serial_port.read(1)
            if packet_len:
                packet_len = ord(packet_len)
                rx_count = 0
                rx_data = self.serial_port.read(packet_len)
                logger.info("target -> PC: {0}".format(binascii.hexlify(rx_data)))
                return rx_data
        return None

    def receive_thread(self):
        try:
            while self.serial_port:
                rx_data = self.receive_packet()
                if rx_data and rx_data[0] in self.packet_handlers:
                        self.packet_handlers[rx_data[0]](rx_data)
        except Exception, e:
            self._send_event(DfuEvent.ERROR_EVENT,
                log_message = e.message)


    def send_bytes(self, data):
        with self.write_lock:
            self.serial_port.write(data)

    def push_timeout(self):
        self._send_event(DfuEvent.TIMEOUT_EVENT,
                log_message="Timed out waiting for acknowledgement from device.")

############### PACKET HANDLERS
    def _handle_dfu(self, data):
        handle = bytes_to_int32(data[:2])
        if handle is MESH_DFU_PACKET_FWID:
            _handle_dfu_fwid(data[2:])
        elif handle is MESH_DFU_PACKET_STATE:
            _handle_dfu_state(data[2:])
        elif handle is MESH_DFU_PACKET_DATA_REQ:
            _handle_dfu_data_req(data[2:])

    def _handle_echo(self, data):
        print "Received echo response: {0}".format(data[1:])

    def _handle_ack(self, data):
        for packet in self.pending_packets:
            if packet.check_ack(data):
                self.pending_packets.remove(packet)

    def _handle_started(self, data):
        if self.device_started:
            raise NordicSemiException("Device aborted the transfer. Mode: " + str(ord(data[1])) + ", Error: " + str(ord(data[2])))
        if data[1] == '\x01' and data[2] == '\x00':
            self.device_started = True
        elif not self.device_started: # should ignore any startup events after the initial
            raise NordicSemiException("Device did not enter bootloader after reset (State: {0}, HW-error: {1})".format(ord(data[1]), ord(data[2])))

    def _handle_dfu_fwid(self, data):
        if self.init_info:
            other_ver = DfuVersion(
                    sd = bytes_to_int32(data[0:2]),
                    bl_id = data[2],
                    bl_ver = data[3],
                    company_id = bytes_to_int32(data[4:8]),
                    app_id = bytes_to_int32(data[8:10]),
                    app_ver = bytes_to_int32(data[10:14]))
            # don't really care yet

    def _handle_dfu_data_req(self, data):
        segment = data[0:2]
        tid = data[2:6]
        if tid is self.tid and firmware and segment > 0:
            rsp = ''
            rsp += int16_to_bytes(MESH_DFU_PACKET_DATA_RSP)
            rsp += data[:6]
            fw_segment = get_fw_segment(segment)
            if not fw_segment:
                return # invalid segment number
            rsp += fw_segment

            rsp_packet = SerialPacket(self, rsp)
            self.send_packet(rsp_packet)

    def _handle_dfu_state(self, data):
        pass


DFU_UPDATE_MODE_NONE = 0
DFU_UPDATE_MODE_SD = 1
DFU_UPDATE_MODE_BL = 2
DFU_UPDATE_MODE_APP = 4

MESH_DFU_OPCODE = 0x78


class SerialPacket(object):
    """Class representing a single Mesh serial packet"""

    def __init__(self, transport, data='', timeout=DfuTransportMesh.RETRY_WAIT_TIME):
        self.data = ''
        self.data += chr(len(data) + 1)
        self.data += chr(MESH_DFU_OPCODE)
        self.data += data
        self.is_acked = False
        self.retries = 0
        self.transport = transport
        self.timeout = timeout

    def send(self):
        Thread(target = self.run).start()

    def run(self):
        while self.retries < 3 and self.transport.serial_port and not self.is_acked:
            self.transport.send_bytes(self.data)
            self.retries += 1
            time.sleep(self.timeout)
        if self.retries is 3:
            self.transport.push_timeout()

    def get_type(self):
        temp = '\x00\x00' + self.data[2:4]
        return (struct.unpack("<L", self.data[2:4] + '\x00\x00')[0])

    def check_ack(self, ack_data):
        self.is_acked = ((ack_data[0] == '\x84') and (ack_data[1] == '\x78'))
        return self.is_acked

    def wait_for_ack(self):
        while not self.is_acked:
            time.sleep(0.01)

    def __str__(self):
        return binascii.hexlify(self.data)

