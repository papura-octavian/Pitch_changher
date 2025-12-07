# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import platform

block_cipher = None

# Get the base directory
base_dir = os.path.dirname(os.path.abspath(SPEC))

# Determine OS
system = platform.system().lower()

# Collect data files (ffmpeg binaries)
datas = []
if system == "windows":
    ffmpeg_dir = os.path.join(base_dir, "ffmpeg", "windows")
    if os.path.exists(ffmpeg_dir):
        # Include entire ffmpeg/windows directory
        datas.append((ffmpeg_dir, "ffmpeg/windows"))
else:
    ffmpeg_dir = os.path.join(base_dir, "ffmpeg", "linux")
    if os.path.exists(ffmpeg_dir):
        # Include entire ffmpeg/linux directory
        datas.append((ffmpeg_dir, "ffmpeg/linux"))

a = Analysis(
    ['Pitch_Changher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'librosa',
        'soundfile',
        'numpy',
        'pydub',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PitchShifter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # You can add an icon file here if you have one
)

