param(
  [string]$GameCode = "2026090002",
  [string]$Branch = "feat/cmpro-shot-data-v0"
)
$ErrorActionPreference = "Stop"
Write-Host "[NEO CMPRO] game=$GameCode branch=$Branch"
git fetch origin
git checkout $Branch
if ($LASTEXITCODE -ne 0) { throw "git checkout failed" }
Push-Location klpga_pipeline
try {
  py -m pytest tests/test_cmpro_shot_collector.py -q
  if ($LASTEXITCODE -ne 0) { throw "cmpro unit test failed" }
  Write-Host "[PASS] cmpro parser unit tests"
  Write-Host "[NEXT] Full live collector runner will be enabled only after the parser tests pass locally."
} finally { Pop-Location }
