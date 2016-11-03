#!/usr/bin/env python
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

"""
Setup script for nrfutil.

USAGE:
    python setup.py install

"""
import os
import platform

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
from pip.req import parse_requirements

from nordicsemi import version

excludes = ["Tkconstants",
            "Tkinter",
            "tcl",
            "pickle",
            "unittest",
            "pyreadline"]

# DFU component cli interface
includes = ["nordicsemi.dfu.dfu"]

packages = []

dll_excludes = [
    "w9xpopen.exe",
    "OLEAUT32.DLL",
    "OLE32.DLL",
    "USER32.DLL",
    "SHELL32.DLL",
    "ADVAPI32.DLL",
    "KERNEL32.DLL",
    "WS2_32.DLL",
    "GDI32.DLL"]

build_dir = os.environ.get("NRFUTIL_BUILD_DIR", "./{}".format(version.NRFUTIL_VERSION))
description = """A Python package that includes the nrfutil utility and the nordicsemi library"""

# parse_requirements() returns generator of pip.req.InstallRequirement objects
install_reqs = parse_requirements("requirements.txt", session=False)
# reqs is a list of requirements as strings
reqs = [str(ir.req) for ir in install_reqs]

class NoseTestCommand(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import nose
        nose.run_exit(argv=['nosetests', '--with-xunit', '--xunit-file=test-reports/unittests.xml'])

setup(
    name="nrfutil",
    version=version.NRFUTIL_VERSION,
    license="Modified BSD License",
    author = "Nordic Semiconductor ASA",
    url="https://github.com/NordicSemiconductor/pc-nrfutil",
    description="Nordic Semiconductor nrfutil utility and Python library",
    long_description=description,
    packages=find_packages(exclude=["tests.*", "tests"]),
    package_data = { 
                '': ['../requirements.txt']
    },
    install_requires=reqs,
    zipfile=None,
    tests_require=[
        "nose >= 1.3.4",
        "behave"
    ],
    zip_safe=False,
    classifiers=[
        'Development Status :: 4 - Beta',

        'Intended Audience :: Developers',
        
        'Operating System :: MacOS',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX :: Linux',

        'Topic :: System :: Networking',
        'Topic :: System :: Hardware :: Hardware Drivers',
        'Topic :: Software Development :: Embedded Systems',
        
        'License :: Other/Proprietary License',

        'Programming Language :: Python :: 2.7',
    ],
    keywords = 'nordic nrf51 nrf52 ble bluetooth dfu ota softdevice serialization nrfutil pc-nrfutil',
    cmdclass={
        'test': NoseTestCommand
    },
    entry_points='''
      [console_scripts]
      nrfutil = nordicsemi.__main__:cli
    ''',
    console=[{
        "script": "./nordicsemi/__main__.py",
        "dest_base": "nrfutil"
    }],
)
