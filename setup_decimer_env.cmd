@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Creates a separate DECIMER environment. Prefer Python 3.10.
rem Usage:
rem   setup_decimer_env.cmd

set "ENV_DIR=.venv-decimer"
set "PYTHON_EXE=py -3.10"
set "FALLBACK_PYTHON=.\.venv-molscribe\Scripts\python.exe"
set "EXIT_CODE=0"

echo.
echo === DECIMER environment setup ===
echo Target: %ENV_DIR%
echo.

if exist "%ENV_DIR%\Scripts\python.exe" goto already_exists

echo [1/2] Creating virtual environment with Python 3.10...
%PYTHON_EXE% -m venv "%ENV_DIR%"
if exist "%ENV_DIR%\Scripts\python.exe" goto install_decimer

echo.
echo Python launcher did not create %ENV_DIR%.
if not exist "%FALLBACK_PYTHON%" goto python_failed
echo Trying fallback Python from MolScribe environment:
echo   %FALLBACK_PYTHON%
"%FALLBACK_PYTHON%" -m venv "%ENV_DIR%"
if not exist "%ENV_DIR%\Scripts\python.exe" goto python_failed

:install_decimer
echo.
echo [2/2] Installing DECIMER Segmentation...
"%ENV_DIR%\Scripts\python.exe" -m pip install -U pip
if errorlevel 1 goto command_failed
"%ENV_DIR%\Scripts\python.exe" -m pip install decimer-segmentation
if errorlevel 1 goto command_failed

echo.
echo DECIMER environment is ready.
goto finish

:already_exists
echo Environment already exists:
echo   %ENV_DIR%\Scripts\python.exe
echo.
echo To reinstall, remove %ENV_DIR% manually and run this script again.
goto finish

:python_failed
echo ERROR: Could not create Python 3.10 virtual environment.
echo Options:
echo   1. Run: py install 3.10
echo   2. Install Python 3.10 manually
echo   3. Edit setup_decimer_env.cmd and set PYTHON_EXE to your Python 3.10 executable
echo   4. Ensure .venv-molscribe exists so it can be used as fallback
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
