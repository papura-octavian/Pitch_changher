@echo off
REM Build script for Windows
echo Building PitchShifter for Windows...

REM Create virtual environment if it doesn't exist
if not exist .venv (
    python -m venv .venv
)

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Upgrade pip
python -m pip install --upgrade pip setuptools wheel

REM Install dependencies
pip install -r requirements.txt

REM Build with PyInstaller
pyinstaller --clean --noconfirm Pitch_Changher.spec

echo.
echo Build complete! Executable is in: dist\PitchShifter.exe
pause



