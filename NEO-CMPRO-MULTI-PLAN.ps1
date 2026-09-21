param(
    [string[]]$GameCodes = @("2026040004","2026060003","2026080002","2026090003")
)
$ErrorActionPreference = "Stop"

Write-Host "[NEO CMPRO MULTI PLAN]"
Push-Location klpga_pipeline
try {
    New-Item -ItemType Directory -Force -Path "reports/cmpro_manifests" | Out-Null

    foreach ($GameCode in $GameCodes) {
        Write-Host ""
        Write-Host "=== PLAN $GameCode ==="
        $Out = "reports/cmpro_manifests/" + $GameCode + "_manifest.csv"
        py scripts/plan_cmpro_collection.py --game $GameCode --out $Out
        if ($LASTEXITCODE -ne 0) {
            throw "BLOCKED: cmpro plan failed for $GameCode"
        }
        Write-Host "[PLAN PASS] $GameCode -> $Out"
    }

    Write-Host ""
    Write-Host "[ALL PLAN PASS]"
    Write-Host "Review PLAYERS / ROUND_COUNTS / PLANNED_HOLES before any full collection."
}
finally {
    Pop-Location
}
