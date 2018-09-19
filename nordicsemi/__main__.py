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
import ipaddress
import signal

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
from nordicsemi.dfu.dfu_transport import DfuEvent, TRANSPORT_LOGGING_LEVEL
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

def display_nokey_warning():
    default_nokey_warning = """
|===============================================================|
|##      ##    ###    ########  ##    ## #### ##    ##  ######  |
|##  ##  ##   ## ##   ##     ## ###   ##  ##  ###   ## ##    ## |
|##  ##  ##  ##   ##  ##     ## ####  ##  ##  ####  ## ##       |
|##  ##  ## ##     ## ########  ## ## ##  ##  ## ## ## ##   ####|
|##  ##  ## ######### ##   ##   ##  ####  ##  ##  #### ##    ## |
|##  ##  ## ##     ## ##    ##  ##   ###  ##  ##   ### ##    ## |
| ###  ###  ##     ## ##     ## ##    ## #### ##    ##  ######  |
|===============================================================|
|You are not providing a signature key, which means the DFU     |
|files will not be signed, and are vulnerable to tampering.     |
|This is only compatible with a signature-less bootloader and is|
|not suitable for production environments.                      |
|===============================================================|
"""
    click.echo("{}".format(default_nokey_warning))

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

def display_settings_backup_warning():
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
|You are generating a DFU settings page with backup page        |
|included. This is only required for bootloaders from nRF SDK   |
|15.1 and newer. If you want to skip backup page genetation,    |
|use --no-backup option.                                        |
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

def pause():
    while True:
        try:
            raw_input()
        except (KeyboardInterrupt, EOFError):
            break

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
              help='Increase verbosity of output. Can be specified more than once (up to -v -v -v -v).',
              count=True)
@click.option('-o', '--output',
              help='Log output to file',
              metavar='<filename>')
def cli(verbose, output):
    #click.echo('verbosity: %s' % verbose)
    if verbose == 0:
        log_level = logging.ERROR
    elif verbose == 1:
        log_level = logging.WARNING
    elif verbose == 2:
        log_level = logging.INFO
    elif verbose == 3:
        log_level = logging.DEBUG
    else:
        # Custom level, logs all the bytes sent/received over the wire/air
        log_level = TRANSPORT_LOGGING_LEVEL

    logging.basicConfig(format='%(asctime)s %(message)s', level=log_level)

    if (output):
        root = logging.getLogger('')
        fh = logging.FileHandler(output)
        fh.setLevel(log_level)
        fh.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        root.addHandler(fh)

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
              help='nRF IC family: NRF51 or NRF52 or NRF52QFAB or NRF52810 or NRF52840',
              type=click.Choice(['NRF51', 'NRF52', 'NRF52QFAB', 'NRF52810', 'NRF52840']))
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
@click.option('--start-address',
              help='Custom start address for the settings page. If not specified, '
                   'then the last page of the flash is used.',
              type=BASED_INT_OR_NONE)
@click.option('--no-backup',
              help='Do not overwrite DFU settings backup page. If not specified, '
                   'than the resulting .hex file will contain a copy of DFU settings, '
                   'that will overwrite contents of DFU settings backup page.',
              type=click.BOOL,
              is_flag=True,
              required=False)
@click.option('--backup-address',
              help='Address of the DFU settings backup page inside flash. '
                   'By default, the backup page address is placed one page below DFU settings. '
                   'The value is precalculated based on configured settings address '
                   '(<DFU_settings_addrsss> - 0x1000).',
              type=BASED_INT_OR_NONE)

def generate(hex_file,
        family,
        application,
        application_version,
        application_version_string,
        bootloader_version,
        bl_settings_version,
        start_address,
        no_backup,
        backup_address):

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

    if (no_backup is not None) and (backup_address is not None):
        click.echo("Error: Bootloader DFU settings backup page cannot be specified if backup is disabled.")
        return

    if no_backup is None:
        no_backup = False

    if no_backup == False:
        display_settings_backup_warning()

    if (start_address is not None) and (backup_address is None):
        click.echo("WARNING: Using default offset in order to calculate bootloader settings backup page")

    sett = BLDFUSettings()
    sett.generate(arch=family, app_file=application, app_ver=application_version_internal, bl_ver=bootloader_version, bl_sett_ver=bl_settings_version, custom_bl_sett_addr=start_address, no_backup=no_backup, backup_address=backup_address)
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


@cli.group(short_help='Display or generate a DFU package (zip file).')
def pkg():
    """
    This set of commands supports Nordic DFU package generation.
    """
    pass


@pkg.command(short_help='Generate a zip file for performing DFU.')
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
              required=True,
              type=BASED_INT)
@click.option('--sd-req',
              help='The SoftDevice requirements. A comma-separated list of SoftDevice firmware IDs '
                   '(1 or more) of which one must be present on the target device. Each item on the '
                   'list must be a two- or four-digit hex number prefixed with \"0x\" (e.g. \"0x12\", '
                   '\"0x1234\").\n'
                   'A non-exhaustive list of well-known values to use with this option follows:'
                   '\n|s112_nrf52_6.0.0|0xA7|'
                   '\n|s112_nrf52_6.1.0|0xB0|'
                   '\n|s130_nrf51_1.0.0|0x67|'
                   '\n|s130_nrf51_2.0.0|0x80|'
                   '\n|s132_nrf52_2.0.0|0x81|'
                   '\n|s130_nrf51_2.0.1|0x87|'
                   '\n|s132_nrf52_2.0.1|0x88|'
                   '\n|s132_nrf52_3.0.0|0x8C|'
                   '\n|s132_nrf52_3.1.0|0x91|'
                   '\n|s132_nrf52_4.0.0|0x95|'
                   '\n|s132_nrf52_4.0.2|0x98|'
                   '\n|s132_nrf52_4.0.3|0x99|'
                   '\n|s132_nrf52_4.0.4|0x9E|'
                   '\n|s132_nrf52_4.0.5|0x9F|'
                   '\n|s132_nrf52_5.0.0|0x9D|'
                   '\n|s132_nrf52_5.1.0|0xA5|'
                   '\n|s132_nrf52_6.0.0|0xA8|'
                   '\n|s132_nrf52_6.1.0|0xAF|'
                   '\n|s140_nrf52_6.0.0|0xA9|'
                   '\n|s140_nrf52_6.1.0|0xAE|',
              type=click.STRING,
              required=True,
              multiple=True)
@click.option('--sd-id',
              help='The new SoftDevice ID to be used as --sd-req for the Application update in case the ZIP '
                   'contains a SoftDevice and an Application.',
              type=click.STRING,
              multiple=True)
@click.option('--softdevice',
              help='The SoftDevice firmware file.',
              type=click.STRING)
@click.option('--key-file',
              help='The private (signing) key in PEM fomat.',
              required=False,
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False))
@click.option('--zigbee',
              help='Create an image and distribution package for Zigbee DFU server.',
              required=False,
              type=click.BOOL)
@click.option('--zigbee-manufacturer-id',
              help='Manufacturer ID to be used in Zigbee OTA header.',
              required=False,
              type=BASED_INT)
@click.option('--zigbee-image-type',
              help='Image type to be used in Zigbee OTA header.',
              required=False,
              type=BASED_INT)
@click.option('--zigbee-comment',
              help='Firmware comment to be used in Zigbee OTA header.',
              required=False,
              type=click.STRING)
def generate(zipfile,
           debug_mode,
           application,
           application_version,
           application_version_string,
           bootloader,
           bootloader_version,
           hw_version,
           sd_req,
           sd_id,
           softdevice,
           key_file,
           zigbee,
           zigbee_manufacturer_id,
           zigbee_image_type,
           zigbee_comment):
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

    if len(sd_id) > 1:
        click.echo("Please specify SoftDevice requirements as a comma-separated list: --sd-id 0xXXXX,0xYYYY,...")
        return
    elif len(sd_id) == 0:
        sd_id = None
    else:
        sd_id = sd_id[0]
        if sd_id == 'none':
            sd_id = None

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
                   ' required with application image.')
        return

    if bootloader is not None and bootloader_version is None:
        click.echo("Error: --bootloader-version required with bootloader image.")
        return

    if application is not None and softdevice is not None and sd_id is None:
        click.echo("Error: --sd-id required with softdevice and application images.")
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

    sd_id_list = []
    if sd_id is not None:
        try:
            # This will parse any string starting with 0x as base 16.
            sd_id_list = sd_id.split(',')
            sd_id_list = map(int_as_text_to_int, sd_id_list)

            # Copy all IDs from sd_id_list to sd_req_list, without duplicates.
            # This ensures that the softdevice update can be repeated in case
            # SD+(BL)+App update terminates during application update after the
            # softdevice was already updated (with new ID). Such update would
            # have to be repeated and the softdevice would have to be sent again,
            # this time updating itself.
            sd_req_list += set(sd_id_list) - set(sd_req_list)
        except ValueError:
            raise NordicSemiException("Could not parse value for --sd-id. "
                                      "Hex values should be prefixed with 0x.")
    else:
        sd_id_list = sd_req_list

    if key_file is None:
        display_nokey_warning()
    else:
        signer = Signing()
        default_key = signer.load_key(key_file)
        if default_key:
            display_sec_warning()

    if zigbee_comment is None:
        zigbee_comment = ''
    elif any(ord(char) > 127 for char in zigbee_comment): # Check if all the characters belong to the ASCII range
        click.echo('Warning: Non-ASCII characters in the comment are not allowed. Discarding comment.')
        zigbee_comment = ''
    elif len(zigbee_comment) > 30:
        click.echo('Warning: truncating the comment to 30 bytes.')
        zigbee_comment = zigbee_comment[:30]

    if zigbee_manufacturer_id is None:
        zigbee_manufacturer_id = 0xFFFF

    if zigbee_image_type is None:
        zigbee_image_type = 0xFFFF

    package = Package(debug_mode,
                      hw_version,
                      application_version_internal,
                      bootloader_version,
                      sd_req_list,
                      sd_id_list,
                      application,
                      bootloader,
                      softdevice,
                      key_file,
                      zigbee,
                      zigbee_manufacturer_id,
                      zigbee_image_type,
                      zigbee_comment)

    package.generate_package(zipfile_path)

    # Regenerate BLE DFU package for Zigbee DFU purposes.
    if zigbee:
        from shutil import copyfile
        from os import remove

        log_message = "Zigbee update created at {0}".format(package.zigbee_ota_file.filename)
        click.echo(log_message)

        binfile = package.zigbee_ota_file.filename.replace(".zigbee", ".bin")
        copyfile(package.zigbee_ota_file.filename, binfile)
        package = Package(debug_mode,
                          hw_version,
                          application_version_internal,
                          bootloader_version,
                          sd_req_list,
                          sd_id_list,
                          binfile,
                          bootloader,
                          softdevice,
                          key_file)

        package.generate_package(zipfile_path)
        remove(binfile)

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

@cli.group(short_help='Perform a Device Firmware Update over, BLE, Thread, or serial transport given a DFU package (zip file).')
def dfu():
    """
    This set of commands supports Device Firmware Upgrade procedures over both BLE and serial transports.
    """
    pass

def do_serial(package, port, connect_delay, flow_control, packet_receipt_notification, baud_rate, ping):

    if flow_control is None:
        flow_control = DfuTransportSerial.DEFAULT_FLOW_CONTROL
    if packet_receipt_notification is None:
        packet_receipt_notification = DfuTransportSerial.DEFAULT_PRN
    if baud_rate is None:
        baud_rate = DfuTransportSerial.DEFAULT_BAUD_RATE
    if ping is None:
        ping = False

    logger.info("Using board at serial port: {}".format(port))
    serial_backend = DfuTransportSerial(com_port=str(port), baud_rate=baud_rate,
                    flow_control=flow_control, prn=packet_receipt_notification, do_ping=ping)
    serial_backend.register_events_callback(DfuEvent.PROGRESS_EVENT, update_progress)
    dfu = Dfu(zip_file_path = package, dfu_transport = serial_backend, connect_delay = connect_delay)

    if logger.getEffectiveLevel() > logging.INFO:
        with click.progressbar(length=dfu.dfu_get_total_size()) as bar:
            global global_bar
            global_bar = bar
            dfu.dfu_send_images()
    else:
        dfu.dfu_send_images()

    click.echo("Device programmed.")

@dfu.command(short_help="Update the firmware on a device over a USB serial connection. The DFU target must be a chip with USB pins (i.e. nRF52840) and provide a USB ACM CDC serial interface.")
@click.option('-pkg', '--package',
              help='Filename of the DFU package.',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
              required=True)
@click.option('-p', '--port',
              help='Serial port address to which the device is connected. (e.g. COM1 in windows systems, /dev/ttyACM0 in linux/mac)',
              type=click.STRING,
              required=True)
@click.option('-cd', '--connect-delay',
              help='Delay in seconds before each connection to the target device during DFU. Default is 3.',
              type=click.INT,
              required=False)
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
def usb_serial(package, port, connect_delay, flow_control, packet_receipt_notification, baud_rate):
    """Perform a Device Firmware Update on a device with a bootloader that supports USB serial DFU."""

    do_serial(package, port, connect_delay, flow_control, packet_receipt_notification, baud_rate, False)


@dfu.command(short_help="Update the firmware on a device over a UART serial connection. The DFU target must be a chip using digital I/O pins as an UART.")
@click.option('-pkg', '--package',
              help='Filename of the DFU package.',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
              required=True)
@click.option('-p', '--port',
              help='Serial port address to which the device is connected. (e.g. COM1 in windows systems, /dev/ttyACM0 in linux/mac)',
              type=click.STRING,
              required=True)
@click.option('-cd', '--connect-delay',
              help='Delay in seconds before each connection to the target device during DFU. Default is 3.',
              type=click.INT,
              required=False)
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
def serial(package, port, connect_delay, flow_control, packet_receipt_notification, baud_rate):
    """Perform a Device Firmware Update on a device with a bootloader that supports UART serial DFU."""

    do_serial(package, port, connect_delay, flow_control, packet_receipt_notification, baud_rate, True)


def enumerate_ports():
    descs   = BLEDriver.enum_serial_ports()
    if len(descs) == 0:
        return None
    click.echo('Please select connectivity serial port:')
    for i, choice in enumerate(descs):
        click.echo('\t{} : {} - {}'.format(i, choice.port, choice.serial_number))

    index = click.prompt('Enter your choice: ', type=click.IntRange(0, len(descs)))
    return descs[index].port

def get_port_by_snr(snr):
    serial_ports = BLEDriver.enum_serial_ports()
    try:
        serial_port = [d.port for d in serial_ports if d.serial_number.lstrip('0') == snr][0]
    except IndexError:
        raise NordicSemiException('board not found')
    return serial_port

@dfu.command(short_help="Update the firmware on a device over a BLE connection.")
@click.option('-pkg', '--package',
              help='Filename of the DFU package.',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
              required=True)
@click.option('-ic', '--conn-ic-id',
              help='Connectivity IC family: NRF51 or NRF52',
              type=click.Choice(['NRF51', 'NRF52']),
              required=True)
@click.option('-p', '--port',
              help='Serial port COM port to which the connectivity IC is connected.',
              type=click.STRING)
@click.option('-cd', '--connect-delay',
              help='Delay in seconds before each connection to the target device during DFU. Default is 3.',
              type=click.INT,
              required=False)
@click.option('-n', '--name',
              help='Device name.',
              type=click.STRING)
@click.option('-a', '--address',
              help='BLE address of the DFU target device.',
              type=click.STRING)
@click.option('-snr', '--jlink_snr',
              help='Jlink serial number for the connectivity IC.',
              type=click.STRING)
@click.option('-f', '--flash_connectivity',
              help='Flash connectivity firmware automatically. Default: disabled.',
              type=click.BOOL,
              is_flag=True)
def ble(package, conn_ic_id, port, connect_delay, name, address, jlink_snr, flash_connectivity):
    """
    Perform a Device Firmware Update on a device with a bootloader that supports BLE DFU.
    This requires a second nRF device, connected to this computer, with connectivity firmware
    loaded. The connectivity device will perform the DFU procedure onto the target device.
    """
    ble_driver_init(conn_ic_id)
    if name is None and address is None:
        name = 'DfuTarg'
        click.echo("No target selected. Default device name: {} is used.".format(name))

    if port is None and jlink_snr is not None:
        port = get_port_by_snr(jlink_snr)

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
    dfu = Dfu(zip_file_path = package, dfu_transport = ble_backend, connect_delay = connect_delay)

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

@dfu.command(short_help="Update the firmware on a device over a Thread connection.")
@click.option('-pkg', '--package',
              help='Filename of the DFU package.',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
              required=True)
@click.option('-p', '--port',
              help='Serial port COM port to which the NCP is connected.',
              type=click.STRING)
@click.option('-a', '--address',
              help='Device IPv6 address. If address is not specified then perform DFU '
                   'on all capable devices. If multicast address is specified (FF03::1), '
                   'perform multicast DFU.',
              type=click.STRING)
@click.option('-sp', '--server_port',
              help='UDP port to which the DFU server binds. If not specified the 5683 is used.',
              type=click.INT,
              default=5683)
@click.option('--panid',
              help='802.15.4 PAN ID. If not specified then 1234 is used as PAN ID.',
              type=click.INT)
@click.option('--channel',
              help='802.15.4 Channel. If not specified then channel 11 is used.',
              type=click.INT)
@click.option('-snr', '--jlink_snr',
              help='Jlink serial number.',
              type=click.STRING)
@click.option('-f', '--flash_connectivity',
              help='Flash NCP connectivity firmware automatically. Default: disabled.',
              type=click.BOOL,
              is_flag=True)
@click.option('-s', '--sim',
              help='Use software NCP and connect to the OT simulator.',
              type=click.BOOL,
              is_flag=True)
@click.option('-r', '--rate',
              help="Multicast upload rate in blocks per second.",
              type=click.FLOAT)
@click.option('-rs', '--reset_suppress',
              help='Suppress device reset after finishing DFU for a given number of milliseconds. ' +
                   'If -1 is given then suppress indefinatelly.',
              type = click.INT,
              metavar = '<delay_in_ms>')

def thread(package, port, address, server_port, panid, channel, jlink_snr, flash_connectivity,
           sim, rate, reset_suppress):
    """
    Perform a Device Firmware Update on a device that supports Thread DFU.
    This requires a second nRF device, connected to this computer, with Thread Network
    CoProcessor (NCP) firmware loaded. The NCP device will perform the DFU procedure onto
    the target device.
    """
    ble_driver_init('NRF52')
    from nordicsemi.thread import tncp
    from nordicsemi.thread.dfu_thread import create_dfu_server
    from nordicsemi.thread.tncp import NCPTransport
    from nordicsemi.thread.ncp_flasher import NCPFlasher

    mcast_dfu = False

    if address is None:
        address = ipaddress.ip_address(u"ff03::1")
        click.echo("Address not specified. Using ff03::1 (all Thread nodes)")
    else:
        try:
            address = ipaddress.ip_address(address)
            mcast_dfu = address.is_multicast
        except:
            click.echo("Invalid IPv6 address")
            return 1

    if (not sim):
        if port is None and jlink_snr is None:
            click.echo("Please specify serial port or Jlink serial number.")
            return 2

        elif port is None:
            port = get_port_by_snr(jlink_snr)
            if port is None:
                click.echo("\nNo Segger USB CDC ports found, please connect your board.")
                return 3

        stream_descriptor = 'u:' + port
        click.echo("Using connectivity board at serial port: {}".format(port))
    else:
        stream_descriptor = 'p:' + Flasher.which('ot-ncp') + ' 30'
        click.echo("Using ot-ncp binary: {}".format(stream_descriptor))

    if flash_connectivity:
        flasher = NCPFlasher(serial_port=port, snr = jlink_snr)
        if flasher.fw_check():
            click.echo("Board already flashed with connectivity firmware.")
        else:
            click.echo("Flashing connectivity firmware...")
            flasher.fw_flash()
            click.echo("Connectivity firmware flashed.")

        flasher.reset()

        # Delay is required because NCP needs time to initialize.
        time.sleep(1.0)

    config = tncp.NCPTransport.get_default_config()
    if (panid):
        config[tncp.NCPTransport.CFG_KEY_PANID] = panid
    if (channel):
        config[tncp.NCPTransport.CFG_KEY_CHANNEL] = channel
    if (flash_connectivity):
        config[tncp.NCPTransport.CFG_KEY_RESET] = False

    opts = type('DFUServerOptions', (object,), {})()
    opts.rate = rate
    opts.reset_suppress = reset_suppress
    opts.mcast_dfu = mcast_dfu

    transport = NCPTransport(server_port, stream_descriptor, config)
    dfu = create_dfu_server(transport, package, opts)

    try:
        sighandler = lambda signum, frame : transport.close()
        signal.signal(signal.SIGINT, sighandler)
        signal.signal(signal.SIGTERM, sighandler)

        transport.open()
        # Delay DFU trigger until NCP promotes to a router (6 seconds by default)
        click.echo("Waiting for NCP to promote to a router...")
        time.sleep(6.0)
        dfu.trigger(address, 3)
        click.echo("Thread DFU server is running... Press <Ctrl + D> to stop.")
        pause()
        click.echo("Terminating")

    except Exception as e:
        logger.exception(e)
    finally:
        transport.close()

@dfu.command(short_help="Update the firmware on a device over a Zigbee connection.")
@click.option('-f', '--file',
              help='Filename of the Zigbee OTA Upgrade file.',
              type=click.Path(exists=True, resolve_path=True, file_okay=True, dir_okay=False),
              required=True)
@click.option('-snr', '--jlink_snr',
              help='JLink serial number of the devboard which shall serve as a OTA Server cluster',
              type=click.STRING)
@click.option('-chan', '--channel',
              help='802.15.4 Channel that the OTA server will use',
              type=click.INT)

def zigbee(file, jlink_snr, channel):
    """
    Perform a Device Firmware Update on a device that implements a  Zigbee OTA Client cluster.
    This requires a second nRF device, connected to this computer, which shall serve as a
    OTA Server cluster.
    """
    ble_driver_init('NRF52')
    from nordicsemi.zigbee.ota_flasher import OTAFlasher
    of = OTAFlasher(fw = file, channel = channel, snr = jlink_snr)

    if of.fw_check():
        click.echo("Board already flashed with connectivity firmware.")
    else:
        click.echo("Flashing connectivity firmware...")
        of.fw_flash()
        click.echo("Connectivity firmware flashed.")

    of.reset()
    time.sleep(3.0) # A delay to init the OTA Server flashed on the devboard and the CLI inside of it
    of.setup_channel()

if __name__ == '__main__':
    cli()
