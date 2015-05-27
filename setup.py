#!/usr/bin/env python

# Copyright (c) 2015 Nordic Semiconductor. All Rights Reserved.
#
# The information contained herein is property of Nordic Semiconductor ASA.
# Terms and conditions of usage are described in detail in NORDIC
# SEMICONDUCTOR STANDARD SOFTWARE LICENSE AGREEMENT.
#
# Licensees are granted free, non-transferable use of the information. NO
# WARRANTY of ANY KIND is provided. This heading must NOT be removed from
# the file.

"""
Setup script for nrfutil.

USAGE:
    python setup.py install
    python setup.py py2exe

"""
import platform

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
import os

if platform.system() == 'Windows':
    import py2exe  # Required even if it is not used in this file. This import adds py2exe to distutils.

excludes = ["Tkconstants",
            "Tkinter",
            "tcl",
            "pickle",
            "unittest",
            "pyreadline"]

# DFU component cli interface
includes = [
    "nordicsemi.dfu.dfu",
    "nordicsemi.dfu.dfu_transport_serial"]

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

nrfutil_version = os.environ.get("NRFUTIL_VERSION", "0.0.0")
build_dir = os.environ.get("NRFUTIL_BUILD_DIR", "./{}".format(nrfutil_version))
description = """A Python package that includes the nrfutil utility and the nordicsemi library"""


class NoseTestCommand(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import nose
        nose.run_exit(argv=['nosetests', '--with-xunit'])

common_requirements=[
    "pyserial >= 2.7",
    "enum34 >= 1.0.4",
    "click",
]


setup(
    name="nrfutil",
    version=nrfutil_version,
    license="Nordic Semicondictor proprietary license",
    url="https://github.com/NordicSemiconductor/pc-nrfutil",
    description="Nordic Semiconductor nrfutil utility and Python library",
    long_description=description,
    packages=find_packages(exclude=["tests.*", "tests"]),
    include_package_data=False,
    install_requires=common_requirements,
    setup_requires=common_requirements,
    zipfile=None,
    tests_require=[
        "nose >= 1.3.4",
        "behave"
    ],
    zip_safe=False,
    classifiers=[
        "Programming Language :: Python :: 2.7",
    ],
    cmdclass={'test': NoseTestCommand},
    entry_points='''
      [console_scripts]
      nrfutil = nordicsemi.__main__:cli
    ''',
    console=[{
        "script": "./nordicsemi/__main__.py",
        "dest_base": "nrfutil"
    }],
    options={
        "py2exe": {
            "includes": includes,
            "excludes": excludes,
            "ascii": False,
            "bundle_files": 1,  # 1 for bunding into exe, 3 for to distdir
            "dist_dir": build_dir,
            "verbose": True,
            "dll_excludes": dll_excludes
        }
    }
)
