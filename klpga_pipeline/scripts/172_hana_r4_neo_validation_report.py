"""HANA R3 -> FINAL PIPELINE, STEP 6 (operator instruction, 2026-09-19):
NEO validation report -- 12 required analyses, all computed from real,
already-existing/already-computed artifacts (candidate freeze, FINAL
preview, BASELINE-no-current-SG variant, R3 freeze, R1 5-prob frozen
model, R2 freeze). Nothing here is a new model or a retrain.

Items 7-9 (probability calibration / Brier / log loss) use the ONE
real probability-vs-known-outcome pair that has actually resolved in
this tournament: NEO_R1_MODEL_V1's cut probability (HANA_2026090002_
R1_5PROB_FROZEN_V1.json, N=105) vs the real, already-known made-cut
fact (2026090002_R2_FROZEN_EVIDENCE.json). The FINAL/win-top-N
probabilities cannot be calibrated yet -- the tournament has not
finished (R4 has not been played) -- so this report does not fabricate
that comparison; it explicitly scopes items 7-9 to the cut-probability
prediction, which is the only genuinely resolved probabilistic forecast
available.

Items 5-6 (most/worst accurate prediction) use the real, already-known
R2->R3 continuous-score comparison (candidate freeze's updated_expected_
round_score_to_par vs the real R3 score) -- the same real, resolved
data Step 7's own OOS report evaluates in full.

Writes content/website_v2/HANA_2026090002_R4_NEO_VALIDATION_REPORT_V1.json.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.round_update_r3 import PlayerR3SimInput, simulate_post_round3  # noqa: E402

FINAL_PATH = CONTENT / "2026090002_POST_R4_FINAL_PREVIEW.json"
BASELINE_PATH = CONTENT / "HANA_2026090002_R4_BASELINE_NO_CURRENT_SG_V1.json"
CANDIDATE_PATH = CONTENT / "2026090002_POST_R3_CANDIDATE_FREEZE_V1.json"
R3_FREEZE_PATH = CONTENT / "2026090002_R3_FROZEN_EVIDENCE.json"
R1_5PROB_PATH = CONTENT / "2026090002_R1_5PROB_FROZEN_V1.json"
R2_FREEZE_PATH = CONTENT / "2026090002_R2_FROZEN_EVIDENCE.json"
OUT_PATH = CONTENT / "HANA_2026090002_R4_NEO_VALIDATION_REPORT_V1.json"

R1_SG_COEF = -0.095010
R2_SG_COEF = -0.112655
SEED = 20260918
N_SIM = 60000


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def main() -> None:
    final = load(FINAL_PATH)
    baseline = load(BASELINE_PATH)
    candidate = load(CANDIDATE_PATH)
    r3_freeze = load(R3_FREEZE_PATH)

    final_by_id = {r["player_id"]: r for r in final["records"]}
    base_by_id = {r["player_id"]: r for r in baseline["records"]}
    cand_by_id = {r["player_id"]: r for r in candidate["records"]}
    r3_by_id = {r["player_id"]: r for r in r3_freeze["records"] if r["status"] == "ACTIVE"}
    assert set(final_by_id) == set(base_by_id) == set(cand_by_id) == set(r3_by_id)
    ids = sorted(final_by_id, key=int)

    # ---- 1. Baseline vs Current SG comparison ----
    comparison = []
    for pid in ids:
        f, b = final_by_id[pid], base_by_id[pid]
        comparison.append({
            "player_id": pid, "player_name": f["player_name"],
            "baseline_win_pct": b["win_pct"], "current_sg_win_pct": f["win_pct"], "delta_win_pct": f["win_pct"] - b["win_pct"],
            "baseline_top5_pct": b["top5_pct"], "current_sg_top5_pct": f["top5_pct"], "delta_top5_pct": f["top5_pct"] - b["top5_pct"],
            "baseline_top10_pct": b["top10_pct"], "current_sg_top10_pct": f["top10_pct"], "delta_top10_pct": f["top10_pct"] - b["top10_pct"],
            "baseline_top20_pct": b["top20_pct"], "current_sg_top20_pct": f["top20_pct"], "delta_top20_pct": f["top20_pct"] - b["top20_pct"],
        })

    # ---- 2. Current SG impact (field-wide summary) ----
    deltas = [c["delta_win_pct"] for c in comparison]
    impact_summary = {
        "n_players": len(deltas),
        "mean_abs_delta_win_pct": sum(abs(d) for d in deltas) / len(deltas),
        "max_delta_win_pct": max(deltas), "max_delta_player": max(comparison, key=lambda c: c["delta_win_pct"])["player_name"],
        "min_delta_win_pct": min(deltas), "min_delta_player": min(comparison, key=lambda c: c["delta_win_pct"])["player_name"],
        "sum_abs_delta_win_pct": sum(abs(d) for d in deltas),
        "n_players_win_pct_increased": sum(1 for d in deltas if d > 1e-9),
        "n_players_win_pct_decreased": sum(1 for d in deltas if d < -1e-9),
        "n_players_win_pct_unchanged": sum(1 for d in deltas if abs(d) <= 1e-9),
    }

    # ---- 3 & 4. TOP10 largest increase / decrease ----
    top10_increase = sorted(comparison, key=lambda c: -c["delta_win_pct"])[:10]
    top10_decrease = sorted(comparison, key=lambda c: c["delta_win_pct"])[:10]

    # ---- 5 & 6. Most / worst accurate prediction (R2->R3 real OOS) ----
    oos = []
    for pid in ids:
        c, r3r = cand_by_id[pid], r3_by_id[pid]
        actual = r3r["r3_score_to_par"]
        pred_updated = c["updated_expected_round_score_to_par"]
        pred_hist = c["historical_expected"]
        oos.append({
            "player_id": pid, "player_name": c["player_name"],
            "actual_r3_score_to_par": actual,
            "historical_expected": pred_hist, "updated_expected_round_score_to_par": pred_updated,
            "error_historical": abs(pred_hist - actual), "error_updated": abs(pred_updated - actual),
        })
    most_accurate = min(oos, key=lambda o: o["error_updated"])
    worst_prediction = max(oos, key=lambda o: o["error_updated"])

    # ---- 7, 8, 9: Probability calibration / Brier / Log Loss (R1 cut-probability vs real made-cut outcome) ----
    r1_5prob = load(R1_5PROB_PATH)
    r2_freeze = load(R2_FREEZE_PATH)
    made_cut_by_id = {r["player_id"]: (r["status"] == "ACTIVE") for r in r2_freeze["records"] if r["status"] != "WD"}
    preds = []
    for p in r1_5prob["predictions"]:
        pid = p["player_id"]
        if pid not in made_cut_by_id:
            continue
        preds.append({"player_id": pid, "predicted_cut_prob": p["cut"], "actual_made_cut": made_cut_by_id[pid]})

    n_cal = len(preds)
    buckets = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0001)]
    calibration = []
    for lo, hi in buckets:
        in_bucket = [p for p in preds if lo <= p["predicted_cut_prob"] < hi]
        if not in_bucket:
            calibration.append({"bucket": f"[{lo:.1f},{hi:.1f})", "n": 0, "mean_predicted": None, "actual_rate": None})
            continue
        mean_pred = sum(p["predicted_cut_prob"] for p in in_bucket) / len(in_bucket)
        actual_rate = sum(1 for p in in_bucket if p["actual_made_cut"]) / len(in_bucket)
        calibration.append({"bucket": f"[{lo:.1f},{hi:.1f})", "n": len(in_bucket), "mean_predicted": mean_pred, "actual_rate": actual_rate})

    brier_score = sum((p["predicted_cut_prob"] - (1.0 if p["actual_made_cut"] else 0.0)) ** 2 for p in preds) / n_cal

    eps = 1e-15
    log_loss = -sum(
        (1.0 if p["actual_made_cut"] else 0.0) * math.log(max(p["predicted_cut_prob"], eps))
        + (0.0 if p["actual_made_cut"] else 1.0) * math.log(max(1.0 - p["predicted_cut_prob"], eps))
        for p in preds
    ) / n_cal

    # ---- 10. Monte Carlo sanity report (determinism / seed reproducibility) ----
    sim_inputs = []
    for pid in ids:
        c, r3r = cand_by_id[pid], r3_by_id[pid]
        sim_inputs.append(PlayerR3SimInput(
            player_code=pid, player_name=c["player_name"],
            expected_round_score_to_par=c["updated_expected_round_score_to_par"], spread=c["spread"],
            r1_score_to_par=c["r1_score_to_par"], r2_score_to_par=c["r2_score_to_par"],
            r3_score_to_par=r3r["r3_score_to_par"], made_cut=True,
        ))
    rerun1 = simulate_post_round3(sim_inputs, n_simulations=N_SIM, rng=random.Random(SEED))
    rerun2 = simulate_post_round3(sim_inputs, n_simulations=N_SIM, rng=random.Random(SEED))
    bit_identical = rerun1 == rerun2
    matches_final_preview = all(
        abs(rerun1[pid]["win_pct"] - final_by_id[pid]["win_pct"]) < 1e-9 for pid in ids
    )
    mc_sanity = {
        "n_simulations": N_SIM, "seed": SEED,
        "reproducible_same_seed_bit_identical": bit_identical,
        "matches_published_final_preview": matches_final_preview,
        "win_pct_sum_final": sum(v["win_pct"] for v in final_by_id.values()),
        "win_pct_sum_baseline": sum(v["win_pct"] for v in base_by_id.values()),
    }

    # ---- 11. Probability concentration report ----
    def top_n_combined(records_by_id: dict, n: int) -> float:
        top = sorted(records_by_id.values(), key=lambda r: -r["win_pct"])[:n]
        return sum(r["win_pct"] for r in top)

    concentration = {
        "post_r2_candidate_stage": {
            "top1": top_n_combined(cand_by_id, 1), "top3": top_n_combined(cand_by_id, 3), "top5": top_n_combined(cand_by_id, 5),
        },
        "post_r3_final_stage": {
            "top1": top_n_combined(final_by_id, 1), "top3": top_n_combined(final_by_id, 3), "top5": top_n_combined(final_by_id, 5),
        },
    }
    concentration["change"] = {
        k: concentration["post_r3_final_stage"][k] - concentration["post_r2_candidate_stage"][k]
        for k in ("top1", "top3", "top5")
    }

    # ---- 12. Current SG decomposition ----
    decomposition = []
    max_recon_error = 0.0
    for pid in ids:
        c = cand_by_id[pid]
        r1_part = R1_SG_COEF * c["r1_sg_total"]
        r2_part = R2_SG_COEF * c["r2_sg_total"]
        reconstructed = r1_part + r2_part
        recon_error = abs(reconstructed - c["current_sg_update"])
        max_recon_error = max(max_recon_error, recon_error)
        decomposition.append({
            "player_id": pid, "player_name": c["player_name"],
            "r1_sg_total": c["r1_sg_total"], "r2_sg_total": c["r2_sg_total"],
            "r1_contribution": r1_part, "r2_contribution": r2_part,
            "current_sg_update": c["current_sg_update"], "reconstructed_sum": reconstructed, "reconstruction_error": recon_error,
        })

    report = {
        "schema_version": 1,
        "artifact": "HANA_2026090002_R4_NEO_VALIDATION_REPORT_V1",
        "purpose": "12-item NEO validation report for the R3->FINAL pipeline, per operator instruction 2026-09-19",
        "model_used": "R1SG_R2SG (already validated/promoted) -- no retraining, no new model",
        "1_baseline_vs_current_sg_comparison": comparison,
        "2_current_sg_impact": impact_summary,
        "3_top10_largest_probability_increase": top10_increase,
        "4_top10_largest_probability_decrease": top10_decrease,
        "5_most_accurate_prediction": most_accurate,
        "6_worst_prediction": worst_prediction,
        "7_probability_calibration": {
            "scope_note": "R1 cut-probability (NEO_R1_MODEL_V1) vs real, already-known made-cut outcome -- the ONE probabilistic forecast that has actually resolved this tournament; FINAL win/top-N probabilities cannot be calibrated until R4 completes.",
            "n": n_cal, "buckets": calibration,
        },
        "8_brier_score": {"scope_note": "same R1 cut-probability dataset as item 7", "n": n_cal, "value": brier_score},
        "9_log_loss": {"scope_note": "same R1 cut-probability dataset as item 7", "n": n_cal, "value": log_loss},
        "10_monte_carlo_sanity_report": mc_sanity,
        "11_probability_concentration_report": concentration,
        "12_current_sg_decomposition": {"max_reconstruction_error": max_recon_error, "records": decomposition},
    }
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT_PATH)
    print("2_current_sg_impact:", json.dumps(impact_summary, ensure_ascii=False))
    print("5_most_accurate_prediction:", most_accurate["player_name"], most_accurate["error_updated"])
    print("6_worst_prediction:", worst_prediction["player_name"], worst_prediction["error_updated"])
    print("8_brier_score:", brier_score)
    print("9_log_loss:", log_loss)
    print("10_mc_sanity:", mc_sanity)
    print("11_concentration:", json.dumps(concentration, ensure_ascii=False))
    print("12_max_reconstruction_error:", max_recon_error)


if __name__ == "__main__":
    main()
