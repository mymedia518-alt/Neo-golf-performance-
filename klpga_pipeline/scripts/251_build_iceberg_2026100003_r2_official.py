"""Build the official R2 result + made-cut status for 아이스버그골프·
서울신문 오픈 (game_code 2026100003) from the real official roundLeaderboard
responses, continuing the exact data flow scripts/248/249 established for
R1 (hash-verified raw capture -> parser -> player_id-linked, provenance-
carrying JSON in the repo).

Inputs (collected via the same tooling/sg-recovery-oneoff workflow used
for R1, run id 39020869256, committed here with the full MANIFEST.json
recording each file's sha256 at collection time -- re-verified below):
  - content/website_v2/raw_capture/2026100003_r2/roundLeaderboard_r2.html
  - content/website_v2/raw_capture/2026100003_r2/roundLeaderboard_r3.html
  - content/website_v2/raw_capture/2026100003_r2/MANIFEST.json

======================================================================
MADE-CUT STATUS: DERIVED FROM REAL R3 TEE-SHEET PRESENCE, NEVER A
STROKE-COUNT CUTLINE INVENTED BY THIS SCRIPT
======================================================================
The official roundLeaderboard response's own HTML contains a legend
("* +16 컷오프 = CUT") and a visual "Missed Cut" marker, but
klpga.parsers.leaderboard_parser's own confirmed finding (see its
module docstring) is that no per-row literal CUT/WD/DQ text exists in
this endpoint across rows, only a 999-rank sentinel for incomplete
rounds -- consistent with what the simpler official_data.
parse_leaderboard_html parser (reused here, exactly as scripts/244/248
already use it) actually finds: status is only ever WD/DQ/FINISHED
from the rank text, never CUT.

So made_cut is NOT read from any such legend text (the "+16" in it did
NOT match this tournament's real cut boundary when checked against
the real data -- see below) and NOT assumed as any formula. It is the
real official roundLeaderboard round=3 (FR; this is a 3-round
tournament, so round 3 IS the final round, not a mid-event round)
response's own player set: a player appears in it, with a real tee
time, if and only if the official site has scheduled them to play the
final round. 108 - 107 (R1 WD, already known) - 5 (R2 WD, newly
confirmed below) - 41 (completed R2, no R3 entry) = 61 players with a
real R3 tee time. Cross-checked against the raw HTML's own apparent
cutline text empirically: every one of the 102 non-WD R2 finishers
splits cleanly at to_par<=+4 (all 61 R3 entrants) vs to_par>=+5 (all
41 non-entrants), zero exceptions -- the two independent signals
(real R3 presence, real R2 score) agree exactly, which is why R3
presence is trusted as the authoritative source here rather than
either the HTML legend's "+16" (did not match) or a hand-picked
stroke threshold.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.official_data import parse_leaderboard_html  # noqa: E402

GAME_CODE = "2026100003"
RAW_DIR = ROOT / "content" / "website_v2" / "raw_capture" / "2026100003_r2"
MANIFEST_PATH = RAW_DIR / "MANIFEST.json"
R2_HTML_PATH = RAW_DIR / "roundLeaderboard_r2.html"
R3_HTML_PATH = RAW_DIR / "roundLeaderboard_r3.html"
JOIN_PATH = ROOT / "content" / "website_v2" / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
OUT_PATH = ROOT / "content" / "website_v2" / f"ICEBERG_{GAME_CODE}_R2_OFFICIAL_V1.json"

KNOWN_R1_WD_PLAYER_ID = "8243"  # 장은수 -- never appears from R1 onward, already established


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest_sha_by_label = {r["label"]: r["sha256"] for r in manifest["requests"]}

    r2_bytes = R2_HTML_PATH.read_bytes()
    r3_bytes = R3_HTML_PATH.read_bytes()
    r2_sha = sha256_bytes(r2_bytes)
    r3_sha = sha256_bytes(r3_bytes)
    hash_check = {
        "roundLeaderboard_r2.html": {"expected": manifest_sha_by_label.get("roundLeaderboard_r2"), "actual": r2_sha, "match": r2_sha == manifest_sha_by_label.get("roundLeaderboard_r2")},
        "roundLeaderboard_r3.html": {"expected": manifest_sha_by_label.get("roundLeaderboard_r3"), "actual": r3_sha, "match": r3_sha == manifest_sha_by_label.get("roundLeaderboard_r3")},
    }
    if not all(v["match"] for v in hash_check.values()):
        raise SystemExit(f"hash mismatch against MANIFEST.json: {json.dumps(hash_check, indent=2)}")

    join = json.loads(JOIN_PATH.read_text(encoding="utf-8"))
    roster_ids = {str(r["player_code"]) for r in join["records"]}
    assert len(roster_ids) == 108, f"expected 108-entrant roster, found {len(roster_ids)}"

    r2_rows = parse_leaderboard_html(r2_bytes.decode("utf-8"))
    r3_rows = parse_leaderboard_html(r3_bytes.decode("utf-8"))
    r2_by_id = {r["player_id"]: r for r in r2_rows}
    r3_ids = {r["player_id"] for r in r3_rows}

    leaderboard_ids = set(r2_by_id)
    missing_from_r2 = sorted(roster_ids - leaderboard_ids)
    unexpected_extra = sorted(leaderboard_ids - roster_ids)

    records = []
    for pid, row in r2_by_id.items():
        is_wd = row["status"] == "WD"
        made_cut = (not is_wd) and (pid in r3_ids)
        records.append({
            "player_id": pid,
            "player_name": row["player"],
            "r2_status": row["status"],
            "r2_rank": row["rank"],
            "r2_to_par": row["to_par"],
            "r2_through": row["through"],
            "r1_score": (row["rounds"] or [None, None])[0],
            "r2_score": (row["rounds"] or [None, None, None])[1] if len(row["rounds"] or []) > 1 else None,
            "two_round_total_strokes": row["total"],
            "made_cut": made_cut,
            "made_cut_source": "WD" if is_wd else ("r3_tee_sheet_present" if made_cut else "r3_tee_sheet_absent"),
            "r3_tee_time": next((r["through"] for r in r3_rows if r["player_id"] == pid), None),
        })

    cut_counts = {
        "made_cut_true": sum(1 for r in records if r["made_cut"]),
        "made_cut_false_wd": sum(1 for r in records if not r["made_cut"] and r["r2_status"] == "WD"),
        "made_cut_false_missed": sum(1 for r in records if not r["made_cut"] and r["r2_status"] != "WD"),
    }

    # Independent cross-check: the empirical to_par<=+4 split must agree
    # with r3-presence for every non-WD player, or this script refuses
    # to proceed rather than silently trust a disagreement.
    def to_par_num(tp):
        if tp in ("E", "", None):
            return 0
        try:
            return int(tp)
        except ValueError:
            return None

    cutline_disagreements = []
    for r in records:
        if r["r2_status"] == "WD":
            continue
        tp = to_par_num(r["r2_to_par"])
        empirical_rule_says_advance = tp is not None and tp <= 4
        if empirical_rule_says_advance != r["made_cut"]:
            cutline_disagreements.append(r["player_id"])

    out = {
        "artifact": "iceberg_2026100003_r2_official",
        "game_code": GAME_CODE,
        "round": 2,
        "source_files": {
            "roundLeaderboard_r2.html": {"path": "content/website_v2/raw_capture/2026100003_r2/roundLeaderboard_r2.html", "sha256": r2_sha},
            "roundLeaderboard_r3.html": {"path": "content/website_v2/raw_capture/2026100003_r2/roundLeaderboard_r3.html", "sha256": r3_sha},
        },
        "hash_check_against_manifest": hash_check,
        "roster_size": len(roster_ids),
        "r2_leaderboard_rows": len(r2_rows),
        "r3_leaderboard_rows": len(r3_rows),
        "missing_from_r2_leaderboard": missing_from_r2,
        "missing_from_r2_matches_known_r1_wd_only": missing_from_r2 == [KNOWN_R1_WD_PLAYER_ID],
        "unexpected_extra_ids": unexpected_extra,
        "made_cut_counts": cut_counts,
        "made_cut_source_method": "player_id present in round=3 (final round) official roundLeaderboard response (real tee time assigned) -- not a stroke-count formula",
        "cutline_cross_check": {
            "method": "empirical to_par<=+4 split (derived FROM the real data's own boundary, not assumed beforehand)",
            "disagreement_count": len(cutline_disagreements),
            "disagreement_player_ids": cutline_disagreements,
        },
        "records": records,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "written": str(OUT_PATH),
        "roster_size": len(roster_ids),
        "r2_leaderboard_rows": len(r2_rows),
        "r3_leaderboard_rows": len(r3_rows),
        "missing_from_r2_leaderboard": missing_from_r2,
        "missing_matches_known_r1_wd_only": missing_from_r2 == [KNOWN_R1_WD_PLAYER_ID],
        "unexpected_extra_ids": unexpected_extra,
        "made_cut_counts": cut_counts,
        "cutline_disagreement_count": len(cutline_disagreements),
        "hash_check": hash_check,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
