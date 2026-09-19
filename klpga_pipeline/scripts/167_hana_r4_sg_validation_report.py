"""HANA R3 -> FINAL PIPELINE, STEP 3 groundwork (operator instruction,
2026-09-19): walk-forward validate whether the Current-SG architecture
(BASE + R1SG + R2SG + R3SG) extends validly to predicting R4 from R1+
R2+R3 SG, using the IDENTICAL 5-criterion promotion gate already used
for R1SG_R2SG (never p-value alone):
  1. paired Wilcoxon signed-rank p < 0.05 (BASE vs R1SG_R2SG_R3SG,
     event-level MAE)
  2. 5000-resample bootstrap 95% CI on the paired event-level MAE
     difference excludes zero
  3. r1_sg_total coefficient negative
  4. r2_sg_total coefficient negative
  5. r3_sg_total coefficient negative
  6. chronological split-half stability (same sign both halves)
(one extra criterion vs the R1SG_R2SG gate, since a 3rd SG coefficient
now needs its own direction check.)

Writes content/website_v2/HANA_2026090002_R4_SG_VALIDATION_REPORT_V1.json.
Never reads or writes any Hana/KB forecast artifact -- pure historical
walk-forward research, same as current_sg_walk_forward.py's own report.
"""
from __future__ import annotations

import json
import random
import sqlite3
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.backtest.point_in_time_features import load_corpus  # noqa: E402
from klpga.models.math_utils import wilcoxon_signed_rank_test  # noqa: E402
from klpga.neo_win.current_sg_walk_forward_r4 import (  # noqa: E402
    MODEL_IDS,
    build_eligible_rows_r4,
    run_walk_forward_r4,
)

CONTENT = ROOT / "content" / "website_v2"
DB_PATH = ROOT / "data" / "klpga.sqlite"
OUT_PATH = CONTENT / "HANA_2026090002_R4_SG_VALIDATION_REPORT_V1.json"

SIGNIFICANCE_ALPHA = 0.05
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260918


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


def main() -> None:
    conn = sqlite3.connect(str(DB_PATH))
    corpus = load_corpus(conn)
    warehouse = json.loads((CONTENT / "historical_sg_warehouse.json").read_text(encoding="utf-8"))
    game_codes = {r["game_code"] for r in warehouse["records"]}
    leakage_check = {
        "2026090002_absent_from_historical_warehouse": "2026090002" not in game_codes,
        "2026090003_absent_from_historical_warehouse": "2026090003" not in game_codes,
    }
    assert all(leakage_check.values()), leakage_check

    rows = build_eligible_rows_r4(conn, warehouse, corpus=corpus)
    result = run_walk_forward_r4(rows)

    base_events = result.event_level_mae["BASE"]
    significance = {}
    stability = {}
    for challenger in ("R1SG", "R2SG", "R3SG", "R1SG_R2SG_R3SG"):
        chal_events = result.event_level_mae[challenger]
        diffs = [b - c for b, c in zip(base_events, chal_events)]
        wtest = wilcoxon_signed_rank_test(diffs)
        significance[challenger] = wtest

        n = len(diffs)
        half = n // 2
        first_half, second_half = diffs[:half], diffs[half:]
        first_mean = sum(first_half) / len(first_half) if first_half else 0.0
        second_mean = sum(second_half) / len(second_half) if second_half else 0.0
        ci_lo, ci_hi = _bootstrap_ci(diffs, resamples=BOOTSTRAP_RESAMPLES, seed=BOOTSTRAP_SEED)
        stability[challenger] = {
            "first_half_n": len(first_half), "first_half_mean_diff": first_mean,
            "first_half_p": wilcoxon_signed_rank_test(first_half)["p_value"] if first_half else None,
            "second_half_n": len(second_half), "second_half_mean_diff": second_mean,
            "second_half_p": wilcoxon_signed_rank_test(second_half)["p_value"] if second_half else None,
            "split_half_same_sign": (first_mean > 0 and second_mean > 0),
            "bootstrap_ci_95": {"lo": ci_lo, "hi": ci_hi},
            "bootstrap_ci_excludes_zero": ci_lo > 0,
        }

    coef = result.final_coefficients["R1SG_R2SG_R3SG"]
    gate_criteria = {
        "p_lt_0.05": significance["R1SG_R2SG_R3SG"]["p_value"] < SIGNIFICANCE_ALPHA,
        "bootstrap_ci_excludes_zero": stability["R1SG_R2SG_R3SG"]["bootstrap_ci_excludes_zero"],
        "coef_r1sg_negative": coef["r1_sg_total"] < 0,
        "coef_r2sg_negative": coef["r2_sg_total"] < 0,
        "coef_r3sg_negative": coef["r3_sg_total"] < 0,
        "split_half_same_sign": stability["R1SG_R2SG_R3SG"]["split_half_same_sign"],
    }
    gate_pass = all(gate_criteria.values())

    report = {
        "schema_version": 1,
        "artifact": "HANA_2026090002_R4_SG_VALIDATION_REPORT_V1",
        "purpose": (
            "Walk-forward validation of whether the SAME Current-SG model "
            "architecture already validated/promoted for R1SG_R2SG (R1+R2 SG "
            "predicting R3) extends to R1SG_R2SG_R3SG (R1+R2+R3 SG predicting "
            "R4/FINAL). NOT a new model kind -- same OLS/walk-forward/gate "
            "methodology, one more round."
        ),
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
        "model_promotion": "PASS" if gate_pass else "FAIL",
    }
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT_PATH)
    print("n_player_rounds:", result.n_player_rounds, "n_events:", result.n_events, "n_evaluated_events:", result.n_evaluated_events)
    print("MODEL_PROMOTION (R1SG_R2SG_R3SG) =", report["model_promotion"])
    for k, v in gate_criteria.items():
        print(f"  {k}: {v}")
    print()
    print("per_model MAE/RMSE:")
    for m in MODEL_IDS:
        print(" ", m, result.per_model[m])
    print()
    print("final_coefficients (R1SG_R2SG_R3SG):", result.final_coefficients["R1SG_R2SG_R3SG"])


if __name__ == "__main__":
    main()
