"""BUGFIX (fix/kb-r2-official-cut-gate-20260911): scripts/112's
cut_known was hardcoded `False` regardless of what the official
collection actually returned -- correct in effect against real KLPGA
data today (see r2_sg_pipeline/aggregate archaeology: the site has
never been observed emitting literal "CUT" text), but wrong in kind: a
hardcoded literal can never respond to real evidence, which is exactly
what klpga.neo_win.r2_readiness.assess_r2's own cut_known parameter
exists to gate on.

Regression coverage for scripts/112_kb_r2_active_cycle.py's new
_derive_cut_known(rows) -- the ONLY sanctioned signal is an explicit,
official per-row status=="CUT" (klpga.parsers.leaderboard_parser's own
literal data-rank="CUT" read, never a computation this pipeline
performs). Never inferred from rank, score, row count, a missing
player, cut-line arithmetic, or expected-field mismatch.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_operator_module():
    spec = importlib.util.spec_from_file_location("op112_cut_gate_under_test", SCRIPTS_DIR / "112_kb_r2_active_cycle.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_operator_module()


# ---------------------------------------------------------------------
# REQUIRED CASE 1: no explicit official CUT -> cut_known=False -> WAIT
# ---------------------------------------------------------------------

def test_no_explicit_cut_status_means_cut_known_false(module):
    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "ACTIVE", "holes_completed": "36"},
    ]
    assert module._derive_cut_known(rows) is False


def test_no_explicit_cut_status_propagates_to_wait_via_assess_r2(module):
    from klpga.neo_win.r2_readiness import assess_r2

    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "ACTIVE", "holes_completed": "36"},
    ]
    result = assess_r2(rows, ["p1", "p2"], official_page_available=True, cut_known=module._derive_cut_known(rows))
    assert result.decision == "WAIT"
    assert "no CUT inferred" in result.reason


def test_no_explicit_cut_status_propagates_to_skip_wait_via_decide_r2_cycle(module):
    from klpga.neo_win.r2_active_cycle import decide_r2_cycle

    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "ACTIVE", "holes_completed": "36"},
    ]
    decision = decide_r2_cycle(
        rows, ["p1", "p2"], official_page_available=True,
        cut_known=module._derive_cut_known(rows), freeze_exists=False,
    )
    assert decision.action == "SKIP_WAIT"


# ---------------------------------------------------------------------
# REQUIRED CASE 2: explicit official CUT -> cut_known=True
# ---------------------------------------------------------------------

def test_explicit_official_cut_status_means_cut_known_true(module):
    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "CUT", "holes_completed": "36"},
    ]
    assert module._derive_cut_known(rows) is True


def test_explicit_official_cut_status_allows_r2_complete_via_assess_r2(module):
    from klpga.neo_win.r2_readiness import assess_r2

    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "CUT", "holes_completed": "36"},
    ]
    result = assess_r2(rows, ["p1", "p2"], official_page_available=True, cut_known=module._derive_cut_known(rows))
    assert result.decision == "R2_COMPLETE"
    assert result.cutmakers == 1
    assert result.cut_players == 1


# ---------------------------------------------------------------------
# REQUIRED CASE 3: missing player alone must not establish CUT
# ---------------------------------------------------------------------

def test_missing_player_row_alone_does_not_establish_cut_known(module):
    # p2 is entirely absent from the collected rows (no row to read a
    # status off of) -- this must never be treated as CUT evidence,
    # only as an "entrant absent without official status" case handled
    # separately (and orthogonally) by assess_r2's own missing-player
    # check.
    rows = [{"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"}]
    assert module._derive_cut_known(rows) is False


def test_missing_player_alone_hard_stops_never_silently_becomes_cut(module):
    from klpga.neo_win.r2_readiness import assess_r2

    rows = [{"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"}]
    # Even if cut_known were somehow True, a genuinely missing player
    # (no WD/DQ/CUT evidence for them at all) must HARD_STOP, never be
    # silently absorbed as an implicit CUT.
    result = assess_r2(rows, ["p1", "p2"], official_page_available=True, cut_known=True)
    assert result.decision == "HARD_STOP"
    assert "absent without official" in result.reason


def test_many_missing_players_still_does_not_flip_cut_known(module):
    """A near-empty round response (most of the field not yet reported)
    must not be mistaken for a mass-CUT signal."""
    rows = [{"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"}]
    expected_ids = [f"p{i}" for i in range(1, 51)]  # 49 players missing
    assert module._derive_cut_known(rows) is False


# ---------------------------------------------------------------------
# REQUIRED CASE 4/5: explicit WD/DQ retain their own status, are never
# folded into or confused with a CUT determination.
# ---------------------------------------------------------------------

def test_wd_status_is_preserved_and_never_counted_as_cut(module):
    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "WD", "holes_completed": "36"},
    ]
    # WD alone (no CUT row anywhere) must not flip cut_known.
    assert module._derive_cut_known(rows) is False

    from klpga.neo_win.r2_readiness import assess_r2
    result = assess_r2(rows, ["p1", "p2"], official_page_available=True, cut_known=True)
    assert result.decision == "R2_COMPLETE"
    assert result.wd == 1
    assert result.cutmakers == 1  # only p1 -- WD is not a cutmaker
    assert result.cut_players == 0  # WD is not counted as CUT


def test_dq_status_is_preserved_and_never_counted_as_cut(module):
    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "DQ", "holes_completed": "36"},
    ]
    assert module._derive_cut_known(rows) is False

    from klpga.neo_win.r2_readiness import assess_r2
    result = assess_r2(rows, ["p1", "p2"], official_page_available=True, cut_known=True)
    assert result.decision == "R2_COMPLETE"
    assert result.dq == 1
    assert result.cut_players == 0


def test_wd_and_dq_coexist_with_a_real_cut_without_cross_contamination(module):
    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "CUT", "holes_completed": "36"},
        {"player_id": "p3", "status": "WD", "holes_completed": "36"},
        {"player_id": "p4", "status": "DQ", "holes_completed": "36"},
    ]
    assert module._derive_cut_known(rows) is True

    from klpga.neo_win.r2_readiness import assess_r2
    result = assess_r2(rows, ["p1", "p2", "p3", "p4"], official_page_available=True, cut_known=module._derive_cut_known(rows))
    assert result.decision == "R2_COMPLETE"
    assert result.cutmakers == 1
    assert result.cut_players == 1
    assert result.wd == 1
    assert result.dq == 1


# ---------------------------------------------------------------------
# Negative control: the confirmed data-rank="999" INCOMPLETE sentinel
# must never be treated as CUT evidence either (it is ambiguous, not a
# real CUT determination).
# ---------------------------------------------------------------------

def test_incomplete_sentinel_status_never_establishes_cut_known(module):
    rows = [
        {"player_id": "p1", "status": "ACTIVE", "holes_completed": "36"},
        {"player_id": "p2", "status": "INCOMPLETE", "holes_completed": None},
    ]
    assert module._derive_cut_known(rows) is False
