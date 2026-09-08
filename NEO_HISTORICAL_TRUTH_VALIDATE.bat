@echo off
setlocal
REM DYNAMIC REPO PATH: this script's own folder IS the repo checkout to
REM validate -- never a hardcoded machine-specific user path.
set "REPO=%~dp0"
if "%REPO:~-1%"=="\" set "REPO=%REPO:~0,-1%"
cd /d "%REPO%"
python klpga_pipeline\scripts\92_build_historical_truth_warehouse.py --db "%REPO%\klpga_pipeline\data\klpga.sqlite"
if errorlevel 1 exit /b 1
python -m pytest -q klpga_pipeline\tests\test_historical_truth_warehouse.py klpga_pipeline\tests\test_neo_ranking_backtest.py
