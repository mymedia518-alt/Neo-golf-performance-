@echo off
REM ============================================================
REM NEO AUTO OPS - Windows Task Scheduler registration TEMPLATE
REM
REM *** NOT SCHEDULED. NOTHING IS REGISTERED UNTIL A HUMAN RUNS
REM     THIS FILE DELIBERATELY. ***
REM
REM This file registers a Windows scheduled task that runs
REM NEO_FINAL_CLOSE.bat (repo root) unattended (SILENTLY, no console
REM window) on whatever schedule is set below. It is prepared here
REM so the mechanism exists, exactly as requested — it must be
REM reviewed and its schedule decided by a human before ever being
REM run. Running THIS FILE is the action that actually creates the
REM scheduled task; nothing in this delivery invokes it.
REM
REM REVIEW BEFORE RUNNING:
REM   1. Change SCHEDULE_TYPE / START_TIME below to when you
REM      actually want this to run (currently a placeholder: daily
REM      at 09:00, which is almost certainly NOT what you want for
REM      a one-time tournament close — a single ONCE trigger, or a
REM      manual/on-demand-only task, is more likely correct).
REM   2. Run this file once (double-click, or `register_task_scheduler.bat`
REM      from an elevated prompt if required) to actually register it.
REM   3. Verify with: schtasks /query /tn "NEO_BETA001_FINAL_CLOSE"
REM   4. To remove it later: schtasks /delete /tn "NEO_BETA001_FINAL_CLOSE" /f
REM ============================================================

set "TASK_NAME=NEO_BETA001_FINAL_CLOSE"
set "LAUNCHER=%~dp0..\..\NEO_FINAL_CLOSE.bat"
set "SCHEDULE_TYPE=DAILY"
set "START_TIME=09:00"

echo This will register a Windows Task Scheduler entry named "%TASK_NAME%"
echo that runs: %LAUNCHER%
echo Schedule: %SCHEDULE_TYPE% at %START_TIME% (EDIT THIS FILE FIRST if that is wrong)
echo.
echo Press Ctrl+C now to cancel, or
pause

schtasks /create ^
    /tn "%TASK_NAME%" ^
    /tr "\"%LAUNCHER%\"" ^
    /sc %SCHEDULE_TYPE% ^
    /st %START_TIME% ^
    /rl LIMITED ^
    /f

echo.
echo Done. Verify with:  schtasks /query /tn "%TASK_NAME%"
echo Remove with:        schtasks /delete /tn "%TASK_NAME%" /f
pause
