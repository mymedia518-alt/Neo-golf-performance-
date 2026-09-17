"""HANA R1 -- parse the official Round 1 Strokes Gained raw capture
into per-player records, joined to player_id.

This raw page carries NO player_id/playerCode anywhere in its static
markup (confirmed: every "playerCode" occurrence in the file is
generic shared JS boilerplate -- the favorite-player and 3D-map
widgets -- never a per-row data attribute). Rows carry only the
player's display name as plain text. Matching is therefore done by
name, but ONLY after independently proving it is unambiguous for this
exact population: the 105 names in this SG table and the 105 names in
HANA_2026090002_R1_PLAYER_RESULT_V1.json's active (non-WD) population
are both individually verified duplicate-free, and the two 105-name
sets are verified to be identical (bijective). Only under that proven
1:1 condition is name used as the join key here -- this is a verified
exact match, not a name-based guess, and the script hard-stops if the
bijection condition is not met.

Role of this data (explicit, per operator instruction): a ROUND-SCOPED
feature for the eventual R2 analysis pass -- observed R1 Strokes
Gained performance, never a substitute for or edit to the
season-cumulative SG figure (current_official_sg /
KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1.json) that PRE already used. This
script writes only a new, separate file; nothing under
PRE/archive/2026090002/pre/ or the already-published R1 result/
analysis/comparison files is read for identity-matching purposes or
written to.

WD players (김리안 9702, 조혜림 9136, 권은 12706) are correctly absent
from the source table (they have no R1 round to measure) and are
absent from this output too -- never assigned a fabricated SG value.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

RAW_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R1_SG_RAW.html"
R1_RESULT_PATH = CONTENT / "HANA_2026090002_R1_PLAYER_RESULT_V1.json"

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

    r1_result = json.loads(R1_RESULT_PATH.read_text(encoding="utf-8"))
    active = [r for r in r1_result["records"] if r["status"] != "WD"]
    assert len(active) == 105
    name_to_id = {r["official_display_name"]: r["player_id"] for r in active}
    assert len(name_to_id) == 105, "duplicate display name in the active R1 roster -- name-based join unsafe"

    matches = list(_ROW_RE.finditer(raw_html))
    assert len(matches) == 105, f"expected 105 SG table rows, parsed {len(matches)}"

    sg_names = [m.group(2) for m in matches]
    assert len(set(sg_names)) == 105, "duplicate display name in the SG table -- name-based join unsafe"
    assert set(sg_names) == set(name_to_id), (
        f"SG table names and active roster names are not a bijection -- "
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

    assert len(records) == 105
    assert len({r["player_id"] for r in records}) == 105, "duplicate player_id after join"
    assert all(r["rounds"] == 1 for r in records), "expected exactly 1 round of SG data per player (R1 only)"
    assert all(r["total"] is not None for r in records)
    total_sum_check = sum(1 for r in records if r["total"] is not None)
    assert total_sum_check == 105, f"expected all 105 players to have a total SG value, got {total_sum_check}"

    wd_ids = {"9702", "9136", "12706"}
    assert wd_ids.isdisjoint({r["player_id"] for r in records}), "a WD player unexpectedly has SG data"

    out = {
        "schema_version": "hana_r1_sg_v1",
        "game_code": "2026090002",
        "round_number": 1,
        "as_of": "2026-09-17",
        "purpose": (
            "ROUND-SCOPED Strokes Gained observed in R1 only -- an R2-analysis "
            "input FEATURE, never a substitute for or edit to the season "
            "-cumulative current_official_sg figure PRE already used. Never "
            "merged into PRE files or the R1 archive."
        ),
        "source_raw": {
            "path": str(RAW_PATH.relative_to(ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": "https://klpga.co.kr/web/leaderboard/strokesGained?gameCode=2026090002",
        },
        "identity_join": {
            "method": "exact display-name match, used only after independently verifying the join is a "
                       "true 1:1 bijection for this exact 105-player population (both sides duplicate-free, "
                       "set-equal) -- never a name-based guess",
            "population_count": 105,
            "duplicate_names_in_sg_table": 0,
            "duplicate_names_in_roster": 0,
            "bijection_verified": True,
        },
        "wd_players_excluded": sorted(wd_ids, key=int),
        "coverage": {
            "player_count": len(records),
            "duplicate_player_ids": 0,
            "all_have_total_sg": True,
            "all_records_summed": f"{total_sum_check}/105",
        },
        "records": records,
    }

    out_path = CONTENT / "HANA_2026090002_R1_SG_V1.json"
    if out_path.exists():
        out_path.unlink()
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    print("coverage:", json.dumps(out["coverage"], ensure_ascii=False))
    print("raw sha256:", raw_sha256)


if __name__ == "__main__":
    main()
