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

"""nrfutil command line tool."""
import os
import sys
import click
import time
import logging
import subprocess
sys.path.append(os.getcwd())

from nordicsemi.dfu.bl_dfu_sett import BLDFUSettings
from nordicsemi.dfu.dfu import Dfu
from nordicsemi.dfu.dfu_transport import DfuEvent
from nordicsemi.dfu.dfu_transport_serial import DfuTransportSerial
from nordicsemi.dfu.package import Package
from nordicsemi import version as nrfutil_version
from nordicsemi.dfu.signing import Signing
from nordicsemi.dfu.util import query_func
from pc_ble_driver_py.exceptions import NordicSemiException, NotImplementedException

logger = logging.getLogger(__name__)

def ble_driver_init(conn_ic_id):
    global BLEDriver, Flasher, DfuTransportBle
    from pc_ble_driver_py import config
    config.__conn_ic_id__ = conn_ic_id
    from pc_ble_driver_py.ble_driver    import BLEDriver, Flasher
    from nordicsemi.dfu.dfu_transport_ble import DfuTransportBle

def display_sec_warning():
    default_key_warning = """
|===============================================================|
|##      ##    ###    ########  ##    ## #### ##    ##  ######  |
|##  ##  ##   ## ##   ##     ## ###   ##  ##  ###   ## ##    ## |
|##  ##  ##  ##   ##  ##     ## ####  ##  ##  ####  ## ##       |
|##  ##  ## ##     ## ########  ## ## ##  ##  ## ## ## ##   ####|
|##  ##  ## ######### ##   ##   ##  ####  ##  ##  #### ##    ## |
|##  ##  ## ##     ## ##    ##  ##   ###  ##  ##   ### ##    ## |
| ###  ###  ##     ## ##     ## ##    ## #### ##    ##  ######  |
|===============================================================|
|The security key you provided is insecure, as it part of a     |
|known set of keys that have been widely distributed. Do NOT use|
|it in your final product or your DFU procedure may be          |
|compromised and at risk of malicious attacks.                  |
|===============================================================|
"""
    click.echo("{}".format(default_key_warning))

def display_debug_warning():
    debug_warning = """
|===============================================================|
|##      ##    ###    ########  ##    ## #### ##    ##  ######  |
|##  ##  ##   ## ##   ##     ## ###   ##  ##  ###   ## ##    ## |
|##  ##  ##  ##   ##  ##     ## ####  ##  ##  ####  ## ##       |
|##  ##  ## ##     ## ########  ## ## ##  ##  ## ## ## ##   ####|
|##  ##  ## ######### ##   ##   ##  ####  ##  ##  #### ##    ## |
|##  ##  ## ##     ## ##    ##  ##   ###  ##  ##   ### ##    ## |
| ###  ###  ##     ## ##     ## ##    ## #### ##    ##  ######  |
|===============================================================|
|You are generating a package with the debug bit enabled in the |
|init packet. This is only compatible with a debug bootloader   |
|and is not suitable for production.                            |
|===============================================================|
"""
    click.echo("{}".format(debug_warning))

def int_as_text_to_int(value):
    try:
        if value[:2].lower() == '0x':
            return int(value[2:], 16)
        elif value[:1] == '0':
            return int(value, 8)
        return int(value, 10)
    except ValueError:
        raise NordicSemiException('%s is not a valid integer' % value)


class BasedIntOrNoneParamType(click.ParamType):
    name = 'Integer'

    def convert(self, value, param, ctx):
        try:
            if value.lower() == 'none':
                return 'none'
            return int_as_text_to_int(value)
        except NordicSemiException:
            self.fail('%s is not a valid integer' % value, param, ctx)

BASED_INT_OR_NONE = BasedIntOrNoneParamType()

class BasedIntParamType(BasedIntOrNoneParamType):
    name = 'Integer'

BASED_INT= BasedIntParamType()

class TextOrNoneParamType(click.ParamType):
    name = 'Text'

    def convert(self, value, param, ctx):
        return value

TEXT_OR_NONE = TextOrNoneParamType()

@click.group()
@click.option('-v', '--verbose',
              help='Show verbose information.',
              count=True)
def cli(verbose):
    #click.echo('verbosity: %s' % verbose)
    if verbose == 0:
        log_level = logging.ERROR
    elif verbose == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    logging.basicConfig(format='%(message)s', level=log_level)

@cli.command()
def version():
    """Display nrfutil version."""
    click.echo("nrfutil version {}".format(nrfutil_version.NRFUTIL_VERSION))
    logger.info("PyPi URL: https://pypi.python.org/pypi/nrfutil")
    logger.debug("GitHub URL: https://github.com/NordicSemiconductor/pc-nrfutil")

@cli.group(short_help='Generate and display Bootloader DFU settings.')
def settings():
    """
    This set of commands supports creating and displaying bootloader settings. 
    """
    pass

@settings.command(short_help='Generate a .hex file with Bootloader DFU settings.')
@click.argument('hex_file', required=True, type=click.Path())
@click.option('--family',
              help='nRF IC family: NRF51 or NRF52 or NRF52840',
              type=click.Choice(['NRF51', 'NRF52', 'NRF52840']))
@click.option('--application',
              help='The application firmware file. This can be omitted if'
                    'the target IC does not contain an application in flash.'
                    'Requires --application-version or --application-version-string.',
              type=click.STRING)
@click.option('--application-version',
              help='The application version.',
              type=BASED_INT_OR_NONE)
@click.option('--application-version-string',
              help='The application version string, e.g "2.7.31".',
              type=click.STRING)
@click.option('--bootloader-version',
              help='The bootloader version.',
              type=BASED_INT_OR_NONE)
@click.option('--bl-settings-version',
              help='The Bootloader settings version.'
              'Defined in nrf_dfu_types.h, the following apply to released SDKs:'
              '\n|SDK12|1|',
              type=BASED_INT_OR_NONE)

def generate(hex_file,
        family,
        application,
        application_version,
        application_version_string,
        bootloader_version,
        bl_settings_version):

    # Initial consistency checks
    if family is None:
        click.echo("Error: IC Family required.")
        return

    # The user can specify the application version with two different
    # formats. As an integer, e.g. 102130, or as a string
    # "10.21.30". Internally we convert to integer.
    if application_version_string:
        application_version_internal = convert_version_string_to_int(application_version_string)
    else:
        application_version_internal = application_version

    if application is not None:
        if not os.path.isfile(application):
            click.echo("Error: Application file not found.")
            return
        if application_version_internal is None:
            click.echo("Error: Application version required.")
            return

    if bootloader_version is None:
        click.echo("Error: Bootloader version required.")
        return
 
    if bl_settings_version is None:
        click.echo("Error: Bootloader DFU settings version required.")
        return
       
    sett = BLDFUSettings()
    sett.generate(arch=family, app_file=application, app_ver=application_version_internal, bl_ver=bootloader_version, bl_sett_ver=bl_settings_version)
    sett.tohexfile(hex_file)

    click.echo("\nGenerated Bootloader DFU settings .hex file and stored it in: {}".format(hex_file))

    click.echo("{0}".format(str(sett)))

@settings.command(short_help='Display the contents of a .hex file with Bootloader DFU settings.')
@click.argument('hex_file', required=True, type=click.Path())

def display(hex_file): 

    sett = BLDFUSettings()
    try:
        sett.fromhexfile(hex_file)
    except NordicSemiException as err:
        click.echo(err)
        return

    click.echo("{0}".format(str(sett)))


@cli.group(short_help='Generate and display private and public keys.')
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
@click.option('--out_file',
              help='If provided, save the output in file out_file.',
              type=click.STRING)

def display(key_file, key, format, out_file):
    signer = Signing()

    if not os.path.isfile(key_file):
        raise NordicSemiException("File not found: %s" % key_file)

    default_key = signer.load_key(key_file)
    if default_key:
        display_sec_warning()

    if not key:
        click.echo("You must specify a key with --key (pk|sk).")
        return
    if key != "pk" and key != "sk":
        click.echo("Invalid key type. Valid types are (pk|sk).")
        return

    if not format:
        click.echo("You must specify a format with --format (hex|code|pem).")
        return
    if format != "hex" and format != "code" and format != "pem" and format != "dbgcode":
        click.echo("Invalid format. Valid formats are (hex|code|pem).")
        return

    if format == "dbgcode":
        format = "code"
        dbg = True
    else:
        dbg = False

    if format == "code" and key == "sk":
        click.echo("Displaying the private key as code is not available.")
        return

    if key == "pk":
        kstr = signer.get_vk(format, dbg)
    elif key == "sk": 
        kstr = "\nWARNING: Security risk! Do not share the private key.\n\n"
        kstr = kstr + signer.get_sk(format, dbg)

    if not out_file:
        click.echo(kstr)
    else:
        with open(out_file, "w") as kfile:
            kfile.write(kstr)


@cli.group(short_help='Generate a Device Firmware Update package.')
def pkg():
    """
    This set of commands supports Nordic DFU package generation.
    """
    pass


@pkg.command(short_help='Generate a firmware package for over-the-air firmware updates.')
@click.argument('zipfile',
                required=True,
                type=click.Path())
@click.option('--debug-mode',
              help='Debug mode switch, enables version check skipping.',
              type=click.BOOL,
              default=False,
              is_flag=True)
@click.option('--application',
              help='The application firmware file.',
              type=click.STRING)
@click.option('--application-version',
              help='The application version.',
              type=BASED_INT_OR_NONE)
@click.option('--application-version-string',
              help='The application version string, e.g "2.7.31".',
              type=click.STRING)
@click.option('--bootloader',
              help='The bootloader firmware file.',
              type=click.STRING)
@click.option('--bootloader-version',
              help='The bootloader version.',
              type=BASED_INT_OR_NONE)
@click.option('--hw-version',
              help='The hardware version.',
              type=BASED_INT)
@click.option('--sd-req',
              help='The SoftDevice requirements. A comma-separated list of SoftDevice firmware IDs (1 or more) '
                   'of which one must be present on the target device. Each item on the list must be in hex and prefixed with \"0x\".'
                   'A list of the possible values to use with this option follows:'
                   '\n|s130_nrf51_1.0.0|0x67|'
                   '\n|s130_nrf51_2.0.0|0x80|'
                   '\n|s132_nrf52_2.0.0|0x81|'
                   '\n|s130_nrf51_2.0.1|0x87|'
                   '\n|s132_nrf52_2.0.1|0x88|'
                   '\n|s132_nrf52_3.0.0|0x8C|'
                   '\n|s132_nrf52_3.1.0|0x91|'
                   '\n|s132_nrf52_4.0.0|0x95|'
                   '\n|s132_nrf52_4.0.2|0x98|'
                   '\n|s132_nrf52_4.0.3|0x99|',
              type=click.STRING,
              multiple=True)
@click.option('--softdevice',
              help='The SoftDevice firmware file.',
              type=click.STRING)
@click.option('--key-file',
              help='The private (signing) key in PEM fomat.',
              required=True,
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False))
def generate(zipfile,
           debug_mode,
           application,
           application_version,
           application_version_string,
           bootloader,
           bootloader_version,
           hw_version,
           sd_req,
           softdevice,
           key_file):
    """
    Generate a zip package for distribution to apps that support Nordic DFU OTA.
    The application, bootloader, and SoftDevice files are converted to .bin if supplied as .hex files.
    For more information on the generated package, see:
    http://developer.nordicsemi.com/nRF5_SDK/doc/

    The following combinations are supported by this command:

    * BL only: Supported.

    * SD only: Supported (SD of same Major Version).

    * APP only: Supported.
   
    * BL + SD: Supported.

    * BL + APP: Not supported (use two packages instead).

    * BL + SD + APP: Supported.

    * SD + APP: Supported (SD of same Major Version).
    """
    zipfile_path = zipfile

    # Check combinations
    if bootloader is not None and application is not None and softdevice is None:
        click.echo("Error: Invalid combination: use two .zip packages instead.")
        return

    if debug_mode is None:
        debug_mode = False

    # The user can specify the application version with two different
    # formats. As an integer, e.g. 102130, or as a string
    # "10.21.30". Internally we convert to integer.
    if application_version_string:
        application_version_internal = convert_version_string_to_int(application_version_string)
    else:
        application_version_internal = application_version

    if application_version_internal == 'none':
        application_version_internal = None

    if bootloader_version == 'none':
        bootloader_version = None

    if hw_version == 'none':
        hw_version = None

    # Convert multiple value into a single instance
    if len(sd_req) > 1:
        click.echo("Please specify SoftDevice requirements as a comma-separated list: --sd-req 0xXXXX,0xYYYY,...")
        return
    elif len(sd_req) == 0:
        sd_req = None
    else:
        sd_req = sd_req[0]
        if sd_req == 'none':
            sd_req = None

    # Initial consistency checks
    if application_version_internal is not None and application is None:
        click.echo("Error: Application version with no image.")
        return

    if bootloader_version is not None and bootloader is None:
        click.echo("Error: Bootloader version with no image.")
        return

    if debug_mode:
        display_debug_warning()
        # Default to no version checking
        if application_version_internal is None:
            application_version_internal=Package.DEFAULT_APP_VERSION
        if bootloader_version is None:
            bootloader_version=Package.DEFAULT_BL_VERSION
        if hw_version is None:
            hw_version=Package.DEFAULT_HW_VERSION
        if sd_req is None:
            # Use string as this will be mapped into an int below
            sd_req=str(Package.DEFAULT_SD_REQ[0])

    # Version checks
    if hw_version is None:
        click.echo("Error: --hw-version required.")
        return

    if sd_req is None: 
        click.echo("Error: --sd-req required.")
        return

    if application is not None and application_version_internal is None: 
        click.echo('Error: --application-version or --application-version-string'
                   'required with application image.')
        return

    if bootloader is not None and bootloader_version is None: 
        click.echo("Error: --bootloader-version required with bootloader image.")
        return

    sd_req_list = []
    if sd_req is not None:
        try:
            # This will parse any string starting with 0x as base 16.
            sd_req_list = sd_req.split(',')
            sd_req_list = map(int_as_text_to_int, sd_req_list)
        except ValueError:
            raise NordicSemiException("Could not parse value for --sd-req. "
                                      "Hex values should be prefixed with 0x.")

    signer = Signing()
    default_key = signer.load_key(key_file)
    if default_key:
        display_sec_warning()

    package = Package(debug_mode,
                      hw_version,
                      application_version_internal,
                      bootloader_version,
                      sd_req_list,
                      application,
                      bootloader,
                      softdevice,
                      key_file)

    package.generate_package(zipfile_path)

    log_message = "Zip created at {0}".format(zipfile_path)
    click.echo(log_message)

@pkg.command(short_help='Display the contents of a .zip package file.')
@click.argument('zip_file', required=True, type=click.Path())

def display(zip_file): 

    package = Package()
    package.parse_package(zip_file, preserve_work_dir=True)

    click.echo("{0}".format(str(package)))

global_bar = None
def update_progress(progress=0):
    if global_bar:
        global_bar.update(progress)

@cli.group(short_help='Perform a Device Firmware Update over a BLE or serial transport.')
def dfu():
    """
    This set of commands supports Device Firmware Upgrade procedures over both BLE and serial transports.
    """
    pass


@dfu.command(short_help="Update the firmware on a device over a serial connection.")
@click.option('-pkg', '--package',
              help='Filename of the DFU package.',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
              required=True)
@click.option('-p', '--port',
              help='Serial port COM port to which the device is connected.',
              type=click.STRING,
              required=True)
@click.option('-fc', '--flow-control',
              help='To enable flow control set this flag to 1',
              type=click.BOOL,
              required=False)
@click.option('-prn', '--packet-receipt-notification',
              help='Set the packet receipt notification value',
              type=click.INT,
              required=False)
@click.option('-b', '--baud-rate',
              help='Set the baud rate',
              type=click.INT,
              required=False)
def serial(package, port, flow_control, packet_receipt_notification, baud_rate):
    """Perform a Device Firmware Update on a device with a bootloader that supports serial DFU."""
    #raise NotImplementedException('Serial transport currently is not supported')
    """Perform a Device Firmware Update on a device with a bootloader that supports BLE DFU."""

    if port is None:
        click.echo("Please specify serial port.")
        return
        
    if flow_control is None:
        flow_control = DfuTransportSerial.DEFAULT_FLOW_CONTROL
    if packet_receipt_notification is None:
        packet_receipt_notification = DfuTransportSerial.DEFAULT_PRN
    if baud_rate is None:
        baud_rate = DfuTransportSerial.DEFAULT_BAUD_RATE

    logger.info("Using board at serial port: {}".format(port))    
    serial_backend = DfuTransportSerial(com_port=str(port), baud_rate=baud_rate, 
                    flow_control=flow_control, prn=packet_receipt_notification)
    serial_backend.register_events_callback(DfuEvent.PROGRESS_EVENT, update_progress)
    dfu = Dfu(zip_file_path = package, dfu_transport = serial_backend)

    if logger.getEffectiveLevel() > logging.INFO: 
        with click.progressbar(length=dfu.dfu_get_total_size()) as bar:
            global global_bar
            global_bar = bar
            dfu.dfu_send_images()
    else:
        dfu.dfu_send_images()

    click.echo("Device programmed.")
    

def enumerate_ports():
    descs   = BLEDriver.enum_serial_ports()
    if len(descs) == 0:
        return None
    click.echo('Please select connectivity serial port:')
    for i, choice in enumerate(descs):
        click.echo('\t{} : {} - {}'.format(i, choice.port, choice.serial_number))

    index = click.prompt('Enter your choice: ', type=click.IntRange(0, len(descs)))
    return descs[index].port


@dfu.command(short_help="Update the firmware on a device over a BLE connection.")
@click.option('-pkg', '--package',
              help='Filename of the DFU package.',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
              required=True)
@click.option('-ic', '--conn-ic-id',
              help='Connectivity IC ID: NRF51 or NRF52',
              type=click.Choice(['NRF51', 'NRF52']),
              required=True)
@click.option('-p', '--port',
              help='Serial port COM port to which the connectivity IC is connected.',
              type=click.STRING)
@click.option('-n', '--name',
              help='Device name.',
              type=click.STRING)
@click.option('-a', '--address',
              help='Device address.',
              type=click.STRING)
@click.option('-snr', '--jlink_snr',
              help='Jlink serial number.',
              type=click.STRING)
@click.option('-f', '--flash_connectivity',
              help='Flash connectivity firmware automatically. Default: disabled.',
              type=click.BOOL,
              is_flag=True)
def ble(package, conn_ic_id, port, name, address, jlink_snr, flash_connectivity):
    ble_driver_init(conn_ic_id)
    """Perform a Device Firmware Update on a device with a bootloader that supports BLE DFU."""
    if name is None and address is None:
        name = 'DfuTarg'
        click.echo("No target selected. Default device name: {} is used.".format(name))

    if port is None and jlink_snr is not None:
        click.echo("Please specify also serial port.")
        return

    elif port is None:
        port = enumerate_ports()
        if port is None:
            click.echo("\nNo Segger USB CDC ports found, please connect your board.")
            return

    if flash_connectivity:
        flasher = Flasher(serial_port=port, snr = jlink_snr) 
        if flasher.fw_check():
            click.echo("Board already flashed with connectivity firmware.")
        else:
            click.echo("Flashing connectivity firmware...")
            flasher.fw_flash()
            click.echo("Connectivity firmware flashed.")
        flasher.reset()
        time.sleep(1)

    logger.info("Using connectivity board at serial port: {}".format(port))
    ble_backend = DfuTransportBle(serial_port=str(port),
                                  target_device_name=str(name),
                                  target_device_addr=str(address))
    ble_backend.register_events_callback(DfuEvent.PROGRESS_EVENT, update_progress)
    dfu = Dfu(zip_file_path = package, dfu_transport = ble_backend)

    if logger.getEffectiveLevel() > logging.INFO: 
        with click.progressbar(length=dfu.dfu_get_total_size()) as bar:
            global global_bar
            global_bar = bar
            dfu.dfu_send_images()
    else:
        dfu.dfu_send_images()

    click.echo("Device programmed.")

def convert_version_string_to_int(s):
    """Convert from semver string "1.2.3", to integer 10203"""
    numbers = s.split(".")
    js = [10000, 100, 1]
    return sum([js[i] * int(numbers[i]) for i in range(3)])


if __name__ == '__main__':
    cli()
