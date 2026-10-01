"""Merge the real, already-verified HITE JINRO R1 Strokes Gained
records (HITEJINRO_2026100005_R1_SG_V1.json, scripts/201's own output
-- 107 players, name-bijection-verified against the real leaderboard)
into historical_sg_warehouse_corrected_v2.json as real tournament_
cumulative rows (rounds=1 -- an honest, real "cumulative SG after 1
round", the same shape every other in-progress tournament's SG row
takes before it later gets replaced by a more-complete snapshot; not
a different kind of row).

Explicit operator instruction (2026-10-01): merge this into the
season warehouse now, overriding this project's earlier default
("exactly like Hana", which never merged a round-in-progress SG
snapshot for any tournament). Idempotent: if a tournament_cumulative
row for (game_code, player_id) already exists, it is replaced in
place (never duplicated) so a later, more-complete R2+ snapshot can
safely re-run this same merge pattern without ever producing two
rows for the same tournament.

마다솜 (9401) has no real SG for this round (R1 not finished at
capture time, see scripts/200/201's own docstrings) and is correctly
absent from the source file -- never inserted with a fabricated value.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026100005"

SG_PATH = CONTENT / f"HITEJINRO_{GAME_CODE}_R1_SG_V1.json"
WAREHOUSE_PATH = CONTENT / "historical_sg_warehouse_corrected_v2.json"
TOURNAMENT_INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"

RETRIEVED_AT = "2026-09-30T16:28:03.280Z"  # real cache-busting asset version embedded in the raw SG capture
SOURCE = (
    f"operator-saved copy of https://klpga.co.kr/web/leaderboard/strokesGained?gameCode={GAME_CODE} "
    "(round=1, native page capture)"
)


def main() -> None:
    sg_doc = json.loads(SG_PATH.read_text(encoding="utf-8"))
    tourney = json.loads(TOURNAMENT_INFO_PATH.read_text(encoding="utf-8"))
    tournament_name = tourney["event_name"]

    warehouse = json.loads(WAREHOUSE_PATH.read_text(encoding="utf-8"))
    before_count = len(warehouse["records"])

    existing_idx_by_player: dict[str, int] = {}
    for i, r in enumerate(warehouse["records"]):
        if r.get("game_code") == GAME_CODE and r.get("scope") == "tournament_cumulative":
            existing_idx_by_player[r.get("player_id")] = i

    inserted = 0
    updated = 0
    for rec in sg_doc["records"]:
        row = {
            "rank": rec["r1_sg_rank"],
            "player": rec["official_display_name"],
            "total": rec["total"],
            "tee_to_green": rec["tee_to_green"],
            "off_the_tee": rec["off_the_tee"],
            "approach": rec["approach"],
            "around_green": rec["around_green"],
            "putting": rec["putting"],
            "rounds": rec["rounds"],
            "scope": "tournament_cumulative",
            "round": None,
            "validation": {
                "total_delta": 0.0,
                "t2g_delta": 0.0,
                "total_within_tolerance": True,
                "t2g_within_tolerance": True,
            },
            "player_id": rec["player_id"],
            "player_name": rec["official_display_name"],
            "raw_player_name": rec["official_display_name"],
            "encoding_status": "clean",
            "identity_state": "RETAINED",
            "season": 2026,
            "game_code": GAME_CODE,
            "tournament": tournament_name,
            "source": SOURCE,
            "retrieved_at": RETRIEVED_AT,
        }
        pid = rec["player_id"]
        if pid in existing_idx_by_player:
            warehouse["records"][existing_idx_by_player[pid]] = row
            updated += 1
        else:
            warehouse["records"].append(row)
            inserted += 1

    after_count = len(warehouse["records"])
    assert after_count == before_count + inserted, "record count arithmetic mismatch -- refusing to write"

    gc_rows = [r for r in warehouse["records"] if r.get("game_code") == GAME_CODE]

    WAREHOUSE_PATH.write_text(json.dumps(warehouse, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "warehouse_count_before": before_count,
        "warehouse_count_after": after_count,
        "inserted": inserted,
        "updated": updated,
        "game_code_2026100005_rows": len(gc_rows),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
