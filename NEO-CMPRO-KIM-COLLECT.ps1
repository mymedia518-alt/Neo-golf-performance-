param(
    [string[]]$GameCodes = @("2026040004","2026060003","2026080002","2026090003"),
    [string]$PlayerCode = "10097"
)
$ErrorActionPreference = "Stop"

Write-Host "[NEO CMPRO KIM COLLECT] code=$PlayerCode"
Push-Location klpga_pipeline
try {
    py -m pytest tests/test_cmpro_shot_collector.py tests/test_cmpro_shot_runner.py -q
    if ($LASTEXITCODE -ne 0) { throw "BLOCKED: cmpro tests failed" }

    New-Item -ItemType Directory -Force -Path "data/player_cmpro" | Out-Null

    foreach ($GameCode in $GameCodes) {
        Write-Host ""
        Write-Host "=== COLLECT $GameCode / $PlayerCode ==="
        $Out = "data/player_cmpro/cmpro_" + $GameCode + "_player_" + $PlayerCode + ".sqlite"
        py scripts/collect_cmpro_shots.py --game $GameCode --player $PlayerCode --out $Out
        if ($LASTEXITCODE -ne 0) {
            throw "BLOCKED: player cmpro collection failed for $GameCode"
        }
        Write-Host "[PLAYER COLLECT PASS] $GameCode -> $Out"
    }

    Write-Host ""
    Write-Host "[ALL PLAYER COLLECTION PASS]"
}
finally {
    Pop-Location
}
