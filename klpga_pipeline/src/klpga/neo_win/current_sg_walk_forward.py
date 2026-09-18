"""RED TEAM MODEL CORRECTION (operator instruction, 2026-09-18):
walk-forward validation of whether current-tournament ROUND-SCOPED
Strokes Gained (R1 SG total, R2 SG total) improves the prediction of a
player's NEXT round (R3) score-to-par, beyond the existing point-in-time
BASE feature (`prior_avg_round_score_to_par` from
klpga.backtest.point_in_time_features -- the same feature family the
production PRE-stage win-probability comparison in klpga.models already
uses).

This module is standalone RESEARCH/VALIDATION only. It does not read or
write any production forecast artifact, and nothing here is wired into
klpga.neo_win.round_update_r2.simulate_post_round2's actual call path.
Promotion to production is a separate, later, explicitly-gated step.

DATA SOURCES (both pre-existing, never newly fetched for this module):
  - `content/website_v2/historical_sg_warehouse.json` -- the corrected,
    multi-event historical SG warehouse (single_round scope rows give
    R1/R2/R3/R4 SG per player per event). 2026090002 (Hana) and
    2026090003 (KB) are both confirmed ABSENT from this file (verified
    by the caller / regression tests), so using it for training never
    leaks either current tournament into its own history.
  - `data/klpga.sqlite` `player_round` table -- the real actual R3
    round_to_par per (game_code, player_id), used as the walk-forward
    TARGET (never SG -- "R3 performance" means the actual round score
    relative to par, the same quantity the production Monte Carlo
    engine's `expected_round_score_to_par` predicts).

LEAKAGE SAFETY: the BASE feature and the walk-forward training/target
split both reuse klpga.backtest.point_in_time_features /
klpga.backtest.temporal verbatim (is_strictly_before: fail-safe, a
missing or tied date excludes rather than includes). No SG row or R3
target row from the target event itself, nor from any event whose
effective date is not STRICTLY earlier than the target event's, is ever
used to fit a model evaluated against that target event.

MODEL FAMILY: four nested linear (OLS, numpy.linalg.lstsq) models,
predicting actual R3 round_to_par:
  BASE       = a + b*BASE
  R1SG       = a + b*BASE + c*R1_SG_TOTAL
  R2SG       = a + b*BASE + c*R2_SG_TOTAL
  R1SG_R2SG  = a + b*BASE + c*R1_SG_TOTAL + d*R2_SG_TOTAL
No coefficient is ever hand-picked or hardcoded (no "70/30", no "SG *
0.2") -- every coefficient is the least-squares fit on the strictly-
prior training corpus for that walk-forward step (or, for the reported
"final" production-candidate coefficients, on the full eligible corpus).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np

from klpga.backtest.point_in_time_features import Corpus, compute_point_in_time_features, load_corpus
from klpga.backtest.temporal import is_strictly_before

MODEL_IDS: tuple[str, ...] = ("BASE", "R1SG", "R2SG", "R1SG_R2SG")

# Minimum strictly-prior training player-rounds required before a
# target event is scored at all -- below this, a 3-4 parameter OLS fit
# is not meaningfully stable. Documented, not silently dropped: events
# skipped for this reason are excluded from n_evaluated_events and
# reported as such by the caller.
MIN_TRAINING_ROWS = 30


@dataclass(frozen=True)
class SgRow:
    game_code: str
    player_id: str
    player_name: str
    effective_date: date
    base: float  # prior_avg_round_score_to_par, point-in-time safe
    base_n: int  # prior_avg_round_score_to_par_n (rounds-weighted denominator)
    r1_sg_total: float
    r2_sg_total: float
    actual_r3_to_par: float


def build_sg_round_index(historical_sg_warehouse: dict) -> dict[tuple[str, str], dict[int, float]]:
    """(game_code, player_id) -> {1: r1_sg_total, 2: r2_sg_total, ...}
    from the warehouse's single_round rows. Never interpolated: a
    missing round for a player is simply absent from the inner dict."""
    idx: dict[tuple[str, str], dict[int, float]] = {}
    for r in historical_sg_warehouse["records"]:
        if r.get("scope") != "single_round":
            continue
        total = r.get("total")
        if total is None:
            continue
        rnd = r.get("round")
        if rnd not in (1, 2):
            continue
        key = (r["game_code"], r["player_id"])
        idx.setdefault(key, {})[rnd] = float(total)
    return idx


def load_r3_actuals(conn: sqlite3.Connection) -> tuple[dict[tuple[str, str], float], dict[str, str]]:
    """(game_code, player_id) -> actual R3 round_to_par, and
    player_id -> player_name, from the real player_round table."""
    r3_actual: dict[tuple[str, str], float] = {}
    names: dict[str, str] = {}
    cur = conn.execute(
        "SELECT game_code, player_id, player_name, round_to_par FROM player_round WHERE round_number = 3"
    )
    for game_code, player_id, player_name, round_to_par in cur.fetchall():
        if round_to_par is None:
            continue
        r3_actual[(game_code, player_id)] = float(round_to_par)
        names[player_id] = player_name
    return r3_actual, names


def build_eligible_rows(
    conn: sqlite3.Connection,
    historical_sg_warehouse: dict,
    *,
    corpus: Optional[Corpus] = None,
) -> list[SgRow]:
    """Every (event, player) with BOTH R1 and R2 round-scoped SG, a
    real actual R3 round_to_par, and a computable point-in-time BASE
    feature (prior_avg_round_score_to_par is not None -- a debuting
    player with zero prior events is excluded from training/evaluation
    here, not given a fabricated BASE)."""
    if corpus is None:
        corpus = load_corpus(conn)
    sg_index = build_sg_round_index(historical_sg_warehouse)
    r3_actual, names = load_r3_actuals(conn)

    rows: list[SgRow] = []
    for (game_code, player_id), sg_by_round in sg_index.items():
        if 1 not in sg_by_round or 2 not in sg_by_round:
            continue
        target = r3_actual.get((game_code, player_id))
        if target is None:
            continue
        eff = corpus.tournament_dates.get(game_code)
        if eff is None or eff.value is None:
            continue
        feats = compute_point_in_time_features(corpus, game_code, eff.value, player_id, names.get(player_id, ""))
        if feats.prior_avg_round_score_to_par is None:
            continue
        rows.append(
            SgRow(
                game_code=game_code,
                player_id=player_id,
                player_name=names.get(player_id, ""),
                effective_date=eff.value,
                base=feats.prior_avg_round_score_to_par,
                base_n=feats.prior_avg_round_score_to_par_n,
                r1_sg_total=sg_by_round[1],
                r2_sg_total=sg_by_round[2],
                actual_r3_to_par=target,
            )
        )
    return rows


def _design_matrix(rows: list[SgRow], model_id: str) -> np.ndarray:
    if model_id == "BASE":
        return np.array([[1.0, r.base] for r in rows])
    if model_id == "R1SG":
        return np.array([[1.0, r.base, r.r1_sg_total] for r in rows])
    if model_id == "R2SG":
        return np.array([[1.0, r.base, r.r2_sg_total] for r in rows])
    if model_id == "R1SG_R2SG":
        return np.array([[1.0, r.base, r.r1_sg_total, r.r2_sg_total] for r in rows])
    raise ValueError(f"unknown model_id: {model_id}")


# Coefficient index -> human label, per model (for reporting).
MODEL_COEF_LABELS: dict[str, tuple[str, ...]] = {
    "BASE": ("intercept", "base"),
    "R1SG": ("intercept", "base", "r1_sg_total"),
    "R2SG": ("intercept", "base", "r2_sg_total"),
    "R1SG_R2SG": ("intercept", "base", "r1_sg_total", "r2_sg_total"),
}


def fit_model(rows: list[SgRow], model_id: str) -> np.ndarray:
    x = _design_matrix(rows, model_id)
    y = np.array([r.actual_r3_to_par for r in rows])
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    return coef


def predict(coef: np.ndarray, rows: list[SgRow], model_id: str) -> np.ndarray:
    x = _design_matrix(rows, model_id)
    return x @ coef


@dataclass
class WalkForwardResult:
    n_player_rounds: int
    n_events: int
    n_evaluated_events: int
    min_training_rows: int
    per_model: dict[str, dict]  # model_id -> {"n", "mae", "rmse"}
    event_wins: dict[str, int]
    final_coefficients: dict[str, dict[str, float]]  # model_id -> {label: value}
    event_level_mae: dict[str, list[float]]  # model_id -> [event_mae, ...] in walk-forward order, one evaluated event per entry


def run_walk_forward(rows: list[SgRow], *, min_training_rows: int = MIN_TRAINING_ROWS) -> WalkForwardResult:
    rows_sorted = sorted(rows, key=lambda r: (r.effective_date, r.game_code, r.player_id))
    events_in_order: list[str] = []
    seen: set[str] = set()
    for r in rows_sorted:
        if r.game_code not in seen:
            seen.add(r.game_code)
            events_in_order.append(r.game_code)

    by_event: dict[str, list[SgRow]] = {}
    for r in rows:
        by_event.setdefault(r.game_code, []).append(r)

    errors: dict[str, list[float]] = {m: [] for m in MODEL_IDS}
    event_wins: dict[str, int] = {m: 0 for m in MODEL_IDS}
    event_level_mae: dict[str, list[float]] = {m: [] for m in MODEL_IDS}
    n_evaluated_events = 0

    for event in events_in_order:
        target_rows = by_event[event]
        target_date = target_rows[0].effective_date
        training_rows = [r for r in rows if r.game_code != event and is_strictly_before(r.effective_date, target_date)]
        if len(training_rows) < min_training_rows:
            continue
        n_evaluated_events += 1

        actual = np.array([r.actual_r3_to_par for r in target_rows])
        event_mae: dict[str, float] = {}
        for m in MODEL_IDS:
            coef = fit_model(training_rows, m)
            preds = predict(coef, target_rows, m)
            abs_err = np.abs(preds - actual)
            errors[m].extend(abs_err.tolist())
            event_mae[m] = float(np.mean(abs_err))
        min_mae = min(event_mae.values())
        for m, v in event_mae.items():
            if abs(v - min_mae) < 1e-9:
                event_wins[m] += 1
            event_level_mae[m].append(v)

    per_model: dict[str, dict] = {}
    for m in MODEL_IDS:
        arr = np.array(errors[m]) if errors[m] else np.array([])
        per_model[m] = {
            "n": int(len(arr)),
            "mae": float(np.mean(arr)) if len(arr) else None,
            "rmse": float(np.sqrt(np.mean(arr**2))) if len(arr) else None,
        }

    final_coefficients: dict[str, dict[str, float]] = {}
    for m in MODEL_IDS:
        coef = fit_model(rows, m)
        labels = MODEL_COEF_LABELS[m]
        final_coefficients[m] = {label: float(v) for label, v in zip(labels, coef)}

    return WalkForwardResult(
        n_player_rounds=len(rows),
        n_events=len(events_in_order),
        n_evaluated_events=n_evaluated_events,
        min_training_rows=min_training_rows,
        per_model=per_model,
        event_wins=event_wins,
        final_coefficients=final_coefficients,
        event_level_mae=event_level_mae,
    )
