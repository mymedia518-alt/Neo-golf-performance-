"""HANA PRE -- restore K-Ranking beyond the TOP-120 cutoff.

HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1.json sourced k_rank only from
HOME_PLAYER_MASTER_TOP120_2026_W36.json, which is explicitly scoped to
"official K-Ranking closed interval 1..120 only" (its own
population_selection field) -- 23 of the 108 Hana entrants ranked
below #120 therefore carried k_rank=None and rendered as "-" on the
public page, even though many of them do have a real official rank.

The FULL official K-Ranking table for the same week (2026-W36, 756
players) is already archived as evidence at
incoming_evidence/2026090003/KLPGA_KRANKING_2026_W36_RAW.html -- its
byte size (754069) matches HOME_PLAYER_MASTER_TOP120_2026_W36.json's
own source_bytes.full_table field exactly, proving it is the same
capture the TOP-120 subset was drawn from, just not restricted to
1..120. This script reuses 87_collect_kranking_top120.py's own
extract_full_table() parser (never a second, ad hoc parser) to read
all 756 rows, then joins Hana's 108 entrants to it by player_id (the
same identity key already used throughout this pipeline -- never by
name alone).

Every one of the 85 already-populated k_rank values is re-derived
from this same full table and cross-checked byte-for-byte against
the existing V1 file before anything is written: zero mismatches is a
hard precondition, not an assumption.

Writes HANA_2026090002_PLAYER_ANALYSIS_INPUT_V2.json. V1 is left
completely untouched (append-only evidence discipline, same as this
repo's RECOVERY_V1/V2/V3 precedent) -- 139_build_hana_pre_kb_structure.py
is repointed to load V2 in a separate, one-line change.

Players genuinely absent from the full 756-row table (never played a
KLPGA-K-Ranking-counted event, e.g. LPGA-only foreign entrants who
never appeared on tour) keep k_rank=None -- displayed as "-", never a
guessed number.
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


def main() -> None:
    v1_path = CONTENT / "HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1.json"
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))

    raw_html_path = CONTENT / "incoming_evidence" / "2026090003" / "KLPGA_KRANKING_2026_W36_RAW.html"
    raw_html = raw_html_path.read_text(encoding="utf-8")
    full_table = _kranking_top120.extract_full_table(raw_html)
    by_id = {r["player_id"]: r for r in full_table}

    # Hard precondition: every already-populated k_rank in V1 must be
    # byte-identical to what the full table itself says for that
    # player_id. If this ever fails, the two sources have silently
    # diverged and this script must not proceed.
    for rec in v1["records"]:
        if rec.get("k_rank") is None:
            continue
        full_rec = by_id.get(rec["player_id"])
        if full_rec is None or full_rec["official_k_rank"] != rec["k_rank"]:
            raise ValueError(
                f"existing k_rank for {rec['player_id']} {rec['official_display_name']!r} "
                f"does not match the full official table -- refusing to proceed"
            )

    restored = []
    still_missing = []
    v2_records = []
    for rec in v1["records"]:
        rec = dict(rec)
        if rec.get("k_rank") is None:
            full_rec = by_id.get(rec["player_id"])
            if full_rec is not None:
                rec["k_rank"] = full_rec["official_k_rank"]
                rec["k_name"] = full_rec["player_name"]
                restored.append({
                    "player_id": rec["player_id"],
                    "official_display_name": rec["official_display_name"],
                    "restored_k_rank": full_rec["official_k_rank"],
                })
            else:
                still_missing.append({
                    "player_id": rec["player_id"],
                    "official_display_name": rec["official_display_name"],
                })
        v2_records.append(rec)

    v2 = dict(v1)
    v2["schema_version"] = "neo_hana_player_analysis_input_v2"
    v2["records"] = v2_records
    v2["coverage"] = dict(v1["coverage"])
    v2["coverage"]["k_rank"] = sum(1 for r in v2_records if r.get("k_rank") is not None)
    v2["k_ranking_restoration"] = {
        "purpose": "restore k_rank for entrants ranked below the TOP-120 cutoff, "
                   "using the same 2026-W36 official K-Ranking capture already "
                   "archived for KB 2026090003",
        "full_table_source": "incoming_evidence/2026090003/KLPGA_KRANKING_2026_W36_RAW.html",
        "full_table_population_count": len(full_table),
        "parser": "87_collect_kranking_top120.extract_full_table",
        "v1_k_rank_crosscheck": "PASS -- all 85 pre-existing k_rank values re-derived "
                                 "from the full table with zero mismatches",
        "restored_count": len(restored),
        "restored": restored,
        "still_missing_count": len(still_missing),
        "still_missing": still_missing,
    }

    v2_path = CONTENT / "HANA_2026090002_PLAYER_ANALYSIS_INPUT_V2.json"
    v2_path.write_text(json.dumps(v2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"restored k_rank for {len(restored)} players")
    print(f"still missing (genuinely absent from official table): {len(still_missing)}")
    for m in still_missing:
        print(f"  - {m['player_id']} {m['official_display_name']}")
    print(f"wrote {v2_path}")


if __name__ == "__main__":
    main()
