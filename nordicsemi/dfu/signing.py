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
# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

import hashlib
import binascii

try:
    from ecdsa import SigningKey
    from ecdsa.curves import NIST256p
    from ecdsa.keys import sigencode_string
except Exception:
    print "Failed to import ecdsa, cannot do signing"

from nordicsemi.exceptions import InvalidArgumentException, IllegalStateException


class Signing(object):
    """
    Class for singing of hex-files
    """
    def gen_key(self, filename):
        """
        Generate a new Signing key using NIST P-256 curve
        """
        self.sk = SigningKey.generate(curve=NIST256p)

        with open(filename, "w") as sk_file:
            sk_file.write(self.sk.to_pem())

    def load_key(self, filename):
        """
        Load signing key (from pem file)
        """
        with open(filename, "r") as sk_file:
            sk_pem = sk_file.read()

        self.sk = SigningKey.from_pem(sk_pem)

        sk_hex = "".join(c.encode('hex') for c in self.sk.to_string())

    def sign(self, init_packet_data):
        """
        Create signature for init package using P-256 curve and SHA-256 as hashing algorithm
        Returns R and S keys combined in a 64 byte array
        """
        # Add assertion of init_packet
        if self.sk is None:
            raise IllegalStateException("Can't save key. No key created/loaded")

        # Sign the init-packet
        signature = self.sk.sign(init_packet_data, hashfunc=hashlib.sha256, sigencode=sigencode_string)
        return signature[31::-1] + signature[63:31:-1]

    def verify(self, init_packet, signature):
        """
        Verify init packet
        """
        # Add assertion of init_packet
        if self.sk is None:
            raise IllegalStateException("Can't save key. No key created/loaded")

        vk = self.sk.get_verifying_key()

        # Verify init packet
        try:
            vk.verify(signature, init_packet, hashfunc=hashlib.sha256)
        except:
            return False

        return True

    def get_vk(self, output_type):
        """
        Get public key (as hex, code or pem)
        """
        if self.sk is None:
            raise IllegalStateException("Can't get key. No key created/loaded")

        if output_type is None:
            raise InvalidArgumentException("Invalid output type for public key.")
        elif output_type == 'hex':
            return self.get_vk_hex()
        elif output_type == 'code':
            return self.get_vk_code()
        elif output_type == 'pem':
            return self.get_vk_pem()
        else:
            raise InvalidArgumentException("Invalid argument. Can't get key")

    def get_sk(self, output_type):
        """
        Get private key (as hex, code or pem)
        """
        if self.sk is None:
            raise IllegalStateException("Can't get key. No key created/loaded")

        if output_type is None:
            raise InvalidArgumentException("Invalid output type for private key.")
        elif output_type == 'hex':
            return self.get_sk_hex()
        elif output_type == 'code':
            return self.get_sk_code()
        elif output_type == 'pem':
            return self.sk.to_pem()
        else:
            raise InvalidArgumentException("Invalid argument. Can't get key")

    def get_sk_hex(self):
        """
        Get the verification key as hex
        """
        if self.sk is None:
            raise IllegalStateException("Can't get key. No key created/loaded")

        sk_hexlify = binascii.hexlify(self.sk.to_string())

        sk_hexlify_list = []
        for i in xrange(len(sk_hexlify)-2, -2, -2):
            sk_hexlify_list.append(sk_hexlify[i:i+2])

        sk_hexlify_list_str = ''.join(sk_hexlify_list)

        vk_hex = "Private (signing) key sk:\n{0}".format(sk_hexlify_list_str)

        return vk_hex

    def get_vk_hex(self):
        """
        Get the verification key as hex
        """
        if self.sk is None:
            raise IllegalStateException("Can't get key. No key created/loaded")

        vk = self.sk.get_verifying_key()
        vk_hexlify = binascii.hexlify(vk.to_string())

        vk_hexlify_list = []
        for i in xrange(len(vk_hexlify[0:64])-2, -2, -2):
            vk_hexlify_list.append(vk_hexlify[i:i+2])

        for i in xrange(len(vk_hexlify)-2, 62, -2):
            vk_hexlify_list.append(vk_hexlify[i:i+2])

        vk_hexlify_list_str = ''.join(vk_hexlify_list)

        vk_hex = "Public (verification) key pk:\n{0}".format(vk_hexlify_list_str)

        return vk_hex

    def get_sk_code(self):
        """
        Get the verification key as code
        """
        if self.sk is None:
            raise IllegalStateException("Can't get key. No key created/loaded")

        sk_hex = binascii.hexlify(self.sk.to_string())

        sk_x_separated = ""
        for i in xrange(0, len(sk_hex), 2):
            sk_x_separated = "0x" + sk_hex[i:i+2] + ", " + sk_x_separated

        sk_x_separated = sk_x_separated[:-2]

        sk_code = "static const uint8_t sk[] = {{ {0} }};".format(sk_x_separated)

        return sk_code + "\nstatic const nrf_crypto_key_t crypto_key_sk = { .p_le_data = (uint8_t *) sk, .len = sizeof(sk) };"

    def get_vk_code(self):
        """
        Get the verification key as code
        """
        if self.sk is None:
            raise IllegalStateException("Can't get key. No key created/loaded")

        vk = self.sk.get_verifying_key()
        vk_hex = binascii.hexlify(vk.to_string())

        vk_x_separated = ""
        vk_x_str = vk_hex[0:64]
        for i in xrange(0, len(vk_x_str), 2):
            vk_x_separated = "0x" + vk_x_str[i:i+2] + ", " + vk_x_separated

        vk_y_separated = ""
        vk_y_str = vk_hex[64:128]
        for i in xrange(0, len(vk_y_str), 2):
            vk_y_separated = "0x" + vk_y_str[i:i+2] + ", " + vk_y_separated
        vk_y_separated = vk_y_separated[:-2]

        vk_code = "static const uint8_t pk[] = {{ {0} }};".format(vk_x_separated+vk_y_separated)

        return vk_code + "\nstatic const nrf_crypto_key_t crypto_key_pk = { .p_le_data = (uint8_t *) pk, .len = sizeof(pk) };"

    def get_vk_pem(self):
        """
        Get the verification key as PEM
        """
        if self.sk is None:
            raise IllegalStateException("Can't get key. No key created/loaded")

        vk = self.sk.get_verifying_key()
        vk_pem = vk.to_pem()

        return vk_pem
