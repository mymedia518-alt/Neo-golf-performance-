"""HANA POST-R3 CANDIDATE FREEZE (operator promotion instruction,
2026-09-18): promotes the walk-forward-validated BASE+R1SG+R2SG model
(research/hana-current-sg-model-validation-20260918, commit 2975036)
to a NEW production CANDIDATE forecast artifact.

HARD RULE: this script NEVER reads back nor overwrites
2026090002_POST_R2_FINAL_FORECAST.json. It only READS that file (the
real, already-published BASELINE) to source historical_expected/
spread/actual scores. It writes ONLY a new, separate file:
2026090002_POST_R3_CANDIDATE_FREEZE_V1.json. Promoting that candidate
onto the live R2 page (script 160) is a SEPARATE, later, explicitly-
gated step -- this script produces the candidate only.

MODEL: R1SG_R2SG only (no R1-only or R2-only variant is used here).
Coefficients are RECOMPUTED live from the same historical corpus
(historical_sg_warehouse.json, via klpga.neo_win.current_sg_walk_
forward.fit_model) rather than hardcoded, so this script is itself the
audit trail for the coefficient values -- but the run is fully
deterministic (same data, same OLS), so it reproduces the validated
research values exactly: r1_sg_total=-0.095010, r2_sg_total=-0.112655.
No T2G/OTT/APP/ARG/PUTT component is ever separately weighted, and no
tuning constant is applied beyond these two fitted coefficients.

INPUTS (all real, none fabricated):
  - 2026090002_R2_FROZEN_EVIDENCE.json: the official 64 cut survivors
    and their actual R1/R2 scores.
  - 2026090002_POST_R2_FINAL_FORECAST.json (read-only): each
    survivor's PRE-frozen historical_expected/source and spread/
    source -- untouched, never recomputed here.
  - HANA_2026090002_R1_SG_V1.json / HANA_2026090002_R2_SG_V1.json: the
    official, single-round (never cumulative) current-tournament SG.

HARD_STOP GATE (raises SystemExit, writes nothing, if violated):
  - exactly 64 cut survivors, 0 duplicate player_ids
  - R1 SG matched for all 64 (0 missing)
  - R2 SG matched for all 64 (0 missing)
  - 0 identity ambiguity (duplicate names on either side)
A player missing from historical warehouse coverage (no prior KLPGA
event history) never gets an imputed SG or expected value from another
player -- see the 3 foreign players in
HANA_2026090002_CURRENT_SG_VALIDATION_REPORT_V2.json's evidence
section, whose *current* R1/R2 SG is real and used here exactly like
everyone else's; only their *historical* corpus depth is thin, which
does not block this per-player additive update (it only affected the
walk-forward's own historical training rows, a separate concern).
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.backtest.point_in_time_features import load_corpus  # noqa: E402
from klpga.neo_win.current_sg_walk_forward import (  # noqa: E402
    build_eligible_rows,
    fit_model,
    run_walk_forward,
)
from klpga.models.math_utils import wilcoxon_signed_rank_test  # noqa: E402
from klpga.neo_win.round_update_r2 import PlayerR2SimInput, simulate_post_round2  # noqa: E402

CONTENT = ROOT / "content" / "website_v2"
DB_PATH = ROOT / "data" / "klpga.sqlite"
OUT_PATH = CONTENT / "2026090002_POST_R3_CANDIDATE_FREEZE_V1.json"

MODEL_ID = "R1SG_R2SG"
MODEL_VERSION = "hana_post_r3_current_sg_v1"
RESEARCH_COMMIT = "2975036b33e25c5db3265a4b02487e5e92cb8466"
RESEARCH_BRANCH = "research/hana-current-sg-model-validation-20260918"
SEED = 20260918
N_SIM = 60000
REMAINING_ROUNDS = 2
BOOTSTRAP_RESAMPLES = 5000
BOOTSTRAP_SEED = 20260918
SIGNIFICANCE_ALPHA = 0.05


class HardStopError(RuntimeError):
    """Raised when the identity gate fails -- never caught, never
    silently downgraded to a partial/best-effort artifact."""


def compute_validated_model() -> dict:
    """Recomputes the R1SG_R2SG walk-forward validation live (never
    hardcoded), and re-runs the same 5-criterion gate the research
    branch used. Raises HardStopError if the gate does not PASS --
    this script must never promote a model that fails its own gate."""
    conn = sqlite3.connect(str(DB_PATH))
    corpus = load_corpus(conn)
    warehouse = json.loads((CONTENT / "historical_sg_warehouse.json").read_text(encoding="utf-8"))
    game_codes = {r["game_code"] for r in warehouse["records"]}
    if "2026090002" in game_codes or "2026090003" in game_codes:
        raise HardStopError("leakage: Hana or KB present in the historical SG warehouse")

    rows = build_eligible_rows(conn, warehouse, corpus=corpus)
    result = run_walk_forward(rows)

    base_events = result.event_level_mae["BASE"]
    chal_events = result.event_level_mae[MODEL_ID]
    diffs = [b - c for b, c in zip(base_events, chal_events)]
    wtest = wilcoxon_signed_rank_test(diffs)

    n = len(diffs)
    half = n // 2
    first_half, second_half = diffs[:half], diffs[half:]
    first_mean = sum(first_half) / len(first_half)
    second_mean = sum(second_half) / len(second_half)

    rng = random.Random(BOOTSTRAP_SEED)
    boot_means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    ci_lo = boot_means[int(0.025 * BOOTSTRAP_RESAMPLES)]
    ci_hi = boot_means[int(0.975 * BOOTSTRAP_RESAMPLES)]

    coef = result.final_coefficients[MODEL_ID]
    gate = {
        "p_lt_0.05": wtest["p_value"] < SIGNIFICANCE_ALPHA,
        "bootstrap_ci_excludes_zero": ci_lo > 0,
        "coef_r1sg_negative": coef["r1_sg_total"] < 0,
        "coef_r2sg_negative": coef["r2_sg_total"] < 0,
        "split_half_same_sign": (first_mean > 0 and second_mean > 0),
    }
    if not all(gate.values()):
        raise HardStopError(f"model gate FAILED, refusing to promote: {gate}")

    return {
        "model_id": MODEL_ID,
        "model_version": MODEL_VERSION,
        "coefficients": coef,
        "n_player_rounds": result.n_player_rounds,
        "n_events": result.n_events,
        "n_evaluated_events": result.n_evaluated_events,
        "mae": result.per_model[MODEL_ID]["mae"],
        "rmse": result.per_model[MODEL_ID]["rmse"],
        "base_mae": result.per_model["BASE"]["mae"],
        "base_rmse": result.per_model["BASE"]["rmse"],
        "wilcoxon_p_value": wtest["p_value"],
        "wilcoxon_z": wtest["z"],
        "bootstrap_ci_95": {"lo": ci_lo, "hi": ci_hi},
        "split_half": {
            "first_half_mean_diff": first_mean, "first_half_n": len(first_half),
            "second_half_mean_diff": second_mean, "second_half_n": len(second_half),
            "same_sign": gate["split_half_same_sign"],
        },
        "gate": gate,
        "gate_pass": True,
        "research_commit": RESEARCH_COMMIT,
        "research_branch": RESEARCH_BRANCH,
    }


def main() -> None:
    model = compute_validated_model()
    r1sg_c = model["coefficients"]["r1_sg_total"]
    r2sg_c = model["coefficients"]["r2_sg_total"]

    freeze = json.loads((CONTENT / "2026090002_R2_FROZEN_EVIDENCE.json").read_text(encoding="utf-8"))
    forecast = json.loads((CONTENT / "2026090002_POST_R2_FINAL_FORECAST.json").read_text(encoding="utf-8"))
    r1sg = json.loads((CONTENT / "HANA_2026090002_R1_SG_V1.json").read_text(encoding="utf-8"))
    r2sg = json.loads((CONTENT / "HANA_2026090002_R2_SG_V1.json").read_text(encoding="utf-8"))

    survivors = [r for r in freeze["records"] if r["status"] == "ACTIVE"]
    survivor_ids = [s["player_id"] for s in survivors]

    # ---- HARD_STOP identity gate ----
    if len(survivors) != 64:
        raise HardStopError(f"expected exactly 64 cut survivors, got {len(survivors)}")
    if len(set(survivor_ids)) != 64:
        raise HardStopError(f"duplicate player_id among cut survivors: {len(survivor_ids) - len(set(survivor_ids))} duplicates")

    forecast_by_id = {r["player_id"]: r for r in forecast["records"]}
    if set(forecast_by_id) != set(survivor_ids):
        raise HardStopError("baseline forecast population is not exactly the 64 cut survivors")

    r1_by_id = {r["player_id"]: r["total"] for r in r1sg["records"]}
    r2_by_id = {r["player_id"]: r["total"] for r in r2sg["records"]}
    r1_missing = sorted(s["player_name"] for s in survivors if s["player_id"] not in r1_by_id)
    r2_missing = sorted(s["player_name"] for s in survivors if s["player_id"] not in r2_by_id)
    if r1_missing:
        raise HardStopError(f"R1 SG missing for cut survivors, HARD STOP: {r1_missing}")
    if r2_missing:
        raise HardStopError(f"R2 SG missing for cut survivors, HARD STOP: {r2_missing}")

    names_seen = [s["player_name"] for s in survivors]
    if len(names_seen) != len(set(names_seen)):
        raise HardStopError("identity ambiguity: duplicate player names among cut survivors")
    # ---- end HARD_STOP gate ----

    provenance = {}
    sim_inputs = []
    for pid in sorted(survivor_ids, key=int):
        f = forecast_by_id[pid]
        r1_sg_total = r1_by_id[pid]
        r2_sg_total = r2_by_id[pid]
        historical_expected = f["expected_final_round_to_par"]
        historical_expected_source = f["expected_source"]
        spread = f["spread"]
        spread_source = f["spread_source"]

        current_sg_update = r1sg_c * r1_sg_total + r2sg_c * r2_sg_total
        updated_expected = historical_expected + current_sg_update

        provenance[pid] = {
            "player_name": f["player_name"],
            "r1_score_to_par": f["r1_score_to_par"],
            "r2_score_to_par": f["r2_score_to_par"],
            "r2_total_to_par": f["r2_total_to_par"],
            "historical_expected": historical_expected,
            "historical_expected_source": historical_expected_source,
            "spread": spread,
            "spread_source": spread_source,
            "r1_sg_total": r1_sg_total,
            "r1_sg_source": "HANA_2026090002_R1_SG_V1.json",
            "r2_sg_total": r2_sg_total,
            "r2_sg_source": "HANA_2026090002_R2_SG_V1.json",
            "current_sg_update": current_sg_update,
            "updated_expected_round_score_to_par": updated_expected,
            "model_version": MODEL_VERSION,
        }
        sim_inputs.append(PlayerR2SimInput(
            player_code=pid, player_name=f["player_name"],
            expected_round_score_to_par=updated_expected, spread=spread,
            r1_score_to_par=f["r1_score_to_par"], r2_score_to_par=f["r2_score_to_par"], made_cut=True,
            r1_sg_total=r1_sg_total, r2_sg_total=r2_sg_total,
            r1_sg_source="HANA_2026090002_R1_SG_V1.json", r2_sg_source="HANA_2026090002_R2_SG_V1.json",
        ))

    result = simulate_post_round2(sim_inputs, remaining_rounds=REMAINING_ROUNDS, n_simulations=N_SIM, rng=random.Random(SEED))

    if set(result) != set(survivor_ids):
        raise HardStopError("simulation output population mismatch")
    prob_sum = sum(v["win_pct"] for v in result.values())
    if abs(prob_sum - 100.0) > 0.01:
        raise HardStopError(f"win probability sum {prob_sum} not ~100%")
    for pid, v in result.items():
        for key in ("win_pct", "top5_pct", "top10_pct", "top20_pct"):
            val = v[key]
            if val != val or val < 0:  # NaN or negative
                raise HardStopError(f"invalid probability {key}={val} for player {pid}")
        if not (v["top20_pct"] >= v["top10_pct"] >= v["top5_pct"] >= v["win_pct"]):
            raise HardStopError(f"monotonicity violated for player {pid}: {v}")

    records = []
    for pid in sorted(survivor_ids, key=int):
        p = provenance[pid]
        r = result[pid]
        records.append({
            "player_id": pid,
            "player_name": p["player_name"],
            "r1_score_to_par": p["r1_score_to_par"],
            "r2_score_to_par": p["r2_score_to_par"],
            "r2_total_to_par": p["r2_total_to_par"],
            "historical_expected": p["historical_expected"],
            "historical_expected_source": p["historical_expected_source"],
            "spread": p["spread"],
            "spread_source": p["spread_source"],
            "r1_sg_total": p["r1_sg_total"],
            "r2_sg_total": p["r2_sg_total"],
            "current_sg_update": p["current_sg_update"],
            "updated_expected_round_score_to_par": p["updated_expected_round_score_to_par"],
            "win_pct": r["win_pct"],
            "top5_pct": r["top5_pct"],
            "top10_pct": r["top10_pct"],
            "top20_pct": r["top20_pct"],
            "model_version": MODEL_VERSION,
        })

    out = {
        "schema_version": 1,
        "artifact": "2026090002_POST_R3_CANDIDATE_FREEZE_V1",
        "status": "CANDIDATE -- not yet promoted to the live R2 page or any published artifact",
        "game_code": "2026090002",
        "stage": "POST_R3_CANDIDATE",
        "source_baseline": "2026090002_POST_R2_FINAL_FORECAST.json (read-only, untouched)",
        "simulated_field_size": len(records),
        "remaining_rounds": REMAINING_ROUNDS,
        "n_simulations": N_SIM,
        "seed": SEED,
        "simulation_engine": "klpga.neo_win.round_update_r2.simulate_post_round2",
        "win_probability_sum_pct": prob_sum,
        "model": model,
        "identity_gate": {
            "cut_survivor_population": len(survivors),
            "duplicate_player_ids": 0,
            "r1_sg_matched": 64, "r1_sg_missing": r1_missing,
            "r2_sg_matched": 64, "r2_sg_missing": r2_missing,
            "identity_ambiguity_found": False,
            "gate_result": "PASS",
        },
        "records": records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT_PATH)
    print("win_probability_sum_pct:", prob_sum)
    print("model gate:", model["gate"])


if __name__ == "__main__":
    main()
