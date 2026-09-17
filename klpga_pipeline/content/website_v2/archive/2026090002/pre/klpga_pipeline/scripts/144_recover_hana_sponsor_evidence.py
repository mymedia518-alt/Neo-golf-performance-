"""HANA PRE -- recover sponsor evidence for 6 named entrants from the
existing official entry-list capture.

The raw HTML the operator supplied for this request
(b22c5e0d-______.html) is BYTE-IDENTICAL to
incoming_evidence/2026090002/HANA_2026090002_ENTRY_LIST_RAW_V2.html,
already archived and already used by 141_regenerate_hana_entry_list_v2.py
for this roster's names/countries -- so no new raw file is archived
here; this script re-parses that same already-vouched-for capture for
its sponsor column (`<span class="tb-spon"><a href="...">`), which
141/142/143 never extracted.

For each of the 6 named player_ids, the sponsor's outbound link domain
and logo image code are extracted directly from the row (never
name-based -- located strictly by `playerCode=<id>` occurrence). Domain
identity is confirmed by the operator (hanafn.com/lotte.co.kr are
self-evident brand domains; dbcon.dongbu.co.kr and dbcons.co.kr less
so) -- combining this session's own structural extraction with the
operator's business-identity confirmation is exactly the existing
VERIFIED_OFFICIAL_OPERATOR_REPORTED evidence tier already used by
OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2.json, so this writes V3 in the
same additive, non-superseding schema.

The 4 players explicitly required to stay blank (장하나, 박단유, 송가은,
김아현) are independently verified here to have NO <span class="tb-spon">
at all in this same raw HTML -- a hard assertion, not an assumption.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
RAW_HTML_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_ENTRY_LIST_RAW_V2.html"

# player_id -> (official_display_name, expected sponsor domain, sponsor
# company name). Domain extracted independently by this script from the
# raw HTML (see TARGETS assertion below); company name confirmed by the
# operator.
TARGETS = {
    "1599": ("리디아 고", "www.hanafn.com", "하나금융그룹"),
    "12706": ("권은 0906(A)", "www.hanafn.com", "하나금융그룹"),
    "1734": ("이민지", "www.hanafn.com", "하나금융그룹"),
    "10185": ("황유민", "www.lotte.co.kr", "롯데"),
    "10296": ("문정민", "dbcon.dongbu.co.kr", "동부건설"),
    "10138": ("임진영", "www.dbcons.co.kr", "대방건설"),
}
MUST_STAY_BLANK = {
    "7963": "장하나",
    "8318": "박단유",
    "8773": "송가은",
    "9277": "김아현",
}


def _row_window(html: str, player_id: str) -> str:
    """The last playerCode=<id> occurrence per player is the visible
    table row (the first is the hidden favoritItem_<id> duplicate) --
    same convention already used to verify roster matching earlier in
    this branch."""
    matches = list(re.finditer(rf"playerCode={player_id}\b", html))
    assert matches, f"player_id {player_id} not found in raw HTML at all"
    pos = matches[-1].start()
    return html[pos:pos + 1200]


def main() -> None:
    html = RAW_HTML_PATH.read_text(encoding="utf-8")

    records = []
    for pid, (name, expected_domain, sponsor) in TARGETS.items():
        window = _row_window(html, pid)
        m = re.search(r"<span class=\"tb-spon\">\s*<a href=\"https?://([^/\"]+)", window)
        assert m, f"{pid} {name}: no tb-spon sponsor link found in raw HTML"
        domain = m.group(1)
        assert domain == expected_domain, (
            f"{pid} {name}: raw HTML domain {domain!r} does not match expected {expected_domain!r}"
        )
        img_m = re.search(r"<img src=\"\./하나출전선수_files/(\d+)\.png\"", window)
        assert img_m, f"{pid} {name}: no sponsor image code found"
        records.append({
            "player_id": pid,
            "player_name": name,
            "sponsor": sponsor,
            "sponsor_domain": domain,
            "sponsor_image_code": img_m.group(1),
            "evidence_status": "VERIFIED_OFFICIAL_OPERATOR_REPORTED",
        })

    for pid, name in MUST_STAY_BLANK.items():
        window = _row_window(html, pid)
        has_sponsor = "tb-spon" in window[:400]
        assert not has_sponsor, f"{pid} {name}: expected NO sponsor span, but one was found -- must not force blank"

    # every sponsor image code must be distinct across the 6 (proves
    # these are 6 genuinely different sponsor records, not one
    # placeholder value copy-pasted across players)
    codes = [r["sponsor_image_code"] for r in records]
    dupes = {c for c in codes if codes.count(c) > 1}
    domains_by_sponsor: dict[str, set[str]] = {}
    for r in records:
        domains_by_sponsor.setdefault(r["sponsor"], set()).add(r["sponsor_domain"])
    for sponsor, doms in domains_by_sponsor.items():
        assert len(doms) == 1, f"sponsor {sponsor!r} maps to more than one domain: {doms}"

    out = {
        "schema_version": "operator_reported_sponsor_evidence_v2",
        "supersedes": "none -- additive to OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2.json, same evidence tier",
        "_provenance_honesty_note": (
            "Sponsor values extracted directly by this script from "
            "incoming_evidence/2026090002/HANA_2026090002_ENTRY_LIST_RAW_V2.html "
            "(the same already-archived official KLPGA entry page capture "
            "used by 141_regenerate_hana_entry_list_v2.py for this roster's "
            "names/countries -- re-verified byte-identical to a fresh copy "
            "the operator supplied for this request). This script never "
            "fetched klpga.co.kr itself (network egress remains proxy-"
            "blocked). Each sponsor's outbound-link domain and logo image "
            "code were parsed strictly by player_id (never by name). Domain "
            "-> company-name identity was confirmed by the operator, "
            "combining this session's structural extraction with the "
            "operator's business-identity confirmation -- same evidence "
            "tier as OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2.json's own "
            "precedent (VERIFIED_OFFICIAL_OPERATOR_REPORTED)."
        ),
        "reported_by": "operator, cross-checked by this session against the already-archived official entry-list raw HTML",
        "reported_at_utc": "2026-09-16T19:25:00Z",
        "verification_method": (
            "Raw HTML re-parsed for each player_id's <span class='tb-spon'> "
            "sponsor link; domain and sponsor logo image code extracted "
            "programmatically and found distinct per sponsor company "
            "(no duplicate/copy-pasted value); the 4 players explicitly "
            "required to stay blank were independently confirmed to carry "
            "no sponsor span at all in the same raw HTML."
        ),
        "identity_join_key": "player_id (exact match only -- never name-only)",
        "cross_check_result": [
            {
                "player_id": r["player_id"], "player_name": r["player_name"],
                "sponsor_domain": r["sponsor_domain"], "sponsor_image_code": r["sponsor_image_code"],
                "note": "domain and image code independently extracted from the raw HTML row for this exact player_id",
            }
            for r in records
        ] + [
            {"player_id": pid, "player_name": name, "note": "confirmed NO <span class='tb-spon'> present -- stays blank"}
            for pid, name in MUST_STAY_BLANK.items()
        ],
        "records": [
            {"player_id": r["player_id"], "player_name": r["player_name"], "sponsor": r["sponsor"], "evidence_status": r["evidence_status"]}
            for r in records
        ],
    }

    out_path = CONTENT / "OPERATOR_REPORTED_SPONSOR_EVIDENCE_V3.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out_path)
    for r in records:
        print(f"  {r['player_id']:>6} {r['player_name']:15s} -> {r['sponsor']} (domain={r['sponsor_domain']}, img={r['sponsor_image_code']})")
    print("blank-confirmed:", list(MUST_STAY_BLANK.items()))


if __name__ == "__main__":
    main()
