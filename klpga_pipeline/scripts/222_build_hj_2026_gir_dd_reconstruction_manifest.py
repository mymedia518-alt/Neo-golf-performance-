"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- build the
per-tournament reconstruction manifest needed for a true season-to-date
cumulative GIR / Driving Distance for the real 108-player field.

Exact same method already validated for the three-winner historical
profile (scripts/212_build_full_reconstruction_manifest.py), just
repointed at the 2026 field and the new 24-tournament 2026 evidence --
no new acquisition method invented, no new network access for THIS
step. For each of the 108 real canonical entrants, finds every one of
the 24 real pre-cutoff 2026 tournaments she actually played (>=1 real
round in that tournament's own scoreRecord capture) and the REAL round
count for that specific tournament -- the ground truth the
reconstruction script's two-layer gate (klpga.collectors.
official_season_stat_reconstruction) uses to trust or reject each
per-tournament publicRecordSeasonDetail call.
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

MANIFEST_PATH = CONTENT_ROOT / "STABLEFORD_2026_PRIOR_TOURNAMENT_MANIFEST_V1.json"
PRIOR_DIR = EVIDENCE_ROOT / "stableford_prior_2026"
IDENTITY_PATH = CONTENT_ROOT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"
OUT_PATH = CONTENT_ROOT / "HJ_2026100004_GIR_DD_RECONSTRUCTION_MANIFEST_V1.json"

TARGET_CUTOFF = "2026-10-08"
SEASON = 2026


def build() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    tournaments = {e["game_code"]: e["start_date"] for e in manifest["entries"]}
    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))

    by_player = load_all_round_records(MANIFEST_PATH, PRIOR_DIR)

    entries = []
    for r in identity["records"]:
        name = r["player_name"]
        rounds = by_player.get(name, [])
        per_tournament = Counter(rr.game_code for rr in rounds)
        pre_cutoff_tournaments = [
            {"game_code": gc, "start_date": tournaments[gc], "real_rounds_this_tournament": n}
            for gc, n in sorted(per_tournament.items())
        ]
        entries.append({
            "player_name": name, "player_code": r["player_code"], "season": SEASON,
            "pre_cutoff_tournaments": pre_cutoff_tournaments,
            "expected_pre_cutoff_rounds_total": sum(per_tournament.values()),
        })

    return {
        "target_cutoff": TARGET_CUTOFF, "season": SEASON, "game_code": "2026100004",
        "tournaments": [{"game_code": gc, "start_date": sd} for gc, sd in sorted(tournaments.items())],
        "entries": entries,
    }


def main() -> int:
    data = build()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    n_calls = sum(len(e["pre_cutoff_tournaments"]) for e in data["entries"])
    n_zero = sum(1 for e in data["entries"] if not e["pre_cutoff_tournaments"])
    print(f"{len(data['entries'])} players, {n_calls} total (player, tournament) calls needed, "
          f"{n_zero} players with zero prior-tournament data")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
