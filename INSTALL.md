# Installation Guide

## Download Pre-built Installers

The easiest way to install PitchShifter is to download a pre-built installer from the [GitHub Releases](https://github.com/yourusername/pitchshifter/releases) page.

### Windows

1. Download `PitchShifter-Setup-*.exe` from the latest release
2. Run the installer
3. Follow the installation wizard
4. Launch PitchShifter from the Start Menu

### Linux

1. Download `PitchShifter-*-x86_64.AppImage` from the latest release
2. Make it executable:
   ```bash
   chmod +x PitchShifter-*-x86_64.AppImage
   ```
3. Run it:
   ```bash
   ./PitchShifter-*-x86_64.AppImage
   ```

**Note**: AppImages are portable - you can run them from anywhere without installation.

## Building from Source

See the main README.md for development installation instructions.

## Troubleshooting

### Windows

- If Windows Defender or antivirus blocks the installer, you may need to allow it or add an exception
- Make sure you have administrator rights to install software

### Linux

- If the AppImage doesn't run, make sure it's executable: `chmod +x PitchShifter-*.AppImage`
- Some distributions may require additional libraries. If you see missing library errors, install:
  ```bash
  sudo apt-get install libfuse2  # For AppImage support
  ```

