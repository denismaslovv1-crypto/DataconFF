@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Main parser entrypoint for datacon_extraction.
rem Usage:
rem   parse_pdf.cmd data\pdf_raw\paper.pdf
rem   parse_pdf.cmd data\pdf_raw\paper.pdf 1 "700,835,1010,1078" "Figure 1" "1" "Figure 1. Caption text."
rem
rem Set NO_PAUSE=1 to disable the final pause when running from another script.

set "PDF=%~1"
set "PAGES=%~2"
set "BBOX=%~3"
set "FIGURE_ID=%~4"
set "COMPOUND_LABEL=%~5"
set "CAPTION=%~6"
set "EXIT_CODE=0"

if "%PDF%"=="" goto usage
if not exist "%PDF%" goto pdf_not_found

if "%PAGES%"=="" set "PAGES=1"
if "%FIGURE_ID%"=="" set "FIGURE_ID=Figure %PAGES%"
if "%COMPOUND_LABEL%"=="" set "COMPOUND_LABEL=%PAGES%"

set "PY=.\.venv\Scripts\python.exe"
set "MOLPY=.\.venv-molscribe\Scripts\python.exe"
set "OUTPUT_DIR=data\pdf_parsed"
set "ZOOM=2"

if not exist "%PY%" goto python_not_found

for %%F in ("%PDF%") do set "PDF_NAME=%%~nF"

set "PAGE_DIR=data\pdf_pages\%PDF_NAME%"
set "CROP_DIR=data\molecule_crops"
set "CROP_BASE=%PDF_NAME%_p%PAGES%_%COMPOUND_LABEL%"
set "CROP_IMAGE=%CROP_DIR%\%CROP_BASE%.png"
set "MOLSCRIBE_JSON=%CROP_DIR%\%CROP_BASE%.molscribe.json"

echo.
echo === Datacon PDF parser ===
echo PDF: %PDF%
echo Output: %OUTPUT_DIR%
echo.

echo [1/5] Running base PDF extraction pipeline...
"%PY%" -m pdf_extraction "%PDF%" --output-dir "%OUTPUT_DIR%"
if errorlevel 1 goto command_failed

echo.
echo [2/5] Rendering PDF page(s) for visual crop selection...
"%PY%" scripts\render_pdf_pages.py --pdf "%PDF%" --pages "%PAGES%" --zoom %ZOOM% --output-dir "%PAGE_DIR%"
if errorlevel 1 goto command_failed

echo.
echo Rendered pages are in:
echo   %PAGE_DIR%
echo.

if "%BBOX%"=="" goto need_bbox

if not exist "%CROP_DIR%" mkdir "%CROP_DIR%"

echo [3/5] Cropping molecule region from PDF...
"%PY%" scripts\crop_pdf_region.py --pdf "%PDF%" --page %PAGES% --bbox "%BBOX%" --bbox-units pixels --zoom %ZOOM% --output "%CROP_IMAGE%"
if errorlevel 1 goto command_failed

echo.
echo Crop image:
echo   %CROP_IMAGE%
echo.

if not exist "%MOLPY%" goto molscribe_not_found

echo [4/5] Running MolScribe on crop...
"%MOLPY%" scripts\run_molscribe_one.py --image "%CROP_IMAGE%" --allow-download --output "%MOLSCRIBE_JSON%"
if errorlevel 1 goto command_failed

echo.
echo [5/5] Importing MolScribe result into parsed JSON and CSV...
"%PY%" scripts\import_molscribe_crop.py --output-dir "%OUTPUT_DIR%" --sidecar "%CROP_IMAGE%.json" --molscribe-json "%MOLSCRIBE_JSON%" --figure-id "%FIGURE_ID%" --compound-label "%COMPOUND_LABEL%" --caption "%CAPTION%" --min-confidence 0.5
if errorlevel 1 goto command_failed

echo.
echo Done.
echo Updated:
echo   %OUTPUT_DIR%\chemical_records.csv
echo   %OUTPUT_DIR%\compound_labels.csv
goto finish

:usage
echo Usage:
echo   parse_pdf.cmd ^<pdf_path^> [page] [bbox_pixels] [figure_id] [compound_label] [caption]
echo.
echo Example:
echo   parse_pdf.cmd data\pdf_raw\paper.pdf 1 "700,835,1010,1078" "Figure 1" "1" "Figure 1. Biological profiles of lead compound 1."
set "EXIT_CODE=2"
goto finish

:pdf_not_found
echo ERROR: PDF not found: %PDF%
set "EXIT_CODE=2"
goto finish

:python_not_found
echo ERROR: Project Python not found: %PY%
echo Create .venv or install project dependencies first.
set "EXIT_CODE=1"
goto finish

:molscribe_not_found
echo ERROR: MolScribe environment not found: %MOLPY%
echo Create or restore .venv-molscribe before running recognition.
set "EXIT_CODE=1"
goto finish

:need_bbox
echo No bbox was provided, so the parser stops after page rendering.
echo Open the rendered PNG, choose molecule coordinates as x0,y0,x1,y1, then rerun:
echo.
echo   parse_pdf.cmd "%PDF%" %PAGES% "x0,y0,x1,y1" "%FIGURE_ID%" "%COMPOUND_LABEL%" "caption"
set "EXIT_CODE=0"
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
