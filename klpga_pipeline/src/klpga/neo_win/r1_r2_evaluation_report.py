"""BETA #001 R1 -> R2 evaluation pipeline, Section D: player-level
evaluation report. Joins the frozen R1 field (Section A) to the
reconciled real R2 outcomes (Section B) into
`klpga.neo_win.cut_evaluation.PlayerCutEvaluationRow`s, then reuses
that module's own `best_and_worst_predictions` as the SOLE ranking
rule for "TOP 5 BEST" / "TOP 5 BIGGEST MISSES" — never a manually
curated list, per the spec's own requirement.

Only frozen R1 players are evaluated (this evaluates R1 PREDICTIONS;
a player who appears only in the real R2 field with no frozen R1
prediction has nothing to evaluate). A frozen R1 player missing a real
R1_MAKE_CUT_probability value is EXCLUDED from evaluation (never a
fabricated 0.0/100.0) and reported separately in
`excluded_missing_r1_probability`. A frozen R1 player absent from the
reconciled R2 set entirely is scored with CUT_OUTCOME_UNRESOLVED (see
klpga.neo_win.r1_to_r2_reconciliation's own docstring) — excluded from
headline metrics by cut_evaluation's own WD/DQ/UNRESOLVED policy, but
never silently dropped from the row list.
"""
from __future__ import annotations

import csv
from pathlib import Path

from klpga.neo_win.cut_evaluation import (
    CUT_OUTCOME_UNRESOLVED,
    PlayerCutEvaluationRow,
    best_and_worst_predictions,
)
from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
from klpga.neo_win.r1_to_r2_reconciliation import PlayerR2Reconciled


def build_player_cut_evaluation_rows(
    frozen_r1: list[PlayerR1Frozen], reconciled_r2: list[PlayerR2Reconciled]
) -> tuple[list[PlayerCutEvaluationRow], list[str]]:
    """Returns (rows, excluded_missing_r1_probability) — the second
    list is the player_codes SKIPPED because their frozen R1 row had
    no real r1_make_cut_probability_pct value (SKIP + LOG, never a
    fabricated prediction)."""
    reconciled_by_code = {r.player_code: r for r in reconciled_r2}
    rows: list[PlayerCutEvaluationRow] = []
    excluded: list[str] = []
    for f in frozen_r1:
        if f.r1_make_cut_probability_pct is None:
            excluded.append(f.player_code)
            continue
        r = reconciled_by_code.get(f.player_code)
        outcome = r.r2_outcome if r is not None else CUT_OUTCOME_UNRESOLVED
        rows.append(
            PlayerCutEvaluationRow(
                player_code=f.player_code,
                player_name=f.player_name,
                r1_rank=f.r1_actual_rank,
                r1_score_to_par=f.r1_actual_score_to_par,
                r1_make_cut_pct=f.r1_make_cut_probability_pct,
                r2_outcome=outcome,
            )
        )
    return rows, excluded


_CSV_FIELDNAMES: tuple[str, ...] = (
    "player_code", "player_name", "r1_rank", "r1_score_to_par", "r1_make_cut_pct",
    "predicted_cut_at_50", "actual_r2_status", "actual_cut", "absolute_probability_error",
)


def _row_to_csv_dict(r: PlayerCutEvaluationRow) -> dict:
    return {
        "player_code": r.player_code,
        "player_name": r.player_name,
        "r1_rank": "" if r.r1_rank is None else r.r1_rank,
        "r1_score_to_par": "" if r.r1_score_to_par is None else r.r1_score_to_par,
        "r1_make_cut_pct": r.r1_make_cut_pct,
        "predicted_cut_at_50": r.predicted_cut_at_50,
        "actual_r2_status": r.r2_outcome,
        "actual_cut": "" if r.actual_cut is None else r.actual_cut,
        "absolute_probability_error": "" if r.absolute_probability_error is None else round(r.absolute_probability_error, 6),
    }


def write_player_evaluation_csv(rows: list[PlayerCutEvaluationRow], out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow(_row_to_csv_dict(r))


def top5_best_and_biggest_misses(rows: list[PlayerCutEvaluationRow]) -> dict:
    """The auto-identified TOP 5 BEST / TOP 5 BIGGEST MISSES — ranked
    ONLY by cut_evaluation.best_and_worst_predictions's deterministic
    absolute_probability_error rule (never cherry-picked)."""
    best, worst = best_and_worst_predictions(rows, n=5)
    return {
        "top5_best": [
            {"player_code": r.player_code, "player_name": r.player_name, "absolute_probability_error": round(r.absolute_probability_error, 6)}
            for r in best
        ],
        "top5_biggest_misses": [
            {"player_code": r.player_code, "player_name": r.player_name, "absolute_probability_error": round(r.absolute_probability_error, 6)}
            for r in worst
        ],
    }
