@echo off
setlocal
cd /d "%~dp0"
python klpga_pipeline\scripts\92_build_historical_truth_warehouse.py --db "C:\Users\user\Desktop\Neo-golf-performance-\klpga_pipeline\data\klpga.sqlite"
if errorlevel 1 exit /b 1
python -m pytest -q klpga_pipeline\tests\test_historical_truth_warehouse.py klpga_pipeline\tests\test_neo_ranking_backtest.py
