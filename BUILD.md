# Build Instructions

This document explains how to build installers for PitchShifter.

## Prerequisites

- **Windows**: Python 3.10+, [Inno Setup](https://jrsoftware.org/isdl.php)
- **Linux**: Python 3.10+ (AppImageTool is downloaded automatically)

FFmpeg binaries are **not** tracked in git. The build scripts download them
automatically via `scripts/get_ffmpeg.py` (Windows: gyan.dev release build,
Linux: johnvansickle static build).

## Quick Build

### Windows

```batch
build_installer_windows.bat
```

This creates a venv, installs dependencies, downloads FFmpeg, builds the
executable with PyInstaller and compiles the installer with Inno Setup.

Output: `installer/PitchShifter-Setup-<version>.exe`

### Linux

```bash
./build_appimage.sh [version]
```

Output: `PitchShifter-[version]-x86_64.AppImage`

## Manual Build Steps

### 1. Build the executable only

- **Windows**: `build_windows.bat` → `dist/PitchShifter.exe`
- **Linux**: `./build_linux.sh` → `dist/PitchShifter`

The scripts copy `ffmpeg/` next to the executable so it runs standalone.

### 2. Create the installer

- **Windows**:
  ```batch
  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.1.0 installer.iss
  ```
- **Linux**: `./build_appimage.sh 1.1.0`

## Automated Builds with GitHub Actions

The **Build Installers** workflow (`.github/workflows/build.yml`) runs on
every `v*` tag and on manual dispatch:

1. Create and push a tag:
   ```bash
   git tag v1.1.0
   git push origin v1.1.0
   ```
2. The workflow builds the Windows installer and the Linux AppImage in
   parallel and attaches both to the GitHub Release for that tag.
3. For manual runs (Actions → Build Installers → Run workflow), the
   installers are available as workflow artifacts instead.

## FFmpeg lookup order (at runtime)

1. `ffmpeg/<os>/ffmpeg[.exe]` next to the executable (installed layout)
2. `../ffmpeg/<os>/ffmpeg` relative to the executable (AppImage layout)
3. `ffmpeg` from `PATH`

## Troubleshooting

- **PyInstaller "Module not found"**: add the module to `hiddenimports` in
  `Pitch_Changher.spec`.
- **Large executable size**: normal — librosa/numpy/PySide6 are bundled.
- **`iscc` not found**: add Inno Setup to PATH or use the full path to
  `ISCC.exe`.
- **AppImage permission denied**: `chmod +x PitchShifter-*.AppImage`.

## File Structure

```
Pitch_changher/
├── Pitch_Changher.py            # Application (UI + processing)
├── Pitch_Changher.spec          # PyInstaller spec
├── requirements.txt             # Runtime dependencies
├── requirements-dev.txt         # + PyInstaller (build)
├── scripts/get_ffmpeg.py        # Downloads FFmpeg for the current OS
├── build_windows.bat            # Windows executable build
├── build_installer_windows.bat  # Windows installer build
├── build_linux.sh               # Linux executable build
├── build_appimage.sh            # Linux AppImage build
├── installer.iss                # Inno Setup script
├── icons/                       # App icons
└── .github/workflows/build.yml  # CI: installers on tag push
```
