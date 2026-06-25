@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Creates a separate MolScribe environment for molecule image recognition.
rem Usage:
rem   setup_molscribe_env.cmd

set "ENV_DIR=.venv-molscribe"
set "PYTHON_EXE=py -3.10"
set "FALLBACK_PYTHON=py -3.11"
set "EXIT_CODE=0"

echo.
echo === MolScribe environment setup ===
echo Target: %ENV_DIR%
echo.

if exist "%ENV_DIR%\Scripts\python.exe" goto already_exists

echo [1/3] Creating virtual environment...
%PYTHON_EXE% -m venv "%ENV_DIR%"
if exist "%ENV_DIR%\Scripts\python.exe" goto install_molscribe

echo Python 3.10 was not available, trying Python 3.11...
%FALLBACK_PYTHON% -m venv "%ENV_DIR%"
if not exist "%ENV_DIR%\Scripts\python.exe" goto python_failed

:install_molscribe
echo.
echo [2/3] Upgrading pip...
"%ENV_DIR%\Scripts\python.exe" -m pip install -U pip
if errorlevel 1 goto command_failed

echo.
echo [3/3] Installing MolScribe runtime packages...
"%ENV_DIR%\Scripts\python.exe" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto command_failed
"%ENV_DIR%\Scripts\python.exe" -m pip install molscribe huggingface_hub rdkit opencv-python pillow
if errorlevel 1 goto command_failed

echo.
echo MolScribe environment is ready.
echo Test with:
echo   .\.venv-molscribe\Scripts\python.exe scripts\run_molscribe_one.py --image path\to\image.png --allow-download
goto finish

:already_exists
echo Environment already exists:
echo   %ENV_DIR%\Scripts\python.exe
echo.
echo To reinstall, remove %ENV_DIR% manually and run this script again.
goto finish

:python_failed
echo ERROR: Could not create a Python virtual environment for MolScribe.
echo Install Python 3.10 or 3.11, or edit setup_molscribe_env.cmd and set PYTHON_EXE.
set "EXIT_CODE=1"
goto finish

:command_failed
echo ERROR: Previous command failed.
set "EXIT_CODE=1"
goto finish

:finish
echo.
echo Setup finished with exit code %EXIT_CODE%.
echo.
if not "%NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
