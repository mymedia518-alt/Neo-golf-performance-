$ErrorActionPreference="Stop"
Push-Location klpga_pipeline
try {
  py scripts/experiment_best_next_state_01.py --root . --min-n 8 --output reports/player_intelligence/kim_minsun7_best_next_state_01.json
  if ($LASTEXITCODE -ne 0) { throw "BLOCKED: Best Next State v1 failed" }
  Write-Host "[BEST NEXT STATE V1 PASS]"
}
finally { Pop-Location }
