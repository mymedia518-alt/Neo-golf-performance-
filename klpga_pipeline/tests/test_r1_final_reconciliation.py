from __future__ import annotations

from klpga.neo_win.r1_final_reconciliation import reconcile_r1_final


def row(pid, status=None, final_score=0, rank="1"):
    return {"player_id": str(pid), "official_status": status, "final_score": final_score, "rank_display": rank}


def test_passes_when_every_active_player_has_a_final_score():
    result = reconcile_r1_final([row(1), row(2)], [1, 2])
    assert result.passed is True
    assert result.active_confirmed == 2


def test_fails_when_a_normal_player_has_no_final_score():
    # "정상 선수는 R1 final score가 존재해야 완료 처리한다"
    result = reconcile_r1_final([row(1), row(2, final_score=None)], [1, 2])
    assert result.passed is False
    assert "final_score" in result.reason


def test_wd_dq_dns_are_exempt_from_the_final_score_requirement():
    result = reconcile_r1_final(
        [row(1), row(2, status="WD", final_score=None), row(3, status="DQ", final_score=None), row(4, status="DNS", final_score=None)],
        [1, 2, 3, 4],
    )
    assert result.passed is True
    assert result.wd == 1 and result.dq == 1 and result.dns == 1


def test_incomplete_is_never_inferred_as_wd_and_is_rejected_as_unrecognized():
    # The core requirement: this module has no concept of "INCOMPLETE"
    # at all (that is the LIVE collector's own internal label, derived
    # from the roundLeaderboard endpoint's raw 999 sentinel -- a
    # completely different endpoint from scoreRecord). If official_
    # status ever literally says "INCOMPLETE", that is treated exactly
    # like any other unrecognized value: FAIL, never silently folded
    # into WD.
    result = reconcile_r1_final([row(1), row(2, status="INCOMPLETE", final_score=None)], [1, 2])
    assert result.passed is False
    assert "unrecognized" in result.reason
    assert "INCOMPLETE" in result.reason


def test_unrecognized_status_fails_rather_than_being_guessed():
    result = reconcile_r1_final([row(1, status="SUSPENDED")], [1])
    assert result.passed is False
    assert "unrecognized" in result.reason


def test_missing_entrant_with_no_official_row_at_all_fails():
    # Every expected entrant must have SOME official record -- even a
    # withdrawn player must appear with an explicit WD row, not simply
    # be absent from the official source.
    result = reconcile_r1_final([row(1)], [1, 2])
    assert result.passed is False
    assert "no official scoreRecord row" in result.reason


def test_unresolved_identity_in_official_rows_fails():
    result = reconcile_r1_final([row(1), row("999-unknown")], [1])
    assert result.passed is False
    assert "unresolved/unexpected" in result.reason


def test_duplicate_identity_in_official_rows_fails():
    result = reconcile_r1_final([row(1), row(1)], [1])
    assert result.passed is False
    assert "duplicate" in result.reason


def test_identity_is_matched_by_player_id_only_never_by_name():
    # official_status/final_score carry no name field at all in the
    # reconciliation contract -- this test exists to document that
    # fact structurally: reconcile_r1_final only ever consumes
    # player_id, so a name mismatch elsewhere cannot silently mask an
    # identity error here.
    result = reconcile_r1_final([row(1)], [1])
    assert result.passed is True
    assert "player_name" not in row(1)
