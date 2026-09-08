@echo off
REM DYNAMIC REPO PATH: this script's own folder IS the klpga_pipeline
REM checkout to operate on -- never a hardcoded machine-specific user
REM path. Uses whichever "python" already resolves on PATH (a venv's
REM Scripts\python.exe if one is active) rather than a pinned .venv path
REM that may not exist on this machine.
set "HERE=%~dp0"
if "%HERE:~-1%"=="\" set "HERE=%HERE:~0,-1%"
set "DATABASE=%HERE%\data\klpga.sqlite"
python "%HERE%\scripts\93_resolve_historical_truth_blockers.py" --db "%DATABASE%"
if errorlevel 1 exit /b %errorlevel%
python -m pytest "%HERE%\tests\test_historical_truth_blocker_resolution.py" -q
