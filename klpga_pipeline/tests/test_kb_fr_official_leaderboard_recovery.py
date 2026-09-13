"""MISSION H -- KB FR OFFICIAL LEADERBOARD RECOVERY: focused tests.

Proves the recovery attempt's reconciliation is internally correct and
that it never fabricates, overwrites, or weakens the existing evidence
chain. Does not touch shared production modules, so no full regression
run is required for this file per the mission's own Section 10.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "kb_fr_recovery", REPO / "scripts/135_kb_fr_official_leaderboard_recovery.py"
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules["kb_fr_recovery"] = mod
SPEC.loader.exec_module(mod)


def _result() -> dict:
    return mod.build()


def test_field_completeness_identity_is_70():
    r = _result()
    gate = r["completeness_gate"]
    assert gate["expected_fr_field"] == 70
    assert gate["identity_accounted_for"] == 70
    assert gate["unmatched"] == 0
    assert gate["ambiguous"] == 0
    assert gate["unsupported"] == 0


def test_unique_player_identity_across_missing_and_confirmed():
    r = _result()
    v3 = json.loads(mod.V3_PATH.read_text(encoding="utf-8"))
    confirmed_ids = {rec["player_id"] for rec in v3["confirmed_records"]}
    missing_ids = {rec["player_id"] for rec in r["missing_fr_scores"]}
    assert confirmed_ids.isdisjoint(missing_ids)
    assert len(missing_ids) == len(r["missing_fr_scores"])  # no duplicates
    assert len(confirmed_ids) + len(missing_ids) == r["r3_active_completer_roster"]["count"]


def test_39_row_overlap_is_exact_with_zero_conflicts():
    r = _result()
    overlap = r["existing_39_overlap"]
    assert overlap["actual_overlap"] == 39
    assert overlap["conflicts"] == []


def test_round_arithmetic_for_every_recovered_identity_row():
    """R1/R2/R3 strokes derived from to-par must satisfy strokes == par + to_par,
    and the through-R3 total must equal r1+r2+r3 strokes for every missing row."""
    r = _result()
    for rec in r["missing_fr_scores"]:
        assert rec["r1_strokes"] == mod.PAR_PER_ROUND + rec["r1_to_par"]
        assert rec["r2_strokes"] == mod.PAR_PER_ROUND + rec["r2_to_par"]
        assert rec["r3_strokes"] is not None
        assert rec["r1_strokes"] + rec["r2_strokes"] + rec["r3_strokes"] == rec["through_r3_total_strokes"]


def test_total_to_par_arithmetic_not_fabricated_for_missing_rows():
    """No missing row may carry a fabricated final_total_strokes/final_to_par/
    fr_score/final_position -- all four must be null (FR score genuinely unknown)."""
    r = _result()
    for rec in r["missing_fr_scores"]:
        assert rec["fr_score"] is None
        assert rec["final_total_strokes"] is None
        assert rec["final_to_par"] is None
        assert rec["final_position"] is None
        assert rec["recovery_status"] == "FR_SCORE_NOT_FOUND"


def test_special_status_wd_excluded_from_missing_and_from_70_field():
    r = _result()
    wd_ids = {rec["player_id"] for rec in r["r3_withdrawals_excluded_from_fr_field"]}
    assert "8881" in wd_ids  # 성유진, the known R3 WD
    missing_ids = {rec["player_id"] for rec in r["missing_fr_scores"]}
    assert wd_ids.isdisjoint(missing_ids)
    # WD + the 70-player active roster must not double count: WD is not
    # part of the "expected 70" field.
    assert r["r3_active_completer_roster"]["count"] == 70


def test_no_unsupported_player_generation():
    r = _result()
    assert r["unsupported"] == []
    assert r["ambiguous"] == []
    assert r["recovered_new_fr_scores"] == 0


def test_r3_freeze_unchanged():
    r = _result()
    check = r["r3_freeze_check"]
    assert check["expected_sha256"] == "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"
    assert check["actual_sha256"] == check["expected_sha256"]
    assert check["unchanged"] is True


def test_status_is_blocked_data_incomplete():
    r = _result()
    assert r["completeness_gate"]["fr_score_missing"] == 31
    assert r["status"] == "BLOCKED_DATA_INCOMPLETE"
    assert r["completeness_gate"]["status"] == "BLOCKED_DATA_INCOMPLETE"


def test_existing_v3_evidence_file_is_untouched_by_this_script():
    before = mod.V3_PATH.read_bytes()
    mod.build()  # running the recovery again must not mutate the source file
    after = mod.V3_PATH.read_bytes()
    assert before == after


def test_written_artifact_matches_in_memory_build(tmp_path):
    mod.main()
    on_disk = json.loads(mod.OUT_PATH.read_text(encoding="utf-8"))
    in_memory = mod.build()
    # recovery_attempted_at_utc will differ by seconds -- compare everything else
    on_disk.pop("recovery_attempted_at_utc")
    in_memory.pop("recovery_attempted_at_utc")
    assert on_disk == in_memory
