# pc-nrfutil

[![Latest version](https://img.shields.io/pypi/v/nrfutil.svg)](https://pypi.python.org/pypi/nrfutil)
[![License](https://img.shields.io/pypi/l/nrfutil.svg)](https://pypi.python.org/pypi/nrfutil)

nrfutil is a Python package that includes the `nrfutil` command line utility and the `nordicsemi` library.

## Introduction

This application and its library offer the following features:

* Device Firmware Update package generation
* Cryptographic key generation, management and storage
* Bootloader DFU settings generation and display
* Device Firmware Update procedure over Bluetooth Low Energy
* Device Firmware Update procedure over Thread
* Device Firmware Update procedure over Zigbee

## License

See the [license file](LICENSE) for details.

## Versions

There are 2 different and incompatible DFU package formats:

* legacy: used a simple structure and no security
* modern: uses Google's protocol buffers for serialization and can be cryptographically signed

The DFU package format transitioned from legacy to modern in SDK 12.0. Depending on the SDK version
that you are using you will need to select a release of this tool compatible with it:

* Version 0.5.x generates legacy firmware packages compatible with **nRF SDK 11.0 and older**
* Versions 1.5.0 and later generate modern firmware packages compatible with **nRF SDK 12.0 and newer**
* Versions 4.0.0 and later generate modern firmware packages compatible with **nRF SDK 15.1 and newer**
* Versions 5.0.0 and later generate modern firmware packages compatible with **nRF SDK 15.3 and newer**

**Note**: In order to generate firmware images, compatible with **nRF SDK 12.0 to nRF SDK 15.0**, use `--no-backup` switch during generation of DFU settings.

## Installing from PyPI

To install the latest published version from the Python Package Index simply type:

    pip install nrfutil

This will also retrieve and install all additional required packages.

**Note**: Please refer to the [pc-ble-driver-py PyPI installation note on Windows](https://github.com/NordicSemiconductor/pc-ble-driver-py#installing-from-pypi) if you are running nrfutil on this operating system.

## Downloading precompiled Windows executable

A Windows standalone executable (.exe) of nrfutil is available for download on the [Releases](https://github.com/NordicSemiconductor/pc-nrfutil/releases) page.

## Running and installing from source

You will need to clone the present repository first to run or install nrfutil from source.

### Prerequisites

To install nrfutil from source the following prerequisites must be satisfied:

* [Python 3.7](https://www.python.org/downloads/)
* [pip](https://pip.pypa.io/en/stable/installing.html)
* setuptools (upgrade to latest version): `pip install -U setuptools`

Additionally, if you want to generate a self-contained executable:

* PyInstaller: `pip install pyinstaller`

### Requirements

To obtain and install all required Python packages simply run:

```
pip install -r requirements.txt
```

### Running from source

You can run the program directly without installing it by executing:
```
python ./nordicsemi
```

### Installing from source

To install the library to the local Python site-packages and script folder:
```
python setup.py install
```

To generate a self-contained executable version of the utility:
```
pyinstaller nrfutil.spec

// on Linux prefix with the full path:
pyinstaller /full/path/to/nrfutil.spec
```

**Note**: Some anti-virus programs will stop PyInstaller from executing correctly when it modifies the executable file.

## Usage

To get info on usage of nrfutil:
```
nrfutil --help
```

### Commands
There are several commands that you can use to perform different tasks related to DFU:

#### pkg
This set of commands allow you to generate a package for Device Firmware Update.

##### generate
Generate a package (.zip file) that you can later use with a mobile application or any other means to update the firmware of an nRF5x IC over the air. This command takes several options that you can list using:
```
nrfutil pkg generate --help
```
Below is an example of the generation of a package in debug mode from an application's `app.hex` file:
```
nrfutil pkg generate --debug-mode --application app.hex --key-file key.pem app_dfu_package.zip
```
When using debug mode you don't need to specify versions for hardware and firmware, so you can develop without having to worry about versioning your application. If you want to generate a package for production, you will need to do so without the `--debug-mode` parameter and specify the versions:
```
nrfutil pkg generate --hw-version 51 --sd-req 0x80 --application-version 4 --application app.hex --key-file key.pem app_dfu_package.zip
```
The option `--hw-version` must correspond to the nRF5x IC used, i.e. 51 for nRF51x22 ICs and 52 for nRF52xxx  ICs

The following table lists the FWIDs which are used to identify the SoftDevice versions both included in the package and installed on the target device to perform the required SoftDevice version check:

SoftDevice            | FWID (sd-req)
----------------------| -------------
`s112_nrf52_6.0.0`    | 0xA7
`s112_nrf52_6.1.0`    | 0xB0
`s112_nrf52_6.1.1`    | 0xB8
`s112_nrf52_7.0.0`    | 0xC4
`s112_nrf52_7.0.1`    | 0xCD
`s113_nrf52_7.0.0`    | 0xC3
`s113_nrf52_7.0.1`    | 0xCC
`s130_nrf51_1.0.0`    | 0x67
`s130_nrf51_2.0.0`    | 0x80
`s132_nrf52_2.0.0`    | 0x81
`s130_nrf51_2.0.1`    | 0x87
`s132_nrf52_2.0.1`    | 0x88
`s212_nrf52_2.0.1`    | 0x8D
`s332_nrf52_2.0.1`    | 0x8E
`s132_nrf52_3.0.0`    | 0x8C
`s132_nrf52_3.1.0`    | 0x91
`s132_nrf52_4.0.0`    | 0x95
`s132_nrf52_4.0.2`    | 0x98
`s132_nrf52_4.0.3`    | 0x99
`s132_nrf52_4.0.4`    | 0x9E
`s132_nrf52_4.0.5`    | 0x9F
`s212_nrf52_4.0.5`    | 0x93
`s332_nrf52_4.0.5`    | 0x94
`s132_nrf52_5.0.0`    | 0x9D
`s212_nrf52_5.0.0`    | 0x9C
`s332_nrf52_5.0.0`    | 0x9B
`s132_nrf52_5.1.0`    | 0xA5
`s132_nrf52_6.0.0`    | 0xA8
`s132_nrf52_6.1.0`    | 0xAF
`s132_nrf52_6.1.1`    | 0xB7
`s132_nrf52_7.0.0`    | 0xC2
`s132_nrf52_7.0.1`    | 0xCB
`s140_nrf52_6.0.0`    | 0xA9
`s140_nrf52_6.1.0`    | 0xAE
`s140_nrf52_6.1.1`    | 0xB6
`s140_nrf52_7.0.0`    | 0xC1
`s140_nrf52_7.0.1`    | 0xCA
`s212_nrf52_6.1.1`    | 0xBC
`s332_nrf52_6.1.1`    | 0xBA
`s340_nrf52_6.1.1`    | 0xB9


**Note**: The Thread and Zigbee stacks don't use a SoftDevice but --sd-req option is required for compatibility reasons. You can provide any value for the option as it is ignored during DFU.

Not all combinations of Bootloader, SoftDevice and Application are possible when generating a package. The table below summarizes the support for different combinations.

The following conventions are used on the table:

* BL: Bootloader
* SD: SoftDevice
* APP: Application

Combination   | Supported | Notes
--------------| ----------|-------
BL            | Yes       | **See note 3 below**
SD            | Yes       | **See note 1 below**
APP           | Yes       |
BL + SD       | Yes       |
BL + APP      | No        | Create two .zip packages instead
BL + SD + APP | Yes       | **See note 2 below**
SD + APP      | Yes       | **See notes 1 and 2 below**

**Note 1:** SD must be of the same Major Version as the old BL may not be compatible with the new SD.

**Note 2:** When updating SD (+ BL) + APP the update is done in 2 following connections, unless a custom bootloader is used. First the SD (+ BL) is updated, then the bootloader will disconnect and the (new) BL will start advertising. Second connection to the bootloader will update the APP. However, the two SDs may have different IDs. The first update requires `--sd-req` to be set to the ID of the old SD. Update of the APP requires the ID of the new SD. In that case the new ID must be set using `--sd-id` parameter. This parameter is
was added in nrfutil 3.1.0 and is required since 3.2.0 in case the package should contain SD (+ BL) + APP. Also, since version 3.2.0 the new ID is copied to `--sd-req` list so that
in case of a link loss during APP update the DFU process can be restarted. In that case the new SD would overwrite itself, so `--sd-req` must contain also the ID of the new SD.

**Note 3:** When creating update packages of bootloaders compiled from nRF5 SDK 15.3.0 and higher, nrfutil version 5.0.0 must be used. This is because of changes to the bootloader projects in the nRF5 SDK, and if an old nrfutil version is used the size of the generated packages
will be too large.

Boot validation for a SD or APP update can be activated by setting the `--sd-boot-validation` or `--app-boot-validation` to the preferred
validation method. When boot validation is set, the bootloader will store the validation data (signature, hash or checksum) of the SD and/or
APP in the bootloader setting page and verify the firmware in flash with the validation data on every boot. This is only supported by
bootloaders using bootloader settings version 2, and is supported for both package and settings generation. See 'settings' for more
information on bootloader settings versions.

Update packages of external applications, e.g. updates that are intended for a third party, can be generated by setting the `--external-app` option. When this option is set the receiving device will store the received update, but not activate it. Note: This functionality is experimental in the  nRF5 SDK and not yet used in any examples.

The boolean option `--zigbee` enables the generation of Zigbee update file in addition to the zip package. The following example demonstrates the generation of such update file:
```
nrfutil pkg generate --hw-version 52 --sd-req 0 --application-version 0x01020101 --application nrf52840_xxaa.hex --key-file ../priv.pem --app-boot-validation VALIDATE_ECDSA_P256_SHA256 app_dfu_package.zip --zigbee True --zigbee-manufacturer-id 0xCAFE --zigbee-image-type 0x1234 --zigbee-comment good_image --zigbee-ota-hw-version 52 --zigbee-ota-fw-version 0x01020101 --zigbee-ota-min-hw-version 52 --zigbee-ota-max-hw-version 52
```
The options `--zigbee-ota-hw-version` and `--zigbee-ota-fw-version`refer to the image which is generated to be distributed to the Zigbee OTA Server to be disseminated later into the network. `--zigbee-ota-hw-version` states the hardware version of the Zigbee OTA Server and `--zigbee-ota-fw-version` states the firmware version of this OTA Server accordingly. Everytime the Zigbee OTA Server receives the image for the dissemination its firmware version is updated. This is done to protect from a malicious attack, where the attacker could wear down the Server flash memory by sending the full Zigbee image to be distributed over and over again (thus wearing down the memory). Thus, in order for the OTA Server to accept the image for dissemination, the value passed as a `--zigbee-ota-fw-version` has to be incremented with every transfer of the image.

The options `--zigbee-ota-min-hw-version` and `--zigbee-ota-max-hw-version` refer to the fields in Zigbee OTA header, which determine the range of OTA Client's hardware version for which the image is suitable. Both `--zigbee-ota-min-hw-version` and `--zigbee-ota-max-hw-version` are optional and if used, both must be given.

**Note 4:** The generated Zigbee update file is named according to the recommendation of the Zigbee Specification ([Zigbee Cluster Library Specification 11.5 - Zigbee Document 07-5123-06](http://www.zigbee.org/~zigbeeor/wp-content/uploads/2014/10/07-5123-06-zigbee-cluster-library-specification.pdf)), so the user doesn't provide the name of the Update file.

##### display
Use this option to display the contents of a DFU package in a .zip file.
```
nrfutil pkg display package.zip
```

#### dfu
This set of commands allow you to perform an actual firmware update over a serial, BLE, Thread, Zigbee or ANT connection.

**Note**: When using Homebrew Python on macOS, you may encounter an error: `Fatal Python error: PyThreadState_Get: no current thread Abort trap: 6`. See [issue #46](https://github.com/NordicSemiconductor/pc-nrfutil/issues/46#issuecomment-383930818).

##### ant
Perform a full DFU procedure over an ANT connection. This command takes several options that you can list using:
```
nrfutil dfu ant --help
```
Below is an example of the execution of a DFU procedure of the file generated above over ANT using an nRF52 connectivity IC connected to COM3:
```
nrfutil dfu ant -pkg app_dfu_package.zip --port 0
```

##### ble
Perform a full DFU procedure over a BLE connection. This command takes several options that you can list using:
```
nrfutil dfu ble --help
```
Below is an example of the execution of a DFU procedure of the file generated above over BLE using an nRF52 connectivity IC connected to COM3, where the remote BLE device to be upgraded is called "MyDevice":
```
nrfutil dfu ble -ic NRF52 -pkg app_dfu_package.zip -p COM3 -n "MyDevice" -f
```
The `-f` option instructs nrfutil to actually program the board connected to COM3 with the connectivity software required to operate as a serialized SoftDevice. Use with caution as this will overwrite the contents of the IC's flash memory.

##### Thread
**Note**: DFU over Thread is experimental

Perform a full DFU procedure over a Thread. This command takes several options that you can list using:
```
nrfutil dfu thread --help
```
Below is an example of the execution of a DFU procedure on all devices in a Thread network using a file generated above and a connectivity IC connected to COM3.
```
nrfutil dfu ble -pkg app_dfu_package.zip -p COM3 -f
```
The `-f` option instructs nrfutil to actually program the board connected to COM3 with the connectivity software required to operate as a network co-processor (NCP). Use with caution as this will overwrite the contents of the IC's flash memory.

##### Zigbee
**Note**: DFU over Zigbee OTA is experimental

Perform a full DFU procedure over Zigbee network using ZCL OTA Upgrade Cluster. This command takes several options that you can list using:
```
nrfutil dfu zigbee --help
```
Below is an example of the execution of a DFU procedure using a file generated above using a OTA Upgrade server deployed on a DK with a OTA Upgrade Server operating on the 802.15.4 channel.
```
nrfutil dfu zigbee -f CAFE-1234-good_image.zigbee -snr 683604699 -chan 20
```
**Note**: OTA Server stays on the network after disseminating the OTA DFU image. However, if power-cycled/reset, the node shall not automatically reconnect, and another issuing of command is needed.

##### Serial

Perform a full DFU procedure over a UART serial line. The DFU target shall be configured to use some of its digital I/O pins as UART.

Please note that most Nordic development kit boards have an [interface MCU](http://infocenter.nordicsemi.com/index.jsp?topic=%2Fcom.nordic.infocenter.nrf52%2Fdita%2Fnrf52%2Fdevelopment%2Fnrf52_dev_kit%2Finterf_mcu.html&cp=2_1_4_4)
which transparently [maps digital pins 6 and 8 into a CDC ACM USB interface (A.K.A. "USB virtual serial port")](http://infocenter.nordicsemi.com/index.jsp?topic=%2Fcom.nordic.infocenter.nrf52%2Fdita%2Fnrf52%2Fdevelopment%2Fnrf52_dev_kit%2Fvir_com_port.html&cp=2_1_4_4_1).
Use `serial` DFU mode when communicating with a nRF chip in this way. Otherwise you may
connect the digital I/O pins to an RS232 connector.

This command takes several options that you can list using:

```
nrfutil dfu serial --help
```

Below is an example of the execution of a DFU procedure of the file generated above over COM3:

```
nrfutil dfu serial -pkg app_dfu_package.zip -p COM3
```

Alternatively, the serial number of a connected device can be specified:
```
nrfutil dfu serial -pkg app_dfu_package.zip -snr 00FEFEAB1234
```

##### usb-serial

Perform a full DFU procedure over a CDC ACM USB connection (A.K.A. "USB virtual serial port"). The DFU target shall be a chip with USB pins (i.e. nRF52840), and shall be running a bootloader enabling a USB-CDC interface.

In the case of the nRF52840 development kit board, the `usb-serial` DFU mode is used when communicating with the board through the female USB port marked "nRF USB", which is wired
to the USB pins in the nRF chip.

```
nrfutil dfu usb-serial --help
```

Below is an example of the execution of a DFU procedure of the file generated above over COM3:

```
nrfutil dfu usb-serial -pkg app_dfu_package.zip -p COM3
```

Alternatively, the serial number of a connected device can be specified:
```
nrfutil dfu usb-serial -pkg app_dfu_package.zip -snr 00FEFEAB1234
```

#### keys
This set of commands allow you to generate and display cryptographic keys used to sign and verify DFU packages.

##### generate
Generate a private (signing) key and store it in a file in PEM format.
The following will generate a private key and store it in a file named `private.pem`:
```
nrfutil keys generate private.pem
```

##### display
Display a private (signing) or public (verification) key from a PEM file taken as input. This command takes several options that you can list using:
```
nrfutil keys display --help
```
Below is an example of displaying a public key in code format from the key file generated above:
```
nrfutil keys display --key pk --format code private.pem
```

#### settings
This set of commands allow you to generate and display Bootloader DFU settings, which must be present on the last page of available flash memory for the bootloader to function correctly.

After SDK 15.1 release, there is an additional page used in order to backup Bootloader DFU settings during value updates. The backup is stored in a flash page before the DFU settings. As a result, the generated hex file will contain a copy of DFU setting in order to keep settings and their backup consistent.

In order to generate DFU setting page without backup (compatibility mode), please use `--no-backup` switch.

##### generate
Generate a flash page of Bootloader DFU settings  and store it in a file in .hex format. This command takes several options that you can list using:
```
nrfutil settings generate --help
```
You can generate a .hex file with Bootloader DFU settings matching a particular flashed application by providing the application .hex to nrfutil:
```
nrfutil settings generate --family NRF52 --application app.hex --application-version 3 --bootloader-version 2 --bl-settings-version 1 sett.hex
```

The `--family` setting depends on the nRF IC that you are targeting:

nRF IC    | Family Setting
--------- | --------------
nRF51xxx  | NRF51
nRF52832, nRF52833  | NRF52
nRF52832-QFAB | NRF52QFAB
nRF52810, nRF52811  | NRF52810
nRF52840  | NRF52840

The `--bl-settings-version` depends on the SDK version used. Check the following table to find out which version to use:

SDK Version   | BL Settings Version
------------- | -------------------
12.0 -        | 1
15.3.0 -      | 2

The Bootloader DFU settings version supported and used by the SDK you are using can be found in `nrf_dfu_types.h` in the `bootloader` library.
Even though bootloaders compiled from nRF5 SDK 15.3.0 and higher only use version 2, they can be configured to support settings pages of version 1.
If a new bootloader boots with a version 1 settings page, the bootloader will translate the settings page to version 2 before booting. When using
settings page version 2, boot validation for SD and APP can be generated with the settings page using the `--sd-boot-validation` and
`--app-boot-validation` in the same way as for DFU packages.

##### display

Use this option to display the contents of the Bootloader DFU settings present in a .hex file. The .hex file might be a full dump of the IC's flash memory, obtained with `nrfjprog`:
```
nrfjprog --readcode flash_dump.hex
```
After you have obtained the contents of the flash memory, use nrfutil to decode the Bootloader DFU settings section:
```
nrfutil settings display flash_dump.hex
```
**Note**: nrfutil will autodetect the IC family when displaying the contents of the Bootloader DFU settings.

#### version
This command displays the version of nrfutil.

#### zigbee

Use this command to issue some zigbee-only related commands. Currently only generation of production config is supported.

##### production_config

Use this option to generate the production config .hex file out of the production config description in YAML format. You can provide the offset where the hex should be located.

```
nrfutil zigbee production_config config_description.yaml config_hex.hex --offset 0xFC000
```

## Init Packet customisation

If you want to modify the Init Packet, which is the packet that contains all of the metadata and that is sent before the actual firmware images, you will need to recompile the Google Protocol Buffers `.proto` file and adapt `nrfutil` itself.

Note that if you modify the format of the Init Packet, you *will need to do the same in the bootloader*, meaning that you will have to recompile it to adapt it to the new format.

### Modifying the Protocol Buffers file

Edit `dfu-cc.proto` and modify the Init packet to suit your needs. Additional information on the format of `.proto` files can be found [here](https://developers.google.com/protocol-buffers/).

### Protocol Buffers versions

Both versions 2 and 3 of Protocol Buffers library can be used, but make sure that the *language version* is version 2, a.k.a **proto2**. A new *syntax* keyword was added in Protocol Buffers v3 to specify language version of a .proto file. If `syntax = "proto3";` is *not* included, then **proto2** language version will be used.

### Compiling the Protocol Buffers file

After you have modified the `.proto` file you will need to compile it to generate the corresponding Python file that will be then usable from the `nrfutil` source code. To do that install the Protocol Buffers compiler from [here](https://developers.google.com/protocol-buffers/docs/downloads) and then execute:

```
$ protoc --python_out=<dest_folder> dfu-cc.proto
```
Where `<dest_folder>` is an empty folder where the Protocol Buffers compiler will write its output.

After compilation is complete, a file named `<dest_folder>/dfu_cc_pb2.py` will be created. You can then use this file to overwrite the one in [nordicsemi/dfu](nordicsemi/dfu) to start using the new Init Packet format.

### Adapting nrfutil to the new Init Packet format

Once you have the customized `dfu_cc_pb2.py` file in your repository you will need to adapt the actual tool to conform to the new format you have designed. To do that you will need to alter several of the Python source files included, as well as potentially having to modify the command-line options to fit the contents of your Init Packet.
Refer to [init_packet_pb.py](nordicsemi/dfu/init_packet_pb.py) and [package.py](nordicsemi/dfu/package.py) for the contents themselves, and to [\_\_main\_\_.py](nordicsemi/__main__.py) for the command-line options.

### Adapting the bootloader to the new Init Packet format

Since you have modified the Init Packet format you will have to do the same with the embedded bootloader, which can be found in the Nordic nRF5 SDK under `examples/dfu/bootloader_secure`.
