@echo off
REM ============================================================
REM NEO ZERO-TOUCH OPS - FINAL CLOSE - ONE-CLICK LAUNCHER
REM
REM DOUBLE-CLICK THIS FILE. Nothing else is required.
REM
REM This file is a thin, zero-logic entry point: it resolves the
REM repo root from its own location, activates the venv if one
REM exists, then runs:
REM     python scripts\neo_ops.py final-close
REM which invokes scripts\final_close_preflight.py as a subprocess,
REM streams the complete output to this console, saves it verbatim
REM to outputs\neo_ops\<game_code>\latest.txt, writes a
REM machine-readable summary to outputs\neo_ops\<game_code>\latest.json,
REM posts an optional Discord notification (NEO_DISCORD_WEBHOOK_URL),
REM and exits with GO=0 / WARN=1 / HARD_STOP=2 / UNKNOWN=3.
REM
REM It never freezes FINAL, never freezes an evaluation, never
REM deploys, never commits/pushes, and never touches docs\index.html.
REM
REM BETA #001's game_code/season/expected-final-round are the
REM defaults baked into scripts\neo_ops.py's own argparse -- any
REM argument you pass to THIS .bat is forwarded straight through, so
REM a future tournament can be run without editing any file:
REM     NEO_FINAL_CLOSE.bat --game-code 2026080002 --season 2026
REM
REM CODE/DATA SEPARATION: this launcher's own folder is the CODE ROOT
REM (whatever worktree it was double-clicked from -- copy/clone it
REM anywhere and it still works). The DATA ROOT -- klpga.sqlite, the
REM HTTP cache, roster files -- is set below via NEO_DATA_ROOT to the
REM one canonical, gitignored data directory, so a different worktree
REM checkout never needs its own copy of the production DB. Nothing in
REM the Python code hardcodes this path; only this launcher does. If
REM NEO_DATA_ROOT is already set in your environment, that value wins
REM and the line below is skipped.
REM ============================================================

cd /d "%~dp0"

if not defined NEO_DATA_ROOT (
    set "NEO_DATA_ROOT=C:\Users\user\Desktop\Neo-golf-performance-\klpga_pipeline\data"
)

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

python scripts\neo_ops.py final-close %*
set "RC=%ERRORLEVEL%"

echo.
echo ============================================================
if "%RC%"=="0" (
    echo NEO FINAL CLOSE: GO
) else if "%RC%"=="1" (
    echo NEO FINAL CLOSE: WARN
) else if "%RC%"=="2" (
    echo NEO FINAL CLOSE: HARD STOP
) else (
    echo NEO FINAL CLOSE: UNKNOWN ^(exit code %RC%^)
)
echo ============================================================

if not "%RC%"=="0" (
    echo.
    echo Press any key to close this window...
    pause >nul
)

exit /b %RC%
