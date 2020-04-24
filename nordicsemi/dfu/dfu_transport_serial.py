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
import struct

# Python 3rd party imports
from serial import Serial
from serial.serialutil import SerialException

# Nordic Semiconductor imports
from nordicsemi.dfu.dfu_transport   import DfuTransport, DfuEvent, TRANSPORT_LOGGING_LEVEL
from pc_ble_driver_py.exceptions    import NordicSemiException
from nordicsemi.lister.device_lister import DeviceLister
from nordicsemi.dfu.dfu_trigger import DFUTrigger

class ValidationException(NordicSemiException):
    """"
    Exception used when validation failed
    """
    pass


logger = logging.getLogger(__name__)

class Slip:
    SLIP_BYTE_END             = 0o300
    SLIP_BYTE_ESC             = 0o333
    SLIP_BYTE_ESC_END         = 0o334
    SLIP_BYTE_ESC_ESC         = 0o335

    SLIP_STATE_DECODING                 = 1
    SLIP_STATE_ESC_RECEIVED             = 2
    SLIP_STATE_CLEARING_INVALID_PACKET  = 3

    @staticmethod
    def encode(data):
        newData = []
        for elem in data:
            if elem == Slip.SLIP_BYTE_END:
                newData.append(Slip.SLIP_BYTE_ESC)
                newData.append(Slip.SLIP_BYTE_ESC_END)
            elif elem == Slip.SLIP_BYTE_ESC:
                newData.append(Slip.SLIP_BYTE_ESC)
                newData.append(Slip.SLIP_BYTE_ESC_ESC)
            else:
                newData.append(elem)
        newData.append(Slip.SLIP_BYTE_END)
        return newData

    @staticmethod
    def decode_add_byte(c, decoded_data, current_state):
        finished = False
        if current_state == Slip.SLIP_STATE_DECODING:
            if c == Slip.SLIP_BYTE_END:
                finished = True
            elif c == Slip.SLIP_BYTE_ESC:
                current_state = Slip.SLIP_STATE_ESC_RECEIVED
            else:
                decoded_data.append(c)
        elif current_state == Slip.SLIP_STATE_ESC_RECEIVED:
            if c == Slip.SLIP_BYTE_ESC_END:
                decoded_data.append(Slip.SLIP_BYTE_END)
                current_state = Slip.SLIP_STATE_DECODING
            elif c == Slip.SLIP_BYTE_ESC_ESC:
                decoded_data.append(Slip.SLIP_BYTE_ESC)
                current_state = Slip.SLIP_STATE_DECODING
            else:
                current_state = Slip.SLIP_STATE_CLEARING_INVALID_PACKET
        elif current_state == Slip.SLIP_STATE_CLEARING_INVALID_PACKET:
            if c == Slip.SLIP_BYTE_END:
                current_state = Slip.SLIP_STATE_DECODING
                decoded_data = []

        return (finished, current_state, decoded_data)

class DFUAdapter:
    def __init__(self, serial_port):
        self.serial_port = serial_port

    def send_message(self, data):
        packet = Slip.encode(data)
        logger.log(TRANSPORT_LOGGING_LEVEL, 'SLIP: --> ' + str(data))
        try:
            self.serial_port.write(packet)
        except SerialException as e:
            raise NordicSemiException('Writing to serial port failed: ' + str(e) + '. '
                                      'If MSD is enabled on the target device, try to disable it ref. '
                                      'https://wiki.segger.com/index.php?title=J-Link-OB_SAM3U')

    def get_message(self):
        current_state = Slip.SLIP_STATE_DECODING
        finished = False
        decoded_data = []

        while finished == False:
            byte = self.serial_port.read(1)
            if byte:
                (byte) = struct.unpack('B', byte)[0]
                (finished, current_state, decoded_data) \
                   = Slip.decode_add_byte(byte, decoded_data, current_state)
            else:
                current_state = Slip.SLIP_STATE_CLEARING_INVALID_PACKET
                return None

        logger.log(TRANSPORT_LOGGING_LEVEL, 'SLIP: <-- ' + str(decoded_data))

        return decoded_data

class DfuTransportSerial(DfuTransport):

    DEFAULT_BAUD_RATE = 115200
    DEFAULT_FLOW_CONTROL = True
    DEFAULT_TIMEOUT = 30.0  # Timeout time for board response
    DEFAULT_SERIAL_PORT_TIMEOUT = 1.0  # Timeout time on serial port read
    DEFAULT_PRN                 = 0
    DEFAULT_DO_PING = True

    OP_CODE = {
        'CreateObject'          : 0x01,
        'SetPRN'                : 0x02,
        'CalcChecSum'           : 0x03,
        'Execute'               : 0x04,
        'ReadError'             : 0x05,
        'ReadObject'            : 0x06,
        'GetSerialMTU'          : 0x07,
        'WriteObject'           : 0x08,
        'Ping'                  : 0x09,
        'Response'              : 0x60,
    }

    def __init__(self,
                 com_port,
                 baud_rate=DEFAULT_BAUD_RATE,
                 flow_control=DEFAULT_FLOW_CONTROL,
                 timeout=DEFAULT_TIMEOUT,
                 prn=DEFAULT_PRN,
                 do_ping=DEFAULT_DO_PING):

        super().__init__()
        self.com_port = com_port
        self.baud_rate = baud_rate
        self.flow_control = 1 if flow_control else 0
        self.timeout = timeout
        self.prn         = prn
        self.serial_port = None
        self.dfu_adapter = None
        self.ping_id     = 0
        self.do_ping     = do_ping

        self.mtu         = 0

        """:type: serial.Serial """


    def open(self):
        super().open()
        try:
            self.__ensure_bootloader()
            self.serial_port = Serial(port=self.com_port,
                baudrate=self.baud_rate, rtscts=self.flow_control, timeout=self.DEFAULT_SERIAL_PORT_TIMEOUT)
            self.dfu_adapter = DFUAdapter(self.serial_port)
        except OSError as e:
            raise NordicSemiException("Serial port could not be opened on {0}"
              ". Reason: {1}".format(self.com_port, e.strerror))

        if self.do_ping:
            ping_success = False
            start = datetime.now()
            while (datetime.now() - start < timedelta(seconds=self.timeout)
                    and ping_success == False):
                if self.__ping() == True:
                    ping_success = True

            if ping_success == False:
                raise NordicSemiException("No ping response after opening COM port")

        self.__set_prn()
        self.__get_mtu()

    def close(self):
        super().close()
        self.serial_port.close()

    def send_init_packet(self, init_packet):
        def try_to_recover():
            if response['offset'] == 0 or response['offset'] > len(init_packet):
                # There is no init packet or present init packet is too long.
                return False

            expected_crc = (binascii.crc32(init_packet[:response['offset']]) & 0xFFFFFFFF)

            if expected_crc != response['crc']:
                # Present init packet is invalid.
                return False

            if len(init_packet) > response['offset']:
                # Send missing part.
                try:
                    self.__stream_data(data     = init_packet[response['offset']:],
                                       crc      = expected_crc,
                                       offset   = response['offset'])
                except ValidationException:
                    return False

            self.__execute()
            return True

        response = self.__select_command()
        assert len(init_packet) <= response['max_size'], 'Init command is too long'

        if try_to_recover():
            return

        try:
            self.__create_command(len(init_packet))
            self.__stream_data(data=init_packet)
            self.__execute()
        except ValidationException:
            raise NordicSemiException("Failed to send init packet")

    def send_firmware(self, firmware):
        def try_to_recover():
            if response['offset'] == 0:
                # Nothing to recover
                return

            expected_crc = binascii.crc32(firmware[:response['offset']]) & 0xFFFFFFFF
            remainder    = response['offset'] % response['max_size']

            if expected_crc != response['crc']:
                # Invalid CRC. Remove corrupted data.
                response['offset'] -= remainder if remainder != 0 else response['max_size']
                response['crc']     = \
                        binascii.crc32(firmware[:response['offset']]) & 0xFFFFFFFF
                return

            if (remainder != 0) and (response['offset'] != len(firmware)):
                # Send rest of the page.
                try:
                    to_send             = firmware[response['offset'] : response['offset']
                                                + response['max_size'] - remainder]
                    response['crc']     = self.__stream_data(data   = to_send,
                                                             crc    = response['crc'],
                                                             offset = response['offset'])
                    response['offset'] += len(to_send)
                except ValidationException:
                    # Remove corrupted data.
                    response['offset'] -= remainder
                    response['crc']     = \
                        binascii.crc32(firmware[:response['offset']]) & 0xFFFFFFFF
                    return

            self.__execute()
            self._send_event(event_type=DfuEvent.PROGRESS_EVENT, progress=response['offset'])

        response = self.__select_data()
        try_to_recover()
        for i in range(response['offset'], len(firmware), response['max_size']):
            data = firmware[i:i+response['max_size']]
            try:
                self.__create_data(len(data))
                response['crc'] = self.__stream_data(data=data, crc=response['crc'], offset=i)
                self.__execute()
            except ValidationException:
                raise NordicSemiException("Failed to send firmware")

            self._send_event(event_type=DfuEvent.PROGRESS_EVENT, progress=len(data))

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
                    logger.info("Serial: Waiting {} ms for device to enter bootloader {}/{} time"\
                    .format(500, checks + 1, retry_count))

                    time.sleep(wait_time_ms / 1000.0)

                    device = lister.get_device(serial_number=device_serial_number)
                    if self.__is_device_in_bootloader_mode(device):
                        self.com_port = device.get_first_available_com_port()
                        break

                trigger.clean()
            if not self.__is_device_in_bootloader_mode(device):
                logger.info("Serial: Device is either not in bootloader mode, or using an unsupported bootloader.")

    def __is_device_in_bootloader_mode(self, device):
        if not device:
            return False

        #  Return true if nrf bootloader or Jlink interface detected.
        return ((device.vendor_id.lower() == '1915' and device.product_id.lower() == '521f') # nRF52 SDFU USB
             or (device.vendor_id.lower() == '1366' and device.product_id.lower() == '0105') # JLink CDC UART Port
             or (device.vendor_id.lower() == '1366' and device.product_id.lower() == '1015'))# JLink CDC UART Port (MSD)

    def __set_prn(self):
        logger.debug("Serial: Set Packet Receipt Notification {}".format(self.prn))
        self.dfu_adapter.send_message([DfuTransportSerial.OP_CODE['SetPRN']]
            + list(struct.pack('<H', self.prn)))
        self.__get_response(DfuTransportSerial.OP_CODE['SetPRN'])

    def __get_mtu(self):
        self.dfu_adapter.send_message([DfuTransportSerial.OP_CODE['GetSerialMTU']])
        response = self.__get_response(DfuTransportSerial.OP_CODE['GetSerialMTU'])

        self.mtu = struct.unpack('<H', bytearray(response))[0]

    def __ping(self):
        self.ping_id = (self.ping_id + 1) % 256

        self.dfu_adapter.send_message([DfuTransportSerial.OP_CODE['Ping'], self.ping_id])
        resp = self.dfu_adapter.get_message() # Receive raw response to check return code

        if not resp:
            logger.debug('Serial: No ping response')
            return False

        if resp[0] != DfuTransportSerial.OP_CODE['Response']:
            logger.debug('Serial: No Response: 0x{:02X}'.format(resp[0]))
            return False

        if resp[1] != DfuTransportSerial.OP_CODE['Ping']:
            logger.debug('Serial: Unexpected Executed OP_CODE.\n' \
                + 'Expected: 0x{:02X} Received: 0x{:02X}'.format(DfuTransportSerial.OP_CODE['Ping'], resp[1]))
            return False

        if resp[2] != DfuTransport.RES_CODE['Success']:
            # Returning an error code is seen as good enough. The bootloader is up and running
            return True
        else:
            if struct.unpack('B', bytearray(resp[3:]))[0] == self.ping_id:
                return True
            else:
                return False

    def __create_command(self, size):
        self.__create_object(0x01, size)

    def __create_data(self, size):
        self.__create_object(0x02, size)

    def __create_object(self, object_type, size):
        self.dfu_adapter.send_message([DfuTransportSerial.OP_CODE['CreateObject'], object_type]\
                                            + list(struct.pack('<L', size)))
        self.__get_response(DfuTransportSerial.OP_CODE['CreateObject'])

    def __calculate_checksum(self):
        self.dfu_adapter.send_message([DfuTransportSerial.OP_CODE['CalcChecSum']])
        response = self.__get_response(DfuTransportSerial.OP_CODE['CalcChecSum'])

        if response is None:
            raise NordicSemiException('Did not receive checksum response from DFU target. '
                                      'If MSD is enabled on the target device, try to disable it ref. '
                                      'https://wiki.segger.com/index.php?title=J-Link-OB_SAM3U')

        (offset, crc) = struct.unpack('<II', bytearray(response))
        return {'offset': offset, 'crc': crc}

    def __execute(self):
        self.dfu_adapter.send_message([DfuTransportSerial.OP_CODE['Execute']])
        self.__get_response(DfuTransportSerial.OP_CODE['Execute'])

    def __select_command(self):
        return self.__select_object(0x01)

    def __select_data(self):
        return self.__select_object(0x02)

    def __select_object(self, object_type):
        logger.debug("Serial: Selecting Object: type:{}".format(object_type))
        self.dfu_adapter.send_message([DfuTransportSerial.OP_CODE['ReadObject'], object_type])

        response = self.__get_response(DfuTransportSerial.OP_CODE['ReadObject'])
        (max_size, offset, crc)= struct.unpack('<III', bytearray(response))

        logger.debug("Serial: Object selected: " +
            " max_size:{} offset:{} crc:{}".format(max_size, offset, crc))
        return {'max_size': max_size, 'offset': offset, 'crc': crc}

    def __get_checksum_response(self):
        resp = self.__get_response(DfuTransportSerial.OP_CODE['CalcChecSum'])

        (offset, crc) = struct.unpack('<II', bytearray(resp))
        return {'offset': offset, 'crc': crc}

    def __stream_data(self, data, crc=0, offset=0):
        logger.debug("Serial: Streaming Data: " +
            "len:{0} offset:{1} crc:0x{2:08X}".format(len(data), offset, crc))
        def validate_crc():
            if (crc != response['crc']):
                raise ValidationException('Failed CRC validation.\n'\
                                + 'Expected: {} Received: {}.'.format(crc, response['crc']))
            if (offset != response['offset']):
                raise ValidationException('Failed offset validation.\n'\
                                + 'Expected: {} Received: {}.'.format(offset, response['offset']))

        current_pnr     = 0

        for i in range(0, len(data), (self.mtu-1)//2 - 1):
            # append the write data opcode to the front
            # here the maximum data size is self.mtu/2,
            # due to the slip encoding which at maximum doubles the size
            to_transmit = data[i:i + (self.mtu-1)//2 - 1 ]
            to_transmit = struct.pack('B',DfuTransportSerial.OP_CODE['WriteObject']) + to_transmit

            self.dfu_adapter.send_message(list(to_transmit))
            crc     = binascii.crc32(to_transmit[1:], crc) & 0xFFFFFFFF
            offset += len(to_transmit) - 1
            current_pnr    += 1
            if self.prn == current_pnr:
                current_pnr = 0
                response    = self.__get_checksum_response()
                validate_crc()
        response = self.__calculate_checksum()
        validate_crc()
        return crc

    def __get_response(self, operation):
        def get_dict_key(dictionary, value):
            return next((key for key, val in list(dictionary.items()) if val == value), None)

        resp = self.dfu_adapter.get_message()

        if not resp:
            return None

        if resp[0] != DfuTransportSerial.OP_CODE['Response']:
            raise NordicSemiException('No Response: 0x{:02X}'.format(resp[0]))

        if resp[1] != operation:
            raise NordicSemiException('Unexpected Executed OP_CODE.\n' \
                             + 'Expected: 0x{:02X} Received: 0x{:02X}'.format(operation, resp[1]))

        if resp[2] == DfuTransport.RES_CODE['Success']:
            return resp[3:]

        elif resp[2] == DfuTransport.RES_CODE['ExtendedError']:
            try:
                data = DfuTransport.EXT_ERROR_CODE[resp[3]]
            except IndexError:
                data = "Unsupported extended error type {}".format(resp[3])
            raise NordicSemiException('Extended Error 0x{:02X}: {}'.format(resp[3], data))
        else:
            raise NordicSemiException('Response Code {}'.format(
                get_dict_key(DfuTransport.RES_CODE, resp[2])))
