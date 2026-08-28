"""BETA #001 R2 FROZEN FORECAST — Section N. Builds the frozen,
publishable-later TOP20/TOP10/TOP5/WIN forecast for the tournament
state at the END OF ROUND 2, restricted to the real, double-verified
Round 3 continuers only (klpga.neo_win.ground_truth_diagnostic).

======================================================================
NO NEW MODEL LOGIC — REUSES klpga.neo_win.round_update_r2 VERBATIM
======================================================================
This module never simulates anything itself. `simulate_post_round2`
already computes win_pct/top5_pct/top10_pct/top20_pct/make_cut_pct per
player via the SAME already-validated Monte Carlo mechanics BETA #001
uses post-R1 (Normal-distributed remaining-round draws from the frozen
PRE prior, no new weights, no shrinkage change). This module only:
  (a) restricts the simulation's input population to exactly the real
      confirmed Round 3 continuers (via `made_cut_by_player`, so
      anyone NOT in that set is excluded from `simulate_post_round2`'s
      own "missing" path — the same real, already-established
      exclusion mechanism, not a new one), and
  (b) shapes the real result into report/CSV rows and validates it.

Round 3 has not started: `simulate_post_round2` only ever draws R3 and
R4 as future, unobserved rounds — real Round 1 + Round 2 scores are
fixed inputs, never simulated. No Round 3 information (once it exists)
may ever be fed into this module's inputs; the caller is responsible
for collecting ONLY real, completed Round 1/Round 2 data.
"""
from __future__ import annotations

import csv
from pathlib import Path

from klpga.neo_win.ground_truth_diagnostic import GroundTruthRow
from klpga.neo_win.round_reconciliation import NormalizedPlayer

_CSV_FIELDNAMES: tuple[str, ...] = (
    "player_code", "player_name", "r2_rank", "r2_total_score",
    "top20_pct", "top10_pct", "top5_pct", "win_pct",
)


def build_r2_forecast_rows(
    ground_truth_rows: list[GroundTruthRow],
    sim_result: dict[str, dict],
    official_r2_normalized: dict[str, NormalizedPlayer],
) -> list[dict]:
    """One row per player in `sim_result` — NEVER more, never fewer
    (see module docstring: `sim_result`'s own keys ARE the real,
    confirmed simulation population). Real R2 rank/total score come
    from the ground truth row's own raw fields (already the real,
    parsed PlayerRoundRow data); win/topN percentages come straight
    from `sim_result`, rounded to 2 decimal places for display only —
    never recomputed. Sorted by (real R2 numeric rank, R2 total
    score), per spec."""
    gt_by_code = {g.player_code: g for g in ground_truth_rows}
    rows = []
    for code, sim in sim_result.items():
        g = gt_by_code.get(code)
        o = official_r2_normalized.get(code)
        rank_display = (g.r2_raw_rank if g else None) or (o.position_display if o else None)
        rank_sort = o.position if (o is not None and o.position is not None) else 10**9
        total_score = g.r2_total_score if g else None
        rows.append(
            {
                "player_code": code,
                "player_name": (g.official_name if g else None) or (o.player_name if o else None) or "",
                "r2_rank": rank_display,
                "_r2_rank_sort": rank_sort,
                "r2_total_score": total_score,
                "top20_pct": round(sim["top20_pct"], 2),
                "top10_pct": round(sim["top10_pct"], 2),
                "top5_pct": round(sim["top5_pct"], 2),
                "win_pct": round(sim["win_pct"], 2),
            }
        )
    rows.sort(key=lambda r: (r["_r2_rank_sort"], r["r2_total_score"] if r["r2_total_score"] is not None else 10**9))
    for r in rows:
        del r["_r2_rank_sort"]
    return rows


def write_r2_forecast_csv(rows: list[dict], out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in _CSV_FIELDNAMES})
    return out_path


def check_forecast_population_matches_confirmed_continuers(
    sim_result: dict[str, dict], confirmed_continuer_codes: set[str]
) -> dict:
    """The hard gate: the simulated population must be EXACTLY the
    real confirmed Round 3 continuers — never a superset (a WD/DQ/
    missed-cut/pre-R1-unavailable/unresolved player slipping in) and
    never a subset (a real continuer silently dropped)."""
    actual = set(sim_result.keys())
    passed = actual == confirmed_continuer_codes
    return {
        "check": "FORECAST_POPULATION_MATCHES_CONFIRMED_CONTINUERS",
        "passed": passed,
        "detail": f"expected_only={sorted(confirmed_continuer_codes - actual)} actual_only={sorted(actual - confirmed_continuer_codes)}",
    }


def check_probability_monotonicity(sim_result: dict[str, dict]) -> dict:
    """For every player: WIN <= TOP5 <= TOP10 <= TOP20. Checked against
    simulate_post_round2's own full-precision output (before the 2dp
    display rounding build_r2_forecast_rows applies), so a rounding
    artifact can never cause a false failure."""
    bad = [
        code for code, s in sim_result.items()
        if not (s["win_pct"] <= s["top5_pct"] <= s["top10_pct"] <= s["top20_pct"])
    ]
    return {
        "check": "PROBABILITY_MONOTONICITY_WIN_LE_TOP5_LE_TOP10_LE_TOP20",
        "passed": len(bad) == 0,
        "detail": f"bad={bad}",
    }


def check_win_sum_approximately_100(sim_result: dict[str, dict], tolerance: float = 1.0) -> dict:
    total = sum(s["win_pct"] for s in sim_result.values())
    passed = (not sim_result) or abs(total - 100.0) <= tolerance
    return {"check": "WIN_PCT_SUM_APPROXIMATELY_100", "passed": passed, "detail": f"sum={total}"}
