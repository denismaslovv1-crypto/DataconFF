@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Automatic parser for all PDFs in a directory.
rem Usage:
rem   parse_pdf_auto_all.cmd [input_dir] [pages]
rem
rem Examples:
rem   parse_pdf_auto_all.cmd
rem   parse_pdf_auto_all.cmd data\pdf_raw
rem   parse_pdf_auto_all.cmd data\pdf_raw 1-3
rem
rem If pages is omitted, all pages are processed.
rem Set NO_PAUSE=1 to disable the final pause when running from another script.

set "INPUT_DIR=%~1"
set "PAGES=%~2"
set "EXIT_CODE=0"

if "%INPUT_DIR%"=="" set "INPUT_DIR=data\pdf_raw"
if not exist "%INPUT_DIR%" goto input_not_found

set "PY=.\.venv\Scripts\python.exe"
set "DECIMER_PY=.\.venv-decimer\Scripts\python.exe"
set "MOLPY=.\.venv-molscribe\Scripts\python.exe"
set "OUTPUT_DIR=data\pdf_parsed"

if not exist "%PY%" goto python_not_found
if not exist "%DECIMER_PY%" goto decimer_not_found
if not exist "%MOLPY%" goto molscribe_not_found

echo.
echo === Datacon automatic batch PDF parser ===
echo Input directory: %INPUT_DIR%
if "%PAGES%"=="" (
  echo Pages: all
) else (
  echo Pages: %PAGES%
)
echo Output: %OUTPUT_DIR%
echo.

echo [1/2] Running base PDF extraction pipeline for all PDFs...
"%PY%" -m pdf_extraction "%INPUT_DIR%" --output-dir "%OUTPUT_DIR%"
if errorlevel 1 goto command_failed

echo.
echo [2/2] Running DECIMER + MolScribe for each PDF...
for %%F in ("%INPUT_DIR%\*.pdf") do call :process_pdf "%%~fF" || goto command_failed

echo.
echo Done.
echo Updated:
echo   %OUTPUT_DIR%\chemical_records.csv
echo   %OUTPUT_DIR%\compound_labels.csv
echo.
echo Recognized image structures:
"%PY%" -c "import csv; rows=[r for r in csv.DictReader(open(r'%OUTPUT_DIR%\chemical_records.csv', encoding='utf-8-sig')) if r.get('record_type')=='image_structure']; print('count=', len(rows)); [print(f\"{r.get('source_file')} | page={r.get('page')} | label={r.get('compound_label')} | conf={r.get('confidence')} | SMILES={r.get('canonical_SMILES') or r.get('SMILES')}\") for r in rows]"
goto finish

:process_pdf
set "CURRENT_PDF=%~1"
echo.
echo --- Auto structure extraction: %CURRENT_PDF%
if "%PAGES%"=="" (
  "%PY%" scripts\run_auto_structure_workflow.py --pdf "%CURRENT_PDF%" --output-dir "%OUTPUT_DIR%" --decimer-python "%DECIMER_PY%" --molscribe-python "%MOLPY%" --min-confidence 0.5
) else (
  "%PY%" scripts\run_auto_structure_workflow.py --pdf "%CURRENT_PDF%" --output-dir "%OUTPUT_DIR%" --pages "%PAGES%" --decimer-python "%DECIMER_PY%" --molscribe-python "%MOLPY%" --min-confidence 0.5
)
if errorlevel 1 exit /b 1
exit /b 0

:input_not_found
echo ERROR: Input directory not found: %INPUT_DIR%
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
