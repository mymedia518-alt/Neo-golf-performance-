"""BETA #001 FINAL validation — R3 -> R4 next-round prediction
evaluation. A NEW, parallel module (never modifies `klpga.neo_win.
round_update_r3` or any other #001 model code): given the SAME
`PlayerR3SimInput` objects `klpga.neo_win.round_update_r3.
build_r3_sim_inputs_from_frozen_snapshot` already produces at POST-R3
time (the caller re-obtains them via that exact, unmodified function --
this module never re-derives expected_round_score_to_par/spread
itself), joins them against the real Round-4 result and scores the
model's own remaining-round distribution against what actually
happened.

======================================================================
POPULATION — must match simulate_post_round3's own cutmaker filter
======================================================================
Only players `simulate_post_round3` itself actually simulates for R4
(made_cut is True, with real r1/r2/r3 scores) are evaluated here --
anyone `simulate_post_round3` would have excluded (a confirmed CUT
player, or a cutmaker missing real prior-round data) is not evaluated
either. This is the SAME filter, re-applied here (not imported, since
`simulate_post_round3` doesn't expose it as a standalone helper) so
this module never scores a population the real prediction never
actually covered.

======================================================================
MISSING DATA
======================================================================
A real, eligible cutmaker with no real Round-4 score (WD/DQ between R3
and R4 -- a real, legitimate outcome, not a data error) is reported in
`missing_r4_players`, excluded from the per-player rows AND from every
aggregate statistic -- never a fabricated actual/error/z_score.

======================================================================
PROVENANCE FINGERPRINT
======================================================================
`compute_input_fingerprint` hashes the EXACT r1/r2/r3/made_cut inputs a
caller passed to `build_r3_sim_inputs_from_frozen_snapshot` -- a
canonical, sorted, deterministic string so two independent runs against
the same real DB state produce an identical hash (order-independent
dict iteration never affects it). Recorded for full audit provenance
even though, per the current model code, mu/sigma (expected_round_
score_to_par/spread) are derived ONLY from the frozen PRE snapshot's
own feature_values (population-mean shrinkage is computed over every
`pre_snapshot.predictions` entrant, independent of r1/r2/r3/made_cut) --
r1/r2/r3/made_cut only decide which players `build_r3_sim_inputs_from_
frozen_snapshot` reports as `missing` and what real cumulative score
each PlayerR3SimInput carries, never the mu/sigma VALUES themselves.
This fingerprint documents exactly what live DB state was read at
evaluation time; it is not evidence that mu/sigma would differ under a
different one.
"""
from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from klpga.neo_win.round_update_r3 import PlayerR3SimInput

_R3_R4_EVALUATION_CSV_FIELDNAMES: tuple[str, ...] = (
    "player_code", "player_name", "r3_total_score_to_par",
    "expected_r4_score_to_par", "r4_spread", "actual_r4_score_to_par",
    "prediction_error", "absolute_error", "z_score",
)


@dataclass(frozen=True)
class PlayerR3R4Evaluation:
    player_code: str
    player_name: str
    r3_total_score_to_par: float
    expected_r4_score_to_par: float
    r4_spread: float
    actual_r4_score_to_par: Optional[float]
    prediction_error: Optional[float]
    absolute_error: Optional[float]
    z_score: Optional[float]


def _r4_eligible_cutmakers(sim_inputs: list[PlayerR3SimInput]) -> list[PlayerR3SimInput]:
    """The SAME cutmaker filter simulate_post_round3 applies internally
    (round_update_r3.py, unmodified) -- re-applied here, not imported,
    since that function doesn't expose the filter as a standalone
    helper. Kept intentionally identical so this module never evaluates
    a population the real POST-R3 simulation didn't also cover."""
    return [
        p for p in sim_inputs
        if p.made_cut is True and p.r1_score_to_par is not None and p.r2_score_to_par is not None
        and p.r3_score_to_par is not None
    ]


def build_r3_r4_evaluation_rows(
    sim_inputs: list[PlayerR3SimInput],
    r4_scores: dict[str, float],
) -> tuple[list[PlayerR3R4Evaluation], list[str]]:
    """Pure function -- no I/O. `sim_inputs` must be the direct,
    unmodified return value of `klpga.neo_win.round_update_r3.
    build_r3_sim_inputs_from_frozen_snapshot` (the caller's
    responsibility -- this function never calls it itself, and never
    recomputes expected_round_score_to_par/spread). Returns
    (rows, missing_r4_players)."""
    eligible = _r4_eligible_cutmakers(sim_inputs)
    rows: list[PlayerR3R4Evaluation] = []
    missing_r4: list[str] = []

    for p in eligible:
        r3_total = p.r1_score_to_par + p.r2_score_to_par + p.r3_score_to_par
        actual = r4_scores.get(p.player_code)
        if actual is None:
            missing_r4.append(p.player_code)
        error = (actual - p.expected_round_score_to_par) if actual is not None else None
        abs_error = abs(error) if error is not None else None
        z = (error / p.spread) if error is not None else None
        rows.append(
            PlayerR3R4Evaluation(
                player_code=p.player_code, player_name=p.player_name,
                r3_total_score_to_par=r3_total,
                expected_r4_score_to_par=p.expected_round_score_to_par, r4_spread=p.spread,
                actual_r4_score_to_par=actual, prediction_error=error, absolute_error=abs_error, z_score=z,
            )
        )
    return rows, missing_r4


def aggregate_r3_r4_evaluation(rows: list[PlayerR3R4Evaluation]) -> dict:
    """Pure function -- computed ONLY over rows with a real
    actual_r4_score_to_par (never over a missing/fabricated value)."""
    evaluated = [r for r in rows if r.actual_r4_score_to_par is not None]
    n = len(evaluated)
    if n == 0:
        return {
            "evaluated_players": 0, "mae": None, "me": None, "rmse": None,
            "within_1_stroke_pct": None, "within_sigma_pct": None,
        }
    errors = [r.prediction_error for r in evaluated]
    abs_errors = [r.absolute_error for r in evaluated]
    mae = sum(abs_errors) / n
    me = sum(errors) / n
    rmse = (sum(e * e for e in errors) / n) ** 0.5
    within_1 = sum(1 for r in evaluated if r.absolute_error <= 1.0) / n * 100.0
    within_sigma = sum(1 for r in evaluated if abs(r.z_score) <= 1.0) / n * 100.0
    return {
        "evaluated_players": n,
        "mae": round(mae, 4), "me": round(me, 4), "rmse": round(rmse, 4),
        "within_1_stroke_pct": round(within_1, 2), "within_sigma_pct": round(within_sigma, 2),
    }


def write_r3_r4_evaluation_csv(rows: list[PlayerR3R4Evaluation], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_R3_R4_EVALUATION_CSV_FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "player_code": r.player_code, "player_name": r.player_name,
                "r3_total_score_to_par": r.r3_total_score_to_par,
                "expected_r4_score_to_par": r.expected_r4_score_to_par, "r4_spread": r.r4_spread,
                "actual_r4_score_to_par": r.actual_r4_score_to_par if r.actual_r4_score_to_par is not None else "unavailable",
                "prediction_error": r.prediction_error if r.prediction_error is not None else "unavailable",
                "absolute_error": r.absolute_error if r.absolute_error is not None else "unavailable",
                "z_score": r.z_score if r.z_score is not None else "unavailable",
            })
    return out_path


def compute_input_fingerprint(
    r1_scores: dict[str, float],
    r2_scores: dict[str, float],
    r3_scores: dict[str, float],
    made_cut_by_player: dict[str, bool],
) -> str:
    """SHA-256 of a canonical, sorted, deterministic text representation
    of exactly the four real-DB inputs passed to `build_r3_sim_inputs_
    from_frozen_snapshot` (besides the frozen PRE snapshot itself) --
    two independent runs against the same real DB state always produce
    the same hash, regardless of dict iteration order."""
    lines = []
    for round_number, scores in ((1, r1_scores), (2, r2_scores), (3, r3_scores)):
        for player_code, value in scores.items():
            lines.append(f"ROUND|{player_code}|{round_number}|{value}")
    for player_code, made_cut in made_cut_by_player.items():
        lines.append(f"MADE_CUT|{player_code}|{made_cut}")
    canonical = "\n".join(sorted(lines))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
