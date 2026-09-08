@echo off
setlocal
set "REPO_ROOT=%~dp0"
python "%REPO_ROOT%klpga_pipeline\scripts\run_two_event_validation_pipeline.py" --repo-root "%REPO_ROOT%" --manifest "%REPO_ROOT%klpga_pipeline\config\NEO_TWO_EVENT_VALIDATION_MANIFEST_V1.json" %*
exit /b %ERRORLEVEL%
