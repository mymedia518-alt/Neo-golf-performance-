"""Walk-forward validation: does real R2 round-scoped Strokes Gained
improve the prediction of a player's FINAL round score-to-par, beyond
the existing point-in-time BASE feature (prior_avg_round_score_to_par)?

Same methodology as scripts/246 (R1SG predicting R2), moved one round
later for the FR forecast: all 10 historical events here are real,
completed 4-round KLPGA events (confirmed via klpga.sqlite
player_round MAX(round_number)=4 for every one), so "final round" is
round 4 for all of them -- this generalizes cleanly even though this
tournament (2026100003) itself is a 3-round event, because the walk-
forward's own target is each HISTORICAL event's own real final round,
never 2026100003's.

DATA SOURCES: klpga_pipeline/data/klpga.sqlite (tournament_master +
player_round) and content/website_v2/sg_official_history/<game_code>/
RECORDS.json (round=2 rows) -- both already repo-committed, no /tmp
dependency, same as scripts/246's fix.

Standalone research/validation only -- writes no production forecast,
scripts/254 reads this printed/written JSON result.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.backtest.point_in_time_features import load_corpus, compute_point_in_time_features  # noqa: E402
from klpga.backtest.temporal import is_strictly_before  # noqa: E402
from klpga.ops.paths import db_path  # noqa: E402

import numpy as np  # noqa: E402

SG_HISTORY_DIR = ROOT / "content" / "website_v2" / "sg_official_history"
HISTORICAL_CODES = [
    "2026070001", "2026070002", "2026070003", "2026080001", "2026080002",
    "2026080003", "2026080004", "2026090002", "2026090003", "2026100005",
]
MIN_TRAINING_ROWS = 30
MODEL_IDS = ("BASE", "R2SG")


def load_r2_sg_index() -> dict[tuple[str, str], float]:
    idx: dict[tuple[str, str], float] = {}
    for gc in HISTORICAL_CODES:
        path = SG_HISTORY_DIR / gc / "RECORDS.json"
        recs = json.loads(path.read_text(encoding="utf-8"))
        for r in recs:
            if r.get("scope") == "single_round" and r.get("round") == 2 and r.get("player_id") and r.get("total") is not None:
                idx[(gc, r["player_id"])] = float(r["total"])
    return idx


def load_final_round_actuals(conn: sqlite3.Connection) -> tuple[dict[tuple[str, str], float], dict[str, str], dict[str, int]]:
    final_round_by_event: dict[str, int] = {}
    for gc, max_round in conn.execute("SELECT event_id, MAX(round_number) FROM player_round GROUP BY event_id"):
        final_round_by_event[gc] = max_round

    final: dict[tuple[str, str], float] = {}
    names: dict[str, str] = {}
    cur = conn.execute(
        "SELECT pr.event_id, pr.player_id, pe.player_name, pr.round_number, pr.round_to_par "
        "FROM player_round pr JOIN player_event pe ON pr.player_id = pe.player_id AND pr.event_id = pe.event_id"
    )
    for game_code, player_id, player_name, round_number, round_to_par in cur.fetchall():
        if round_to_par is None:
            continue
        if round_number != final_round_by_event.get(game_code):
            continue
        final[(game_code, player_id)] = float(round_to_par)
        names[player_id] = player_name
    return final, names, final_round_by_event


def main() -> None:
    conn = sqlite3.connect(db_path())
    corpus = load_corpus(conn)
    sg_index = load_r2_sg_index()
    final_actual, names, final_round_by_event = load_final_round_actuals(conn)

    rows = []
    for (gc, pid), r2_sg in sg_index.items():
        target = final_actual.get((gc, pid))
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
            "r2_sg_total": r2_sg, "actual_final_round_to_par": target,
            "final_round_number": final_round_by_event.get(gc),
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
        return np.array([[1.0, r["base"], r["r2_sg_total"]] for r in rs])

    def fit(rs, model_id):
        x = design(rs, model_id)
        y = np.array([r["actual_final_round_to_par"] for r in rs])
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
        actual = np.array([r["actual_final_round_to_par"] for r in target_rows])
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
        "r2sg_beats_base": (
            per_model["R2SG"]["mae"] is not None and per_model["BASE"]["mae"] is not None
            and per_model["R2SG"]["mae"] < per_model["BASE"]["mae"]
            and event_wins["R2SG"] > event_wins["BASE"]
        ),
    }
    out_path = ROOT / "content" / "website_v2" / "R2_PREDICTS_FINAL_WALK_FORWARD_V1.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
