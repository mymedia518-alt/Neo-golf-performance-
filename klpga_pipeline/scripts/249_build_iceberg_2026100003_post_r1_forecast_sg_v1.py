"""SG-ADJUSTED post-R1 probability forecast for 아이스버그골프·서울신문
오픈 (game_code 2026100003) -- produces win/TOP5/TOP10/TOP20 using BOTH
the real R1 score AND the real official R1 Strokes Gained, alongside the
already-shipped BASE-only forecast (scripts/247's
ICEBERG_2026100003_POST_R1_FORECAST_V2.json), for a side-by-side
before/after comparison. Operator instruction, 2026-10-16: "SG를 수집하고도
계산에서 제외하는 결과로 끝내지 마" -- this script is the required
follow-through: the R1SG walk-forward model (scripts/246, refit here from
the same repo-committed historical data) is actually used as simulation
input, not archived and left unused.

======================================================================
WALK-FORWARD RESULT THIS SCRIPT USES (re-read, not copied by hand)
======================================================================
scripts/246 fits two nested OLS models on 9 real historical 2026-season
events (10 HISTORICAL_CODES configured, 1 -- 2026070002 -- produced zero
matched rows and drops out before n_events is even counted; walk-forward
then evaluates 8 of those 9 strictly-prior-trained events, skipping
2026070002 again for insufficient prior training rows):
  BASE:  predicted_R2_to_par = b0 + b1*prior_avg_round_to_par
  R1SG:  predicted_R2_to_par = b0 + b1*prior_avg_round_to_par + b2*r1_sg_total
Result: r1sg_beats_base=False (event_wins tied 4-4 across the 8 evaluated
events; R1SG's pooled MAE improvement over BASE is 0.0035 strokes,
2.5446 -> 2.5411 -- not a real signal by either criterion). The R1SG
model is NOT shown as more accurate than BASE; it is shown anyway, as a
labeled alternative, per the operator instruction above.

======================================================================
WHAT "SG-ADJUSTED" MEANS HERE
======================================================================
Per-player expected_round_score_to_par is recomputed as
R1SG model's own fitted prediction (b0 + b1*BASE + b2*r1_sg_total,
scripts/246's final_coefficients.R1SG, fit on ALL 9 real historical
events together -- this tournament contributes zero rows to that fit,
it is not in HISTORICAL_CODES) instead of scripts/247's plain BASE
value. Applied identically to BOTH remaining rounds (R2, FR) -- the
walk-forward only validates an R1-SG -> R2 relationship, there is no
separately-validated R1-SG -> FR model, so this script extends the
same fitted R2-conditional expectation to FR as its best available
estimate, documented here as a stated assumption, not a second
validated model.

Spread (per-round variance around the expectation) is UNCHANGED from
scripts/247 -- the walk-forward only validates a shift in the mean,
never touches variance, so re-deriving a different spread here would
not be grounded in anything actually tested.

Same N_SIMULATIONS/RANDOM_SEED as scripts/247, for an apples-to-apples
comparison against the already-published BASE-only numbers.

======================================================================
MISSING DATA / CUT PROBABILITY
======================================================================
Same exclusion rule as scripts/247 (no real R1 score, no BASE feature,
or WD -> excluded, never a fabricated average). cut_probability is NOT
touched by this script -- the official cut rule for THIS tournament
(klpga_pipeline/raw/2026100003/game_list.json, totalRound=3,
expectCutRank=0) could not be confirmed (no completed 3-round-format
cut outcome exists anywhere in this repo's historical data to validate
against, and 0 does not reliably mean "no cut" vs "not yet assigned").
Building an SG-adjusted cut classifier on the 10 historical 4-round/
36-hole-cut events and applying it to a 3-round event whose own cut
rule is unconfirmed would mean inventing the very cutline the operator
instruction says not to invent. cut_probability stays the unchanged,
separate frozen PRE model value, exactly as scripts/247 already left it.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.ops.paths import db_path  # noqa: E402
import sqlite3  # noqa: E402

GAME_CODE = "2026100003"
CONTENT = ROOT / "content" / "website_v2"
R1_SG_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_R1_SG_OFFICIAL_V1.json"
BASE_FORECAST_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_POST_R1_FORECAST_V2.json"
WALK_FORWARD_PATH = CONTENT / "R1_PREDICTS_R2_WALK_FORWARD_V1.json"
M4_CANDIDATE_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_PRE_M4_CANDIDATE_V1.json"
OUT_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_POST_R1_FORECAST_SG_V1.json"

N_SIMULATIONS = 60000
RANDOM_SEED = 20261016
REMAINING_ROUNDS = 2
MIN_PERSONAL_ROUNDS_FOR_OWN_SPREAD = 3


def main() -> None:
    walk_forward = json.loads(WALK_FORWARD_PATH.read_text(encoding="utf-8"))
    r1sg_beats_base = bool(walk_forward.get("r1sg_beats_base"))
    coef = walk_forward["final_coefficients"]["R1SG"]
    b0, b1, b2 = coef  # intercept, BASE coefficient, R1SG coefficient

    r1_sg = json.loads(R1_SG_PATH.read_text(encoding="utf-8"))
    sg_by_id: dict[str, float] = {
        r["player_id"]: float(r["total"])
        for r in r1_sg["records"]
        if r.get("player_id") and r.get("total") is not None
    }

    base_forecast = json.loads(BASE_FORECAST_PATH.read_text(encoding="utf-8"))
    base_by_pid: dict[str, dict] = {r["player_id"]: r for r in base_forecast["records"]}

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
    # Carry forward scripts/247's own exclusions (NO_BASE_FEATURE / WD) --
    # base_by_pid only contains the 99 players scripts/247 already
    # simulated, so without this the 9 upstream-excluded players would
    # silently vanish from this script's own excluded-count instead of
    # being visibly accounted for.
    excluded = [dict(e, reason=f"INHERITED_FROM_BASE_FORECAST:{e['reason']}") for e in base_forecast.get("excluded", [])]
    for pid, base_rec in base_by_pid.items():
        r1_sg_total = sg_by_id.get(pid)
        base_feature = base_feature_by_id.get(pid)
        if base_feature is None:
            excluded.append({"player_id": pid, "reason": "NO_BASE_FEATURE"})
            continue
        if r1_sg_total is None:
            excluded.append({"player_id": pid, "reason": "NO_R1_SG"})
            continue
        sg_adjusted_expected = b0 + b1 * base_feature + b2 * r1_sg_total
        spread, spread_source = spread_for(pid)
        sim_inputs.append({
            "player_id": pid,
            "r1_score_to_par": base_rec["r1_score_to_par"],
            "base_only_expected_round_score_to_par": base_rec["expected_round_score_to_par"],
            "sg_adjusted_expected_round_score_to_par": sg_adjusted_expected,
            "r1_sg_total": r1_sg_total,
            "spread": spread,
            "spread_source": spread_source,
        })

    rng = random.Random(RANDOM_SEED)
    wins = {p["player_id"]: 0.0 for p in sim_inputs}
    top5 = {p["player_id"]: 0 for p in sim_inputs}
    top10 = {p["player_id"]: 0 for p in sim_inputs}
    top20 = {p["player_id"]: 0 for p in sim_inputs}

    for _ in range(N_SIMULATIONS):
        totals = []
        for p in sim_inputs:
            remaining = sum(
                rng.normalvariate(p["sg_adjusted_expected_round_score_to_par"], p["spread"])
                for _ in range(REMAINING_ROUNDS)
            )
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
        base_rec = base_by_pid[pid]
        sg_win = round(wins[pid] / N_SIMULATIONS, 6)
        sg_top5 = round(top5[pid] / N_SIMULATIONS, 6)
        sg_top10 = round(top10[pid] / N_SIMULATIONS, 6)
        sg_top20 = round(top20[pid] / N_SIMULATIONS, 6)
        records.append({
            "player_id": pid,
            "r1_score_to_par": p["r1_score_to_par"],
            "r1_sg_total": p["r1_sg_total"],
            "base_only_expected_round_score_to_par": round(p["base_only_expected_round_score_to_par"], 4),
            "sg_adjusted_expected_round_score_to_par": round(p["sg_adjusted_expected_round_score_to_par"], 4),
            "spread": round(p["spread"], 4),
            "spread_source": p["spread_source"],
            "base_only_win_probability": base_rec["win_probability"],
            "base_only_top5_probability": base_rec["top5_probability"],
            "base_only_top10_probability": base_rec["top10_probability"],
            "base_only_top20_probability": base_rec["top20_probability"],
            "sg_adjusted_win_probability": sg_win,
            "sg_adjusted_top5_probability": sg_top5,
            "sg_adjusted_top10_probability": sg_top10,
            "sg_adjusted_top20_probability": sg_top20,
            "win_delta": round(sg_win - base_rec["win_probability"], 6),
            "top5_delta": round(sg_top5 - base_rec["top5_probability"], 6),
            "top10_delta": round(sg_top10 - base_rec["top10_probability"], 6),
            "top20_delta": round(sg_top20 - base_rec["top20_probability"], 6),
        })

    out = {
        "artifact": "iceberg_2026100003_post_r1_forecast_sg_v1",
        "game_code": GAME_CODE,
        "source_round": 1,
        "method": "Monte Carlo (same mechanics as scripts/247's BASE-only forecast): real R1 score + "
                  "remaining_rounds drawn from Normal(R1SG-model-predicted expectation, spread), ranked "
                  "across the field. The R1SG model's expectation = final_coefficients.R1SG applied to "
                  "(prior_avg_round_to_par, real R1 Strokes Gained total).",
        "walk_forward_source": str(WALK_FORWARD_PATH.relative_to(ROOT.parent)),
        "walk_forward_r1sg_beats_base": r1sg_beats_base,
        "walk_forward_disclosure": (
            "R1SG model does NOT outperform the BASE-only model in walk-forward validation "
            "(event_wins tied 4-4 across 8 evaluated historical events, pooled MAE improvement "
            "0.0035 strokes) -- the numbers below are a labeled alternative calculation, not a "
            "validated improvement over the already-published BASE-only forecast."
        ),
        "fitted_coefficients_R1SG_model": {"intercept": b0, "base_coef": b1, "r1sg_coef": b2},
        "fr_assumption": "same fitted R2-conditional expectation applied to FR (no separately-validated R1SG->FR model exists)",
        "cut_probability_note": "not touched by this script -- official cut rule for this 3-round tournament unconfirmed, see module docstring",
        "cut_gating_applied": False,
        "remaining_rounds": REMAINING_ROUNDS,
        "n_simulations": N_SIMULATIONS,
        "random_seed": RANDOM_SEED,
        "spread_source": f"klpga_pipeline/data/klpga.sqlite player_round (own stdev if >= {MIN_PERSONAL_ROUNDS_FOR_OWN_SPREAD} real rounds, else population pstdev={round(pop_spread, 4)}) -- same as scripts/247, unchanged",
        "excluded": excluded,
        "records": records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    problems = []
    for r in records:
        if not (r["sg_adjusted_win_probability"] <= r["sg_adjusted_top5_probability"] <= r["sg_adjusted_top10_probability"] <= r["sg_adjusted_top20_probability"] <= 1.0 + 1e-9):
            problems.append(r["player_id"])
    win_sum = sum(r["sg_adjusted_win_probability"] for r in records)

    deltas = sorted(records, key=lambda r: abs(r["win_delta"]), reverse=True)[:5]

    print(json.dumps({
        "written": str(OUT_PATH),
        "simulated_players": len(records),
        "excluded": len(excluded),
        "excluded_detail": excluded,
        "monotonicity_problems": problems,
        "monotonicity_pass": len(problems) == 0,
        "win_probability_sum": round(win_sum, 4),
        "r1sg_beats_base": r1sg_beats_base,
        "largest_win_deltas": [{"player_id": r["player_id"], "base": r["base_only_win_probability"], "sg": r["sg_adjusted_win_probability"], "delta": r["win_delta"]} for r in deltas],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
