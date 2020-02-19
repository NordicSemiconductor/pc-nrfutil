import struct
from enum import IntEnum


class DfuOperationError(Exception):
    """ Raised when an operation command failed """

    pass


class DfuOperationResCodeError(DfuOperationError):
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


def op_txd_pack(opcode, **kwargs):
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


def op_rxd_unpack(opcode, data, has_header=True):
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


def op_rxd_parse_header(opcode, data):
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
        raise DfuOperationError(emsg, "incomplete size", len(data))

    try:
        rx_opcode = OP_CODE(data[1])
    except ValueError as e:
        raise DfuOperationError(emsg, "OP_CODE.<unknown>", str(e))

    if rx_opcode != tx_opcode:
        raise DfuOperationError(emsg, "unexpected opcode", rx_opcode)

    try:
        rescode = RES_CODE(data[2])
    except ValueError as e:
        raise DfuOperationError(emsg, "RES_CODE.<unknown>", str(e))

    if rescode == RES_CODE.EXT_ERROR:
        if len(data) < 4:
            raise DfuOperationError(emsg, "missing EXT_ERROR")

        try:
            exterr = EXT_ERROR(data[3])
        except ValueError as e:
            # raise DfuOperationResCodeError even if ext error code is unknown
            exterr = "EXT_ERROR.<unknown> - {}".format(str(e))

        raise DfuOperationResCodeError(emsg, exterr)

    # note SUCCESS is not zero
    if rescode != RES_CODE.SUCCESS:
        raise DfuOperationResCodeError(emsg, rescode)

    # success
    return data[3:]

