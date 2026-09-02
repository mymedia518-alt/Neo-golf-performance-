@echo off
set "PYTHON=C:\Users\user\Desktop\Neo-golf-performance-\klpga_pipeline\.venv\Scripts\python.exe"
set "DATABASE=C:\Users\user\Desktop\Neo-golf-performance-\klpga_pipeline\data\klpga.sqlite"
"%PYTHON%" "%~dp0scripts\93_resolve_historical_truth_blockers.py" --db "%DATABASE%"
if errorlevel 1 exit /b %errorlevel%
"%PYTHON%" -m pytest "%~dp0tests\test_historical_truth_blocker_resolution.py" -q
