$ErrorActionPreference = 'Stop'
$TaskName = 'NEO-GOLF-R1-ACTIVE-30MIN'
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
  # Untracked build byproducts under klpga_pipeline/candidate/ are ignored
  # here on purpose: that whole tree is fully regenerated, deterministically,
  # by _rebuild_and_promote() every cycle (scripts 84/86/88 rewrite it from
  # source JSON, never incrementally) -- an untracked stray file there (e.g.
  # left behind by a human running pytest in this same checkout between
  # cycles) can never be "hidden real work" the way an untracked file
  # elsewhere could be. Confirmed reproducible: an unrelated pytest run in
  # this checkout regenerated klpga_pipeline/candidate/neo-data-home/ranking/
  # as a stray untracked directory that is not part of the real pipeline
  # output and previously would have HARD_STOPped every cycle indefinitely
  # until a human noticed and manually cleaned it.
  $status = (& git -c safe.directory=$Repo status --porcelain) | Where-Object { $_ -notmatch '^\?\? (\.pytest-|\.test-|klpga_pipeline/candidate/)' }
  if ($status) { Write-Output 'HARD_STOP: worktree dirty'; $status; exit 2 }
  & git -c safe.directory=$Repo fetch origin
  $local = (& git -c safe.directory=$Repo rev-parse HEAD).Trim()
  $remote = (& git -c safe.directory=$Repo rev-parse origin/neo-website-v2).Trim()
  if ($local -ne $remote) {
    # Another actor (e.g. a hotfix pushed from elsewhere) can advance
    # origin between cycles. A plain HARD_STOP here means the 30-minute
    # cycle silently stops running -- forever, with nobody paged --
    # until a human notices and manually pulls. Self-heal the ONE safe
    # case: local is a strict ancestor of origin (fast-forward only,
    # never a merge/rebase/reset -- git itself refuses if this is not a
    # true fast-forward). Any real divergence still HARD_STOPs exactly
    # as before.
    # COLLECT/VALIDATE/PUBLISH decoupling (P0 incident follow-up): a
    # true divergence still HARD_STOPs the PUBLISH path here (no
    # automatic merge/rebase/overwrite -- that stays a human decision).
    # But official round data is time-sensitive and cannot be
    # re-observed later, so during a real incident an operator can
    # still run, by hand, whichever historical collect-only escape
    # hatch matches the currently active stage (e.g.
    #   & $Python 'klpga_pipeline\scripts\96_ok_open_r1_active_cycle.py' --live --collect-only
    # for an R1 incident): it saves the immutable snapshot + stage
    # state to local disk WITHOUT touching git or docs/, so no official
    # data point is lost merely because publishing is blocked. This
    # script does not do that automatically (rebuilding/promoting from
    # a diverged checkout risks locally regressing content that already
    # shipped from elsewhere) -- resolving the divergence and a normal
    # run_tournament.py --git-push cycle remains the actual fix.
    $mergeBase = (& git -c safe.directory=$Repo merge-base HEAD origin/neo-website-v2).Trim()
    if ($mergeBase -ne $local) { Write-Output "HARD_STOP: local=$local remote=$remote; true divergence, no automatic overwrite -- run --live --collect-only by hand to preserve official data while this is resolved"; exit 2 }
    & git -c safe.directory=$Repo merge --ff-only origin/neo-website-v2
    if ($LASTEXITCODE -ne 0) { Write-Output "HARD_STOP: fast-forward sync from origin failed unexpectedly"; exit 2 }
    $local = (& git -c safe.directory=$Repo rev-parse HEAD).Trim()
    Write-Output "AUTO-SYNCED: fast-forwarded local to $local before running the cycle"
  }
  if (Test-Path $InternalLock) {
    $iraw = (Get-Content -Raw -LiteralPath $InternalLock -ErrorAction SilentlyContinue).Trim()
    $ipid = 0; [void][int]::TryParse(($iraw -split '\s+')[0], [ref]$ipid)
    $iproc = if ($ipid) { Get-CimInstance Win32_Process -Filter "ProcessId=$ipid" -ErrorAction SilentlyContinue } else { $null }
    $iage = ((Get-Date) - (Get-Item -LiteralPath $InternalLock).LastWriteTime).TotalSeconds
    if ($iproc) { Write-Output "SKIP_WAIT: active cycle process pid=$ipid"; exit 0 }
    if ($iage -ge 1500) { Remove-Item -LiteralPath $InternalLock -Force } else { Write-Output "HARD_STOP: internal lock has no live owner but is too young (age=${iage}s)"; exit 2 }
  }
  # GENERIC ENTRY POINT (was: direct call to
  # 96_ok_open_r1_active_cycle.py --live --git-push). run_tournament.py
  # resolves the currently active tournament itself (DISCOVERY), infers
  # its real current stage from on-disk artifacts, and dispatches to
  # whichever per-stage script that stage actually needs -- 96 while R1
  # is live, but 99/101/build_current_round_page.py etc. once the
  # tournament moves past R1, with no change to this wrapper or its
  # schedule. --git-push mirrors script 96's own opt-in commit+push
  # behavior generically for whichever action actually ran.
  $cycleOutput = & $Python 'klpga_pipeline\scripts\run_tournament.py' --git-push
  $cycleExit = $LASTEXITCODE
  $cycleOutput | ForEach-Object { Write-Output $_ }
  if ($cycleExit -ne 0) { exit $cycleExit }

  # TOURNAMENT-CLOSE AUTO-STOP: run_tournament.py's own JSON summary
  # carries stop_active_cycle=true once POSTMORTEM has genuinely run --
  # i.e. the whole tournament lifecycle (not just R1) is complete.
  # Before run_tournament.py existed, only script 96's R1-close signal
  # was available, so this schedule had to be re-enabled by hand for
  # every later stage; now the same 30-minute task can safely run
  # across R1 -> R2 -> R3/FINAL -> POSTMORTEM unattended, and this is
  # the one place that ever turns it off. Parse the last JSON summary
  # line of stdout and, if it reports the tournament closed, disable
  # (never delete -- keeps history and Enable-ScheduledTask trivially
  # reversible for the next tournament) the recurring schedule so
  # cycles genuinely stop firing.
  $lastJsonLine = ($cycleOutput | Where-Object { $_ -match '^\{.*\}$' } | Select-Object -Last 1)
  if ($lastJsonLine) {
    try {
      $parsed = $lastJsonLine | ConvertFrom-Json
      if ($parsed.stop_active_cycle -eq $true) {
        Write-Output "TOURNAMENT CLOSED (stop_active_cycle=true) -- disabling scheduled task '$TaskName'"
        Disable-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Out-Null
      }
    } catch {
      Write-Output "WARN: could not parse cycle JSON output for the close-cycle stop signal: $($_.Exception.Message)"
    }
  }
} catch { Write-Output ('HARD_STOP: ' + $_.Exception.Message); exit 2 }
finally {
  Remove-Item -LiteralPath $Lock -Force -ErrorAction SilentlyContinue
  Stop-Transcript | Out-Null
}
