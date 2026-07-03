# -*- mode: python ; coding: utf-8 -*-

import os

base_dir = os.path.dirname(os.path.abspath(SPEC))

# FFmpeg is intentionally NOT bundled inside the executable: the installer /
# AppImage ships it next to the app instead. Bundling it in a onefile exe
# would double the download size and slow down every launch (extraction).
datas = []
icon_png = os.path.join(base_dir, "icons", "icon.png")
if os.path.exists(icon_png):
    datas.append((icon_png, "icons"))
assets_dir = os.path.join(base_dir, "assets")
if os.path.exists(assets_dir):
    datas.append((assets_dir, "assets"))

a = Analysis(
    ['Pitch_Changher.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim libraries PyInstaller tends to pull in via numpy/librosa
        'matplotlib',
        'tkinter',
        'IPython',
        'pandas',
        'PIL',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

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
    icon='icons/icon.ico' if os.path.exists('icons/icon.ico') else None,
)
