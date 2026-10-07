"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- Three-Winner DNA
CHECK, a SEPARATE explanatory layer, never blended into Stableford V1.

Per explicit instruction, this does NOT merge the Three-Winner CORE
metrics into V1's net_expected_value, and does NOT invent a new
composite score. It simply asks, per already-validated CORE metric
that is ACTUALLY AVAILABLE for the 2026 field: does this player clear
the same top-25%-of-own-field bar the three historical winners
(방신실/김민별/김민솔) were shown to clear?

Reuses klpga.website_v2.stableford_round_level_profile UNCHANGED
(load_all_round_records / compute_scoring_ceiling_profile /
compute_reconstructed_official_stats) against the already-real 2026
prior-tournament evidence -- the exact same functions already used and
verified for the 2023/2024/2025 three-winner validation, just applied
to a new field.

AVAILABLE CORE metrics for 2026 (no new acquisition needed):
  - avg_birdies_per_round, max_birdies_per_round, sub70_round_rate,
    high_scoring_round_rate (from compute_scoring_ceiling_profile)
  - official Average Score, Par5 scoring (RECONSTRUCTED, from
    compute_reconstructed_official_stats)
  - Birdie+/Bogey+ ratio, Expected Stableford points/hole (from the
    V1 snapshot itself, klpga.website_v2.stableford_2026_preevent)

NOT AVAILABLE for 2026 (disclosed, never fabricated): official GIR,
Driving Distance, SG Total, SG Tee-to-Green -- these require the
publicRecordSeasonDetail season-cumulative reconstruction (scripts
210-214) run against the FULL 2026 field across 24 tournaments, a
materially larger acquisition not undertaken this turn.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.website_v2.stableford_round_level_profile import (  # noqa: E402
    compute_reconstructed_official_stats,
    compute_scoring_ceiling_profile,
    load_all_round_records,
)

CONTENT_ROOT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"
EVIDENCE_ROOT = KLPGA_PIPELINE_ROOT / "evidence"
MANIFEST_PATH = CONTENT_ROOT / "STABLEFORD_2026_PRIOR_TOURNAMENT_MANIFEST_V1.json"
PRIOR_DIR = EVIDENCE_ROOT / "stableford_prior_2026"
V1_SNAPSHOT_PATH = CONTENT_ROOT / "STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1.json"
IDENTITY_PATH = CONTENT_ROOT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"
OUT_PATH = CONTENT_ROOT / "HJ_2026100004_THREE_WINNER_DNA_CHECK_V1.json"

AVAILABLE_METRICS = (
    "avg_birdies_per_round", "max_birdies_per_round", "sub70_round_rate", "high_scoring_round_rate",
    "avg_score", "par5_scoring", "birdie_bogey_plus_ratio", "net_expected_value",
)
MISSING_METRICS = ("official_gir", "driving_distance", "sg_total", "sg_tee_to_green")

LOWER_BETTER = {"avg_score", "par5_scoring"}


def _percentile(value: float, population: list[float], lower_better: bool) -> float:
    n = len(population)
    if lower_better:
        better_or_equal = sum(1 for v in population if v >= value)
    else:
        better_or_equal = sum(1 for v in population if v <= value)
    return round(100.0 * better_or_equal / n, 2)


def build() -> dict:
    by_player = load_all_round_records(MANIFEST_PATH, PRIOR_DIR)
    v1 = json.loads(V1_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    v1_by_name = {r["player_name"]: r for r in v1["records"]}
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    hj_field_names = {r["player_name"] for r in identity["records"]}

    per_player: dict[str, dict] = {}
    for name, rounds in by_player.items():
        if name not in hj_field_names:
            continue  # own-field population only -- same convention as every other metric in this project
        if len(rounds) < 10:  # same pre-declared floor used throughout this session
            continue
        ceiling = compute_scoring_ceiling_profile(name, rounds)
        official = compute_reconstructed_official_stats(name, rounds)
        v1_rec = v1_by_name.get(name)
        bb_ratio = None
        if v1_rec and v1_rec.get("bogey") and v1_rec.get("double_or_worse") is not None:
            bogey_plus = v1_rec["bogey"] + v1_rec["double_or_worse"]
            birdie_plus = v1_rec["birdie"] + v1_rec["eagle"] + v1_rec["albatross"]
            bb_ratio = round(birdie_plus / bogey_plus, 4) if bogey_plus else None
        per_player[name] = {
            "avg_birdies_per_round": ceiling.avg_birdies_per_round,
            "max_birdies_per_round": ceiling.max_birdies_per_round,
            "sub70_round_rate": ceiling.sub70_round_rate,
            "high_scoring_round_rate": ceiling.high_scoring_round_rate,
            "avg_score": official.avg_score,
            "par5_scoring": official.par5_scoring,
            "birdie_bogey_plus_ratio": bb_ratio,
            "net_expected_value": v1_rec["net_expected_value"] if v1_rec else None,
        }

    populations = {
        m: [p[m] for p in per_player.values() if p.get(m) is not None] for m in AVAILABLE_METRICS
    }

    results = {}
    for name, metrics in per_player.items():
        core_met = []
        for m in AVAILABLE_METRICS:
            if metrics.get(m) is None:
                continue
            pct = _percentile(metrics[m], populations[m], m in LOWER_BETTER)
            if pct >= 75.0:
                core_met.append(m)
        results[name] = {
            "metrics": metrics,
            "core_criteria_met": core_met,
            "core_criteria_met_count": len(core_met),
            "core_criteria_available_count": len(AVAILABLE_METRICS),
        }

    return {
        "schema_version": 1,
        "game_code": "2026100004",
        "note": "SEPARATE explanatory layer -- never merged into Stableford V1's net_expected_value. "
                "Reuses the same CORE-metric top-25%-of-own-field rule already validated for the "
                "three historical winners, applied here to the 2026 field only for the metrics "
                "actually available (no new acquisition).",
        "available_metrics": list(AVAILABLE_METRICS),
        "missing_metrics_not_computed": list(MISSING_METRICS),
        "field_n": len(per_player),
        "players": results,
    }


def main() -> int:
    data = build()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    ranked = sorted(data["players"].items(), key=lambda kv: -kv[1]["core_criteria_met_count"])
    print(f"field_n={data['field_n']}  available_metrics={len(AVAILABLE_METRICS)}  "
          f"missing_metrics={MISSING_METRICS}")
    for name, r in ranked[:10]:
        print(f"  {name}: {r['core_criteria_met_count']}/{r['core_criteria_available_count']} -> {r['core_criteria_met']}")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
