param([string]$GameCode="2026090002")
$ErrorActionPreference="Stop"

Write-Host "[NEO CMPRO FULL] game=$GameCode"
Push-Location klpga_pipeline
try {
    py -m pytest tests/test_cmpro_shot_collector.py tests/test_cmpro_shot_runner.py -q
    if ($LASTEXITCODE -ne 0) { throw "cmpro tests failed" }

    $Out = "data/cmpro_" + $GameCode + "_full.sqlite"
    py scripts/collect_cmpro_shots.py --game $GameCode --out $Out
    if ($LASTEXITCODE -ne 0) { throw "cmpro full collection QA failed" }

    Write-Host "[CMPRO FULL PASS] $Out"
}
finally {
    Pop-Location
}
