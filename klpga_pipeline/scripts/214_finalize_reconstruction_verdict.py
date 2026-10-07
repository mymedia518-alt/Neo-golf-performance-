"""NEO Stableford three-winner pre-event profile validation -- final
verdict step. Reads the real, Windows-acquired season-to-date
cumulative reconstruction (evidence/stableford_official_stats_
reconstructed_<year>/RECONSTRUCTION_REPORT.json, commit eadf36f) and
computes each winner's Driving Distance / Fairway Accuracy / GIR field
rank and percentile, under BOTH the raw (every player with a
reconstructed value) and a sample-qualified (>=10 real pre-cutoff
rounds used) population -- per the explicit instruction that a thin
sample must not be silently mixed into the same percentile population
as a full-season sample without disclosure.

MIN_ROUNDS_QUALIFIED=10 is a pre-declared, round-number generic floor
(not reverse-engineered from the winners, who all sit at 32-62 rounds,
far above it) chosen because no KLPGA-confirmed official eligibility
rule for these stat leaderboards was found in this repo (still an open
question, disclosed in the Red Team). It is applied identically before
looking at how it affects any specific player's percentile."""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
EVIDENCE_ROOT = KLPGA_PIPELINE_ROOT / "evidence"

WINNERS = {"2023": ("방신실", "10095"), "2024": ("김민별", "10002"), "2025": ("김민솔", "10725")}
METRICS = ["driving_distance", "fairway_accuracy", "gir"]
MIN_ROUNDS_QUALIFIED = 10


def load_results(year: str) -> list[dict]:
    path = EVIDENCE_ROOT / f"stableford_official_stats_reconstructed_{year}" / "RECONSTRUCTION_REPORT.json"
    return json.loads(path.read_text(encoding="utf-8"))["results"]


def _percentile_higher_better(value: float, population: list[float]) -> float:
    n = len(population)
    better_or_equal = sum(1 for v in population if v <= value)
    return round(100.0 * better_or_equal / n, 2)


def _rank_higher_better(value: float, population: list[float]) -> int:
    return sorted(population, reverse=True).index(value) + 1


def winner_report(year: str) -> dict:
    winner_name, winner_code = WINNERS[year]
    results = load_results(year)
    by_code = {r["player_code"]: r for r in results}
    winner = by_code[winner_code]

    out = {"year": year, "winner": winner_name, "player_code": winner_code,
           "expected_pre_cutoff_rounds_total": winner["expected_pre_cutoff_rounds_total"], "metrics": {}}

    for metric in METRICS:
        winner_value = winner["reconstructed"][metric]["value"]
        raw_population = [r["reconstructed"][metric]["value"] for r in results
                           if r["reconstructed"][metric]["value"] is not None]
        qualified_population = [r["reconstructed"][metric]["value"] for r in results
                                 if r["reconstructed"][metric]["value"] is not None
                                 and r["expected_pre_cutoff_rounds_total"] >= MIN_ROUNDS_QUALIFIED]
        out["metrics"][metric] = {
            "value": winner_value,
            "raw_field_n": len(raw_population),
            "raw_rank": _rank_higher_better(winner_value, raw_population),
            "raw_percentile": _percentile_higher_better(winner_value, raw_population),
            "qualified_field_n": len(qualified_population),
            "qualified_rank": _rank_higher_better(winner_value, qualified_population),
            "qualified_percentile": _percentile_higher_better(winner_value, qualified_population),
        }
    return out


def main() -> int:
    for year in ("2023", "2024", "2025"):
        print(json.dumps(winner_report(year), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
