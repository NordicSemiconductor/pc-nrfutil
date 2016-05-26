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

from nordicsemi.dfu.dfu import Dfu
from nordicsemi.dfu.dfu_transport import DfuEvent
from nordicsemi.dfu.dfu_transport_serial import DfuTransportSerial
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
              help='Show verbose information.',
              is_flag=True)
def cli(verbose):
    if verbose:
        logging.basicConfig(format='%(message)s', level=logging.INFO)
    else:
        logging.basicConfig(format='%(message)s')


@cli.command()
def version():
    """Display nrfutil version."""
    click.echo("nrfutil version {}".format(nrfutil_version.NRFUTIL_VERSION))

@cli.group(short_help='Generate and display private and public keys.')
#@click.argument('key_file', required=True, type=click.Path())
def keys():
    """
    This set of commands supports creating and displaying a private (signing) key
    as well as displaying the public (verification) key derived from a private key.
    Private keys are stored in PEM format.
    """
    pass


@keys.command(short_help='Generate a private key and store it in a file in PEM format.')
@click.argument('key_file', required=True, type=click.Path())
              
def generate(key_file):
    signer = Signing()
    
    if os.path.exists(key_file):
        if not query_func("File found at %s. Do you want to overwrite the file?" % key_file):
            click.echo('Key generation aborted.')
            return

    signer.gen_key(key_file)
    click.echo("Generated private key and stored it in: %s" % key_file)

@keys.command(short_help='Display the private key that is stored in a file in PEM format or a public key derived from it.')
@click.argument('key_file', required=True, type=click.Path())
@click.option('--key',
              help='(pk|sk) Display the public key (pk) or the private key (sk).',
              type=click.STRING)
@click.option('--format',
              help='(hex|code|pem) Display the key in hexadecimal format (hex), C code (code), or PEM (pem) format.',
              type=click.STRING)

def display(key_file, key, format):
    signer = Signing()

    if not os.path.isfile(key_file):
        raise nRFException("File not found: %s" % key_file)

    signer.load_key(key_file)

    if not key:
        click.echo("You must specify a key with --key (pk|sk).")
        return
    if key != "pk" and key != "sk":
        click.echo("Invalid key type. Valid types are (pk|sk).")
        return

    if not format:
        click.echo("You must specify a format with --format (hex|code|pem).")
        return
    if format != "hex" and format != "code" and format != "pem":
        click.echo("Invalid format. Valid formats are (hex|code|pem).")
        return


    if key == "pk":
        click.echo(signer.get_vk(format))
    elif key == "sk": 
        click.echo("WARNING: Security risk! Do not share the private key.")
        click.echo(signer.get_sk(format))


@cli.group(short_help='Perform a Device Firmware Update.')
def dfu():
    """
    This set of commands supports Nordic DFU package generation for both over-the-air and serial device firmware updates.
    """
    pass


@dfu.command(short_help='Generate a firmware package for over-the-air firmware updates.')
@click.argument('zipfile',
                required=True,
                type=click.Path())
@click.option('--application',
              help='The application firmware file.',
              type=click.STRING)
@click.option('--application-version',
              help='The application version. Default: 0xFFFFFFFF',
              type=BASED_INT_OR_NONE,
              default=str(Package.DEFAULT_APP_VERSION))
@click.option('--bootloader',
              help='The bootloader firmware file.',
              type=click.STRING)
@click.option('--dev-revision',
              help='The device revision. Default: 0xFFFF',
              type=BASED_INT_OR_NONE,
              default=str(Package.DEFAULT_DEV_REV))
@click.option('--dev-type',
              help='The device type. Default: 0xFFFF',
              type=BASED_INT_OR_NONE,
              default=str(Package.DEFAULT_DEV_TYPE))
@click.option('--sd-req',
              help='The SoftDevice requirement. A list of SoftDevice versions (1 or more) '
                   'of which one must be present on the target device. '
                   'Example: --sd-req 0x4F,0x5A. Default: 0xFFFE',
              type=TEXT_OR_NONE,
              default=str(Package.DEFAULT_SD_REQ[0]))
@click.option('--softdevice',
              help='The SoftDevice firmware file.',
              type=click.STRING)
@click.option('--key-file',
              help='The private (signing) key in PEM fomat.',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False))
def genpkg(zipfile,
           application,
           application_version,
           bootloader,
           dev_revision,
           dev_type,
           sd_req,
           softdevice,
           key_file):
    """
    Generate a zip package for distribution to apps that support Nordic DFU OTA.
    The application, bootloader, and SoftDevice files are converted to .bin if supplied as .hex files.
    For more information on the generated package, see:
    http://developer.nordicsemi.com/nRF5_SDK/doc/
    """
    zipfile_path = zipfile

    if application_version == 'none':
        application_version = None

    if dev_revision == 'none':
        dev_revision = None

    if dev_type == 'none':
        dev_type = None

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

    package = Package(dev_type,
                      dev_revision,
                      application_version,
                      sd_req_list,
                      application,
                      bootloader,
                      softdevice,
                      key_file)

    package.generate_package(zipfile_path)

    log_message = "Zip created at {0}".format(zipfile_path)
    click.echo(log_message)


global_bar = None


def update_progress(progress=0, done=False, log_message=""):
    del done, log_message  # Unused parameters
    if global_bar:
        global_bar.update(max(1, progress))


@dfu.command(short_help="Program a device that supports serial DFU.")
@click.option('-pkg', '--package',
              help='Filename of the DFU package.',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
              required=True)
@click.option('-p', '--port',
              help='Serial port COM port to which the device is connected.',
              type=click.STRING,
              required=True)
@click.option('-b', '--baudrate',
              help='Desired baud rate: 38400/96000/115200/230400/250000/460800/921600/1000000. Default: 38400. '
                   'Note: Physical serial ports (for example, COM1) typically do not support baud rates > 115200.',
              type=click.INT,
              default=DfuTransportSerial.DEFAULT_BAUD_RATE)
@click.option('-fc', '--flowcontrol',
              help='Enable flow control. Default: disabled.',
              type=click.BOOL,
              is_flag=True)
def serial(package, port, baudrate, flowcontrol):
    """Perform a Device Firmware Update on a device with a bootloader that supports serial DFU."""
    serial_backend = DfuTransportSerial(port, baudrate, flowcontrol)
    serial_backend.register_events_callback(DfuEvent.PROGRESS_EVENT, update_progress)
    dfu = Dfu(package, dfu_transport=serial_backend)

    click.echo("Updating target on {1} with DFU package {0}. Flow control is {2}."
               .format(package, port, "enabled" if flowcontrol else "disabled"))

    try:
        with click.progressbar(length=100) as bar:
            global global_bar
            global_bar = bar
            dfu.dfu_send_images()

    except Exception as e:
        click.echo("")
        click.echo("Failed to update the target. Error is: {0}".format(e.message))
        click.echo("")
        click.echo("Possible causes:")
        click.echo("- The bootloader, SoftDevice, or application on target "
                   "does not match the requirements in the DFU package.")
        click.echo("- The baud rate or flow control is not the same as in the target bootloader.")
        click.echo("- The target is not in DFU mode. If using the SDK examples, "
                   "press Button 4 and RESET and release both to enter DFU mode.")

        return False

    click.echo("Device programmed.")

    return True


if __name__ == '__main__':
    cli()
