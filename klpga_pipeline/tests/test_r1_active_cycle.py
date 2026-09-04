from __future__ import annotations

import datetime

from klpga.neo_win.r1_active_cycle import CycleDecision, assess_r1_snapshot_safety, decide_cycle

EXPECTED = ["1", "2", "3"]
NOW = datetime.datetime(2026, 9, 4, 6, 0, tzinfo=datetime.timezone.utc)


def _row(pid, status="ACTIVE", holes="18"):
    return {"player_id": pid, "status": status, "holes_completed": holes, "rank": 1}


def test_snapshot_safety_rejects_empty_collection():
    result = assess_r1_snapshot_safety([], EXPECTED)
    assert result.safe is False and "empty" in result.reason


def test_snapshot_safety_rejects_duplicate_identity():
    rows = [_row("1"), _row("1")]
    result = assess_r1_snapshot_safety(rows, EXPECTED)
    assert result.safe is False and "duplicate" in result.reason


def test_snapshot_safety_rejects_unknown_identity():
    rows = [_row("1"), _row("999")]
    result = assess_r1_snapshot_safety(rows, EXPECTED)
    assert result.safe is False and "unresolved" in result.reason


def test_snapshot_safety_accepts_a_mixed_in_progress_field():
    # A player still mid-round (holes_completed < 18) is exactly what a
    # legitimate in-progress R1 snapshot looks like -- not a defect.
    rows = [_row("1", holes="9"), _row("2", holes="18"), _row("3", holes="4")]
    result = assess_r1_snapshot_safety(rows, EXPECTED)
    assert result.safe is True and result.row_count == 3


def test_decide_cycle_waits_when_official_page_unavailable():
    decision = decide_cycle([], EXPECTED, official_page_available=False, tournament_finished=False, now=NOW)
    assert decision.action == "SKIP_WAIT"
    assert decision.retrieved_at == "2026-09-04T06:00:00Z"


def test_decide_cycle_hard_stops_on_corrupted_snapshot():
    rows = [_row("1"), _row("1")]
    decision = decide_cycle(rows, EXPECTED, official_page_available=True, tournament_finished=False, now=NOW)
    assert decision.action == "HARD_STOP"
    assert "duplicate" in decision.reason


def test_decide_cycle_publishes_a_safe_in_progress_snapshot():
    rows = [_row("1", holes="9"), _row("2", holes="18"), _row("3", holes="4")]
    decision = decide_cycle(rows, EXPECTED, official_page_available=True, tournament_finished=False, now=NOW)
    assert decision.action == "PUBLISH"
    assert decision.r1_status == "WAIT"
    assert decision.row_count == 3


def test_decide_cycle_publishes_and_closes_on_full_r1_completion():
    rows = [_row("1", holes="18"), _row("2", holes="18"), _row("3", status="WD", holes="9")]
    decision = decide_cycle(rows, EXPECTED, official_page_available=True, tournament_finished=False, now=NOW)
    assert decision.action == "PUBLISH_AND_CLOSE"
    assert decision.r1_status == "R1_COMPLETE"


def test_decide_cycle_hard_stops_when_completion_gate_finds_a_real_problem():
    # An entrant absent from the official rows without any WD/DQ/DNS
    # status is a real data-integrity problem, not "still in progress".
    rows = [_row("1", holes="18"), _row("2", holes="18")]  # "3" is missing entirely
    decision = decide_cycle(rows, EXPECTED, official_page_available=True, tournament_finished=False, now=NOW)
    assert decision.action == "HARD_STOP"
    assert decision.r1_status == "HARD_STOP"


def test_cycle_decision_is_immutable():
    decision = CycleDecision("SKIP_WAIT", "x", "2026-09-04T06:00:00Z")
    try:
        decision.action = "PUBLISH"  # type: ignore[misc]
        assert False, "CycleDecision must be frozen"
    except Exception:
        pass
