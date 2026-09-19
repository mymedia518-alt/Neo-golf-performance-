"""HANA R3 -> FINAL PIPELINE, STEP 4 (operator instruction, 2026-09-19,
"Proceed with Option 1"): generate the FINAL (post-R3, remaining_rounds
=1) forecast for 2026090002 using the ALREADY-VALIDATED R1SG_R2SG model
EXACTLY as promoted -- no retraining, no new coefficients, no new
model. R3 SG is deliberately NOT used as a predictive feature (the
R1SG_R2SG_R3SG walk-forward extension was tested and FAILED its
promotion gate -- see HANA_2026090002_R4_SG_VALIDATION_REPORT_V1.json);
it is evidence/diagnostic only (HANA_2026090002_R3_SG_V1.json).

INPUTS (read-only, never modified/overwritten/recomputed):
  - 2026090002_POST_R3_CANDIDATE_FREEZE_V1.json -- the immutable,
    already-validated R1SG_R2SG forecast. This script reads each
    player's own `updated_expected_round_score_to_par` and `spread`
    VERBATIM -- these already encode the promoted model's R1+R2 SG
    adjustment; nothing is recomputed here.
  - 2026090002_R3_FROZEN_EVIDENCE.json -- the real official R3 result
    (r3_score_to_par) for the same 64 players, built this session from
    operator-supplied official evidence.
  - 2026090002_R2_FROZEN_EVIDENCE.json -- real r1/r2_score_to_par
    (cross-checked against the candidate freeze's own copies).

ENGINE: klpga.neo_win.round_update_r3.simulate_post_round3 -- the same
generic Monte Carlo engine already used in production for R3->FINAL
forecasts elsewhere (KB). Only ONE remaining round (R4) is simulated;
every one of the 64 real cutmakers is guaranteed to play it (no new
elimination event between R3 and FINAL -- see round_update_r3.py's own
docstring). n_simulations=60000, seed=20260918 (same seed threaded
through every Hana Monte Carlo run so far this pipeline).

HARD_STOP identity gate runs BEFORE any simulation.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.round_update_r3 import PlayerR3SimInput, simulate_post_round3  # noqa: E402

CANDIDATE_PATH = CONTENT / "2026090002_POST_R3_CANDIDATE_FREEZE_V1.json"
R3_FREEZE_PATH = CONTENT / "2026090002_R3_FROZEN_EVIDENCE.json"
R2_FREEZE_PATH = CONTENT / "2026090002_R2_FROZEN_EVIDENCE.json"
R3_SG_PATH = CONTENT / "HANA_2026090002_R3_SG_V1.json"
OUT_PATH = CONTENT / "2026090002_POST_R4_FINAL_PREVIEW.json"

MODEL_ID = "R1SG_R2SG"
MODEL_VERSION = "hana_post_r3_current_sg_v1"
SEED = 20260918
N_SIM = 60000


class HardStopError(RuntimeError):
    pass


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    candidate = _load(CANDIDATE_PATH)
    r3_freeze = _load(R3_FREEZE_PATH)
    r2_freeze = _load(R2_FREEZE_PATH)
    r3_sg = _load(R3_SG_PATH)

    cand_by_id = {r["player_id"]: r for r in candidate["records"]}
    r3_active = [r for r in r3_freeze["records"] if r["status"] == "ACTIVE"]
    r3_by_id = {r["player_id"]: r for r in r3_active}
    r2_active = [r for r in r2_freeze["records"] if r["status"] == "ACTIVE"]
    r2_by_id = {r["player_id"]: r for r in r2_active}
    r3_sg_by_id = {r["player_id"]: r for r in r3_sg["records"]}

    # ---- HARD_STOP IDENTITY GATE (before any simulation) ----
    cand_ids = set(cand_by_id)
    r3_ids = set(r3_by_id)
    r2_ids = set(r2_by_id)
    r3_sg_ids = set(r3_sg_by_id)

    if len(cand_ids) != 64:
        raise HardStopError(f"candidate freeze population != 64: {len(cand_ids)}")
    if len(r3_ids) != 64:
        raise HardStopError(f"R3 freeze ACTIVE population != 64: {len(r3_ids)}")
    if cand_ids != r3_ids:
        raise HardStopError(
            f"candidate freeze vs R3 freeze population mismatch -- "
            f"only in candidate: {sorted(cand_ids - r3_ids)}, only in R3: {sorted(r3_ids - cand_ids)}"
        )
    if cand_ids != r2_ids:
        raise HardStopError(
            f"candidate freeze vs R2 freeze population mismatch -- "
            f"only in candidate: {sorted(cand_ids - r2_ids)}, only in R2: {sorted(r2_ids - cand_ids)}"
        )
    if r3_sg_ids != r3_ids:
        raise HardStopError(
            f"R3 SG evidence vs R3 freeze population mismatch -- "
            f"only in SG: {sorted(r3_sg_ids - r3_ids)}, only in freeze: {sorted(r3_ids - r3_sg_ids)}"
        )
    # cross-check r1/r2 scores agree between candidate (frozen at R2 promotion time) and R2 freeze (source of truth)
    r1r2_mismatches = []
    for pid in cand_ids:
        c = cand_by_id[pid]
        r2r = r2_by_id[pid]
        if c["r1_score_to_par"] != r2r["r1_score_to_par"] or c["r2_score_to_par"] != r2r["r2_score_to_par"]:
            r1r2_mismatches.append(pid)
    if r1r2_mismatches:
        raise HardStopError(f"R1/R2 score disagreement between candidate freeze and R2 freeze: {r1r2_mismatches}")
    print("[IDENTITY GATE] 64/64 population match (candidate == R3 freeze == R2 freeze == R3 SG), 0 mismatches -- PASS")

    # ---- build sim inputs: REUSE candidate's own updated_expected_round_score_to_par + spread VERBATIM ----
    sim_inputs = []
    provenance = {}
    for pid in sorted(cand_ids, key=int):
        c = cand_by_id[pid]
        r3r = r3_by_id[pid]
        r3sg = r3_sg_by_id[pid]
        sim_inputs.append(
            PlayerR3SimInput(
                player_code=pid,
                player_name=c["player_name"],
                expected_round_score_to_par=c["updated_expected_round_score_to_par"],
                spread=c["spread"],
                r1_score_to_par=c["r1_score_to_par"],
                r2_score_to_par=c["r2_score_to_par"],
                r3_score_to_par=r3r["r3_score_to_par"],
                made_cut=True,
            )
        )
        provenance[pid] = {
            "player_id": pid,
            "player_name": c["player_name"],
            "r1_score_to_par": c["r1_score_to_par"],
            "r2_score_to_par": c["r2_score_to_par"],
            "r3_score_to_par": r3r["r3_score_to_par"],
            "r3_total_under_par": r3r["r3_total_under_par"],
            "historical_expected": c["historical_expected"],
            "historical_expected_source": c["historical_expected_source"],
            "spread": c["spread"],
            "spread_source": c["spread_source"],
            "r1_sg_total": c["r1_sg_total"],
            "r2_sg_total": c["r2_sg_total"],
            "current_sg_update": c["current_sg_update"],
            "expected_round_score_to_par": c["updated_expected_round_score_to_par"],
            "r3_sg_total": r3sg["total"],
            "r3_sg_note": "EVIDENCE/DIAGNOSTIC ONLY -- NOT used as a predictive feature (R1SG_R2SG_R3SG failed its promotion gate)",
            "model_version": MODEL_VERSION,
            "model_id": MODEL_ID,
        }

    missing = [p.player_code for p in sim_inputs if p.r1_score_to_par is None or p.r2_score_to_par is None or p.r3_score_to_par is None]
    if missing:
        raise HardStopError(f"REFUSING: missing real score(s) for confirmed cutmaker(s): {missing}")

    rng = random.Random(SEED)
    result = simulate_post_round3(sim_inputs, n_simulations=N_SIM, rng=rng)

    if set(result.keys()) != cand_ids:
        raise HardStopError(f"simulation output population != input population -- missing: {cand_ids - set(result.keys())}, extra: {set(result.keys()) - cand_ids}")

    # ---- STEP 5: post-simulation validation ----
    win_sum = sum(v["win_pct"] for v in result.values())
    if abs(win_sum - 100.0) > 0.01:
        raise HardStopError(f"win_pct sum {win_sum} not within 0.01 of 100.0")
    for pid, v in result.items():
        for k, val in v.items():
            if val != val:  # NaN check
                raise HardStopError(f"NaN probability for {pid}.{k}")
            if val < 0:
                raise HardStopError(f"negative probability for {pid}.{k} = {val}")
        if not (v["top20_pct"] >= v["top10_pct"] >= v["top5_pct"] >= v["win_pct"]):
            raise HardStopError(f"monotonicity violated for {pid}: {v}")
    print(f"[VALIDATION] win_pct sum = {win_sum}, no NaN, no negative, monotonicity holds for all 64 -- PASS")

    records = []
    for pid in sorted(cand_ids, key=int):
        rec = dict(provenance[pid])
        rec.update(result[pid])
        records.append(rec)

    out = {
        "schema_version": 1,
        "artifact": "2026090002_POST_R4_FINAL_PREVIEW",
        "status": "PREVIEW -- not yet promoted to any published page or artifact",
        "game_code": "2026090002",
        "stage": "post_r3_pre_final",
        "source_baseline": "2026090002_POST_R3_CANDIDATE_FREEZE_V1.json (read-only, untouched, model/coefficients reused verbatim)",
        "source_r3_freeze": "2026090002_R3_FROZEN_EVIDENCE.json (read-only, untouched)",
        "remaining_rounds": 1,
        "n_simulations": N_SIM,
        "seed": SEED,
        "simulation_engine": "klpga.neo_win.round_update_r3.simulate_post_round3",
        "model": {
            "model_id": MODEL_ID,
            "model_version": MODEL_VERSION,
            "note": (
                "Reuses the already-validated/promoted R1SG_R2SG model EXACTLY as "
                "promoted -- same coefficients (r1_sg_total=-0.095010, "
                "r2_sg_total=-0.112655), same additive current_sg_update per player "
                "(read verbatim from the candidate freeze), NO retraining, NO new "
                "coefficients, NO R3 SG term. R3 SG is recorded per player for "
                "evidence/diagnostic/reporting purposes only -- see r3_sg_total / "
                "HANA_2026090002_R3_SG_VS_FINAL_RESEARCH_REPORT_V1.json for the "
                "separate, non-production research analysis."
            ),
        },
        "identity_gate": {
            "population": 64,
            "duplicate_player_ids": 0,
            "missing_players": 0,
            "candidate_r3_r2_sg_population_match": True,
            "r1r2_score_cross_check_mismatches": 0,
            "gate_result": "PASS",
        },
        "win_probability_sum_pct": win_sum,
        "records": records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT_PATH)
    print("population:", len(records), "win_pct sum:", win_sum)


if __name__ == "__main__":
    main()
