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
import queue
import logging

# Python 3rd party imports
import wrapt

from pc_ble_driver_py import config
from pc_ble_driver_py.exceptions import NordicSemiException, IllegalStateException
from pc_ble_driver_py.ble_adapter import BLEAdapter, BLEAdapterObserver, EvtSync
from pc_ble_driver_py.ble_driver import (
    ATT_MTU_DEFAULT,
    BLEAdvData,
    BLEConfig,
    BLEConfigConnGap,
    BLEConfigConnGatt,
    BLEDriver,
    BLEDriverObserver,
    BLEEnableParams,
    BLEGapConnParams,
    BLEGapIOCaps,
    BLEGapSecKDist,
    BLEGapSecParams,
    BLEGapSecStatus,
    BLEUUID,
    BLEUUIDBase,
    driver,
    NordicSemiErrorCheck,
)

# Local imports
from nordicsemi.dfu.dfu_transport import (
    DfuTransport,
    OperationResponseTimeoutError,
    OP_CODE,
)

global nrf_sd_ble_api_ver
nrf_sd_ble_api_ver = config.sd_api_ver_get()

logger = logging.getLogger(__name__)


class DFUAdapter(BLEDriverObserver, BLEAdapterObserver):
    # fmt: off
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
    # fmt: on

    def __init__(
        self,
        serial_port,
        baud_rate,
        bonded=False,
        keyset=None,
        local_att_mtu=LOCAL_ATT_MTU,
    ):
        super().__init__()

        self.evt_sync = EvtSync(
            [
                "connected",
                "disconnected",
                "sec_params",
                "auth_status",
                "conn_sec_update",
            ]
        )

        ble_driver = DfuBLEDriver(serial_port=serial_port, baud_rate=baud_rate)
        self.adapter = BLEAdapter(ble_driver)
        # fmt: off
        self.conn_handle        = None
        self.bonded             = bonded
        self.keyset             = keyset
        self.notifications_q    = queue.Queue()
        self.indication_q       = queue.Queue()
        self.att_mtu            = ATT_MTU_DEFAULT
        self.packet_size        = self.att_mtu - 3
        self.local_att_mtu = local_att_mtu
        # fmt: on
        self.adapter.observer_register(self)
        self.adapter.driver.observer_register(self)

    def open(self):
        self.adapter.driver.open()

        assert nrf_sd_ble_api_ver in [2, 5]

        if nrf_sd_ble_api_ver == 2:
            self.adapter.driver.ble_enable(
                BLEEnableParams(
                    vs_uuid_count=10,
                    service_changed=True,
                    periph_conn_count=0,
                    central_conn_count=1,
                    central_sec_count=1,
                )
            )

        if nrf_sd_ble_api_ver == 5:
            self.adapter.driver.ble_cfg_set(
                BLEConfig.conn_gatt, BLEConfigConnGatt(att_mtu=self.local_att_mtu),
            )
            self.adapter.driver.ble_cfg_set(
                BLEConfig.conn_gap, BLEConfigConnGap(event_length=5)
            )  # Event length 5 is required for max data length
            self.adapter.driver.ble_enable()

        self.adapter.driver.ble_vs_uuid_add(DFUAdapter.BASE_UUID)

    def close(self):
        if self.conn_handle is not None:
            logger.info("BLE: Disconnecting from target")
            self.adapter.disconnect(self.conn_handle)
            self.evt_sync.wait("disconnected")
        self.conn_handle = None
        self.evt_sync = None
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

        logger.info("BLE: Scanning for {}".format(self.target_device_name))
        self.adapter.driver.ble_gap_scan_start()
        self.verify_stable_connection()
        if self.conn_handle is None:
            raise NordicSemiException("Timeout. Target device not found.")

        logger.info("BLE: Service Discovery")
        self.adapter.service_discovery(conn_handle=self.conn_handle)

        # Check if connected peer has Buttonless service.
        if self.adapter.db_conns[self.conn_handle].get_cccd_handle(
            DFUAdapter.BLE_DFU_BUTTONLESS_CHAR_UUID
        ):
            self.jump_from_buttonless_mode_to_bootloader(
                DFUAdapter.BLE_DFU_BUTTONLESS_CHAR_UUID
            )
        elif self.adapter.db_conns[self.conn_handle].get_cccd_handle(
            DFUAdapter.BLE_DFU_BUTTONLESS_BONDED_CHAR_UUID
        ):
            self.jump_from_buttonless_mode_to_bootloader(
                DFUAdapter.BLE_DFU_BUTTONLESS_BONDED_CHAR_UUID
            )

        if self.bonded:
            # For combined Updates with bonds enabled, re-encryption is needed
            self.encrypt()

        if nrf_sd_ble_api_ver >= 3:
            if self.local_att_mtu > ATT_MTU_DEFAULT:
                logger.info("BLE: Enabling longer ATT MTUs")
                self.att_mtu = self.adapter.att_mtu_exchange(
                    self.conn_handle, self.local_att_mtu
                )

                logger.info("BLE: Enabling longer Data Length")
                max_data_length = 251  # Max data length for SD v5
                data_length = self.att_mtu + 4  # ATT PDU overhead is 4
                if data_length > max_data_length:
                    data_length = max_data_length
                self.adapter.data_length_update(self.conn_handle, data_length)
            else:
                logger.info("BLE: Using default ATT MTU")

        logger.debug("BLE: Enabling Notifications")
        self.adapter.enable_notification(
            conn_handle=self.conn_handle, uuid=DFUAdapter.CP_UUID
        )
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
            logger.info(
                "Un-bonded Buttonless characteristic discovered -> Increment target device addr"
            )
            self.target_device_addr = "{:X}".format(
                int(self.target_device_addr, 16) + 1
            )
            self.target_device_addr_type.addr[-1] += 1

        # Enable indication for Buttonless DFU Service
        self.adapter.enable_indication(self.conn_handle, buttonless_uuid)

        # Enable indication for Service changed Service, if present.
        if self.adapter.db_conns[self.conn_handle].get_char_handle(
            DFUAdapter.SERVICE_CHANGED_UUID
        ):
            self.adapter.enable_indication(
                self.conn_handle, DFUAdapter.SERVICE_CHANGED_UUID
            )

        # Enter DFU mode
        self.adapter.write_req(self.conn_handle, buttonless_uuid, [0x01])
        response = self.indication_q.get(timeout=DfuTransportBle.DEFAULT_TIMEOUT)
        if response[DFUAdapter.ERROR_CODE_POS] != 0x01:
            raise Exception("Error - Unexpected response")

        # Wait for buttonless peer to disconnect
        self.evt_sync.wait("disconnected")

        # Reconnect
        self.target_device_name = None
        self.adapter.driver.ble_gap_scan_start()
        self.verify_stable_connection()
        if self.conn_handle is None:
            raise NordicSemiException("Timeout. Target device not found.")
        logger.info("BLE: Connected to target")

        logger.debug("BLE: Service Discovery")
        self.adapter.service_discovery(conn_handle=self.conn_handle)

    def verify_stable_connection(self):
        """ Verify connection event, and verify that unexpected disconnect
         events are not received.

        Returns:
            True if connected, else False.

        """
        self.conn_handle = self.evt_sync.wait("connected")
        if self.conn_handle is not None:
            retries = DFUAdapter.CONNECTION_ATTEMPTS
            while retries:
                if self.evt_sync.wait("disconnected", timeout=1) is None:
                    break

                logger.warning(
                    "Received unexpected disconnect event, "
                    "trying to re-connect to: {}".format(self.target_device_addr)
                )
                time.sleep(1)

                self.adapter.connect(
                    address=self.target_device_addr_type, conn_params=self.conn_params
                )
                self.conn_handle = self.evt_sync.wait("connected")
                retries -= 1
            else:
                if self.evt_sync.wait("disconnected", timeout=1) is not None:
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

        self.keyset.keys_own.p_enc_key = self.enc_key_own
        self.keyset.keys_own.p_id_key = self.id_key_own
        self.keyset.keys_own.p_sign_key = self.sign_info_own
        self.keyset.keys_own.p_pk = self.lesc_pk_own
        self.keyset.keys_peer.p_enc_key = self.enc_key_peer
        self.keyset.keys_peer.p_id_key = self.id_key_peer
        self.keyset.keys_peer.p_sign_key = self.sign_info_peer
        self.keyset.keys_peer.p_pk = self.lesc_pk_peer

    def setup_sec_params(self):
        """ Setup Security parameters.

        """

        self.kdist_own = BLEGapSecKDist(enc=True, id=True, sign=False, link=False)
        self.kdist_peer = BLEGapSecKDist(enc=True, id=True, sign=False, link=False)
        self.sec_params = BLEGapSecParams(
            bond=True,
            mitm=False,
            lesc=False,
            keypress=False,
            io_caps=BLEGapIOCaps.none,
            oob=False,
            min_key_size=7,
            max_key_size=16,
            kdist_own=self.kdist_own,
            kdist_peer=self.kdist_peer,
        )

    def bond(self):
        """ Bond to Application with Buttonless Service.

        """
        self.bonded = True
        self.setup_sec_params()
        self.setup_keyset()

        self.adapter.driver.ble_gap_authenticate(self.conn_handle, self.sec_params)
        self.evt_sync.wait(evt="sec_params")
        self.adapter.driver.ble_gap_sec_params_reply(
            self.conn_handle, BLEGapSecStatus.success, None, self.keyset, None
        )

        result = self.evt_sync.wait(evt="auth_status")
        if result != BLEGapSecStatus.success:
            raise NordicSemiException(
                "Auth Status returned error code: {}".format(result)
            )

    def encrypt(self):
        """ Re-encrypt to bootloader.

        """
        logger.info("Re-encryption to bootloader")
        self.adapter.driver.ble_gap_encrypt(
            self.conn_handle,
            self.keyset.keys_peer.p_enc_key.master_id,
            self.keyset.keys_peer.p_enc_key.enc_info,
        )
        self.evt_sync.wait("conn_sec_update")

    def write_control_point(self, data):
        self.adapter.write_req(self.conn_handle, DFUAdapter.CP_UUID, data)

    def write_data_point(self, data):
        self.adapter.write_cmd(self.conn_handle, DFUAdapter.DP_UUID, data)

    def on_gap_evt_sec_params_request(self, ble_driver, conn_handle, peer_params):
        logger.info("Got sec params req")
        self.evt_sync.notify(evt="sec_params", data=conn_handle)

    def on_gap_evt_auth_status(self, ble_driver, conn_handle, auth_status):
        logger.info("Got auth status:{}".format(auth_status))
        self.evt_sync.notify(evt="auth_status", data=auth_status)

    def on_gap_evt_conn_sec_update(self, ble_driver, conn_handle):
        logger.info("Got Conn sec update")
        self.evt_sync.notify(evt="conn_sec_update", data=conn_handle)

    def on_gap_evt_connected(
        self, ble_driver, conn_handle, peer_addr, role, conn_params
    ):
        self.evt_sync.notify(evt="connected", data=conn_handle)
        logger.info("BLE: Connected to {}".format(peer_addr.addr))

    def on_gap_evt_disconnected(self, ble_driver, conn_handle, reason):
        self.evt_sync.notify(evt="disconnected", data=conn_handle)
        self.conn_handle = None
        logger.info("BLE: Disconnected with reason: {}".format(reason))

    def on_gap_evt_adv_report(
        self, ble_driver, conn_handle, peer_addr, rssi, adv_type, adv_data
    ):
        dev_name_list = []
        if BLEAdvData.Types.complete_local_name in adv_data.records:
            dev_name_list = adv_data.records[BLEAdvData.Types.complete_local_name]

        elif BLEAdvData.Types.short_local_name in adv_data.records:
            dev_name_list = adv_data.records[BLEAdvData.Types.short_local_name]

        dev_name = "".join(chr(e) for e in dev_name_list)
        address_string = "".join("{0:02X}".format(b) for b in peer_addr.addr)
        logger.info(
            "Received advertisement report, address: 0x{}, device_name: {}".format(
                address_string, dev_name
            )
        )

        if (dev_name == self.target_device_name) or (
            address_string == self.target_device_addr
        ):
            self.conn_params = BLEGapConnParams(
                min_conn_interval_ms=7.5,
                max_conn_interval_ms=30,
                conn_sup_timeout_ms=4000,
                slave_latency=0,
            )
            logger.info(
                "BLE: Found target advertiser, address: 0x{}, name: {}".format(
                    address_string, dev_name
                )
            )
            logger.info("BLE: Connecting to 0x{}".format(address_string))
            # Connect must specify tag=1 to enable the settings
            # set with BLEConfigConnGatt (that implicitly operates
            # on connections with tag 1) to allow for larger MTU.
            self.adapter.connect(address=peer_addr, conn_params=self.conn_params, tag=1)
            # store the address for subsequent connections
            self.target_device_addr = address_string
            self.target_device_addr_type = peer_addr

    def on_notification(self, ble_adapter, conn_handle, uuid, data):
        if self.conn_handle != conn_handle:
            return
        if DFUAdapter.CP_UUID.value != uuid.value:
            return
        self.notifications_q.put(data)

    def on_indication(self, ble_adapter, conn_handle, uuid, data):
        if self.conn_handle != conn_handle:
            return
        if (
            DFUAdapter.BLE_DFU_BUTTONLESS_BONDED_CHAR_UUID.value != uuid.value
            and DFUAdapter.BLE_DFU_BUTTONLESS_CHAR_UUID.value != uuid.value
        ):
            return
        self.indication_q.put(data)

    def on_gattc_evt_exchange_mtu_rsp(
        self, ble_driver, conn_handle, *, status, att_mtu
    ):
        logger.info(
            "ATT MTU exchanged: conn_handle={} att_mtu={}".format(conn_handle, att_mtu)
        )
        self.att_mtu = att_mtu
        self.packet_size = att_mtu - 3


class DfuBLEDriver(BLEDriver):
    def __init__(self, serial_port, baud_rate=115200, auto_flash=False):
        super().__init__(serial_port, baud_rate)

    @NordicSemiErrorCheck
    @wrapt.synchronized(BLEDriver.api_lock)
    def ble_gap_sec_params_reply(
        self, conn_handle, sec_status, sec_params, own_keys, peer_keys
    ):
        assert isinstance(sec_status, BLEGapSecStatus), "Invalid argument type"
        assert sec_params is None or isinstance(
            sec_params, BLEGapSecParams
        ), "Invalid argument type"
        assert peer_keys is None, "NOT IMPLEMENTED"

        return driver.sd_ble_gap_sec_params_reply(
            self.rpc_adapter,
            conn_handle,
            sec_status.value,
            sec_params.to_c() if sec_params else None,
            own_keys,
        )


class DfuTransportBle(DfuTransport):

    DEFAULT_TIMEOUT = 20
    RETRIES_NUMBER = 3

    def __init__(
        self,
        serial_port,
        att_mtu,
        target_device_name=None,
        target_device_addr=None,
        baud_rate=1000000,
        prn=0,
    ):
        super().__init__(name="BLE", retries_number=self.RETRIES_NUMBER)
        self.baud_rate = baud_rate
        self.serial_port = serial_port
        self.att_mtu = att_mtu
        self.target_device_name = target_device_name
        self.target_device_addr = target_device_addr
        self.dfu_adapter = None
        self.prn = prn

        self.bonded = False
        self.keyset = None

    def open(self):
        if self.dfu_adapter:
            raise IllegalStateException("DFU Adapter is already open")

        super().open()
        self.dfu_adapter = DFUAdapter(
            serial_port=self.serial_port,
            baud_rate=self.baud_rate,
            bonded=self.bonded,
            keyset=self.keyset,
            local_att_mtu=self.att_mtu,
        )
        self.dfu_adapter.open()
        self.target_device_name, self.target_device_addr = self.dfu_adapter.connect(
            target_device_name=self.target_device_name,
            target_device_addr=self.target_device_addr,
        )

        logger.debug("BLE: Set Packet Receipt Notification {}".format(self.prn))
        self._operation_command(OP_CODE.PRN_SET, prn=self.prn)

    def close(self):
        # Get bonded status and BLE keyset from DfuAdapter
        self.bonded = self.dfu_adapter.bonded
        self.keyset = self.dfu_adapter.keyset

        if not self.dfu_adapter:
            raise IllegalStateException("DFU Adapter is already closed")
        super().close()
        self.dfu_adapter.close()
        self.dfu_adapter = None

    def _operation_message_recv(self):
        """ Required by super() """
        timeout = DfuTransportBle.DEFAULT_TIMEOUT
        try:
            rxdata = self.dfu_adapter.notifications_q.get(timeout=timeout)
        except queue.Empty:
            raise OperationResponseTimeoutError("Timeout: operation {}".format(timeout))
        return rxdata

    def _operation_message_send(self, message):
        """ Required by super() """
        # TODO must it be a list?
        return self.dfu_adapter.write_control_point(list(message))

    @property
    def _packet_size(self):
        """ Required by super() """
        return self.dfu_adapter.packet_size

    def _stream_packet(self, data):
        """ Required by super() """
        self.dfu_adapter.write_data_point(list(data))  # TODO why list


