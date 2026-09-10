@echo off
REM DYNAMIC REPO PATH: this script's own folder IS the klpga_pipeline
REM checkout to operate on -- never a hardcoded machine-specific user
REM path (see NEO_HISTORICAL_TRUTH_BLOCKER_RESOLUTION.bat for the same
REM established pattern). Uses whichever "python" already resolves on
REM PATH (a venv's Scripts\python.exe if one is active), falling back
REM to a .venv under this folder if present.
setlocal
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
set "PYTHON=python"
if exist "%HERE%\.venv\Scripts\python.exe" set "PYTHON=%HERE%\.venv\Scripts\python.exe"

echo === NEO historical R1 full-field recovery (CUT/WD/DQ inclusive) ===
echo Repo: %HERE%
echo Python: %PYTHON%
echo.

"%PYTHON%" "%HERE%\scripts\106_recover_historical_r1_full_field.py"
if errorlevel 1 (
    echo.
    echo Recovery script exited with an error. See output above.
    exit /b 1
)

echo.
echo === Running regression tests ===
"%PYTHON%" -m pytest "%HERE%\tests\test_recover_historical_r1_full_field.py" -q
if errorlevel 1 (
    echo.
    echo Regression tests failed. Do not treat the recovered data as trusted until this is fixed.
    exit /b 1
)

echo.
echo Done. Output files:
echo   content\website_v2\NEO_HISTORICAL_R1_FULL_FIELD_V1.json
echo   content\website_v2\NEO_HISTORICAL_R1_FULL_FIELD_V1_AUDIT.json
echo   evidence\historical_r1_full_field_v1\  (raw archived evidence)
endlocal
