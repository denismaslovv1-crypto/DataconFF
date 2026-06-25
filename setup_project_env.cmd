@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Creates the main project environment for RAG, PDF parsing, and tests.
rem Usage:
rem   setup_project_env.cmd

set "ENV_DIR=.venv"
set "PYTHON_EXE=py -3.12"
set "EXIT_CODE=0"

echo.
echo === Datacon main environment setup ===
echo Target: %ENV_DIR%
echo.

if exist "%ENV_DIR%\Scripts\python.exe" goto already_exists

echo [1/3] Creating virtual environment...
%PYTHON_EXE% -m venv "%ENV_DIR%"
if not exist "%ENV_DIR%\Scripts\python.exe" goto python_failed

:install_project
echo.
echo [2/3] Upgrading pip...
"%ENV_DIR%\Scripts\python.exe" -m pip install -U pip
if errorlevel 1 goto command_failed

echo.
echo [3/3] Installing project in editable mode...
"%ENV_DIR%\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto command_failed

echo.
echo Main project environment is ready.
goto finish

:already_exists
echo Environment already exists:
echo   %ENV_DIR%\Scripts\python.exe
echo.
echo To reinstall, remove %ENV_DIR% manually and run this script again.
goto finish

:python_failed
echo ERROR: Could not create Python 3.12 virtual environment.
echo Install Python 3.12 or edit setup_project_env.cmd and set PYTHON_EXE.
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
