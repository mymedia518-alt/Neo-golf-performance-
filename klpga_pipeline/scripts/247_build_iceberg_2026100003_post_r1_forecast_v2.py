"""Real post-R1 probability forecast for 아이스버그골프·서울신문 오픈
(game_code 2026100003) -- supersedes scripts/243's frozen-PRE-copy
POST_R1_FORECAST (which carried zero R1 information forward).

TECHNIQUE: the SAME Monte Carlo mechanics klpga.neo_win.round_update_r2/
round_update_r3 already use in production for every other tournament's
post-round forecast (Normal-distributed remaining-round draws from a
point-in-time BASE prior, summed with the real already-played round
score(s), ranked across the field by total simulated score) -- applied
one round earlier (post-R1 instead of post-R2) because this is this
specific real R1 state. Not a new technique.

ONE INPUT DECISION THIS SCRIPT MAKES THAT round_update_r2 DOES NOT:
whether to let real R1 Strokes Gained adjust the remaining-round
expectation. scripts/246's walk-forward test (R1SG vs BASE predicting
real R2 round_to_par, 10 real historical events, strictly-prior
training only) found R1SG_beats_base=False (event_wins tied 4-4, MAE
improvement 0.0035 strokes -- not a real signal). Per that result, this
script does NOT apply an SG adjustment -- expected_round_score_to_par
is BASE only (prior_avg_round_to_par, already computed and stored for
every entrant in ICEBERG_2026100003_PRE_M4_CANDIDATE_V1.json's own
features -- not recomputed here).

NO CUT GATING: 2026100003's own official cut rule is unconfirmed
(raw/2026100003/game_list.json's own expectCutRank=0, already
established by scripts/238/242's own docstrings) and no cut has
happened yet at the R1 stage regardless -- every non-WD entrant with a
real BASE feature is simulated for both remaining rounds (R2, FR; this
tournament is 3 rounds/54 holes, not 4).

REMAINING-ROUND SPREAD: no neo_consistency_stddev field exists in this
tournament's own M4 feature set (that field is a different, older
model's artifact -- klpga.neo_win.archive -- never built for this
tournament). Computed fresh here instead, real and documented: each
player's own sample stdev of real historical round_to_par
(klpga_pipeline/data/klpga.sqlite player_round, the same 10-event real
corpus scripts/241 built), population stdev (all 3,392 real historical
rounds) as the fallback for a player with fewer than 3 personal rounds
on file -- never a hand-picked constant.

MISSING DATA: a player with no real R1 score, no real BASE feature, or
WD status is excluded from simulation and reported, never assigned a
fabricated average.
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

from klpga.website_v2.official_data import parse_leaderboard_html  # noqa: E402
from klpga.ops.paths import db_path  # noqa: E402

GAME_CODE = "2026100003"
CONTENT = ROOT / "content" / "website_v2"
RAW_R1_LEADERBOARD = CONTENT / "raw_capture" / "2026100003_r1" / "roundLeaderboard_r1.html"
M4_CANDIDATE_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_PRE_M4_CANDIDATE_V1.json"
WALK_FORWARD_PATH = CONTENT / "R1_PREDICTS_R2_WALK_FORWARD_V1.json"
OUT_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_POST_R1_FORECAST_V2.json"

N_SIMULATIONS = 60000
RANDOM_SEED = 20261016
REMAINING_ROUNDS = 2  # R2 + FR (this tournament is 3 rounds / 54 holes, not 4)
MIN_PERSONAL_ROUNDS_FOR_OWN_SPREAD = 3


def main() -> None:
    walk_forward = json.loads(WALK_FORWARD_PATH.read_text(encoding="utf-8"))
    sg_adjustment_applied = bool(walk_forward.get("r1sg_beats_base"))
    assert not sg_adjustment_applied, (
        "walk-forward found r1sg_beats_base=True -- this script was written assuming the "
        "already-run negative result; an SG-adjustment branch would need to be added, not silently skipped"
    )

    r1_html = RAW_R1_LEADERBOARD.read_text(encoding="utf-8")
    r1_rows = parse_leaderboard_html(r1_html)
    r1_by_id = {r["player_id"]: r for r in r1_rows}

    m4 = json.loads(M4_CANDIDATE_PATH.read_text(encoding="utf-8"))
    base_by_id: dict[str, float] = {}
    for rec in m4.get("records", []):
        base = (rec.get("features") or {}).get("prior_avg_round_to_par")
        if base is not None:
            base_by_id[str(rec["playerCode"])] = float(base)

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
    for pid, r1 in r1_by_id.items():
        if r1.get("status") == "WD":
            excluded.append({"player_id": pid, "reason": "WD"})
            continue
        r1_score = (r1.get("rounds") or [None])[0]
        if r1_score is None:
            excluded.append({"player_id": pid, "reason": "NO_REAL_R1_SCORE"})
            continue
        base = base_by_id.get(pid)
        if base is None:
            excluded.append({"player_id": pid, "reason": "NO_BASE_FEATURE"})
            continue
        spread, spread_source = spread_for(pid)
        sim_inputs.append({
            "player_id": pid, "r1_score_to_par": float(r1_score),
            "expected_round_score_to_par": base, "spread": spread, "spread_source": spread_source,
        })

    rng = random.Random(RANDOM_SEED)
    wins = {p["player_id"]: 0.0 for p in sim_inputs}
    top5 = {p["player_id"]: 0 for p in sim_inputs}
    top10 = {p["player_id"]: 0 for p in sim_inputs}
    top20 = {p["player_id"]: 0 for p in sim_inputs}

    for _ in range(N_SIMULATIONS):
        totals = []
        for p in sim_inputs:
            remaining = sum(rng.normalvariate(p["expected_round_score_to_par"], p["spread"]) for _ in range(REMAINING_ROUNDS))
            totals.append((p["player_id"], p["r1_score_to_par"] + remaining))
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

    records = []
    for p in sim_inputs:
        pid = p["player_id"]
        records.append({
            "player_id": pid,
            "win_probability": round(wins[pid] / N_SIMULATIONS, 6),
            "top5_probability": round(top5[pid] / N_SIMULATIONS, 6),
            "top10_probability": round(top10[pid] / N_SIMULATIONS, 6),
            "top20_probability": round(top20[pid] / N_SIMULATIONS, 6),
            "r1_score_to_par": p["r1_score_to_par"],
            "expected_round_score_to_par": p["expected_round_score_to_par"],
            "spread": round(p["spread"], 4),
            "spread_source": p["spread_source"],
        })

    out = {
        "artifact": "iceberg_2026100003_post_r1_forecast_v2",
        "game_code": GAME_CODE,
        "source_round": 1,
        "method": "Monte Carlo (same mechanics as klpga.neo_win.round_update_r2/r3, applied post-R1): "
                  "real R1 score + remaining_rounds drawn from Normal(BASE, spread), ranked across the field.",
        "sg_adjustment_applied": sg_adjustment_applied,
        "sg_adjustment_walk_forward_result": {
            "source_file": str(WALK_FORWARD_PATH.relative_to(ROOT.parent)),
            "r1sg_beats_base": walk_forward.get("r1sg_beats_base"),
            "event_wins": walk_forward.get("event_wins"),
            "per_model_mae": {k: v.get("mae") for k, v in walk_forward.get("per_model", {}).items()},
        },
        "cut_gating_applied": False,
        "cut_gating_reason": "official cut rule unconfirmed (expectCutRank=0) and no cut has occurred at R1",
        "remaining_rounds": REMAINING_ROUNDS,
        "n_simulations": N_SIMULATIONS,
        "random_seed": RANDOM_SEED,
        "base_feature_source": str(M4_CANDIDATE_PATH.relative_to(ROOT.parent)) + "#records[].features.prior_avg_round_to_par",
        "spread_source": f"klpga_pipeline/data/klpga.sqlite player_round (own stdev if >= {MIN_PERSONAL_ROUNDS_FOR_OWN_SPREAD} real rounds, else population pstdev={round(pop_spread, 4)})",
        "excluded": excluded,
        "records": records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Monotonicity + sanity checks
    problems = []
    for r in records:
        if not (r["win_probability"] <= r["top5_probability"] <= r["top10_probability"] <= r["top20_probability"] <= 1.0 + 1e-9):
            problems.append(r["player_id"])
    prob_sum_win = sum(r["win_probability"] for r in records)

    print(json.dumps({
        "written": str(OUT_PATH),
        "simulated_players": len(records),
        "excluded": len(excluded),
        "excluded_detail": excluded,
        "monotonicity_problems": problems,
        "monotonicity_pass": len(problems) == 0,
        "win_probability_sum": round(prob_sum_win, 4),
        "sg_adjustment_applied": sg_adjustment_applied,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
