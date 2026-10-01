"""HITE JINRO R1 -- parse the official Round 1 leaderboard raw capture
(operator-supplied, no Reader available in this sandbox: klpga.co.kr is
network-blocked here) into klpga.neo_win.hitejinro_round_page's exact
LEADERBOARD.json contract.

The raw page carries the real playerCode directly in each row's own
markup (<li id="favoritItem_{playerCode}" data-rank=... data-name=...
data-round1score=...>) -- no name-based join needed, unlike Hana's own
R1 SG page. 108 rows parsed, matching 2026100005_ENTRY_KRANKING_JOIN.json's
real 108-entrant field exactly.

One real, disclosed gap: 마다솜 (9401) had not completed Round 1 at the
moment this snapshot was captured (data-round1score="0", rank="999",
in-progress through hole 10 per _hole="10"/_level markers in the raw
HTML) -- her r1_score is written as None here, never fabricated. She is
therefore correctly absent from the "played" rows hitejinro_round_page.py
renders (same "absent, not guessed" rule this repo uses everywhere for
WD/incomplete players) until a later, complete capture is supplied.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026100005"

RAW_PATH = CONTENT / "incoming_evidence" / GAME_CODE / "HITEJINRO_2026100005_R1_LEADERBOARD_RAW.html"
ENTRY_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
OUT_PATH = CONTENT / f"{GAME_CODE}_LEADERBOARD.json"

_ROW_RE = re.compile(
    r'<li id="favoritItem_(\d+)"[^>]*data-rank="([^"]*)" data-name="([^"]*)" '
    r'data-totunderpar="([^"]*)" data-inghole="([^"]*)" data-todayunderpar="([^"]*)" '
    r'data-score="([^"]*)" data-round1score="([^"]*)" data-round2score="([^"]*)" '
    r'data-round3score="([^"]*)" data-round4score="([^"]*)" data-updown="([^"]*)"'
)


def _int_or_none(s: str) -> int | None:
    s = s.strip()
    if s == "":
        return None
    return int(s)


def main() -> None:
    raw_html = RAW_PATH.read_text(encoding="utf-8")
    raw_sha256 = hashlib.sha256(RAW_PATH.read_bytes()).hexdigest()

    entrants = json.loads(ENTRY_PATH.read_text(encoding="utf-8"))["records"]
    assert len(entrants) == 108, f"expected 108 official entrants, found {len(entrants)}"
    entrant_ids = {r["player_code"] for r in entrants}

    matches = list(_ROW_RE.finditer(raw_html))
    assert len(matches) == 108, f"expected 108 leaderboard rows, parsed {len(matches)}"

    parsed_ids = {m.group(1) for m in matches}
    assert parsed_ids == entrant_ids, (
        f"leaderboard playerCodes and the official entry roster are not the same set -- "
        f"only in leaderboard: {sorted(parsed_ids - entrant_ids)}, "
        f"only in roster: {sorted(entrant_ids - parsed_ids)}"
    )

    records = []
    not_yet_complete = []
    for m in matches:
        player_id, rank, name, totunderpar, inghole, todayunderpar, score, r1, r2, r3, r4, updown = m.groups()
        incomplete = rank == "999"
        r1_score = None if incomplete else _int_or_none(r1)
        if incomplete:
            not_yet_complete.append((player_id, name))
            finish_position = None
            finish_position_numeric = None
            score_to_par = None
        else:
            finish_position = rank
            finish_position_numeric = int(rank)
            score_to_par = _int_or_none(totunderpar)
        records.append({
            "player_id": player_id,
            "player_name": name,
            "finish_position": finish_position,
            "finish_position_numeric": finish_position_numeric,
            "score_to_par": score_to_par,
            "r1_score": r1_score,
            "r2_score": _int_or_none(r2),
            "r3_score": _int_or_none(r3),
            "r4_score": _int_or_none(r4),
            "withdrawn": False,
            "disqualified": False,
        })

    assert len(records) == 108
    assert len({r["player_id"] for r in records}) == 108, "duplicate player_id after parse"

    out = {
        "schema_version": "hitejinro_r1_leaderboard_v1",
        "game_code": GAME_CODE,
        "final_round": 1,
        "as_of": "2026-10-01",
        "source_raw": {
            "path": str(RAW_PATH.relative_to(ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": f"https://klpga.co.kr/web/leaderboard/sumScore?gameCode={GAME_CODE}",
        },
        "coverage": {
            "player_count": len(records),
            "completed_round1_count": sum(1 for r in records if r["r1_score"] is not None),
            "not_yet_complete_at_capture_time": [{"player_id": pid, "player_name": n} for pid, n in not_yet_complete],
        },
        "records": records,
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", OUT_PATH)
    print("coverage:", json.dumps(out["coverage"], ensure_ascii=False))
    print("raw sha256:", raw_sha256)


if __name__ == "__main__":
    main()
