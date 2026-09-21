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

    Write-Host "[GATE COMPLETE] single-hole live PASS."

    $ProbeOut = "data/cmpro_" + $GameCode + "_" + $Player + "_playerScore.html"
    py scripts/probe_cmpro_player_score.py --game $GameCode --player $Player --out $ProbeOut
    if ($LASTEXITCODE -ne 0) {
        throw "playerScore probe failed"
    }

    Write-Host "[PLAYER SCORE PROBE COMPLETE] inspect structure before full collection."
}
finally {
    Pop-Location
}
