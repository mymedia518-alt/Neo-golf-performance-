#!/usr/bin/env python3
"""MISSION J -- KB FR OFFICIAL 70/70 DATA GATE.

Validates the operator-supplied KB_2026090003_KLPGA_OFFICIAL_FR_70_SUPPLIED.json
(a real uploaded file, copied into evidence/KB_2026090003_FR/ with its
sha256 recorded) against:

  1. Internal completeness: row_count==70, unique player names, R1+R2+R3+FR
     ==total_strokes, total_strokes-288==to_par for every row.
  2. Identity resolution: every supplied player_name must resolve to
     exactly one player_id in the frozen 70-player R3-active roster
     (KB_2026090003_R3_OFFICIAL_FINAL_JOINED.json), and that player's
     R1/R2/R3 strokes (derived from the R3 evidence) must match the
     supplied R1/R2/R3 exactly -- this is what proves the supplied FR
     column is genuinely this tournament's 4th round, not a different
     round or a different tournament.
  3. WD exclusion: 성유진 (player_id 8881, R3 WD) must NOT appear in the
     supplied 70 rows.
  4. 39/39 cross-check: every one of V3's 39 confirmed rows must appear in
     the supplied data with identical r1/r2/r3/fr/total/to_par -- any
     disagreement is a CONFLICT, never silently overwritten.

Writes content/website_v2/KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V3.json
(additive -- V1/V2/V3 screenshot evidence and RECOVERY_V1/V2 untouched).
Never modifies R3 freeze or /final/.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GAME_CODE = "2026090003"
PAR_PER_ROUND = 72
TOTAL_PAR = PAR_PER_ROUND * 4  # 288
EXPECTED_FR_FIELD = 70
R3_WD_PLAYER_ID = "8881"  # 성유진

SUPPLIED_PATH = REPO / "evidence/KB_2026090003_FR/KB_2026090003_KLPGA_OFFICIAL_FR_70_SUPPLIED.json"
V3_PATH = REPO / "content/website_v2/KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
R3_JOINED_PATH = REPO / "evidence/KB_2026090003_R3/KB_2026090003_R3_OFFICIAL_FINAL_JOINED.json"
R3_FORECAST_PATH = REPO / "content/website_v2/2026090003_POST_R3_FINAL_FORECAST.json"
OUT_PATH = REPO / "content/website_v2/KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V3.json"

EXPECTED_R3_FORECAST_SHA256 = "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _to_par_to_strokes(to_par) -> int | None:
    if to_par is None:
        return None
    return PAR_PER_ROUND + int(to_par)


def build() -> dict:
    supplied = json.loads(SUPPLIED_PATH.read_text(encoding="utf-8"))
    v3 = json.loads(V3_PATH.read_text(encoding="utf-8"))
    r3_joined = json.loads(R3_JOINED_PATH.read_text(encoding="utf-8"))

    players = supplied["players"]
    r3_active_by_name = {r["player_name"]: r for r in r3_joined["records"] if r["status"] == "ACTIVE"}
    v3_by_name = {r["player_name"]: r for r in v3["confirmed_records"]}

    # -- 1. internal completeness ------------------------------------
    row_count = len(players)
    names = [p["player_name"] for p in players]
    name_counts = Counter(names)
    duplicate_names = [n for n, c in name_counts.items() if c > 1]
    unique_names = len(duplicate_names) == 0

    arithmetic_errors = []
    for p in players:
        r1, r2, r3, fr = p["r1_score"], p["r2_score"], p["r3_score"], p["fr_score"]
        total, to_par = p["total_strokes"], p["to_par"]
        if r1 + r2 + r3 + fr != total:
            arithmetic_errors.append({"player_name": p["player_name"], "issue": "round_sum",
                                       "computed": r1 + r2 + r3 + fr, "supplied_total": total})
        if total - TOTAL_PAR != to_par:
            arithmetic_errors.append({"player_name": p["player_name"], "issue": "to_par",
                                       "computed": total - TOTAL_PAR, "supplied_to_par": to_par})

    # -- 2. identity resolution against frozen R3-active roster -------
    unmatched = []
    ambiguous = []
    r1r3_mismatches = []
    resolved = {}
    for p in players:
        name = p["player_name"]
        r3_rec = r3_active_by_name.get(name)
        if r3_rec is None:
            unmatched.append(name)
            continue
        expected_r1 = _to_par_to_strokes(r3_rec.get("r1_score_to_par"))
        expected_r2 = _to_par_to_strokes(r3_rec.get("r2_score_to_par"))
        expected_r3 = r3_rec.get("r3_strokes")
        if (p["r1_score"], p["r2_score"], p["r3_score"]) != (expected_r1, expected_r2, expected_r3):
            r1r3_mismatches.append({
                "player_name": name, "player_id": r3_rec["player_id"],
                "supplied": [p["r1_score"], p["r2_score"], p["r3_score"]],
                "expected_from_r3_evidence": [expected_r1, expected_r2, expected_r3],
            })
            continue
        resolved[name] = r3_rec["player_id"]

    # duplicate player_id resolution would be a real ambiguity (two names
    # mapping to the same roster player) -- check for it explicitly.
    id_counts = Counter(resolved.values())
    ambiguous = [pid for pid, c in id_counts.items() if c > 1]

    # -- 3. WD exclusion -----------------------------------------------
    wd_present = any(pid == R3_WD_PLAYER_ID for pid in resolved.values())

    # -- 4. 39/39 cross-check against V3 --------------------------------
    conflicts = []
    overlap = 0
    supplied_by_name = {p["player_name"]: p for p in players}
    for name, v3_rec in v3_by_name.items():
        sp = supplied_by_name.get(name)
        if sp is None:
            conflicts.append({"player_name": name, "issue": "present in V3 but missing from supplied 70-row dataset"})
            continue
        overlap += 1
        if (sp["r1_score"], sp["r2_score"], sp["r3_score"], sp["fr_score"], sp["total_strokes"], sp["to_par"]) != (
            v3_rec["r1_strokes"], v3_rec["r2_strokes"], v3_rec["r3_strokes"], v3_rec["r4_strokes"],
            v3_rec["final_total_strokes"], v3_rec["final_to_par"],
        ):
            conflicts.append({
                "player_name": name, "player_id": v3_rec["player_id"],
                "v3": [v3_rec["r1_strokes"], v3_rec["r2_strokes"], v3_rec["r3_strokes"],
                       v3_rec["r4_strokes"], v3_rec["final_total_strokes"], v3_rec["final_to_par"]],
                "supplied": [sp["r1_score"], sp["r2_score"], sp["r3_score"], sp["fr_score"],
                             sp["total_strokes"], sp["to_par"]],
                "issue": "supplied 70-row dataset disagrees with V3 confirmed evidence",
            })

    accounted_for = len(resolved)
    r3_forecast_sha256 = _sha256(R3_FORECAST_PATH)
    r3_freeze_unchanged = r3_forecast_sha256 == EXPECTED_R3_FORECAST_SHA256

    gate_pass = (
        row_count == EXPECTED_FR_FIELD
        and unique_names
        and not arithmetic_errors
        and not unmatched
        and not ambiguous
        and not r1r3_mismatches
        and not wd_present
        and overlap == 39
        and not conflicts
        and accounted_for == EXPECTED_FR_FIELD
        and r3_freeze_unchanged
    )

    status = "PASS" if gate_pass else "BLOCKED_DATA_INCOMPLETE"

    return {
        "schema_version": "fr_official_leaderboard_recovery.v3",
        "mission": "MISSION J -- KB FR OFFICIAL 70/70 DATA GATE",
        "additive_to": [
            "KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V1.json",
            "KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V2.json",
        ],
        "game_code": GAME_CODE,
        "validated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "supplied_source": {
            "file": str(SUPPLIED_PATH.relative_to(REPO)),
            "sha256": _sha256(SUPPLIED_PATH),
            "declared_source_url": supplied.get("source_url"),
            "declared_row_count": supplied.get("row_count"),
        },
        "internal_completeness": {
            "row_count": row_count,
            "row_count_ok": row_count == EXPECTED_FR_FIELD,
            "unique_names": unique_names,
            "duplicate_names": duplicate_names,
            "arithmetic_errors": arithmetic_errors,
        },
        "identity_resolution": {
            "unmatched": unmatched,
            "ambiguous_player_ids": ambiguous,
            "r1_r2_r3_mismatches_vs_r3_evidence": r1r3_mismatches,
            "resolved_count": accounted_for,
        },
        "wd_exclusion": {
            "wd_player_id": R3_WD_PLAYER_ID,
            "wd_present_in_supplied_70": wd_present,
        },
        "existing_39_overlap": {
            "overlap_count": overlap,
            "conflicts": conflicts,
        },
        "completeness_gate": {
            "expected_fr_field": EXPECTED_FR_FIELD,
            "accounted_for": accounted_for,
            "ambiguous": len(ambiguous),
            "unsupported": len(unmatched),
            "arithmetic_errors": len(arithmetic_errors),
            "conflicts": len(conflicts),
            "status": status,
        },
        "r3_freeze_check": {
            "expected_sha256": EXPECTED_R3_FORECAST_SHA256,
            "actual_sha256": r3_forecast_sha256,
            "unchanged": r3_freeze_unchanged,
        },
        "resolved_player_ids_by_name": resolved,
        "status": status,
    }


def main() -> None:
    result = build()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(REPO)}")
    print(f"status: {result['status']}")
    gate = result["completeness_gate"]
    print(f"accounted_for={gate['accounted_for']} ambiguous={gate['ambiguous']} "
          f"unsupported={gate['unsupported']} arithmetic_errors={gate['arithmetic_errors']} "
          f"conflicts={gate['conflicts']}")
    print(f"39/39 overlap: {result['existing_39_overlap']['overlap_count']}")
    print(f"r3_freeze_unchanged={result['r3_freeze_check']['unchanged']}")


if __name__ == "__main__":
    main()
