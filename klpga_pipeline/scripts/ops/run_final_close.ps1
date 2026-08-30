# NEO AUTO OPS — BETA #001 FINAL CLOSE preflight, real logic.
#
# Invoked by neo_final_close_launcher.bat (the double-click target) via
# `powershell -ExecutionPolicy Bypass -File`, which bypasses the
# system's default script-execution-policy restriction for THIS file
# only, without changing any machine-wide PowerShell setting.
#
# Does exactly what scripts/final_close_preflight.py does — this
# wrapper adds NOTHING to the underlying logic. It only:
#   - locates the repo root and (if present) activates a venv
#   - runs the real preflight, showing output live AND saving it
#   - also asks the preflight to write a machine-readable JSON summary
#     (--json-out)
#   - prints ONE unambiguous final line: "NEO FINAL CLOSE: GO/WARN/HARD STOP"
#   - keeps the window open only when GO was NOT reached (WARN/HARD STOP/
#     unknown), since those need a human to read the reasons
#
# Never freezes, deploys, commits, pushes, or touches docs/index.html —
# it only ever calls scripts/final_close_preflight.py, which itself
# never does any of those (see that script's own module docstring).
#
# Parameters allow a FUTURE caller (e.g. a parameterized scheduled
# task) to override game_code/season/etc. without editing this file —
# see item 10 of the NEO AUTO OPS request this was built for. Today's
# defaults are exactly BETA #001's real values.

param(
    [string]$GameCode = "2026080001",
    [string]$Season = "2026",
    [string]$ExpectedFinalRound = "4",
    [string]$Finalists = "data/roster/r3_finalists_2026080001.csv",
    [string]$DbPath = "data/klpga.sqlite"
)

$ErrorActionPreference = "Continue"

# --- Resolve repo root: this script lives in klpga_pipeline\scripts\ops\ ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path (Join-Path $ScriptDir "..\..")).Path
Set-Location $RepoRoot

# --- Activate a venv if one exists here. Never creates one. ---
$venvCandidates = @(
    (Join-Path $RepoRoot ".venv\Scripts\Activate.ps1"),
    (Join-Path $RepoRoot "venv\Scripts\Activate.ps1")
)
foreach ($venvPath in $venvCandidates) {
    if (Test-Path $venvPath) {
        Write-Host "Activating venv: $venvPath"
        & $venvPath
        break
    }
}

# --- Output paths ---
$OutDir = Join-Path $RepoRoot "outputs\neo_ops\$GameCode"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$LogPath = Join-Path $OutDir "live_final_close.txt"
$JsonPath = Join-Path $OutDir "live_final_close.json"

Write-Host "============================================================"
Write-Host "NEO AUTO OPS - BETA #001 FINAL CLOSE PREFLIGHT"
Write-Host "game_code=$GameCode season=$Season expected_final_round=$ExpectedFinalRound"
Write-Host "repo root: $RepoRoot"
Write-Host "log:  $LogPath"
Write-Host "json: $JsonPath"
Write-Host "============================================================"
Write-Host ""

$pythonArgs = @(
    "scripts\final_close_preflight.py",
    "--db", $DbPath,
    "--season", $Season,
    "--game-code", $GameCode,
    "--expected-final-round", $ExpectedFinalRound,
    "--finalists", $Finalists,
    "--json-out", $JsonPath
)

# Tee-Object shows the real preflight output live on screen AND saves
# the complete, unedited console output to $LogPath in one pass — the
# operator never needs to copy anything by hand.
& python @pythonArgs 2>&1 | Tee-Object -FilePath $LogPath
$exitCode = $LASTEXITCODE

# --- Parse the ONE authoritative "VERDICT: X" line the preflight itself printed ---
$verdict = "UNKNOWN"
$verdictMatch = Select-String -Path $LogPath -Pattern "^VERDICT:\s*(\S+)" | Select-Object -Last 1
if ($verdictMatch) {
    $verdict = $verdictMatch.Matches[0].Groups[1].Value
}

Write-Host ""
Write-Host "============================================================"
switch ($verdict) {
    "GO" {
        Write-Host "NEO FINAL CLOSE: GO" -ForegroundColor Green
    }
    "WARN" {
        Write-Host "NEO FINAL CLOSE: WARN" -ForegroundColor Yellow
    }
    "HARD_STOP" {
        Write-Host "NEO FINAL CLOSE: HARD STOP" -ForegroundColor Red
    }
    default {
        Write-Host "NEO FINAL CLOSE: UNKNOWN - see $LogPath" -ForegroundColor Red
    }
}
Write-Host "Full log:  $LogPath"
if (Test-Path $JsonPath) {
    Write-Host "JSON:      $JsonPath"
}
Write-Host "============================================================"

# --- Keep the window open only when attention is required ---
if ($verdict -ne "GO") {
    Write-Host ""
    Write-Host "Press any key to close this window..."
    try {
        $null = [System.Console]::ReadKey($true)
    } catch {
        Start-Sleep -Seconds 30
    }
} else {
    Start-Sleep -Seconds 8
}

exit $exitCode
