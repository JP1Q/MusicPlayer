# -*- mode: python ; coding: utf-8 -*-


import glob
import os

# Bundle all PNG assets found in the project root (so custom images are included
# without manually editing this spec every time).
# NOTE: spec execution context does not always provide __file__, so we use CWD.
_ROOT = os.path.abspath(os.getcwd())
_PNG_DATAS = [(p, '.') for p in glob.glob(os.path.join(_ROOT, '*.png'))]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=_PNG_DATAS,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='UkasCoUmis',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='UkasCoUmis',
)
