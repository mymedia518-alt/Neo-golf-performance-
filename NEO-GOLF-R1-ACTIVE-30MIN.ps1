$ErrorActionPreference = 'Stop'
$Repo = 'C:\Users\user\Desktop\Neo-golf-performance-live'
$LogDir = 'C:\Users\user\Desktop\Neo-golf-performance-live-logs'
$Lock = Join-Path $LogDir 'r1-active-cycle.lock'
$InternalLock = Join-Path $Repo 'klpga_pipeline\content\website_v2\.r1_active_cycle.lock'
$Python = 'C:\Python313\python.exe'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $LogDir "$stamp.log"
Start-Transcript -Path $log -Append | Out-Null
try {
  if (Test-Path $Lock) {
    $raw = (Get-Content -Raw -LiteralPath $Lock -ErrorAction SilentlyContinue).Trim()
    $ownerPid = 0
    [void][int]::TryParse(($raw -split '\s+')[0], [ref]$ownerPid)
    $owner = if ($ownerPid) { Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue } else { $null }
    $age = ((Get-Date) - (Get-Item -LiteralPath $Lock).LastWriteTime).TotalSeconds
    if ($owner -and $owner.CommandLine -and $owner.CommandLine -like '*NEO-GOLF-R1-ACTIVE-30MIN.ps1*') { Write-Output "SKIP_WAIT: duplicate execution lock pid=$ownerPid"; exit 0 }
    if ($age -lt 1800) { Write-Output "HARD_STOP: lock exists without verifiable owner (age=${age}s)"; exit 2 }
    Remove-Item -LiteralPath $Lock -Force
  }
  New-Item -ItemType File -Path $Lock -Force | Set-Content -Value "$PID $(Get-Date -Format o)"
  $env:GIT_TERMINAL_PROMPT = '0'
  Set-Location $Repo
  $status = (& git -c safe.directory=$Repo status --porcelain) | Where-Object { $_ -notmatch '^\?\? (\.pytest-|\.test-)' }
  if ($status) { Write-Output 'HARD_STOP: worktree dirty'; $status; exit 2 }
  & git -c safe.directory=$Repo fetch origin
  $local = (& git -c safe.directory=$Repo rev-parse HEAD).Trim()
  $remote = (& git -c safe.directory=$Repo rev-parse origin/neo-website-v2).Trim()
  if ($local -ne $remote) { Write-Output "HARD_STOP: local=$local remote=$remote; no automatic overwrite"; exit 2 }
  if (Test-Path $InternalLock) {
    $iraw = (Get-Content -Raw -LiteralPath $InternalLock -ErrorAction SilentlyContinue).Trim()
    $ipid = 0; [void][int]::TryParse(($iraw -split '\s+')[0], [ref]$ipid)
    $iproc = if ($ipid) { Get-CimInstance Win32_Process -Filter "ProcessId=$ipid" -ErrorAction SilentlyContinue } else { $null }
    $iage = ((Get-Date) - (Get-Item -LiteralPath $InternalLock).LastWriteTime).TotalSeconds
    if ($iproc) { Write-Output "SKIP_WAIT: active cycle process pid=$ipid"; exit 0 }
    if ($iage -ge 1500) { Remove-Item -LiteralPath $InternalLock -Force } else { Write-Output "HARD_STOP: internal lock has no live owner but is too young (age=${iage}s)"; exit 2 }
  }
  & $Python 'klpga_pipeline\scripts\96_ok_open_r1_active_cycle.py' --live --git-push
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} catch { Write-Output ('HARD_STOP: ' + $_.Exception.Message); exit 2 }
finally {
  Remove-Item -LiteralPath $Lock -Force -ErrorAction SilentlyContinue
  Stop-Transcript | Out-Null
}
