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
import tempfile
import os.path
import logging

from nordicsemi.dfu.package import Package
from nordicsemi.thread.dfu_server import DfuServer
import time

logger = logging.getLogger(__name__)

def _get_manifest_items(manifest):
	import inspect
	result = []

	for key, value in inspect.getmembers(manifest):
		if (key.startswith('__')):
			continue
		if not value:
			continue
		if inspect.ismethod(value) or inspect.isfunction(value):
			continue

		result.append((key, value))

	return result

class ThreadDFU:
	def __init__(self, transport_factory, zip_file_path, prefix):
		self.temp_dir = tempfile.mkdtemp(prefix="nrf_dfu_")
		self.unpacked_zip_path = os.path.join(self.temp_dir, 'unpacked_zip')
		self.manifest = Package.unpack_package(zip_file_path, self.unpacked_zip_path)

		init_file, image_file = self._get_paths(self.manifest)
		self.server = DfuServer(transport_factory, init_file, image_file, prefix)

	def start(self):
		self.server.start()

	def stop(self):
		self.server.stop()

	def __enter__(self):
		self.start()
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		self.stop()

	def _get_abs_path(self, f):
		return os.path.join(self.unpacked_zip_path, f)

	def _get_paths(self, manifest):
		data_attrs = _get_manifest_items(manifest)
		if (len(data_attrs) > 1):
			raise RuntimeError("More than one image present in manifest")
		data_attrs = data_attrs[0]
		firmware = data_attrs[1]
		logger.info("Image type {} found".format(data_attrs[0]))
		return self._get_abs_path(firmware.dat_file), self._get_abs_path(firmware.bin_file)

	def trigger(self, address, num_of_requests = 3):
		self.server.trigger(address, num_of_requests)