"""Post-R3 probability forecast for 제20회 S-OIL 챔피언십 (game_code
2026100001) -- the next stage after scripts/279's post-R2 forecast, same
engine (klpga.neo_win.sg_pre_v1), same methodology, one round later:
only FR (the final round) remains unplayed now, so this simulates 1
remaining round instead of 2, fixed onto each real cutmaker's real,
official R1+R2+R3 total (scripts/282) -- no cut is re-simulated (there
is none left to simulate; the field is fixed at 68, confirmed by
scripts/282 against both the R3 and R4 raw pages).

INPUTS (all real, officially sourced):
  - SOIL_2026100001_R3_OFFICIAL_V1.json (scripts/282): real R1+R2+R3
    scores for the 68 real cutmakers.
  - SOIL_2026100001_R1_SG_OFFICIAL_V1.json / _R2_SG_OFFICIAL_V1.json:
    already collected and reused unchanged (same files scripts/279
    used).
  - SOIL_2026100001_R3_SG_OFFICIAL_V1.json: official R3 total SG,
    collected for this task via collect-r3-sg-oneoff.yml (game_code=
    2026100001, round=3) against the real KLPGA strokesGained_detail
    endpoint, published to collector-output/2026100001-r3, pulled onto
    this branch unchanged.
  - The same retained 2026-season single-round SG corpus
    load_2026_sg_round_history() already loads -- unchanged, re-read.

All three of this tournament's own official SG rows (R1, R2, R3) are
added to each of the 68 real cutmakers' prior-round history before
estimating their post-R3 mean/variance for the one round that remains --
the same recency-weighted formula (estimate_player_sg_forecasts,
unmodified) scripts/276 and 279 already use, simply given one more real
row to weight.
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
R3_OFFICIAL_PATH = CONTENT / f"SOIL_{GAME_CODE}_R3_OFFICIAL_V1.json"
R1_SG_PATH = CONTENT / f"SOIL_{GAME_CODE}_R1_SG_OFFICIAL_V1.json"
R2_SG_PATH = CONTENT / f"SOIL_{GAME_CODE}_R2_SG_OFFICIAL_V1.json"
R3_SG_PATH = CONTENT / f"SOIL_{GAME_CODE}_R3_SG_OFFICIAL_V1.json"
OUT_PATH = CONTENT / f"SOIL_{GAME_CODE}_POST_R3_FORECAST_V1.json"

REMAINING_ROUNDS = 1  # FR only -- R1, R2, and R3 are all now real, known totals
R1_DATE = "2026-10-29"
R2_DATE = "2026-10-30"
R3_DATE = "2026-10-31"


def _round_to_integer_strokes(value: float) -> int:
    """Identical half-away-from-zero rounding to sg_pre_v1.py's own
    private _round_to_integer_strokes -- re-stated here, not imported
    across a module boundary by its underscore-prefixed name (same
    convention scripts/242/254/279 already use)."""
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
    """Simulate ONLY the round that has not been played yet (FR), for a
    fixed, already-real field of 68. Mechanically identical per-round
    draw to scripts/279's own simulate_remaining_rounds."""
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
    parser.add_argument("--cutoff-date", default="2026-11-01", help="exclusive cutoff for SG history (FR's own date)")
    parser.add_argument("--simulations", type=int, default=DEFAULT_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=20261031)
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    date.fromisoformat(args.cutoff_date)

    r3_official = json.loads(R3_OFFICIAL_PATH.read_text(encoding="utf-8"))
    official_records = r3_official["records"]
    assert r3_official["field_count"] == 68
    assert len(official_records) == 68
    by_id = {r["player_id"]: r for r in official_records}
    field_ids = list(by_id)

    if not R3_SG_PATH.is_file():
        print(json.dumps({
            "status": "BLOCKED_INCOMPLETE_SG",
            "reason": f"{R3_SG_PATH.name} does not exist -- official R3 Strokes Gained has not been collected. "
                       "Refusing to compute post-R3 probabilities without it (SG is the model's only performance signal).",
        }, ensure_ascii=False, indent=2))
        return 1

    base_history, base_summary = load_2026_sg_round_history(CONTENT)
    own_r1 = _load_own_round_sg(R1_SG_PATH, 1, R1_DATE)
    own_r2 = _load_own_round_sg(R2_SG_PATH, 2, R2_DATE)
    own_r3 = _load_own_round_sg(R3_SG_PATH, 3, R3_DATE)
    assert len(own_r1) == 96, f"expected 96 official R1 SG rows, found {len(own_r1)}"
    assert len(own_r2) == 96, f"expected 96 official R2 SG rows, found {len(own_r2)}"
    assert len(own_r3) == 68, f"expected 68 official R3 SG rows, found {len(own_r3)}"
    combined_history = base_history + own_r1 + own_r2 + own_r3

    forecasts = estimate_player_sg_forecasts(
        field_ids,
        combined_history,
        cutoff_date=args.cutoff_date,
        half_life_days=SG_HALF_LIFE_DAYS,
        prior_rounds=SG_PRIOR_ROUNDS,
        volatility_prior_df=SG_VOLATILITY_PRIOR_DF,
    )

    known_totals = {pid: by_id[pid]["total_score"] for pid in field_ids}
    outcomes = simulate_remaining_rounds(
        known_totals, forecasts,
        remaining_rounds=REMAINING_ROUNDS,
        n_simulations=args.simulations,
        seed=args.seed,
    )

    field_records = []
    for pid in sorted(field_ids, key=lambda p: known_totals[p]):
        f = forecasts[pid]
        row = by_id[pid]
        field_records.append({
            "player_id": pid,
            "player_name": row["player_name"],
            "r1_score": row["r1_score"],
            "r2_score": row["r2_score"],
            "r3_score": row["r3_score"],
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

    problems = []
    for r in field_records:
        vals = [r["top20_probability"], r["top10_probability"], r["top5_probability"], r["win_probability"]]
        if not all(vals[i] >= vals[i + 1] - 1e-9 for i in range(len(vals) - 1)):
            problems.append(r["player_id"])
    win_sum = sum(r["win_probability"] for r in field_records)
    data_insufficient = [r["player_id"] for r in field_records if r["analysis_status"] == "DATA_INSUFFICIENT"]

    out = {
        "schema_version": "SOIL_2026100001_POST_R3_FORECAST_V1",
        "game_code": GAME_CODE,
        "stage": "POST_R3",
        "tournament_name": "제20회 S-OIL 챔피언십",
        "field_gating": {
            "method": "scripts/282 -- real official R3 field (68, no second cut, confirmed against R3+R4 raw pages)",
            "field_count": len(field_ids),
        },
        "method": {
            "recency_half_life_days": SG_HALF_LIFE_DAYS,
            "prior_equivalent_rounds": SG_PRIOR_ROUNDS,
            "volatility_prior_degrees_of_freedom": SG_VOLATILITY_PRIOR_DF,
            "forecast": "Use all prior single-round total SG rows plus this tournament's own real R1, R2 and R3 SG "
                        "rows to estimate each real R3 player's updated round-level SG mean and variance. Fix the "
                        "real R1+R2+R3 total; simulate FR (1 remaining round) from negative simulated SG; rank "
                        "among the real 68-player field only.",
            "remaining_rounds": REMAINING_ROUNDS,
            "simulations": args.simulations,
            "random_seed": args.seed,
        },
        "sg_cutoff_exclusive": args.cutoff_date,
        "sg_source_summary": {
            "base_2026_season_corpus": base_summary,
            "own_r1_sg_rows": len(own_r1),
            "own_r2_sg_rows": len(own_r2),
            "own_r3_sg_rows": len(own_r3),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_hashes": {
            str(p.relative_to(ROOT)): sha256(p)
            for p in sorted([R3_OFFICIAL_PATH, R1_SG_PATH, R2_SG_PATH, R3_SG_PATH])
        },
        "validation": {
            "field_count_matches_official": len(field_records) == 68,
            "nesting_monotonicity_violations": problems,
            "nesting_monotonicity_pass": len(problems) == 0,
            "win_probability_sum_over_field": round(win_sum, 6),
            "win_probability_sum_within_tolerance": abs(win_sum - 1.0) < 1e-6,
            "data_insufficient_players": data_insufficient,
        },
        "field_records": field_records,
    }
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "written",
        "path": str(args.output),
        "field_simulated": len(field_records),
        "nesting_monotonicity_pass": len(problems) == 0,
        "win_probability_sum": round(win_sum, 6),
        "data_insufficient_players": data_insufficient,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
