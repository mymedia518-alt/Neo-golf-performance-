"""HANA R1 -- recover 양서후 (10867)'s country flag and sponsor from the
official R1 raw leaderboard capture itself, since she has no PRE-stage
entry (never appears in HANA_2026090002_ENTRY_FLAG_MATCH_V2.json --
that file is PRE evidence and is never touched or extended here).

Two independent facts, both extracted directly from
HANA_2026090002_R1_LEADERBOARD_RAW_V1.html:

  country flag: her row's own
    <td><span class="tb-flag" style="background-image:
    url('/resources/web/images/country/KOR.png');"></span></td>
  sponsor: her row's own
    <span class="group-item tb-spon"><a ...><img
    src=".../00100262.png" ...></a></span>
  -- image code "00100262" is CROSS-CHECKED against the already
  -archived HANA_2026090002_ENTRY_LIST_RAW_V2.html, where the exact
  same code belongs to 강가율(9174) linked to http://www.saeki.co.kr/
  (Saeki), i.e. the same "세기P&C" sponsor name already used elsewhere
  in this codebase -- so this is an independent re-derivation that
  happens to agree with the earlier cross-tournament-cache value, not
  a fabricated one.

Output is additive and R1-scoped only (HANA_2026090002_R1_NEW_ENTRANT_
IDENTITY_EVIDENCE_V1.json, a single-player record) -- never edits
HANA_2026090002_ENTRY_FLAG_MATCH_V2.json or any other PRE-stage file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"

R1_RAW_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R1_LEADERBOARD_RAW_V1.html"
ENTRY_RAW_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_ENTRY_LIST_RAW_V2.html"

PLAYER_ID = "10867"
PLAYER_NAME = "양서후"
KNOWN_SPONSOR_BY_CODE = {"00100262": ("세기P&C", "www.saeki.co.kr")}


def main() -> None:
    r1_html = R1_RAW_PATH.read_text(encoding="utf-8")

    m = re.search(rf'_playercode="{PLAYER_ID}"[^>]*', r1_html)
    assert m, f"player_id {PLAYER_ID} detail block not found in R1 raw"
    row_start = r1_html.rfind("<li", 0, m.start())
    window = r1_html[row_start:row_start + 2500]

    flag_m = re.search(r"tb-flag[^>]*url\('/resources/web/images/country/([A-Z]{3})\.png'\)", window)
    assert flag_m, f"{PLAYER_NAME}: no tb-flag country image found in R1 raw row"
    country_code = flag_m.group(1)
    assert country_code == "KOR", f"{PLAYER_NAME}: expected KOR flag, found {country_code}"

    spon_m = re.search(r"tb-spon.*?(\d{8})\.png", window, re.DOTALL)
    assert spon_m, f"{PLAYER_NAME}: no tb-spon sponsor image code found in R1 raw row"
    sponsor_code = spon_m.group(1)
    assert sponsor_code in KNOWN_SPONSOR_BY_CODE, (
        f"{PLAYER_NAME}: sponsor image code {sponsor_code} has no known company mapping -- "
        "refusing to guess a name from a code alone"
    )
    sponsor_name, sponsor_domain = KNOWN_SPONSOR_BY_CODE[sponsor_code]

    # independent cross-check against the entry list's own record of this exact code
    entry_html = ENTRY_RAW_PATH.read_text(encoding="utf-8")
    code_idx = entry_html.find(sponsor_code)
    assert code_idx != -1, f"sponsor code {sponsor_code} not found anywhere in the entry list raw"
    entry_window = entry_html[max(0, code_idx - 600):code_idx]
    assert sponsor_domain in entry_window, (
        f"entry list's own occurrence of sponsor code {sponsor_code} does not link to {sponsor_domain}"
    )

    out = {
        "schema_version": "hana_r1_new_entrant_identity_evidence_v1",
        "game_code": "2026090002",
        "purpose": (
            f"{PLAYER_NAME}({PLAYER_ID}) has no PRE-stage entry (never in "
            "HANA_2026090002_ENTRY_FLAG_MATCH_V2.json) -- this file recovers her "
            "country flag and sponsor directly from the official R1 raw leaderboard "
            "capture, independently cross-checked against the entry list raw's own "
            "record of the same sponsor image code. Additive, R1-scoped only; PRE "
            "evidence files are never touched."
        ),
        "source_r1_raw": str(R1_RAW_PATH.relative_to(ROOT.parent)),
        "source_entry_list_raw_cross_check": str(ENTRY_RAW_PATH.relative_to(ROOT.parent)),
        "records": [
            {
                "player_id": PLAYER_ID,
                "official_display_name": PLAYER_NAME,
                "country_code": country_code,
                "sponsor": sponsor_name,
                "sponsor_image_code": sponsor_code,
                "sponsor_domain": sponsor_domain,
                "evidence_status": "VERIFIED_OFFICIAL_R1_LEADERBOARD",
            }
        ],
    }

    out_path = CONTENT / "HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json"
    if out_path.exists():
        out_path.unlink()
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    print(out["records"][0])


if __name__ == "__main__":
    main()
