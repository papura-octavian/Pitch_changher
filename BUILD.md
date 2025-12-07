# Build Instructions

This document explains how to build installers for PitchShifter.

## Prerequisites

### For Windows:
- Python 3.9+
- [Inno Setup](https://jrsoftware.org/isdl.php) (for creating the installer)

### For Linux:
- Python 3.9+
- AppImageTool (automatically downloaded by the build script)

## Quick Build

### Windows
```batch
build_installer_windows.bat
```

This will:
1. Create a virtual environment
2. Install dependencies
3. Build the executable with PyInstaller
4. Create a Windows installer using Inno Setup

Output: `installer/PitchShifter-Setup-1.0.0.exe`

### Linux
```bash
./build_appimage.sh [version]
```

This will:
1. Create a virtual environment
2. Install dependencies
3. Build the executable with PyInstaller
4. Create an AppImage

Output: `PitchShifter-[version]-x86_64.AppImage`

## Manual Build Steps

### 1. Build Executable Only

**Windows:**
```batch
build_windows.bat
```

**Linux:**
```bash
./build_linux.sh
```

This creates `dist/PitchShifter.exe` (Windows) or `dist/PitchShifter` (Linux).

### 2. Create Installer

**Windows:**
1. Install Inno Setup
2. Open `installer.iss` in Inno Setup Compiler
3. Click "Build" → "Compile"

Or use the command line:
```batch
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

**Linux:**
```bash
./build_appimage.sh
```

## Automated Builds with GitHub Actions

The project includes GitHub Actions workflows that automatically build installers when you create a release tag.

### How to Trigger Automated Builds

1. **Create a tag:**
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Or create a release on GitHub:**
   - Go to "Releases" → "Create a new release"
   - Create a new tag (e.g., `v1.0.0`)
   - GitHub Actions will automatically build and attach installers

3. **Check the build status:**
   - Go to "Actions" tab in GitHub
   - You'll see two workflows: "Build Windows Installer" and "Build Linux AppImage"

4. **Download installers:**
   - Once builds complete, go to the Release page
   - Download the installers from the release assets

## Customizing the Installer

### Windows (Inno Setup)

Edit `installer.iss` to customize:
- App name, version, publisher
- Installation directory
- Desktop/Start Menu shortcuts
- License file
- Installer icon

### Linux (AppImage)

Edit `build_appimage.sh` to customize:
- App name
- Desktop file metadata
- Icon (add to `AppDir/usr/share/icons/`)

## Troubleshooting

### PyInstaller Issues

- **"Module not found"**: Add missing modules to `hiddenimports` in `Pitch_Changher.spec`
- **Large executable size**: This is normal due to bundled libraries (librosa, numpy, etc.)
- **FFmpeg not found**: Make sure `ffmpeg/` directory contains the binaries

### Inno Setup Issues

- **"iscc not found"**: Add Inno Setup to your PATH or use full path to `ISCC.exe`
- **Installer doesn't run**: Check that the executable was built successfully first

### AppImage Issues

- **"Permission denied"**: Run `chmod +x appimagetool.AppImage`
- **AppImage doesn't run**: Make sure it's executable: `chmod +x PitchShifter-*.AppImage`

## File Structure

```
Pitch_changher/
├── Pitch_Changher.py          # Main application
├── Pitch_Changher.spec        # PyInstaller spec file
├── requirements.txt           # Python dependencies
├── build_windows.bat         # Windows build script
├── build_linux.sh            # Linux build script
├── build_installer_windows.bat  # Windows installer script
├── build_appimage.sh         # Linux AppImage script
├── installer.iss              # Inno Setup script
├── ffmpeg/                    # Bundled FFmpeg binaries
│   ├── windows/
│   └── linux/
└── .github/workflows/         # GitHub Actions workflows
    ├── build-windows.yml
    └── build-linux.yml
```

