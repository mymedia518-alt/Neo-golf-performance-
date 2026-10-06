"""NEO HJ 2026 Stableford three-winner pre-event profile validation --
analyze the official season-stat evidence acquired by
scripts/210_acquire_official_season_stats.py on a machine with real
klpga.co.kr access (evidence/stableford_official_stats_<year>/
ACQUISITION_REPORT.json, already committed to neo-website-v2).

CRITICAL FINDING THIS SCRIPT SURFACES (do not silently average over
it): the "last_pre_cutoff_game_code"-scoped publicRecordSeasonDetail
call does NOT return a season-to-date cumulative value. It returns
stats for that SINGLE tournament only. Evidence: 라운드수 (rounds) in
the returned average_score detail is 1-4 for every one of the
102/103/102 acquired players in all three years (2023/2024/2025),
matching a single KLPGA event's round count, never a season total
(the winners' own independently-reconstructed pre-cutoff season round
counts are 52/62/32). The temporal-safety cross-check built into
script 210 (returned_rounds <= expected_pre_cutoff_rounds_total) still
reports SOURCE_EXISTS_AND_ACQUIRED for these, because it only guards
against OVER-counting (post-cutoff leakage into the call) -- a 1-4
round single-event return is trivially <= a 32-62 round season total,
so the guard passes even though the value is not the cumulative
statistic this report needs.

This means: Driving Distance / Fairway Accuracy / GIR, as acquired,
are REAL, OFFICIAL, and TEMPORALLY SAFE (zero leakage -- the single
tournament used is confirmed pre-cutoff), but describe only the
player's LAST pre-cutoff tournament (2-4 rounds), not her full
pre-cutoff season (32-62 rounds) -- a completely different sample
scope than every other metric in this report. They are reported here
for transparency (real value + real field percentile within this same
single-tournament scope), but are classified INCONCLUSIVE rather than
CORE/SUPPORTING/REJECTED, because the scope mismatch breaks this
report's own metric-definition-consistency and sample-size Red Team
rules.

A genuine season-cumulative reconstruction would require summing this
same endpoint's numerator/denominator pairs across EVERY pre-cutoff
tournament gameCode per player (17/19/9 per winner, already known from
the existing STABLEFORD_<year>_PRIOR_TOURNAMENT_MANIFEST_V1.json
files) -- a materially larger acquisition (thousands of calls across
the full field), not run this turn.
"""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent

WINNERS = {"2023": ("방신실", "10095"), "2024": ("김민별", "10002"), "2025": ("김민솔", "10725")}
METRICS = ["driving_distance", "fairway_accuracy", "gir", "average_score", "par5_scoring"]
LOWER_IS_BETTER = {"average_score", "par5_scoring"}


def load_acquired(year: str) -> dict:
    path = KLPGA_PIPELINE_ROOT / "evidence" / f"stableford_official_stats_{year}" / "ACQUISITION_REPORT.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {r["player_code"]: r for r in data["results"] if r.get("status") == "SOURCE_EXISTS_AND_ACQUIRED"}


def field_values_for_metric(acquired: dict, metric: str) -> list[float]:
    values = []
    for r in acquired.values():
        m = r["metrics"].get(metric)
        if m and m.get("value") is not None:
            values.append(m["value"])
    return values


def percentile_of(value: float, field_values: list[float], lower_is_better: bool) -> float:
    n = len(field_values)
    if lower_is_better:
        better_or_equal = sum(1 for v in field_values if v >= value)
    else:
        better_or_equal = sum(1 for v in field_values if v <= value)
    return round(100.0 * better_or_equal / n, 2)


def rounds_scope_check(acquired: dict) -> dict:
    """Confirms, for a given year's acquired set, that every player's
    last_pre_cutoff_game_code call returned a single-tournament round
    count (1-4), never a season total -- the scoping finding above."""
    rounds = []
    for r in acquired.values():
        m = r["metrics"]["average_score"]
        if m and m.get("detail") and m["detail"].get("라운드수") is not None:
            rounds.append(int(float(m["detail"]["라운드수"])))
    return {"n": len(rounds), "min": min(rounds), "max": max(rounds), "median": median(rounds)}


def winner_metric_report(year: str) -> dict:
    winner_name, winner_code = WINNERS[year]
    acquired = load_acquired(year)
    scope = rounds_scope_check(acquired)
    winner = acquired.get(winner_code)
    out = {"year": year, "winner": winner_name, "field_n": len(acquired),
           "single_tournament_scope_check": scope, "metrics": {}}
    for metric in METRICS:
        m = winner["metrics"][metric]
        if not m or m.get("value") is None:
            out["metrics"][metric] = None
            continue
        field_vals = field_values_for_metric(acquired, metric)
        pct = percentile_of(m["value"], field_vals, metric in LOWER_IS_BETTER)
        out["metrics"][metric] = {"value": m["value"], "detail": m.get("detail"),
                                   "field_n": len(field_vals), "percentile": pct}
    return out


def main() -> int:
    for year in ("2023", "2024", "2025"):
        report = winner_metric_report(year)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
