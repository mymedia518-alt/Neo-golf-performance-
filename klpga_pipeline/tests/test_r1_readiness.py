import pytest
from klpga.neo_win.r1_readiness import assess_r1

def row(pid, status="ACTIVE", holes=18, rank=1):
    return {"player_id": str(pid), "status": status, "holes_completed": holes, "rank": rank}

def test_complete_r1_preserves_wd_dq_and_does_not_create_cut():
    result = assess_r1([row(1), row(2, "WD", holes=None, rank=None), row(3, "DQ", holes=None, rank=None)], [1,2,3])
    assert result.decision == "R1_COMPLETE"
    assert result.wd == 1 and result.dq == 1

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
