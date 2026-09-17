"""HANA PRE -- rebuild PLAYER_ANALYSIS_INPUT for the corrected roster
(박현경 9130 removed, 김리안 9702 added; see
141_regenerate_hana_entry_list_v2.py and the OFFICIAL_ENTRY_LIST_V2 /
ENTRY_FLAG_MATCH_V2 it produced).

Regenerates every field from raw sources for the new 108-player
population -- never hand-patches a name or a single player's record in
place. Reuses exactly the same sources and derivation rules as V1/V2:

  - k_rank: joined by player_id against the full official K-Ranking
    table (2026-W36, 756 players) via 87_collect_kranking_top120's own
    extract_full_table() parser -- same method as
    140_restore_hana_full_kranking.py. For player_id 9702 this yields
    131 (cross-checked against the repo's own archived official
    capture; note this disagrees with an operator-stated 135, which is
    NOT used here per explicit instruction to prefer the archived
    official source).
  - current_official_sg: KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1.json,
    joined by player_id. Already contains 9702 with a cross-validated
    SG record.
  - historical_sample: aggregated from
    historical_sg_warehouse_corrected_v2.json, reproducing the exact
    formula found in the pre-existing V1/V2 records for other players
    (verified against 9174/강가율's own numbers before writing this
    script): rows = count of ALL scope records for the player_id
    (cumulative + single_round, unfiltered), events = count of distinct
    (tournament, season) pairs, avg_* = simple mean over all `rows`
    records (not scope-filtered).
  - analysis_status: READY_FOR_REVIEW if current_official_sg is present,
    else DATA_INSUFFICIENT -- same rule as V1/V2.

Writes HANA_2026090002_PLAYER_ANALYSIS_INPUT_V3.json, and
HANA_2026090002_SEASON_SG_SORTED_V2.json (same season-cumulative-SG-
descending transform as V1, over the V3 population -- this second file
is indexed directly by player_id with no fallback in
139_build_hana_pre_kb_structure.py, so it must cover all 108 or the
build crashes).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

spec = importlib.util.spec_from_file_location(
    "_kranking_top120", ROOT / "scripts" / "87_collect_kranking_top120.py"
)
_kranking_top120 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_kranking_top120)


def load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def main() -> None:
    entry_v2 = load("HANA_2026090002_OFFICIAL_ENTRY_LIST_V2.json")
    entries = entry_v2["records"]
    assert len(entries) == 108
    ids = [r["player_id"] for r in entries]
    assert len(set(ids)) == 108
    assert "9130" not in ids and "9702" in ids

    raw_html = (CONTENT / "incoming_evidence" / "2026090003" / "KLPGA_KRANKING_2026_W36_RAW.html").read_text(encoding="utf-8")
    full_table = _kranking_top120.extract_full_table(raw_html)
    k_by_id = {r["player_id"]: r for r in full_table}

    sg_capture = load("KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1.json")
    sg_by_id = {p["player_id"]: p for p in sg_capture["players"]}

    warehouse = load("historical_sg_warehouse_corrected_v2.json")
    hist_by_id: dict[str, list[dict]] = {}
    for r in warehouse["records"]:
        hist_by_id.setdefault(r.get("player_id"), []).append(r)

    records = []
    for e in entries:
        pid = e["player_id"]
        k = k_by_id.get(pid)
        sg = sg_by_id.get(pid)
        hist_recs = hist_by_id.get(pid, [])

        current_official_sg = None
        if sg is not None:
            current_official_sg = {
                "total": sg["sg_total"], "ott": sg["sg_ott"], "app": sg["sg_app"],
                "arg": sg["sg_arg"], "putt": sg["sg_putt"], "rounds": sg["measured_rounds"],
                "source_capture": "KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1.json",
                "identity_match": "player_id",
            }

        historical_sample = None
        if hist_recs:
            events = len({(r.get("tournament"), r.get("season")) for r in hist_recs})
            def avg(field):
                vals = [r.get(field) for r in hist_recs if r.get(field) is not None]
                return round(sum(vals) / len(vals), 3) if vals else None
            historical_sample = {
                "rows": len(hist_recs), "events": events,
                "avg_total": avg("total"), "avg_ott": avg("off_the_tee"),
                "avg_app": avg("approach"), "avg_arg": avg("around_green"),
                "avg_putt": avg("putting"),
            }

        records.append({
            "player_id": pid,
            "official_display_name": e["official_display_name"],
            "entry_category": e["entry_category"],
            "k_rank": k["official_k_rank"] if k else None,
            "k_name": k["player_name"] if k else None,
            "current_official_sg": current_official_sg,
            "historical_sample": historical_sample,
            "analysis_status": "READY_FOR_REVIEW" if current_official_sg is not None else "DATA_INSUFFICIENT",
        })

    v1 = load("HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1.json")
    out = {
        "schema_version": "neo_hana_player_analysis_input_v3",
        "game_code": v1["game_code"],
        "tournament_name": v1["tournament_name"],
        "as_of": "2026-09-16",
        "purpose": v1["purpose"],
        "sources": [
            "HANA_2026090002_OFFICIAL_ENTRY_LIST_V2.json",
            "KLPGA_KRANKING_2026_W36_RAW.html (full 756-player official table)",
            "KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1.json",
            "historical_sg_warehouse_corrected_v2.json",
        ],
        "roster_change_from_v1": {"removed": [{"player_id": "9130", "name": "박현경"}],
                                   "added": [{"player_id": "9702", "name": "김리안"}]},
        "kranking_9702_note": "official archived K-Ranking capture (2026-W36) shows 131; "
                               "an operator-stated 135 was NOT used -- see 140/141/142 provenance.",
        "coverage": {
            "players": len(records),
            "k_rank": sum(1 for r in records if r["k_rank"] is not None),
            "current_official_sg": sum(1 for r in records if r["current_official_sg"] is not None),
            "historical": sum(1 for r in records if r["historical_sample"] is not None),
            "ready_for_review": sum(1 for r in records if r["analysis_status"] == "READY_FOR_REVIEW"),
            "data_insufficient": sum(1 for r in records if r["analysis_status"] == "DATA_INSUFFICIENT"),
        },
        "publication_gate": v1["publication_gate"],
        "records": records,
    }
    out_path = CONTENT / "HANA_2026090002_PLAYER_ANALYSIS_INPUT_V3.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["coverage"], ensure_ascii=False))
    r9702 = next(r for r in records if r["player_id"] == "9702")
    print("9702:", json.dumps(r9702, ensure_ascii=False))
    print("wrote", out_path)

    # ---- SEASON_SG_SORTED_V2 -- same transform as V1: season cumulative
    # SG total descending, missing KLPGA SG last as 데이터 부족. Directly
    # indexed by player_id (by_id_sg[pid], no .get()) in
    # 139_build_hana_pre_kb_structure.py, so it must cover all 108.
    sg1 = load("HANA_2026090002_SEASON_SG_SORTED_V1.json")
    confirmed = sorted(
        (r for r in records if r["current_official_sg"] is not None),
        key=lambda r: -r["current_official_sg"]["total"],
    )
    insufficient = [r for r in records if r["current_official_sg"] is None]
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
        "schema_version": sg1["schema_version"],
        "game_code": sg1["game_code"],
        "tournament_name": sg1["tournament_name"],
        "as_of": "2026-09-16",
        "sort_rule": sg1["sort_rule"],
        "source_input": "HANA_2026090002_PLAYER_ANALYSIS_INPUT_V3.json",
        "coverage": {
            "total_players": len(sorted_records),
            "sg_confirmed": len(confirmed),
            "data_insufficient": len(insufficient),
            "foreign_or_amateur_not_converted": True,
        },
        "records": sorted_records,
    }
    sg_out_path = CONTENT / "HANA_2026090002_SEASON_SG_SORTED_V2.json"
    sg_out_path.write_text(json.dumps(sg_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(sg_out["coverage"], ensure_ascii=False))
    print("wrote", sg_out_path)


if __name__ == "__main__":
    main()
