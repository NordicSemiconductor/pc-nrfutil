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

import json
import logging
import os
from zipfile import ZipFile
from behave import given, then, when
from click.testing import CliRunner
from nordicsemi.__main__ import cli, int_as_text_to_int
from common_steps import get_resources_path


logger = logging.getLogger(__file__)


@given('the user wants to generate a DFU package with application {application}, bootloader {bootloader} and SoftDevice {softdevice} with name {package}')
def step_impl(context, application, bootloader, softdevice, package):
    runner = CliRunner()
    context.runner = runner
    args = ['pkg', 'generate']

    if application != 'not_set':
        args.extend(['--application', os.path.join(get_resources_path(), application)])
        context.application = application
    else:
        context.application = None

    if bootloader != 'not_set':
        args.extend(['--bootloader', os.path.join(get_resources_path(), bootloader)])
        context.bootloader = bootloader
    else:
        context.bootloader = None

    if softdevice != 'not_set':
        args.extend(['--softdevice', os.path.join(get_resources_path(), softdevice)])
        context.softdevice = softdevice
    else:
        context.softdevice = None

    args.append(package)

    context.args = args


@given('with option --application-version {app_ver}')
def step_impl(context, app_ver):
    context.application_version = None

    if app_ver == 'not_set':
        context.application_version = 0xFFFFFFFF
    elif app_ver == 'none':
        context.args.extend(['--application-version', 'None'])
    else:
        context.args.extend(['--application-version', app_ver])
        context.application_version = int_as_text_to_int(app_ver)


@given('with option --hw-version {hw_ver}')
def step_impl(context, hw_ver):
    context.args.extend(['--hw-version', hw_ver])
    context.hw_ver = float(hw_ver)


@given('with option --sd-req {sd_reqs}')
def step_impl(context, sd_reqs):
    context.sd_req = None

    if sd_reqs == 'not_set':
        context.sd_req = [0xFFFE]
    elif sd_reqs == 'none':
        context.args.extend(['--sd-req', 'None'])
    else:
        context.args.extend(['--sd-req', sd_reqs])

        sd_reqs = sd_reqs.split(",")
        sd_reqs_value = []

        for sd_req in sd_reqs:
            sd_reqs_value.append(int_as_text_to_int(sd_req))

        context.sd_req = sd_reqs_value


@given('with option --key-file {pem_file}')
def step_impl(context, pem_file):
    if pem_file != 'not_set':
        context.args.extend(['--key-file', os.path.join(get_resources_path(), pem_file)])


@when('user press enter')
def step_impl(context):
    pass


@then('the generated DFU package {package} contains correct data')
def step_impl(context, package):
    with context.runner.isolated_filesystem():
        pkg_full_name = os.path.join(os.getcwd(), package)
        logger.debug("Package full name %s", pkg_full_name)

        result = context.runner.invoke(cli, context.args)
        logger.debug("exit_code: %s, output: \'%s\'", result.exit_code, result.output)
        print(result.exit_code, result.output)
        assert result.exit_code == 0

        with ZipFile(pkg_full_name, 'r') as pkg:
            infolist = pkg.infolist()

            expected_zip_content = ["manifest.json"]

            if context.bootloader and context.softdevice:
                expected_zip_content.append("sd_bl.bin")
                expected_zip_content.append("sd_bl.dat")
            elif context.bootloader:
                expected_zip_content.append(context.bootloader.split(".")[0] + ".bin")
                expected_zip_content.append(context.bootloader.split(".")[0] + ".dat")
            elif context.softdevice:
                expected_zip_content.append(context.softdevice.split(".")[0] + ".bin")
                expected_zip_content.append(context.softdevice.split(".")[0] + ".dat")

            if context.application:
                expected_zip_content.append(context.application.split(".")[0] + '.bin')
                expected_zip_content.append(context.application.split(".")[0] + '.dat')

            for file_information in infolist:
                assert file_information.filename in expected_zip_content
                assert file_information.file_size > 0

            # Extract all and load json document to see if it is correct regarding to paths
            pkg.extractall()

            with open('manifest.json', 'r') as f:
                _json = json.load(f)

                if context.bootloader and context.softdevice:
                    data = _json['manifest']['softdevice_bootloader']['init_packet_data']
                    assert_init_packet_data(context, data)
                elif context.bootloader:
                    data = _json['manifest']['bootloader']['init_packet_data']
                    assert_init_packet_data(context, data)
                elif context.softdevice:
                    data = _json['manifest']['softdevice']['init_packet_data']
                    assert_init_packet_data(context, data)
                if context.application:
                    data = _json['manifest']['application']['init_packet_data']
                    assert_init_packet_data(context, data)


def assert_init_packet_data(context, data):
    if context.application_version:
        assert 'application_version' in data
        assert data['application_version'] == context.application_version

    if context.dev_revision:
        assert 'device_revision' in data
        assert data['device_revision'] == context.dev_revision

    if context.dev_type:
        assert 'device_type' in data
        assert data['device_type'] == context.dev_type

    if context.sd_req:
        assert 'softdevice_req' in data
        assert data['softdevice_req'] == context.sd_req

    if context.ext_packet_id:
        assert 'ext_packet_id' in data
        assert data['ext_packet_id'] == context.ext_packet_id

    if context.firmware_hash:
        assert 'firmware_hash' in data

    if context.init_packet_ecds:
        assert 'init_packet_ecds' in data
