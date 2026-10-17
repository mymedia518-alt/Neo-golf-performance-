"""Post-R2 (FR-stage) probability forecast for 아이스버그골프·서울신문
오픈 (game_code 2026100003) -- the next-round prediction step, one stage
later than scripts/247/249's post-R1 forecast, built the same way:
real scores as simulation input, a walk-forward-checked SG adjustment
shown alongside the score-only number, never archived-and-unused.

======================================================================
CUT GATING: A REAL FACT NOW, NOT A SIMULATED PROBABILITY
======================================================================
scripts/251 determined made_cut for all 107 R2 leaderboard entrants
from the real official R3 (FR) tee sheet -- not a guess. Only the 61
real cutmakers are simulated here for the one remaining round (FR);
the 41 players who missed the cut and the 6 total withdrawals (1 from
R1, 5 from R2) get win/top5/top10/top20 = 0.0, a real known fact, same
convention klpga.neo_win.round_update_r2.simulate_post_round2 already
established site-wide for every other tournament's own post-cut stage
(cut_players get 0.0 across the board, cutmakers get make_cut_pct=100.0
-- this script's own cut_probability field follows that exact
precedent: 100.0 for the 61 real cutmakers, 0.0 for everyone else,
never a probabilistic model output anymore once the cut is a real,
already-determined fact).

======================================================================
SCORE INPUT / SG ADJUSTMENT
======================================================================
Each cutmaker's known total = real R1 + real R2 score. One remaining
round (FR) is drawn from Normal(expected, spread):
  - BASE-only variant: expected = prior_avg_round_to_par (same frozen
    PRE M4 feature used throughout, ICEBERG_2026100003_PRE_M4_CANDIDATE_V1.json)
  - SG-adjusted variant: expected = scripts/253's walk-forward-fit
    R2SG model (intercept + BASE_coef*prior_avg_round_to_par +
    R2SG_coef*real R2 SG total), same technique scripts/249 used for
    R1->R2. scripts/253 found r2sg_beats_base=False (event wins tied
    4-4 across 8 evaluated historical events, R2SG's pooled MAE is
    actually very slightly WORSE than BASE, 2.5467 vs 2.5456) -- the
    SG-adjusted numbers are still produced and shown side by side with
    BASE-only, per the same operator instruction scripts/249 already
    followed, not withheld for a weak/negative validation result.

Spread (per-round variance) is each player's own historical round_to_par
pstdev (klpga_pipeline/data/klpga.sqlite player_round, >=3 real rounds)
or the population pstdev fallback -- same method scripts/247/249 used,
re-derived fresh here rather than copied, since the corpus itself is
unchanged.

Output is a NEW, separately-versioned file
(ICEBERG_2026100003_POST_R2_FORECAST_V1.json) -- scripts/247's and
scripts/249's own R1-stage forecast files are not touched or
overwritten.
"""
from __future__ import annotations

import json
import random
import sqlite3
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.ops.paths import db_path  # noqa: E402

GAME_CODE = "2026100003"
CONTENT = ROOT / "content" / "website_v2"
R2_OFFICIAL_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_R2_OFFICIAL_V1.json"
R2_SG_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_R2_SG_OFFICIAL_V1.json"
M4_CANDIDATE_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_PRE_M4_CANDIDATE_V1.json"
WALK_FORWARD_PATH = CONTENT / "R2_PREDICTS_FINAL_WALK_FORWARD_V1.json"
OUT_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_POST_R2_FORECAST_V1.json"

N_SIMULATIONS = 60000
RANDOM_SEED = 20261017
REMAINING_ROUNDS = 1  # FR only -- this tournament is 3 rounds, R1+R2 are both now real
MIN_PERSONAL_ROUNDS_FOR_OWN_SPREAD = 3


def main() -> None:
    r2_official = json.loads(R2_OFFICIAL_PATH.read_text(encoding="utf-8"))
    r2_by_id = {r["player_id"]: r for r in r2_official["records"]}
    cutmaker_ids = [pid for pid, r in r2_by_id.items() if r["made_cut"]]
    assert len(cutmaker_ids) == r2_official["made_cut_counts"]["made_cut_true"]

    walk_forward = json.loads(WALK_FORWARD_PATH.read_text(encoding="utf-8"))
    r2sg_beats_base = bool(walk_forward.get("r2sg_beats_base"))
    b0, b1, b2 = walk_forward["final_coefficients"]["R2SG"]

    r2_sg = json.loads(R2_SG_PATH.read_text(encoding="utf-8"))
    sg_by_id: dict[str, float] = {
        r["player_id"]: float(r["total"])
        for r in r2_sg["records"]
        if r.get("player_id") and r.get("total") is not None
    }

    m4 = json.loads(M4_CANDIDATE_PATH.read_text(encoding="utf-8"))
    base_feature_by_id: dict[str, float] = {}
    for rec in m4.get("records", []):
        base = (rec.get("features") or {}).get("prior_avg_round_to_par")
        if base is not None:
            base_feature_by_id[str(rec["playerCode"])] = float(base)

    conn = sqlite3.connect(db_path())
    hist_rounds: dict[str, list[float]] = {}
    for pid, rtp in conn.execute("SELECT player_id, round_to_par FROM player_round WHERE round_to_par IS NOT NULL"):
        hist_rounds.setdefault(pid, []).append(float(rtp))
    pop_spread = statistics.pstdev([x for v in hist_rounds.values() for x in v])

    def spread_for(pid: str) -> tuple[float, str]:
        own = hist_rounds.get(pid, [])
        if len(own) >= MIN_PERSONAL_ROUNDS_FOR_OWN_SPREAD:
            return max(statistics.pstdev(own), 0.5), f"own_{len(own)}_rounds"
        return pop_spread, "population_fallback"

    sim_inputs = []
    excluded = []
    for pid in cutmaker_ids:
        r2rec = r2_by_id[pid]
        r1_score = r2rec["r1_score"]
        r2_score = r2rec["r2_score"]
        base_feature = base_feature_by_id.get(pid)
        r2_sg_total = sg_by_id.get(pid)
        if r1_score is None or r2_score is None:
            excluded.append({"player_id": pid, "reason": "NO_REAL_R1_OR_R2_SCORE"})
            continue
        if base_feature is None:
            excluded.append({"player_id": pid, "reason": "NO_BASE_FEATURE"})
            continue
        if r2_sg_total is None:
            excluded.append({"player_id": pid, "reason": "NO_R2_SG"})
            continue
        spread, spread_source = spread_for(pid)
        sim_inputs.append({
            "player_id": pid,
            "known_total_to_par": r1_score + r2_score,
            "r2_sg_total": r2_sg_total,
            "base_only_expected": base_feature,
            "sg_adjusted_expected": b0 + b1 * base_feature + b2 * r2_sg_total,
            "spread": spread,
            "spread_source": spread_source,
        })

    def simulate(expected_key: str) -> dict[str, dict]:
        rng = random.Random(RANDOM_SEED)
        wins = {p["player_id"]: 0.0 for p in sim_inputs}
        top5 = {p["player_id"]: 0 for p in sim_inputs}
        top10 = {p["player_id"]: 0 for p in sim_inputs}
        top20 = {p["player_id"]: 0 for p in sim_inputs}
        for _ in range(N_SIMULATIONS):
            totals = []
            for p in sim_inputs:
                remaining = sum(rng.normalvariate(p[expected_key], p["spread"]) for _ in range(REMAINING_ROUNDS))
                totals.append((p["player_id"], p["known_total_to_par"] + remaining))
            totals.sort(key=lambda t: t[1])
            if totals:
                best = totals[0][1]
                leaders = [code for code, score in totals if score == best]
                for code in leaders:
                    wins[code] += 1.0 / len(leaders)
            for rank, (code, _s) in enumerate(totals, start=1):
                if rank <= 5:
                    top5[code] += 1
                if rank <= 10:
                    top10[code] += 1
                if rank <= 20:
                    top20[code] += 1
        return {
            pid: {
                "win": round(wins[pid] / N_SIMULATIONS, 6),
                "top5": round(top5[pid] / N_SIMULATIONS, 6),
                "top10": round(top10[pid] / N_SIMULATIONS, 6),
                "top20": round(top20[pid] / N_SIMULATIONS, 6),
            }
            for pid in wins
        }

    base_sim = simulate("base_only_expected")
    sg_sim = simulate("sg_adjusted_expected")

    records = []
    for p in sim_inputs:
        pid = p["player_id"]
        records.append({
            "player_id": pid,
            "made_cut": True,
            "cut_probability": 100.0,
            "known_total_to_par": p["known_total_to_par"],
            "r2_sg_total": p["r2_sg_total"],
            "base_only_expected_round_score_to_par": round(p["base_only_expected"], 4),
            "sg_adjusted_expected_round_score_to_par": round(p["sg_adjusted_expected"], 4),
            "spread": round(p["spread"], 4),
            "spread_source": p["spread_source"],
            "base_only_win_probability": base_sim[pid]["win"],
            "base_only_top5_probability": base_sim[pid]["top5"],
            "base_only_top10_probability": base_sim[pid]["top10"],
            "base_only_top20_probability": base_sim[pid]["top20"],
            "sg_adjusted_win_probability": sg_sim[pid]["win"],
            "sg_adjusted_top5_probability": sg_sim[pid]["top5"],
            "sg_adjusted_top10_probability": sg_sim[pid]["top10"],
            "sg_adjusted_top20_probability": sg_sim[pid]["top20"],
            "win_delta": round(sg_sim[pid]["win"] - base_sim[pid]["win"], 6),
        })

    # Players who missed the cut or withdrew: real fact 0 across the board.
    non_cutmaker_records = []
    for pid, r in r2_by_id.items():
        if r["made_cut"]:
            continue
        non_cutmaker_records.append({
            "player_id": pid,
            "made_cut": False,
            "made_cut_source": r["made_cut_source"],
            "cut_probability": 0.0,
            "win_probability": 0.0, "top5_probability": 0.0, "top10_probability": 0.0, "top20_probability": 0.0,
        })

    out = {
        "artifact": "iceberg_2026100003_post_r2_forecast_v1",
        "game_code": GAME_CODE,
        "source_round": 2,
        "method": "Monte Carlo (same mechanics as scripts/247/249): real R1+R2 total + "
                  "1 remaining round (FR) drawn from Normal(expected, spread), ranked across the "
                  "real cutmaker field only.",
        "cut_gating": {
            "method": "real official R3 (FR) tee-sheet presence (scripts/251), not a simulated probability",
            "cutmakers": len(cutmaker_ids),
            "non_cutmakers": len(non_cutmaker_records),
        },
        "walk_forward_source": str(WALK_FORWARD_PATH.relative_to(ROOT.parent)),
        "walk_forward_r2sg_beats_base": r2sg_beats_base,
        "walk_forward_disclosure": (
            "R2SG model does NOT outperform BASE-only in walk-forward validation (event_wins tied "
            "4-4 across 8 evaluated historical events; R2SG's pooled MAE is marginally WORSE than "
            "BASE, 2.5467 vs 2.5456 strokes) -- the SG-adjusted numbers are a labeled alternative, "
            "not a validated improvement."
        ),
        "fitted_coefficients_R2SG_model": {"intercept": b0, "base_coef": b1, "r2sg_coef": b2},
        "remaining_rounds": REMAINING_ROUNDS,
        "n_simulations": N_SIMULATIONS,
        "random_seed": RANDOM_SEED,
        "spread_source": f"klpga_pipeline/data/klpga.sqlite player_round (own stdev if >= {MIN_PERSONAL_ROUNDS_FOR_OWN_SPREAD} real rounds, else population pstdev={round(pop_spread, 4)})",
        "excluded_cutmakers": excluded,
        "cutmaker_records": records,
        "non_cutmaker_records": non_cutmaker_records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    problems = []
    for r in records:
        if not (r["sg_adjusted_win_probability"] <= r["sg_adjusted_top5_probability"] <= r["sg_adjusted_top10_probability"] <= r["sg_adjusted_top20_probability"] <= 1.0 + 1e-9):
            problems.append(r["player_id"])
    win_sum = sum(r["sg_adjusted_win_probability"] for r in records)

    print(json.dumps({
        "written": str(OUT_PATH),
        "cutmakers_simulated": len(records),
        "excluded_cutmakers": len(excluded),
        "excluded_detail": excluded,
        "non_cutmakers": len(non_cutmaker_records),
        "monotonicity_problems": problems,
        "monotonicity_pass": len(problems) == 0,
        "win_probability_sum": round(win_sum, 4),
        "r2sg_beats_base": r2sg_beats_base,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
