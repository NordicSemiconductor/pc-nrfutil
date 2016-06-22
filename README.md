# nrfutil

pc-nrfutil is a Python package that includes the `nrfutil` command line utility and the `nordicsemi` library.

## Introduction

This application and its library offer the following features:

* Device Firmware Update package generation
* Cryptographic key generation, management and storage
* Device Firmware Update procedure over Bluetooth Low Energy

## License

See the [license file](LICENSE) for details.

## Versions

There are 2 different and incompatible DFU package formats:

* legacy: used a simple structure and no security
* modern: uses Google's protocol buffers for serialization and can be cryptographically signed

**IMPORTANT NOTE**: SDK 12.0 is yet to be released, the master branch contains pre-release code.

The DFU package format transitioned from legacy to modern in SDK 12.0. Depending on the SDK version
that you are using you will need to select a release of this tool compatible with it:

* Version 0.5.1 generates legacy firmware packages compatible with **nRF SDK 11.0 and older**
* Versions 1.0.0 and later generate modern firmware packages compatible with **nRF SDK 11.1 and newer**

## Prerequisites

To install nrfutil the following prerequisites must be satisfied:

* Python 2.7 (2.7.6 or newer, not Python 3)
* pip (https://pip.pypa.io/en/stable/installing.html)
* setuptools (upgrade to latest version: pip install -U setuptools)
* install required modules: pip install -r requirements.txt

py2exe prerequisites (Windows only):  

* py2exe (Windows only) (v0.6.9) (pip install http://sourceforge.net/projects/py2exe/files/latest/download?source=files)
* VC compiler for Python (Windows only) (http://www.microsoft.com/en-us/download/confirmation.aspx?id=44266)

## Installation

To install the library to the local Python site-packages and script folder:  
```
python setup.py install
```

To generate a self-contained Windows exe version of the utility (Windows only):  
```
python setup.py py2exe
```
NOTE: Some anti-virus programs will stop py2exe from executing correctly when it modifies the .exe file.

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
Below is an example of the generation of a package from an application's `app.hex` file:
```
nrfutil pkg generate --application app.hex --key-file key.pem app_dfu_package.zip
```
#### dfu
This set of commands allow you to perform an actual firmware update over a serial or BLE connection.

##### ble
Perform a full DFU procedure over a BLE connection. This command takes several options that you can list using:
```
nrfutil dfu ble --help
```

##### serial

**Note**: DFU over a serial line is currently disabled

Perform a full DFU procedure over a serial (UART) line. This command takes several options that you can list using:
```
nrfutil dfu serial --help
```
Below is an example of the execution of a DFU procedure of the file generated above over COM3 at 115200 bits per second:
```
nrfutil dfu serial -pkg app_dfu_package.zip -p COM3 -b 115200
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

#### version
This command displays the version of nrfutil.
