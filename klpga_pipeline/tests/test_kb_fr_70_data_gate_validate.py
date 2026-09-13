"""MISSION J -- KB FR OFFICIAL 70/70 DATA GATE: focused tests.

Covers: complete FR population, identity uniqueness, ties, WD exclusion,
round arithmetic, to-par arithmetic, 39/39 crosscheck, no fabrication,
R3 fingerprint unchanged, previous-evidence immutability.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "kb_fr_v3_gate", REPO / "scripts/137_kb_fr_70_data_gate_validate.py"
)
mod = importlib.util.module_from_spec(SPEC)
sys.modules["kb_fr_v3_gate"] = mod
SPEC.loader.exec_module(mod)


def _result() -> dict:
    return mod.build()


def test_complete_fr_population_is_70():
    r = _result()
    gate = r["completeness_gate"]
    assert r["internal_completeness"]["row_count"] == 70
    assert gate["accounted_for"] == 70


def test_identity_uniqueness_70_unique_player_ids():
    r = _result()
    ids = list(r["resolved_player_ids_by_name"].values())
    assert len(ids) == 70
    assert len(set(ids)) == 70


def test_tie_position_notation_matches_independent_recomputation():
    supplied = json.loads(mod.SUPPLIED_PATH.read_text(encoding="utf-8"))
    players = sorted(supplied["players"], key=lambda p: p["to_par"])
    i, n = 0, len(players)
    while i < n:
        j = i
        while j < n and players[j]["to_par"] == players[i]["to_par"]:
            j += 1
        expected = str(i + 1) if (j - i) == 1 else f"T{i + 1}"
        for p in players[i:j]:
            assert p["final_position"] == expected, p["player_name"]
        i = j


def test_wd_player_excluded_from_70():
    r = _result()
    assert r["wd_exclusion"]["wd_present_in_supplied_70"] is False
    assert mod.R3_WD_PLAYER_ID not in r["resolved_player_ids_by_name"].values()


def test_round_arithmetic_zero_errors():
    r = _result()
    assert r["internal_completeness"]["arithmetic_errors"] == []
    assert r["completeness_gate"]["arithmetic_errors"] == 0


def test_to_par_arithmetic_independently():
    supplied = json.loads(mod.SUPPLIED_PATH.read_text(encoding="utf-8"))
    for p in supplied["players"]:
        assert p["r1_score"] + p["r2_score"] + p["r3_score"] + p["fr_score"] == p["total_strokes"]
        assert p["total_strokes"] - mod.TOTAL_PAR == p["to_par"]


def test_39_39_crosscheck_zero_conflicts():
    r = _result()
    assert r["existing_39_overlap"]["overlap_count"] == 39
    assert r["existing_39_overlap"]["conflicts"] == []


def test_no_fabrication_identity_resolved_against_frozen_r3_roster():
    r = _result()
    assert r["identity_resolution"]["unmatched"] == []
    assert r["identity_resolution"]["ambiguous_player_ids"] == []
    assert r["identity_resolution"]["r1_r2_r3_mismatches_vs_r3_evidence"] == []
    resolved_ids = set(r["resolved_player_ids_by_name"].values())
    r3 = json.loads(mod.R3_JOINED_PATH.read_text(encoding="utf-8"))
    r3_active_ids = {rec["player_id"] for rec in r3["records"] if rec["status"] == "ACTIVE"}
    assert resolved_ids == r3_active_ids


def test_r3_fingerprint_unchanged():
    r = _result()
    check = r["r3_freeze_check"]
    assert check["expected_sha256"] == "016d02966bd57f88f466a5acfb4da480d3895fa4f28181157472d5ef5622141f"
    assert check["actual_sha256"] == check["expected_sha256"]
    assert check["unchanged"] is True


def test_gate_status_pass():
    r = _result()
    assert r["status"] == "PASS"
    assert r["completeness_gate"]["status"] == "PASS"


def test_previous_evidence_files_immutable():
    paths = [
        mod.V3_PATH,
        REPO / "content/website_v2/KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V1.json",
        REPO / "content/website_v2/KB_2026090003_FR_OFFICIAL_LEADERBOARD_RECOVERY_V2.json",
    ]
    before = {p: p.read_bytes() for p in paths}
    mod.build()
    after = {p: p.read_bytes() for p in paths}
    assert before == after
