@echo off
REM Build script for Windows
echo Building PitchShifter for Windows...

REM Create virtual environment if it doesn't exist
if not exist .venv (
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Upgrade pip and install dependencies (runtime + PyInstaller)
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements-dev.txt

REM Download FFmpeg if not already present
python scripts\get_ffmpeg.py

REM Build with PyInstaller
pyinstaller --clean --noconfirm Pitch_Changher.spec

REM Copy FFmpeg next to the executable so dist\PitchShifter.exe runs standalone
xcopy /E /I /Y ffmpeg dist\ffmpeg >nul

echo.
echo Build complete! Executable is in: dist\PitchShifter.exe
pause
