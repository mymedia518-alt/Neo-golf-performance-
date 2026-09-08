@echo off
setlocal
set "REPO_ROOT=%~dp0"
set "COLLECT_SCRIPT=%REPO_ROOT%klpga_pipeline\scripts\collect_official_final_result.py"
set "VALIDATE_SCRIPT=%REPO_ROOT%klpga_pipeline\scripts\run_two_event_validation_pipeline.py"
set "MANIFEST=%REPO_ROOT%klpga_pipeline\config\NEO_TWO_EVENT_VALIDATION_MANIFEST_V1.json"
set "RESULT_PATH=klpga_pipeline\content\website_v2\OK_OPEN_2026_FINAL_RESULT.json"
set "AUDIT_PATH=klpga_pipeline\content\website_v2\OK_OPEN_2026_FINAL_RESULT_SOURCE_AUDIT.json"
set "RAW_DIR=outputs\official_final_results"
set "CACHE_DIR=%REPO_ROOT%data\raw_cache\http"

python "%COLLECT_SCRIPT%" --repo-root "%REPO_ROOT%" --game-code "2026120001" --final-round "3" --result-path "%RESULT_PATH%" --source-audit-path "%AUDIT_PATH%" --raw-dir "%RAW_DIR%" --cache-dir "%CACHE_DIR%" --live
set "COLLECT_EXIT=%ERRORLEVEL%"

if not "%COLLECT_EXIT%"=="0" (
    echo OFFICIAL RESULT COLLECTION FAILED: %COLLECT_EXIT%
    exit /b %COLLECT_EXIT%
)

python "%VALIDATE_SCRIPT%" --repo-root "%REPO_ROOT%" --manifest "%MANIFEST%" %*
exit /b %ERRORLEVEL%
