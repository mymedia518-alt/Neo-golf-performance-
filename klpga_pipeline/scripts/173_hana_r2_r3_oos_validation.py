"""HANA R3 -> FINAL PIPELINE, STEP 7 (operator instruction, 2026-09-19):
R2 -> R3 out-of-sample validation. Uses the IMMUTABLE
2026090002_POST_R3_CANDIDATE_FREEZE_V1.json exactly as written -- never
recomputed, never overwritten. Compares its two per-player expected-
score fields (historical_expected = PRE-time baseline before any
current-SG adjustment; updated_expected_round_score_to_par = the
promoted R1SG_R2SG model's actual prediction) against the real,
official R3 score (2026090002_R3_FROZEN_EVIDENCE.json, built this
session from operator-supplied official evidence).

Reports MAE, RMSE, Bias, per-player error, and classifies each player
as IMPROVEMENT (current-SG prediction closer to actual than the
historical-only baseline) or REGRESSION (further away) or TIE.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

CANDIDATE_PATH = CONTENT / "2026090002_POST_R3_CANDIDATE_FREEZE_V1.json"
R3_FREEZE_PATH = CONTENT / "2026090002_R3_FROZEN_EVIDENCE.json"
OUT_PATH = CONTENT / "HANA_2026090002_R2_R3_OOS_VALIDATION_REPORT_V1.json"


def main() -> None:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    r3_freeze = json.loads(R3_FREEZE_PATH.read_text(encoding="utf-8"))
    cand_by_id = {r["player_id"]: r for r in candidate["records"]}
    r3_by_id = {r["player_id"]: r for r in r3_freeze["records"] if r["status"] == "ACTIVE"}
    assert set(cand_by_id) == set(r3_by_id) and len(cand_by_id) == 64

    per_player = []
    for pid in sorted(cand_by_id, key=int):
        c = cand_by_id[pid]
        actual = r3_by_id[pid]["r3_score_to_par"]
        hist = c["historical_expected"]
        upd = c["updated_expected_round_score_to_par"]
        err_hist = hist - actual
        err_upd = upd - actual
        abs_err_hist = abs(err_hist)
        abs_err_upd = abs(err_upd)
        if abs_err_upd < abs_err_hist - 1e-9:
            classification = "IMPROVEMENT"
        elif abs_err_upd > abs_err_hist + 1e-9:
            classification = "REGRESSION"
        else:
            classification = "TIE"
        per_player.append({
            "player_id": pid, "player_name": c["player_name"],
            "actual_r3_score_to_par": actual,
            "historical_expected": hist, "updated_expected_round_score_to_par": upd,
            "current_sg_update": c["current_sg_update"],
            "bias_historical": err_hist, "bias_updated": err_upd,
            "abs_error_historical": abs_err_hist, "abs_error_updated": abs_err_upd,
            "classification": classification,
        })

    n = len(per_player)
    mae_hist = sum(p["abs_error_historical"] for p in per_player) / n
    mae_upd = sum(p["abs_error_updated"] for p in per_player) / n
    rmse_hist = (sum(p["bias_historical"] ** 2 for p in per_player) / n) ** 0.5
    rmse_upd = (sum(p["bias_updated"] ** 2 for p in per_player) / n) ** 0.5
    bias_hist = sum(p["bias_historical"] for p in per_player) / n
    bias_upd = sum(p["bias_updated"] for p in per_player) / n

    n_improvement = sum(1 for p in per_player if p["classification"] == "IMPROVEMENT")
    n_regression = sum(1 for p in per_player if p["classification"] == "REGRESSION")
    n_tie = sum(1 for p in per_player if p["classification"] == "TIE")

    summary = {
        "n_players": n,
        "mae_historical_expected": mae_hist,
        "mae_updated_expected": mae_upd,
        "mae_improvement": mae_hist - mae_upd,
        "rmse_historical_expected": rmse_hist,
        "rmse_updated_expected": rmse_upd,
        "rmse_improvement": rmse_hist - rmse_upd,
        "bias_historical_expected": bias_hist,
        "bias_updated_expected": bias_upd,
        "n_improvement": n_improvement,
        "n_regression": n_regression,
        "n_tie": n_tie,
    }

    report = {
        "schema_version": 1,
        "artifact": "HANA_2026090002_R2_R3_OOS_VALIDATION_REPORT_V1",
        "purpose": "Out-of-sample validation of the promoted R1SG_R2SG model's R3 prediction against the real, official R3 result -- reads the immutable candidate freeze and R3 freeze only, never recomputes either.",
        "source_candidate_freeze": "2026090002_POST_R3_CANDIDATE_FREEZE_V1.json (read-only, untouched)",
        "source_r3_freeze": "2026090002_R3_FROZEN_EVIDENCE.json (read-only, untouched)",
        "summary": summary,
        "per_player": per_player,
    }
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT_PATH)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
