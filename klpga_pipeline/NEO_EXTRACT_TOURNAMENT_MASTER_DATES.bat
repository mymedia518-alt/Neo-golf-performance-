@echo off
REM DYNAMIC REPO PATH: this script's own folder IS the klpga_pipeline
REM checkout to operate on -- never a hardcoded machine-specific user
REM path (see NEO_HISTORICAL_TRUTH_BLOCKER_RESOLUTION.bat for the same
REM established pattern).
setlocal
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
set "PYTHON=python"
if exist "%HERE%\.venv\Scripts\python.exe" set "PYTHON=%HERE%\.venv\Scripts\python.exe"
set "DATABASE=%HERE%\data\klpga.sqlite"

echo === NEO tournament_master date extraction (read-only) ===
echo Repo: %HERE%
echo Database: %DATABASE%
echo.

"%PYTHON%" "%HERE%\scripts\107_extract_tournament_master_dates.py" --db "%DATABASE%"
if errorlevel 1 (
    echo.
    echo Extraction failed. See output above.
    exit /b 1
)

echo.
echo === Running regression tests ===
"%PYTHON%" -m pytest "%HERE%\tests\test_extract_tournament_master_dates.py" -q
if errorlevel 1 (
    echo.
    echo Regression tests failed.
    exit /b 1
)

echo.
echo Done. Output file:
echo   content\website_v2\TOURNAMENT_MASTER_DATES_V1.json
endlocal
