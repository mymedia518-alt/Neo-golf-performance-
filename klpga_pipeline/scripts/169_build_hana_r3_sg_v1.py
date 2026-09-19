"""HANA R3 -> FINAL PIPELINE, STEP 1 (operator instruction, 2026-09-19):
parse the official Round 3 Strokes Gained raw capture into per-player
records, joined to player_id -- mirrors scripts/154/155/165's R1/R2 SG
ingestion exactly (same raw-page shape, same regex, same identity-join
discipline).

Population: the R3 SG table covers exactly the 64 official cut
survivors who played Round 3 (there is no cut event at R3 -- see
r3_freeze.py's own docstring) -- the same 64 ACTIVE population as
2026090002_R3_FROZEN_EVIDENCE.json.

PER OPERATOR INSTRUCTION (2026-09-19): R3 SG is an evidence artifact /
diagnostic / reporting field ONLY -- it is never used as a predictive
feature in the production FINAL forecast (the R1SG_R2SG_R3SG walk-
forward extension was validated and FAILED its promotion gate; see
HANA_2026090002_R4_SG_VALIDATION_REPORT_V1.json). This script only
ingests and records the real official R3 SG values for reporting/
research purposes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

RAW_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R3_SG_RAW.html"
R3_FREEZE_PATH = CONTENT / "2026090002_R3_FROZEN_EVIDENCE.json"

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

    freeze = json.loads(R3_FREEZE_PATH.read_text(encoding="utf-8"))
    active = [r for r in freeze["records"] if r["status"] == "ACTIVE"]
    assert len(active) == 64
    name_to_id = {r["player_name"]: r["player_id"] for r in active}
    assert len(name_to_id) == 64, "duplicate display name in the active R3 roster -- name-based join unsafe"

    matches = list(_ROW_RE.finditer(raw_html))
    assert len(matches) == 64, f"expected 64 SG table rows, parsed {len(matches)}"

    sg_names = [m.group(2) for m in matches]
    assert len(set(sg_names)) == 64, "duplicate display name in the SG table -- name-based join unsafe"
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
            "r3_sg_rank": int(rank),
            "total": float(total),
            "tee_to_green": float(tee_to_green),
            "off_the_tee": float(off_the_tee),
            "approach": float(approach),
            "around_green": float(around_green),
            "putting": float(putting),
            "rounds": int(rounds),
        })

    assert len(records) == 64
    assert len({r["player_id"] for r in records}) == 64, "duplicate player_id after join"
    assert all(r["rounds"] == 1 for r in records), "expected exactly 1 round of SG data per player (R3 only, never cumulative)"
    assert all(r["total"] is not None for r in records)

    out = {
        "schema_version": "hana_r3_sg_v1",
        "game_code": "2026090002",
        "round_number": 3,
        "as_of": "2026-09-19",
        "purpose": (
            "ROUND-SCOPED Strokes Gained observed in R3 only. Per explicit operator "
            "instruction (2026-09-19), this is an EVIDENCE ARTIFACT / DIAGNOSTIC / "
            "REPORTING FIELD ONLY -- NEVER a predictive feature in the production "
            "FINAL forecast. The R1SG_R2SG_R3SG walk-forward extension was tested "
            "and FAILED its promotion gate (p=n.s., bootstrap CI includes zero); "
            "see HANA_2026090002_R4_SG_VALIDATION_REPORT_V1.json. The production "
            "FINAL forecast uses ONLY the already-validated/promoted R1SG_R2SG "
            "model, unchanged."
        ),
        "source_raw": {
            "path": str(RAW_PATH.relative_to(ROOT.parent)),
            "sha256": raw_sha256,
            "saved_from_url": "https://klpga.co.kr/web/leaderboard/strokesGained?gameCode=2026090002",
            "note": "client-side round tab, same outer URL shell as R1/R2 -- round identity verified by table content (all 64 official R3 cut-survivor names), not by URL",
        },
        "identity_join": {
            "method": "exact display-name match against 2026090002_R3_FROZEN_EVIDENCE.json's 64 ACTIVE "
                       "population, used only after independently verifying the join is a true 1:1 "
                       "bijection (both sides duplicate-free, set-equal) -- never a name-based guess",
            "population_count": 64,
            "duplicate_names_in_sg_table": 0,
            "duplicate_names_in_roster": 0,
            "bijection_verified": True,
        },
        "coverage": {
            "player_count": len(records),
            "duplicate_player_ids": 0,
            "all_have_total_sg": True,
            "all_records_summed": f"{len(records)}/64",
        },
        "records": records,
    }

    out_path = CONTENT / "HANA_2026090002_R3_SG_V1.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    print("coverage:", json.dumps(out["coverage"], ensure_ascii=False))
    print("raw sha256:", raw_sha256)


if __name__ == "__main__":
    main()
