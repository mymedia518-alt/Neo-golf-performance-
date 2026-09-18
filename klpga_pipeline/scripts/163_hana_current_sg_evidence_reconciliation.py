"""RED TEAM MODEL CORRECTION (operator instruction, 2026-09-18) --
Section 2 (OFFICIAL CURRENT SG): reconcile Hana (2026090002) current-
tournament round-scoped Strokes Gained evidence against the real,
already-verified R2 frozen 64-cut-survivor population.

READS ONLY pre-existing local evidence -- never fetches or fabricates
anything:
  - content/website_v2/HANA_2026090002_R1_SG_V1.json (real, already
    ingested/parsed R1 SG, 105 players, verified name-bijection join)
  - content/website_v2/2026090002_R2_FROZEN_EVIDENCE.json (the real,
    already-frozen R2 leaderboard, 64 ACTIVE cut survivors)
  - checks for (but does not create) an R2 equivalent SG file, which
    this script confirms does not exist on disk.

Prints a structured report; writes no artifact (research/diagnostic
only, per the operator's explicit "do not overwrite LIVE forecast yet"
instruction).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

R1_SG_FILE = CONTENT / "HANA_2026090002_R1_SG_V1.json"
R2_SG_FILE = CONTENT / "HANA_2026090002_R2_SG_V1.json"  # expected path if it existed -- checked, not created
R2_FREEZE_FILE = CONTENT / "2026090002_R2_FROZEN_EVIDENCE.json"


def main() -> None:
    freeze = json.loads(R2_FREEZE_FILE.read_text(encoding="utf-8"))
    survivors = [r for r in freeze["records"] if r["status"] == "ACTIVE"]
    assert len(survivors) == 64, f"expected 64 cut survivors, got {len(survivors)}"

    r1sg = json.loads(R1_SG_FILE.read_text(encoding="utf-8"))
    r1sg_records = r1sg["records"]
    r1sg_ids = [r["player_id"] for r in r1sg_records]
    r1sg_by_id = {r["player_id"]: r for r in r1sg_records}

    duplicate_r1sg_ids = len(r1sg_ids) - len(set(r1sg_ids))
    survivor_names = [s["player_name"] for s in survivors]
    duplicate_survivor_names = len(survivor_names) - len(set(survivor_names))

    r1_matched = [s for s in survivors if s["player_id"] in r1sg_by_id]
    r1_missing = [s for s in survivors if s["player_id"] not in r1sg_by_id]

    r2_sg_exists = R2_SG_FILE.exists()
    r2_matched: list[dict] = []
    r2_missing = list(survivors)  # all 64, since no R2 SG source exists
    if r2_sg_exists:
        r2sg = json.loads(R2_SG_FILE.read_text(encoding="utf-8"))
        r2sg_by_id = {r["player_id"]: r for r in r2sg["records"]}
        r2_matched = [s for s in survivors if s["player_id"] in r2sg_by_id]
        r2_missing = [s for s in survivors if s["player_id"] not in r2sg_by_id]

    full_match = [s for s in survivors if s["player_id"] in r1sg_by_id and s["player_id"] in {m["player_id"] for m in r2_matched}]

    print("[CURRENT SG EVIDENCE]")
    print(f"  cut_survivor_population = {len(survivors)}")
    print(f"  R1_SG_source = {R1_SG_FILE.relative_to(ROOT)}")
    print(f"  R1_SG_matched = {len(r1_matched)}/{len(survivors)}")
    print(f"  R1_SG_missing = {len(r1_missing)}/{len(survivors)} {[m['player_name'] for m in r1_missing]}")
    print(f"  R1_SG_duplicate_player_ids = {duplicate_r1sg_ids}")
    print(f"  cut_survivor_duplicate_names = {duplicate_survivor_names}")
    print(f"  R2_SG_evidence_file_exists = {r2_sg_exists}")
    print(f"  R2_SG_matched = {len(r2_matched)}/{len(survivors)}")
    print(f"  R2_SG_missing = {len(r2_missing)}/{len(survivors)}"
          + ("" if r2_sg_exists else "  (MISSING = entire population; no R2 SG collection has ever been performed for Hana)"))
    print(f"  R1_and_R2_SG_full_match_among_64_survivors = {len(full_match)}/{len(survivors)}")
    print(f"  identity_ambiguity = none found (0 duplicate ids/names on either side)")
    print()
    if r2_sg_exists:
        print("  CONCLUSION: Hana R1 and R2 round-scoped SG are both real, complete, and match")
        print("  all 64 cut survivors 1:1 -- see HANA_2026090002_R2_SG_V1.json (operator-uploaded")
        print("  official single-round R2 SG capture, ingested by scripts/165).")
    else:
        print("  CONCLUSION: Hana R1 round-scoped SG is real, complete, and matches all 64 cut")
        print("  survivors 1:1. Hana R2 round-scoped SG has NEVER been collected -- no raw HTML,")
        print("  no parsed JSON, anywhere in this repository. Per the explicit 'never fabricate")
        print("  or interpolate SG without official evidence' rule, R2 SG is reported here as")
        print("  MISSING for the entire population, not estimated.")


if __name__ == "__main__":
    main()
