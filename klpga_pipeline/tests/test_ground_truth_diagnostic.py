"""Tests for klpga.neo_win.ground_truth_diagnostic — the double-
verification CUT-status diagnostic. Never asserts MISSED_CUT from row
absence; only WD/DQ status text or real Round 3 grouping presence
ever produce a non-UNRESOLVED classification."""
from __future__ import annotations

from klpga.neo_win.ground_truth_diagnostic import (
    STATUS_CONFIRMED_CONTINUING,
    STATUS_DQ,
    STATUS_UNRESOLVED,
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


def _r3(code, name="A", group="1조", tee_time="08:00"):
    return R3GroupingRow(player_code=code, player_name=name, group=group, tee_time=tee_time)


# ---------------------------------------------------------------
# build_ground_truth_table — evidence-tier classification
# ---------------------------------------------------------------


def test_r3_grouping_present_means_confirmed_continuing():
    r2 = [_row("p1", "A", 2, round2=68)]
    r3 = [_r3("p1")]
    rows, _summary = build_ground_truth_table([], r2, r3)
    row = rows[0]
    assert row.proposed_cut_status == STATUS_CONFIRMED_CONTINUING
    assert row.r3_grouping_present is True
    assert row.r3_group == "1조"
    assert row.r3_tee_time == "08:00"


def test_r2_explicit_wd_status_is_honored():
    r2 = [_row("p1", "A", 2, status="WD")]
    rows, _summary = build_ground_truth_table([], r2, [])
    assert rows[0].proposed_cut_status == STATUS_WD
    assert "Round 2 status text" in rows[0].reason


def test_r1_explicit_dq_status_is_honored_when_absent_from_r2():
    r1 = [_row("p1", "A", 1, status="DQ")]
    rows, _summary = build_ground_truth_table(r1, [], [])
    assert rows[0].proposed_cut_status == STATUS_DQ
    assert "Round 1 status text" in rows[0].reason


def test_r3_grouping_present_wins_over_r2_ambiguous_status():
    """Real R3 grouping evidence is the strongest tier — it wins even
    if Round 2's own status text looks ambiguous (e.g. the 999/
    INCOMPLETE sentinel)."""
    r2 = [_row("p1", "A", 2, status="INCOMPLETE")]
    r3 = [_r3("p1")]
    rows, _summary = build_ground_truth_table([], r2, r3)
    assert rows[0].proposed_cut_status == STATUS_CONFIRMED_CONTINUING


def test_absent_from_r3_with_real_r3_data_available_is_unresolved_never_missed():
    """The core rule this diagnostic exists to enforce: absence from
    Round 3 grouping, even with real R3 data available for other
    players, is NEVER auto-classified as MISSED_CUT."""
    r1 = [_row("p1", "A", 1)]
    r2 = [_row("p1", "A", 2, round2=75)]
    r3 = [_r3("p9", name="Someone Else")]  # real R3 data exists, but p1 isn't in it
    rows, summary = build_ground_truth_table(r1, r2, r3)
    p1 = next(r for r in rows if r.player_code == "p1")
    assert p1.proposed_cut_status == STATUS_UNRESOLVED
    assert "insufficient to assert MISSED_CUT" in p1.reason
    assert summary["unexplained_count"] == 1


def test_no_r3_data_collected_yet_reports_distinct_reason():
    r2 = [_row("p1", "A", 2, round2=75)]
    rows, _summary = build_ground_truth_table([], r2, [])
    assert rows[0].proposed_cut_status == STATUS_UNRESOLVED
    assert "not collected yet" in rows[0].reason


def test_raw_r2_fields_preserved_in_comparison_row():
    r2 = [_row("p1", "A", 2, round2=68, rank=5, total_strokes=140)]
    rows, _summary = build_ground_truth_table([], r2, [])
    row = rows[0]
    assert row.r2_raw_rank == "5"
    assert row.r2_round_score == 68
    assert row.r2_total_score == 140


def test_player_code_is_the_only_join_key_never_name():
    r1 = [_row("p1", "Same Name", 1)]
    r2 = [_row("p2", "Same Name", 2, round2=70)]
    rows, summary = build_ground_truth_table(r1, r2, [])
    codes = {r.player_code for r in rows}
    assert codes == {"p1", "p2"}  # never collapsed by matching names
    assert summary["total_tournament_players"] == 2


# ---------------------------------------------------------------
# summary counts
# ---------------------------------------------------------------


def test_summary_counts_are_accurate():
    r1 = [_row("p1", "A", 1), _row("p2", "B", 1), _row("p3", "C", 1, status="DQ")]
    r2 = [_row("p1", "A", 2, round2=68), _row("p4", "D", 2, status="WD")]
    r3 = [_r3("p1")]
    rows, summary = build_ground_truth_table(r1, r2, r3)
    assert summary["total_tournament_players"] == 4  # p1, p2, p3, p4
    assert summary["r3_grouping_player_count"] == 1
    assert summary["r3_absent_count"] == 3
    assert summary["explicit_wd_count"] == 1  # p4
    assert summary["explicit_dq_count"] == 1  # p3
    assert summary["unexplained_count"] == 1  # p2 — no evidence anywhere


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
