param(
    [string[]]$GameCodes = @("2026040004","2026060003","2026080002","2026090003"),
    [string]$PlayerCode = "10097"
)
$ErrorActionPreference = "Stop"

Write-Host "[NEO CMPRO PLAYER PLAN] code=$PlayerCode"
Push-Location klpga_pipeline
try {
    foreach ($GameCode in $GameCodes) {
        Write-Host ""
        Write-Host "=== PLAYER PLAN $GameCode ==="
        py scripts/plan_cmpro_player.py --game $GameCode --player-code $PlayerCode
        if ($LASTEXITCODE -ne 0) {
            throw "BLOCKED: player plan failed for $GameCode"
        }
    }
    Write-Host ""
    Write-Host "[ALL PLAYER PLAN PASS]"
}
finally {
    Pop-Location
}
