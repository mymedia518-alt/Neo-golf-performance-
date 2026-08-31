from klpga.neo_win.r2_readiness import assess_r2

def row(pid, status="ACTIVE", holes=36):
    return {"player_id": str(pid), "status": status, "holes_completed": holes}

def test_r2_requires_official_cut_and_preserves_statuses():
    rows = [row(1), row(2, "CUT"), row(3, "WD", None), row(4, "DQ", None)]
    assert assess_r2(rows, [1,2,3,4], cut_known=False).decision == "WAIT"
    result = assess_r2(rows, [1,2,3,4], cut_known=True)
    assert result.decision == "R2_COMPLETE" and result.cut_players == 1 and result.wd == 1 and result.dq == 1

def test_r2_blocks_future_data_and_duplicate_or_missing_identity():
    assert assess_r2([row(1)], [1], cut_known=True, future_round3_rows=1).decision == "HARD_STOP"
    assert assess_r2([row(1), row(1)], [1], cut_known=True).decision == "HARD_STOP"
    assert assess_r2([row(1)], [1,2], cut_known=True).decision == "HARD_STOP"

def test_r2_suspension_and_existing_freeze_wait_or_stop():
    assert assess_r2([row(1)], [1], cut_known=True, suspended=True).decision == "WAIT"
    assert assess_r2([row(1)], [1], cut_known=True, freeze_exists=True).decision == "HARD_STOP"
