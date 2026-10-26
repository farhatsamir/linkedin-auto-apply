# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Path to the installed Chromium browser (confirmed on this machine).
# This gets bundled into the app so end users need nothing pre-installed.
CHROMIUM_SOURCE = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright\chromium-1208")
CHROMIUM_DEST = os.path.join("ms-playwright", "chromium-1208")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        (CHROMIUM_SOURCE, CHROMIUM_DEST),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LinkedInAutoApplyHelper",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,   # keep console visible for now, matching current dev behavior
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LinkedInAutoApplyHelper",
)