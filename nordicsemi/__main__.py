# Copyright (c) 2015, Nordic Semiconductor
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of Nordic Semiconductor ASA nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""nrfutil command line tool."""
import logging

import os

import click

import tempfile
import binascii
from nordicsemi.dfu.dfu import Dfu
from nordicsemi.dfu.dfu_transport_serial import DfuTransportSerial
from nordicsemi.dfu.package import Package
from nordicsemi import version as nrfutil_version
import shutil


class nRFException(Exception):
    pass


def int_as_text_to_int(value):
    try:
        if value[:2].lower() == '0x':
            return int(value[2:], 16)
        elif value[:1] == '0':
            return int(value, 8)
        return int(value, 10)
    except ValueError:
        raise nRFException('%s is not a valid integer' % value)


class BasedIntParamType(click.ParamType):
    name = 'integer'

    def convert(self, value, param, ctx):
        try:
            return int_as_text_to_int(value)
        except nRFException:
            self.fail('%s is not a valid integer' % value, param, ctx)

BASED_INT = BasedIntParamType()


@click.group()
@click.option('--verbose',
              help='Show verbose information',
              is_flag=True)
def cli(verbose):
    if verbose:
        logging.basicConfig(format='%(message)s', level=logging.INFO)
    else:
        logging.basicConfig(format='%(message)s')


@cli.command()
def version():
    """Displays nrf utility version."""
    click.echo("nrfutil version {}".format(nrfutil_version.NRFUTIL_VERSION))


@cli.group()
def dfu():
    """
    This set of commands support .dat file generation, hash generation of firmware files, automatic
    conversion of .hex files to .bin files, Nordic DFU OTA package generation for distribution to
    applications.
    """
    pass


@dfu.command(short_help='Generate a package for distribution to Apps supporting Nordic DFU OTA')
@click.argument('zipfile',
                required=True)
@click.option('--application',
              help='The application firmware file',
              type=click.STRING)
@click.option('--application-version',
              help='Application version',
              type=BASED_INT)
@click.option('--bootloader',
              help='The bootloader firmware file',
              type=click.STRING)
@click.option('--dev-revision',
              help='Device revision',
              type=BASED_INT)
@click.option('--dev-type',
              help='Device type',
              type=BASED_INT)
@click.option('--dfu-ver',
              help='DFU packet version to use',
              type=click.FLOAT)
@click.option('--sd-req',
              help='SoftDevice requirement. What SoftDevice is required to already be present on '
                   'the target device. Should be a list of firmware IDs. '
                   'Example: --sd-req 0x4F,0x5A. '
                   'For an empty list use \'none\'. '
                   'See: http://developer.nordicsemi.com/nRF51_SDK/doc/7.2.0/s110/html/a00065.html',
              type=click.STRING)
@click.option('--softdevice',
              help='The SoftDevice firmware file',
              type=click.STRING)
def genpkg(zipfile,
           application,
           application_version,
           bootloader,
           dev_revision,
           dev_type,
           dfu_ver,
           sd_req,
           softdevice):
    """
    Generate a zipfile package for distribution to Apps supporting Nordic DFU OTA.
    The application, bootloader and softdevice files are converted to .bin if it is a .hex file.
    """
    zipfile_path = zipfile  # TODO: check if we can use click.path instead
    sd_req_list = None

    if sd_req == "none":
        sd_req_list = []

    elif sd_req:
        try:
            # This will parse any string starting with 0x as base 16.
            sd_req_list = sd_req.split(',')
            sd_req_list = map(int_as_text_to_int, sd_req_list)
        except ValueError:
            raise nRFException("Could not parse value for --sd-req. "
                               "Hex values should be prefixed with 0x.")

    package = Package(dev_type,
                      dev_revision,
                      application_version,
                      '',
                      sd_req_list,
                      application,
                      bootloader,
                      softdevice,
                      dfu_ver)

    package.generate_package(zipfile_path)

    log_message = "Zip created at {0}".format(zipfile_path)
    click.echo(log_message)


@dfu.command(short_help='Generate a hash for the firmware file provided')
@click.argument('firmware')
def hash(firmware):
    """Calculates a hash for the provided file. The file is converted to .bin if it is a .hex file."""

    firmware_path = firmware[0]

    work_directory = tempfile.mkdtemp(prefix="nrf_", suffix="_dfu")
    Package.normalize_firmware_to_bin(work_directory, firmware_path)

    firmware_bin_filename = os.path.basename(firmware_path)
    firmware_bin_filename = firmware_bin_filename.replace(".hex", ".bin")
    firmware_bin_path = os.path.join(work_directory, firmware_bin_filename)

    firmware_hash = Package.calculate_sha256_hash(firmware_bin_path)
    shutil.rmtree(work_directory)

    result = binascii.hexlify(firmware_hash)
    log_message = "Calculated hash for {0}: {1}".format(firmware_path, result)
    click.echo(log_message)


@dfu.command(short_help="Program a device with bootloader that support serial DFU")
@click.option('-pkg', '--package',
              help='DFU package filename',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
              required=True)
@click.option('-p', '--port',
              help='Serial port COM Port to which the device is connected',
              type=click.STRING,
              required=True)
@click.option('-b', '--baudrate',
              help='Desired baud rate 38400/96000/115200/230400/250000/460800/921600/1000000 (default: 38400). '
                   'Note: Baud rates >115200 are supported by nRF51822, '
                   'but may not be supported by all RS232 devices on Windows.',
              type=click.INT,
              default=38400)
@click.option('-fc', '--flowcontrol',
              help='Enable flow control, default: disabled',
              type=click.BOOL,
              is_flag=True)
def serial(package, port, baudrate, flowcontrol):
    """Program a device with bootloader that support serial DFU"""

    # TODO: Look into using click.progressbar to show progress during DFU
    serial_backend = DfuTransportSerial(port, baudrate, flowcontrol)
    dfu = Dfu(package, dfu_transport=serial_backend)

    click.echo("Upgrading target on {1} with DFU package {0}. Flow control is {2}."
               .format(package, port, "enabled" if flowcontrol else "disabled"))

    try:
        dfu.dfu_send_images()
    except Exception as e:
        click.echo("")
        click.echo("Failed to upgrade target. Error is: {0}".format(e.message))
        click.echo("")
        click.echo("Possible causes:")
        click.echo("- bootloader, SoftDevice or application on target "
                   "does not match the requirements in the DFU package.")
        click.echo("- baud rate or flow control is not the same as in the target bootloader.")
        click.echo("- target is not in DFU mode. If using the SDK examples, "
                   "press Button 4 and RESET and release both to enter DFU mode.")

        return False

    click.echo("Device programmed.")

    return True


if __name__ == '__main__':
    cli()
