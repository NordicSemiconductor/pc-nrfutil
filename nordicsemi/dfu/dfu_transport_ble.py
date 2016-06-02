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

# Python standard library
import os
import abc
import Queue
import struct
import logging
import binascii

from functools      import wraps

# Nordic libraries
import nordicsemi.dfu.ble_driver.s130_nrf51_ble_driver  as ble_driver
import nordicsemi.dfu.ble_driver.ble_driver_util        as util

from nordicsemi.exceptions              import NordicSemiException, IllegalStateException
from nordicsemi.dfu.dfu_transport       import DfuTransport, DfuEvent


logging.basicConfig()
logger  = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
hdlr    = logging.FileHandler('myapp.log')
logger.addHandler(hdlr) 


CCCD_UUID = 0x2902

class Descriptor(object):
    def __init__(self, uuid, handle):
        self.handle = handle
        self.uuid   = uuid



class Characteristic(object):
    def __init__(self, uuid, start_handle):
        self.uuid           = uuid
        self.start_handle   = start_handle
        self.end_handle     = None
        self.descriptors    = list()
        self.cccd_handle    = None


    def desc_add(self, desc):
        self.descriptors.append(desc)
        if desc.uuid == CCCD_UUID:
            self.cccd_handle = desc.handle



class Service(object):
    def __init__(self):
        self.uuid               = None
        self.start_handle       = None
        self.end_handle         = None
        self.characteristics    = list()
        self.connection_handle  = None


    def char_add(self, char):
        char.end_handle = self.end_handle
        self.characteristics.append(char)
        if len(self.characteristics) > 1:
            self.characteristics[-2].end_handle = char.start_handle - 1



class DbDiscovery(object):
    def __init__(self):
        self.services                   = list()
        self.service_under_discovery    = None
        self.connection_handle          = None
        self.serv_disc_q                = Queue.Queue()
        self.char_disc_q                = Queue.Queue()
        self.desc_disc_q                = Queue.Queue()


    def get_char_value_handle_from_uuid(self, uuid):
        for s in self.services:
            for c in s.characteristics:
                if c.uuid == uuid:
                    for d in c.descriptors:
                        if d.uuid == uuid:
                            return d.handle


    def get_cccd_handle_from_uuid(self, uuid):
        for s in self.services:
            for c in s.characteristics:
                if c.uuid == uuid:
                    for d in c.descriptors:
                        if d.uuid == CCCD_UUID:
                            return d.handle
                    break
        return False


    def get_char_handle_from_ser_uuid(self, uuid):
        for s in self.services:
            for c in s.characteristics:
                if c.uuid == uuid:
                    return c.start_handle
                break
        return False


    def start_service_discovery(self):
        logger.debug("Discovering primary services")
        self.discover_serv(0x0001)
        #Discover all services
        while True:
            serv = self.serv_disc_q.get(timeout=5)
            if serv == None:
                break
            elif type(serv) == int:
                self.discover_serv(serv)
            else:
                self.services.append(serv)

        # Discover all characteristics and descriptors
        for s in self.services:
            self.discover_char(s.start_handle, s.end_handle)
            while True:
                chars = self.char_disc_q.get(timeout=5)
                if chars == None:
                    break
                for char in chars:
                    s.char_add(char)
                self.discover_char(char.start_handle+1, s.end_handle)
            for c in s.characteristics:
                self.discover_desc(c.start_handle, c.end_handle)
                while True:
                    descs = self.desc_disc_q.get(timeout=5)
                    if descs == None:
                        break
                    for desc in descs:
                        c.desc_add(desc)
                    if desc.handle == c.end_handle:
                        break
                    self.discover_desc(desc.handle+1, c.end_handle)


    def discover_desc(self, start_handle, end_handle):
        handle_range = ble_driver.ble_gattc_handle_range_t()
        handle_range.start_handle = start_handle
        handle_range.end_handle = end_handle
        err_code = ble_driver.NRF_ERROR_BUSY
        while err_code == ble_driver.NRF_ERROR_BUSY:
            err_code = ble_driver.sd_ble_gattc_descriptors_discover(self.connection_handle, handle_range)
        if err_code != ble_driver.NRF_SUCCESS:
            raise Exception("Failed descriptor discovery. Error code 0x{:02X}.".format(err_code))


    def discover_char(self, start_handle, end_handle):
        handle_range = ble_driver.ble_gattc_handle_range_t()
        handle_range.start_handle = start_handle
        handle_range.end_handle = end_handle
        err_code = ble_driver.NRF_ERROR_BUSY
        while err_code == ble_driver.NRF_ERROR_BUSY:
            err_code = ble_driver.sd_ble_gattc_characteristics_discover(self.connection_handle, handle_range)
        if err_code != ble_driver.NRF_SUCCESS:
            raise Exception("Failed characteristic discovery. Error code 0x{:02X}".format(err_code))

    def discover_serv(self, start_handle):
        err_code = ble_driver.sd_ble_gattc_primary_services_discover(self.connection_handle,
                                                                     start_handle,
                                                                     None)
        if err_code != ble_driver.NRF_SUCCESS:
            raise Exception("Failed primary services discovery. Error code 0x{:02X}".format(err_code))

    def on_service_discovery_response(self, gattc_event):
        if gattc_event.gatt_status == ble_driver.BLE_GATT_STATUS_ATTERR_ATTRIBUTE_NOT_FOUND:
            # No more services to discover, done
            self.serv_disc_q.put(None)
            return

        if gattc_event.gatt_status != ble_driver.NRF_SUCCESS:
            raise Exception("Failed service discovery. Error code 0x{:02X}".format(gattc_event.gatt_status))

        count = gattc_event.params.prim_srvc_disc_rsp.count

        if count == 0: return

        service_list = util.service_array_to_list(gattc_event.params.prim_srvc_disc_rsp.services, count)
        for _service in service_list:

            service = Service()

            service.uuid = _service.uuid.uuid
            service.start_handle = _service.handle_range.start_handle
            service.end_handle = _service.handle_range.end_handle
            logger.debug("UUID: 0x{0:04X}, start handle: 0x{1:04X}, end handle: 0x{2:04X}".format(service.uuid, service.start_handle, service.end_handle))
            self.serv_disc_q.put(service)
        # end_handle == 0xFFFF means all services discovered, done
        if service.end_handle == 0xFFFF:
            self.serv_disc_q.put(None)
            return
        # Put the end handle back to the queue so discovery can continue from there
        self.serv_disc_q.put(int(service.end_handle)+1)


    def on_characteristic_discovery_response(self, gattc_event):
        if gattc_event.gatt_status == ble_driver.BLE_GATT_STATUS_ATTERR_ATTRIBUTE_NOT_FOUND:
            # No more characteristics inside requested handle range, done
            self.char_disc_q.put(None)
            return

        if gattc_event.gatt_status != ble_driver.NRF_SUCCESS:
            raise Exception("Failed characteristic discovery. Error code 0x{:02X}".format(gattc_event.gatt_status))

        count = gattc_event.params.char_disc_rsp.count

        char_list = util.char_array_to_list(gattc_event.params.char_disc_rsp.chars, count)
        retval = []
        for _char in char_list:
            logger.debug("Characteristic handle: 0x{0:04X}, UUID: 0x{1:04X}".format(_char.handle_decl, _char.uuid.uuid))
            char = Characteristic(_char.uuid.uuid, _char.handle_decl)
            retval.append(char)
        self.char_disc_q.put(retval)

    def on_descriptor_discovery_response(self, gattc_event):
        if gattc_event.gatt_status == ble_driver.BLE_GATT_STATUS_ATTERR_ATTRIBUTE_NOT_FOUND:
            # No more descriptors inside requested handle range, done
            self.desc_disc_q.put(None)
            return
        if gattc_event.gatt_status != ble_driver.NRF_SUCCESS:
            raise Exception("Failed descriptor discovery. Error code 0x{:02X}".format(gattc_event.gatt_status))

        count = gattc_event.params.desc_disc_rsp.count
        desc_list = util.desc_array_to_list(gattc_event.params.desc_disc_rsp.descs, count)

        retval = []
        for _desc in desc_list:
            logger.debug("Descriptor handle: 0x{0:04X}, UUID: 0x{1:04X}".format(_desc.handle, _desc.uuid.uuid))
            desc = Descriptor(_desc.uuid.uuid, _desc.handle)
            retval.append(desc)
        self.desc_disc_q.put(retval)

    def ble_evt_handler(self, ble_event):
        evt_id = ble_event.header.evt_id

        if evt_id == ble_driver.BLE_GATTC_EVT_PRIM_SRVC_DISC_RSP:
            self.on_service_discovery_response(ble_event.evt.gattc_evt)

        elif evt_id == ble_driver.BLE_GATTC_EVT_CHAR_DISC_RSP:
            self.on_characteristic_discovery_response(ble_event.evt.gattc_evt)

        elif evt_id == ble_driver.BLE_GATTC_EVT_DESC_DISC_RSP:
            self.on_descriptor_discovery_response(ble_event.evt.gattc_evt)

        elif evt_id == ble_driver.BLE_GAP_EVT_CONNECTED:
            self.connection_handle = ble_event.evt.gap_evt.conn_handle

        elif evt_id == ble_driver.BLE_GAP_EVT_DISCONNECTED:
            self.connection_handle = ble_driver.BLE_CONN_HANDLE_INVALID



class BleAdapter(object):
    def __init__(self, serial_port, baud_rate):
        # Setup Connection Params
        self.conn_params                    = ble_driver.ble_gap_conn_params_t()
        self.conn_params.min_conn_interval  = util.msec_to_units(7.5,   util.UNIT_1_25_MS)
        self.conn_params.max_conn_interval  = util.msec_to_units(30,    util.UNIT_1_25_MS)
        self.conn_params.conn_sup_timeout   = util.msec_to_units(4000,  util.UNIT_10_MS)
        self.conn_params.slave_latency      = 0

        # Setup Scanning Params
        self.scan_params                    = ble_driver.ble_gap_scan_params_t()
        self.scan_params.active             = 1
        self.scan_params.selective          = 0
        self.scan_params.interval           = util.msec_to_units(200, util.UNIT_0_625_MS)
        self.scan_params.window             = util.msec_to_units(150, util.UNIT_0_625_MS)
        self.scan_params.timeout            = 0xA


        self.connection_is_in_progress  = False
        self.connection_handle          = ble_driver.BLE_CONN_HANDLE_INVALID
        self.evts_q                     = Queue.Queue()
        self.target_device_names        = list()
        self.target_device_addrs        = list()

        # Setup Discovery Database
        self.ble_evt_handlers           = list()
        self.db_discovery               = DbDiscovery()
        self.add_ble_evt_handler(self.db_discovery.ble_evt_handler)

        ble_driver.sd_rpc_serial_port_name_set(serial_port)
        ble_driver.sd_rpc_serial_baud_rate_set(baud_rate)
        ble_driver.sd_rpc_evt_handler_set(self.ble_evt_handler)
        ble_driver.sd_rpc_log_handler_set(self.log_message_handler)
        err_code = ble_driver.sd_rpc_open()
        if err_code != ble_driver.NRF_SUCCESS:
                raise Exception("Failed to open the BLE Driver. Error code: 0x{0:02X}".format(err_code))

        ble_enable_params = ble_driver.ble_enable_params_t()
        ble_enable_params.gatts_enable_params.attr_tab_size     = ble_driver.BLE_GATTS_ATTR_TAB_SIZE_DEFAULT
        ble_enable_params.gatts_enable_params.service_changed   = False

        error_code = ble_driver.sd_ble_enable(ble_enable_params)
        if error_code != ble_driver.NRF_SUCCESS:
            raise Exception("Failed ble stack initialization. Error code: 0x{0:02X}".format(error_code))


    def add_ble_evt_handler(self, handler):
        self.ble_evt_handlers.append(handler)


    def vs_uuid_add(self, uuid128):
        '''
        Returns ble_uuid_t.type value
        '''
        pointer         = util.list_to_uint8_array(uuid128)
        uuid            = ble_driver.ble_uuid128_t()
        uuid.uuid128    = pointer.cast()
        uuid_type       = ble_driver.new_uint8()

        err_code = ble_driver.sd_ble_uuid_vs_add(uuid, uuid_type)
        if err_code != ble_driver.NRF_SUCCESS:
            raise Exception("Failed vs_uuidn. Error code: 0x{0:02X}".format(error_code))
        return ble_driver.uint8_value(uuid_type)


    def wait_for_event(self, evt, timeout=20):
        while True:
            pulled_evt = self.evts_q.get(timeout=timeout)
            if pulled_evt == evt:
                logger.debug("Received expected event {}".format(pulled_evt))
                break
            if pulled_evt == None:
                raise Exception("Wait for event timed out, expected event: {}".format(evt))


    def set_conn_targets(self, target_device_name=None, target_device_addr=None):
        if target_device_name: 
            self.target_device_names.append(target_device_name)
        if target_device_addr: 
            self.target_device_addrs.append(target_device_addr)


    def close(self):
        error_code = ble_driver.sd_rpc_close()
        if error_code != ble_driver.NRF_SUCCESS:
            raise Exception("Failed to close the BLE Driver. Error code: 0x{0:02X}".format(error_code))


    def enable_notification(self, handle):
        cccd_list = [1, 0]
        self._gattc_write(cccd_list, handle)
        logger.debug("Notifications enabled on handle 0x{:04X}".format(handle))


    def _gattc_write(self, values, handle):
        cccd_array = util.list_to_uint8_array(values)

        write_params = ble_driver.ble_gattc_write_params_t()
        write_params.handle = handle
        write_params.len = len(values)
        write_params.p_value = cccd_array.cast()
        write_params.write_op = ble_driver.BLE_GATT_OP_WRITE_REQ
        write_params.offset = 0
        err_code = ble_driver.sd_ble_gattc_write(self.connection_handle, write_params)
        if err_code != ble_driver.NRF_SUCCESS:
            raise Exception("Failed gattc_write. Error code: 0x{0:02X}".format(err_code))

    def _gattc_write_cmd(self, values, handle):
        cccd_array = util.list_to_uint8_array(values)

        write_params = ble_driver.ble_gattc_write_params_t()
        write_params.handle = handle
        write_params.len = len(values)
        write_params.p_value = cccd_array.cast()
        write_params.write_op = ble_driver.BLE_GATT_OP_WRITE_CMD
        write_params.offset = 0
        err_code = ble_driver.sd_ble_gattc_write(self.connection_handle, write_params)
        if err_code != ble_driver.NRF_SUCCESS:
            raise Exception("Failed gattc_write_cmd. Error code: 0x{0:02X}".format(err_code))


    def start_scan(self):
        error_code = ble_driver.sd_ble_gap_scan_start(self.scan_params)
        if error_code != ble_driver.NRF_SUCCESS:
            raise Exception("Failed scan start. Error code: 0x{0:02X}".format(err_code))


    def log_message_handler(self, severity, log_message):
        logger.error("RPC Message: {}".format(log_message))


    def on_gap_evt_adv_report(self, gap_event):
        def parse_adv_report(adv_type, adv_data):
            index       = 0
            parsed_data = None
            try:
                while index < len(adv_data):
                    field_length = adv_data[index]
                    field_type = adv_data[index + 1]

                    if field_type == adv_type:
                        offset      = index + 2
                        parsed_data = adv_data[offset: offset + field_length - 1]
                        break
                    index += (field_length + 1)
            finally:
                return parsed_data

        if self.connection_is_in_progress: return
        address_list    = util.uint8_array_to_list(gap_event.params.adv_report.peer_addr.addr, 6)
        adv_data_list   = util.uint8_array_to_list(gap_event.params.adv_report.data, 
                                                   gap_event.params.adv_report.dlen)

        dev_name = parse_adv_report(ble_driver.BLE_GAP_AD_TYPE_COMPLETE_LOCAL_NAME, adv_data_list)
        if not dev_name:
            dev_name = parse_adv_report(ble_driver.BLE_GAP_AD_TYPE_SHORT_LOCAL_NAME, adv_data_list)

        peer_device_name    = "".join(chr(e) for e in dev_name)
        peer_device_addr    = "".join("{0:02X}".format(b) for b in address_list)

        logger.debug("Received advertisment report, address: 0x{}, device_name: {}".format(peer_device_addr,
                                                                                           peer_device_name))

        if (peer_device_name in self.target_device_names) or (peer_device_addr in self.target_device_addrs):
            self.connection_is_in_progress = True
            err_code = ble_driver.sd_ble_gap_connect(gap_event.params.adv_report.peer_addr,
                                                     self.scan_params,
                                                     self.conn_params)

            if err_code != ble_driver.NRF_SUCCESS:
                raise Exception("Failed sd_ble_gap_connect. Err_code {:02X}".format(err_code))


    def ble_evt_handler(self, ble_event):
        if ble_event is None: return

        evt_id = ble_event.header.evt_id

        for handler in self.ble_evt_handlers:
            handler(ble_event)

        if evt_id == ble_driver.BLE_GAP_EVT_CONNECTED:
            self.evts_q.put('connected')
            self.connection_handle          = ble_event.evt.gap_evt.conn_handle
            self.connection_is_in_progress  = False

        elif evt_id == ble_driver.BLE_GAP_EVT_DISCONNECTED:
            self.evts_q.put('disconnected')
            self.connection_handle = ble_driver.BLE_CONN_HANDLE_INVALID

        elif evt_id == ble_driver.BLE_GAP_EVT_ADV_REPORT:
            self.on_gap_evt_adv_report(ble_event.evt.gap_evt)

        elif evt_id == ble_driver.BLE_GATTS_EVT_SYS_ATTR_MISSING:
            ble_driver.sd_ble_gatts_sys_attr_set(self.connection_handle, None, 0, 0)

        elif evt_id == ble_driver.BLE_EVT_TX_COMPLETE:
            self.evts_q.put('tx_complete')

        elif evt_id == ble_driver.BLE_GATTC_EVT_WRITE_RSP:
            self.evts_q.put('gattc_write_rsp')


class DfuTransportBle(DfuTransport):

    DATA_PACKET_SIZE    = 20
    DEFAULT_TIMEOUT     = 20

    DFU_SERV_UUID = [0x23, 0xD1, 0xBC, 0xEA, 0x5F, 0x78, 0x23, 0x15,
                     0xDE, 0xEF, 0x12, 0x12, 0x00, 0x00, 0x00, 0x00]

    DFU_CHAR_UUID = {
        'ControlPoint'          : 0x1531,
        'DataPoint'             : 0x1532,
    }

    OP_CODE = {
        'CreateObject'          : 0x01,
        'SetPRN'                : 0x02,
        'CalcChecSum'           : 0x03,
        'Execute'               : 0x04,
        'ReadObject'            : 0x05,
        'ReadObjectInfo'        : 0x06,
        'Response'              : 0x60,
    }

    RES_CODE = {
        'InvalidCode'           : 0x00,
        'Success'               : 0x01,
        'NotSupported'          : 0x02,
        'InvParam'              : 0x03,
        'InsufficientResources' : 0x04,
        'InvObject'             : 0x05,
        'InvSignature'          : 0x06,
        'UnsupportedType'       : 0x07,
        'OperationFailed'       : 0x0A,
    }

    def __init__(self, serial_port, target_device_name=None, target_device_addr=None, baud_rate=115200):
        super(DfuTransportBle, self).__init__()
        self.baud_rate          = baud_rate
        self.serial_port        = serial_port
        self.target_device_name = target_device_name
        self.target_device_addr = target_device_addr
        self.ble_adapter        = None
        self.notifications_q    = Queue.Queue()


    def open(self):
        if self.ble_adapter:
            raise Exception('Already opened')

        super(DfuTransportBle, self).open()
        self.ble_adapter = BleAdapter(serial_port=self.serial_port, baud_rate=self.baud_rate)
        self.ble_adapter.add_ble_evt_handler(self.__ble_evt_handler)
        self.ble_adapter.vs_uuid_add(DfuTransportBle.DFU_SERV_UUID)

        self.ble_adapter.set_conn_targets(target_device_name=self.target_device_name,
                                          target_device_addr=self.target_device_addr)
        self.ble_adapter.start_scan()
        self.ble_adapter.wait_for_event('connected')

        self.ble_adapter.db_discovery.start_service_discovery()

        # Enable control point
        handle = self.ble_adapter.db_discovery.get_cccd_handle_from_uuid(DfuTransportBle.DFU_CHAR_UUID['ControlPoint'])
        if handle == 0:
            raise Exception('Characteristic not found')
        self.ble_adapter.enable_notification(handle)
        self.ble_adapter.wait_for_event('gattc_write_rsp')


    def close(self):
        if self.ble_adapter == None:
            raise Exception('Already closed')

        super(DfuTransportBle, self).close()
        self.ble_adapter.close()
        self.ble_adapter = None


    def send_init_packet(self, init_packet):
        response    = self.__read_command_info()
        with open(init_packet, 'rb') as f:
            data    = f.read()
            if len(data) > response['max_size']:
                raise Exception('Init command too long')

            self.__create_command(len(data))
            self.__stream_data(data=data)
            self.__execute()


    def send_firmware(self, firmware):
        response    = self.__read_data_info()
        object_size = response['max_size']
        hex_size    = os.path.getsize(firmware)

        with open(firmware, 'rb') as f:
            crc = 0
            for i in range(0, hex_size, object_size):
                data    = f.read(object_size)
                self.__create_data(len(data))
                crc     = self.__stream_data(data=data, crc=crc, offset=i)
                self.__execute()


    def __create_command(self, size):
        self.__create_object(0x01, size)


    def __create_data(self, size):
        self.__create_object(0x02, size)


    def __create_object(self, object_type, size):
        self.__write_control_point([DfuTransportBle.OP_CODE['CreateObject'], object_type] + map(ord, struct.pack('<L', size)))
        self.__get_response(DfuTransportBle.OP_CODE['CreateObject'])


    def __calculate_checksum(self):
        self.__write_control_point([DfuTransportBle.OP_CODE['CalcChecSum']])

        result                              = self.__get_response(DfuTransportBle.OP_CODE['CalcChecSum'])
        (result['offset'], result['crc'])   = struct.unpack('<II', bytearray(result.pop('args')))

        return result


    def __execute(self):
        self.__write_control_point([DfuTransportBle.OP_CODE['Execute']])
        self.__get_response(executed_operation=DfuTransportBle.OP_CODE['Execute'])


    def __read_command_info(self):
        return self.__read_object_info(0x01)


    def __read_data_info(self):
        return self.__read_object_info(0x02)


    def __read_object_info(self, request_type):
        self.__write_control_point([DfuTransportBle.OP_CODE['ReadObjectInfo'], request_type])
        result  = self.__get_response(DfuTransportBle.OP_CODE['ReadObjectInfo'])

        (result['max_size'], result['offset'], result['crc']) = struct.unpack('<III',
                                                                              bytearray(result.pop('args')))
        return result


    def __stream_data(self, data, crc=0, offset=0):
        for i in range(0, len(data), DfuTransportBle.DATA_PACKET_SIZE):
            to_transmit     = data[i:i + DfuTransportBle.DATA_PACKET_SIZE]
            self.__write_data_point(map(ord, to_transmit))
            crc     = binascii.crc32(to_transmit, crc) & 0xFFFFFFFF
            offset += len(to_transmit)

        response = self.__calculate_checksum()
        logger.debug("CRC Expected: {} Recieved: {}".format(crc, response['crc']))
        logger.debug("Offset Expected: {} Recieved: {}".format(offset, response['offset']))
        if (crc != response['crc']):
            raise Exception('Failed crc validation. Expected: {} Recieved: {}.'.format(crc, response['crc']))
        if (offset != response['offset']):
            raise Exception('Failed offset validation. Expected: {} Recieved: {}.'.format(offset, response['offset']))

        return crc


    def __write_data_point(self, data): 
        logger.debug("Write to Data Point {}".format(data))

        handle = self.ble_adapter.db_discovery.get_char_value_handle_from_uuid(DfuTransportBle.DFU_CHAR_UUID['DataPoint'])
        if handle == 0:
            raise Exception('Invalid Handle')

        self.ble_adapter._gattc_write_cmd(data, handle)
        self.ble_adapter.wait_for_event('tx_complete')


    def __write_control_point(self, data):
        logger.debug("Write to Control Point {}".format(data))

        handle = self.ble_adapter.db_discovery.get_char_value_handle_from_uuid(DfuTransportBle.DFU_CHAR_UUID['ControlPoint'])
        if handle == 0:
            raise Exception('Invalid Handle')

        self.ble_adapter._gattc_write(data, handle)
        self.ble_adapter.wait_for_event('gattc_write_rsp')


    def __get_response(self, executed_operation):
        def get_dict_key(dictionary, value):
            return next((key for key, val in dictionary.items() if val == value), None)
        try:
            resp = self.notifications_q.get(timeout=DfuTransportBle.DEFAULT_TIMEOUT)

        except Queue.Empty:
            raise Exception('Timeout: operation - {}'.format(get_dict_key(DfuTransportBle.OP_CODE, executed_operation)))

        else:
            if resp[0] != DfuTransportBle.OP_CODE['Response']:
                raise Exception('Unexpected DfuTransportBle.OP_CODE 0x{:02X}'.format(resp[0]))

            if resp[1] != executed_operation:
                raise Exception('Unexpected executed operation code.\n' \
                              + 'Expected: 0x{:02X} Received: 0x{:02X}'.format(executed_operation, resp[1]))

            if resp[2] != DfuTransportBle.RES_CODE['Success']:
                raise Exception('Invalid response code {}'.format(get_dict_key(DfuTransportBle.RES_CODE, resp[2])))

            return {'args'  : resp[3:]}


    def __ble_evt_handler(self, ble_event):
        if ble_event.header.evt_id == ble_driver.BLE_GATTC_EVT_HVX:
            if ble_event.evt.gattc_evt.gatt_status != ble_driver.NRF_SUCCESS:
                raise Exception('Error. Handle value notification failed.\n' \
                              + 'Gatt status error code 0x{:X}'.format(ble_event.evt.gattc_evt.gatt_status))

            a = util.uint8_array_to_list(ble_event.evt.gattc_evt.params.hvx.data,
                                         ble_event.evt.gattc_evt.params.hvx.len)
            self.notifications_q.put(a)
            logger.debug("HVX Notification {}".format(a))
