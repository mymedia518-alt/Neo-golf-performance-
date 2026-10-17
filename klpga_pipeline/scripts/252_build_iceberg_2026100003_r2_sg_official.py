"""Link the official R2 Strokes Gained table to the roster by player_id,
same method scripts/248 established for R1: exact name match against
ROUND 2's OWN leaderboard (never fuzzy, never cross-round).

Expected shape: 107 R2 leaderboard rows (108 - 1 known R1 WD), 102 SG
rows (107 - 5 players who WD'd during/by R2, confirmed in scripts/251's
own output as made_cut_false_wd). The 5 R2-WD players are therefore
expected to be exactly the leaderboard rows with no SG counterpart --
this script does NOT fabricate SG for them.
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
RAW_DIR = ROOT / "content" / "website_v2" / "raw_capture" / "2026100003_r2"
MANIFEST_PATH = RAW_DIR / "MANIFEST.json"
SG_HTML_PATH = RAW_DIR / "sg_r2.html"
LEADERBOARD_HTML_PATH = RAW_DIR / "roundLeaderboard_r2.html"
R2_OFFICIAL_PATH = ROOT / "content" / "website_v2" / f"ICEBERG_{GAME_CODE}_R2_OFFICIAL_V1.json"
OUT_PATH = ROOT / "content" / "website_v2" / f"ICEBERG_{GAME_CODE}_R2_SG_OFFICIAL_V1.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_sha_by_label = {r["label"]: r["sha256"] for r in manifest["requests"]}

    sg_bytes = SG_HTML_PATH.read_bytes()
    lb_bytes = LEADERBOARD_HTML_PATH.read_bytes()
    sg_html = sg_bytes.decode("utf-8")
    lb_html = lb_bytes.decode("utf-8")
    sg_sha = sha256_bytes(sg_bytes)
    lb_sha = sha256_bytes(lb_bytes)

    hash_check = {
        "sg_r2.html": {"expected": manifest_sha_by_label.get("sg_r2"), "actual": sg_sha, "match": sg_sha == manifest_sha_by_label.get("sg_r2")},
        "roundLeaderboard_r2.html": {"expected": manifest_sha_by_label.get("roundLeaderboard_r2"), "actual": lb_sha, "match": lb_sha == manifest_sha_by_label.get("roundLeaderboard_r2")},
    }
    if not all(v["match"] for v in hash_check.values()):
        raise SystemExit(f"hash mismatch against MANIFEST.json: {json.dumps(hash_check, indent=2)}")

    leaderboard_rows = parse_leaderboard_html(lb_html)
    assert len(leaderboard_rows) == 107, f"expected 107 R2 leaderboard rows, found {len(leaderboard_rows)}"
    name_to_id_r2 = {str(r["player"]): str(r["player_id"]) for r in leaderboard_rows if r.get("player_id")}
    all_player_ids = {str(r["player_id"]) for r in leaderboard_rows if r.get("player_id")}
    wd_ids = {str(r["player_id"]) for r in leaderboard_rows if r.get("status") == "WD"}

    sg_rows_raw = parse_sg_html(sg_html, scope="single_round", round_number=2)

    rows: list[dict] = []
    for row in sg_rows_raw:
        pid = name_to_id_r2.get(str(row.get("player")))
        row = dict(row)
        row.update({
            "player_id": pid,
            "identity_state": "RETAINED" if pid else "UNRESOLVED_IDENTITY",
            "season": 2026,
            "game_code": GAME_CODE,
            "tournament": "아이스버그골프 · 서울신문 오픈",
            "date": "2026-10-17",
            "source": "https://klpga.co.kr/load/leaderboard/strokesGained_detail POST gameCode=2026100003, round=2",
            "source_file": "content/website_v2/raw_capture/2026100003_r2/sg_r2.html",
            "source_file_sha256": sg_sha,
            "validation": validate_sg_record(row),
        })
        row.update(standardize_player_name(row.get("player"), pid))
        rows.append(row)

    batch_validation = validate_sg_records(rows)
    sg_player_ids = {r["player_id"] for r in rows if r.get("player_id")}
    duplicates = sorted({r["player_id"] for r in rows if r.get("player_id") and [x["player_id"] for x in rows].count(r["player_id"]) > 1})
    unresolved = [r for r in rows if r["identity_state"] == "UNRESOLVED_IDENTITY"]
    leaderboard_without_sg = sorted(all_player_ids - sg_player_ids)
    sg_without_leaderboard_match = sorted(sg_player_ids - all_player_ids)
    leaderboard_without_sg_matches_wd = set(leaderboard_without_sg) == wd_ids

    out = {
        "artifact": "iceberg_2026100003_r2_sg_official",
        "game_code": GAME_CODE,
        "round": 2,
        "scope": "single_round",
        "source_files": {
            "sg_r2.html": {"path": "content/website_v2/raw_capture/2026100003_r2/sg_r2.html", "sha256": sg_sha},
            "roundLeaderboard_r2.html": {"path": "content/website_v2/raw_capture/2026100003_r2/roundLeaderboard_r2.html", "sha256": lb_sha},
        },
        "hash_check_against_manifest": hash_check,
        "leaderboard_rows": len(leaderboard_rows),
        "sg_rows": len(rows),
        "batch_validation": batch_validation,
        "duplicate_player_ids": duplicates,
        "unresolved_identity_count": len(unresolved),
        "unresolved_identity_detail": unresolved,
        "leaderboard_without_sg": leaderboard_without_sg,
        "leaderboard_without_sg_matches_wd_ids": leaderboard_without_sg_matches_wd,
        "known_wd_ids_from_r2_leaderboard": sorted(wd_ids),
        "sg_without_leaderboard_match": sg_without_leaderboard_match,
        "records": rows,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    tol_fail = [r for r in rows if not r["validation"]["total_within_tolerance"]]

    print(json.dumps({
        "written": str(OUT_PATH),
        "leaderboard_rows": len(leaderboard_rows),
        "sg_rows": len(rows),
        "batch_validation": batch_validation,
        "duplicate_player_ids": duplicates,
        "leaderboard_without_sg": leaderboard_without_sg,
        "matches_wd_ids": leaderboard_without_sg_matches_wd,
        "sg_without_leaderboard_match": sg_without_leaderboard_match,
        "component_sum_tolerance_fail_count": len(tol_fail),
        "hash_check": hash_check,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
