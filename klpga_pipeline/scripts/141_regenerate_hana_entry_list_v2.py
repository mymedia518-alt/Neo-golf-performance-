"""HANA PRE -- regenerate the official entry list from the updated
roster capture (2026-09-16): 박현경 9130 removed, 김리안 9702 added.

Parses incoming_evidence/2026090002/HANA_2026090002_ENTRY_LIST_RAW_V2.html
(the newer of two official KLPGA entry-page captures -- confirmed via
its own <!-- saved from url=... --> marker pointing at the same
gameCode=2026090002 entry page) through the repo's existing, already-
tested klpga.parsers.entry_list_parser -- never a new/ad hoc parser,
never a hand patch of a player name in generated HTML.

Writes V2 of both derived files, preserving V1 as historical record of
the prior roster (repo's established RECOVERY_V1/V2/V3 evidence
discipline):
  - HANA_2026090002_OFFICIAL_ENTRY_LIST_V2.json
  - HANA_2026090002_ENTRY_FLAG_MATCH_V2.json
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.parsers.entry_list_parser import parse_entry_list_html, parse_entry_summary  # noqa: E402

RAW_HTML_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_ENTRY_LIST_RAW_V2.html"
ENTRY_URL = "https://klpga.co.kr/web/tourInfo/entry?gameCode=2026090002"

_CATEGORY_MAP = {"자격자": "eligible", "추천자": "recommended", "초청자": "invited"}


def main() -> None:
    html = RAW_HTML_PATH.read_text(encoding="utf-8")
    assert f"saved from url=(0058){ENTRY_URL}" in html, "raw HTML source-URL marker does not match the Hana entry page"
    raw_sha256 = hashlib.sha256(RAW_HTML_PATH.read_bytes()).hexdigest()

    summary = parse_entry_summary(html)
    result = parse_entry_list_html(html)

    assert result.unparsed_row_count == 0, f"unparsed rows: {result.unparsed_samples}"
    codes = [r.player_code for r in result.rows]
    assert len(codes) == len(set(codes)), "duplicate playerCode in parsed roster"
    assert summary.counts.get("총 참가자") == len(result.rows), "summary-box total disagrees with parsed row count"

    by_id = {r.player_code: r for r in result.rows}
    assert "9130" not in by_id, "박현경 (9130) still present -- not the updated roster"
    assert "9702" in by_id, "김리안 (9702) missing -- not the updated roster"
    assert by_id["9702"].player_name == "김리안"
    assert by_id["9702"].nationality == "KOR"
    assert by_id["6085"].player_name == "청 야니", "청 야니 name spelling must match the latest roster verbatim"

    # ---- OFFICIAL_ENTRY_LIST_V2 ----
    v1_entry = json.loads((CONTENT / "HANA_2026090002_OFFICIAL_ENTRY_LIST_V1.json").read_text(encoding="utf-8"))
    entry_records = [
        {
            "player_id": r.player_code,
            "official_display_name": r.player_name,
            "entry_category": _CATEGORY_MAP[r.qualification_category],
        }
        for r in result.rows
    ]
    entry_v2 = {
        "schema_version": "neo_official_entry_list_v2",
        "tournament": v1_entry["tournament"],
        "source": {
            "entry_url": ENTRY_URL,
            "tournament_url": v1_entry["source"]["tournament_url"],
            "retrieved_at": "2026-09-16",
            "verification": "updated official KLPGA entry page capture, re-parsed via the repo's existing "
                             "entry_list_parser; supersedes V1 (박현경 9130 removed, 김리안 9702 added).",
            "raw_html_path": str(RAW_HTML_PATH.relative_to(ROOT.parent)),
            "raw_html_sha256": raw_sha256,
            "roster_change_from_v1": {"removed": [{"player_id": "9130", "name": "박현경"}],
                                       "added": [{"player_id": "9702", "name": "김리안"}]},
        },
        "summary": {
            "total": summary.counts.get("총 참가자"),
            "eligible": summary.counts.get("자격자", 0),
            "recommended": summary.counts.get("추천자", 0),
            "invited": summary.counts.get("초청자", 0),
        },
        "records": entry_records,
    }
    (CONTENT / "HANA_2026090002_OFFICIAL_ENTRY_LIST_V2.json").write_text(
        json.dumps(entry_v2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # ---- ENTRY_FLAG_MATCH_V2 ----
    v1_flag = json.loads((CONTENT / "HANA_2026090002_ENTRY_FLAG_MATCH_V1.json").read_text(encoding="utf-8"))
    missing_country = [r.player_code for r in result.rows if not r.nationality]
    flag_records = [
        {"player_id": r.player_code, "official_display_name": r.player_name, "country_code": r.nationality}
        for r in result.rows
    ]
    country_dist = Counter(r.nationality for r in result.rows if r.nationality)
    non_kor = [
        {"player_id": r.player_code, "player_name": r.player_name, "country_code": r.nationality}
        for r in result.rows if r.nationality and r.nationality != "KOR"
    ]
    flag_v2 = {
        "schema_version": "1.0",
        "purpose": v1_flag["purpose"],
        "game_code": "2026090002",
        "generated_at_utc": "2026-09-16T16:30:00Z",
        "source": {
            "entry_url": ENTRY_URL,
            "raw_html_saved_at": str(RAW_HTML_PATH.relative_to(ROOT.parent)),
            "raw_html_sha256": raw_sha256,
            "verification": "user-supplied updated raw HTML capture of the official KLPGA entry page; source URL "
                             "confirmed via the saved page's own <!-- saved from url=(...) --> marker before "
                             "parsing. Supersedes V1 (박현경 9130 removed, 김리안 9702 added).",
            "parser": "klpga.parsers.entry_list_parser.parse_entry_list_html (repo's existing, already-tested "
                       "official parser -- not a new/ad hoc parser).",
            "extraction_method": v1_flag["source"]["extraction_method"],
        },
        "validation": {
            "summary_box_total": summary.counts.get("총 참가자"),
            "parsed_row_count": len(result.rows),
            "unparsed_row_count": result.unparsed_row_count,
            "unique_player_id_count": len(set(codes)),
            "duplicate_player_ids": {},
            "missing_country_code_player_ids": missing_country,
            "country_code_distribution": dict(country_dist),
            "matches_existing_108_population": False,
            "matches_existing_108_population_note": "population changed from V1: 박현경 9130 removed, 김리안 9702 added",
        },
        "non_kor_players": non_kor,
        "records": flag_records,
    }
    (CONTENT / "HANA_2026090002_ENTRY_FLAG_MATCH_V2.json").write_text(
        json.dumps(flag_v2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"total parsed: {len(result.rows)}")
    print(f"unique playerCode: {len(set(codes))}")
    print("9130 present:", "9130" in by_id)
    print("9702:", by_id["9702"])
    print("wrote OFFICIAL_ENTRY_LIST_V2.json and ENTRY_FLAG_MATCH_V2.json")


if __name__ == "__main__":
    main()
