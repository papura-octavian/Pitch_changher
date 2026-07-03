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

# Upgrade pip and install dependencies (runtime + PyInstaller)
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-dev.txt

# Download FFmpeg (static build) if not already present
python scripts/get_ffmpeg.py

# Build with PyInstaller
pyinstaller --clean --noconfirm Pitch_Changher.spec

# Copy FFmpeg next to the executable so dist/PitchShifter runs standalone
cp -r ffmpeg dist/ffmpeg

echo ""
echo "Build complete! Executable is in: dist/PitchShifter"
