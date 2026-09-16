"""HANA PRE -- refresh K-Ranking for all 108 entrants from a newer official
KLPGA K-Ranking capture (2026-09-16 upload), superseding the 2026-W36
archived table used by 140/142.

Background: 16 named players were reported as having K-Ranking values
that disagreed with an operator's expectation. Direct re-verification
against the repo's archived W36 capture confirmed the CURRENT build
values matched that W36 source exactly (0 mismatches) -- so nothing was
"missing"; the operator was simply looking at a later snapshot. A fresh
official capture was then supplied (saved-from-url confirmed as the same
klpga.co.kr/web/record/publicRecordDetail page), archived here unmodified
as KLPGA_KRANKING_2026_LATEST_V2_RAW.html (W36 file untouched, preserved
for history). Parsing the new capture with the SAME existing parser
(87_collect_kranking_top120.extract_full_table -- never a new/ad hoc
parser) reproduced the operator's 16 numbers exactly, and showed 646 of
741 common player_ids differ from the W36 table -- i.e. this is a whole
newer snapshot, not a 16-player patch. Per explicit instruction, this
script re-derives K-Ranking for the full 108-player Hana field from this
one new snapshot only (never a per-player mix of old/new sources).

Everything else about each player (current_official_sg, historical_sample,
analysis_status, entry_category, official_display_name) is carried
forward unchanged from PLAYER_ANALYSIS_INPUT_V3.json -- only k_rank/
k_name are re-sourced. Matching is by player_id only, never by name.

Writes HANA_2026090002_PLAYER_ANALYSIS_INPUT_V4.json and
HANA_2026090002_SEASON_SG_SORTED_V3.json (same SG-descending transform
as V1/V2, over the V4 population -- 139_build_hana_pre_kb_structure.py
indexes this by player_id with no .get() fallback, so it must cover all
108). V3/SORTED_V2 are left untouched (append-only evidence discipline).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

spec = importlib.util.spec_from_file_location(
    "_kranking_top120", ROOT / "scripts" / "87_collect_kranking_top120.py"
)
_kranking_top120 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_kranking_top120)

NEW_RAW_PATH = CONTENT / "incoming_evidence" / "2026090002" / "KLPGA_KRANKING_2026_LATEST_V2_RAW.html"
OLD_RAW_PATH = CONTENT / "incoming_evidence" / "2026090003" / "KLPGA_KRANKING_2026_W36_RAW.html"


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def main() -> None:
    v3 = load("HANA_2026090002_PLAYER_ANALYSIS_INPUT_V3.json")
    records_v3 = v3["records"]
    assert len(records_v3) == 108
    ids = [r["player_id"] for r in records_v3]
    assert len(set(ids)) == 108, "duplicate player_id in V3 population"
    assert "9130" not in ids, "박현경 (9130) must remain absent -- not in the official entry list"
    assert "9702" in ids, "김리안 (9702) must be present"

    new_html = NEW_RAW_PATH.read_text(encoding="utf-8")
    old_html = OLD_RAW_PATH.read_text(encoding="utf-8")
    new_table = _kranking_top120.extract_full_table(new_html)
    old_table = _kranking_top120.extract_full_table(old_html)
    new_by_id = {r["player_id"]: r for r in new_table}
    old_by_id = {r["player_id"]: r for r in old_table}
    print(f"new capture: {len(new_table)} players, old (W36) capture: {len(old_table)} players")

    records_v4 = []
    changed = []
    unchanged_with_rank = []
    newly_absent = []
    newly_present = []
    still_absent = []
    for rec in records_v3:
        pid = rec["player_id"]
        new_k = new_by_id.get(pid)
        old_rank = rec.get("k_rank")
        new_rank = new_k["official_k_rank"] if new_k else None
        new_name = new_k["player_name"] if new_k else None

        out = dict(rec)
        out["k_rank"] = new_rank
        out["k_name"] = new_name
        records_v4.append(out)

        if old_rank is None and new_rank is None:
            still_absent.append((pid, rec["official_display_name"]))
        elif old_rank is None and new_rank is not None:
            newly_present.append((pid, rec["official_display_name"], new_rank))
        elif old_rank is not None and new_rank is None:
            newly_absent.append((pid, rec["official_display_name"], old_rank))
        elif old_rank != new_rank:
            changed.append((pid, rec["official_display_name"], old_rank, new_rank))
        else:
            unchanged_with_rank.append((pid, rec["official_display_name"], old_rank))

    # hard preconditions before writing anything
    r9702 = next(r for r in records_v4 if r["player_id"] == "9702")
    assert r9702["k_rank"] == 135, f"김리안 expected 135 from the new capture, got {r9702['k_rank']}"
    assert all(r["player_id"] != "9130" for r in records_v4), "박현경 must not appear"
    assert len(records_v4) == 108
    assert len({r["player_id"] for r in records_v4}) == 108

    out = dict(v3)
    out["schema_version"] = "neo_hana_player_analysis_input_v4"
    out["as_of"] = "2026-09-16"
    out["sources"] = v3["sources"] + [
        "KLPGA_KRANKING_2026_LATEST_V2_RAW.html (newer official K-Ranking capture, supersedes W36 for k_rank only)",
    ]
    out["kranking_refresh_v4"] = {
        "purpose": "replace k_rank/k_name for all 108 Hana entrants from a single newer official "
                   "K-Ranking capture (never a per-player mix of old/new snapshots)",
        "new_capture_path": str(NEW_RAW_PATH.relative_to(ROOT.parent)),
        "new_capture_population_count": len(new_table),
        "old_capture_path": str(OLD_RAW_PATH.relative_to(ROOT.parent)),
        "old_capture_preserved_unmodified": True,
        "parser": "87_collect_kranking_top120.extract_full_table (same existing parser, not ad hoc)",
        "matched_by": "player_id only, never by name",
        "kim_rian_9702_check": "135 (was 131 under W36) -- PASS",
        "park_hyun_kyung_9130_check": "absent from entry list, 0 records -- PASS",
        "changed_count": len(changed),
        "newly_present_count": len(newly_present),
        "newly_absent_count": len(newly_absent),
        "unchanged_count": len(unchanged_with_rank),
        "still_absent_count": len(still_absent),
    }
    out["coverage"] = {
        "players": len(records_v4),
        "k_rank": sum(1 for r in records_v4 if r["k_rank"] is not None),
        "current_official_sg": sum(1 for r in records_v4 if r["current_official_sg"] is not None),
        "historical": sum(1 for r in records_v4 if r["historical_sample"] is not None),
        "ready_for_review": sum(1 for r in records_v4 if r["analysis_status"] == "READY_FOR_REVIEW"),
        "data_insufficient": sum(1 for r in records_v4 if r["analysis_status"] == "DATA_INSUFFICIENT"),
    }
    out["records"] = records_v4

    out_path = CONTENT / "HANA_2026090002_PLAYER_ANALYSIS_INPUT_V4.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("coverage:", json.dumps(out["coverage"], ensure_ascii=False))
    print("wrote", out_path)

    print()
    print(f"changed (W36 -> new): {len(changed)}")
    for pid, name, o, n in sorted(changed, key=lambda x: x[3]):
        print(f"  {pid:>6} {name:20s} {o} -> {n}")
    print(f"newly present (was '-', now ranked): {len(newly_present)}")
    for pid, name, n in newly_present:
        print(f"  {pid:>6} {name:20s} -> {n}")
    print(f"newly absent (was ranked, now '-'): {len(newly_absent)}")
    for pid, name, o in newly_absent:
        print(f"  {pid:>6} {name:20s} {o} -> -")
    print(f"still absent from both captures: {len(still_absent)}")
    for pid, name in still_absent:
        print(f"  {pid:>6} {name}")
    print(f"unchanged (same rank in both): {len(unchanged_with_rank)}")

    # ---- SEASON_SG_SORTED_V3 -- same transform as V1/V2, over V4 population.
    # Directly indexed by player_id (by_id_sg[pid], no .get()) in
    # 139_build_hana_pre_kb_structure.py, so it must cover all 108.
    sg2 = load("HANA_2026090002_SEASON_SG_SORTED_V2.json")
    confirmed = sorted(
        (r for r in records_v4 if r["current_official_sg"] is not None),
        key=lambda r: -r["current_official_sg"]["total"],
    )
    insufficient = [r for r in records_v4 if r["current_official_sg"] is None]
    sorted_records = []
    for i, r in enumerate(confirmed, 1):
        rr = dict(r)
        rr["season_sg_status"] = "확인"
        rr["season_sg_rank"] = i
        sorted_records.append(rr)
    for r in insufficient:
        rr = dict(r)
        rr["season_sg_status"] = "데이터 부족"
        rr["season_sg_rank"] = None
        sorted_records.append(rr)

    sg_out = {
        "schema_version": sg2["schema_version"],
        "game_code": sg2["game_code"],
        "tournament_name": sg2["tournament_name"],
        "as_of": "2026-09-16",
        "sort_rule": sg2["sort_rule"],
        "source_input": "HANA_2026090002_PLAYER_ANALYSIS_INPUT_V4.json",
        "coverage": {
            "total_players": len(sorted_records),
            "sg_confirmed": len(confirmed),
            "data_insufficient": len(insufficient),
            "foreign_or_amateur_not_converted": True,
        },
        "records": sorted_records,
    }
    sg_out_path = CONTENT / "HANA_2026090002_SEASON_SG_SORTED_V3.json"
    sg_out_path.write_text(json.dumps(sg_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print()
    print("SG sorted coverage:", json.dumps(sg_out["coverage"], ensure_ascii=False))
    print("wrote", sg_out_path)


if __name__ == "__main__":
    main()
