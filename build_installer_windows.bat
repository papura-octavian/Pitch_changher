@echo off
REM Build Windows installer using Inno Setup
echo Building Windows installer...

REM First build the executable
call build_windows.bat

REM Check if Inno Setup is installed
where iscc >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Inno Setup Compiler (iscc.exe) not found in PATH!
    echo Please install Inno Setup from: https://jrsoftware.org/isdl.php
    echo And add it to your PATH, or run iscc.exe directly with full path.
    pause
    exit /b 1
)

REM Create installer directory
if not exist installer mkdir installer

REM Compile installer
iscc installer.iss

echo.
echo Installer created in: installer\PitchShifter-Setup-1.0.0.exe
pause



