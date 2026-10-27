"""Reshape 2026100001_ENTRY_SNAPSHOT.json (the raw NEO Sync entry list,
records[]/player_code) into the same KE entry-snapshot bridge shape
2026100005_KE_ENTRY_SNAPSHOT.json / 2026100003_KE_ENTRY_SNAPSHOT.json
already use (entries[]/player_id) -- a pure, lossless field rename, no
new or dropped records, following those two files' own established
convention so klpga.models/pre_v2's M4 build (scripts/274) can read
this tournament's field the same way it already reads every other
tournament's.

Purely additive: reads only 2026100001_ENTRY_SNAPSHOT.json, writes only
2026100001_KE_ENTRY_SNAPSHOT.json.
"""
from __future__ import annotations

import json
from pathlib import Path

GAME_CODE = "2026100001"
CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
SRC_PATH = CONTENT / f"{GAME_CODE}_ENTRY_SNAPSHOT.json"
OUT_PATH = CONTENT / f"{GAME_CODE}_KE_ENTRY_SNAPSHOT.json"


def main() -> None:
    src = json.loads(SRC_PATH.read_text(encoding="utf-8"))
    assert src["game_code"] == GAME_CODE
    assert src["parsed_row_count"] == len(src["records"])

    entries = [
        {
            "player_id": r["player_code"],
            "player_name": r["player_name"],
            "entry_status": "listed",
            "nationality": r["nationality"],
            "qualification_category": r["qualification_category"],
            "qualification_reason": r.get("qualification_reason"),
        }
        for r in src["records"]
    ]
    ids = [e["player_id"] for e in entries]
    duplicate_ids = sorted({i for i in ids if ids.count(i) > 1})

    out = {
        "schema_version": "neo_home_ke_entry_snapshot_v1",
        "game_code": GAME_CODE,
        "retrieved_at": src["collected_at"],
        "source_url": src["source"],
        "player_count": len(entries),
        "parser_unparsed_rows": src["unparsed_row_count"],
        "duplicate_player_ids": duplicate_ids,
        "unresolved_player_ids": [],
        "withdrawals_marked_by_source": [],
        "entries": entries,
    }
    assert not duplicate_ids, f"duplicate player_id values in source entry list: {duplicate_ids}"

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"written": str(OUT_PATH), "entries": len(entries)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
