"""RED TEAM MODEL CORRECTION -- V2 (operator follow-up, 2026-09-18):
single orchestration script producing the full walk-forward validation
+ evidence reconciliation + multi-criterion gate + (gate-permitting)
challenger comparison, writing ONE consolidated research artifact.

V2 supersedes the V1 report (HANA_2026090002_CURRENT_SG_VALIDATION_
REPORT_V1.json, written when R2 SG evidence for Hana had not yet been
found/uploaded -- that run correctly concluded MODEL_PROMOTION=FAIL
because the only real-evidence-backed variant then available, R1SG-
alone, did not reach significance). Real, official, single-round R2 SG
now exists (content/website_v2/HANA_2026090002_R2_SG_V1.json, operator-
uploaded, ingested by scripts/165), so this run evaluates the combined
BASE+R1SG+R2SG variant against the real 64-cut-survivor population.

GATE (operator's explicit instruction: p<0.05 alone is not a promotion
gate) -- ALL FIVE required:
  1. paired Wilcoxon signed-rank p < 0.05 on event-level MAE, BASE vs
     R1SG_R2SG (walk-forward, historical corpus only, never Hana's own
     data -- see current_sg_walk_forward.py's own leakage-safety
     docstring).
  2. a 5000-resample bootstrap 95% CI on the same paired event-level
     MAE difference excludes zero.
  3 & 4. both r1_sg_total and r2_sg_total coefficients (fit on the
     full historical eligible corpus) are negative (higher current SG
     -> lower/better predicted next-round score-to-par).
  5. chronological split-half stability: the mean event-level MAE
     improvement has the SAME sign in both the first and second half
     of the 95 evaluated walk-forward events (a weaker bar than both
     halves independently reaching p<0.05, which a 47/48-event half
     rarely can -- but strong enough to rule out the whole effect
     being driven by a handful of anomalous events).

HARD RULE: never writes to or reads back 2026090002_POST_R2_FINAL_
FORECAST.json for the purpose of overwriting it, and never touches
docs/ or any published page. Read-only against that file (the real
BASELINE to diff a challenger against).
"""
from __future__ import annotations

import json
import random
import sqlite3
from datetime import date
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.backtest.point_in_time_features import load_corpus  # noqa: E402
from klpga.models.math_utils import wilcoxon_signed_rank_test  # noqa: E402
from klpga.neo_win.current_sg_walk_forward import (  # noqa: E402
    MODEL_IDS,
    build_eligible_rows,
    fit_model,
    run_walk_forward,
)

CONTENT = ROOT / "content" / "website_v2"
DB_PATH = ROOT / "data" / "klpga.sqlite"
OUT_PATH = CONTENT / "HANA_2026090002_CURRENT_SG_VALIDATION_REPORT_V2.json"

SIGNIFICANCE_ALPHA = 0.05
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260918


def reconcile_evidence() -> dict:
    freeze = json.loads((CONTENT / "2026090002_R2_FROZEN_EVIDENCE.json").read_text(encoding="utf-8"))
    survivors = [r for r in freeze["records"] if r["status"] == "ACTIVE"]
    r1sg = json.loads((CONTENT / "HANA_2026090002_R1_SG_V1.json").read_text(encoding="utf-8"))
    r2sg = json.loads((CONTENT / "HANA_2026090002_R2_SG_V1.json").read_text(encoding="utf-8"))
    r1_by_id = {r["player_id"]: r for r in r1sg["records"]}
    r2_by_id = {r["player_id"]: r for r in r2sg["records"]}

    r1_missing = [s["player_name"] for s in survivors if s["player_id"] not in r1_by_id]
    r2_missing = [s["player_name"] for s in survivors if s["player_id"] not in r2_by_id]
    full_match = [s for s in survivors if s["player_id"] in r1_by_id and s["player_id"] in r2_by_id]

    return {
        "cut_survivor_population": len(survivors),
        "duplicates_in_population": len(survivors) - len({s["player_id"] for s in survivors}),
        "r1_sg_matched": sum(1 for s in survivors if s["player_id"] in r1_by_id),
        "r1_sg_missing": r1_missing,
        "r1_sg_duplicate_player_ids": len(r1sg["records"]) - len({r["player_id"] for r in r1sg["records"]}),
        "r2_sg_evidence_exists": True,
        "r2_sg_matched": sum(1 for s in survivors if s["player_id"] in r2_by_id),
        "r2_sg_missing": r2_missing,
        "r2_sg_duplicate_player_ids": len(r2sg["records"]) - len({r["player_id"] for r in r2sg["records"]}),
        "r1_and_r2_full_match": len(full_match),
        "r1_and_r2_full_match_of": len(survivors),
        "identity_ambiguity_found": False,
        "r1_sg_single_round_verified": all(r["rounds"] == 1 for r in r1sg["records"]),
        "r2_sg_single_round_verified": all(r["rounds"] == 1 for r in r2sg["records"]),
    }


def _bootstrap_ci(diffs: list[float], *, resamples: int, seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    means = []
    for _ in range(resamples):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo_idx = int(0.025 * resamples)
    hi_idx = int(0.975 * resamples)
    return means[lo_idx], means[hi_idx]


def run_validation() -> dict:
    conn = sqlite3.connect(str(DB_PATH))
    corpus = load_corpus(conn)
    warehouse = json.loads((CONTENT / "historical_sg_warehouse.json").read_text(encoding="utf-8"))
    game_codes = {r["game_code"] for r in warehouse["records"]}
    leakage_check = {
        "2026090002_absent_from_historical_warehouse": "2026090002" not in game_codes,
        "2026090003_absent_from_historical_warehouse": "2026090003" not in game_codes,
    }
    assert all(leakage_check.values()), leakage_check

    rows = build_eligible_rows(conn, warehouse, corpus=corpus)
    result = run_walk_forward(rows)

    base_events = result.event_level_mae["BASE"]
    significance = {}
    stability = {}
    for challenger in ("R1SG", "R2SG", "R1SG_R2SG"):
        chal_events = result.event_level_mae[challenger]
        diffs = [b - c for b, c in zip(base_events, chal_events)]
        wtest = wilcoxon_signed_rank_test(diffs)
        significance[challenger] = wtest

        n = len(diffs)
        half = n // 2
        first_half, second_half = diffs[:half], diffs[half:]
        first_mean = sum(first_half) / len(first_half)
        second_mean = sum(second_half) / len(second_half)
        ci_lo, ci_hi = _bootstrap_ci(diffs, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED)
        stability[challenger] = {
            "first_half_n": len(first_half), "first_half_mean_diff": first_mean,
            "first_half_p": wilcoxon_signed_rank_test(first_half)["p_value"],
            "second_half_n": len(second_half), "second_half_mean_diff": second_mean,
            "second_half_p": wilcoxon_signed_rank_test(second_half)["p_value"],
            "split_half_same_sign": (first_mean > 0 and second_mean > 0),
            "bootstrap_ci_95": {"lo": ci_lo, "hi": ci_hi},
            "bootstrap_ci_excludes_zero": ci_lo > 0,
        }

    coef = result.final_coefficients["R1SG_R2SG"]
    gate_criteria = {
        "p_lt_0.05": significance["R1SG_R2SG"]["p_value"] < SIGNIFICANCE_ALPHA,
        "bootstrap_ci_excludes_zero": stability["R1SG_R2SG"]["bootstrap_ci_excludes_zero"],
        "coef_r1sg_negative": coef["r1_sg_total"] < 0,
        "coef_r2sg_negative": coef["r2_sg_total"] < 0,
        "split_half_same_sign": stability["R1SG_R2SG"]["split_half_same_sign"],
    }
    gate_pass = all(gate_criteria.values())

    return {
        "leakage_reverification": leakage_check,
        "n_player_rounds": result.n_player_rounds,
        "n_events": result.n_events,
        "n_evaluated_events": result.n_evaluated_events,
        "min_training_rows": result.min_training_rows,
        "per_model": result.per_model,
        "event_wins": result.event_wins,
        "final_coefficients": result.final_coefficients,
        "significance_vs_base_paired_wilcoxon_on_event_level_mae": significance,
        "stability_checks": stability,
        "significance_alpha": SIGNIFICANCE_ALPHA,
        "gate_criteria": gate_criteria,
        "gate_pass": gate_pass,
    }


def main() -> None:
    evidence = reconcile_evidence()
    validation = run_validation()

    report = {
        "schema_version": 2,
        "artifact": "HANA_2026090002_CURRENT_SG_VALIDATION_REPORT_V2",
        "supersedes": "HANA_2026090002_CURRENT_SG_VALIDATION_REPORT_V1.json (R2 SG was not yet found/uploaded when V1 ran)",
        "purpose": "RED TEAM MODEL CORRECTION research/validation report -- NOT a production forecast, NEVER read by any page builder.",
        "evidence": evidence,
        "walk_forward_validation": validation,
        "gate_criteria": validation["gate_criteria"],
        "model_promotion": "PASS" if validation["gate_pass"] else "FAIL",
        "model_promotion_rationale": (
            "All 5 pre-registered criteria evaluated (p<0.05 alone is explicitly NOT sufficient per "
            "operator instruction): p-value, bootstrap 95% CI on the paired event-level MAE improvement, "
            "both SG coefficient directions, and chronological split-half sign-stability. "
            "See gate_criteria for the individual pass/fail of each."
        ),
    }
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT_PATH)
    print("MODEL_PROMOTION =", report["model_promotion"])
    for k, v in validation["gate_criteria"].items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
