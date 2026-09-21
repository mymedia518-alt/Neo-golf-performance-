$ErrorActionPreference="Stop"
Push-Location klpga_pipeline
try {
  py scripts/experiment_kim_multi_event_01.py --root . --output reports/player_intelligence/kim_minsun7_multi_event_01.json
  if ($LASTEXITCODE -ne 0) { throw "BLOCKED: Kim multi-event experiment failed" }
  Write-Host "[KIM MULTI EVENT PASS]"
}
finally { Pop-Location }
