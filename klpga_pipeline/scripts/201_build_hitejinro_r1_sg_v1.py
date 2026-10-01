"""HITE JINRO R1 -- parse the official Round 1 Strokes Gained raw
capture into per-player records, joined to player_id.

Mirrors scripts/155_build_hana_r1_sg_v1.py exactly (same module purpose,
same identity-join discipline, same output shape): this raw page
carries NO player_id anywhere in its static markup (every row is
"<tr data-sgrank=...><td>rank</td><td>name</td>..."), so the join is by
display name, done ONLY after independently proving it is unambiguous
for this exact population -- both the 107 names in this SG table and
the 107 names of players who actually completed Round 1 (per the
real, already-parsed 2026100005_LEADERBOARD.json) are verified
duplicate-free, and the two 107-name sets are verified identical
(bijective).

Role of this data (same as Hana's own R1 SG file): a ROUND-SCOPED
feature, never merged into the season-wide historical_sg_warehouse_
corrected_v2.json that knowledge_engine.py's recent_5_sg/current_form
pipeline reads -- confirmed real precedent: that warehouse holds ZERO
rows for Hana's own game_code (2026090002) to this day, so a
round-in-progress snapshot has never been merged into it for any
tournament. This script writes only this one new, separate file.

마다솜 (9401, Round 1 not yet complete at capture time -- see
200_build_hitejinro_r1_leaderboard.py's own docstring) is correctly
absent from this SG table's source page and therefore absent here too
-- never assigned a fabricated SG value.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
GAME_CODE = "2026100005"

RAW_PATH = CONTENT / "incoming_evidence" / GAME_CODE / "HITEJINRO_2026100005_R1_SG_RAW.html"
LEADERBOARD_PATH = CONTENT / f"{GAME_CODE}_LEADERBOARD.json"

_ROW_RE = re.compile(
    r'<tr data-sgrank="(\d+)" data-teetogreenrank="\d+" data-driverrank="\d+" '
    r'data-approachrank="\d+" data-aroundrank="\d+" data-putterrank="\d+">\s*'
    r'<td[^>]*>\d+</td>\s*<td[^>]*>([^<]+)</td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>([-\d.]+)<span[^>]*>[^<]*</span></td>\s*'
    r'<td[^>]*>(\d+)</td>',
    re.DOTALL,
)


def main() -> None:
    raw_html = RAW_PATH.read_text(encoding="utf-8")
    raw_sha256 = hashlib.sha256(RAW_PATH.read_bytes()).hexdigest()

    leaderboard = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))
    completed = [r for r in leaderboard["records"] if r["r1_score"] is not None]
    assert len(completed) == 107
    name_to_id = {r["player_name"]: r["player_id"] for r in completed}
    assert len(name_to_id) == 107, "duplicate display name among completed R1 players -- name-based join unsafe"

    matches = list(_ROW_RE.finditer(raw_html))
    assert len(matches) == 107, f"expected 107 SG table rows, parsed {len(matches)}"

    sg_names = [m.group(2) for m in matches]
    assert len(set(sg_names)) == 107, "duplicate display name in the SG table -- name-based join unsafe"
    assert set(sg_names) == set(name_to_id), (
        f"SG table names and completed-R1 roster names are not a bijection -- "
        f"only in SG: {sorted(set(sg_names) - set(name_to_id))}, "
        f"only in roster: {sorted(set(name_to_id) - set(sg_names))}"
    )

    records = []
    for m in matches:
        rank, name, total, tee_to_green, off_the_tee, approach, around_green, putting, rounds = m.groups()
        records.append({
            "player_id": name_to_id[name],
            "official_display_name": name,
            "r1_sg_rank": int(rank),
            "total": float(total),
            "tee_to_green": float(tee_to_green),
            "off_the_tee": float(off_the_tee),
            "approach": float(approach),
            "around_green": float(around_green),
            "putting": float(putting),
            "rounds": int(rounds),
        })

    assert len(records) == 107
    assert len({r["player_id"] for r in records}) == 107, "duplicate player_id after join"
    assert all(r["rounds"] == 1 for r in records), "expected exactly 1 round of SG data per player (R1 only)"

    out = {
        "schema_version": "hitejinro_r1_sg_v1",
        "game_code": GAME_CODE,
        "round_number": 1,
        "as_of": "2026-10-01",
        "purpose": (
            "ROUND-SCOPED Strokes Gained observed in R1 only -- never merged "
            "into historical_sg_warehouse_corrected_v2.json or the PRE/R1 "
            "page's own NEO 경기력 band (same discipline as Hana's own "
            "scripts/155-179 R1-R4 SG files, which were never merged either)."
        ),
        "source_raw": {
            "path": str(RAW_PATH.relative_to(ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": f"https://klpga.co.kr/web/leaderboard/strokesGained?gameCode={GAME_CODE}",
        },
        "identity_join": {
            "method": "exact display-name match, used only after independently verifying the join is a "
                       "true 1:1 bijection for this exact 107-player population (both sides duplicate-free, "
                       "set-equal) -- never a name-based guess",
            "population_count": 107,
            "bijection_verified": True,
        },
        "not_yet_complete_excluded": [{"player_id": "9401", "player_name": "마다솜"}],
        "coverage": {
            "player_count": len(records),
            "duplicate_player_ids": 0,
        },
        "records": records,
    }

    out_path = CONTENT / "HITEJINRO_2026100005_R1_SG_V1.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    print("coverage:", json.dumps(out["coverage"], ensure_ascii=False))
    print("raw sha256:", raw_sha256)


if __name__ == "__main__":
    main()
