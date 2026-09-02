@echo off
setlocal
cd /d "%~dp0"
python klpga_pipeline\scripts\86_build_neo_data_home_candidate.py
if errorlevel 1 exit /b 1
python -m pytest -q klpga_pipeline\tests\test_neo_data_home.py
if errorlevel 1 exit /b 1
start "NEO DATA HOME" http://localhost:8788/
python -m http.server 8788 --directory klpga_pipeline\candidate\neo-data-home
