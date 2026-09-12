"""Build the immutable OFFICIAL PROFILE and OFFICIAL SG snapshots, and
run the Profile<->SG and Warehouse<->NEO identity joins. Read-only
against the raw captures + existing frozen NEO artifacts; writes only
the two new content-addressed snapshot files (idempotent). Never
touches NEO Ranking, HOME, or production docs/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
RAW = CONTENT / "raw_sources"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.record_report_warehouse import (  # noqa: E402
    RecordReportSnapshotConflict,
    build_snapshot as build_profile_snapshot,
    parse_record_report_html,
    sha256_file,
    snapshot_to_dict as profile_snapshot_to_dict,
    write_snapshot_immutable as write_profile_snapshot,
)
from klpga.website_v2.official_sg_warehouse import (  # noqa: E402
    OfficialSGSnapshotConflict,
    build_snapshot as build_sg_snapshot,
    parse_official_sg_html,
    snapshot_to_dict as sg_snapshot_to_dict,
    write_snapshot_immutable as write_sg_snapshot,
)
from klpga.website_v2.top120_validation import evaluate  # noqa: E402

CAPTURE_A = RAW / "KLPGA_RECORD_REPORT_2026_CAPTURE_A_10ROW.html"
CAPTURE_B = RAW / "KLPGA_RECORD_REPORT_2026_CAPTURE_B_EXPANDED.html"
CAPTURE_SG = RAW / "KLPGA_OFFICIAL_SG_2026_CAPTURE.html"
EXPECTED_SHA_A = "198df55cf31b05a141deb83c5269fe40c46a5d20ad623093dc86ab647e0a9538"
EXPECTED_SHA_B = "31ee0f1096f7e552bb4fd235dc4c8533f694f265c4aaa445d44a327fbac05ae0"
EXPECTED_SHA_SG = "fbb5d3fa3e4cb123cf9197fb3def2679277f0d446ff54c4a1da8fae7806fa26c"

PROFILE_SNAPSHOT_PATH = CONTENT / "OFFICIAL_PROFILE_NORMALIZED.json"
SG_SNAPSHOT_PATH = CONTENT / "OFFICIAL_SG_NORMALIZED.json"


def load(name):
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def build() -> dict:
    sha_a, sha_b, sha_sg = sha256_file(CAPTURE_A), sha256_file(CAPTURE_B), sha256_file(CAPTURE_SG)
    checks = {
        "capture_A_sha256_match": sha_a == EXPECTED_SHA_A,
        "capture_B_sha256_match": sha_b == EXPECTED_SHA_B,
        "capture_SG_sha256_match": sha_sg == EXPECTED_SHA_SG,
    }
    if not all(checks.values()):
        return {"action": "HARD_STOP", "reason": f"source SHA256 mismatch: {checks}", "measured": {"A": sha_a, "B": sha_b, "SG": sha_sg}}

    html_b = CAPTURE_B.read_text(encoding="utf-8")
    profile_snapshot = build_profile_snapshot(
        html=html_b, source_sha256=sha_b, source_url="https://klpga.co.kr/web/record/totalRecord",
        capture_timestamp="UNKNOWN_BROWSER_CAPTURE_TIME", effective_season=2026, menu_mode="All", expanded_view=True,
    )
    profile_wrote_new = write_profile_snapshot(profile_snapshot, PROFILE_SNAPSHOT_PATH)

    html_sg = CAPTURE_SG.read_text(encoding="utf-8")
    sg_snapshot = build_sg_snapshot(
        html=html_sg, source_sha256=sha_sg, source_url="https://klpga.co.kr/web/record/locationRecord",
        capture_timestamp="UNKNOWN_BROWSER_CAPTURE_TIME", effective_season=2026, menu_mode="All",
    )
    sg_wrote_new = write_sg_snapshot(sg_snapshot, SG_SNAPSHOT_PATH)

    # --- Source proof gate summary ---
    profile_source_proof = {
        "FILE_PATH": str(CAPTURE_B), "SHA256": sha_b, "SOURCE_URL": "https://klpga.co.kr/web/record/totalRecord",
        "SOURCE_ROWS": profile_snapshot.source_rows, "UNIQUE_PLAYER_CODES": profile_snapshot.unique_players,
        "DUPLICATE_PLAYER_CODES": profile_snapshot.source_rows - profile_snapshot.unique_players,
        "BLANK_PLAYER_CODES": sum(1 for r in profile_snapshot.records if not r["playerCode"]),
        "BLANK_PLAYER_NAMES": sum(1 for r in profile_snapshot.records if not r["player_name"]),
    }
    rounds = [r["official_sg_rounds"] for r in sg_snapshot.records if r["official_sg_rounds"] is not None]
    import statistics
    sg_source_proof = {
        "FILE_PATH": str(CAPTURE_SG), "SHA256": sha_sg, "SOURCE_URL": "https://klpga.co.kr/web/record/locationRecord",
        "SOURCE_ROWS": sg_snapshot.source_rows, "UNIQUE_PLAYER_CODES": sg_snapshot.unique_players,
        "DUPLICATE_PLAYER_CODES": sg_snapshot.source_rows - sg_snapshot.unique_players,
        "BLANK_PLAYER_CODES": sum(1 for r in sg_snapshot.records if not r["playerCode"]),
        "BLANK_PLAYER_NAMES": sum(1 for r in sg_snapshot.records if not r["player_name"]),
        "MIN_MEASURED_ROUNDS": min(rounds) if rounds else None,
        "MAX_MEASURED_ROUNDS": max(rounds) if rounds else None,
        "MEDIAN_MEASURED_ROUNDS": statistics.median(rounds) if rounds else None,
        "sample_5": [
            {"playerCode": r["playerCode"], "player_name": r["player_name"], "SG_TOTAL": r["official_sg_total"],
             "SG_OTT": r["official_sg_ott"], "SG_APP": r["official_sg_app"], "SG_ARG": r["official_sg_arg"],
             "SG_PUTT": r["official_sg_putt"], "ROUNDS": r["official_sg_rounds"]}
            for r in sg_snapshot.records[:5]
        ],
    }

    # --- Profile <-> SG identity join (playerCode ONLY) ---
    profile_by_code = {r["playerCode"]: r for r in profile_snapshot.records}
    sg_by_code = {r["playerCode"]: r for r in sg_snapshot.records}
    matched_codes = sorted(set(profile_by_code) & set(sg_by_code))
    profile_only = sorted(set(profile_by_code) - set(sg_by_code))
    sg_only = sorted(set(sg_by_code) - set(profile_by_code))
    name_conflicts = [
        {"playerCode": c, "profile_name": profile_by_code[c]["player_name"], "sg_name": sg_by_code[c]["player_name"]}
        for c in matched_codes if profile_by_code[c]["player_name"] != sg_by_code[c]["player_name"]
    ]

    # --- Warehouse <-> current NEO (W36 TOP120 / NEO108 / pending12) ---
    cohort_top120 = load("HOME_PLAYER_MASTER_TOP120_2026_W36.json")
    warehouse = load("historical_sg_warehouse_corrected.json")
    config = load("NEO_RANKING_VALIDATION_MODEL_V1.json")
    top120_out, summary = evaluate(cohort_top120, warehouse, config)
    top120_sha = sha256_file(CONTENT / "HOME_PLAYER_MASTER_TOP120_2026_W36.json")

    neo_ids = {r["player_id"] for r in top120_out}
    warehouse_codes = set(profile_by_code) | set(sg_by_code)
    warehouse_matched_to_neo = sorted(warehouse_codes & neo_ids)
    warehouse_unmatched_to_neo = sorted(warehouse_codes - neo_ids)
    neo_without_profile = [r["player_id"] for r in top120_out if r["player_id"] not in profile_by_code]
    neo_without_sg = [r["player_id"] for r in top120_out if r["player_id"] not in sg_by_code]

    return {
        "action": "WAREHOUSE_BUILT",
        "profile_wrote_new_file": profile_wrote_new,
        "sg_wrote_new_file": sg_wrote_new,
        "profile_snapshot_id": profile_snapshot.snapshot_id,
        "sg_snapshot_id": sg_snapshot.snapshot_id,
        "profile_normalized_sha256": profile_snapshot.normalized_sha256,
        "sg_normalized_sha256": sg_snapshot.normalized_sha256,
        "PROFILE_SOURCE_PROOF": profile_source_proof,
        "OFFICIAL_SG_SOURCE_PROOF": sg_source_proof,
        "PROFILE_SG_IDENTITY_JOIN": {
            "PROFILE_PLAYERS": len(profile_by_code), "SG_PLAYERS": len(sg_by_code),
            "MATCHED_PLAYER_CODES": len(matched_codes), "PROFILE_ONLY": profile_only, "SG_ONLY": sg_only,
            "NAME_CONFLICTS_FOR_SAME_CODE": name_conflicts,
        },
        "NEO_IDENTITY_JOIN": {
            "WAREHOUSE_MATCHED_TO_NEO": len(warehouse_matched_to_neo),
            "WAREHOUSE_UNMATCHED_TO_NEO": warehouse_unmatched_to_neo,
            "NEO_WITHOUT_OFFICIAL_PROFILE": neo_without_profile,
            "NEO_WITHOUT_OFFICIAL_SG": neo_without_sg,
        },
        "CURRENT_NEO": {
            "RANKED_COUNT": summary["neo_ranked"], "VALIDATION_PENDING_COUNT": summary["validation_pending"],
            "SOURCE_OF_TRUTH_FILE": "HOME_PLAYER_MASTER_TOP120_2026_W36.json", "SOURCE_SHA256": top120_sha,
        },
    }


if __name__ == "__main__":
    try:
        result = build()
    except (RecordReportSnapshotConflict, OfficialSGSnapshotConflict) as exc:
        result = {"action": "HARD_STOP", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
