"""Build the 아이스버그골프·서울신문 오픈 (game_code 2026100003) entry x
K-Ranking join, same shape and method as 2026100005_ENTRY_KRANKING_JOIN.json
(scripts/190's own documented precedent for this join): the 108 official
entrants (content/website_v2/2026100003_ENTRY_SNAPSHOT.json, mirrored
from the validated `reader/2026100003` branch -- NEO Sync, all 7
validation checks PASS, see reports/2026100003/REVIEW_REPORT_V1.md on
that branch) joined by official player_code against the committed
K-Ranking population (content/website_v2/2026100003_KRANKING_TOP120.json,
official K-Ranking closed interval 1..120 only -- the same artifact
shape this repo's registered NEO Sync pipeline persists for every
gameCode; a genuine full-747-style table was never collected for this
gameCode, so an entrant ranked below 120 is honestly unmatched here,
exactly like 140's own "no number is ever guessed for those" rule).

No player_master/warehouse dependency. Purely additive: reads only the
two files above, writes only this one new join file.
"""
from __future__ import annotations

import json
from pathlib import Path

GAME_CODE = "2026100003"
CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
ENTRY_PATH = CONTENT / f"{GAME_CODE}_ENTRY_SNAPSHOT.json"
KRANKING_PATH = CONTENT / f"{GAME_CODE}_KRANKING_TOP120.json"
OUT_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"


def main() -> None:
    entry = json.loads(ENTRY_PATH.read_text(encoding="utf-8"))
    kranking = json.loads(KRANKING_PATH.read_text(encoding="utf-8"))
    assert entry["game_code"] == GAME_CODE
    assert entry["parsed_row_count"] == len(entry["records"]) == 108

    k_by_id = {r["player_id"]: r for r in kranking["records"]}

    records = []
    matched = 0
    for r in entry["records"]:
        pid = r["player_code"]
        k = k_by_id.get(pid)
        out = {
            "player_code": pid,
            "player_name": r["player_name"],
            "nationality": r["nationality"],
            "qualification_category": r["qualification_category"],
            "qualification_reason": r.get("qualification_reason"),
            "official_k_rank": k["official_k_rank"] if k else None,
            "k_rating": k["rating"] if k else None,
            "k_total_points": k["total_points"] if k else None,
            "k_event_count": k["event_count"] if k else None,
        }
        if k:
            matched += 1
        records.append(out)

    assert len(records) == 108

    out = {
        "game_code": GAME_CODE,
        "ranking_week": kranking["ranking_week"],
        "full_population_count": kranking["full_population_count"],
        "entrants_matched": matched,
        "entrants_unmatched": len(records) - matched,
        "source": (
            "k-rankings.klpga.co.kr/allplayer.jsp official K-Ranking closed interval "
            "1..120 (2026100003_KRANKING_TOP120.json), joined by official player_code "
            "-- no player_master/warehouse dependency. An entrant ranked below 120 is "
            "honestly unmatched (official_k_rank=null), never estimated."
        ),
        "records": records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "written": str(OUT_PATH),
        "entrants": len(records),
        "matched": matched,
        "unmatched": len(records) - matched,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
