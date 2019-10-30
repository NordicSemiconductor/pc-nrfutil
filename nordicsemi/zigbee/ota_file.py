#
# Copyright (c) 2018 Nordic Semiconductor ASA
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

import struct

OTA_UPGRADE_FILE_HEADER_FILE_ID       = 0x0BEEF11E
OTA_UPGRADE_FILE_HEADER_FILE_VERSION  = 0x0100
OTA_UPGRADE_FILE_HEADER_LENGTH        = 4 + 2 + 2 + 2 + 2 + 2 + 4 + 2 + 32 + 4
OTA_UPGRADE_FIELD_CONTROL             = 0x00
OTA_UPGRADE_MANUFACTURER_WILDCARD     = 0xFFFF
OTA_UPGRADE_IMAGE_TYPE_WILDCARD       = 0xFFFF
OTA_UPGRADE_FILE_HEADER_STACK_PRO     = 0x0002

OTA_UPGRADE_SUBELEMENT_HEADER_SIZE    = 2 + 4  # Tag ID + Length Field
OTA_UPGRADE_SUBELEMENT_TRIGGER_TYPE   = 0xCDEF
OTA_UPGRADE_SUBELEMENT_TRIGGER_LENGTH = 1 + 4 + 4 + 4 + 4 # See background_dfu_trigger_t in the nRF5 SDK for explanation

OTA_UPGRADE_FIELD_CONTROL_BIT_MASK_HW_VER = (1 << 2)
OTA_UPGRADE_MIN_HW_VERSION_LENGTH         = 2
OTA_UPGRADE_MAX_HW_VERSION_LENGTH         = 2
'''
   background_dfu_trigger_t type defined in components/iot/background_dfu/background_dfu_state.h of nRF5 SDK:

    /** @brief Trigger packet structure. */
    typedef PACKED_STRUCT
    {
        uint8_t  flags;         /**< Trigger message flags. Bits 7:4 (oldest) - trigger version, bit 3 - DFU mode, bits 2:0 - reserved. */
        uint32_t init_length;
        uint32_t init_crc;
        uint32_t image_length;
        uint32_t image_crc;
    } background_dfu_trigger_t;
'''

class OTA_file:

    def __init__(self,
                 file_version,
                 init_cmd_len,
                 init_cmd_crc,
                 init_cmd,
                 firmware_len,
                 firmware_crc,
                 firmware,
                 manufacturer_code = OTA_UPGRADE_MANUFACTURER_WILDCARD,
                 image_type = OTA_UPGRADE_IMAGE_TYPE_WILDCARD,
                 comment = '',
                 min_hw_version=None,
                 max_hw_version=None):
        '''A constructor for the OTA file class, see Zigbee ZCL spec 11.4.2 (Zigbee Document 07-5123-06)
           see: http://www.zigbee.org/~zigbeeor/wp-content/uploads/2014/10/07-5123-06-zigbee-cluster-library-specification.pdf
           (access verified as of 2018-08-06)
        '''

        total_len = OTA_UPGRADE_FILE_HEADER_LENGTH + 3 * OTA_UPGRADE_SUBELEMENT_HEADER_SIZE + OTA_UPGRADE_SUBELEMENT_TRIGGER_LENGTH + init_cmd_len + firmware_len

        ota_header = OTA_header(OTA_UPGRADE_FILE_HEADER_FILE_ID,
                                OTA_UPGRADE_FILE_HEADER_FILE_VERSION,
                                OTA_UPGRADE_FILE_HEADER_LENGTH,
                                OTA_UPGRADE_FIELD_CONTROL,
                                manufacturer_code,
                                image_type,
                                file_version,
                                OTA_UPGRADE_FILE_HEADER_STACK_PRO,
                                comment,
                                total_len,
                                min_hw_version,
                                max_hw_version)

        subelement_header_pack_format = '<HL'
        subelement_trigger_pack_format = '>cLLLL'

        subelement_trigger = struct.pack(subelement_header_pack_format,
                                         OTA_UPGRADE_SUBELEMENT_TRIGGER_TYPE,
                                         OTA_UPGRADE_SUBELEMENT_TRIGGER_LENGTH)
        subelement_trigger_payload  = struct.pack(subelement_trigger_pack_format,
                                                  bytes([0x10]),  # flags
                                                  init_cmd_len,
                                                  init_cmd_crc,
                                                  firmware_len,
                                                  firmware_crc)

        subelement_init_cmd = struct.pack(subelement_header_pack_format, 0x0000, init_cmd_len) # Subelement tags are not really needed in case of Init Cmd and Firmware subelements
        subelement_firmware = struct.pack(subelement_header_pack_format, 0x0000, firmware_len)

        self.binary = ota_header.header + subelement_trigger + subelement_trigger_payload + subelement_init_cmd + init_cmd + subelement_firmware + firmware
        self.filename = '-'.join(['{:04X}'.format(manufacturer_code),
                                  '{:04X}'.format(image_type),
                                  '{:08X}'.format(file_version),
                                  comment]) + '.zigbee'


class OTA_header:
    def __init__(self,
                 file_id,
                 header_version,
                 header_length,
                 header_field_control,
                 manufacturer_code,
                 image_type,
                 file_version,
                 zigbee_stack_version,
                 header_string,
                 total_image_size,
                 min_hw_version=None,
                 max_hw_version=None):

        self.__pack_format = '<LHHHHHLHc31sL'
        self.__header_length = header_length
        self.__total_size = total_image_size
        self.__field_control = header_field_control
        self.__additional_fields = []

        # If min and max hardware version are present add optional fields to the header
        if (type(min_hw_version) is int) and (type(max_hw_version) is int):
            self.__add_optional_fields((OTA_UPGRADE_MIN_HW_VERSION_LENGTH + OTA_UPGRADE_MAX_HW_VERSION_LENGTH),
                                       OTA_UPGRADE_FIELD_CONTROL_BIT_MASK_HW_VER,
                                       'HH',
                                       [min_hw_version, max_hw_version])

        self.__pack_args = [file_id,
                            header_version,
                            self.__header_length,
                            self.__field_control,
                            manufacturer_code,
                            image_type,
                            file_version,
                            zigbee_stack_version,
                            bytes([len(header_string)]),
                            bytes(header_string.encode('ascii')),
                            self.__total_size]
        self.__pack_args.extend(self.__additional_fields)

    @property
    def header(self):
        return struct.pack(self.__pack_format, *self.__pack_args)

    def __add_optional_fields(self, fields_length, field_control_bit_mask, fields_formatting, fields_values):
        self.__total_size    += fields_length
        self.__header_length += fields_length
        self.__field_control += field_control_bit_mask
        self.__pack_format   += fields_formatting
        if type(fields_values) in (tuple, list):
            self.__additional_fields.extend(fields_values)
        else:
            self.__additional_fields.append(fields_values)
