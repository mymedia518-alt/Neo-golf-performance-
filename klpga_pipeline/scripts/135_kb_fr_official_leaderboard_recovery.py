#!/usr/bin/env python3
"""MISSION H -- KB FR OFFICIAL LEADERBOARD RECOVERY (data recovery only).

Attempts to recover the missing 31 of 70 official FR (4th-round) rows for
gameCode 2026090003 by joining EVERY existing evidence source already in
this repository -- it fabricates nothing. It:

  1. Loads the frozen R3-active roster (70 completers + 1 WD), which
     carries confirmed player_id/name/R1-R3 scores through R3 for the
     complete official field.
  2. Loads the existing 39-row confirmed FR evidence (V3) and proves it is
     a strict subset of the R3-active roster (39/39 overlap, 0 conflicts).
  3. For the remaining 31 R3-active completers, records their known
     identity + R1/R2/R3 scores (recoverable) alongside an explicit
     fr_score=null / final_total_strokes=null (NOT recoverable -- no
     source anywhere in the repo, cache, archive, warehouse, or an
     accessible official endpoint carries a 4th-round score for them).
  4. Verifies the R3 forecast freeze fingerprint is unchanged.

Writes content/website_v2/KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V1.json.
Never overwrites V1/V2/V3 FINAL evidence or the R3 freeze. No UI, no
deploy -- this is an evidence artifact only.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GAME_CODE = "2026090003"
PAR_PER_ROUND = 72

V3_PATH = REPO / "content/website_v2/KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json"
R3_JOINED_PATH = REPO / "evidence/KB_2026090003_R3/KB_2026090003_R3_OFFICIAL_FINAL_JOINED.json"
R3_FORECAST_PATH = REPO / "content/website_v2/2026090003_POST_R3_FINAL_FORECAST.json"
OUT_PATH = REPO / "content/website_v2/KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V1.json"

EXPECTED_R3_FORECAST_SHA256 = "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"

# Sources actually checked this mission (read-only), per SOURCE PRIORITY /
# SEARCH EXISTING ARCHIVES FIRST -- recorded for audit, not re-executed here.
SOURCES_CHECKED = [
    {"source": "repo-wide grep for 2026090003/KB금융/골든라이프/roundLeaderboard/"
               "getGameList/R4/FR/FINAL/result/score/player_id across "
               "raw/, archive/, snapshots/, content/, candidate/, data/, "
               "cache/, warehouse/, truth/, docs_internal_archive/, artifacts/",
     "result": "no file beyond the already-known V1/V2/V3 operator-supplied "
               "evidence contains 4th-round score data for this game_code"},
    {"source": "klpga_pipeline/data/raw_cache/{http,readiness}/",
     "result": "both directories exist and are empty -- no raw ingestion "
               "cache survives with round-4 content"},
    {"source": "all .db/.sqlite files in the repo and scratchpad "
               "(queried read-only via sqlite3)",
     "result": "no .db/.sqlite file exists in the repo itself; loose "
               "scratchpad test fixtures return 0 rows for "
               "game_code=2026090003 in every table"},
    {"source": "git log --all (file history of the V3 evidence file and a "
               "repo-wide search for any added-then-removed R4/FR-named path)",
     "result": "evidence file only ever grew 23 -> 38 -> 39 across V1/V2/V3; "
               "no larger version ever existed and was truncated; no "
               "R4/FR-named file was ever added and later removed"},
    {"source": "klpga_pipeline/content/website_v2/2026090003_VALIDATION_LEDGER.json",
     "result": "documents that the official site's own R3 raw capture "
               "carried a round4score column that was present in markup "
               "but EMPTY/unpopulated for every player at capture time -- "
               "direct evidence the source itself never exposed round-4 "
               "scores beyond what was later operator-supplied into V3"},
    {"source": "klpga_pipeline/content/website_v2/2026090003_OFFICIAL_KLPGA_RANKING.json",
     "result": "120-player season/career ranking document (ranking_category, "
               "week_evidence_state) -- useful only as a name/identity "
               "cross-reference, carries no per-round score data, so not "
               "used as FR score evidence"},
    {"source": "direct request to https://klpga.co.kr/ajax/tourInfo/getGameList",
     "result": "requests.exceptions.ProxyError: Max retries exceeded "
               "(Tunnel connection failed: 403 Forbidden) -- proxy-blocked, "
               "consistent with every prior attempt this project has made"},
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _to_par_to_strokes(to_par: float | int | None) -> int | None:
    if to_par is None:
        return None
    return PAR_PER_ROUND + int(to_par)


def build() -> dict:
    v3 = json.loads(V3_PATH.read_text(encoding="utf-8"))
    r3_joined = json.loads(R3_JOINED_PATH.read_text(encoding="utf-8"))

    r3_records = r3_joined["records"]
    r3_active = [r for r in r3_records if r["status"] == "ACTIVE"]
    r3_wd = [r for r in r3_records if r["status"] != "ACTIVE"]
    r3_active_by_id = {r["player_id"]: r for r in r3_active}

    v3_records = v3["confirmed_records"]
    v3_ids = {r["player_id"] for r in v3_records}

    conflicts = []
    overlap = 0
    for rec in v3_records:
        r3_rec = r3_active_by_id.get(rec["player_id"])
        if r3_rec is None:
            conflicts.append({
                "player_id": rec["player_id"], "player_name": rec["player_name"],
                "issue": "present in V3 confirmed evidence but NOT in the "
                         "R3-active completer roster",
            })
            continue
        overlap += 1
        # R1-R3 cross-check: V3's r1/r2/r3 strokes must match the R3-join's
        # to-par-derived strokes (both ultimately trace to the same R3
        # official evidence, so a mismatch would indicate a real conflict).
        for label, v3_field, r3_field in (
            ("r1", "r1_strokes", "r1_score_to_par"),
            ("r2", "r2_strokes", "r2_score_to_par"),
            ("r3", "r3_strokes", "r3_score_to_par"),
        ):
            v3_val = rec.get(v3_field)
            r3_val = _to_par_to_strokes(r3_rec.get(r3_field))
            if v3_val is not None and r3_val is not None and int(v3_val) != r3_val:
                conflicts.append({
                    "player_id": rec["player_id"], "player_name": rec["player_name"],
                    "round": label, "v3_value": v3_val, "r3_evidence_value": r3_val,
                    "issue": "round score disagreement between V3 confirmed "
                             "evidence and R3 official join",
                })

    missing_ids = set(r3_active_by_id) - v3_ids
    missing_records = []
    for pid in missing_ids:
        r = r3_active_by_id[pid]
        r1_strokes = _to_par_to_strokes(r.get("r1_score_to_par"))
        r2_strokes = _to_par_to_strokes(r.get("r2_score_to_par"))
        r3_strokes = r.get("r3_strokes")
        through_r3_total = r.get("total_strokes")
        missing_records.append({
            "player_id": pid,
            "player_name": r["player_name"],
            "sponsor": None,  # not present in any recovered source -- left
                               # blank per the sponsor invariant, never guessed
            "r1_strokes": r1_strokes,
            "r1_to_par": r.get("r1_score_to_par"),
            "r2_strokes": r2_strokes,
            "r2_to_par": r.get("r2_score_to_par"),
            "r3_strokes": r3_strokes,
            "r3_to_par": r.get("r3_score_to_par"),
            "through_r3_total_strokes": through_r3_total,
            "fr_score": None,
            "final_total_strokes": None,
            "final_to_par": None,
            "final_position": None,
            "status": "ACTIVE_THROUGH_R3",
            "recovery_status": "FR_SCORE_NOT_FOUND",
            "source_note": "identity + R1-R3 scores confirmed via "
                            "KB_2026090003_R3_OFFICIAL_FINAL_JOINED.json; "
                            "no FR/round-4 score located in any repository "
                            "archive, cache, warehouse, or accessible "
                            "official source during this recovery attempt",
        })
    missing_records.sort(key=lambda r: (r["through_r3_total_strokes"] or 0, r["player_id"]))

    wd_records = [{
        "player_id": r["player_id"], "player_name": r["player_name"],
        "status": r["status"], "note": "withdrew during R3 -- excluded from "
                                        "the 70-player official FR field per "
                                        "the frozen population chain",
    } for r in r3_wd]

    r3_forecast_sha256 = _sha256(R3_FORECAST_PATH)
    r3_freeze_unchanged = r3_forecast_sha256 == EXPECTED_R3_FORECAST_SHA256

    expected_fr_field = 70
    identity_accounted_for = len(r3_active)
    fr_score_verified = len(v3_ids)
    fr_score_missing = len(missing_records)

    status = (
        "BLOCKED_DATA_INCOMPLETE"
        if fr_score_missing > 0 or conflicts
        else "PASS"
    )

    return {
        "schema_version": "fr_official_leaderboard_recovery.v1",
        "mission": "MISSION H -- KB FR OFFICIAL LEADERBOARD RECOVERY",
        "game_code": GAME_CODE,
        "tournament_name": "2026 KB금융 골든라이프 챔피언십",
        "recovery_attempted_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "par_per_round": PAR_PER_ROUND,
        "source_priority_order": [
            "1. KLPGA official leaderboard/result data already present in repository/cache/archive",
            "2. Existing official KLPGA downloaded artifacts",
            "3. Existing tournament ingestion/archive reconstruction data",
            "4. Official KLPGA endpoint/page if accessible",
            "5. Operator-supplied official screenshots already available in project evidence",
        ],
        "sources_checked": SOURCES_CHECKED,
        "official_endpoint_access": {
            "attempted": True,
            "endpoint": "https://klpga.co.kr/ajax/tourInfo/getGameList",
            "result": "BLOCKED",
            "reason": "ProxyError 403 Forbidden on proxy tunnel",
        },
        "r3_active_completer_roster": {
            "source_artifact": str(R3_JOINED_PATH.relative_to(REPO)),
            "source_sha256": _sha256(R3_JOINED_PATH),
            "count": identity_accounted_for,
        },
        "r3_withdrawals_excluded_from_fr_field": wd_records,
        "existing_confirmed_evidence": {
            "source_artifact": str(V3_PATH.relative_to(REPO)),
            "source_sha256": _sha256(V3_PATH),
            "count": fr_score_verified,
            "immutable": True,
            "note": "39 confirmed rows are anchors; NOT overwritten or "
                    "reinterpreted by this recovery attempt",
        },
        "existing_39_overlap": {
            "expected_overlap": fr_score_verified,
            "actual_overlap": overlap,
            "conflicts": conflicts,
        },
        "recovered_new_fr_scores": 0,
        "missing_fr_scores": missing_records,
        "ambiguous": [],
        "unsupported": [],
        "completeness_gate": {
            "expected_fr_field": expected_fr_field,
            "identity_accounted_for": identity_accounted_for,
            "fr_score_verified": fr_score_verified,
            "fr_score_missing": fr_score_missing,
            "unmatched": 0,
            "ambiguous": 0,
            "unsupported": 0,
            "status": status,
        },
        "r3_freeze_check": {
            "expected_sha256": EXPECTED_R3_FORECAST_SHA256,
            "actual_sha256": r3_forecast_sha256,
            "unchanged": r3_freeze_unchanged,
        },
        "status": status,
    }


def main() -> None:
    result = build()
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH.relative_to(REPO)}")
    print(f"status: {result['status']}")
    gate = result["completeness_gate"]
    print(f"identity_accounted_for={gate['identity_accounted_for']} "
          f"fr_score_verified={gate['fr_score_verified']} "
          f"fr_score_missing={gate['fr_score_missing']}")
    print(f"r3_freeze_unchanged={result['r3_freeze_check']['unchanged']}")


if __name__ == "__main__":
    main()
