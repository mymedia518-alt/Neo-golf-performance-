"""Link the official R1 Strokes Gained table (아이스버그골프·서울신문 오픈,
game_code 2026100003) to the 108-entrant roster by player_id, and write a
normalized, provenance-carrying JSON into the repo.

Reuses, verbatim, the same official parsers scripts/sg_recovery_oneoff.py
(branch tooling/sg-recovery-oneoff, commit 8115cdbe) and script 63 already
use: official_data.parse_sg_html / parse_leaderboard_html /
validate_sg_record, and analytics.sg_performance.standardize_player_name /
validate_sg_records. Same identity-resolution method too: a player_id is
attached to an SG row ONLY if that row's player name is an exact match
against ROUND 1's OWN leaderboard (roundLeaderboard_r1.html, the same
round, not a cross-round or fuzzy match) -- never guessed, never matched
by position/order.

Inputs (already committed, not re-fetched):
  - content/website_v2/raw_capture/2026100003_r1/sg_r1.html (official
    strokesGained_detail response, round=1)
  - content/website_v2/raw_capture/2026100003_r1/roundLeaderboard_r1.html
    (official roundLeaderboard response, round=1 -- source of player_id)
  - content/website_v2/raw_capture/2026100003_r1/MANIFEST.json (sha256 of
    both files at original collection time, run_id 38894425383)

This script re-verifies both files' sha256 against that MANIFEST before
parsing -- if either has drifted, it aborts rather than parse a file that
may no longer be the one originally collected from klpga.co.kr.

Expected shape: 108 real leaderboard rows, 107 SG rows (the official SG
table has no row for a withdrawn player -- 장은수/8243 withdrew and has no
completed R1 to compute SG from). 장은수 is therefore expected to be the
one player_id in the 108-roster with no SG row; this script does NOT
fabricate one, and reports this player_id separately as
"official_sg_unavailable" (not an error) rather than mixing them into
mismatches.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.official_data import (  # noqa: E402
    parse_leaderboard_html,
    parse_sg_html,
    validate_sg_record,
)
from klpga.analytics.sg_performance import (  # noqa: E402
    standardize_player_name,
    validate_sg_records,
)

GAME_CODE = "2026100003"
RAW_DIR = ROOT / "content" / "website_v2" / "raw_capture" / "2026100003_r1"
MANIFEST_PATH = RAW_DIR / "MANIFEST.json"
SG_HTML_PATH = RAW_DIR / "sg_r1.html"
LEADERBOARD_HTML_PATH = RAW_DIR / "roundLeaderboard_r1.html"
OUT_PATH = ROOT / "content" / "website_v2" / f"ICEBERG_{GAME_CODE}_R1_SG_OFFICIAL_V1.json"

KNOWN_WD_PLAYER_ID = "8243"  # 장은수 -- established fact from scripts/244's own audited leaderboard


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_sha_by_label = {r["label"]: r["sha256"] for r in manifest["requests"]}

    # Hashed from raw bytes (read_bytes), never read_text -- read_text applies
    # universal-newline translation (\r\n -> \n) on input, which silently
    # changes the byte content relative to what was actually written to disk
    # at collection time and makes the hash check below fail on a file that
    # has not actually changed. Parsing itself is newline-agnostic (BeautifulSoup),
    # so the decoded text is only used for parsing, the raw bytes only for the hash.
    sg_bytes = SG_HTML_PATH.read_bytes()
    lb_bytes = LEADERBOARD_HTML_PATH.read_bytes()
    sg_html = sg_bytes.decode("utf-8")
    lb_html = lb_bytes.decode("utf-8")
    sg_sha = sha256_bytes(sg_bytes)
    lb_sha = sha256_bytes(lb_bytes)

    hash_check = {
        "sg_r1.html": {"expected": manifest_sha_by_label.get("sg_r1"), "actual": sg_sha, "match": sg_sha == manifest_sha_by_label.get("sg_r1")},
        "roundLeaderboard_r1.html": {"expected": manifest_sha_by_label.get("roundLeaderboard_r1"), "actual": lb_sha, "match": lb_sha == manifest_sha_by_label.get("roundLeaderboard_r1")},
    }
    if not all(v["match"] for v in hash_check.values()):
        raise SystemExit(f"hash mismatch against MANIFEST.json -- raw file(s) changed since collection: {json.dumps(hash_check, indent=2)}")

    leaderboard_rows = parse_leaderboard_html(lb_html)
    assert len(leaderboard_rows) == 108, f"expected 108 R1 leaderboard rows, found {len(leaderboard_rows)}"
    name_to_id_r1 = {str(r["player"]): str(r["player_id"]) for r in leaderboard_rows if r.get("player_id")}
    all_player_ids = {str(r["player_id"]) for r in leaderboard_rows if r.get("player_id")}

    sg_rows_raw = parse_sg_html(sg_html, scope="single_round", round_number=1)

    rows: list[dict] = []
    for row in sg_rows_raw:
        pid = name_to_id_r1.get(str(row.get("player")))
        row = dict(row)
        row.update({
            "player_id": pid,
            "identity_state": "RETAINED" if pid else "UNRESOLVED_IDENTITY",
            "season": 2026,
            "game_code": GAME_CODE,
            "tournament": "아이스버그골프 · 서울신문 오픈",
            "date": "2026-10-16",
            "source": "https://klpga.co.kr/load/leaderboard/strokesGained_detail POST gameCode=2026100003, round=1",
            "source_file": "content/website_v2/raw_capture/2026100003_r1/sg_r1.html",
            "source_file_sha256": sg_sha,
            "validation": validate_sg_record(row),
        })
        row.update(standardize_player_name(row.get("player"), pid))
        rows.append(row)

    batch_validation = validate_sg_records(rows)

    sg_player_ids = {r["player_id"] for r in rows if r.get("player_id")}
    duplicates = [r["player_id"] for r in rows if r.get("player_id") and [x["player_id"] for x in rows].count(r["player_id"]) > 1]
    unresolved = [r for r in rows if r["identity_state"] == "UNRESOLVED_IDENTITY"]
    leaderboard_without_sg = sorted(all_player_ids - sg_player_ids)
    sg_without_leaderboard_match = sorted(sg_player_ids - all_player_ids)

    expected_missing = leaderboard_without_sg == [KNOWN_WD_PLAYER_ID]
    unexpected_missing = [pid for pid in leaderboard_without_sg if pid != KNOWN_WD_PLAYER_ID]

    out = {
        "artifact": "iceberg_2026100003_r1_sg_official",
        "game_code": GAME_CODE,
        "round": 1,
        "scope": "single_round",
        "source_files": {
            "sg_r1.html": {"path": "content/website_v2/raw_capture/2026100003_r1/sg_r1.html", "sha256": sg_sha},
            "roundLeaderboard_r1.html": {"path": "content/website_v2/raw_capture/2026100003_r1/roundLeaderboard_r1.html", "sha256": lb_sha},
        },
        "hash_check_against_manifest": hash_check,
        "leaderboard_rows": len(leaderboard_rows),
        "sg_rows": len(rows),
        "batch_validation": batch_validation,
        "duplicate_player_ids": sorted(set(duplicates)),
        "unresolved_identity_count": len(unresolved),
        "unresolved_identity_detail": unresolved,
        "leaderboard_without_sg": leaderboard_without_sg,
        "leaderboard_without_sg_matches_known_wd_only": expected_missing,
        "unexpected_missing_player_ids": unexpected_missing,
        "sg_without_leaderboard_match": sg_without_leaderboard_match,
        "known_wd_player_id": KNOWN_WD_PLAYER_ID,
        "records": rows,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "written": str(OUT_PATH),
        "leaderboard_rows": len(leaderboard_rows),
        "sg_rows": len(rows),
        "batch_validation": batch_validation,
        "duplicate_player_ids": sorted(set(duplicates)),
        "leaderboard_without_sg": leaderboard_without_sg,
        "matches_known_wd_only": expected_missing,
        "unexpected_missing_player_ids": unexpected_missing,
        "sg_without_leaderboard_match": sg_without_leaderboard_match,
        "hash_check": hash_check,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
