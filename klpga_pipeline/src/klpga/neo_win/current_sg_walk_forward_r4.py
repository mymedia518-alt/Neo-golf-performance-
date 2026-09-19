"""HANA R3 -> FINAL PIPELINE (operator instruction, 2026-09-19):
walk-forward validation of whether current-tournament ROUND-SCOPED
Strokes Gained through R3 (R1 SG total, R2 SG total, R3 SG total)
improves the prediction of a player's NEXT round (R4/FINAL) score-to-
par, beyond the existing point-in-time BASE feature.

This is the SAME model architecture and methodology already validated
and promoted to production for R1SG_R2SG (predicting R3 from R1+R2 SG,
see current_sg_walk_forward.py) -- extended by one round, never a new
kind of model: linear OLS, walk-forward-by-event, the identical
5-criterion promotion gate (paired Wilcoxon p<0.05, bootstrap 95% CI
excludes zero, all included SG coefficients negative, chronological
split-half same-sign). No coefficient is ever hand-picked; every
coefficient is the least-squares fit on the strictly-prior training
corpus.

DATA SOURCES (both pre-existing, never newly fetched):
  - content/website_v2/historical_sg_warehouse.json -- single_round
    rows give R1/R2/R3/R4 SG per player per event. 2026090002 (Hana)
    and 2026090003 (KB) are both confirmed ABSENT (verified by the
    caller / tests), so training never leaks either current tournament
    into its own history.
  - data/klpga.sqlite `player_round` table -- the real actual R4
    round_to_par per (game_code, player_id), the walk-forward TARGET.

LEAKAGE SAFETY: identical to current_sg_walk_forward.py -- reuses
klpga.backtest.point_in_time_features / klpga.backtest.temporal
verbatim (is_strictly_before: fail-safe, a missing or tied date
excludes rather than includes).

MODEL FAMILY: nested linear (OLS) models predicting actual R4
round_to_par:
  BASE              = a + b*BASE
  R1SG_R2SG_R3SG    = a + b*BASE + c*R1_SG_TOTAL + d*R2_SG_TOTAL + e*R3_SG_TOTAL
Intermediate single/pair-SG variants are included only for reporting
context (never promoted on their own without passing the same gate).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np

from klpga.backtest.point_in_time_features import Corpus, compute_point_in_time_features, load_corpus
from klpga.backtest.temporal import is_strictly_before

MODEL_IDS: tuple[str, ...] = ("BASE", "R1SG", "R2SG", "R3SG", "R1SG_R2SG_R3SG")

MIN_TRAINING_ROWS = 30


@dataclass(frozen=True)
class SgRowR4:
    game_code: str
    player_id: str
    player_name: str
    effective_date: date
    base: float
    base_n: int
    r1_sg_total: float
    r2_sg_total: float
    r3_sg_total: float
    actual_r4_to_par: float


def build_sg_round_index_r123(historical_sg_warehouse: dict) -> dict[tuple[str, str], dict[int, float]]:
    """(game_code, player_id) -> {1: r1_sg_total, 2: r2_sg_total, 3: r3_sg_total}
    from the warehouse's single_round rows. Never interpolated."""
    idx: dict[tuple[str, str], dict[int, float]] = {}
    for r in historical_sg_warehouse["records"]:
        if r.get("scope") != "single_round":
            continue
        total = r.get("total")
        if total is None:
            continue
        rnd = r.get("round")
        if rnd not in (1, 2, 3):
            continue
        key = (r["game_code"], r["player_id"])
        idx.setdefault(key, {})[rnd] = float(total)
    return idx


def load_r4_actuals(conn: sqlite3.Connection) -> tuple[dict[tuple[str, str], float], dict[str, str]]:
    r4_actual: dict[tuple[str, str], float] = {}
    names: dict[str, str] = {}
    cur = conn.execute(
        "SELECT game_code, player_id, player_name, round_to_par FROM player_round WHERE round_number = 4"
    )
    for game_code, player_id, player_name, round_to_par in cur.fetchall():
        if round_to_par is None:
            continue
        r4_actual[(game_code, player_id)] = float(round_to_par)
        names[player_id] = player_name
    return r4_actual, names


def build_eligible_rows_r4(
    conn: sqlite3.Connection,
    historical_sg_warehouse: dict,
    *,
    corpus: Optional[Corpus] = None,
) -> list[SgRowR4]:
    """Every (event, player) with ALL THREE of R1/R2/R3 round-scoped
    SG, a real actual R4 round_to_par, and a computable point-in-time
    BASE feature."""
    if corpus is None:
        corpus = load_corpus(conn)
    sg_index = build_sg_round_index_r123(historical_sg_warehouse)
    r4_actual, names = load_r4_actuals(conn)

    rows: list[SgRowR4] = []
    for (game_code, player_id), sg_by_round in sg_index.items():
        if 1 not in sg_by_round or 2 not in sg_by_round or 3 not in sg_by_round:
            continue
        target = r4_actual.get((game_code, player_id))
        if target is None:
            continue
        eff = corpus.tournament_dates.get(game_code)
        if eff is None or eff.value is None:
            continue
        feats = compute_point_in_time_features(corpus, game_code, eff.value, player_id, names.get(player_id, ""))
        if feats.prior_avg_round_score_to_par is None:
            continue
        rows.append(
            SgRowR4(
                game_code=game_code,
                player_id=player_id,
                player_name=names.get(player_id, ""),
                effective_date=eff.value,
                base=feats.prior_avg_round_score_to_par,
                base_n=feats.prior_avg_round_score_to_par_n,
                r1_sg_total=sg_by_round[1],
                r2_sg_total=sg_by_round[2],
                r3_sg_total=sg_by_round[3],
                actual_r4_to_par=target,
            )
        )
    return rows


def _design_matrix(rows: list[SgRowR4], model_id: str) -> np.ndarray:
    if model_id == "BASE":
        return np.array([[1.0, r.base] for r in rows])
    if model_id == "R1SG":
        return np.array([[1.0, r.base, r.r1_sg_total] for r in rows])
    if model_id == "R2SG":
        return np.array([[1.0, r.base, r.r2_sg_total] for r in rows])
    if model_id == "R3SG":
        return np.array([[1.0, r.base, r.r3_sg_total] for r in rows])
    if model_id == "R1SG_R2SG_R3SG":
        return np.array([[1.0, r.base, r.r1_sg_total, r.r2_sg_total, r.r3_sg_total] for r in rows])
    raise ValueError(f"unknown model_id: {model_id}")


MODEL_COEF_LABELS: dict[str, tuple[str, ...]] = {
    "BASE": ("intercept", "base"),
    "R1SG": ("intercept", "base", "r1_sg_total"),
    "R2SG": ("intercept", "base", "r2_sg_total"),
    "R3SG": ("intercept", "base", "r3_sg_total"),
    "R1SG_R2SG_R3SG": ("intercept", "base", "r1_sg_total", "r2_sg_total", "r3_sg_total"),
}


def fit_model(rows: list[SgRowR4], model_id: str) -> np.ndarray:
    x = _design_matrix(rows, model_id)
    y = np.array([r.actual_r4_to_par for r in rows])
    coef, *_ = np.linalg.lstsq(x, y, rcond=None)
    return coef


def predict(coef: np.ndarray, rows: list[SgRowR4], model_id: str) -> np.ndarray:
    x = _design_matrix(rows, model_id)
    return x @ coef


@dataclass
class WalkForwardResultR4:
    n_player_rounds: int
    n_events: int
    n_evaluated_events: int
    min_training_rows: int
    per_model: dict[str, dict]
    event_wins: dict[str, int]
    final_coefficients: dict[str, dict[str, float]]
    event_level_mae: dict[str, list[float]]


def run_walk_forward_r4(rows: list[SgRowR4], *, min_training_rows: int = MIN_TRAINING_ROWS) -> WalkForwardResultR4:
    rows_sorted = sorted(rows, key=lambda r: (r.effective_date, r.game_code, r.player_id))
    events_in_order: list[str] = []
    seen: set[str] = set()
    for r in rows_sorted:
        if r.game_code not in seen:
            seen.add(r.game_code)
            events_in_order.append(r.game_code)

    by_event: dict[str, list[SgRowR4]] = {}
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

        actual = np.array([r.actual_r4_to_par for r in target_rows])
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

    return WalkForwardResultR4(
        n_player_rounds=len(rows),
        n_events=len(events_in_order),
        n_evaluated_events=n_evaluated_events,
        min_training_rows=min_training_rows,
        per_model=per_model,
        event_wins=event_wins,
        final_coefficients=final_coefficients,
        event_level_mae=event_level_mae,
    )
