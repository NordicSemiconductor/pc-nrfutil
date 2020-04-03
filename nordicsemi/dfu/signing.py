
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
import datetime

try:
    from ecdsa import SigningKey
    from ecdsa.curves import NIST256p
    from ecdsa.keys import sigencode_string
except Exception:
    print("Failed to import ecdsa, cannot do signing")


keys_default_pem = """-----BEGIN EC PRIVATE KEY-----
MHcCAQEEIGvsrpXh8m/E9bj1dq/0o1aBPQVAFJQ6Pzusx685URE0oAoGCCqGSM49
AwEHoUQDQgAEaHYrUu/oFKIXN457GH+8IOuv6OIPBRLqoHjaEKM0wIzJZ0lhfO/A
53hKGjKEjYT3VNTQ3Zq1YB3o5QSQMP/LRg==
-----END EC PRIVATE KEY-----"""

class Signing:
    """
    Class for singing of hex-files
    """
    def gen_key(self, filename):
        """
        Generate a new Signing key using NIST P-256 curve
        """
        self.sk = SigningKey.generate(curve=NIST256p)

        with open(filename, "wb") as sk_file:
            sk_file.write(self.sk.to_pem())

    def load_key(self, filename):
        """
        Load signing key (from pem file)
        """
        default_sk = SigningKey.from_pem(keys_default_pem)

        with open(filename, "r") as sk_file:
            sk_pem = sk_file.read()

        self.sk = SigningKey.from_pem(sk_pem)
        return default_sk.to_string() == self.sk.to_string()

    def sign(self, init_packet_data):
        """
        Create signature for init package using P-256 curve and SHA-256 as hashing algorithm
        Returns R and S keys combined in a 64 byte array
        """
        # Add assertion of init_packet
        if self.sk is None:
            raise AssertionError("Can't save key. No key created/loaded")

        # Sign the init-packet
        signature = self.sk.sign(init_packet_data, hashfunc=hashlib.sha256, sigencode=sigencode_string)
        return signature[31::-1] + signature[63:31:-1]

    def verify(self, init_packet, signature):
        """
        Verify init packet
        """
        # Add assertion of init_packet
        if self.sk is None:
            raise AssertionError("Can't save key. No key created/loaded")

        vk = self.sk.get_verifying_key()

        # Verify init packet
        try:
            vk.verify(signature, init_packet, hashfunc=hashlib.sha256)
        except:
            return False

        return True

    def get_vk(self, output_type, dbg) -> str:
        """
        Get public key (as hex, code or pem)
        """
        if self.sk is None:
            raise AssertionError("Can't get key. No key created/loaded")

        if output_type is None:
            raise ValueError("Invalid output type for public key.")
        elif output_type == 'hex':
            return self.get_vk_hex()
        elif output_type == 'code':
            return self.get_vk_code(dbg)
        elif output_type == 'pem':
            return self.get_vk_pem()
        else:
            raise ValueError("Invalid argument. Can't get key")

    def get_sk(self, output_type, dbg) -> str:
        """
        Get private key (as hex, code or pem)
        """
        if self.sk is None:
            raise AssertionError("Can't get key. No key created/loaded")

        if output_type is None:
            raise ValueError("Invalid output type for private key.")
        elif output_type == 'hex':
            return self.get_sk_hex()
        elif output_type == 'code':
            raise ValueError("Private key cannot be shown as code")
        elif output_type == 'pem':
            # Return pem as str to conform in type with the other cases.
            return self.sk.to_pem().decode()
        else:
            raise ValueError("Invalid argument. Can't get key")

    def get_sk_hex(self):
        """
        Get the verification key as hex
        """
        if self.sk is None:
            raise AssertionError("Can't get key. No key created/loaded")

        # Reverse the key for display. This emulates a memory
        # dump of the key interpreted a 256bit little endian
        # integer.
        key = self.sk.to_string()
        displayed_key = key[::-1].hex()

        return f"Private (signing) key sk:\n{displayed_key}"

    def get_vk_hex(self):
        """
        Get the verification key as hex
        """
        if self.sk is None:
            raise AssertionError("Can't get key. No key created/loaded")

        # Reverse the two halves of key for display. This
        # emulates a memory dump of the key interpreted as two
        # 256bit little endian integers.
        key = self.sk.get_verifying_key().to_string()
        displayed_key = (key[:32][::-1] + key[32:][::-1]).hex()

        return f"Public (verification) key pk:\n{displayed_key}"

    def wrap_code(self, key_code, dbg):

        header = """
/* This file was automatically generated by nrfutil on {0} */

#include "stdint.h"
#include "compiler_abstraction.h"
""".format(datetime.datetime.now().strftime("%Y-%m-%d (YY-MM-DD) at %H:%M:%S"))

        dbg_header = """
/* This file was generated with a throwaway private key, that is only intended for a debug version of the DFU project.
  Please see https://github.com/NordicSemiconductor/pc-nrfutil/blob/master/README.md to generate a valid public key. */

#ifdef NRF_DFU_DEBUG_VERSION
"""
        dbg_footer = """
#else
#error "Debug public key not valid for production. Please see https://github.com/NordicSemiconductor/pc-nrfutil/blob/master/README.md to generate it"
#endif
"""
        if dbg:
            code = header + dbg_header + key_code + dbg_footer
        else:
            code = header + key_code
        return code


    def get_vk_code(self, dbg):
        """
        Get the verification key as code
        """
        if self.sk is None:
            raise AssertionError("Can't get key. No key created/loaded")

        to_two_digit_hex_with_0x = '0x{0:02x}'.format

        key = self.sk.get_verifying_key().to_string()
        vk_x_separated = ', '.join(map(to_two_digit_hex_with_0x,
                                       key[:32][::-1]))
        vk_y_separated = ', '.join(map(to_two_digit_hex_with_0x,
                                       key[32:][::-1]))

        key_code = """
/** @brief Public key used to verify DFU images */
__ALIGN(4) const uint8_t pk[64] =
{{
    {0},
    {1}
}};
"""
        key_code = key_code.format(vk_x_separated, vk_y_separated)
        vk_code = self.wrap_code(key_code, dbg)

        return vk_code

    def get_vk_pem(self) -> str:
        """
        Get the verification key as PEM
        """
        if self.sk is None:
            raise AssertionError("Can't get key. No key created/loaded")

        vk = self.sk.get_verifying_key()
        vk_pem = vk.to_pem()

        # Return pem as str to conform in type with the other cases.
        return vk_pem.decode()
