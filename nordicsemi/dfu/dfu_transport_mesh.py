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
from collections import deque

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
            if self.sd is None:
                raise ValueError("sd can't be None if type is SD")
            return int16_to_bytes(self.sd)
        elif dfu_type == DFU_UPDATE_MODE_BL:
            if self.bl_id is None:
                raise ValueError("bl_id can't be None if type is BL")
            if self.bl_ver is None:
                raise ValueError("bl_ver can't be None if type is BL")
            number = ''
            number += chr(self.bl_id)
            number += chr(self.bl_ver)
            return number
        elif dfu_type == DFU_UPDATE_MODE_APP:
            if self.company_id is None:
                raise ValueError("company_id can't be None if type is APP")
            if self.app_id is None:
                raise ValueError("app_id can't be None if type is APP")
            if self.app_ver is None:
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
    DEFAULT_SERIAL_PORT_TIMEOUT = 5.0  # Timeout time on serial port read
    SEND_START_DFU_WAIT_TIME = 2.0  # Time to wait before communicating with bootloader after start DFU packet is sent
    SEND_DATA_PACKET_WAIT_TIME = 0.5 # Time between each data packet
    DFU_PACKET_MAX_SIZE = 16  # The DFU packet max size
    ACK_WAIT_TIME = 0.5 # Time to wait for an ack before attempting to resend a packet.
    DATA_REQ_WAIT_TIME = 10.0 # Time to wait for missing packet requests after sending all packets
    MAX_CONTINUOUS_MESSAGE_INTERBYTE_GAP = 0.1 # Maximal time to wait between two bytes in the same packet
    MAX_RETRIES = 10 # Number of send retries before the serial connection is considered lost.

    # Worst case page erase time (max time + max time * worst case % of HFINT accuracy):
    # 52832: 89.7 + 6%: 95.08 ms; 52833: 87.5 + 9%: 88.59 ms; 52840: 85 + 8% : 86.08
    PAGE_ERASE_TIME_MAX = 95.08/1000
    PAGE_SIZE = 4096

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
        self.requested_packets = deque()
        self.info = None
        self.tid = 0
        self.firmware = None
        self.rxthread = None
        self.interval = interval

    def open(self):
        super(DfuTransportMesh, self).open()

        try:
            self.serial_port = Serial(port=self.com_port, baudrate=self.baud_rate, rtscts=self.flow_control, timeout=DfuTransportMesh.MAX_CONTINUOUS_MESSAGE_INTERBYTE_GAP)
        except Exception, e:
            if self.serial_port:
                self.serial_port.close()
            raise NordicSemiException("Serial port could not be opened on {0}. Reason: {1}".format(self.com_port, e.message))

        # Flush out-buffer
        logger.info("Flushing com-port...")
        # Flush incoming data by the assumption that no continuous message has a time gap of >MAX_CONTINUOUS_MESSAGE_INTERBYTE_GAP seconds
        while len(self.serial_port.read()) > 0:
            pass
        self.serial_port.timeout = self.timeout # set the timeout to actually wanted value
        logger.info("Opened com-port")
        self.rxthread = Thread(target=self.receive_thread)
        self.rxthread.daemon = False
        self.rxthread.start()
        time.sleep(1)

    def __del__(self):
        self.close()

    def close(self):
        logger.info("Closing serial port...")
        if self.is_open():
            self.serial_port.close()
        if self.rxthread:
            self.rxthread.join()

    def is_open(self):
        if self.serial_port is None:
            return False

        return self.serial_port.isOpen()

    def send_validate_firmware(self):
        super(DfuTransportMesh, self).send_validate_firmware()
        return True

    def send_start_dfu(self, mode, softdevice_size=None, bootloader_size=None, app_size=None):
        super(DfuTransportMesh, self).send_start_dfu(mode, softdevice_size, bootloader_size, app_size)

        # send echo for testing
        echo_packet = SerialPacket('\xAA\xBB\xCC\xDD', opcode=0x02)
        self.send_packet(echo_packet)

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

        ready_packet = SerialPacket(ready)
        logger.info("Sending ready packet")
        self.send_packet(ready_packet)
        time.sleep(DfuTransportMesh.SEND_START_DFU_WAIT_TIME)

        # send twice to ensure the application catches the TID.
        self.send_packet(ready_packet)
        time.sleep(DfuTransportMesh.SEND_START_DFU_WAIT_TIME)

        start_data = ''
        start_data += int16_to_bytes(MESH_DFU_PACKET_DATA)
        start_data += '\x00\x00'
        start_data += int32_to_bytes(self.tid)
        start_data += int32_to_bytes(self.info.start_addr)
        start_data += int32_to_bytes(self.info.fw_len / 4)
        start_data += int16_to_bytes(self.info.sign_len)
        start_data += '\x0C'

        start_packet = SerialPacket(start_data)
        logger.info("Sending start packet")
        self.send_packet(start_packet)

        # Wait time: time to erase flash + 50% margin for stack operation and timeslots if GATT is connected
        wait_time = DfuTransportMesh.PAGE_ERASE_TIME_MAX * (self.info.fw_len / DfuTransportMesh.PAGE_SIZE) * 1.50
        logger.info("Waiting for %.1f seconds for flash bank erase to complete." % wait_time)
        time.sleep(wait_time)

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
        self.temp_progress = 0.0
        for (count, pkt) in enumerate(frames):
            # First resend any requested packets
            while len(self.requested_packets) > 0:
                self.send_packet(SerialPacket(self.requested_packets.popleft()))
                time.sleep(self.interval)
            # Then send next frame
            self.send_packet(SerialPacket(pkt))
            self.log_progress(100.0 / float(frames_count))
            time.sleep(self.interval)

        # Wait for any final missing packet requests
        time.sleep(DfuTransportMesh.DATA_REQ_WAIT_TIME)
        while len(self.requested_packets) > 0:
            self.send_packet(SerialPacket(self.requested_packets.popleft()))
            time.sleep(self.interval)

        while len(self.pending_packets) > 0:
            time.sleep(0.01)

        self._send_event(DfuEvent.PROGRESS_EVENT, progress=100, done=True, log_message="")

    def log_progress(self, progress):
        self.temp_progress += progress
        if self.temp_progress > 1.0:
            self._send_event(DfuEvent.PROGRESS_EVENT,
                             log_message="",
                             progress= self.temp_progress,
                             done=False)
            self.temp_progress = 0.0


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
        wait_time = DfuTransportMesh.ACK_WAIT_TIME
        self.pending_packets.append(pkt)
        retries = 0
        while retries < DfuTransportMesh.MAX_RETRIES and pkt in self.pending_packets:
            logger.info(str(retries + 1) + ": PC -> target: " + binascii.hexlify(pkt.data))
            self.serial_port.write(pkt.data)
            timeout = wait_time + time.clock()
            while pkt in self.pending_packets and time.clock() < timeout:
                time.sleep(0.01)
            retries += 1

        if retries == DfuTransportMesh.MAX_RETRIES:
            raise Exception(pkt.fail_reason)

    def receive_packet(self):
        if self.serial_port and self.serial_port.isOpen():
            packet_len = self.serial_port.read(1)
            if packet_len:
                packet_len = ord(packet_len)
                if packet_len > 0:
                    rx_data = self.serial_port.read(packet_len)
                    logger.info("target -> PC: " + format(packet_len, '02x') + binascii.hexlify(rx_data))
                    return rx_data
        return None

    def receive_thread(self):
        try:
            while self.is_open():
                rx_data = self.receive_packet()
                if rx_data and rx_data[0] in self.packet_handlers:
                        self.packet_handlers[rx_data[0]](rx_data)
        except:
            pass

    def send_bytes(self, data):
        with self.write_lock:
            logger.info("PC -> target: " + binascii.hexlify(data))
            self.serial_port.write(data)

    def push_timeout(self):
        self._send_event(DfuEvent.TIMEOUT_EVENT,
                log_message="Timed out waiting for acknowledgement from device.")

############### PACKET HANDLERS
    def _handle_dfu(self, data):
        handle = bytes_to_int32(data[1:3])
        if handle == MESH_DFU_PACKET_DATA_REQ:
            self._handle_dfu_data_req(data[3:])

    def _handle_echo(self, data):
        for packet in self.pending_packets:
            if packet.get_opcode() == 0x02:
                self.pending_packets.remove(packet)
                logger.info("Got echo response")

    def _handle_ack(self, data):
        for packet in self.pending_packets:
            if packet.check_ack(data):
                self.pending_packets.remove(packet)

    def _handle_started(self, data):
        pass

    def _handle_dfu_data_req(self, data):
        segment = bytes_to_int32(data[0:2])
        tid = bytes_to_int32(data[2:6])
        if (tid == self.tid) and (self.firmware is not None) and (segment > 0):
            rsp = ''
            rsp += int16_to_bytes(MESH_DFU_PACKET_DATA_RSP)
            rsp += data[:6]
            fw_segment = self.get_fw_segment(segment)
            if not fw_segment:
                return # invalid segment number
            rsp += fw_segment

            self.requested_packets.append(rsp)

def get_longest_matching(lst, data):
    i = max([k for k in lst if data.startswith(k)], key=lambda k: len(k))
    if i in lst:
        return lst[i]
    else:
        return None

class SerialPacket(object):
    FAIL_REASON = {
        '\x02': 'Failed to establish connection',
        '\x78\xFA\xFF': 'Lost connection in the middle of responding to a missing packet request',
        '\x78\xFC\xFF\x00\x00': 'Crashed on start packet',
        '\x78\xFC\xFF': 'Lost connection in the middle of the transfer',
        '\x78\xFD\xFF': 'Lost connection in the setup phase',
        '\x78\xFE\xFF': 'Lost connection before starting the transfer'
    }
    SERIAL_STATUS_CODES={
        0x00: 'SUCCESS',
        0x80: 'ERROR_UNKNOWN',
        0x81: 'ERROR_INTERNAL',
        0x82: 'ERROR_CMD_UNKNOWN',
        0x83: 'ERROR_DEVICE_STATE_INVALID',
        0x84: 'ERROR_INVALID_LENGTH',
        0x85: 'ERROR_INVALID_PARAMETER',
        0x86: 'ERROR_BUSY',
        0x87: 'ERROR_INVALID_DATA',
        0x90: 'ERROR_PIPE_INVALID'
    }
    SERIAL_OPCODES={
    '\x02': 'Echo',
    '\x0E': 'Radio reset',
    '\x70': 'Init',
    '\x71': 'Value set',
    '\x72': 'Value enable',
    '\x73': 'Value disable',
    '\x74': 'Start',
    '\x75': 'Stop',
    '\x76': 'Flag set',
    '\x77': 'Flag get',
    '\x78\xFE': 'DFU FWID beacon',
    '\x78\xFD': 'DFU state beacon',
    '\x78\xFC\x00\x00': 'DFU start',
    '\x78\xFC': 'DFU data',
    '\x78\xFA': 'DFU data response',
    '\x7A': 'Value get',
    '\x7B': 'Build version get',
    '\x7C': 'Access addr get',
    '\x7D': 'Channel get',
    '\x7F': 'Interval get'
    }

    """Class representing a single Mesh serial packet"""
    def __init__(self, data='', opcode=0x78):
        self.data = ''
        self.data += chr(len(data) + 1)
        self.data += chr(opcode)
        self.data += data
        self.packet_name = get_longest_matching(SerialPacket.SERIAL_OPCODES, self.data[1:])
        self.fail_reason = get_longest_matching(SerialPacket.FAIL_REASON, self.data[1:])

    def get_opcode(self):
        return ord(self.data[1])

    def get_type(self):
        temp = '\x00\x00' + self.data[2:4]
        return (struct.unpack("<L", self.data[2:4] + '\x00\x00')[0])

    def check_ack(self, ack_data):
        error_code = ord(ack_data[2])
        for_me = ((ack_data[0] == '\x84') and (ack_data[1] == self.data[1]))
        acked = (for_me and (error_code == 0x00))
        if for_me and error_code != 0:
            if error_code in SerialPacket.SERIAL_STATUS_CODES:
                self.fail_reason = 'Device returned status code ' + SerialPacket.SERIAL_STATUS_CODES[error_code] + ' (' + str(error_code) + ') on a ' + self.packet_name + ' packet.'
            else:
                self.fail_reason = 'Device returned an unknown status code (' + str(error_code) + ') on a ' + self.packet_name + ' packet.'
        return acked

    def __str__(self):
        return binascii.hexlify(self.data)
