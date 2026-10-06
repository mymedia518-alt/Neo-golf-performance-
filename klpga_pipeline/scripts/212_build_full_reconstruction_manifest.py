"""NEO Stableford three-winner pre-event profile validation -- build
the FULL per-tournament reconstruction manifest needed to compute a
true season-to-date cumulative Driving Distance / Fairway Accuracy /
GIR value (not the single-tournament snapshot that
scripts/210_acquire_official_season_stats.py's gameCode scoping
accidentally produced -- see STABLEFORD_THREE_WINNER_PRE_EVENT_PROFILE
_V1.md's "Critical finding").

No new network access. Built entirely from data already on disk:
  - content/website_v2/STABLEFORD_<year>_PRIOR_TOURNAMENT_MANIFEST_V1
    .json -- the 19/23/23 real, already leakage-verified pre-cutoff
    tournament game_codes for each season (every start_date already
    confirmed strictly before that year's target cutoff).
  - evidence/stableford_prior_<year>/<game_code>_scoreRecord.html --
    the real scorecards for those same tournaments, already used for
    every other round-level metric in this report.
  - content/website_v2/STABLEFORD_OFFICIAL_SEASON_STAT_ACQUISITION_
    MANIFEST_V1.json -- the already-resolved, already-tested
    player_name -> player_code mapping (102/103/103 players/year).

For each player, this script finds every pre-cutoff tournament they
ACTUALLY played (at least 1 real 18-hole round in that game_code's
scoreRecord capture) and records the real round count for THAT
SPECIFIC tournament -- the ground truth a new acquisition script uses
as its scope-detection gate: if a `publicRecordSeasonDetail` call for
(player, that one game_code) returns a "라운드수" different from this
real, independently-known count, the gate fails and that tournament's
data must not be trusted or summed.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

from klpga.website_v2.stableford_round_level_profile import load_all_round_records  # noqa: E402

CONTENT_ROOT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"
EVIDENCE_ROOT = KLPGA_PIPELINE_ROOT / "evidence"

YEAR_CONFIG = {
    "2023": ("STABLEFORD_2023_PRIOR_TOURNAMENT_MANIFEST_V1.json", "stableford_prior_2023"),
    "2024": ("STABLEFORD_2024_PRIOR_TOURNAMENT_MANIFEST_V1.json", "stableford_prior_2024"),
    "2025": ("STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json", "stableford_prior_2025"),
}

OUTPUT_PATH = CONTENT_ROOT / "STABLEFORD_OFFICIAL_SEASON_STAT_RECONSTRUCTION_MANIFEST_V1.json"


def build_year(year: str) -> dict:
    manifest_name, prior_name = YEAR_CONFIG[year]
    prior_manifest = json.loads((CONTENT_ROOT / manifest_name).read_text(encoding="utf-8"))
    target_cutoff = prior_manifest.get("target_start_date") or prior_manifest["target_event_start_date"]
    tournaments = [{"game_code": e["game_code"], "start_date": e["start_date"]} for e in prior_manifest["entries"]]

    player_codes = json.loads(
        (CONTENT_ROOT / "STABLEFORD_OFFICIAL_SEASON_STAT_ACQUISITION_MANIFEST_V1.json").read_text(encoding="utf-8")
    )[year]
    code_by_name = {e["player_name"]: e["player_code"] for e in player_codes["entries"]}
    expected_total_by_name = {e["player_name"]: e["expected_pre_cutoff_rounds_total"] for e in player_codes["entries"]}

    by_player = load_all_round_records(CONTENT_ROOT / manifest_name, EVIDENCE_ROOT / prior_name)

    entries = []
    for player_name, rounds in by_player.items():
        player_code = code_by_name.get(player_name)
        if player_code is None:
            continue  # same unresolved-playerCode exclusion as the existing manifest -- not fabricated
        per_tournament = Counter(r.game_code for r in rounds)
        pre_cutoff_tournaments = [
            {"game_code": gc, "start_date": next(t["start_date"] for t in tournaments if t["game_code"] == gc),
             "real_rounds_this_tournament": n}
            for gc, n in sorted(per_tournament.items())
        ]
        total_rounds = sum(n for _, n in per_tournament.items())
        entries.append({
            "player_name": player_name, "player_code": player_code, "season": int(year),
            "pre_cutoff_tournaments": pre_cutoff_tournaments,
            "expected_pre_cutoff_rounds_total": total_rounds,
        })
        # cross-check against the already-committed, already-tested manifest's own total -- must match exactly
        expected = expected_total_by_name.get(player_name)
        if expected is not None and expected != total_rounds:
            raise AssertionError(
                f"{year} {player_name}: round total mismatch, existing manifest says {expected}, "
                f"recomputed {total_rounds}"
            )

    return {
        "target_cutoff": target_cutoff, "season": int(year),
        "tournaments": tournaments, "entries": entries,
    }


def main() -> int:
    out = {year: build_year(year) for year in YEAR_CONFIG}
    OUTPUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    for year, data in out.items():
        n_calls = sum(len(e["pre_cutoff_tournaments"]) for e in data["entries"])
        print(f"{year}: {len(data['entries'])} players, {len(data['tournaments'])} tournaments, "
              f"{n_calls} total (player, tournament) pairs to acquire")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
