param(
    [string]$GameCode = "2026090002",
    [string]$Player = "10097",
    [int]$Round = 4,
    [int]$Hole = 18
)

$ErrorActionPreference = "Stop"

Write-Host "[NEO CMPRO] game=$GameCode player=$Player R$Round H$Hole"

Push-Location klpga_pipeline
try {
    py -m pytest tests/test_cmpro_shot_collector.py tests/test_cmpro_shot_runner.py -q
    if ($LASTEXITCODE -ne 0) {
        throw "cmpro tests failed"
    }

    $Out = "data/cmpro_" + $GameCode + "_gate.sqlite"

    py scripts/collect_cmpro_shots.py --game $GameCode --player $Player --round $Round --hole $Hole --out $Out
    if ($LASTEXITCODE -ne 0) {
        throw "live single-hole gate failed"
    }

    Write-Host "[GATE COMPLETE] require SUMMARY PASS before full collection."
}
finally {
    Pop-Location
}
