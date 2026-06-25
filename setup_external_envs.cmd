@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Convenience setup for optional local structure-recognition environments.
rem Usage:
rem   setup_external_envs.cmd

set "EXIT_CODE=0"
set "NO_PAUSE=1"

call setup_molscribe_env.cmd
if errorlevel 1 set "EXIT_CODE=1"

if "%EXIT_CODE%"=="0" call setup_decimer_env.cmd
if errorlevel 1 set "EXIT_CODE=1"

echo.
echo External environment setup finished with exit code %EXIT_CODE%.
echo.
pause
exit /b %EXIT_CODE%
