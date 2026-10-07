"""NEO HJ 2026 (gameCode 2026100004, real confirmed start_date
2026-10-08) -- build the 2026-season prior-tournament manifest, the
same role STABLEFORD_2023/2024/2025_PRIOR_TOURNAMENT_MANIFEST_V1.json
played for those years' blind backtests.

No new network access. Built entirely from two already-real, already-
cross-checked calendar sources already in this repo:
  - content/website_v2/TOURNAMENT_K_WEEK_MAPPING_V1.json -- 20 real
    2026 tournaments (2026030001 through 2026080004), each with a
    real start_date AND end_date (not derived).
  - content/website_v2/OFFICIAL_KLPGA_SCHEDULE.json -- the only source
    this repo treats as calendar-identity-authoritative for the most
    recent tournaments; gives the remaining 4 real pre-cutoff 2026
    codes (2026090002/2026090003/2026100005/2026120001) PLUS the
    target event 2026100004 itself (used here only to confirm the
    cutoff, 2026-10-08 -- the target's own data is never included as
    an entry).

Every entry's start_date is independently verified < 2026-10-08
(assert_no_leakage below raises loudly otherwise) -- the same
leakage-safety discipline as the 2023/2024/2025 manifests."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KLPGA_PIPELINE_ROOT = SCRIPT_DIR.parent
CONTENT_ROOT = KLPGA_PIPELINE_ROOT / "content" / "website_v2"

TARGET_GAME_CODE = "2026100004"
TARGET_START_DATE = "2026-10-08"

OUT_PATH = CONTENT_ROOT / "STABLEFORD_2026_PRIOR_TOURNAMENT_MANIFEST_V1.json"


def assert_no_leakage(entries: list[dict]) -> None:
    target = date.fromisoformat(TARGET_START_DATE)
    for e in entries:
        start = date.fromisoformat(e["start_date"])
        if start >= target:
            raise AssertionError(
                f"LEAKAGE: {e['game_code']} ({e['tournament_name']}) starts {start}, "
                f"not strictly before target {target}"
            )


def build_entries() -> list[dict]:
    k_week = json.loads((CONTENT_ROOT / "TOURNAMENT_K_WEEK_MAPPING_V1.json").read_text(encoding="utf-8"))
    schedule = json.loads((CONTENT_ROOT / "OFFICIAL_KLPGA_SCHEDULE.json").read_text(encoding="utf-8"))

    entries = [
        {"game_code": r["game_code"], "tournament_name": r["tournament_name"], "start_date": r["start_date"]}
        for r in k_week["records"]
        if r.get("season") == 2026
    ]
    seen = {e["game_code"] for e in entries}
    for t in schedule["tournaments"]:
        if t["game_code"] == TARGET_GAME_CODE or t["game_code"] in seen:
            continue
        entries.append({
            "game_code": t["game_code"], "tournament_name": t["tournament_name"], "start_date": t["start_date"],
        })
        seen.add(t["game_code"])

    entries.sort(key=lambda e: e["start_date"])
    assert_no_leakage(entries)
    return entries


def main() -> int:
    entries = build_entries()
    manifest = {
        "schema_version": 1,
        "purpose": "2026-season prior-tournament manifest for the HJ중공업·동부건설 챔피언십 "
                   "(gameCode=2026100004) Stableford V1 pre-event application",
        "target_game_code": TARGET_GAME_CODE,
        "target_start_date": TARGET_START_DATE,
        "entry_count": len(entries),
        "entries": entries,
    }
    OUT_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(entries)} entries, all confirmed strictly before {TARGET_START_DATE}")
    for e in entries:
        print(f"  {e['game_code']}  {e['start_date']}  {e['tournament_name']}")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
