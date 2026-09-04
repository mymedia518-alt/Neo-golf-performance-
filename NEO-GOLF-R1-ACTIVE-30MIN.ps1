$ErrorActionPreference = 'Stop'
$Repo = 'C:\Users\user\Desktop\Neo-golf-performance-live'
$LogDir = 'C:\Users\user\Desktop\Neo-golf-performance-live-logs'
$Lock = Join-Path $LogDir 'r1-active-cycle.lock'
$Python = 'C:\Python313\python.exe'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $LogDir "$stamp.log"
Start-Transcript -Path $log -Append | Out-Null
try {
  if (Test-Path $Lock) { Write-Output 'HARD_STOP: duplicate execution lock'; exit 2 }
  New-Item -ItemType File -Path $Lock -Force | Out-Null
  $env:GIT_TERMINAL_PROMPT = '0'
  Set-Location $Repo
  $status = (& git -c safe.directory=$Repo status --porcelain) | Where-Object { $_ -notmatch '^\?\? (\.pytest-|\.test-)' }
  if ($status) { Write-Output 'HARD_STOP: worktree dirty'; $status; exit 2 }
  & git -c safe.directory=$Repo fetch origin
  $local = (& git -c safe.directory=$Repo rev-parse HEAD).Trim()
  $remote = (& git -c safe.directory=$Repo rev-parse origin/neo-website-v2).Trim()
  if ($local -ne $remote) { Write-Output "HARD_STOP: local=$local remote=$remote; no automatic overwrite"; exit 2 }
  & $Python 'klpga_pipeline\scripts\96_ok_open_r1_active_cycle.py' --live --git-push
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch { Write-Output ('HARD_STOP: ' + $_.Exception.Message); exit 2 }
finally {
  Remove-Item -LiteralPath $Lock -Force -ErrorAction SilentlyContinue
  Stop-Transcript | Out-Null
}
