# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build spec for Tone Generator.

Produces a single portable Windows executable at dist\\ToneGenerator.exe
that includes wxPython, NumPy, and the PortAudio DLL that sounddevice
needs at runtime.

Usage:
    pip install -r requirements.txt
    pip install pyinstaller
    pyinstaller tone_generator.spec

The resulting dist\\ToneGenerator.exe has no external dependencies and
can be copied to any Windows machine.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, copy_metadata

# sounddevice ships PortAudio DLLs in the _sounddevice_data package. Collect
# them explicitly so the single-file executable can play audio on machines
# without a separate PortAudio installation.
sd_datas = collect_data_files("_sounddevice_data") + copy_metadata("sounddevice")
sd_binaries = collect_dynamic_libs("_sounddevice_data")
sd_hidden = ["_sounddevice", "_sounddevice_data"]

a = Analysis(
    ["tone_generator.py"],
    pathex=[],
    binaries=sd_binaries,
    datas=sd_datas,
    hiddenimports=sd_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ToneGenerator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="version_info.txt",
)
