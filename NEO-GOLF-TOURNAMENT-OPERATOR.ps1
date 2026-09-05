param(
    [switch]$Promote
)

$ErrorActionPreference = 'Stop'

$Repo = $PSScriptRoot
$Python = 'python'

$DataRoot = if ($env:NEO_DATA_ROOT) {
    $env:NEO_DATA_ROOT
} else {
    Join-Path $Repo 'klpga_pipeline\data'
}

$LogRoot = if ($env:NEO_LOG_ROOT) {
    $env:NEO_LOG_ROOT
} else {
    Join-Path $Repo 'logs\tournament-engine'
}

$TournamentConfigPath = Join-Path $PSScriptRoot "klpga_pipeline\config\active_tournament.json"

if (-not (Test-Path -LiteralPath $TournamentConfigPath)) {
    throw "Tournament config missing: $TournamentConfigPath"
}

$TournamentConfig = Get-Content `
    -LiteralPath $TournamentConfigPath `
    -Raw `
    -Encoding UTF8 |
    ConvertFrom-Json

$GameCode = [string]$TournamentConfig.game_code
$TournamentName = [string]$TournamentConfig.tournament_name
$FinalRound = [int]$TournamentConfig.final_round_number
$CurrentRound = [int]$TournamentConfig.current_round_number
$ValidatedStage = [string]$TournamentConfig.validated_stage
$CutAfterRound = $TournamentConfig.cut_after_round
$ModelReady = [bool]$TournamentConfig.model_ready

if ([string]::IsNullOrWhiteSpace($GameCode)) {
    throw "Tournament config game_code required"
}

if ([string]::IsNullOrWhiteSpace($TournamentName)) {
    throw "Tournament config tournament_name required"
}

if ($FinalRound -lt 2) {
    throw "Tournament config final_round_number invalid"
}

if ($CurrentRound -lt 1 -or $CurrentRound -gt $FinalRound) {
    throw "Tournament config current_round_number invalid"
}

if ([string]::IsNullOrWhiteSpace($ValidatedStage)) {
    throw "Tournament config validated_stage required"
}

if ($null -ne $CutAfterRound) {
    $CutAfterRound = [int]$CutAfterRound

    if (
        $CutAfterRound -lt 1 -or
        $CutAfterRound -ge $FinalRound
    ) {
        throw "Tournament config cut_after_round invalid"
    }
}

$Lock = Join-Path $LogRoot 'tournament-engine.lock'
$InternalLock = Join-Path $Repo 'klpga_pipeline\content\website_v2\.tournament_engine.lock'

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logPath = Join-Path $LogRoot "tournament-engine-$stamp.json"

$result = [ordered]@{
    started_at = (Get-Date).ToUniversalTime().ToString('o')
    game_code = $GameCode
    stage = $ValidatedStage
    round = $CurrentRound
    promote = [bool]$Promote
    decision = 'HARD_STOP'
    reason = ''
    commit = ''
    remote = ''
    exit_code = 2
}

$exitCode = 2

try {
    if (Test-Path $Lock) {
        $raw = (Get-Content -Raw $Lock).Trim()
        $ownerPid = 0
        [void][int]::TryParse(
            ($raw -split '\s+')[0],
            [ref]$ownerPid
        )

        $owner = if ($ownerPid) {
            Get-CimInstance Win32_Process `
                -Filter "ProcessId=$ownerPid" `
                -ErrorAction SilentlyContinue
        } else {
            $null
        }

        $age = (
            (Get-Date) -
            (Get-Item -LiteralPath $Lock).LastWriteTime
        ).TotalSeconds

        if ($owner) {
            $result.decision = 'SKIP_WAIT'
            $result.reason = "active lock pid=$ownerPid"
            $exitCode = 0
            return
        }

        if ($age -lt 1800) {
            $result.reason = "stale lock too young age=$([int]$age)s"
            $exitCode = 2
            return
        }

        Remove-Item -LiteralPath $Lock -Force
    }

    "$PID $(Get-Date -Format o)" |
        Set-Content -LiteralPath $Lock -Encoding utf8

    Set-Location $Repo
    $env:GIT_TERMINAL_PROMPT = '0'

    git -c safe.directory=$Repo fetch origin | Out-Null

    $branch = (
        git -c safe.directory=$Repo branch --show-current
    ).Trim()

    if ($branch -ne 'neo-tournament-engine-v1') {
        $result.reason = "wrong branch=$branch"
        $exitCode = 2
        return
    }

    $local = (
        git -c safe.directory=$Repo rev-parse HEAD
    ).Trim()

    $remote = (
        git -c safe.directory=$Repo `
            rev-parse origin/neo-tournament-engine-v1
    ).Trim()

    $result.commit = $local
    $result.remote = $remote

    if ($local -ne $remote) {
        $base = (
            git -c safe.directory=$Repo `
                merge-base HEAD origin/neo-tournament-engine-v1
        ).Trim()

        if ($base -ne $local) {
            $result.reason = "true divergence local=$local remote=$remote"
            $exitCode = 2
            return
        }

        git -c safe.directory=$Repo `
            merge --ff-only origin/neo-tournament-engine-v1 |
            Out-Null
    }

    # Fail closed on dirty SOURCE files.
    # Generated candidate/output content is tolerated.
    $dirty = @(
        git -c safe.directory=$Repo status --porcelain |
        Where-Object {
            $_ -and
            $_ -notmatch '^\?\? \.pytest-' -and
            $_ -notmatch '^\?\? \.test-' -and
            $_ -notmatch '^\s*[MADRCU?]{1,2} klpga_pipeline/candidate/' -and
            $_ -notmatch '^\s*[MADRCU?]{1,2} klpga_pipeline/outputs/' -and
            $_ -notmatch '^\s*[MADRCU?]{1,2} klpga_pipeline/content/website_v2/' -and
            $_ -notmatch '^\?\? klpga_pipeline/content/website_v2/' -and
            $_ -notmatch 'NEO_RECOVER\.bat' -and
            $_ -notmatch 'NEO-GOLF-TOURNAMENT-OPERATOR\.ps1' -and
            $_ -notmatch '\.r1_active_cycle\.lock' -and
            $_ -notmatch '\.tournament_engine\.lock'
        }
    )

    if ($dirty.Count -gt 0) {
        $result.reason = 'unapproved dirty source worktree: ' + ($dirty -join '; ')
        $exitCode = 2
        return
    }

    $env:PYTHONPATH = (
        (Join-Path $Repo 'klpga_pipeline\src') +
        ';' +
        (Join-Path $Repo 'klpga_pipeline\scripts')
    )

    $promoteLiteral = if ($Promote) { 'True' } else { 'False' }

    $py = @"
from pathlib import Path
import hashlib
import json
import neo_tournament_runtime as runtime

ROOT = Path(r'$Repo')
DATA = Path(r'$DataRoot')
GAME = '$GameCode'
ROUND = $CurrentRound

work = ROOT / 'klpga_pipeline' / 'outputs' / 'neo_tournament_engine' / GAME
target = work / 'operator-target' / f'round-{ROUND}' / 'index.html'
target.parent.mkdir(parents=True, exist_ok=True)

live = ROOT / 'docs' / 'index.html'
before = hashlib.sha256(live.read_bytes()).hexdigest() if live.exists() else None

CUT_AFTER = $(
    if ($null -eq $CutAfterRound) {
        'None'
    } else {
        [string]$CutAfterRound
    }
)

MODEL_READY = $(
    if ($ModelReady) {
        'True'
    } else {
        'False'
    }
)

state = runtime.RuntimeState(
    game_code=GAME,
    final_round_number=$FinalRound,
    current_round_number=ROUND,
    validated_stage='$ValidatedStage',
    cut_after_round=CUT_AFTER,
    model_ready=MODEL_READY,
)

snapshot, decision, publication = runtime.run_publication_once(
    state,
    tournament_name=r'$TournamentName',
    cache_dir=DATA / 'raw_cache' / 'http',
    frozen_root=work / 'operator-frozen',
    candidate_root=work / 'operator-candidate',
    target_path=target,
    promote=$promoteLiteral,
)

after = hashlib.sha256(live.read_bytes()).hexdigest() if live.exists() else None

if not $promoteLiteral and before != after:
    raise RuntimeError('LIVE_CHANGED_DURING_DRY_RUN')

if decision.should_publish_model:
    raise RuntimeError('MODEL_PUBLICATION_LEAK')

print(json.dumps({
    'official_rows': len(snapshot.players),
    'observed_stage': decision.observed_stage,
    'publication_mode': decision.publication_mode,
    'next_gate': decision.next_gate,
    'unfinished_count': decision.unfinished_count,
    'publish_factual': decision.should_publish_factual,
    'publish_model': decision.should_publish_model,
    'disable_cycle': decision.should_disable_cycle,
    'promote': $promoteLiteral,
    'live_before': before,
    'live_after': after,
}, ensure_ascii=False))
"@

    $output = $py | & $Python -
    $code = $LASTEXITCODE

    if ($code -ne 0) {
        $result.reason = "generic runtime exit=$code"
        $exitCode = $code
        return
    }

    $runtimeResult = $output |
        Select-Object -Last 1 |
        ConvertFrom-Json

    $result.observed_stage = $runtimeResult.observed_stage
    $result.publication_mode = $runtimeResult.publication_mode
    $result.next_gate = $runtimeResult.next_gate
    $result.unfinished_count = $runtimeResult.unfinished_count
    $result.publish_model = $runtimeResult.publish_model

    if ($runtimeResult.publish_model) {
        $result.reason = 'model publication leak'
        $exitCode = 2
        return
    }

    if ($runtimeResult.next_gate -eq 'CUT_CONFIRMATION') {
        $result.decision = 'WAIT_CUT_CONFIRMATION'
        $result.reason = 'official configured cut round complete; model remains blocked'
        $exitCode = 0
        return
    }

    if ($runtimeResult.next_gate -eq 'FINAL_VALIDATION') {
        $result.decision = 'WAIT_FINAL_VALIDATION'
        $result.reason = 'official final round complete; awaiting final validation'
        $exitCode = 0
        return
    }

    if ($runtimeResult.next_gate -eq 'NEXT_STAGE_VALIDATION') {
        $result.decision = 'WAIT_NEXT_STAGE_VALIDATION'
        $result.reason = 'official round complete; awaiting next validated stage'
        $exitCode = 0
        return
    }

    $result.decision = 'FACTUAL_CYCLE_PASS'
    $result.reason = 'generic tournament runtime completed'
    $exitCode = 0
}
catch {
    $result.reason = $_.Exception.Message
    $exitCode = 2
}
finally {
    $result.finished_at = (
        Get-Date
    ).ToUniversalTime().ToString('o')

    $result.exit_code = $exitCode

    ($result | ConvertTo-Json -Depth 8) |
        Set-Content -LiteralPath $logPath -Encoding utf8

    if (Test-Path $Lock) {
        Remove-Item -LiteralPath $Lock `
            -Force `
            -ErrorAction SilentlyContinue
    }

    Write-Host ($result | ConvertTo-Json -Depth 8)
}

exit $exitCode
