@echo off
setlocal
cd /d "%~dp0"
python klpga_pipeline\scripts\84_build_ok_open_pre_website_candidate.py
if errorlevel 1 (
  echo NEO candidate generation FAILED.
  pause
  exit /b 1
)
python -m pytest -q klpga_pipeline\tests\test_ok_open_pre_website_candidate.py
if errorlevel 1 (
  echo NEO PUBLIC UI CONTRACT FAILED. Browser will not open.
  pause
  exit /b 1
)
start "NEO PRE Preview" http://localhost:8787/tournaments/2026/ok-savings-bank-open/pre/
python -m http.server 8787 --directory klpga_pipeline\candidate\website-v2-ok-open-pre
