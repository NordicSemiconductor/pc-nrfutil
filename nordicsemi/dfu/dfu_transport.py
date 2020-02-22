# Copyright (c) 2016 - 2019 Nordic Semiconductor ASA
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

import logging
import struct
from enum import IntEnum
from abc import ABC, abstractmethod

# Nordic Semiconductor imports

logger = logging.getLogger(__name__)


# Custom logging level for logging all transport events, including all bytes
# being transported over the wire or over the air.
# Note that this logging level is more verbose than logging.DEBUG.
TRANSPORT_LOGGING_LEVEL = 5

class DfuEvent:
    PROGRESS_EVENT = 1

class ValidationException(Exception):
    """"
    Exception used when validation failed. 
    """
    pass

class OperationError(Exception):
    """ Raised when a operation command failed. Example a write command """
    pass

class OperationResTimeoutError(OperationError):
    """ DFU operation response timeout """
    pass

class OperationResCodeError(OperationError):
    """ Raised when an operation command succesfully sent and received
    but response code (RES_CODE) indicates an error """
    pass


class _IntEnumFormat(IntEnum):
    """ 
    IntEnum base class for pretty formated strings
    """

    def __str__(self):
        return "{}.{}:0x{:02X}".format(type(self).__name__, self.name, self.value)

    def __repr__(self):
        return self.__str__()


class OP_CODE(_IntEnumFormat):
    """ 
    Operation command codes. (control point characteristic in case of BLE)
    names (more or less) according to C enum nrf_dfu_op_t (prefix: OP_CODE) 

    Excluded:
        `INVALID =  0xFF` 
        'ReadError' = 0x05 - for `ant` and `serial` transport. never used. deprecated?  
    """

    # fmt: off
    PROTOCOL_VERSION   =  0x00
    OBJECT_CREATE      =  0x01 # aka CreateObject
    PRN_SET            =  0x02 # aka RECEIPT_NOTIF_SET or setPRN
    CRC_GET            =  0x03 # aka CalcChecSum
    OBJECT_EXECUTE     =  0x04 # aka Execute
    OBJECT_SELECT      =  0x06 # aka ReadObject
    MTU_GET            =  0x07 # aka GetSerialMTU
    OBJECT_WRITE       =  0x08 # aka WriteObject
    PING               =  0x09 # aka Ping
    HARDWARE_VERSION   =  0x0A
    FIRMWARE_VERSION   =  0x0B
    ABORT              =  0x0C
    RESPONSE           =  0x60 # aka Response
    # fmt: on


class RES_CODE(_IntEnumFormat):
    """ 
    Operation command response codes (control point characteristic in case of BLE)
    note: success is _not_ zero!
    names according to C enum nrf_dfu_result_t (prefix: RES_CODE).
    Excluding:
        INVALID =  0x00
        INVALID_SIGNATURE  aka 'InvalidSignature'  = 0x06
    """

    # fmt: off
    SUCCESS                  =  0x01 # aka Success
    OP_CODE_NOT_SUPPORTED    =  0x02 # aka NotSupported
    INVALID_PARAMETER        =  0x03 # aka InvalidParameter
    INSUFFICIENT_RESOURCES   =  0x04 # aka InsufficientResources
    INVALID_OBJECT           =  0x05 # aka InvalidObject
    UNSUPPORTED_TYPE         =  0x07 # aka UnsupportedType
    OPERATION_NOT_PERMITTED  =  0x08 # aka OperationNotPermitted
    OPERATION_FAILED         =  0x0A # aka OperationFailed
    EXT_ERROR                =  0x0B # aka ExtendedError
    # fmt: on


class EXT_ERROR(_IntEnumFormat):
    """ 
    Operation extended error code.
    names according to C enum nrf_dfu_ext_error_code_t (prefix: NRF_DFU_EXT_ERROR) 
    """

    # fmt: off
    NO_ERROR              =  0x00
    INVALID_ERROR_CODE    =  0x01
    WRONG_COMMAND_FORMAT  =  0x02
    UNKNOWN_COMMAND       =  0x03
    INIT_COMMAND_INVALID  =  0x04
    FW_VERSION_FAILURE    =  0x05
    HW_VERSION_FAILURE    =  0x06
    SD_VERSION_FAILURE    =  0x07
    SIGNATURE_MISSING     =  0x08
    WRONG_HASH_TYPE       =  0x09
    HASH_FAILED           =  0x0A
    WRONG_SIGNATURE_TYPE  =  0x0B
    VERIFICATION_FAILED   =  0x0C
    INSUFFICIENT_SPACE    =  0x0D
    # fmt: on


EXT_ERROR_DESCR = [
    "No extended error code has been set. This error indicates an implementation problem.",
    "Invalid error code. This error code should never be used outside of development.",
    "The format of the command was incorrect. This error code is not used in the current implementation, because @ref NRF_DFU_RES_CODE_OP_CODE_NOT_SUPPORTED and @ref NRF_DFU_RES_CODE_INVALID_PARAMETER cover all possible format errors.",
    "The command was successfully parsed, but it is not supported or unknown.",
    "The init command is invalid. The init packet either has an invalid update type or it is missing required fields for the update type (for example, the init packet for a SoftDevice update is missing the SoftDevice size field).",
    "The firmware version is too low. For an application, the version must be greater than or equal to the current application. For a bootloader, it must be greater than the current version. This requirement prevents downgrade attacks.""",
    "The hardware version of the device does not match the required hardware version for the update.",
    "The array of supported SoftDevices for the update does not contain the FWID of the current SoftDevice.",
    "The init packet does not contain a signature, but this bootloader requires all updates to have one.",
    "The hash type that is specified by the init packet is not supported by the DFU bootloader.",
    "The hash of the firmware image cannot be calculated.",
    "The type of the signature is unknown or not supported by the DFU bootloader.",
    "The hash of the received firmware image does not match the hash in the init packet.",
    "The available space on the device is insufficient to hold the firmware.",
    "The requested firmware to update was already present on the system.",
]

class OBJ_TYPE(_IntEnumFormat):
    """ 
    object_type. Relates to OP_CODE.OBJECT_SELECT and OP_CODE.OBJECT_CREATE
    names according to C enum nrf_dfu_obj_type_t. 
    excluding: INVALID  =  0x00 
    """

    # fmt: off
    COMMAND  =  0x01
    DATA     =  0x02
    # fmt: on


class FW_TYPE(_IntEnumFormat):
    """ Firwmare type.
    names according to enum nrf_dfu_firmware_type_t (prefix: NRF_DFU_FIRMWARE_TYPE_) """

    # fmt: off
    SOFTDEVICE   =  0x00
    APPLICATION  =  0x01
    BOOTLOADER   =  0x02
    # fmt: on


def operation_txd_pack(opcode, **kwargs):
    """ Pack operation command request/transmit/tx data .
    (control point characteristic TX data in case of BLE).
    returns bytes or bytearray
    """
    if not isinstance(opcode, OP_CODE):
        opcode = OP_CODE(opcode)  # raise ValueError if invalid

    if opcode == OP_CODE.PRN_SET:
        prn = kwargs.pop("prn")  # '<H':uint16 (LE)
        packed = struct.pack("<BH", opcode, prn)

    elif opcode == OP_CODE.OBJECT_SELECT:
        obj_type = kwargs.pop("object_type")  # '<B':uint8
        obj_type = OBJ_TYPE(obj_type)  # raise ValueError if invalid
        packed = struct.pack("<BB", opcode, obj_type)

    elif opcode == OP_CODE.OBJECT_CREATE:
        obj_type = kwargs.pop("object_type")  # B:uint8
        obj_size = kwargs.pop("size")  # '<I':uint32 (LE)
        obj_type = OBJ_TYPE(obj_type)  # raise ValueError if invalid
        packed = struct.pack("<BBI", opcode, obj_type, obj_size)

    elif opcode == OP_CODE.OBJECT_WRITE:
        data = kwargs.pop("data")  # bytes [int] or similar
        packed = bytes([opcode, *data])

    elif opcode == OP_CODE.PING:
        ping_id = kwargs.pop("ping_id")  # B:uint8
        packed = struct.pack("<BB", opcode, ping_id)

    else:
        packed = struct.pack("<B", opcode)

    if kwargs:
        raise ValueError(
            "Unrecognised argument(s) {} for {}".format(
                list(kwargs.keys()), str(opcode)
            )
        )

    return packed


def operation_rxd_unpack(opcode, data, has_header=True):
    """ Parses/unpack operation command response/received data.
    (control point characteristic RX data in case of BLE)
    """

    if not isinstance(opcode, OP_CODE):
        opcode = OP_CODE(opcode)

    if has_header:
        payload = op_rxd_parse_header(opcode, data)
    else:
        payload = data

    if opcode == OP_CODE.OBJECT_SELECT:
        (max_size, offset, crc) = struct.unpack("<III", payload)  # '<I':uint32 (LE)
        return {"max_size": max_size, "offset": offset, "crc": crc}

    if opcode == OP_CODE.CRC_GET:
        (offset, crc) = struct.unpack("<II", payload)  # '<I':uint32 (LE)
        return {"offset": offset, "crc": crc}

    if opcode == OP_CODE.MTU_GET:
        return struct.unpack("<H", payload)[0]  # mtu: '<H':uint16 (LE)

    if opcode == OP_CODE.PING:
        return struct.unpack("<B", payload)[0]  # uint8 ping_id

    return payload


def operation_rxd_parse_header(opcode, data):
    """ Parse operation command header and verify success. 
    returns payload with header removed.
    (control point characteristic RX data header in case of BLE)
    """

    if isinstance(opcode, OP_CODE):
        tx_opcode = opcode
    else:
        tx_opcode = OP_CODE(opcode)

    emsg = "Operation {} failed - response: ".format(str(tx_opcode))

    if len(data) < 3:
        raise OperationError(emsg, "incomplete size", len(data))

    try:
        rx_opcode = OP_CODE(data[1])
    except ValueError as e:
        raise OperationError(emsg, "OP_CODE.<unknown>", str(e))

    if rx_opcode != tx_opcode:
        raise OperationError(emsg, "unexpected opcode", rx_opcode)

    try:
        rescode = RES_CODE(data[2])
    except ValueError as e:
        raise OperationError(emsg, "RES_CODE.<unknown>", str(e))

    if rescode == RES_CODE.EXT_ERROR:
        if len(data) < 4:
            raise OperationError(emsg, "missing EXT_ERROR")

        try:
            exterr = EXT_ERROR(data[3])
        except ValueError as e:
            # raise OperationResCodeError even if ext error code is unknown
            exterr = "EXT_ERROR.<unknown> - {}".format(str(e))

        raise OperationResCodeError(emsg, exterr)

    # note SUCCESS is not zero
    if rescode != RES_CODE.SUCCESS:
        raise OperationResCodeError(emsg, rescode)

    # success
    return data[3:]




class DfuTransport(ABC):
    """
    This class as an abstract base class inherited from when implementing transports.

    The class is generic in nature, the underlying implementation may have missing semantic
    than this class describes. But the intent is that the implementer shall follow the semantic as
    best as she can.
    """

    @abstractmethod
    def __init__(self):
        self.callbacks = {}


    @abstractmethod
    def open(self):
        """
        Open a port if appropriate for the transport.
        :return:
        """
        pass


    @abstractmethod
    def close(self):
        """
        Close a port if appropriate for the transport.
        :return:
        """
        pass

    @abstractmethod
    def _operation_message_recv(self):
        """ return bytearray/bytes operation data message without any transport
        specific traits.  aka `get_message`.
        Should raise OperationRxTimeoutError on repsonse timeout"""
        raise NotImplementedError()

    @abstractmethod
    def _operation_message_send(self, txdata):
        """ write/send operation message (aka `send_message`)
        txdata - packed bytearray or bytes . 
        """
        raise NotImplementedError()

    def _operation_recv(self, opcode):
        rxdata = self._operation_read_bytes()
        logger.log(TRANSPORT_LOGGING_LEVEL, "{}: <-- {}".format(self._name, rxdata))
        return operation_rxd_unpack(opcode, rxdata)

    def _operation_send(self, opcode, **kwargs):
        """ Write/send operation data (repsonse not read). (control point characteristic in case of BLE"""
        logger.log(TRANSPORT_LOGGING_LEVEL, "{}: <-- {}".format(self._name, rxdata))
        operation_operation_

    def _operation_cmd(self, opcode, **kwargs):

        """ 
        send operation request, 
        recive response, parse response and verify success.
        returns parsed payload (if any)
        """
        self._operation_send(opcode, **kwargs):
        retrun self._operation_recv(opcode)


    @abstractmethod 
    def _stream_data_packet(self, data): # TODO name what?
        """ aka `write_data_point` (BLE) """
        # TODO: BLE
            self.dfu_adapter.write_data_point(list(to_transmit))

        # TODO: ANT
            # append the write data opcode to the front
            # here the maximum data size is self.mtu - 4
            # due to the header bytes in commands.
            to_transmit = data[i:i + self.mtu - 4 ]
            to_transmit = struct.pack('B',DfuTransportAnt.OP_CODE['WriteObject']) + to_transmit

        # TODO: SER
            # append the write data opcode to the front
            # here the maximum data size is self.mtu/2,
            # due to the slip encoding which at maximum doubles the size
            to_transmit = data[i:i + (self.mtu-1)//2 - 1 ]
            #to_transmit = struct.pack('B',DfuTransportSerial.OP_CODE['WriteObject']) + to_transmit
            #self.dfu_adapter.send_message(list(to_transmit))
            self._operation_data_write(OP_CODE.OBJECT_WRITE, data)

    def _stream_data(self, data, crc, offset, packet_size):
        """ packet_size differs depending on transport :
                ANT: self.mtu - 4
                SER: (self.mtu-1)//2 - 1)
                BLE: self.dfu_adapter.packet_size
            """
        logger.debug("{}: Streaming Data: len:{0} offset:{1} crc:0x{2:08X}".format(self._name,
            len(data), offset, crc)
        )
        def validate_crc():
            if (crc != response['crc']):
                raise ValidationException('Failed CRC validation.\n'\
                                + 'Expected: {} Received: {}.'.format(crc, response['crc']))
            if (offset != response['offset']):
                raise ValidationException('Failed offset validation.\n'\
                                + 'Expected: {} Received: {}.'.format(offset, response['offset']))

        current_pnr = 0
        for i in range(0, len(data), packet_size):
            to_transmit     = data[i:i + packet_size]
            self.dfu_adapter.write_data_point(list(to_transmit))
            crc     = binascii.crc32(to_transmit, crc) & 0xFFFFFFFF
            offset += len(to_transmit)
            current_pnr    += 1
            if self.prn == current_pnr:
                current_pnr = 0
                response    = self.op_read(OP_CODE.CRC_GET)
                validate_crc()

        response = self.op_cmd(OP_CODE.CRC_GET)
        validate_crc()

        return crc

    def send_init_packet(self, init_packet, retries=0):
        """
        Send init_packet to device.

        This call will block until init_packet is sent and transfer of packet is complete.

        :param init_packet: Init packet
        :param retries: retries to send if failed
        :return:
        """
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

            self.dfu_adapter.op_cmd(OP_CODE.OBJ_EXECUTE)
            return True

        response = self.op_cmd(OP_CODE.OBJ_SELECT, obj_type=OBJ_TYPE.COMMAND)

        assert len(init_packet) <= response['max_size'], 'Init command is too long'

        if try_to_recover():
            return

        for _r in range(retries):
            try:
                self.__create_command(len(init_packet))
                self._stream_data(data=init_packet)
                self.__execute()
            except ValidationException:
                pass
            break
        else:
            raise NordicSemiException("Failed to send init packet")


    def send_firmware(self, firmware):
        """
        Start sending firmware to device.

        This call will block until transfer of firmware is complete.

        :param firmware:
        :return:
        """
        def try_to_recover():
            if response['offset'] == 0:
                # Nothing to recover
                return

            expected_crc = crc32(firmware[:response['offset']]) & 0xFFFFFFFF
            remainder    = response['offset'] % response['max_size']

            # TODO:diff ANT: if (expected_crc != response['crc']) or (remainder == 0): 
            # ant from commit ~2018 not in BLE/SER: from ~2016
            if expected_crc != response['crc'] or remainder == 0:
                # Invalid CRC. Remove corrupted data.
                response['offset'] -= remainder if remainder != 0 else response['max_size']
                response['crc']     = binascii.crc32(firmware[:response['offset']]) & 0xFFFFFFFF
                return

            if (remainder != 0) and (response['offset'] != len(firmware)):
                # Send rest of the page.
                try:
                    to_send             = firmware[response['offset'] : response['offset'] + response['max_size'] - remainder]
                    response['crc']     = self._stream_data(data   = to_send,
                                                             crc    = response['crc'],
                                                             offset = response['offset'])
                    response['offset'] += len(to_send)
                except ValidationException:
                    # Remove corrupted data.
                    response['offset'] -= remainder
                    response['crc']     = binascii.crc32(firmware[:response['offset']]) & 0xFFFFFFFF
                    return

            self.op_cmd(OP_CODE.OBJECT_EXECUTE)
            self._send_event(event_type=DfuEvent.PROGRESS_EVENT, progress=response['offset'])

        response = self._operation_cmd(OP_CODE.OBJ_SELECT, obj_type=OBJ_TYPE.DATA)
        try_to_recover()

        for i in range(response['offset'], len(firmware), response['max_size']):
            data = firmware[i:i+response['max_size']]
            for r in range(DfuTransportBle.RETRIES_NUMBER):
                try:
                    self.__create_data(len(data))
                    response['crc'] = self.__stream_data(data=data, crc=response['crc'], offset=i)
                    self.op_cmd(OP_CODE.OBJECT_EXECUTE)
                except ValidationException:
                    pass
                break
            else:
                raise NordicSemiException("Failed to send firmware")
            self._send_event(event_type=DfuEvent.PROGRESS_EVENT, progress=len(data))


    def register_events_callback(self, event_type, callback):
        """
        Register a callback.

        :param DfuEvent callback:
        :return: None
        """
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []

        self.callbacks[event_type].append(callback)


    def _send_event(self, event_type, **kwargs):
        """
        Method for sending events to registered callbacks.

        If callbacks throws exceptions event propagation will stop and this method be part of the track trace.

        :param DfuEvent event_type:
        :param kwargs: Arguments to callback function
        :return:
        """
        if event_type in list(self.callbacks.keys()):
            for callback in self.callbacks[event_type]:
                callback(**kwargs)
