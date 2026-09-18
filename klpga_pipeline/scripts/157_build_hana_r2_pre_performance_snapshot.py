"""Build 2026090002_PRE_PERFORMANCE_SNAPSHOT.json for Hana (하나금융그룹
챔피언십) by calling the SAME already-existing, generic
scripts/67_build_ok_open_pre_performance.py::build() used to produce
KB (2026090003)'s own snapshot -- zero new statistical/modeling logic.

Prerequisite gap: build() requires context.artifact_path("entry_snapshot")
(schema: {"entries": [{"player_id", "player_name", ...}, ...]}), which
Hana's own PRE-stage pipeline (scripts/130+) never produced under that
generic name -- it wrote HANA_2026090002_OFFICIAL_ENTRY_LIST_V2.json
instead, with different field names (official_display_name,
entry_category). This script performs ONLY a pure field-name adapter
over that already-verified real entry list (same 108 real players,
same real identities -- no re-collection, no new data) and writes it
to the generic entry_snapshot path so build() can run unmodified.

Leakage safety is verified explicitly before running build(): prints
historical_sg_warehouse.json's max event date/game_code and confirms
it predates Hana's real start_date (2026-09-17, OFFICIAL_KLPGA_
SCHEDULE.json) -- the same warehouse file, unchanged, already used for
Hana's PRE (script 130) and R1 (script 149) stages.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.tournament_context import load_tournament_context  # noqa: E402

GAME_CODE = "2026090002"
CONTENT = ROOT / "content" / "website_v2"
ENTRY_LIST_SOURCE = CONTENT / "HANA_2026090002_OFFICIAL_ENTRY_LIST_V2.json"
WAREHOUSE = CONTENT / "historical_sg_warehouse.json"


def _verify_leakage_safety(context) -> None:
    warehouse = json.loads(WAREHOUSE.read_text(encoding="utf-8"))
    dates = [r.get("date") for r in warehouse["records"] if r.get("date")]
    retrieved = [r.get("retrieved_at") for r in warehouse["records"] if r.get("retrieved_at")]
    max_date = max(dates) if dates else None
    max_retrieved = max(retrieved) if retrieved else None
    game_codes_in_warehouse = sorted({str(r.get("game_code")) for r in warehouse["records"]})
    print(f"[LEAKAGE CHECK] historical_sg_warehouse.json generated_at={warehouse.get('generated_at')!r}")
    print(f"[LEAKAGE CHECK] max per-record date field={max_date!r}, max retrieved_at={max_retrieved!r}")
    print(f"[LEAKAGE CHECK] Hana own game_code {GAME_CODE!r} present in warehouse: {GAME_CODE in game_codes_in_warehouse}")
    print(f"[LEAKAGE CHECK] KB game_code 2026090003 present in warehouse: {'2026090003' in game_codes_in_warehouse}")
    print(f"[LEAKAGE CHECK] Hana context.start_date={context.start_date!r} (this is the CUTOFF script 67 will use)")
    if GAME_CODE in game_codes_in_warehouse:
        raise RuntimeError(f"REFUSING: warehouse contains Hana's own game_code {GAME_CODE!r} -- leakage risk")
    if max_date is not None and max_date >= context.start_date:
        raise RuntimeError(
            f"REFUSING: warehouse max per-record date {max_date!r} >= Hana start_date {context.start_date!r} -- leakage risk"
        )
    print("[LEAKAGE CHECK] PASS -- warehouse predates Hana's start_date; same file already used for Hana PRE/R1 unchanged")


def _write_entry_snapshot_adapter(context) -> Path:
    out_path = context.artifact_path("entry_snapshot")
    if out_path.exists():
        print(f"[ADAPTER] {out_path} already exists -- not overwriting (immutable-once-written)")
        return out_path
    source = json.loads(ENTRY_LIST_SOURCE.read_text(encoding="utf-8"))
    records = source["records"]
    entries = [
        {
            "player_id": str(r["player_id"]),
            "player_name": r["official_display_name"],
            "entry_status": "listed",
            "nationality": None,
            "qualification_category": r.get("entry_category"),
            "qualification_reason": None,
            "identity_match": None,
            "canonical_name": None,
        }
        for r in records
    ]
    payload = {
        "schema_version": "neo_tournament_entry_v1",
        "game_code": context.game_code,
        "retrieved_at": source.get("source", {}).get("retrieved_at") if isinstance(source.get("source"), dict) else None,
        "source_url": f"https://klpga.co.kr/web/tourInfo/entry?gameCode={context.game_code}",
        "collection_method": "field_name_adapter_over_verified_real_entry_list",
        "source_description": f"pure field-rename over already-verified {ENTRY_LIST_SOURCE.name} ({len(records)} real official entrants) -- no new data collected",
        "player_count": len(entries),
        "parser_unparsed_rows": 0,
        "duplicate_player_ids": [],
        "unresolved_player_ids": [],
        "withdrawals_marked_by_source": [],
        "identity_matched": "not attempted (adapter over already-identity-resolved Hana entry list)",
        "entries": entries,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"[ADAPTER] wrote {out_path} with {len(entries)} entries (adapted from {ENTRY_LIST_SOURCE.name})")
    return out_path


def main():
    context = load_tournament_context(GAME_CODE)
    print(f"[CONTEXT] {context.game_code} {context.tournament_name} start_date={context.start_date} final_round_number={context.final_round_number}")
    _verify_leakage_safety(context)
    _write_entry_snapshot_adapter(context)

    snap_path = context.artifact_path("pre_performance_snapshot")
    if snap_path.exists():
        print(f"[SNAPSHOT] {snap_path} already exists (immutable) -- not rebuilding")
    else:
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_ok_open_pre_performance", ROOT / "scripts" / "67_build_ok_open_pre_performance.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        summary = mod.build(GAME_CODE)
        print(f"[SNAPSHOT] built via scripts/67 build({GAME_CODE!r}): {json.dumps(summary, ensure_ascii=False)}")

    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    print(f"[VERIFY] snapshot cutoff={snapshot.get('cutoff')!r} profiles={len(snapshot.get('profiles', []))}")
    coverage_counts = {}
    for p in snapshot["profiles"]:
        coverage_counts[p["coverage"]] = coverage_counts.get(p["coverage"], 0) + 1
    print(f"[VERIFY] coverage breakdown: {coverage_counts}")


if __name__ == "__main__":
    main()
