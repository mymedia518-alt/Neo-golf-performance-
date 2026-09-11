"""R3 HOUSE: klpga.neo_win.r3_readiness / r3_active_cycle -- the
completion/decision layer, no cut-known check (no new cut event at
R3)."""
from __future__ import annotations

from klpga.neo_win.r3_active_cycle import decide_r3_cycle
from klpga.neo_win.r3_readiness import assess_r3

EXPECTED = ["p1", "p2"]


def _row(pid, status="ACTIVE", holes="54"):
    return {"player_id": pid, "status": status, "holes_completed": holes}


def test_freeze_exists_hard_stops_refuses_overwrite():
    r = assess_r3([], EXPECTED, freeze_exists=True)
    assert r.decision == "HARD_STOP"
    assert "already exists" in r.reason


def test_future_round4_rows_hard_stops():
    r = assess_r3([], EXPECTED, future_round4_rows=3)
    assert r.decision == "HARD_STOP"


def test_official_page_unavailable_waits():
    r = assess_r3([], EXPECTED, official_page_available=False)
    assert r.decision == "WAIT"


def test_suspended_waits():
    r = assess_r3([_row("p1"), _row("p2")], EXPECTED, suspended=True)
    assert r.decision == "WAIT"


def test_duplicate_identity_hard_stops():
    r = assess_r3([_row("p1"), _row("p1")], EXPECTED)
    assert r.decision == "HARD_STOP"
    assert "duplicate" in r.reason


def test_unresolved_identity_hard_stops():
    r = assess_r3([_row("p1"), _row("p9")], EXPECTED)
    assert r.decision == "HARD_STOP"
    assert "unresolved identity" in r.reason


def test_missing_entrant_without_status_hard_stops():
    r = assess_r3([_row("p1")], EXPECTED)
    assert r.decision == "HARD_STOP"
    assert "absent without" in r.reason


def test_unrecognized_status_hard_stops():
    r = assess_r3([_row("p1", status="CUT"), _row("p2")], EXPECTED)
    assert r.decision == "HARD_STOP"
    assert "unrecognized" in r.reason


def test_incomplete_holes_waits():
    r = assess_r3([_row("p1", holes="36"), _row("p2")], EXPECTED)
    assert r.decision == "WAIT"


def test_wd_dq_dns_never_require_holes_completed():
    """A WD/DQ/DNS player structurally has no real R3 round -- their
    holes_completed is irrelevant to the completion check."""
    r = assess_r3([_row("p1", status="WD", holes=None), _row("p2")], EXPECTED)
    assert r.decision == "R3_COMPLETE"
    assert r.wd == 1
    assert r.active == 1


def test_complete_with_f_marker():
    r = assess_r3([_row("p1", holes="F"), _row("p2", holes="FINAL")], EXPECTED)
    assert r.decision == "R3_COMPLETE"
    assert r.active == 2


def test_decide_r3_cycle_wait_maps_to_skip_wait():
    decision = decide_r3_cycle([], EXPECTED, official_page_available=False)
    assert decision.action == "SKIP_WAIT"


def test_decide_r3_cycle_hard_stop_maps_to_hard_stop():
    decision = decide_r3_cycle([_row("p1"), _row("p1")], EXPECTED, official_page_available=True)
    assert decision.action == "HARD_STOP"


def test_decide_r3_cycle_complete_maps_to_publish_and_close():
    decision = decide_r3_cycle([_row("p1"), _row("p2")], EXPECTED, official_page_available=True)
    assert decision.action == "PUBLISH_AND_CLOSE"
    assert decision.readiness.decision == "R3_COMPLETE"
