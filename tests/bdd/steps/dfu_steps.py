#
# Copyright (c) 2019 Nordic Semiconductor ASA
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

import logging
import os
import subprocess
import time

from click.testing import CliRunner
import click
from behave import then, given

from nordicsemi.__main__ import cli
from nordicsemi.lister.device_lister import DeviceLister
from pc_ble_driver_py import config
connectivity_root = os.path.join(os.path.dirname(config.__file__), 'hex', 'sd_api_v5')


ENUMERATE_WAIT_TIME = 5.0 # Seconds to wait for enumeration to finish

all_boards = {
    'PCA10056': DeviceLister().get_device(get_all=True, vendor_id='1366'),
    'PCA10059': DeviceLister().get_device(get_all=True, vendor_id='1915')
}
boards = {}


def exe_runner(exe_name):
    @click.command(name=exe_name, context_settings=dict(ignore_unknown_options=True,))
    @click.argument('command', nargs=-1)
    def f(command):
        subprocess.run([exe_name, *command], shell=True)
    return f


def resolve_hex_path(filename):
    if filename == "connectivity":
        hex_version = config.get_connectivity_hex_version()
        filename = f'connectivity_{hex_version}_1m_with_s132_5.1.0.hex'
        return os.path.join(connectivity_root, filename)
    elif filename == "connectivity_usb":
        hex_version = config.get_connectivity_hex_version()
        filename = f'connectivity_{hex_version}_usb_with_s132_5.1.0_dfu_pkg.zip'
        return os.path.join(connectivity_root, filename)
    else:
        return os.path.join(*filename.split("\\"))


def find_nrfjprog(program):
    """
        From pc-ble-driver-py/ble-driver.py
    """
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def program_image_usb_serial(context, nrfjprog, full_image_path, snr):
    lister = DeviceLister()

    return_code = subprocess.call("\"{nrfjprog}\" --eraseall --snr {snr}" .format(nrfjprog=nrfjprog,snr=snr), shell=True)
    assert return_code == 0, "Nrfjprog could not erase board with serial number {}".format(snr)
    time.sleep(ENUMERATE_WAIT_TIME) # Waiting for device to enumerate

    devices_before_programming = lister.get_device(get_all=True, vendor_id="1915", product_id="521F")
    return_code = subprocess.call("\"{nrfjprog}\" --program {image} --chiperase -r  --snr {snr}"
    .format(nrfjprog=nrfjprog, image=full_image_path, snr=snr), shell=True)

    assert return_code == 0, \
    "Nrfjprog could program image {} to board with serial number {}".format(full_image_path, snr)

    time.sleep(ENUMERATE_WAIT_TIME) # Waiting for device to enumerate

    devices_after_programming = lister.get_device(get_all=True, vendor_id="1915", product_id="521F")
    dfu_device = None

    for device in devices_after_programming:
        match = False
        for device_old in devices_before_programming:
            if device.serial_number == device_old.serial_number:
                match = True
                break
        if not match:
            dfu_device = device
            break

    assert dfu_device, "Device was programmed, but did not enumerate in {} seconds.".format(ENUMERATE_WAIT_TIME)

    port = dfu_device.get_first_available_com_port()
    return port


def program_image_serial(context, nrfjprog, full_image_path, snr):
    lister = DeviceLister()

    return_code = subprocess.call("\"{nrfjprog}\" --eraseall --snr {snr}"
    .format(nrfjprog=nrfjprog,snr=snr), shell=True)

    assert return_code == 0, "Nrfjprog could not erase board with serial number {}".format(snr)

    return_code = subprocess.call("\"{nrfjprog}\" --program {image} --chiperase -r  --snr {snr}"
    .format(nrfjprog=nrfjprog, image=full_image_path, snr=snr), shell=True)

    assert return_code == 0, \
    "Nrfjprog could program image {} to board with serial number {}".format(full_image_path, snr)

    time.sleep(ENUMERATE_WAIT_TIME) # Waiting for device to enumerate

    snr_left_pad = snr
    if (len(snr_left_pad)) < 12:
        snr_left_pad = '0'*(12-len(snr_left_pad)) + snr_left_pad

    device = lister.get_device(get_all=False, serial_number=snr_left_pad)
    devices = lister.enumerate()

    assert device, "Device was programmed, but did not enumerate in {} seconds.".format(ENUMERATE_WAIT_TIME)

    port = device.get_first_available_com_port()
    return port


def program_image_ble(nrfjprog, full_image_path, snr):
    return_code = subprocess.call("\"{nrfjprog}\" --eraseall --snr {snr}"
    .format(nrfjprog=nrfjprog,snr=snr), shell=True)
    assert return_code == 0, "Nrfjprog could not erase board with serial number {}".format(snr)

    return_code = subprocess.call("\"{nrfjprog}\" --program {image} --chiperase -r  --snr {snr}"
    .format(nrfjprog=nrfjprog, image=full_image_path, snr=snr), shell=True)

    assert return_code == 0, \
    "Nrfjprog could program image {} to board with serial number {}".format(full_image_path, snr)

logger = logging.getLogger(__file__)

STDOUT_TEXT_WAIT_TIME = 50  # Number of seconds to wait for expected output from stdout


@given('the user wants to perform dfu {dfu_type}')
def step_impl(context, dfu_type):
    runner = CliRunner()
    context.runner = runner
    args = ['dfu', dfu_type]

    context.args = args


@given('using package {package}')
def step_impl(context, package):
    full_package_path = resolve_hex_path(package)
    context.args.extend(['-pkg', full_package_path])
    context.pkg = full_package_path


@given('option {args}')
def step_impl(context, args):
    context.args.extend(args.split(" "))


@given('-snr {device}')
def step_impl(context, device):
    snr = False
    if device not in os.environ and device not in boards:
        try:
            boards[device] = all_boards[device.split('_')[0]].pop()
            snr = boards[device].serial_number.lower().lstrip('0')
        except:
            assert False, "Environment variable '{}' must be exported with device serial number or a device must be connected".format(device)
    elif device in os.environ:
        snr = os.environ[device].lower().lstrip('0') # Remove zeros to the left.
    else:
        snr = boards[device].serial_number.lower().lstrip('0')
    context.args.extend(["-snr", snr])


@given('nrfjprog {image} for {image_type} {board}')
def step_impl(context, image, image_type, board):

    full_image_path = resolve_hex_path(image)

    nrfjprog = find_nrfjprog("nrfjprog")
    if nrfjprog is None:
        nrfjprog = find_nrfjprog("nrfjprog.exe")

    assert nrfjprog, "nrfjprog is not installed"

    if board not in os.environ and board not in boards:
        try:
            boards[board] = all_boards[board.split('_')[0]].pop()
            snr = boards[board].serial_number.lower().lstrip('0')
        except:
            assert False, "Environment variable '{}' must be exported with JLink serial number or a JLink board must be connected".format(board)
    elif board in os.environ:
        snr = str(int(os.environ[board])) # Remove zeros to the left.
    else:
        snr = boards[board].serial_number.lower().lstrip('0')

    if image_type == "usb-serial":
        port = program_image_usb_serial(context, nrfjprog, full_image_path, snr)
        context.args.extend(['-p', port])
        context.p = port
    elif image_type == "serial":
        port = program_image_serial(context, nrfjprog, full_image_path, snr)
        context.args.extend(['-p', port])
        context.p = port
    elif image_type == 'ble':
        program_image_ble(nrfjprog, full_image_path, snr)
    else:
        assert False, "Invalid dfu transport."


@then('perform dfu using nrfutil {nrfutil}')
def step_impl(context, nrfutil):
    if nrfutil not in os.environ:
        nrfutil = cli
    else:
        nrfutil = exe_runner(os.environ[nrfutil])

    result = context.runner.invoke(nrfutil, context.args)
    logger.debug("exit_code: %s, output: \'%s\'", result.exit_code, result.output)
    assert result.exit_code == 0, "exit_code: {}, output: \'{}\'".format( result.exit_code, result.output)
    time.sleep(ENUMERATE_WAIT_TIME) # Waiting some time to ensure enumeration before next test.


@then('perform dfu twice with port change')
def step_impl(context):
    lister = DeviceLister()

    devices_before_programming = lister.get_device(get_all=True, vendor_id="1915", product_id="521F")

    result = context.runner.invoke(cli, context.args)
    logger.debug("exit_code: %s, output: \'%s\'", result.exit_code, result.output)
    assert result.exit_code == 0, "exit_code: {}, output: \'{}\'".format( result.exit_code, result.output)
    time.sleep(ENUMERATE_WAIT_TIME) # Waiting for device to enumerate

    devices_after_programming = lister.get_device(get_all=True, vendor_id="1915", product_id="C00A")
    dfu_device = None

    for device in devices_after_programming:
        match = False
        for device_old in devices_before_programming:
            if device.serial_number == device_old.serial_number:
                dfu_device = device
                match = True
                break
        if match:
            break

    assert dfu_device, "Device was programmed, but did not enumerate in {} seconds.".format(ENUMERATE_WAIT_TIME)

    port = dfu_device.get_first_available_com_port()
    context.args[-1] = port
    result = context.runner.invoke(cli, context.args)
    logger.debug("exit_code: %s, output: \'%s\'", result.exit_code, result.output)
    assert result.exit_code == 0, "exit_code: {}, output: \'{}\'".format( result.exit_code, result.output)
    time.sleep(ENUMERATE_WAIT_TIME) # Waiting some time to ensure enumeration before next test.
