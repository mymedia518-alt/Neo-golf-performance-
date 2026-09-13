"""MISSION I -- KB FR OFFICIAL 70/70 RECOVERY FROM KLPGA GROUP LEADERBOARD:
focused tests.

Covers: 4R section identification (the supplied rows are round-4/FR data,
distinguished from R1-R3 by cross-check against R3 evidence), complete
field accounting, unique identities, 39-row V3 reconciliation,
R1+R2+R3+FR=TOT, TOT-288=to_par, WD exclusion, no fabrication, R3 frozen
fingerprint, and previous-evidence immutability. Does not touch shared
production modules -- no full regression run required per the mission's
own test section.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "kb_fr_v2_reconciliation", REPO / "scripts/136_kb_fr_leaderboard_group_source_reconciliation.py"
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules["kb_fr_v2_reconciliation"] = mod
SPEC.loader.exec_module(mod)


def _result() -> dict:
    return mod.build()


def test_4r_section_identified_not_confused_with_r1_r3():
    """Every supplied row's R1/R2/R3 must independently match this repo's
    own R3-official evidence -- proving the 4th value in each tuple is
    genuinely the FR/round-4 score, not a mislabeled earlier round."""
    r = _result()
    for row in r["supplied_text_rows_evaluated"]:
        assert row["r1_r2_r3_matches_existing_r3_official_evidence"] is True


def test_new_source_retrieval_was_actually_attempted_and_blocked():
    r = _result()
    src = r["new_source_cited"]
    assert src["url"] == mod.NEW_SOURCE_URL
    assert len(src["retrieval_attempts"]) == 3
    methods = {a["method"] for a in src["retrieval_attempts"]}
    assert any("requests" in m for m in methods)
    assert any("Chromium" in m for m in methods)
    assert any("WebFetch" in m for m in methods)


def test_complete_field_count_and_no_pass_forced():
    r = _result()
    gate = r["completeness_gate"]
    assert gate["expected_fr_field"] == 70
    assert gate["fr_score_verified_total"] == 42
    assert gate["fr_score_missing"] == 28
    assert gate["status"] == "BLOCKED_DATA_INCOMPLETE"
    assert r["status"] == "BLOCKED_DATA_INCOMPLETE"


def test_unique_identities_among_newly_recovered():
    r = _result()
    ids = [row["player_id"] for row in r["newly_recovered_fr_scores"]]
    assert len(ids) == len(set(ids))
    assert len(ids) == 3


def test_39_row_v3_reconciliation_zero_unresolved_conflicts():
    r = _result()
    assert r["conflicts_with_existing_v3_evidence"] == []
    already_confirmed_rows = [row for row in r["supplied_text_rows_evaluated"]
                               if row["already_in_v3_confirmed_evidence"]]
    assert len(already_confirmed_rows) == 3  # 박보겸, 김우정, 빳차라쭈타 콩끄라판(I)
    for row in already_confirmed_rows:
        assert row["conflict_with_v3"] is False


def test_round_and_total_arithmetic_for_every_supplied_row():
    for name, (r1, r2, r3, fr, total, to_par) in mod.SUPPLIED_TEXT_ROWS.items():
        assert r1 + r2 + r3 + fr == total, name
        assert total - mod.TOTAL_PAR == to_par, name


def test_wd_player_not_present_among_supplied_or_recovered_rows():
    r = _result()
    wd_player_id = "8881"  # 성유진, known R3 WD -- excluded from the 70-field
    recovered_ids = {row["player_id"] for row in r["newly_recovered_fr_scores"]}
    assert wd_player_id not in recovered_ids


def test_no_fabrication_final_position_left_null_for_new_rows():
    r = _result()
    for row in r["newly_recovered_fr_scores"]:
        assert row["final_position"] is None
        assert row["sponsor"] is None
        assert row["evidence_tier"] == "OPERATOR_REPORTED_EXTERNAL_CROSS_VERIFIED"


def test_r3_frozen_fingerprint_unchanged():
    r = _result()
    check = r["r3_freeze_check"]
    assert check["expected_sha256"] == "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"
    assert check["actual_sha256"] == check["expected_sha256"]
    assert check["unchanged"] is True


def test_previous_evidence_files_immutable():
    before = {
        p: mod.REPO.joinpath("content/website_v2", p).read_bytes()
        for p in [
            "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V1.json",
            "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V2.json",
            "KB_2026090003_OPERATOR_SUPPLIED_OFFICIAL_SCREENSHOT_FINAL_V3.json",
            "KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V1.json",
        ]
    }
    mod.build()
    after = {
        p: mod.REPO.joinpath("content/website_v2", p).read_bytes()
        for p in before
    }
    assert before == after


def test_v2_artifact_is_additive_not_overwriting_v1():
    r = _result()
    assert r["additive_to"] == "content/website_v2/KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V1.json"
    assert mod.RECOVERY_V1_PATH.is_file()
    assert mod.OUT_PATH != mod.RECOVERY_V1_PATH
