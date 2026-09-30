<#
.SYNOPSIS
    NEO Sync -- collects one KLPGA tournament's official data end to end
    and (unless -SkipGithubUpload or -DryRun) publishes it to a review
    branch, so Claude can build PRE/R1/R2/R3/FR/FINAL/HOME/Player
    Reports/Rankings from committed artifacts only, never live KLPGA
    access.

.DESCRIPTION
    A thin wrapper only. All real logic (fetch, parse, normalize,
    warehouse, validate, review report, git publish) lives in the
    already-reviewed Python package klpga.neo_reader -- see its own
    module docstrings for exactly which endpoints it calls and why
    each one is already confirmed. This script never duplicates that
    logic; it only sequences it and stops on the first failure.

.PARAMETER GameCode
    The official KLPGA gameCode, e.g. 2026100001.

.PARAMETER Season
    The season year this gameCode belongs to, e.g. 2026. Defaults to
    the gameCode's own leading 4 digits if not given.

.PARAMETER Stage
    'pre' (default) collects Tournament Info + Entry List + K-Ranking --
    everything available before a round has been played. 'results'
    additionally collects the round leaderboard, and only makes sense
    once at least one round has real data.

.PARAMETER DryRun
    Run collection, normalize, warehouse, validate, and the review
    report, but never touch git. Inspect reports/<GameCode>/
    REVIEW_REPORT_V1.md before deciding to publish.

.PARAMETER SkipGithubUpload
    Same effect as -DryRun for stage 6 specifically, named for
    clarity when scripting.

.EXAMPLE
    .\neo-sync.ps1 -GameCode 2026100001 -Season 2026 -DryRun
    .\neo-sync.ps1 -GameCode 2026100001 -Season 2026
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameCode,

    [Parameter(Mandatory = $false)]
    [int]$Season,

    [Parameter(Mandatory = $false)]
    [ValidateSet("pre", "results")]
    [string]$Stage = "pre",

    [switch]$DryRun,
    [switch]$SkipGithubUpload
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PipelineRoot = Join-Path $RepoRoot "klpga_pipeline"

Push-Location $PipelineRoot
try {
    $env:PYTHONPATH = Join-Path $PipelineRoot "src"

    # Season inference (if -Season is omitted) lives in exactly one
    # place -- klpga.neo_reader.cli's own --season handling -- rather
    # than being duplicated here in PowerShell.
    $pyArgs = @(
        "-m", "klpga.neo_reader.cli", "sync",
        "--game-code", $GameCode,
        "--stage", $Stage
    )
    if ($Season) { $pyArgs += @("--season", $Season) }
    if ($DryRun) { $pyArgs += "--dry-run" }
    if ($SkipGithubUpload) { $pyArgs += "--skip-github-upload" }

    Write-Host "=== NEO Sync: python $($pyArgs -join ' ') ==="
    python @pyArgs
    $exitCode = $LASTEXITCODE
}
finally {
    Pop-Location
}

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "NEO Sync did not complete successfully (exit code $exitCode)." -ForegroundColor Red
    Write-Host "See klpga_pipeline/reports/$GameCode/REVIEW_REPORT_V1.md for exactly what failed and why."
}
else {
    Write-Host ""
    Write-Host "NEO Sync completed successfully." -ForegroundColor Green
    Write-Host "Review: klpga_pipeline/reports/$GameCode/REVIEW_REPORT_V1.md"
}

exit $exitCode
