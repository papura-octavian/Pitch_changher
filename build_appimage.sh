#!/bin/bash
# Build AppImage for Linux locally

set -e

echo "Building PitchShifter AppImage..."

# Build the executable first
./build_linux.sh

# Download AppImageTool if not present
if [ ! -f "appimagetool.AppImage" ]; then
    echo "Downloading AppImageTool..."
    wget -q https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage -O appimagetool.AppImage
    chmod +x appimagetool.AppImage
fi

# Create AppDir structure
echo "Creating AppDir structure..."
rm -rf AppDir
mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps

# Copy executable
cp dist/PitchShifter AppDir/usr/bin/
cp -r ffmpeg AppDir/usr/

# Create desktop file
cat > AppDir/usr/share/applications/pitchshifter.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=PitchShifter
Comment=Pitch shifting tool for audio and video files
Exec=pitchshifter
Icon=pitchshifter
Categories=AudioVideo;Audio;Video;
Terminal=false
EOF

# Create AppRun
cat > AppDir/AppRun << 'EOF'
#!/bin/bash
SELF="$(readlink -f "${0}")"
HERE="$(dirname "${SELF}")"
exec "${HERE}/usr/bin/PitchShifter" "$@"
EOF
chmod +x AppDir/AppRun

# Build AppImage
VERSION=${1:-"dev"}
ARCH=x86_64 ./appimagetool.AppImage AppDir PitchShifter-${VERSION}-x86_64.AppImage

echo ""
echo "AppImage created: PitchShifter-${VERSION}-x86_64.AppImage"

