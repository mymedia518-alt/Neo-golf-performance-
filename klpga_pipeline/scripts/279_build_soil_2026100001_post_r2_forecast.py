"""Post-R2 (confirmed cut) probability forecast for 제20회 S-OIL
챔피언십 (game_code 2026100001) -- the next stage after scripts/276's
PRE-stage SG candidate, built the same way the repo's own POST_R1 work
for this tournament already did (see SOIL_2026100001_POST_R1_SG_HISTORY_
CANDIDATE_V1.json on research/soil-2026100001-r1-sg-recheck: "Fix the
actual R1 score, simulate R2-R4 scores from negative simulated SG,
apply the cut after R2 at 60 plus ties" -- same engine
(klpga.neo_win.sg_pre_v1), same recency/shrinkage constants, same
60,000-simulation count), with ONE change required by this stage: the
36-hole cut is now a REAL, OFFICIALLY DETERMINED fact (scripts/278,
68 of 96 survive), not the PRE/POST_R1 stage's "cut_position=60 plus
ties" SIMULATION ASSUMPTION. The cut is therefore never re-simulated
here -- only the 68 real survivors are simulated forward, for the 2
rounds that remain (R3, FR); the 28 real non-survivors get no
simulated outcome at all (not 0.0%, not a probability of any kind --
genuinely not applicable, matching this stage's own public-page
convention of showing '-' for a player who is out of contention).

INPUTS (all real, officially sourced, no estimate standing in for an
official fact):
  - SOIL_2026100001_R2_OFFICIAL_V1.json (scripts/278): real R1+R2
    scores and the real cut determination for all 96 entrants.
  - SOIL_2026100001_R1_SG_OFFICIAL_V1.json: official R1 total SG,
    already collected and committed to research/soil-2026100001-r1-
    sg-recheck (pulled onto this branch unchanged).
  - SOIL_2026100001_R2_SG_OFFICIAL_V1.json: official R2 total SG,
    collected for this task via collect-r3-sg-oneoff.yml (game_code=
    2026100001, round=2) against the real KLPGA strokesGained_detail
    endpoint, then published to collector-output/2026100001-r2 and
    pulled onto this branch unchanged.
  - The same retained 2026-season single-round SG corpus (11 prior
    events, 3882 rows) klpga.neo_win.sg_pre_v1.load_2026_sg_round_
    history() already loads for the PRE-stage candidate -- unchanged,
    re-read here, not copied.

Both R1 and R2's own official SG rows are added to each player's prior
-round history before estimating their post-R2 mean/variance for the
two rounds that remain -- this is the SAME recency-weighted formula
scripts/276 already uses (estimate_player_sg_forecasts, unmodified),
simply given more real rows to weight, exactly as the already-published
POST_R1 candidate already did for its own one-round update.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.neo_win.sg_pre_v1 import (  # noqa: E402
    DEFAULT_SIMULATIONS,
    SG_HALF_LIFE_DAYS,
    SG_PRIOR_ROUNDS,
    SG_VOLATILITY_PRIOR_DF,
    PlayerSGForecast,
    estimate_player_sg_forecasts,
    load_2026_sg_round_history,
)

GAME_CODE = "2026100001"
CONTENT = ROOT / "content" / "website_v2"
R2_OFFICIAL_PATH = CONTENT / f"SOIL_{GAME_CODE}_R2_OFFICIAL_V1.json"
R1_SG_PATH = CONTENT / f"SOIL_{GAME_CODE}_R1_SG_OFFICIAL_V1.json"
R2_SG_PATH = CONTENT / f"SOIL_{GAME_CODE}_R2_SG_OFFICIAL_V1.json"
OUT_PATH = CONTENT / f"SOIL_{GAME_CODE}_POST_R2_FORECAST_V1.json"

REMAINING_ROUNDS = 2  # R3 + FR -- R1 and R2 are both now real, known totals
R1_DATE = "2026-10-29"
R2_DATE = "2026-10-30"


def _round_to_integer_strokes(value: float) -> int:
    """Identical half-away-from-zero rounding to sg_pre_v1.py's own
    private _round_to_integer_strokes -- re-stated here, not imported
    across a module boundary by its underscore-prefixed name, so this
    script stays self-contained (same convention 242/254 already used:
    "ported line-for-line", never a new, unvalidated formula)."""
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _load_own_round_sg(path: Path, round_number: int, round_date: str) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for r in doc["records"]:
        if r.get("total") is None or not r.get("player_id"):
            continue
        rows.append({
            "player_id": str(r["player_id"]),
            "total": float(r["total"]),
            "game_code": GAME_CODE,
            "round": round_number,
            "scope": "single_round",
            "date": round_date,
            "season": 2026,
        })
    return rows


def simulate_remaining_rounds(
    known_totals: dict[str, int],
    forecasts: dict[str, PlayerSGForecast],
    *,
    remaining_rounds: int,
    n_simulations: int,
    seed: int,
) -> dict[str, dict[str, float]]:
    """Simulate ONLY the rounds that have not been played yet, for a
    FIXED, already-real field (real cutmakers only -- no cut step).
    Mechanically identical per-round draw to sg_pre_v1.simulate_sg_
    tournament_outcomes (same _round_to_integer_strokes(-gauss(mean_sg,
    round_sd)) draw), just added onto each player's real known total
    instead of simulating every round from scratch."""
    players = sorted(known_totals)
    if any(p not in forecasts for p in players):
        missing = [p for p in players if p not in forecasts]
        raise ValueError(f"missing SG forecast for real cutmaker(s): {missing}")
    rng = random.Random(seed)
    counts = {p: [0, 0, 0, 0] for p in players}  # top20, top10, top5, win
    for _ in range(n_simulations):
        totals = {}
        for p in players:
            f = forecasts[p]
            remaining = sum(_round_to_integer_strokes(-rng.gauss(f.mean_sg, f.round_sd)) for _ in range(remaining_rounds))
            totals[p] = known_totals[p] + remaining
        best = min(totals.values())
        winners = [p for p in players if totals[p] == best]
        for p in players:
            rank = 1 + sum(score < totals[p] for score in totals.values())
            counts[p][0] += rank <= 20
            counts[p][1] += rank <= 10
            counts[p][2] += rank <= 5
            if totals[p] == best:
                counts[p][3] += 1.0 / len(winners)
    return {
        p: {
            "top20_probability": counts[p][0] / n_simulations,
            "top10_probability": counts[p][1] / n_simulations,
            "top5_probability": counts[p][2] / n_simulations,
            "win_probability": counts[p][3] / n_simulations,
        }
        for p in players
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff-date", default="2026-10-31", help="exclusive cutoff for SG history (R3's own date)")
    parser.add_argument("--simulations", type=int, default=DEFAULT_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=20261030)
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    date.fromisoformat(args.cutoff_date)

    r2_official = json.loads(R2_OFFICIAL_PATH.read_text(encoding="utf-8"))
    official_records = r2_official["records"]
    assert len(official_records) == 96
    assert r2_official["made_cut_counts"]["made_cut_true"] + r2_official["made_cut_counts"]["made_cut_false"] == 96
    by_id = {r["player_id"]: r for r in official_records}
    cutmaker_ids = [r["player_id"] for r in official_records if r["made_cut"]]
    non_cutmaker_ids = [r["player_id"] for r in official_records if not r["made_cut"]]
    assert len(cutmaker_ids) == r2_official["made_cut_counts"]["made_cut_true"]

    if not R2_SG_PATH.is_file():
        print(json.dumps({
            "status": "BLOCKED_INCOMPLETE_SG",
            "reason": f"{R2_SG_PATH.name} does not exist -- official R2 Strokes Gained has not been collected. "
                       "Refusing to compute post-R2 probabilities without it (SG is the model's only performance signal).",
        }, ensure_ascii=False, indent=2))
        return 1

    base_history, base_summary = load_2026_sg_round_history(CONTENT)
    own_r1 = _load_own_round_sg(R1_SG_PATH, 1, R1_DATE)
    own_r2 = _load_own_round_sg(R2_SG_PATH, 2, R2_DATE)
    assert len(own_r1) == 96, f"expected 96 official R1 SG rows, found {len(own_r1)}"
    assert len(own_r2) == 96, f"expected 96 official R2 SG rows, found {len(own_r2)}"
    combined_history = base_history + own_r1 + own_r2

    forecasts = estimate_player_sg_forecasts(
        cutmaker_ids,
        combined_history,
        cutoff_date=args.cutoff_date,
        half_life_days=SG_HALF_LIFE_DAYS,
        prior_rounds=SG_PRIOR_ROUNDS,
        volatility_prior_df=SG_VOLATILITY_PRIOR_DF,
    )

    known_totals = {pid: by_id[pid]["total_score"] for pid in cutmaker_ids}
    outcomes = simulate_remaining_rounds(
        known_totals, forecasts,
        remaining_rounds=REMAINING_ROUNDS,
        n_simulations=args.simulations,
        seed=args.seed,
    )

    cutmaker_records = []
    for pid in sorted(cutmaker_ids, key=lambda p: known_totals[p]):
        f = forecasts[pid]
        row = by_id[pid]
        cutmaker_records.append({
            "player_id": pid,
            "player_name": row["player_name"],
            "made_cut": True,
            "r1_score": row["r1_score"],
            "r2_score": row["r2_score"],
            "known_total_score": known_totals[pid],
            "known_score_to_par": row["score_to_par"],
            "analysis_status": "PASS" if f.has_player_sg else "DATA_INSUFFICIENT",
            "top20_probability": outcomes[pid]["top20_probability"],
            "top10_probability": outcomes[pid]["top10_probability"],
            "top5_probability": outcomes[pid]["top5_probability"],
            "win_probability": outcomes[pid]["win_probability"],
            "sg_features": {
                "prior_sg_rounds": f.rounds,
                "prior_sg_events": f.events,
                "prior_sg_effective_rounds": round(f.effective_rounds, 4),
                "prior_sg_mean_shrunk": round(f.mean_sg, 6),
                "round_sd": round(f.round_sd, 6),
                "latest_sg_date": f.latest_sg_date,
            },
        })

    non_cutmaker_records = [
        {
            "player_id": pid,
            "player_name": by_id[pid]["player_name"],
            "made_cut": False,
            "r1_score": by_id[pid]["r1_score"],
            "r2_score": by_id[pid]["r2_score"],
            "known_total_score": by_id[pid]["total_score"],
            "known_score_to_par": by_id[pid]["score_to_par"],
        }
        for pid in non_cutmaker_ids
    ]

    problems = []
    for r in cutmaker_records:
        vals = [r["top20_probability"], r["top10_probability"], r["top5_probability"], r["win_probability"]]
        if not all(vals[i] >= vals[i + 1] - 1e-9 for i in range(len(vals) - 1)):
            problems.append(r["player_id"])
    win_sum = sum(r["win_probability"] for r in cutmaker_records)
    data_insufficient = [r["player_id"] for r in cutmaker_records if r["analysis_status"] == "DATA_INSUFFICIENT"]

    out = {
        "schema_version": "SOIL_2026100001_POST_R2_FORECAST_V1",
        "game_code": GAME_CODE,
        "stage": "POST_R2",
        "tournament_name": "제20회 S-OIL 챔피언십",
        "publication_status": "EXPLORATORY_NOT_VALIDATED_FOR_PUBLICATION",
        "cut_gating": {
            "method": "scripts/278 -- real official cut (R3 field-listing subset), not a simulated probability",
            "cutmakers": len(cutmaker_ids),
            "non_cutmakers": len(non_cutmaker_ids),
        },
        "method": {
            "recency_half_life_days": SG_HALF_LIFE_DAYS,
            "prior_equivalent_rounds": SG_PRIOR_ROUNDS,
            "volatility_prior_degrees_of_freedom": SG_VOLATILITY_PRIOR_DF,
            "forecast": "Use all prior single-round total SG rows plus this tournament's own real R1 and R2 SG rows "
                        "to estimate each real cutmaker's updated round-level SG mean and variance. Fix the real "
                        "R1+R2 total; simulate R3+FR (2 remaining rounds) from negative simulated SG; rank among "
                        "real cutmakers only -- the cut itself is never re-simulated.",
            "remaining_rounds": REMAINING_ROUNDS,
            "simulations": args.simulations,
            "random_seed": args.seed,
        },
        "sg_cutoff_exclusive": args.cutoff_date,
        "sg_source_summary": {
            "base_2026_season_corpus": base_summary,
            "own_r1_sg_rows": len(own_r1),
            "own_r2_sg_rows": len(own_r2),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {
            str(p.relative_to(ROOT)): sha256(p)
            for p in sorted([R2_OFFICIAL_PATH, R1_SG_PATH, R2_SG_PATH])
        },
        "validation": {
            "field_count_matches_official": len(cutmaker_records) + len(non_cutmaker_records) == 96,
            "nesting_monotonicity_violations": problems,
            "nesting_monotonicity_pass": len(problems) == 0,
            "win_probability_sum_over_cutmakers": round(win_sum, 6),
            "win_probability_sum_within_tolerance": abs(win_sum - 1.0) < 1e-6,
            "data_insufficient_cutmakers": data_insufficient,
        },
        "cutmaker_records": cutmaker_records,
        "non_cutmaker_records": non_cutmaker_records,
    }
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "written",
        "path": str(args.output),
        "cutmakers_simulated": len(cutmaker_records),
        "non_cutmakers": len(non_cutmaker_records),
        "nesting_monotonicity_pass": len(problems) == 0,
        "win_probability_sum": round(win_sum, 6),
        "data_insufficient_cutmakers": data_insufficient,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
