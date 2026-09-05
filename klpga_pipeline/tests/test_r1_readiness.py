import pytest
from klpga.neo_win.r1_readiness import assess_r1

def row(pid, status="ACTIVE", holes=18, rank=1):
    return {"player_id": str(pid), "status": status, "holes_completed": holes, "rank": rank}

def test_complete_r1_preserves_wd_dq_and_does_not_create_cut():
    result = assess_r1([row(1), row(2, "WD", holes=None, rank=None), row(3, "DQ", holes=None, rank=None)], [1,2,3])
    assert result.decision == "R1_COMPLETE"
    assert result.wd == 1 and result.dq == 1


def test_incomplete_status_never_hard_stops_and_never_closes_r1():
    # klpga.parsers.leaderboard_parser's real, only-ever-observed
    # did-not-complete signal is status="INCOMPLETE" (the raw "999"
    # sentinel) -- a literal "WD"/"DQ" string has never actually been
    # seen live, and a bare INCOMPLETE is NOT itself official WD/DQ/DNS
    # evidence (klpga.neo_win.r1_final_reconciliation deliberately
    # rejects it too). It must never HARD_STOP as an "unrecognized
    # status" (that would just error-loop every cycle), but it must
    # ALSO never let the round reach R1_COMPLETE -- that would let the
    # live 30-minute cycle fire PUBLISH_AND_CLOSE and disable further
    # collection while this player's true status is still unconfirmed.
    # The correct outcome is a quiet WAIT: keep polling.
    result = assess_r1(
        [row(1), row(2, "INCOMPLETE", holes=None, rank=None)], [1, 2],
    )
    assert result.decision == "WAIT"
    assert "INCOMPLETE" in result.reason

def test_partial_and_suspended_r1_wait():
    assert assess_r1([row(1, holes=12), row(2)], [1,2]).decision == "WAIT"
    assert assess_r1([row(1), row(2)], [1,2], suspended=True).decision == "WAIT"

def test_identity_duplicate_and_missing_status_are_hard_stop():
    assert assess_r1([row(1), row(1)], [1]).decision == "HARD_STOP"
    assert assess_r1([row(1)], [1,2]).decision == "HARD_STOP"
    assert assess_r1([row(1), row(2, status="UNKNOWN")], [1,2]).decision == "HARD_STOP"

def test_54_hole_r1_never_uses_cut():
    result = assess_r1([row(1), row(2)], [1,2], expected_holes=18)
    assert result.decision == "R1_COMPLETE"
    assert not hasattr(result, "cut")
