"""Tests for klpga.neo_win.ground_truth_diagnostic — the double-
verification CUT-status diagnostic. Never asserts MISSED_CUT_CANDIDATE
purely from Round 2/3 row absence without a valid completed Round 2
score, and never finalizes it past a REVIEW_REQUIRED conflict when it
disagrees with the derived cut line."""
from __future__ import annotations

from klpga.neo_win.ground_truth_diagnostic import (
    STATUS_DQ,
    STATUS_MADE_CUT,
    STATUS_MISSED_CUT_CANDIDATE,
    STATUS_REVIEW_REQUIRED,
    STATUS_WD,
    R3GroupingRow,
    build_ground_truth_table,
    raw_round_row_to_dict,
)
from klpga.parsers.leaderboard_parser import PlayerRoundRow


def _row(code, name, round_number, *, round2=None, status=None, rank=1, total_strokes=None):
    return PlayerRoundRow(
        game_code="G1", player_code=code, player_name=name, player_eng_name=None, round_number=round_number,
        rank_display=(status or str(rank)), rank=(None if status else rank), tie_flag=False, status=status,
        total_under_par_display=None, total_under_par=None,
        today_under_par_display=None, today_under_par=None,
        total_strokes=total_strokes, holes_completed="18",
        round1_score=None, round2_score=round2, round3_score=None, round4_score=None,
    )


def _r3(code, name="A", group="1조", tee_time="08:00", starting_tee=None):
    return R3GroupingRow(player_code=code, player_name=name, group=group, tee_time=tee_time, starting_tee=starting_tee)


# ---------------------------------------------------------------
# build_ground_truth_table — evidence-tier classification
# ---------------------------------------------------------------


def test_r3_grouping_present_means_made_cut_confirmed():
    r2 = [_row("p1", "A", 2, round2=68, total_strokes=140)]
    r3 = [_r3("p1", starting_tee="1")]
    rows, _summary = build_ground_truth_table([], r2, r3)
    row = rows[0]
    assert row.final_ground_truth_status == STATUS_MADE_CUT
    assert row.r3_grouping_present is True
    assert row.r3_group == "1조"
    assert row.r3_tee_time == "08:00"
    assert row.r3_starting_tee == "1"


def test_r2_explicit_wd_status_is_honored():
    r2 = [_row("p1", "A", 2, status="WD")]
    rows, _summary = build_ground_truth_table([], r2, [])
    assert rows[0].final_ground_truth_status == STATUS_WD
    assert "Round 2" in rows[0].reason


def test_r1_explicit_dq_status_is_honored_when_absent_from_r2():
    r1 = [_row("p1", "A", 1, status="DQ")]
    rows, _summary = build_ground_truth_table(r1, [], [])
    assert rows[0].final_ground_truth_status == STATUS_DQ
    assert "Round 1" in rows[0].reason


def test_wd_status_conflicting_with_r3_presence_is_review_required():
    """A real evidence conflict: official status says withdrawn, but
    the player is found in the real Round 3 grouping list. The hard
    gate says REVIEW_REQUIRED, never a silent pick of one source."""
    r2 = [_row("p1", "A", 2, status="WD")]
    r3 = [_r3("p1")]
    rows, _summary = build_ground_truth_table([], r2, r3)
    assert rows[0].final_ground_truth_status == STATUS_REVIEW_REQUIRED
    assert "conflict" in rows[0].reason


def test_absent_from_r3_with_valid_r2_score_is_missed_cut_candidate():
    r2 = [
        _row("p1", "A", 2, round2=68, total_strokes=140),  # confirmed continuer
        _row("p2", "B", 2, round2=75, total_strokes=147),  # absent from r3, worse score
    ]
    r3 = [_r3("p1")]
    rows, summary = build_ground_truth_table([], r2, r3)
    p2 = next(r for r in rows if r.player_code == "p2")
    assert p2.final_ground_truth_status == STATUS_MISSED_CUT_CANDIDATE
    assert summary["missed_cut_candidate_count"] == 1
    assert summary["derived_cut_line"] == 140


def test_missed_cut_candidate_beating_cut_line_becomes_review_required():
    """The core hard gate this diagnostic exists to enforce: a
    candidate whose real Round 2 score is as good as or better than
    the derived cut line conflicts with the real Round 3 field and
    must never be finalized as a missed-cut candidate."""
    r2 = [
        _row("p1", "A", 2, round2=70, total_strokes=140),  # confirmed continuer, cut line = 140
        _row("p2", "B", 2, round2=68, total_strokes=138),  # scored better than the cut line, absent from r3
    ]
    r3 = [_r3("p1")]
    rows, summary = build_ground_truth_table([], r2, r3)
    p2 = next(r for r in rows if r.player_code == "p2")
    assert p2.final_ground_truth_status == STATUS_REVIEW_REQUIRED
    assert "cut-line conflict" in p2.reason
    assert summary["cut_line_exceptions"] == ["p2"]
    assert summary["missed_cut_candidate_count"] == 0


def test_missed_cut_candidate_worse_than_cut_line_stays_candidate():
    r2 = [
        _row("p1", "A", 2, round2=70, total_strokes=140),
        _row("p2", "B", 2, round2=80, total_strokes=150),  # worse than the cut line
    ]
    r3 = [_r3("p1")]
    rows, summary = build_ground_truth_table([], r2, r3)
    p2 = next(r for r in rows if r.player_code == "p2")
    assert p2.final_ground_truth_status == STATUS_MISSED_CUT_CANDIDATE
    assert summary["cut_line_exceptions"] == []


def test_no_valid_r2_score_and_no_r3_membership_is_review_required():
    r1 = [_row("p1", "A", 1)]
    r3 = [_r3("p9", name="Someone Else")]  # real R3 data exists, but p1 has no R2 row at all
    rows, summary = build_ground_truth_table(r1, [], r3)
    p1 = next(r for r in rows if r.player_code == "p1")
    assert p1.final_ground_truth_status == STATUS_REVIEW_REQUIRED
    assert "insufficient evidence" in p1.reason
    assert summary["review_required_count"] >= 1


def test_no_r3_data_collected_yet_reports_distinct_reason_for_review_required_player():
    r1 = [_row("p1", "A", 1)]  # no r2 row, no r3 data at all
    rows, _summary = build_ground_truth_table(r1, [], [])
    assert rows[0].final_ground_truth_status == STATUS_REVIEW_REQUIRED
    assert "not collected yet" in rows[0].reason


def test_no_r3_data_collected_yet_still_produces_tentative_candidate():
    r2 = [_row("p1", "A", 2, round2=75, total_strokes=147)]
    rows, summary = build_ground_truth_table([], r2, [])
    assert rows[0].final_ground_truth_status == STATUS_MISSED_CUT_CANDIDATE
    assert "not collected yet" in rows[0].reason
    assert summary["derived_cut_line"] is None


def test_raw_r2_fields_preserved_in_comparison_row():
    r2 = [_row("p1", "A", 2, round2=68, rank=5, total_strokes=140)]
    rows, _summary = build_ground_truth_table([], r2, [])
    row = rows[0]
    assert row.r2_raw_rank == "5"
    assert row.r2_round_score == 68
    assert row.r2_total_score == 140


def test_player_code_is_the_only_join_key_never_name():
    r1 = [_row("p1", "Same Name", 1)]
    r2 = [_row("p2", "Same Name", 2, round2=70, total_strokes=140)]
    rows, summary = build_ground_truth_table(r1, r2, [])
    codes = {r.player_code for r in rows}
    assert codes == {"p1", "p2"}  # never collapsed by matching names
    assert summary["total_tournament_players"] == 2


# ---------------------------------------------------------------
# summary counts
# ---------------------------------------------------------------


def test_summary_counts_are_accurate():
    r1 = [_row("p1", "A", 1), _row("p2", "B", 1), _row("p3", "C", 1, status="DQ")]
    r2 = [
        _row("p1", "A", 2, round2=68, total_strokes=140),
        _row("p4", "D", 2, status="WD"),
    ]
    r3 = [_r3("p1")]
    rows, summary = build_ground_truth_table(r1, r2, r3)
    assert summary["total_tournament_players"] == 4  # p1, p2, p3, p4
    assert summary["r3_grouping_player_count"] == 1
    assert summary["r3_absent_count"] == 3
    assert summary["explicit_wd_count"] == 1  # p4
    assert summary["explicit_dq_count"] == 1  # p3
    assert summary["made_cut_confirmed_count"] == 1  # p1
    assert summary["review_required_count"] == 1  # p2 — no R2 row, no WD/DQ, no R3 membership


# ---------------------------------------------------------------
# raw_round_row_to_dict — every field preserved
# ---------------------------------------------------------------


def test_raw_round_row_to_dict_preserves_every_field():
    row = _row("p1", "A", 2, round2=68, rank=3, total_strokes=140)
    d = raw_round_row_to_dict(row)
    assert d["player_code"] == "p1"
    assert d["round2_score"] == 68
    assert d["rank_display"] == "3"
    assert d["total_strokes"] == 140
    assert "status" in d and "round1_score" in d and "round4_score" in d
