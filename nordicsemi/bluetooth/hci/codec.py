# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

UART_HEADER_OCTET_COUNT = 4


class ThreeWireUartPacket(object):
    """
    This class encapsulate a three wire uart packet according to Bluetooth specification
    version 4.0 [Vol 4] part D.
    """
    def __init__(self):
        self.ack = None  # Acknowledgement number
        self.seq = None  # Sequence number
        self.di = None  # Data integrity present
        self.rp = None  # Reliable packet
        self.type = None  # Packet type
        self.length = None  # Payload Length
        self.checksum = None  # Header checksum
        self.payload = None  # Payload

    @staticmethod
    def decode(packet):
        """
        Decodes a packet from a str encoded array

        :param packet_bytes: A str encoded array
        :return: TheeWireUartPacket
        """

        decoded_packet = ThreeWireUartPacket()

        packet_bytes = bytearray(packet)

        decoded_packet.ack = (packet_bytes[0] & int('38', 16)) >> 3
        decoded_packet.seq = (packet_bytes[0] & int('07', 16))
        decoded_packet.di = (packet_bytes[0] & int('40', 16)) >> 6
        decoded_packet.rp = (packet_bytes[0] & int('80', 16)) >> 7
        decoded_packet.type = (packet_bytes[1] & int('0F', 16))
        decoded_packet.length = ((packet_bytes[1] & int('F0', 16)) >> 4) + (packet_bytes[2] * 16)

        checksum = packet_bytes[0]
        checksum = checksum + packet_bytes[1]
        checksum = checksum + packet_bytes[2]
        checksum &= int('FF', 16)
        decoded_packet.checksum = (~checksum + 1) & int('FF', 16)

        if decoded_packet.length > 0:
            decoded_packet.payload = packet_bytes[UART_HEADER_OCTET_COUNT:-1]

        return decoded_packet
