"""HANA R3 -> FINAL PIPELINE, STEP 6 groundwork -- BASELINE (no current
SG) comparison variant, research-only, never published.

Same population/engine/seed/n_simulations as
2026090002_POST_R4_FINAL_PREVIEW.json, the ONLY difference being
expected_round_score_to_par = candidate freeze's own `historical_expected`
(the PRE-time baseline, before any current-SG adjustment) instead of
`updated_expected_round_score_to_par`. This isolates exactly what the
already-promoted R1SG_R2SG current-SG adjustment changes about the
FINAL forecast -- never a different model, never re-fit.

Writes content/website_v2/HANA_2026090002_R4_BASELINE_NO_CURRENT_SG_V1.json.
Research artifact only -- never read by any page builder.
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
OUT_PATH = CONTENT / "HANA_2026090002_R4_BASELINE_NO_CURRENT_SG_V1.json"

SEED = 20260918
N_SIM = 60000


def main() -> None:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    r3_freeze = json.loads(R3_FREEZE_PATH.read_text(encoding="utf-8"))
    cand_by_id = {r["player_id"]: r for r in candidate["records"]}
    r3_by_id = {r["player_id"]: r for r in r3_freeze["records"] if r["status"] == "ACTIVE"}
    assert set(cand_by_id) == set(r3_by_id) and len(cand_by_id) == 64

    sim_inputs = []
    for pid in sorted(cand_by_id, key=int):
        c = cand_by_id[pid]
        r3r = r3_by_id[pid]
        sim_inputs.append(
            PlayerR3SimInput(
                player_code=pid, player_name=c["player_name"],
                expected_round_score_to_par=c["historical_expected"],
                spread=c["spread"],
                r1_score_to_par=c["r1_score_to_par"], r2_score_to_par=c["r2_score_to_par"],
                r3_score_to_par=r3r["r3_score_to_par"], made_cut=True,
            )
        )
    rng = random.Random(SEED)
    result = simulate_post_round3(sim_inputs, n_simulations=N_SIM, rng=rng)
    win_sum = sum(v["win_pct"] for v in result.values())
    assert abs(win_sum - 100.0) < 0.01, win_sum

    records = []
    for pid in sorted(cand_by_id, key=int):
        rec = {"player_id": pid, "player_name": cand_by_id[pid]["player_name"], "historical_expected": cand_by_id[pid]["historical_expected"]}
        rec.update(result[pid])
        records.append(rec)

    out = {
        "schema_version": 1,
        "artifact": "HANA_2026090002_R4_BASELINE_NO_CURRENT_SG_V1",
        "purpose": "Research-only BASELINE (no current-SG adjustment) FINAL-stage comparison, never published",
        "seed": SEED, "n_simulations": N_SIM, "remaining_rounds": 1,
        "win_probability_sum_pct": win_sum,
        "records": records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT_PATH, "win_pct sum:", win_sum)


if __name__ == "__main__":
    main()
