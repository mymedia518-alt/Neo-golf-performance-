"""Walk-forward validation: does real R1 round-scoped Strokes Gained
improve the prediction of a player's NEXT round (R2) score-to-par,
beyond the existing point-in-time BASE feature
(prior_avg_round_score_to_par)?

Same methodology as klpga.neo_win.current_sg_walk_forward (nested OLS,
walk-forward by strictly-prior events only, klpga.backtest.
point_in_time_features for leakage-safe BASE) -- retargeted from
"R1+R2 SG predicting R3" to "R1 SG alone predicting R2", which is the
actual question for a 2026100003 R1-only forecast (R2 hasn't happened
yet, so there is no R2 SG to add).

DATA SOURCES:
  - klpga_pipeline/data/klpga.sqlite: tournament_master (10 real
    completed KLPGA regular-tour events, built by scripts/241) +
    player_round (real actual R1/R2 round_to_par per player).
  - The 10 matching collector-output/sg-recovery-<gameCode> branches'
    RECORDS.json (real official R1 SG, collected + sha256-verified
    earlier this session) -- single_round scope, round=1.

This module is standalone RESEARCH/VALIDATION. It does not write any
production forecast artifact; scripts/247 reads its printed JSON
result and decides, based on the real event_wins/MAE comparison,
whether R1 SG may be used to adjust the Monte Carlo remaining-round
expectation for 2026100003's own R1 forecast.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.backtest.point_in_time_features import load_corpus, compute_point_in_time_features  # noqa: E402
from klpga.backtest.temporal import is_strictly_before  # noqa: E402
from klpga.ops.paths import db_path  # noqa: E402

SCRATCH_SG_ALL = Path("/tmp/claude-0/-home-user-Neo-golf-performance-/bee7b372-e13f-52b9-816d-77030a003a04/scratchpad/sg_all")
HISTORICAL_CODES = [
    "2026070001", "2026070002", "2026070003", "2026080001", "2026080002",
    "2026080003", "2026080004", "2026090002", "2026090003", "2026100005",
]
MIN_TRAINING_ROWS = 30
MODEL_IDS = ("BASE", "R1SG")


def load_r1_sg_index() -> dict[tuple[str, str], float]:
    """(game_code, player_id) -> real official R1 SG total, from the
    already sha256-verified RECORDS.json for each historical event."""
    idx: dict[tuple[str, str], float] = {}
    for gc in HISTORICAL_CODES:
        path = SCRATCH_SG_ALL / gc / "RECORDS.json"
        recs = json.loads(path.read_text(encoding="utf-8"))
        for r in recs:
            if r.get("scope") == "single_round" and r.get("round") == 1 and r.get("player_id") and r.get("total") is not None:
                idx[(gc, r["player_id"])] = float(r["total"])
    return idx


def load_r2_actuals(conn: sqlite3.Connection) -> tuple[dict[tuple[str, str], float], dict[str, str]]:
    r2: dict[tuple[str, str], float] = {}
    names: dict[str, str] = {}
    cur = conn.execute(
        "SELECT pr.event_id, pr.player_id, pe.player_name, pr.round_to_par "
        "FROM player_round pr JOIN player_event pe ON pr.player_id = pe.player_id AND pr.event_id = pe.event_id "
        "WHERE pr.round_number = 2"
    )
    for game_code, player_id, player_name, round_to_par in cur.fetchall():
        if round_to_par is None:
            continue
        r2[(game_code, player_id)] = float(round_to_par)
        names[player_id] = player_name
    return r2, names


def main() -> None:
    conn = sqlite3.connect(db_path())
    corpus = load_corpus(conn)
    sg_index = load_r1_sg_index()
    r2_actual, names = load_r2_actuals(conn)

    rows = []
    for (gc, pid), r1_sg in sg_index.items():
        target = r2_actual.get((gc, pid))
        if target is None:
            continue
        eff = corpus.tournament_dates.get(gc)
        if eff is None or eff.value is None:
            continue
        feats = compute_point_in_time_features(corpus, gc, eff.value, pid, names.get(pid, ""))
        if feats.prior_avg_round_score_to_par is None:
            continue
        rows.append({
            "game_code": gc, "player_id": pid, "player_name": names.get(pid, ""),
            "effective_date": eff.value, "base": feats.prior_avg_round_score_to_par,
            "r1_sg_total": r1_sg, "actual_r2_to_par": target,
        })

    rows_sorted = sorted(rows, key=lambda r: (r["effective_date"], r["game_code"], r["player_id"]))
    events_in_order: list[str] = []
    seen: set[str] = set()
    for r in rows_sorted:
        if r["game_code"] not in seen:
            seen.add(r["game_code"])
            events_in_order.append(r["game_code"])

    def design(rs, model_id):
        if model_id == "BASE":
            return np.array([[1.0, r["base"]] for r in rs])
        return np.array([[1.0, r["base"], r["r1_sg_total"]] for r in rs])

    def fit(rs, model_id):
        x = design(rs, model_id)
        y = np.array([r["actual_r2_to_par"] for r in rs])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        return coef

    def predict(coef, rs, model_id):
        return design(rs, model_id) @ coef

    errors = {m: [] for m in MODEL_IDS}
    event_wins = {m: 0 for m in MODEL_IDS}
    event_level = {m: [] for m in MODEL_IDS}
    n_evaluated = 0
    skipped_events = []

    for event in events_in_order:
        target_rows = [r for r in rows if r["game_code"] == event]
        target_date = target_rows[0]["effective_date"]
        training_rows = [r for r in rows if r["game_code"] != event and is_strictly_before(r["effective_date"], target_date)]
        if len(training_rows) < MIN_TRAINING_ROWS:
            skipped_events.append({"game_code": event, "training_rows": len(training_rows)})
            continue
        n_evaluated += 1
        actual = np.array([r["actual_r2_to_par"] for r in target_rows])
        event_mae = {}
        for m in MODEL_IDS:
            coef = fit(training_rows, m)
            preds = predict(coef, target_rows, m)
            abs_err = np.abs(preds - actual)
            errors[m].extend(abs_err.tolist())
            event_mae[m] = float(np.mean(abs_err))
        min_mae = min(event_mae.values())
        for m, v in event_mae.items():
            if abs(v - min_mae) < 1e-9:
                event_wins[m] += 1
            event_level[m].append(v)

    per_model = {}
    for m in MODEL_IDS:
        arr = np.array(errors[m]) if errors[m] else np.array([])
        per_model[m] = {
            "n": int(len(arr)),
            "mae": float(np.mean(arr)) if len(arr) else None,
            "rmse": float(np.sqrt(np.mean(arr**2))) if len(arr) else None,
        }

    final_coef = {m: fit(rows, m).tolist() for m in MODEL_IDS} if rows else {}

    result = {
        "n_player_rounds": len(rows),
        "n_events": len(events_in_order),
        "n_evaluated_events": n_evaluated,
        "skipped_events": skipped_events,
        "min_training_rows": MIN_TRAINING_ROWS,
        "per_model": per_model,
        "event_wins": event_wins,
        "event_level_mae": event_level,
        "final_coefficients": {m: list(final_coef[m]) for m in MODEL_IDS} if final_coef else {},
        "r1sg_beats_base": (
            per_model["R1SG"]["mae"] is not None and per_model["BASE"]["mae"] is not None
            and per_model["R1SG"]["mae"] < per_model["BASE"]["mae"]
            and event_wins["R1SG"] > event_wins["BASE"]
        ),
    }
    out_path = ROOT / "content" / "website_v2" / "R1_PREDICTS_R2_WALK_FORWARD_V1.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
