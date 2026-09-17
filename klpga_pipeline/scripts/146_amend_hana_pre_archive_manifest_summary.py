"""HANA PRE archive -- additive amendment of PRE_ARCHIVE_MANIFEST_V1.json
with the dataset-level summary facts an operator explicitly asked to have
recorded in it: game_code, total player-field size, the count of players
whose 경기력 band renders as "데이터 부족" on the live PRE page, 김리안's
k_rank, and 박현경's excluded status.

Per docs/OPERATING_RULES.md rule 3 ("a manifest may be amended, never
rewritten"): every field the manifest already has (base_commit, the 21
per-file sha256 records, file_count, etc.) is read back unchanged and
rewritten byte-for-byte identical; this script only ADDS one new
top-level key, "dataset_summary", and hard-asserts every value in it
against the ALREADY-ARCHIVED copies of the source files (never the live
working tree) so the amendment stays pinned to the same base_commit the
rest of the manifest is pinned to.

Provenance of the two numbers that need a non-trivial computation:

- 108 players: len(records) in the archived PLAYER_ANALYSIS_INPUT_V4.json.
- "데이터 부족" band count (8): 139_build_hana_pre_kb_structure.py's own
  `insufficient` boolean (see its main(), row-building loop) is
  `rec["analysis_status"] != "PASS" or pid in amateur_kga_insufficient_ids`
  -- i.e. an M4-PASS-status test OR the 3 amateur entrants forced to
  DATA_INSUFFICIENT per HANA_2026090002_AMATEUR_KGA_ANALYSIS_V1.json.
  This is the number actually rendered as "데이터 부족" in the band
  column on the live page -- distinct from PLAYER_ANALYSIS_INPUT_V4's
  own broader `coverage.data_insufficient` count (13), which measures a
  different thing (season SG data availability, not the rendered M4
  band). Both are real, verifiable numbers; this script records the one
  the operator asked for (the rendered band count) and notes the
  distinction explicitly in the output so the two are never confused
  later.

This script is idempotent-refusing, not idempotent: it hard-asserts the
manifest does not already carry a "dataset_summary" key, so it can only
ever run once against a given manifest (consistent with the "never
overwrite" discipline -- a second, different amendment would need its
own new key, never a silent overwrite of this one).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_PRE = ROOT / "content" / "website_v2" / "archive" / "2026090002" / "pre"
ARCHIVE_CONTENT = ARCHIVE_PRE / "klpga_pipeline" / "content" / "website_v2"
MANIFEST_PATH = ARCHIVE_PRE / "PRE_ARCHIVE_MANIFEST_V1.json"


def _load_archived(name: str) -> dict:
    return json.loads((ARCHIVE_CONTENT / name).read_text(encoding="utf-8"))


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert "dataset_summary" not in manifest, "manifest already amended -- refusing to run again"

    player_input = _load_archived("HANA_2026090002_PLAYER_ANALYSIS_INPUT_V4.json")
    m4 = _load_archived("HANA_2026090002_PRE_M4_60000_CANDIDATE_V2.json")
    amateur = _load_archived("HANA_2026090002_AMATEUR_KGA_ANALYSIS_V1.json")

    records = player_input["records"]
    total_players = len(records)
    assert total_players == 108, f"expected 108 players in archived PLAYER_ANALYSIS_INPUT_V4.json, got {total_players}"
    assert len({r["player_id"] for r in records}) == 108, "duplicate player_id in archived population"

    kim_rian = next((r for r in records if r["player_id"] == "9702"), None)
    assert kim_rian is not None, "김리안 (9702) missing from archived population"
    assert kim_rian["k_rank"] == 135, f"김리안 expected k_rank 135, archived value is {kim_rian['k_rank']}"

    assert all(r["player_id"] != "9130" for r in records), "박현경 (9130) must remain absent from archived population"

    # same boolean 139_build_hana_pre_kb_structure.py uses to decide the
    # rendered band column -- see this script's module docstring
    amateur_forced_ids = {r["player_id"] for r in amateur["records"] if r["decision"] == "DATA_INSUFFICIENT"}
    band_insufficient_ids = [
        r["playerCode"] for r in m4["records"]
        if r["analysis_status"] != "PASS" or r["playerCode"] in amateur_forced_ids
    ]
    assert len(band_insufficient_ids) == 8, (
        f"expected 8 players with rendered band '데이터 부족', got {len(band_insufficient_ids)}: {band_insufficient_ids}"
    )
    assert len(set(band_insufficient_ids)) == 8, "duplicate player_id in band-insufficient set"

    manifest["dataset_summary"] = {
        "game_code": "2026090002",
        "total_players": total_players,
        "band_insufficient_count": len(band_insufficient_ids),
        "band_insufficient_player_ids": sorted(band_insufficient_ids, key=int),
        "band_insufficient_note": (
            "count of players whose 경기력 band renders as '데이터 부족' on the "
            "live PRE page (139_build_hana_pre_kb_structure.py's `insufficient` "
            "boolean: M4 analysis_status != PASS, OR forced by "
            "HANA_2026090002_AMATEUR_KGA_ANALYSIS_V1.json) -- distinct from "
            "PLAYER_ANALYSIS_INPUT_V4.json's own coverage.data_insufficient "
            "(13), which measures season-SG data availability, a different "
            "metric. Both numbers are independently real; this one is the "
            "rendered-band count."
        ),
        "kim_rian_9702_k_rank": 135,
        "park_hyun_kyung_9130_status": "excluded (absent from the official 108-player entry list)",
        "verified_against": "the already-archived copies of PLAYER_ANALYSIS_INPUT_V4.json, "
                             "PRE_M4_60000_CANDIDATE_V2.json and AMATEUR_KGA_ANALYSIS_V1.json "
                             "under this same archive directory -- never the live working tree",
        "amended_at_utc": "2026-09-17T00:00:00Z",
    }

    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("amended", MANIFEST_PATH)
    print(json.dumps(manifest["dataset_summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
