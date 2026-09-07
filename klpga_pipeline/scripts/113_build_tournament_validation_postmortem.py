"""Build TOURNAMENT_VALIDATION_POSTMORTEM.json -- NEO SITE V5 Mission 4.

Evaluates the frozen OK Open 2026 PRE win-probability forecast
(OK_OPEN_2026_PRE_WIN_FORECAST.json, generated only from information
available before the tournament -- future_data_excluded: true) against
the real, official FINAL result
(content/website_v2/r1_final_snapshots/OK_OPEN_2026120001_FINAL_
20260905T141909.json). This IS legitimately a post-tournament
evaluation of an already-frozen prediction -- the mission brief
distinguishes "tune the model using the tournament immediately after
completion" (never do this) from "freeze the postmortem first, then
evaluate an improved model separately against the frozen original
prediction" (this script's whole purpose). This script computes
metrics only; it never rewrites OK_OPEN_2026_PRE_WIN_FORECAST.json and
never feeds this postmortem's numbers back into any model-fitting code.

outcome := "finished at rank_display T1/1 in the real FINAL result"
(win). Every other computed metric (calibration, MAE, Spearman between
predicted win_probability order and actual final rank order) is
evaluated only over the two frozen artifacts above -- nothing here
reads or waits on R2/R3 stage-specific artifacts, since OK Open is a
54-hole/3-round event whose FINAL result IS its R3 result (see the
site-inventory finding: OK Open's own final/index.html is a redirect
to r3/, not a separate stage).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from klpga.validation import ranking_stats as rs  # noqa: E402

CONTENT = ROOT / "content" / "website_v2"
FORECAST_PATH = CONTENT / "OK_OPEN_2026_PRE_WIN_FORECAST.json"
FINAL_PATH = CONTENT / "r1_final_snapshots" / "OK_OPEN_2026120001_FINAL_20260905T141909.json"
OUT_PATH = CONTENT / "TOURNAMENT_VALIDATION_POSTMORTEM.json"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build() -> dict:
    forecast_doc = json.loads(FORECAST_PATH.read_text(encoding="utf-8"))
    final_doc = json.loads(FINAL_PATH.read_text(encoding="utf-8"))

    predictions = {
        str(r["player_id"]): r["win_probability"]
        for r in forecast_doc["records"]
        if r.get("win_probability") is not None
    }
    final_score = {
        str(r["player_id"]): r["final_score"]
        for r in final_doc["rows"]
        if r.get("final_score") is not None
    }
    # win outcome: any player sharing the lowest final_score (ties count
    # as a real co-win, e.g. the real T1 tie in this tournament).
    if final_score:
        best = min(final_score.values())
        outcomes = {pid: (score == best) for pid, score in final_score.items()}
    else:
        outcomes = {}

    calibration = rs.calibration_bins(predictions, outcomes)
    error = rs.mean_absolute_prediction_error(predictions, {pid: (1.0 if won else 0.0) for pid, won in outcomes.items()})
    # Ranking discrimination: did higher-predicted-win_probability
    # players actually finish with lower (better) final_score?
    discrimination = rs.spearman_rank_correlation(
        predictions, {pid: score for pid, score in final_score.items()},
    )

    doc = {
        "schema_version": "neo_tournament_validation_postmortem_v1",
        "game_code": forecast_doc.get("game_code"),
        "pre_prediction": {
            "artifact": "OK_OPEN_2026_PRE_WIN_FORECAST.json",
            "model_version": forecast_doc.get("model_version"),
            "cutoff": forecast_doc.get("cutoff"),
            "future_data_excluded": forecast_doc.get("future_data_excluded"),
        },
        "final_actual": {
            "artifact": "r1_final_snapshots/OK_OPEN_2026120001_FINAL_20260905T141909.json",
            "collected_at": final_doc.get("collected_at"),
            "reconciliation": final_doc.get("reconciliation"),
        },
        "r1_actual": None,
        "r2_actual": None,
        "r3_actual": None,
        "evaluation": {
            "sample_size": len(set(predictions) & set(final_score)),
            "calibration_bins": [
                {"lower": b.lower, "upper": b.upper, "predicted_count": b.predicted_count,
                 "actual_positive_count": b.actual_positive_count, "actual_rate": b.actual_rate}
                for b in calibration
            ],
            "mean_absolute_error_vs_win_outcome": error,
            "win_probability_vs_final_score_discrimination": discrimination,
            "win_probability_vs_final_score_discrimination_note": (
                "raw ascending-value-rank correlation over two oppositely"
                "-oriented metrics (win_probability: higher=better; "
                "final_score: lower/more-negative=better under par) -- a "
                "well-discriminating model therefore shows NEGATIVE rho "
                "here (higher predicted win probability correlating with "
                "lower/better actual final score), not positive."
            ),
        },
        "model_tuned_using_this_result": False,
        "generated_at": now(),
    }
    OUT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"sample_size": doc["evaluation"]["sample_size"],
                      "mae": error["mae"], "rho": discrimination["rho"]}, ensure_ascii=False))
    return doc


if __name__ == "__main__":
    build()
