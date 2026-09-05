@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "REPO=C:\Users\user\Desktop\Neo-golf-performance-live"
set "LOGDIR=C:\Users\user\Desktop\Neo-golf-performance-live-logs"
set "LOCK=%LOGDIR%\neo-recover.lock"
if not exist "%REPO%\" exit /b 2
if not exist "%LOGDIR%\" mkdir "%LOGDIR%" >nul 2>&1
if exist "%LOCK%" (
  echo HARD_STOP: recovery lock exists
  exit /b 2
)
>"%LOCK%" echo %DATE% %TIME% %PROCESS_ID%
set "LOG=%LOGDIR%\NEO_RECOVER-%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%-%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.log"
set "LOG=%LOG: =0%"
(
  echo NEO_RECOVER start %DATE% %TIME%
  cd /d "%REPO%" || goto :fail
  git -c safe.directory="%REPO%" --version || goto :fail
  python --version || goto :fail
  git -c safe.directory="%REPO%" branch --show-current
  git -c safe.directory="%REPO%" rev-parse HEAD
  git -c safe.directory="%REPO%" fetch origin
  if errorlevel 1 goto :fail
  echo Delegating to canonical NEO-GOLF-R1-ACTIVE-30MIN.ps1
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPO%\NEO-GOLF-R1-ACTIVE-30MIN.ps1"
  set "RC=!ERRORLEVEL!"
) >"%LOG%" 2>&1
goto :done
:fail
set "RC=2"
:done
del /q "%LOCK%" >nul 2>&1
exit /b %RC%
