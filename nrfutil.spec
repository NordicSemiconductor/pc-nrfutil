# -*- mode: python -*-

block_cipher = None

import importlib
import os
import sys

module = importlib.import_module("pc_ble_driver_py")
mod_dir = os.path.dirname(module.__file__)
shlib_dir = os.path.join(os.path.abspath(mod_dir), 'lib')

a = Analysis(['nordicsemi\\__main__.py'],
             binaries=[(shlib_dir, "lib")],
             datas=None,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='nrfutil',
          debug=False,
          strip=False,
          upx=True,
          console=True )
