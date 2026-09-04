<#
NEO-GOLF-R1-INSTALL-SCHEDULE.ps1

Registers (or re-registers, idempotently) the Windows Task Scheduler entry
that runs NEO-GOLF-R1-ACTIVE-30MIN.ps1 every 30 minutes. Before this
script existed, that Task Scheduler entry had to be created by hand
through the Task Scheduler GUI (or an ad hoc schtasks/Register-
ScheduledTask command typed once and never captured anywhere) -- a real
human-intervention step on every new live round and every time this
machine is reprovisioned. This script replaces that manual step.

Run this ONCE on the operator PC before an OK Open round's tee time:
    powershell -NoProfile -ExecutionPolicy Bypass -File .\NEO-GOLF-R1-INSTALL-SCHEDULE.ps1

Safe to re-run at any time -- it unregisters any existing task with the
same name first, then registers fresh, so re-running after this script or
NEO-GOLF-R1-ACTIVE-30MIN.ps1 changes always picks up the latest version
rather than silently keeping a stale registration.

STOPPING: NEO-GOLF-R1-ACTIVE-30MIN.ps1 now disables (never deletes) this
task automatically once script 96 reports the round has closed
(stop_active_cycle: true in its JSON summary) -- see the R1-CLOSE
AUTO-STOP block in that script. Re-enable for the next round with:
    Enable-ScheduledTask -TaskName 'NEO-GOLF-R1-ACTIVE-30MIN'
or simply re-run this installer, which always leaves the task enabled.
To stop early by hand at any time:
    Disable-ScheduledTask -TaskName 'NEO-GOLF-R1-ACTIVE-30MIN'

HONESTY NOTE: this script has never actually been executed against a real
Windows Task Scheduler -- the environment that wrote it is a Linux
sandbox with no Windows runtime, no PowerShell interpreter, and no route
to klpga.co.kr at all (confirmed repeatedly: no pwsh, no C:\, no /mnt/c).
It is written against the standard, documented ScheduledTasks module
cmdlets and reviewed carefully, but it has not been run for real. The
operator running it for the first time should verify the registration
(see the Get-ScheduledTask line this script prints at the end) and report
back anything that fails so it can be fixed.
#>
$ErrorActionPreference = 'Stop'

$TaskName = 'NEO-GOLF-R1-ACTIVE-30MIN'
$Repo = 'C:\Users\user\Desktop\Neo-golf-performance-live'
$ScriptPath = Join-Path $Repo 'NEO-GOLF-R1-ACTIVE-30MIN.ps1'

if (-not (Test-Path $ScriptPath)) {
  throw "Cannot find $ScriptPath -- run this installer from a machine with the repo checked out at that exact path (or edit `$Repo above to match), since NEO-GOLF-R1-ACTIVE-30MIN.ps1 itself also hardcodes that path."
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
  Write-Output "Existing task '$TaskName' found -- unregistering before re-registering with the current definition."
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

# Fire once "now", then repeat every 30 minutes for a long window (10
# years) -- Task Scheduler has no literal "run forever" repetition; this
# is the standard idiom for an effectively-indefinite recurring task. This
# long window is only a safety ceiling, not the real stop mechanism: the
# wrapper script disables the task itself once R1 genuinely closes (see
# the R1-CLOSE AUTO-STOP block in NEO-GOLF-R1-ACTIVE-30MIN.ps1).
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes 30) `
  -RepetitionDuration (New-TimeSpan -Days 3650)

# ExecutionTimeLimit caps a single run well under the 30-minute cadence,
# and MultipleInstances IgnoreNew refuses to start a second run if one is
# still going -- both are defense-in-depth on top of (not a replacement
# for) NEO-GOLF-R1-ACTIVE-30MIN.ps1's own file-lock check, which is the
# primary overlap guard and also correctly detects a run that is stuck
# past its OS-level time limit.
$settings = New-ScheduledTaskSettingsSet `
  -MultipleInstances IgnoreNew `
  -StartWhenAvailable `
  -DontStopOnIdleEnd `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 25)

# Runs under the currently logged-in operator account (Interactive logon),
# matching how this machine has always been operated in this project -- a
# human is expected to be logged in on a live tournament day. Running
# unattended across a logoff/reboot would need a S4U or SYSTEM principal
# with a stored credential; deliberately not set up here without an
# explicit ask, since managing that credential is a real security
# decision this script should not make silently on the operator's behalf.
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
  -Description 'NEO GOLF DATA: OK Open R1 30-minute active collection cycle (NEO-GOLF-R1-ACTIVE-30MIN.ps1). Auto-disables itself once R1 closes. Re-run NEO-GOLF-R1-INSTALL-SCHEDULE.ps1 before the next live round to re-register.' `
  | Out-Null

Write-Output "Registered scheduled task '$TaskName' -- runs $ScriptPath every 30 minutes, starting now."
Write-Output "Verify with:        Get-ScheduledTask -TaskName '$TaskName' | Format-List *"
Write-Output "Disable by hand:    Disable-ScheduledTask -TaskName '$TaskName'"
Write-Output "Re-enable later:    Enable-ScheduledTask -TaskName '$TaskName'"
