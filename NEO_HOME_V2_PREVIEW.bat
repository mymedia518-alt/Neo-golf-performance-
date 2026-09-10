@echo off
setlocal
cd /d "%~dp0"
python klpga_pipeline\scripts\design_home_v2_preview.py
if errorlevel 1 exit /b 1
start "NEO HOME V2 DESIGN PREVIEW" klpga_pipeline\candidate\home-ranking-v2-preview\index.html
