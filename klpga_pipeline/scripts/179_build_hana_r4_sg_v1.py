"""HANA FINAL -- parse the official Round 4 (single-round) and
tournament-cumulative Strokes Gained captures into per-player evidence
records, joined to player_id via the already-written FINAL truth
roster. Mirrors scripts/154/155/165/169's R1/R2/R3 SG ingestion exactly
(same raw-page shape, same regex, same identity-join discipline) --
no new parser invented.

EVIDENCE/DIAGNOSTIC ONLY, per the same standing operator instruction
already recorded for R3 SG (see 169_build_hana_r3_sg_v1.py, HANA_
2026090002_R4_SG_VALIDATION_REPORT_V1.json): Strokes Gained data for
this tournament is NEVER used as a predictive feature for the FINAL
forecast (2026090002_POST_R4_FINAL_PREVIEW.json, R1SG_R2SG model,
frozen and untouched). This script only ingests and records the real
official R4 (single round) and TotalSG (tournament-cumulative) values
for reporting/research purposes; it does not feed either the frozen
forecast or the FinalTruth artifact.

Two files share an identical "saved from url=" marker
(klpga.co.kr/web/leaderboard/strokesGained?gameCode=2026090002) because
the live page is a client-side Round/Total tab toggle -- the
distinguishing signal is which tab's table is actually populated in
each saved DOM, confirmed below via each row's own `rounds` field
(the 9th regex-captured column): the Round-4-only file's rows all show
rounds=1, while the tournament-cumulative file's rows show 1-4
(matching however many rounds each player has actually played).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

R4_SG_RAW_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R4_SG_RAW.html"
TOTAL_SG_RAW_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_TOTAL_SG_RAW.html"
FINAL_TRUTH_PATH = CONTENT / "2026090002_FINAL_TRUTH.json"

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


def _parse_sg_table(html: str) -> list[dict]:
    matches = list(_ROW_RE.finditer(html))
    rows = []
    for m in matches:
        rank, name, total, tee_to_green, off_the_tee, approach, around_green, putting, rounds = m.groups()
        rows.append({
            "sg_rank": int(rank),
            "official_display_name": name,
            "total": float(total),
            "tee_to_green": float(tee_to_green),
            "off_the_tee": float(off_the_tee),
            "approach": float(approach),
            "around_green": float(around_green),
            "putting": float(putting),
            "rounds": int(rounds),
        })
    return rows


def main() -> None:
    truth = json.loads(FINAL_TRUTH_PATH.read_text(encoding="utf-8"))
    active = [r for r in truth["records"] if r["status"] == "ACTIVE"]
    assert len(active) == 63, f"expected 63 ACTIVE FINAL finishers, got {len(active)}"
    name_to_id = {r["player_name"]: r["player_id"] for r in active}
    assert len(name_to_id) == 63, "duplicate display name in the ACTIVE FINAL roster -- name-based join unsafe"

    # ---------------- R4 (single round) SG ----------------
    r4_raw = R4_SG_RAW_PATH.read_bytes()
    r4_sha256 = hashlib.sha256(r4_raw).hexdigest()
    r4_rows = _parse_sg_table(r4_raw.decode("utf-8", errors="replace"))
    assert len(r4_rows) == 63, f"expected 63 R4 SG rows (the 63 ACTIVE FINAL finishers), got {len(r4_rows)}"
    r4_rounds_vals = {r["rounds"] for r in r4_rows}
    assert r4_rounds_vals == {1}, f"expected all R4 SG rows to report rounds=1 (single-round table), got {r4_rounds_vals}"
    r4_names = {r["official_display_name"] for r in r4_rows}
    assert r4_names == set(name_to_id), (
        f"R4 SG table names and ACTIVE roster names are not a bijection -- "
        f"only in SG: {sorted(r4_names - set(name_to_id))}, only in roster: {sorted(set(name_to_id) - r4_names)}"
    )
    r4_records = []
    for r in r4_rows:
        pid = name_to_id[r["official_display_name"]]
        r4_records.append({"player_id": pid, **r})
    assert len({r["player_id"] for r in r4_records}) == 63, "duplicate player_id after R4 SG join"

    # ---------------- TotalSG (tournament-cumulative) ----------------
    total_raw = TOTAL_SG_RAW_PATH.read_bytes()
    total_sha256 = hashlib.sha256(total_raw).hexdigest()
    total_rows = _parse_sg_table(total_raw.decode("utf-8", errors="replace"))
    total_rounds_vals = sorted({r["rounds"] for r in total_rows})
    assert set(total_rounds_vals) & {2, 3, 4} and total_rounds_vals != [1], (
        "expected TotalSG table to show a genuine cumulative (multi-round) rounds distribution, "
        "not a single-round table -- refusing to record it as TotalSG if it looks identical to the R4 table"
    )
    assert len(total_rows) != len(r4_rows) or {r["official_display_name"] for r in total_rows} != r4_names, (
        "R4 SG and TotalSG parsed to an identical player set/shape -- the two tabs may not actually differ "
        "in this capture; refusing to silently treat them as distinct evidence"
    )
    total_records = []
    for r in total_rows:
        pid = name_to_id.get(r["official_display_name"])  # may be None: TotalSG covers a wider historical population
        total_records.append({"player_id": pid, **r})

    out = {
        "schema_version": "hana_r4_sg_v1",
        "game_code": "2026090002",
        "round_number": 4,
        "as_of": "2026-09-20",
        "purpose": (
            "EVIDENCE ARTIFACT / DIAGNOSTIC / REPORTING FIELD ONLY -- per standing operator instruction "
            "(2026-09-19, first recorded in 169_build_hana_r3_sg_v1.py), Strokes Gained data for this "
            "tournament is NEVER used as a predictive feature in the production FINAL forecast "
            "(2026090002_POST_R4_FINAL_PREVIEW.json is frozen and untouched by this script)."
        ),
        "r4_single_round_sg": {
            "source_raw": {
                "path": str(R4_SG_RAW_PATH.relative_to(ROOT.parent)),
                "sha256": r4_sha256,
                "saved_from_url": "https://klpga.co.kr/web/leaderboard/strokesGained?gameCode=2026090002",
                "tab_identification": "rounds=1 for all 63 rows -- confirmed single-round (Round 4 only) tab",
            },
            "population": len(r4_records),
            "records": r4_records,
        },
        "total_cumulative_sg": {
            "source_raw": {
                "path": str(TOTAL_SG_RAW_PATH.relative_to(ROOT.parent)),
                "sha256": total_sha256,
                "saved_from_url": "https://klpga.co.kr/web/leaderboard/strokesGained?gameCode=2026090002",
                "tab_identification": f"rounds distribution {total_rounds_vals} -- confirmed tournament-cumulative (Total) tab, distinct from the R4-only tab",
            },
            "population": len(total_records),
            "population_matched_to_active_final_roster": sum(1 for r in total_records if r["player_id"] is not None),
            "records": total_records,
        },
    }

    out_path = CONTENT / "HANA_2026090002_R4_SG_V1.json"
    assert not out_path.exists(), f"refusing to overwrite existing file: {out_path}"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    print("R4 SG population:", len(r4_records))
    print("TotalSG population:", len(total_records), "matched to active FINAL roster:", out["total_cumulative_sg"]["population_matched_to_active_final_roster"])


if __name__ == "__main__":
    main()
