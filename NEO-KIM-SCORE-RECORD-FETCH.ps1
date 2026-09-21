param(
    [string[]]$GameCodes = @("2026040004","2026060003","2026080002","2026090003")
)
$ErrorActionPreference = "Stop"
Push-Location klpga_pipeline
try {
    foreach ($GameCode in $GameCodes) {
        Write-Host ""
        Write-Host "=== SCORE RECORD $GameCode ==="
        py scripts/97_fetch_score_record_sample.py --game-code $GameCode
        if ($LASTEXITCODE -ne 0) { throw "BLOCKED: scoreRecord fetch failed for $GameCode" }
    }
    Write-Host ""
    Write-Host "[ALL SCORE RECORD FETCH PASS]"
}
finally { Pop-Location }
