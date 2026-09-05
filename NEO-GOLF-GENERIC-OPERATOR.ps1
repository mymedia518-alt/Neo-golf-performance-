param(
    [Parameter(Mandatory=$true)]
    [string]$Stage,

    [Parameter(Mandatory=$true)]
    [int]$FinalRound,

    [int]$CurrentRound = 0,

    [switch]$ModelReady
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $RepoRoot "klpga_pipeline\src"

$Python = @"
from klpga.tournament_engine import Stage
from klpga.tournament_operator import decide_operator_action

stage = Stage("$Stage")

current = $CurrentRound
if current == 0:
    current = None

decision = decide_operator_action(
    stage,
    final_round_number=$FinalRound,
    current_round_number=current,
    model_ready=("$($ModelReady.IsPresent)" == "True"),
)

print("STAGE=" + decision.stage.value)
print("ACTION=" + decision.action.value)
print("PUBLISH_FACTUAL=" + str(decision.publish_factual))
print("PUBLISH_MODEL=" + str(decision.publish_model))
print("REASON=" + decision.reason)
"@

$Python | python -
if ($LASTEXITCODE -ne 0) {
    throw "GENERIC_OPERATOR_FAILED"
}
