"""NEO GOLF roadmap #3 — evidence-only accuracy evaluation of frozen
PRE/R1/R2/R3 predictions against real, recorded FINAL results
(klpga.neo_win.tournament_history). Never modifies a frozen artifact,
never fits or tunes anything, never touches a probability. Reuses
`klpga.models.metrics`'s fully generic primitives (log_loss, brier_
norm/raw, calibration_report, summarize_model — already documented as
model-agnostic, operating on plain {player_code: probability} dicts) —
Brier/LogLoss/calibration/Top-N-hit-rate math is never reimplemented
here.

======================================================================
EVIDENCE REQUIRED PER (tournament, stage)
======================================================================
A (game_code, stage) pair is evaluable ONLY if ALL of:
  1. The stage's history record exists AND its status is RECORDED
     (never HISTORICAL_SNAPSHOT_MISSING — a missing stage is excluded,
     never treated as a 0% prediction).
  2. That tournament's FINAL stage is ALSO recorded (status RECORDED)
     with exactly one confirmed winner (klpga.neo_win.tournament_
     history.build_final_stage_entry's own "finish_position_numeric==1
     AND winner name field agrees" convention — never inferred here).
  3. The confirmed winner's player_code is present in the stage's own
     predicted field (a real join failure otherwise — reported as an
     exclusion, never silently dropped or guessed).
  4. The stage's own recorded generation time is NOT after FINAL's
     (leakage guard — a "prediction" written after the result was
     already known is not a real forecast and is excluded, never
     scored as one).

Every tournament/stage that fails any check is reported in
`exclusions`, never silently dropped from the record and never
"filled in" with a default probability.

======================================================================
INSUFFICIENT_EVIDENCE, never a manufactured score
======================================================================
`evaluate_stage` returns status="INSUFFICIENT_EVIDENCE" (summary=None,
calibration=None) rather than any metric when zero tournaments clear
the checks above for that stage — a real, honest outcome, not an
error.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from klpga.models.metrics import (
    ModelMetricsSummary,
    TournamentPrediction,
    calibration_report,
    make_prediction,
    summarize_model,
)
from klpga.neo_win.tournament_history import (
    STAGE_FINAL,
    STAGE_ORDER,
    STATUS_RECORDED,
    HistoryStageSnapshot,
    read_full_tournament_history,
)

PREDICTION_STAGES: tuple[str, ...] = tuple(s for s in STAGE_ORDER if s != STAGE_FINAL)


@dataclass(frozen=True)
class ExclusionRecord:
    game_code: str
    stage: str
    reason: str


@dataclass(frozen=True)
class StageEvaluation:
    stage: str
    status: str  # "EVALUATED" | "INSUFFICIENT_EVIDENCE"
    sample_size: int
    summary: Optional[ModelMetricsSummary]
    calibration: Optional[list]
    exclusions: tuple[ExclusionRecord, ...]


def build_tournament_prediction(
    stage_snapshot: Optional[HistoryStageSnapshot],
    final_snapshot: Optional[HistoryStageSnapshot],
) -> tuple[Optional[TournamentPrediction], Optional[ExclusionRecord]]:
    """Pure, never raises. Returns (prediction, None) on success, or
    (None, ExclusionRecord|None) — the exclusion is None only when
    `stage_snapshot` itself is None (nothing was even attempted for
    this tournament/stage — not a reportable failure, just absence)."""
    if stage_snapshot is None:
        return None, None

    game_code, stage = stage_snapshot.game_code, stage_snapshot.stage

    if stage_snapshot.status != STATUS_RECORDED:
        return None, ExclusionRecord(game_code, stage, f"stage status={stage_snapshot.status!r}, not RECORDED")

    if final_snapshot is None:
        return None, ExclusionRecord(game_code, stage, "no FINAL stage recorded for this tournament")
    if final_snapshot.status != STATUS_RECORDED:
        return None, ExclusionRecord(game_code, stage, f"FINAL stage status={final_snapshot.status!r}, not RECORDED")

    winners = [e.player_code for e in final_snapshot.entrants if e.actual_confirmed_winner]
    if len(winners) != 1:
        return None, ExclusionRecord(
            game_code, stage, f"FINAL has {len(winners)} confirmed winner(s) (expected exactly 1)"
        )
    winner = winners[0]

    probabilities = {e.player_code: e.win_pct / 100.0 for e in stage_snapshot.entrants if e.win_pct is not None}
    if not probabilities:
        return None, ExclusionRecord(game_code, stage, "no entrant in this stage has a real win_pct")
    if winner not in probabilities:
        return None, ExclusionRecord(
            game_code, stage, f"confirmed winner {winner!r} is not present in this stage's predicted field"
        )

    if stage_snapshot.source_generated_at_utc and final_snapshot.source_generated_at_utc:
        if stage_snapshot.source_generated_at_utc > final_snapshot.source_generated_at_utc:
            return None, ExclusionRecord(
                game_code, stage, "prediction recorded AFTER the final result (leakage guard) — excluded, never scored"
            )

    prior_n_by_player = {code: 0 for code in probabilities}
    prediction = make_prediction(
        target_event_id=game_code,
        target_game_code=game_code,
        target_start_date=stage_snapshot.source_generated_at_utc or "",
        raw_probabilities=probabilities,
        winner=winner,
        prior_events_n_by_player=prior_n_by_player,
    )
    return prediction, None


def evaluate_stage(tournament_histories: dict[str, dict[str, HistoryStageSnapshot]], stage: str) -> StageEvaluation:
    """`tournament_histories` is {game_code: {stage: HistoryStageSnapshot}}
    — one entry per tournament already loaded via `load_tournament_
    histories` below (or hand-built for tests)."""
    predictions: list[TournamentPrediction] = []
    exclusions: list[ExclusionRecord] = []
    for stages in tournament_histories.values():
        stage_snapshot = stages.get(stage)
        final_snapshot = stages.get(STAGE_FINAL)
        prediction, exclusion = build_tournament_prediction(stage_snapshot, final_snapshot)
        if prediction is not None:
            predictions.append(prediction)
        if exclusion is not None:
            exclusions.append(exclusion)

    if not predictions:
        return StageEvaluation(
            stage=stage, status="INSUFFICIENT_EVIDENCE", sample_size=0,
            summary=None, calibration=None, exclusions=tuple(exclusions),
        )

    summary = summarize_model(stage, predictions)
    calibration = calibration_report(predictions)
    return StageEvaluation(
        stage=stage, status="EVALUATED", sample_size=len(predictions),
        summary=summary, calibration=calibration, exclusions=tuple(exclusions),
    )


def evaluate_all_stages(tournament_histories: dict[str, dict[str, HistoryStageSnapshot]]) -> dict[str, StageEvaluation]:
    return {stage: evaluate_stage(tournament_histories, stage) for stage in PREDICTION_STAGES}


# ----------------------------------------------------------------
# Read-only discovery/loading over neo_tournament_history/ — never
# writes anything, never touches a frozen prediction artifact.
# ----------------------------------------------------------------


def discover_game_codes(history_root: Path) -> list[str]:
    root = Path(history_root)
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir())


def load_tournament_histories(history_root: Path, game_codes: list[str]) -> dict[str, dict[str, HistoryStageSnapshot]]:
    return {game_code: read_full_tournament_history(history_root, game_code) for game_code in game_codes}
