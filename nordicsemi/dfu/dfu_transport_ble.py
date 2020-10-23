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
import time
import wrapt
import queue
import struct
import logging
import binascii

from nordicsemi.dfu.dfu_transport   import DfuTransport, DfuEvent
from pc_ble_driver_py.exceptions    import NordicSemiException, IllegalStateException
from pc_ble_driver_py.ble_driver    import BLEDriver, BLEDriverObserver, BLEEnableParams, BLEUUIDBase, BLEGapSecKDist, BLEGapSecParams, \
    BLEGapIOCaps, BLEUUID, BLEAdvData, BLEGapConnParams, NordicSemiErrorCheck, BLEGapSecStatus, driver
from pc_ble_driver_py.ble_driver    import ATT_MTU_DEFAULT, BLEConfig, BLEConfigConnGatt, BLEConfigConnGap
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

    BASE_UUID = BLEUUIDBase([0x8E, 0xC9, 0x00, 0x00, 0xF3, 0x15, 0x4F, 0x60,
                             0x9F, 0xB8, 0x83, 0x88, 0x30, 0xDA, 0xEA, 0x50])

    # Buttonless characteristics
    BLE_DFU_BUTTONLESS_CHAR_UUID        = BLEUUID(0x0003, BASE_UUID)
    BLE_DFU_BUTTONLESS_BONDED_CHAR_UUID = BLEUUID(0x0004, BASE_UUID)
    SERVICE_CHANGED_UUID                = BLEUUID(0x2A05)

    # Bootloader characteristics
    CP_UUID     = BLEUUID(0x0001, BASE_UUID)
    DP_UUID     = BLEUUID(0x0002, BASE_UUID)

    CONNECTION_ATTEMPTS   = 3
    ERROR_CODE_POS        = 2
    LOCAL_ATT_MTU         = 247

    def __init__(self, adapter, bonded=False, keyset=None):
        super().__init__()

        self.evt_sync           = EvtSync(['connected', 'disconnected', 'sec_params',
                                           'auth_status', 'conn_sec_update'])
        self.conn_handle        = None
        self.adapter            = adapter
        self.bonded             = bonded
        self.keyset             = keyset
        self.notifications_q    = queue.Queue()
        self.indication_q       = queue.Queue()
        self.att_mtu            = ATT_MTU_DEFAULT
        self.packet_size        = self.att_mtu - 3
        self.adapter.observer_register(self)
        self.adapter.driver.observer_register(self)

    def open(self):
        self.adapter.driver.open()

        assert nrf_sd_ble_api_ver in [2, 5]

        if nrf_sd_ble_api_ver == 2:
            self.adapter.driver.ble_enable(
                BLEEnableParams(
                    vs_uuid_count = 10,
                    service_changed = True,
                    periph_conn_count = 0,
                    central_conn_count = 1,
                    central_sec_count = 1,
                )
            )

        if nrf_sd_ble_api_ver == 5:
            self.adapter.driver.ble_cfg_set(
                BLEConfig.conn_gatt,
                BLEConfigConnGatt(att_mtu=DFUAdapter.LOCAL_ATT_MTU),
            )
            self.adapter.driver.ble_cfg_set(
                BLEConfig.conn_gap,
                BLEConfigConnGap(event_length=5))  # Event length 5 is required for max data length
            self.adapter.driver.ble_enable()

        self.adapter.driver.ble_vs_uuid_add(DFUAdapter.BASE_UUID)

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

    def connect(self, target_device_name, target_device_addr):
        """ Connect to Bootloader or Application with Buttonless Service.

        Args:
            target_device_name (str): Device name to scan for.
            target_device_addr (str): Device addr to scan for.
        """
        self.target_device_name = target_device_name
        self.target_device_addr = target_device_addr

        logger.info('BLE: Scanning for {}'.format(self.target_device_name))
        self.adapter.driver.ble_gap_scan_start()
        self.verify_stable_connection()
        if self.conn_handle is None:
            raise NordicSemiException('Timeout. Target device not found.')

        logger.info('BLE: Service Discovery')
        self.adapter.service_discovery(conn_handle=self.conn_handle)

        # Check if connected peer has Buttonless service.
        if self.adapter.db_conns[self.conn_handle].get_cccd_handle(DFUAdapter.BLE_DFU_BUTTONLESS_CHAR_UUID):
            self.jump_from_buttonless_mode_to_bootloader(DFUAdapter.BLE_DFU_BUTTONLESS_CHAR_UUID)
        elif self.adapter.db_conns[self.conn_handle].get_cccd_handle(DFUAdapter.BLE_DFU_BUTTONLESS_BONDED_CHAR_UUID):
            self.jump_from_buttonless_mode_to_bootloader(DFUAdapter.BLE_DFU_BUTTONLESS_BONDED_CHAR_UUID)

        if self.bonded:
            # For combined Updates with bonds enabled, re-encryption is needed
            self.encrypt()

        if nrf_sd_ble_api_ver >= 3:
            if DFUAdapter.LOCAL_ATT_MTU > ATT_MTU_DEFAULT:
                logger.info('BLE: Enabling longer ATT MTUs')
                self.att_mtu = self.adapter.att_mtu_exchange(self.conn_handle, DFUAdapter.LOCAL_ATT_MTU)

                logger.info('BLE: Enabling longer Data Length')
                max_data_length = 251  # Max data length for SD v5
                data_length = self.att_mtu + 4  # ATT PDU overhead is 4
                if data_length > max_data_length:
                    data_length = max_data_length
                self.adapter.data_length_update(self.conn_handle, data_length)
            else:
                logger.info('BLE: Using default ATT MTU')

        logger.debug('BLE: Enabling Notifications')
        self.adapter.enable_notification(conn_handle=self.conn_handle, uuid=DFUAdapter.CP_UUID)
        return self.target_device_name, self.target_device_addr

    def jump_from_buttonless_mode_to_bootloader(self, buttonless_uuid):
        """ Function for going to bootloader mode from application with
         buttonless service. It supports both bonded and unbonded
         buttonless characteristics.

        Args:
            buttonless_uuid: UUID of discovered buttonless characteristic.

        """
        if buttonless_uuid == DFUAdapter.BLE_DFU_BUTTONLESS_BONDED_CHAR_UUID:
            logger.info("Bonded Buttonless characteristic discovered -> Bond")
            self.bond()
        else:
            logger.info("Un-bonded Buttonless characteristic discovered -> Increment target device addr")
            self.target_device_addr = "{:X}".format(int(self.target_device_addr, 16) + 1)
            self.target_device_addr_type.addr[-1] += 1

        # Enable indication for Buttonless DFU Service
        self.adapter.enable_indication(self.conn_handle, buttonless_uuid)

        # Enable indication for Service changed Service, if present.
        if self.adapter.db_conns[self.conn_handle].get_char_handle(DFUAdapter.SERVICE_CHANGED_UUID):
            self.adapter.enable_indication(self.conn_handle, DFUAdapter.SERVICE_CHANGED_UUID)

        # Enter DFU mode
        self.adapter.write_req(self.conn_handle, buttonless_uuid, [0x01])
        response = self.indication_q.get(timeout=DfuTransportBle.DEFAULT_TIMEOUT)
        if response[DFUAdapter.ERROR_CODE_POS] != 0x01:
            raise Exception("Error - Unexpected response")

        # Wait for buttonless peer to disconnect
        self.evt_sync.wait('disconnected')

        # Reconnect
        self.target_device_name = None
        self.adapter.driver.ble_gap_scan_start()
        self.verify_stable_connection()
        if self.conn_handle is None:
            raise NordicSemiException('Timeout. Target device not found.')
        logger.info('BLE: Connected to target')

        logger.debug('BLE: Service Discovery')
        self.adapter.service_discovery(conn_handle=self.conn_handle)

    def verify_stable_connection(self):
        """ Verify connection event, and verify that unexpected disconnect
         events are not received.

        Returns:
            True if connected, else False.

        """
        self.conn_handle = self.evt_sync.wait('connected')
        if self.conn_handle is not None:
            retries = DFUAdapter.CONNECTION_ATTEMPTS
            while retries:
                if self.evt_sync.wait('disconnected', timeout=1) is None:
                    break

                logger.warning("Received unexpected disconnect event, "
                               "trying to re-connect to: {}".format(self.target_device_addr))
                time.sleep(1)

                self.adapter.connect(address=self.target_device_addr_type,
                                     conn_params=self.conn_params,
                                     tag=1)
                self.conn_handle = self.evt_sync.wait('connected')
                retries -= 1
            else:
                if self.evt_sync.wait('disconnected', timeout=1) is not None:
                    raise Exception("Failure - Connection failed due to 0x3e")

            logger.info("Successfully Connected")
            return

        self.adapter.driver.ble_gap_scan_stop()
        raise Exception("Connection Failure - Device not found!")

    def setup_keyset(self):
        """ Setup keyset structure.

        """
        self.keyset = driver.ble_gap_sec_keyset_t()

        self.id_key_own = driver.ble_gap_id_key_t()
        self.id_key_peer = driver.ble_gap_id_key_t()

        self.enc_key_own = driver.ble_gap_enc_key_t()
        self.enc_key_peer = driver.ble_gap_enc_key_t()

        self.sign_info_own = driver.ble_gap_sign_info_t()
        self.sign_info_peer = driver.ble_gap_sign_info_t()

        self.lesc_pk_own = driver.ble_gap_lesc_p256_pk_t()
        self.lesc_pk_peer = driver.ble_gap_lesc_p256_pk_t()

        self.keyset.keys_own.p_enc_key   = self.enc_key_own
        self.keyset.keys_own.p_id_key    = self.id_key_own
        self.keyset.keys_own.p_sign_key  = self.sign_info_own
        self.keyset.keys_own.p_pk        = self.lesc_pk_own
        self.keyset.keys_peer.p_enc_key  = self.enc_key_peer
        self.keyset.keys_peer.p_id_key   = self.id_key_peer
        self.keyset.keys_peer.p_sign_key = self.sign_info_peer
        self.keyset.keys_peer.p_pk       = self.lesc_pk_peer

    def setup_sec_params(self):
        """ Setup Security parameters.

        """

        self.kdist_own = BLEGapSecKDist(enc=True,
                                        id=True,
                                        sign=False,
                                        link=False)
        self.kdist_peer = BLEGapSecKDist(enc=True,
                                         id=True,
                                         sign=False,
                                         link=False)
        self.sec_params = BLEGapSecParams(bond=True,
                                          mitm=False,
                                          lesc=False,
                                          keypress=False,
                                          io_caps=BLEGapIOCaps.none,
                                          oob=False,
                                          min_key_size=7,
                                          max_key_size=16,
                                          kdist_own=self.kdist_own,
                                          kdist_peer=self.kdist_peer)

    def bond(self):
        """ Bond to Application with Buttonless Service.

        """
        self.bonded = True
        self.setup_sec_params()
        self.setup_keyset()

        self.adapter.driver.ble_gap_authenticate(self.conn_handle, self.sec_params)
        self.evt_sync.wait(evt="sec_params")
        self.adapter.driver.ble_gap_sec_params_reply(self.conn_handle,
                                                     BLEGapSecStatus.success,
                                                     None,
                                                     self.keyset,
                                                     None)

        result = self.evt_sync.wait(evt="auth_status")
        if result != BLEGapSecStatus.success:
            raise NordicSemiException("Auth Status returned error code: {}".format(result))

    def encrypt(self):
        """ Re-encrypt to bootloader.

        """
        logger.info("Re-encryption to bootloader")
        self.adapter.driver.ble_gap_encrypt(self.conn_handle,
                                            self.keyset.keys_peer.p_enc_key.master_id,
                                            self.keyset.keys_peer.p_enc_key.enc_info)
        self.evt_sync.wait('conn_sec_update')

    def write_control_point(self, data):
        self.adapter.write_req(self.conn_handle, DFUAdapter.CP_UUID, data)

    def write_data_point(self, data):
        self.adapter.write_cmd(self.conn_handle, DFUAdapter.DP_UUID, data)

    def on_gap_evt_sec_params_request(self, ble_driver, conn_handle, peer_params):
        logger.info("Got sec params req")
        self.evt_sync.notify(evt='sec_params', data=conn_handle)

    def on_gap_evt_auth_status(self, ble_driver, conn_handle, auth_status):
        logger.info("Got auth status:{}".format(auth_status))
        self.evt_sync.notify(evt='auth_status', data=auth_status)

    def on_gap_evt_conn_sec_update(self, ble_driver, conn_handle):
        logger.info("Got Conn sec update")
        self.evt_sync.notify(evt='conn_sec_update', data=conn_handle)

    def on_gap_evt_connected(self, ble_driver, conn_handle, peer_addr, role, conn_params):
        self.evt_sync.notify(evt = 'connected', data = conn_handle)
        logger.info('BLE: Connected to {}'.format(peer_addr.addr))

    def on_gap_evt_disconnected(self, ble_driver, conn_handle, reason):
        self.evt_sync.notify(evt = 'disconnected', data = conn_handle)
        self.conn_handle = None
        logger.info('BLE: Disconnected with reason: {}'.format(reason))

    def on_gap_evt_adv_report(self, ble_driver, conn_handle, peer_addr, rssi, adv_type, adv_data):
        dev_name_list = []
        if BLEAdvData.Types.complete_local_name in adv_data.records:
            dev_name_list = adv_data.records[BLEAdvData.Types.complete_local_name]

        elif BLEAdvData.Types.short_local_name in adv_data.records:
            dev_name_list = adv_data.records[BLEAdvData.Types.short_local_name]

        dev_name        = "".join(chr(e) for e in dev_name_list)
        address_string  = "".join("{0:02X}".format(b) for b in peer_addr.addr)
        logger.info('Received advertisement report, address: 0x{}, device_name: {}'.format(address_string, dev_name))

        if (dev_name == self.target_device_name) or (address_string == self.target_device_addr):
            self.conn_params = BLEGapConnParams(min_conn_interval_ms = 7.5,
                                                max_conn_interval_ms = 30,
                                                conn_sup_timeout_ms  = 4000,
                                                slave_latency        = 0)
            logger.info('BLE: Found target advertiser, address: 0x{}, name: {}'.format(address_string, dev_name))
            logger.info('BLE: Connecting to 0x{}'.format(address_string))
            # Connect must specify tag=1 to enable the settings
            # set with BLEConfigConnGatt (that implicitly operates
            # on connections with tag 1) to allow for larger MTU.
            self.adapter.connect(address=peer_addr,
                                 conn_params=self.conn_params,
                                 tag=1)
            # store the address for subsequent connections
            self.target_device_addr = address_string
            self.target_device_addr_type = peer_addr

    def on_notification(self, ble_adapter, conn_handle, uuid, data):
        if self.conn_handle         != conn_handle: return
        if DFUAdapter.CP_UUID.value != uuid.value:
            return
        self.notifications_q.put(data)

    def on_indication(self, ble_adapter, conn_handle, uuid, data):
        if self.conn_handle         != conn_handle: return
        if DFUAdapter.BLE_DFU_BUTTONLESS_BONDED_CHAR_UUID.value != uuid.value and \
           DFUAdapter.BLE_DFU_BUTTONLESS_CHAR_UUID.value != uuid.value:
            return
        self.indication_q.put(data)

    def on_gattc_evt_exchange_mtu_rsp(self, ble_driver, conn_handle, *, status, att_mtu):
        logger.info('ATT MTU exchanged: conn_handle={} att_mtu={}'.format(conn_handle, att_mtu))
        self.att_mtu = att_mtu
        self.packet_size = att_mtu - 3


class DfuBLEDriver(BLEDriver):
    def __init__(self, serial_port, baud_rate=115200, auto_flash=False):
        super().__init__(serial_port, baud_rate)

    @NordicSemiErrorCheck
    @wrapt.synchronized(BLEDriver.api_lock)
    def ble_gap_sec_params_reply(self, conn_handle, sec_status, sec_params, own_keys, peer_keys):
        assert isinstance(sec_status, BLEGapSecStatus), 'Invalid argument type'
        assert sec_params is None or isinstance(sec_params, BLEGapSecParams), 'Invalid argument type'
        assert peer_keys is None, 'NOT IMPLEMENTED'

        return driver.sd_ble_gap_sec_params_reply(self.rpc_adapter,
                                                  conn_handle,
                                                  sec_status.value,
                                                  sec_params.to_c() if sec_params else None,
                                                  own_keys)


class DfuTransportBle(DfuTransport):

    DEFAULT_TIMEOUT     = 20
    RETRIES_NUMBER      = 3

    def __init__(self,
                 serial_port,
                 att_mtu,
                 target_device_name=None,
                 target_device_addr=None,
                 baud_rate=1000000,
                 prn=0):
        super().__init__()
        DFUAdapter.LOCAL_ATT_MTU = att_mtu
        self.baud_rate          = baud_rate
        self.serial_port        = serial_port
        self.att_mtu            = att_mtu
        self.target_device_name = target_device_name
        self.target_device_addr = target_device_addr
        self.dfu_adapter        = None
        self.prn                = prn

        self.bonded             = False
        self.keyset             = None

    def open(self):
        if self.dfu_adapter:
            raise IllegalStateException('DFU Adapter is already open')

        super().open()
        driver           = DfuBLEDriver(serial_port = self.serial_port,
                                        baud_rate   = self.baud_rate)
        adapter          = BLEAdapter(driver)
        self.dfu_adapter = DFUAdapter(adapter=adapter, bonded=self.bonded, keyset=self.keyset)
        self.dfu_adapter.open()
        self.target_device_name, self.target_device_addr = self.dfu_adapter.connect(
                                                        target_device_name = self.target_device_name,
                                                        target_device_addr = self.target_device_addr)
        self.__set_prn()

    def close(self):

        # Get bonded status and BLE keyset from DfuAdapter
        self.bonded = self.dfu_adapter.bonded
        self.keyset = self.dfu_adapter.keyset

        if not self.dfu_adapter:
            raise IllegalStateException('DFU Adapter is already closed')
        super().close()
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
        self.dfu_adapter.write_control_point([DfuTransportBle.OP_CODE['SetPRN']] + list(struct.pack('<H', self.prn)))
        self.__get_response(DfuTransportBle.OP_CODE['SetPRN'])

    def __create_command(self, size):
        self.__create_object(0x01, size)

    def __create_data(self, size):
        self.__create_object(0x02, size)

    def __create_object(self, object_type, size):
        self.dfu_adapter.write_control_point([DfuTransportBle.OP_CODE['CreateObject'], object_type]\
                                            + list(struct.pack('<L', size)))
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
                                + 'Expected: {} Received: {}.'.format(crc, response['crc']))
            if (offset != response['offset']):
                raise ValidationException('Failed offset validation.\n'\
                                + 'Expected: {} Received: {}.'.format(offset, response['offset']))

        current_pnr = 0
        for i in range(0, len(data), self.dfu_adapter.packet_size):
            to_transmit     = data[i:i + self.dfu_adapter.packet_size]
            self.dfu_adapter.write_data_point(list(to_transmit))
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
            return next((key for key, val in list(dictionary.items()) if val == value), None)

        try:
            resp = self.dfu_adapter.notifications_q.get(timeout=DfuTransportBle.DEFAULT_TIMEOUT)
        except queue.Empty:
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
