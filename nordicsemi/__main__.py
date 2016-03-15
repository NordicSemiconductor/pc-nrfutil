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
import sys
import traceback

from nordicsemi.dfu.dfu import Dfu
from nordicsemi.dfu.dfu_transport import DfuEvent
from nordicsemi.dfu.dfu_transport_serial import DfuTransportSerial
from nordicsemi.dfu.dfu_transport_mesh import DfuTransportMesh
from nordicsemi.dfu.package import Package
from nordicsemi import version as nrfutil_version
from nordicsemi.dfu.signing import Signing
from nordicsemi.dfu.util import query_func


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


class BasedIntOrNoneParamType(click.ParamType):
    name = 'Int or None'

    def convert(self, value, param, ctx):
        try:
            if value.lower() == 'none':
                return 'none'
            return int_as_text_to_int(value)
        except nRFException:
            self.fail('%s is not a valid integer' % value, param, ctx)

BASED_INT_OR_NONE = BasedIntOrNoneParamType()


class TextOrNoneParamType(click.ParamType):
    name = 'Text or None'

    def convert(self, value, param, ctx):
        return value

TEXT_OR_NONE = TextOrNoneParamType()


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


@cli.command(short_help='Generate keys for signing or generate public keys')
@click.argument('key_file', required=True)
@click.option('--gen-key',
              help='generate signing key and store at given path (pem-file)',
              type=click.BOOL,
              is_flag=True)
@click.option('--show-vk',
              help='Show the verification keys for DFU Signing (hex|code|pem)',
              type=click.STRING)
def keys(key_file,
         gen_key,
         show_vk):
    """
    This set of commands support creation of signing key (private) and showing the verification key (public)
    from a previously loaded signing key. Signing key is stored in PEM format
    """
    if not gen_key and show_vk is None:
        raise nRFException("Use either gen-key or show-vk.")

    signer = Signing()

    if gen_key:
        if os.path.exists(key_file):
            if not query_func("File found at %s. Do you want to overwrite the file?" % key_file):
                click.echo('Key generation aborted')
                return

        signer.gen_key(key_file)
        click.echo("Generated key at: %s" % key_file)

    elif show_vk:
        if not os.path.isfile(key_file):
            raise nRFException("No key file to load at: %s" % key_file)

        signer.load_key(key_file)
        click.echo(signer.get_vk(show_vk))


@cli.group()
def dfu():
    """
    This set of commands support Nordic DFU OTA package generation for distribution to
    applications and serial DFU.
    """
    pass


@dfu.command(short_help='Generate a package for distribution to Apps supporting Nordic DFU OTA')
@click.argument('zipfile',
                required=True,
                type=click.Path())
@click.option('--application',
              help='The application firmware file',
              type=click.STRING)
@click.option('--company-id',
            help='Company ID for mesh-application. Must either be a Bluetooth SIG assigned company ID '
            '(see https://www.bluetooth.com/specifications/assigned-numbers/company-identifiers '
            'for more information), or a random number between 65535 and 4294967295. If a random number '
            'is chosen, it is recommended to not use the \"lazy\" approach of selecting an easy number, '
            'as this increases the risk of namespace collisions for the app-IDs. It is also recommended to '
            'use the same company-ID for all your applications.',
            type=BASED_INT_OR_NONE)
@click.option('--application-id',
            help='Mesh application ID, default: 0x0000',
            type=BASED_INT_OR_NONE,
            default=str(Package.DEFAULT_MESH_APP_ID))
@click.option('--application-version',
            help='Application version, default: 0xFFFFFFFF',
            type=BASED_INT_OR_NONE,
            default=str(Package.DEFAULT_APP_VERSION))
@click.option('--bootloader-id',
            help='Mesh bootloader id, default: 0xFF00',
            type=BASED_INT_OR_NONE,
            default=str(Package.DEFAULT_MESH_BOOTLOADER_ID))
@click.option('--bootloader',
              help='The bootloader firmware file',
              type=click.STRING)
@click.option('--dev-revision',
              help='Device revision, default: 0xFFFF',
              type=BASED_INT_OR_NONE,
              default=str(Package.DEFAULT_DEV_REV))
@click.option('--dev-type',
              help='Device type, default: 0xFFFF',
              type=BASED_INT_OR_NONE,
              default=str(Package.DEFAULT_DEV_TYPE))
@click.option('--dfu-ver',
              help='DFU packet version to use, default: 0.5',
              type=click.FLOAT,
              default=Package.DEFAULT_DFU_VER)
@click.option('--sd-req',
              help='SoftDevice requirement. A list of SoftDevice versions (1 or more)'
                   'of which one is required to be present on the target device.'
                   'Example: --sd-req 0x4F,0x5A. Default: 0xFFFE.',
              type=TEXT_OR_NONE,
              default=str(Package.DEFAULT_SD_REQ[0]))
@click.option('--softdevice',
              help='The SoftDevice firmware file',
              type=click.STRING)
@click.option('--key-file',
              help='Signing key (pem fomat)',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False))
@click.option('--mesh',
              help='Generate a package targeting Mesh-DFU',
              type=click.BOOL,
              is_flag=True)
def genpkg(zipfile,
           application,
           company_id,
           application_id,
           application_version,
           bootloader_id,
           bootloader,
           dev_revision,
           dev_type,
           dfu_ver,
           sd_req,
           softdevice,
           key_file,
           mesh):
    """
    Generate a zipfile package for distribution to Apps supporting Nordic DFU OTA.
    The application, bootloader and softdevice files are converted to .bin if it is a .hex file.
    For more information on the generated init packet see:
    http://developer.nordicsemi.com/nRF51_SDK/doc/7.2.0/s110/html/a00065.html
    """
    zipfile_path = zipfile

    if company_id == 'none':
        company_id = None

    if application_id == 'none':
        application_id = None

    if application_version == 'none':
        application_version = None

    if dev_revision == 'none':
        dev_revision = None

    if dev_type == 'none':
        dev_type = None

    if bootloader_id == 'none':
        bootloader_id = None

    sd_req_list = None

    if sd_req.lower() == 'none':
        sd_req_list = []
    elif sd_req:
        try:
            # This will parse any string starting with 0x as base 16.
            sd_req_list = sd_req.split(',')
            sd_req_list = map(int_as_text_to_int, sd_req_list)
        except ValueError:
            raise nRFException("Could not parse value for --sd-req. "
                               "Hex values should be prefixed with 0x.")

    if key_file and dfu_ver < 0.8:
        click.echo("Key file was given, setting DFU version to 0.8")

    package = Package(dev_type,
                      dev_revision,
                      company_id,
                      application_id,
                      application_version,
                      bootloader_id,
                      sd_req_list,
                      application,
                      bootloader,
                      softdevice,
                      dfu_ver,
                      key_file,
                      mesh)

    package.generate_package(zipfile_path)

    log_message = "Zip created at {0}".format(zipfile_path)
    click.echo(log_message)


global_bar = None


def update_progress(progress=0, done=False, log_message=""):
    del done, log_message  # Unused parameters
    if global_bar:
        global_bar.update(max(1, progress))


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
                   'Note: Physical serial ports (e.g. COM1) typically do not support baud rates > 115200',
              type=click.INT,
              default=DfuTransportSerial.DEFAULT_BAUD_RATE)
@click.option('-fc', '--flowcontrol',
              help='Enable flow control, default: disabled',
              type=click.BOOL,
              is_flag=True)
@click.option('-i', '--interval',
              help='Desired interval between data packets in milliseconds. Default: 500. Only applies to Mesh-DFU. '
                   'Note: It is recommended to keep the interval above 200ms to avoid buffer overflow, and below '
                   '2 seconds to avoid timeout.',
              type=click.INT,
              default=1000 * DfuTransportMesh.SEND_DATA_PACKET_WAIT_TIME)
@click.option('-m', '--mesh',
              help='Use mesh serial mode',
              type=click.BOOL,
              is_flag=True)
def serial(package, port, baudrate, flowcontrol, interval, mesh):
    """Program a device with bootloader that support serial DFU"""
    if mesh:
        serial_backend = DfuTransportMesh(port, baudrate, flowcontrol, interval=interval / 1000.0)
        serial_backend.register_events_callback(DfuEvent.PROGRESS_EVENT, update_progress)
    else:
        serial_backend = DfuTransportSerial(port, baudrate, flowcontrol)
        serial_backend.register_events_callback(DfuEvent.PROGRESS_EVENT, update_progress)
    dfu = Dfu(package, dfu_transport=serial_backend)

    click.echo("Upgrading target on {1} with DFU package {0}. Flow control is {2}."
               .format(package, port, "enabled" if flowcontrol else "disabled"))

    try:
        with click.progressbar(length=100) as bar:
            global global_bar
            global_bar = bar
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

        click.echo("Trace:\r\n{0}".format(traceback.print_exc()))
        return False

    click.echo("Device programmed.")

    return True


if __name__ == '__main__':
    cli()
