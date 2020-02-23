#
# Copyright (c) 2016-2018 Nordic Semiconductor ASA
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
import binascii
from datetime import datetime
import logging
import queue
import struct
import sys


# Python 3rd party imports
try:
    import antlib
    import antlib.antdefines as antdefines
    import antlib.antmessage as antmessage
except ImportError as e:
    print(e)
    raise Exception("Try running 'pip install antlib'.")


# Local imports
from nordicsemi.dfu.dfu_transport import (
    OP_CODE,
    TRANSPORT_LOGGING_LEVEL,
    DfuTransport,
    DfuEvent,
    NordicSemiException,
    ValidationException,
    OperationResCodeError,
)

logger = logging.getLogger(__name__)


def platform_supported():
    """
    A platform check should be performed before using this module.
    Only a python 32bit interpreter on windows is supported. The 'antlib'
    package depends on precompiled windows 32bit libraries.

    :return: True if platform is windows 32bit or False otherwise.
    :rtype: bool
    """
    can_run = False

    if sys.platform in ["win32", "win64"]:
        # Check if Python is 32 bit.
        if struct.calcsize("P") * 8 == 32:
            can_run = True

    if not can_run:
        print(
            "The ant dfu command is only available on Windows with a 32bit Python \n"
            "which can be downloaded here: 'https://www.python.org/downloads/windows/'."
        )

    return can_run


class AntParams:
    # 2466 MHz
    DEF_RF_FREQ = 66
    # 16 Hz
    DEF_CHANNEL_PERIOD = 2048
    # Wildcard specific device.
    DEF_DEVICE_NUM = 0
    DEF_DEVICE_TYPE = 10
    DEF_TRANS_TYPE = 0
    DEF_NETWORK_KEY = None

    def __init__(self):
        self.rf_freq = self.DEF_RF_FREQ
        self.channel_period = self.DEF_CHANNEL_PERIOD
        self.device_num = self.DEF_DEVICE_NUM
        self.device_type = self.DEF_DEVICE_TYPE
        self.trans_type = self.DEF_TRANS_TYPE
        self.network_key = self.DEF_NETWORK_KEY


class DfuAdapter:
    ANT_RSP_TIMEOUT = 100
    ANT_DFU_CHAN = 0
    ANT_NET_KEY_IDX = 0

    DATA_MESGS = (
        antmessage.MESG_BROADCAST_DATA_ID,
        antmessage.MESG_ACKNOWLEDGED_DATA_ID,
        antmessage.MESG_BURST_DATA_ID,
        antmessage.MESG_ADV_BURST_DATA_ID,
    )

    def __init__(self, ant_dev, timeout, search_timeout, ant_config):
        self.ant_dev = ant_dev
        self.timeout = timeout
        self.search_timeout = search_timeout
        self.ant_config = ant_config
        self.connected = False
        self.tx_result = None
        self.beacon_rx = False
        self.tx_seq = None
        self.rx_seq = None
        self.rx_data = None
        self.resp_queue = queue.Queue()

    def open(self):
        # TODO: use constant from antlib when it exists.
        # Set up advanced burst with optional frequency hopping. This can help
        # Increase the throughput by about 3x.
        self.ant_dev.configure_advanced_burst(
            True, 3, 0, 0x01, response_time_msec=self.ANT_RSP_TIMEOUT
        )

        if self.ant_config.network_key is not None:
            self.ant_dev.set_network_key(
                self.ANT_NET_KEY_IDX, self.ant_config.network_key
            )

        self.ant_dev.assign_channel(
            self.ANT_DFU_CHAN,
            antdefines.CHANNEL_TYPE_SLAVE,
            self.ANT_NET_KEY_IDX,
            response_time_msec=self.ANT_RSP_TIMEOUT,
        )

        # The params here are fairly arbitrary, but must match what the device
        # uses. These match the defaults in the example projects.
        self.ant_dev.set_channel_freq(
            self.ANT_DFU_CHAN,
            self.ant_config.rf_freq,
            response_time_msec=self.ANT_RSP_TIMEOUT,
        )

        self.ant_dev.set_channel_period(
            self.ANT_DFU_CHAN,
            self.ant_config.channel_period,
            response_time_msec=self.ANT_RSP_TIMEOUT,
        )

        self.ant_dev.set_channel_id(
            self.ANT_DFU_CHAN,
            self.ant_config.device_num,
            self.ant_config.device_type,
            self.ant_config.trans_type,
            response_time_msec=self.ANT_RSP_TIMEOUT,
        )

        # Disable high priority search. It doesn't matter much which search
        # is used as there are no other open channels, but configuring only
        # one makes sure the timeout arrives when expected.
        self.ant_dev.set_channel_search_timeout(
            self.ANT_DFU_CHAN, 0, response_time_msec=self.ANT_RSP_TIMEOUT
        )

        self.ant_dev.set_low_priority_search_timeout(
            self.ANT_DFU_CHAN,
            int(self.search_timeout / 2.5),
            response_time_msec=self.ANT_RSP_TIMEOUT,
        )

        self.ant_dev.open_channel(
            self.ANT_DFU_CHAN, response_time_msec=self.ANT_RSP_TIMEOUT
        )

        self.__wait_for_condition(lambda: self.connected, self.search_timeout + 1.0)

    def close(self):
        self.ant_dev.reset_system(response_time_msec=self.ANT_RSP_TIMEOUT)
        self.ant_dev.ant_close()
        self.ant_dev = None

    def send_message(self, req):
        logger.log(TRANSPORT_LOGGING_LEVEL, "ANT: --> {}".format(req))

        self.tx_seq = (self.tx_seq + 1) & 0xFF
        data = list(struct.pack("<HB", len(req) + 3, self.tx_seq)) + req

        self.tx_result = None

        while self.tx_result != True:
            self.tx_result = None

            self.ant_dev.send_burst(self.ANT_DFU_CHAN, data)
            self.__wait_for_condition(lambda: self.tx_result is not None)

            # Wait for a beacon, needed in tx fail case to allow for flush of
            # any sequence number errors that could interrupt the burst.
            self.beacon_rx = False
            self.__wait_for_condition(lambda: self.beacon_rx)

    def get_message(self):
        self.__wait_for_condition(lambda: not self.resp_queue.empty())
        mesg = self.resp_queue.get_nowait()

        logger.log(TRANSPORT_LOGGING_LEVEL, "ANT: <-- {}".format(mesg))
        return mesg

    def __wait_for_condition(self, cond, timeout=None):
        if timeout is None:
            timeout = self.timeout

        start = datetime.now()
        while not cond():
            self.__process_mesg(timeout - (datetime.now() - start).total_seconds())

    def __process_mesg(self, timeout):
        mesg = self.__get_ant_mesg(timeout)

        if mesg.msgid in self.DATA_MESGS:
            self.__process_data_mesg(mesg)
        elif mesg.msgid == antmessage.MESG_RESPONSE_EVENT_ID:
            if mesg.data[1] == antmessage.MESG_EVENT_ID:
                self.__process_evt(mesg.data[2])

    def __process_data_mesg(self, mesg):
        if mesg.msgid == antmessage.MESG_BROADCAST_DATA_ID:
            self.connected = True
            self.beacon_rx = True
            # Broadcast data should always contain the current sequence numbers.
            if self.tx_seq is None:
                self.tx_seq = mesg.data[1]
            if self.rx_seq is None:
                self.rx_seq = mesg.data[2]
            return

        if not self.connected:
            # Ignore non-broadcast data until connection is established.
            return

        data = mesg.data[1 : 1 + antdefines.ANT_STANDARD_DATA_PAYLOAD_SIZE]
        is_first = False
        is_last = False

        if mesg.msgid == antmessage.MESG_ACKNOWLEDGED_DATA_ID:
            is_first = is_last = True
        else:
            if mesg.sequence_number == antdefines.SEQUENCE_FIRST_MESSAGE:
                is_first = True
            if (mesg.sequence_number & antdefines.SEQUENCE_LAST_MESSAGE) != 0:
                is_last = True
            if mesg.msgid == antmessage.MESG_ADV_BURST_DATA_ID:
                data = mesg.data[1:]

        if is_first:
            self.rx_data = data
        else:
            self.rx_data += data

        if is_last:
            self.__process_resp()
            self.rx_data = None

    def __process_resp(self):
        (size, seq) = struct.unpack("<HB", bytearray(self.rx_data[:3]))

        if seq == self.rx_seq:
            logger.debug("Duplicate response received")
            return

        self.rx_seq = seq
        self.resp_queue.put(self.rx_data[3:size])

    def __process_evt(self, evt):
        if evt == antdefines.EVENT_CHANNEL_CLOSED:
            raise NordicSemiException("Device connection lost")
        elif evt == antdefines.EVENT_TRANSFER_TX_COMPLETED:
            self.tx_result = True
        elif evt == antdefines.EVENT_TRANSFER_TX_FAILED:
            self.tx_result = False
        elif evt == antdefines.EVENT_TRANSFER_RX_FAILED:
            self.rx_data = None

    def __get_ant_mesg(self, timeout):
        mesg = None
        if self.ant_dev.wait_for_message(int(timeout * 1000)):
            mesg = self.ant_dev.get_message()

        if not mesg:
            raise NordicSemiException("No message received from device")

        return mesg


class DfuTransportAnt(DfuTransport):
    ANT_RST_TIMEOUT_MS = 500
    DEFAULT_PORT = 0
    DEFAULT_CMD_TIMEOUT = 5.0  # Timeout on waiting for a response.
    DEFAULT_SEARCH_TIMEOUT = 10.0  # Timeout when searching for the device.
    DEFAULT_PRN = 0
    DEFAULT_DO_PING = True
    DEFAULT_DO_DEBUG = False

    def __init__(
        self,
        ant_config=None,
        port=DEFAULT_PORT,
        timeout=DEFAULT_CMD_TIMEOUT,
        search_timeout=DEFAULT_SEARCH_TIMEOUT,
        prn=DEFAULT_PRN,
        debug=DEFAULT_DO_DEBUG,
    ):

        super().__init__()
        if ant_config is None:
            ant_config = AntParams()
        self.ant_config = ant_config
        self.port = port
        self.timeout = timeout
        self.search_timeout = search_timeout
        self.prn = prn
        self.ping_id = 0
        self.dfu_adapter = None
        self.mtu = 0
        self.debug = debug

    def open(self):
        super().open()
        ant_dev = None
        try:
            ant_dev = antlib.ANTDevice(
                self.port,
                57600,
                antlib.antdevice.ANTDevice.USB_PORT_TYPE,
                antlib.antdevice.ANTDevice.FRAMER_TYPE_BASIC,
            )
            ant_dev.reset_system(response_time_msec=self.ANT_RST_TIMEOUT_MS)
            # There might be a back log of messages, clear them out.
            while ant_dev.get_message():
                pass
            if self.debug:
                ant_dev.enable_debug_logging()
        except Exception as e:
            raise NordicSemiException(
                "Could not open {0}. Reason: {1}".format(ant_dev, e)
            )

        self.dfu_adapter = DfuAdapter(
            ant_dev, self.timeout, self.search_timeout, self.ant_config
        )
        self.dfu_adapter.open()

        if not self.__ping():
            raise NordicSemiException("No ping response from device.")

        logger.debug("ANT: Set Packet Receipt Notification {}".format(self.prn))
        self._operation_cmd(OP_CODE.PRN_SET, prn=self.prn)
        self.mtu = self._operation_cmd(OP_CODE.MTU_GET)

    def close(self):
        super().close()
        self.dfu_adapter.close()

    def _operation_message_recv(self):
        return self.dfu_adapter.get_message()

    def _operation_message_send(self, txdata):
        return self.dfu_adapter.send_message(list(txdata))

    @property
    def _packet_size(self):
        # maximum data size is self.mtu - 4 due to the header bytes in commands.
        return self.mtu - 4

    def _stream_packet(self, txdata):
        return self._operation_send(OP_CODE.OBJ_WRITE, data=txdata)

    def __ping(self):
        self.ping_id = (self.ping_id + 1) % 256
        try:
            rx_ping_id = self._operation_cmd(OP_CODE.PING, ping_id=self.ping_id)
        except OperationResCodeError as e:
            logger.debug("ignoring ping response error {}".format(e))
            # Returning an error code is seen as good enough. The bootloader is up and running
            return True

        return bool(rx_ping_id == self.ping_id)
