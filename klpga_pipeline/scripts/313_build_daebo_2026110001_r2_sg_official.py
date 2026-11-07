"""Normalize 대보 하우스디 챔피언십 (game_code 2026110001) Round 2's real
official Strokes Gained table into the same schema every other round's
own *_SG_OFFICIAL_V1.json already uses (see
DAEBO_2026110001_R1_SG_OFFICIAL_V1.json, built by scripts/311), so
klpga.neo_win.sg_pre_v1's estimate_player_sg_forecasts can consume it
identically.

Source: content/website_v2/raw_capture/2026110001_r2/sg.json, collected
for real via collect_current_round_evidence.py on a GitHub-hosted
runner (real network access to klpga.co.kr's own strokesGained_detail
endpoint, game_code=2026110001, round=2) and cross-checked there
against that run's own real leaderboard + per-player scorecards before
being written -- every row's player_id is therefore already real,
scorecard-verified identity, not re-resolved here. This script only
reshapes the already-verified rows; it does not re-fetch or re-resolve
anything.

방신실 withdrew (WD) during Round 2 and has no official Round 2
scorecard or SG row; this round's field is 59, not 60. The source
collector (collect_current_round_evidence.py) was patched to skip
scorecard reconciliation for WD/DQ rows rather than asserting every
leaderboard row has a tee-group pairing for this round.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GAME_CODE = "2026110001"
CONTENT = ROOT / "content" / "website_v2"
RAW_SG_PATH = CONTENT / "raw_capture" / f"{GAME_CODE}_r2" / "sg.json"
OUT_PATH = CONTENT / f"DAEBO_{GAME_CODE}_R2_SG_OFFICIAL_V1.json"

EXPECTED_FIELD_SIZE = 59  # 60 entrants minus 방신실 (WD during Round 2)


def main() -> None:
    raw = json.loads(RAW_SG_PATH.read_text(encoding="utf-8"))
    rows = raw["records"]
    if len(rows) != EXPECTED_FIELD_SIZE:
        raise RuntimeError(f"expected {EXPECTED_FIELD_SIZE} official R2 SG rows, found {len(rows)}")

    records = []
    seen_ids: set[str] = set()
    for row in rows:
        pid = str(row["player_id"])
        if pid in seen_ids:
            raise RuntimeError(f"duplicate player_id in official R2 SG rows: {pid}")
        seen_ids.add(pid)
        validation = row.get("validation") or {}
        if not (validation.get("total_within_tolerance") and validation.get("t2g_within_tolerance")):
            raise RuntimeError(f"official R2 SG row for {pid} failed its own component-sum validation: {validation}")
        records.append({
            "player_id": pid,
            "player_name": row["player"],
            "total": float(row["total"]),
            "rounds": int(row["rounds"]),
        })

    out = {
        "schema_version": 1,
        "game_code": GAME_CODE,
        "source_url": "https://klpga.co.kr/load/leaderboard/strokesGained_detail POST gameCode=2026110001, round=2",
        "scope": "single_round",
        "round": 2,
        "metric": "total_strokes_gained",
        "retrieved_context_date": "2026-11-07",
        "retrieved_at": raw["retrieved_at"],
        "field_size": len(records),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": sorted(records, key=lambda r: r["player_id"]),
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}: {len(records)} players")


if __name__ == "__main__":
    main()
