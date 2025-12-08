#!/bin/bash
# Build script for Linux

set -e

echo "Building PitchShifter for Linux..."

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
python -m pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements.txt

# Make ffmpeg executable
chmod +x ffmpeg/linux/ffmpeg 2>/dev/null || true
chmod +x ffmpeg/linux/ffprobe 2>/dev/null || true

# Build with PyInstaller
pyinstaller --clean --noconfirm Pitch_Changher.spec

echo ""
echo "Build complete! Executable is in: dist/PitchShifter"




