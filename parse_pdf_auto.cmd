@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Automatic parser: base PDF extraction + DECIMER Segmentation + MolScribe + CSV import.
rem Usage:
rem   parse_pdf_auto.cmd data\pdf_raw\paper.pdf [pages]
rem
rem Example:
rem   parse_pdf_auto.cmd data\pdf_raw\paper.pdf 1-3
rem
rem Set NO_PAUSE=1 to disable the final pause when running from another script.

set "PDF=%~1"
set "PAGES=%~2"
set "EXIT_CODE=0"

if "%PDF%"=="" goto usage
if not exist "%PDF%" goto pdf_not_found
if "%PAGES%"=="" set "PAGES=1"

set "PY=.\.venv\Scripts\python.exe"
set "DECIMER_PY=.\.venv-decimer\Scripts\python.exe"
set "MOLPY=.\.venv-molscribe\Scripts\python.exe"
set "OUTPUT_DIR=data\pdf_parsed"

if not exist "%PY%" goto python_not_found
if not exist "%DECIMER_PY%" goto decimer_not_found
if not exist "%MOLPY%" goto molscribe_not_found

echo.
echo === Datacon automatic PDF parser ===
echo PDF: %PDF%
echo Pages: %PAGES%
echo Output: %OUTPUT_DIR%
echo.

echo [1/2] Running base PDF extraction pipeline...
"%PY%" -m pdf_extraction "%PDF%" --output-dir "%OUTPUT_DIR%"
if errorlevel 1 goto command_failed

echo.
echo [2/2] Running DECIMER auto segmentation, MolScribe recognition, and CSV import...
"%PY%" scripts\run_auto_structure_workflow.py --pdf "%PDF%" --output-dir "%OUTPUT_DIR%" --pages "%PAGES%" --decimer-python "%DECIMER_PY%" --molscribe-python "%MOLPY%" --min-confidence 0.5
if errorlevel 1 goto command_failed

echo.
echo Done.
echo Updated:
echo   %OUTPUT_DIR%\chemical_records.csv
echo   %OUTPUT_DIR%\compound_labels.csv
goto finish

:usage
echo Usage:
echo   parse_pdf_auto.cmd ^<pdf_path^> [pages]
echo.
echo Example:
echo   parse_pdf_auto.cmd data\pdf_raw\paper.pdf 1-3
set "EXIT_CODE=2"
goto finish

:pdf_not_found
echo ERROR: PDF not found: %PDF%
set "EXIT_CODE=2"
goto finish

:python_not_found
echo ERROR: Project Python not found: %PY%
set "EXIT_CODE=1"
goto finish

:decimer_not_found
echo ERROR: DECIMER Python not found: %DECIMER_PY%
echo Run setup_decimer_env.cmd first.
set "EXIT_CODE=1"
goto finish

:molscribe_not_found
echo ERROR: MolScribe Python not found: %MOLPY%
echo Create or restore .venv-molscribe before running recognition.
set "EXIT_CODE=1"
goto finish

:command_failed
echo ERROR: Previous command failed.
set "EXIT_CODE=1"
goto finish

:finish
echo.
echo Parser finished with exit code %EXIT_CODE%.
echo.
if not "%NO_PAUSE%"=="1" pause
exit /b %EXIT_CODE%
