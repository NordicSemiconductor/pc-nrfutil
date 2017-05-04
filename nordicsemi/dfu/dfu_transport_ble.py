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

# Python standard library
import os
import sys
import Queue
import struct
import logging
import binascii

from nordicsemi.dfu.dfu_transport   import DfuTransport, DfuEvent
from pc_ble_driver_py.exceptions    import NordicSemiException, IllegalStateException
from pc_ble_driver_py.ble_driver    import BLEDriver, BLEDriverObserver, BLEEnableParams, BLEUUIDBase, BLEUUID, BLEAdvData, BLEGapConnParams, NordicSemiException
from pc_ble_driver_py.ble_driver    import ATT_MTU_DEFAULT
from pc_ble_driver_py.ble_adapter   import BLEAdapter, BLEAdapterObserver, EvtSync

logger  = logging.getLogger(__name__)
#logger.setLevel(logging.DEBUG)

from pc_ble_driver_py import config
global nrf_sd_ble_api_ver
nrf_sd_ble_api_ver = config.sd_api_ver_get()


class ValidationException(NordicSemiException):
    """"
    Exception used when validation failed
    """
    pass



class DFUAdapter(BLEDriverObserver, BLEAdapterObserver):
    BASE_UUID   = BLEUUIDBase([0x8E, 0xC9, 0x00, 0x00, 0xF3, 0x15, 0x4F, 0x60,
                               0x9F, 0xB8, 0x83, 0x88, 0x30, 0xDA, 0xEA, 0x50])
    CP_UUID     = BLEUUID(0x0001, BASE_UUID)
    DP_UUID     = BLEUUID(0x0002, BASE_UUID)

    LOCAL_ATT_MTU     = 23

    def __init__(self, adapter):
        super(DFUAdapter, self).__init__()
        self.evt_sync           = EvtSync(['connected', 'disconnected'])
        self.conn_handle        = None
        self.adapter            = adapter
        self.notifications_q    = Queue.Queue()
        self.adapter.observer_register(self)
        self.adapter.driver.observer_register(self)


    def open(self):
        self.adapter.driver.open()
        ble_enable_params = BLEEnableParams(vs_uuid_count      = 10,
                                            service_changed    = False,
                                            periph_conn_count  = 0,
                                            central_conn_count = 1,
                                            central_sec_count  = 1)
        if nrf_sd_ble_api_ver >= 3:
            logger.info("\nBLE: ble_enable with local ATT MTU: {}".format(DFUAdapter.LOCAL_ATT_MTU))
            ble_enable_params.att_mtu = DFUAdapter.LOCAL_ATT_MTU

        self.adapter.driver.ble_enable(ble_enable_params)
        self.adapter.driver.ble_vs_uuid_add(DFUAdapter.BASE_UUID)

    def connect(self, target_device_name, target_device_addr):
        self.target_device_name = target_device_name
        self.target_device_addr = target_device_addr
        logger.debug('BLE: connect: target address: 0x{}'.format(self.target_device_addr))
        logger.info('BLE: Scanning...')
        self.adapter.driver.ble_gap_scan_start()
        self.conn_handle = self.evt_sync.wait('connected')
        if self.conn_handle is None:
            raise NordicSemiException('Timeout. Target device not found.')
        logger.info('BLE: Connected to target')
        logger.debug('BLE: Service Discovery')

        if nrf_sd_ble_api_ver >= 3:
            if DFUAdapter.LOCAL_ATT_MTU > ATT_MTU_DEFAULT:
                logger.info('BLE: Enabling longer ATT MTUs')
                self.att_mtu = self.adapter.att_mtu_exchange(self.conn_handle)
                logger.info('BLE: ATT MTU: {}'.format(self.att_mtu))
            else:
                logger.info('BLE: Using default ATT MTU')

        self.adapter.service_discovery(conn_handle=self.conn_handle)
        logger.debug('BLE: Enabling Notifications')
        self.adapter.enable_notification(conn_handle=self.conn_handle, uuid=DFUAdapter.CP_UUID)
        return self.target_device_name, self.target_device_addr

    def close(self):
        if self.conn_handle is not None:
            logger.info('BLE: Disconnecting from target')
            self.adapter.disconnect(self.conn_handle)
            self.evt_sync.wait('disconnected')
        self.conn_handle    = None
        self.evt_sync       = None
        self.adapter.observer_unregister(self)
        self.adapter.driver.observer_unregister(self)
        self.adapter.driver.close()


    def write_control_point(self, data):
        self.adapter.write_req(self.conn_handle, DFUAdapter.CP_UUID, data)


    def write_data_point(self, data):
        self.adapter.write_cmd(self.conn_handle, DFUAdapter.DP_UUID, data)


    def on_gap_evt_connected(self, ble_driver, conn_handle, peer_addr, role, conn_params):
        self.evt_sync.notify(evt = 'connected', data = conn_handle)
        logger.info('BLE: Connected to {}'.format(peer_addr))


    def on_gap_evt_disconnected(self, ble_driver, conn_handle, reason):
        self.evt_sync.notify(evt = 'disconnected', data = conn_handle)
        self.conn_handle = None
        logger.info('BLE: Disconnected')


    def on_gap_evt_adv_report(self, ble_driver, conn_handle, peer_addr, rssi, adv_type, adv_data):
        dev_name_list = []
        if BLEAdvData.Types.complete_local_name in adv_data.records:
            dev_name_list = adv_data.records[BLEAdvData.Types.complete_local_name]

        elif BLEAdvData.Types.short_local_name in adv_data.records:
            dev_name_list = adv_data.records[BLEAdvData.Types.short_local_name]

        dev_name        = "".join(chr(e) for e in dev_name_list)
        address_string  = "".join("{0:02X}".format(b) for b in peer_addr.addr)
        logger.debug('Received advertisement report, address: 0x{}, device_name: {}'.format(address_string, dev_name))

        if (dev_name == self.target_device_name) or (address_string == self.target_device_addr):
            conn_params = BLEGapConnParams(min_conn_interval_ms = 15,
                                           max_conn_interval_ms = 30,
                                           conn_sup_timeout_ms  = 4000,
                                           slave_latency        = 0)
            logger.info('BLE: Found target advertiser, address: 0x{}, name: {}'.format(address_string, dev_name))
            logger.info('BLE: Connecting to 0x{}'.format(address_string))
            self.adapter.connect(address = peer_addr, conn_params = conn_params)
            # store the name and address for subsequent connections
            self.target_device_name = dev_name
            self.target_device_addr = address_string


    def on_notification(self, ble_adapter, conn_handle, uuid, data):
        if self.conn_handle         != conn_handle: return
        if DFUAdapter.CP_UUID.value != uuid.value:  return
        #logger.debug(data)
        self.notifications_q.put(data)


    def on_att_mtu_exchanged(self, ble_driver, conn_handle, att_mtu):
        logger.info('ATT MTU exchanged: conn_handle={} att_mtu={}'.format(conn_handle, att_mtu))


    def on_gattc_evt_exchange_mtu_rsp(self, ble_driver, conn_handle, **kwargs):
        logger.info('ATT MTU exchange response: conn_handle={}'.format(conn_handle))
    


class DfuTransportBle(DfuTransport):

    DATA_PACKET_SIZE    = 20
    DEFAULT_TIMEOUT     = 20
    RETRIES_NUMBER      = 3


    def __init__(self,
                 serial_port,
                 target_device_name=None,
                 target_device_addr=None,
                 baud_rate=115200,
                 prn=0):
        super(DfuTransportBle, self).__init__()
        self.baud_rate          = baud_rate
        self.serial_port        = serial_port
        self.target_device_name = target_device_name
        self.target_device_addr = target_device_addr
        self.dfu_adapter        = None
        self.prn                = prn

    def open(self):
        if self.dfu_adapter:
            raise IllegalStateException('DFU Adapter is already open')

        super(DfuTransportBle, self).open()
        driver           = BLEDriver(serial_port    = self.serial_port,
                                     baud_rate      = self.baud_rate)
        adapter          = BLEAdapter(driver)
        self.dfu_adapter = DFUAdapter(adapter       = adapter)
        self.dfu_adapter.open()
        self.target_device_name, self.target_device_addr = self.dfu_adapter.connect(
                                                        target_device_name = self.target_device_name,
                                                        target_device_addr = self.target_device_addr)
        self.__set_prn()

    def close(self):
        if not self.dfu_adapter:
            raise IllegalStateException('DFU Adapter is already closed')
        super(DfuTransportBle, self).close()
        self.dfu_adapter.close()
        self.dfu_adapter = None


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

        for r in range(DfuTransportBle.RETRIES_NUMBER):
            try:
                self.__create_command(len(init_packet))
                self.__stream_data(data=init_packet)
                self.__execute()
            except ValidationException:
                pass
            break
        else:
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
                response['crc']     = binascii.crc32(firmware[:response['offset']]) & 0xFFFFFFFF
                return

            if (remainder != 0) and (response['offset'] != len(firmware)):
                # Send rest of the page.
                try:
                    to_send             = firmware[response['offset'] : response['offset'] + response['max_size'] - remainder]
                    response['crc']     = self.__stream_data(data   = to_send,
                                                             crc    = response['crc'],
                                                             offset = response['offset'])
                    response['offset'] += len(to_send)
                except ValidationException:
                    # Remove corrupted data.
                    response['offset'] -= remainder
                    response['crc']     = binascii.crc32(firmware[:response['offset']]) & 0xFFFFFFFF
                    return

            self.__execute()
            self._send_event(event_type=DfuEvent.PROGRESS_EVENT, progress=response['offset'])

        response = self.__select_data()
        try_to_recover()

        for i in range(response['offset'], len(firmware), response['max_size']):
            data = firmware[i:i+response['max_size']]
            for r in range(DfuTransportBle.RETRIES_NUMBER):
                try:
                    self.__create_data(len(data))
                    response['crc'] = self.__stream_data(data=data, crc=response['crc'], offset=i)
                    self.__execute()
                except ValidationException:
                    pass
                break
            else:
                raise NordicSemiException("Failed to send firmware")
            self._send_event(event_type=DfuEvent.PROGRESS_EVENT, progress=len(data))

    
    def __set_prn(self):
        logger.debug("BLE: Set Packet Receipt Notification {}".format(self.prn))
        self.dfu_adapter.write_control_point([DfuTransportBle.OP_CODE['SetPRN']] + map(ord, struct.pack('<H', self.prn)))
        self.__get_response(DfuTransportBle.OP_CODE['SetPRN'])
    
    def __create_command(self, size):
        self.__create_object(0x01, size)


    def __create_data(self, size):
        self.__create_object(0x02, size)


    def __create_object(self, object_type, size):
        self.dfu_adapter.write_control_point([DfuTransportBle.OP_CODE['CreateObject'], object_type]\
                                            + map(ord, struct.pack('<L', size)))
        self.__get_response(DfuTransportBle.OP_CODE['CreateObject'])


    def __calculate_checksum(self):
        self.dfu_adapter.write_control_point([DfuTransportBle.OP_CODE['CalcChecSum']])
        response = self.__get_response(DfuTransportBle.OP_CODE['CalcChecSum'])

        (offset, crc) = struct.unpack('<II', bytearray(response))
        return {'offset': offset, 'crc': crc}


    def __execute(self):
        self.dfu_adapter.write_control_point([DfuTransportBle.OP_CODE['Execute']])
        self.__get_response(DfuTransportBle.OP_CODE['Execute'])


    def __select_command(self):
        return self.__select_object(0x01)


    def __select_data(self):
        return self.__select_object(0x02)


    def __select_object(self, object_type):
        logger.debug("BLE: Selecting Object: type:{}".format(object_type))
        self.dfu_adapter.write_control_point([DfuTransportBle.OP_CODE['ReadObject'], object_type])
        response = self.__get_response(DfuTransportBle.OP_CODE['ReadObject'])

        (max_size, offset, crc)= struct.unpack('<III', bytearray(response))
        logger.debug("BLE: Object selected: max_size:{} offset:{} crc:{}".format(max_size, offset, crc))
        return {'max_size': max_size, 'offset': offset, 'crc': crc}
    
    def __get_checksum_response(self):
        response = self.__get_response(DfuTransportBle.OP_CODE['CalcChecSum'])

        (offset, crc) = struct.unpack('<II', bytearray(response))
        return {'offset': offset, 'crc': crc}

    def __stream_data(self, data, crc=0, offset=0):
        logger.debug("BLE: Streaming Data: len:{0} offset:{1} crc:0x{2:08X}".format(len(data), offset, crc))
        def validate_crc():
            if (crc != response['crc']):
                raise ValidationException('Failed CRC validation.\n'\
                                + 'Expected: {} Recieved: {}.'.format(crc, response['crc']))
            if (offset != response['offset']):
                raise ValidationException('Failed offset validation.\n'\
                                + 'Expected: {} Recieved: {}.'.format(offset, response['offset']))
        
        current_pnr     = 0
        for i in range(0, len(data), DfuTransportBle.DATA_PACKET_SIZE):
            to_transmit     = data[i:i + DfuTransportBle.DATA_PACKET_SIZE]
            self.dfu_adapter.write_data_point(map(ord, to_transmit))
            crc     = binascii.crc32(to_transmit, crc) & 0xFFFFFFFF
            offset += len(to_transmit)
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
            return next((key for key, val in dictionary.items() if val == value), None)

        try:
            resp = self.dfu_adapter.notifications_q.get(timeout=DfuTransportBle.DEFAULT_TIMEOUT)
        except Queue.Empty:
            raise NordicSemiException('Timeout: operation - {}'.format(get_dict_key(DfuTransportBle.OP_CODE,
                                                                                    operation)))

        if resp[0] != DfuTransportBle.OP_CODE['Response']:
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
            raise NordicSemiException('Response Code {}'.format(get_dict_key(DfuTransport.RES_CODE, resp[2])))

