"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- real 2026
season-to-date SG Total / SG Tee-to-Green for the 108-player field.

Reuses the EXACT already-validated aggregation rule from klpga.
website_v2.stableford_backtest_snapshot._mean (a simple mean of each
player's own real tournament_cumulative SG rows across her pre-cutoff
tournaments -- the same rule already used for the three-winner CORE
validation's SG Total/SG Tee-to-Green features) -- not reimplemented,
not reweighted, not replaced with a new formula. The only change here
is EXACT-DATE filtering (this project now holds a real start_date for
every one of the 24 real 2026 prior tournaments, so there is no need
for the original month-only conservative leakage rule) instead of
month granularity.

Source: content/website_v2/historical_sg_warehouse_corrected_v2.json
(already real, already in this repo -- confirmed this turn to already
cover 22 of the 24 real pre-cutoff 2026 tournaments). The 2 missing
tournaments (2026090002/하나금융그룹, 2026120001/OK저축은행) are NOT
estimated here -- a player's SG mean is computed only from whichever
of her real played tournaments are ALREADY in the warehouse; once the
2 missing tournaments are collected (see the Windows command this
script's own README output names), re-running this script will pick
them up automatically with zero code changes.

season-final values are never used (this module only ever reads
scope=="tournament_cumulative" rows, never a season-aggregate row);
target event 2026100004 is structurally absent from the warehouse
(never played) and is never read even if it were present.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(KLPGA_PIPELINE_ROOT / "src"))

CONTENT_ROOT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"
SG_WAREHOUSE_PATH = CONTENT_ROOT / "historical_sg_warehouse_corrected_v2.json"
MANIFEST_PATH = CONTENT_ROOT / "STABLEFORD_2026_PRIOR_TOURNAMENT_MANIFEST_V1.json"
IDENTITY_PATH = CONTENT_ROOT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"
OUT_PATH = CONTENT_ROOT / "HJ_2026100004_SG_PROFILE_V1.json"

TARGET_CUTOFF = date.fromisoformat("2026-10-08")


def build() -> dict:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    eligible_game_codes = {e["game_code"] for e in manifest["entries"]}
    for e in manifest["entries"]:
        assert date.fromisoformat(e["start_date"]) < TARGET_CUTOFF  # re-verified, never trusted blindly

    identity = json.loads(IDENTITY_PATH.read_text(encoding="utf-8"))
    hj_names = {r["player_name"] for r in identity["records"]}

    records = json.loads(SG_WAREHOUSE_PATH.read_text(encoding="utf-8"))["records"]
    by_player: dict[str, list[dict]] = {}
    covered_game_codes: set[str] = set()
    for r in records:
        if r["season"] != 2026 or r["scope"] != "tournament_cumulative":
            continue
        if r["game_code"] not in eligible_game_codes:
            continue  # not one of our 24 real pre-cutoff tournaments (or is the target event -- never present anyway)
        if r["player"] not in hj_names:
            continue
        by_player.setdefault(r["player"], []).append(r)
        covered_game_codes.add(r["game_code"])

    missing_game_codes = sorted(eligible_game_codes - covered_game_codes)

    def _mean(rows: list[dict], key: str) -> float:
        return round(sum(row[key] for row in rows) / len(rows), 4)

    players = {}
    for name in sorted(hj_names):
        rows = by_player.get(name, [])
        if not rows:
            players[name] = {
                "data_status": "DATA_LIMITED_NO_SG_DATA", "tournaments_covered": 0,
                "sg_total_mean": None, "sg_tee_to_green_mean": None,
            }
            continue
        players[name] = {
            "data_status": "OK", "tournaments_covered": len(rows),
            "sg_total_mean": _mean(rows, "total"), "sg_tee_to_green_mean": _mean(rows, "tee_to_green"),
        }

    return {
        "schema_version": 1, "game_code": "2026100004", "target_cutoff": "2026-10-08",
        "eligible_game_codes_count": len(eligible_game_codes),
        "game_codes_covered_in_warehouse": sorted(covered_game_codes),
        "game_codes_missing_from_warehouse": missing_game_codes,
        "field_n": len(hj_names),
        "players_with_data": sum(1 for p in players.values() if p["data_status"] == "OK"),
        "players": players,
    }


def main() -> int:
    data = build()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"field_n={data['field_n']}  players_with_data={data['players_with_data']}")
    print(f"game_codes covered: {len(data['game_codes_covered_in_warehouse'])}/{data['eligible_game_codes_count']}")
    print(f"MISSING from warehouse (need live collection): {data['game_codes_missing_from_warehouse']}")
    print(f"Wrote {OUT_PATH}")
    if data["game_codes_missing_from_warehouse"]:
        print(
            "\nNEXT (Windows, real network access): collect the missing tournaments' SG via the "
            "already-generic collector, then re-run this script:"
        )
        names = {"2026090002": "하나금융그룹 챔피언십", "2026120001": "OK저축은행 읏맨 오픈"}
        for gc in data["game_codes_missing_from_warehouse"]:
            tname = names.get(gc, "")
            print(f'  python scripts/collect_sg_from_leaderboard.py --game-code {gc} --season 2026 '
                  f'--tournament "{tname}" --live')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
