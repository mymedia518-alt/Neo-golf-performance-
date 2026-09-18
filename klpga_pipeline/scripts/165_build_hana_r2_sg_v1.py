"""HANA R2 -- parse the official Round 2 Strokes Gained raw capture
into per-player records, joined to player_id.

RED TEAM MODEL CORRECTION follow-up (operator instruction, 2026-09-18):
mirrors scripts/154/155's R1 SG ingestion exactly (same raw-page shape,
same regex, same identity-join discipline), for the round=2 single-
round SG table the operator uploaded directly into this session
(content/website_v2/incoming_evidence/2026090002/HANA_2026090002_R2_SG_RAW.html).
The page's outer URL is the same client-rendered
`strokesGained?gameCode=2026090002` shell as R1 (round selection is a
client-side tab, not a distinct URL) -- confirmed as genuinely ROUND 2
by its own table content, not by the URL: every row's own `rounds`
column reads 1 (single-round, never cumulative), and the per-player
SG figures differ sharply from the already-ingested R1 file for the
same player_id (e.g. 이채은2: R1 total=0.21 rank 50 -> R2 total=5.17
rank 1) -- the two files are not duplicates of the same round.

Research/validation only. This is a NEW, separate file; nothing under
PRE/R1/R2 archive, the R2 leaderboard freeze, or the production
forecast is read for identity-matching purposes or written to.

Population: the R2 SG table covers every player who actually played
Round 2 -- both eventual cut survivors AND cut misses (the cut is a
cumulative-score fact determined AFTER R2 is played, not a
precondition for having a Round 2 SG figure) -- i.e. the same 102
non-WD population as 2026090002_R2_FROZEN_EVIDENCE.json, not just the
64 survivors. The 64-survivor restriction is applied downstream, at
model-input time, never here.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

RAW_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R2_SG_RAW.html"
R2_FREEZE_PATH = CONTENT / "2026090002_R2_FROZEN_EVIDENCE.json"

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

    freeze = json.loads(R2_FREEZE_PATH.read_text(encoding="utf-8"))
    non_wd = [r for r in freeze["records"] if r["status"] != "WD"]
    assert len(non_wd) == 102
    name_to_id = {r["player_name"]: r["player_id"] for r in non_wd}
    assert len(name_to_id) == 102, "duplicate display name in the active R2 roster -- name-based join unsafe"

    matches = list(_ROW_RE.finditer(raw_html))
    assert len(matches) == 102, f"expected 102 SG table rows, parsed {len(matches)}"

    sg_names = [m.group(2) for m in matches]
    assert len(set(sg_names)) == 102, "duplicate display name in the SG table -- name-based join unsafe"
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
            "r2_sg_rank": int(rank),
            "total": float(total),
            "tee_to_green": float(tee_to_green),
            "off_the_tee": float(off_the_tee),
            "approach": float(approach),
            "around_green": float(around_green),
            "putting": float(putting),
            "rounds": int(rounds),
        })

    assert len(records) == 102
    assert len({r["player_id"] for r in records}) == 102, "duplicate player_id after join"
    assert all(r["rounds"] == 1 for r in records), "expected exactly 1 round of SG data per player (R2 only, never cumulative)"
    assert all(r["total"] is not None for r in records)

    wd_ids = {"9702", "9136", "12706"}
    assert wd_ids.isdisjoint({r["player_id"] for r in records}), "a WD player unexpectedly has SG data"

    out = {
        "schema_version": "hana_r2_sg_v1",
        "game_code": "2026090002",
        "round_number": 2,
        "as_of": "2026-09-18",
        "purpose": (
            "ROUND-SCOPED Strokes Gained observed in R2 only -- an R3-analysis "
            "input FEATURE, never cumulative R1+R2, never a substitute for the "
            "season-cumulative current_official_sg figure. Never merged into "
            "PRE/R1/R2 archive files or the production forecast."
        ),
        "source_raw": {
            "path": str(RAW_PATH.relative_to(ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": "https://klpga.co.kr/web/leaderboard/strokesGained?gameCode=2026090002",
            "note": "client-side round tab, same outer URL as R1 -- round identity verified by table content, not URL (see module docstring)",
        },
        "identity_join": {
            "method": "exact display-name match against 2026090002_R2_FROZEN_EVIDENCE.json's 102 non-WD "
                       "population, used only after independently verifying the join is a true 1:1 "
                       "bijection (both sides duplicate-free, set-equal) -- never a name-based guess",
            "population_count": 102,
            "duplicate_names_in_sg_table": 0,
            "duplicate_names_in_roster": 0,
            "bijection_verified": True,
        },
        "wd_players_excluded": sorted(wd_ids, key=int),
        "coverage": {
            "player_count": len(records),
            "duplicate_player_ids": 0,
            "all_have_total_sg": True,
            "all_records_summed": f"{len(records)}/102",
        },
        "records": records,
    }

    out_path = CONTENT / "HANA_2026090002_R2_SG_V1.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    print("coverage:", json.dumps(out["coverage"], ensure_ascii=False))
    print("raw sha256:", raw_sha256)


if __name__ == "__main__":
    main()
