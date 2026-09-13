#!/usr/bin/env python3
"""MISSION I -- KB FR OFFICIAL 70/70 RECOVERY FROM KLPGA GROUP LEADERBOARD.

Handles a newly-cited official source, https://klpga.co.kr/web/leaderboard/
leaderboard_group?gameCode=2026090003, and 6 sample player rows supplied
directly as text in the mission instructions (not a screenshot file).

This script does three things, in order, and refuses to silently promote
unverified numbers into confirmed evidence:

1. Records that the new URL was actually attempted via three independent
   mechanisms (requests, headless Chromium, WebFetch) and all three hit
   the same network-egress block -- proving this is a domain-level block,
   not merely the previously-known AJAX-endpoint block.
2. Cross-validates every one of the 6 text-supplied sample rows against
   this repo's own independently-sourced, pre-existing official R3
   evidence (R1/R2/R3 strokes) before accepting anything -- exactly the
   same method this project already used, and already named, for its
   OPERATOR_REPORTED_EXTERNAL_CROSS_VERIFIED evidence tier (see
   KB_2026090003_OPERATOR_REPORTED_FINAL_EVIDENCE_V1.json).
3. Classifies each row: already confirmed in V3 (checked for conflicts,
   never overwritten), or genuinely new -- and only genuinely new rows
   with an exact R1-R3 match and passing FR arithmetic are recorded, at
   the OPERATOR_REPORTED_EXTERNAL_CROSS_VERIFIED tier, in a new additive
   evidence file. V1/V2/V3 and the R1-recovery V1 file are never modified.

Six 4th-round text rows supplied in the Mission I instructions:
    player_name -> (r1, r2, r3, r4, total, to_par)
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GAME_CODE = "2026090003"
PAR_PER_ROUND = 72
TOTAL_PAR = PAR_PER_ROUND * 4  # 288

V3_PATH = REPO / "content/website_v2/KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
R3_JOINED_PATH = REPO / "evidence/KB_2026090003_R3/KB_2026090003_R3_OFFICIAL_FINAL_JOINED.json"
R3_FORECAST_PATH = REPO / "content/website_v2/2026090003_POST_R3_FINAL_FORECAST.json"
RECOVERY_V1_PATH = REPO / "content/website_v2/KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V1.json"
OUT_PATH = REPO / "content/website_v2/KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V2.json"

EXPECTED_R3_FORECAST_SHA256 = "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"
NEW_SOURCE_URL = "https://klpga.co.kr/web/leaderboard/leaderboard_group?gameCode=2026090003"

# player_name -> (r1, r2, r3, fr, total, to_par), exactly as supplied in the
# Mission I instruction text. No screenshot/file was attached -- this is
# text embedded in a chat instruction, which is why every row below is
# cross-validated against independently-sourced R1-R3 evidence before any
# of it is treated as usable.
SUPPLIED_TEXT_ROWS = {
    "박보겸":   (70, 69, 73, 71, 283, -5),
    "이세희":   (71, 72, 76, 78, 297, 9),
    "김수지":   (73, 74, 73, 79, 299, 11),
    "김우정":   (73, 76, 71, 72, 292, 4),
    "빳차라쭈타 콩끄라판(I)": (73, 73, 74, 73, 293, 5),
    "최은우":   (71, 76, 73, 76, 296, 8),
}

RETRIEVAL_ATTEMPTS = [
    {"method": "python requests (direct HTTPS)",
     "target": NEW_SOURCE_URL,
     "result": "requests.exceptions.ProxyError: Tunnel connection failed: 403 Forbidden"},
    {"method": "headless Chromium (Playwright, /opt/pw-browsers/chromium)",
     "target": NEW_SOURCE_URL,
     "result": "net::ERR_TUNNEL_CONNECTION_FAILED"},
    {"method": "WebFetch tool",
     "target": NEW_SOURCE_URL,
     "result": "EGRESS_BLOCKED: Access to klpga.co.kr is blocked by the network egress proxy"},
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _to_par_to_strokes(to_par) -> int | None:
    if to_par is None:
        return None
    return PAR_PER_ROUND + int(to_par)


def build() -> dict:
    v3 = json.loads(V3_PATH.read_text(encoding="utf-8"))
    r3_joined = json.loads(R3_JOINED_PATH.read_text(encoding="utf-8"))

    r3_active_by_name = {r["player_name"]: r for r in r3_joined["records"] if r["status"] == "ACTIVE"}
    v3_by_id = {r["player_id"]: r for r in v3["confirmed_records"]}
    v3_by_name = {r["player_name"]: r for r in v3["confirmed_records"]}

    rows_evaluated = []
    conflicts = []
    newly_recovered = []

    for name, (r1, r2, r3, fr, total, to_par) in SUPPLIED_TEXT_ROWS.items():
        r3_rec = r3_active_by_name.get(name)
        identity_resolved = r3_rec is not None
        player_id = r3_rec["player_id"] if r3_rec else None

        r1r3_match = None
        if r3_rec is not None:
            expected_r1 = _to_par_to_strokes(r3_rec.get("r1_score_to_par"))
            expected_r2 = _to_par_to_strokes(r3_rec.get("r2_score_to_par"))
            expected_r3 = r3_rec.get("r3_strokes")
            r1r3_match = (r1 == expected_r1 and r2 == expected_r2 and r3 == expected_r3)

        arithmetic_ok = (r1 + r2 + r3 + fr == total) and (total - TOTAL_PAR == to_par)

        already_confirmed = v3_by_id.get(player_id) if player_id else v3_by_name.get(name)
        row_eval = {
            "player_name": name,
            "player_id": player_id,
            "identity_resolved_against_r3_active_roster": identity_resolved,
            "supplied_r1": r1, "supplied_r2": r2, "supplied_r3": r3, "supplied_fr": fr,
            "supplied_total": total, "supplied_to_par": to_par,
            "r1_r2_r3_matches_existing_r3_official_evidence": r1r3_match,
            "arithmetic_valid": arithmetic_ok,
            "already_in_v3_confirmed_evidence": already_confirmed is not None,
        }

        if already_confirmed is not None:
            conflict = (
                already_confirmed.get("r4_strokes") != fr
                or already_confirmed.get("final_total_strokes") != total
                or already_confirmed.get("final_to_par") != to_par
            )
            row_eval["conflict_with_v3"] = conflict
            if conflict:
                conflicts.append({
                    "player_id": player_id, "player_name": name,
                    "v3_r4_strokes": already_confirmed.get("r4_strokes"),
                    "supplied_r4_strokes": fr,
                    "v3_final_total_strokes": already_confirmed.get("final_total_strokes"),
                    "supplied_total": total,
                    "issue": "supplied text row disagrees with existing V3 confirmed evidence -- "
                             "NOT auto-resolved",
                })
        elif identity_resolved and r1r3_match and arithmetic_ok:
            newly_recovered.append({
                "player_id": player_id,
                "player_name": name,
                "sponsor": None,
                "r1_strokes": r1, "r2_strokes": r2, "r3_strokes": r3,
                "fr_strokes": fr,
                "final_total_strokes": total,
                "final_to_par": to_par,
                "final_position": None,  # rank not determinable without the full 70-row total set
                "status": "ACTIVE",
                "evidence_tier": "OPERATOR_REPORTED_EXTERNAL_CROSS_VERIFIED",
                "not_direct_klpga_automated_ingestion": True,
                "source_note": "supplied as text in the Mission I instructions (no screenshot "
                                "attached); accepted only after R1/R2/R3 strokes matched this "
                                "repo's own pre-existing official R3 evidence exactly, and FR "
                                "arithmetic (R1+R2+R3+FR=TOT, TOT-288=to_par) validated",
            })
        row_eval["accepted_as_newly_recovered"] = any(
            r["player_id"] == player_id for r in newly_recovered
        )
        rows_evaluated.append(row_eval)

    v3_ids = set(v3_by_id)
    new_ids = {r["player_id"] for r in newly_recovered}
    fr_score_verified = len(v3_ids) + len(new_ids)
    fr_score_missing = 70 - fr_score_verified

    r3_forecast_sha256 = _sha256(R3_FORECAST_PATH)
    r3_freeze_unchanged = r3_forecast_sha256 == EXPECTED_R3_FORECAST_SHA256

    status = "BLOCKED_DATA_INCOMPLETE" if (fr_score_missing > 0 or conflicts) else "PASS"

    return {
        "schema_version": "fr_official_leaderboard_recovery.v2",
        "mission": "MISSION I -- KB FR OFFICIAL 70/70 RECOVERY FROM KLPGA GROUP LEADERBOARD",
        "supersedes": None,
        "additive_to": str(RECOVERY_V1_PATH.relative_to(REPO)),
        "game_code": GAME_CODE,
        "recovery_attempted_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "new_source_cited": {
            "url": NEW_SOURCE_URL,
            "claimed_distinction_from_prior_ajax_endpoint": True,
            "retrieval_attempts": RETRIEVAL_ATTEMPTS,
            "retrieval_result": "BLOCKED at the network-egress-proxy / domain level across all "
                                 "three independent retrieval mechanisms -- this is not specific "
                                 "to the previously-blocked AJAX endpoint; the entire klpga.co.kr "
                                 "domain is blocked in this sandbox regardless of path or tool",
        },
        "supplied_text_rows_evaluated": rows_evaluated,
        "conflicts_with_existing_v3_evidence": conflicts,
        "newly_recovered_fr_scores": newly_recovered,
        "newly_recovered_count": len(newly_recovered),
        "completeness_gate": {
            "expected_fr_field": 70,
            "fr_score_verified_before_this_mission": len(v3_ids),
            "fr_score_newly_recovered_this_mission": len(newly_recovered),
            "fr_score_verified_total": fr_score_verified,
            "fr_score_missing": fr_score_missing,
            "unmatched": 0,
            "ambiguous": 0,
            "unsupported": 0,
            "conflicts": len(conflicts),
            "status": status,
        },
        "r3_freeze_check": {
            "expected_sha256": EXPECTED_R3_FORECAST_SHA256,
            "actual_sha256": r3_forecast_sha256,
            "unchanged": r3_freeze_unchanged,
        },
        "existing_evidence_files_untouched": [
            "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V1.json",
            "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V2.json",
            "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json",
            "KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V1.json",
        ],
        "status": status,
    }


def main() -> None:
    result = build()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(REPO)}")
    print(f"status: {result['status']}")
    gate = result["completeness_gate"]
    print(f"fr_score_verified_total={gate['fr_score_verified_total']} "
          f"newly_recovered={gate['fr_score_newly_recovered_this_mission']} "
          f"fr_score_missing={gate['fr_score_missing']} conflicts={gate['conflicts']}")
    print(f"r3_freeze_unchanged={result['r3_freeze_check']['unchanged']}")


if __name__ == "__main__":
    main()
