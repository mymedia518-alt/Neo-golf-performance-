@echo off
REM ============================================================
REM NEO AUTO OPS - BETA #001 FINAL CLOSE - ONE-CLICK LAUNCHER
REM
REM DOUBLE-CLICK THIS FILE. Nothing else is required.
REM
REM This file is a thin, zero-logic entry point: it hands off
REM immediately to run_final_close.ps1 (in this same folder),
REM which does the real work — locate the repo, activate the venv
REM if present, run scripts\final_close_preflight.py, save the
REM full console output + a JSON summary, and print one clear
REM NEO FINAL CLOSE: GO / WARN / HARD STOP line.
REM
REM -ExecutionPolicy Bypass applies ONLY to this one invocation —
REM it does not change any system-wide PowerShell policy.
REM
REM Today's game_code/season/etc. are BETA #001's real values,
REM hardcoded as the .ps1's parameter defaults. Any argument you
REM pass to THIS .bat is forwarded straight through to the .ps1,
REM so a future tournament can be run without editing either file:
REM   neo_final_close_launcher.bat -GameCode 2026080002 -Season 2026
REM ============================================================

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_final_close.ps1" %*
