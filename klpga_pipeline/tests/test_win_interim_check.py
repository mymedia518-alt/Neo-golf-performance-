"""Tests for klpga.neo_win.win_interim_check — the R1 WIN% -> R2
leaderboard INTERIM CHECK (never a final WIN probability evaluation).
Hand-computed Spearman reference values, the <2-resolvable-pairs None
case, contention partitioning, and deterministic movement tie-breaking."""
from __future__ import annotations

import pytest

from klpga.neo_win.win_interim_check import (
    INTERIM_CHECK_LABEL,
    PlayerWinInterimRow,
    biggest_movements,
    spearman_rank_correlation,
    top_n_still_in_contention,
    win_interim_summary,
)


def _row(code, name, r1_rank, r1_pct, r2_pos):
    return PlayerWinInterimRow(
        player_code=code, player_name=name, r1_win_rank=r1_rank, r1_win_pct=r1_pct,
        r2_leaderboard_position=r2_pos,
    )


# ---------------------------------------------------------------
# spearman_rank_correlation — hand-computed reference values
# ---------------------------------------------------------------


def test_spearman_perfect_positive_correlation():
    rows = [_row("p1", "A", 1, 20.0, 1), _row("p2", "B", 2, 15.0, 2), _row("p3", "C", 3, 10.0, 3)]
    assert spearman_rank_correlation(rows) == pytest.approx(1.0)


def test_spearman_perfect_negative_correlation():
    rows = [_row("p1", "A", 1, 20.0, 3), _row("p2", "B", 2, 15.0, 2), _row("p3", "C", 3, 10.0, 1)]
    assert spearman_rank_correlation(rows) == pytest.approx(-1.0)


def test_spearman_hand_computed_mixed():
    # r1_win_rank = [1,2,3,4], r2_pos = [2,1,4,3]
    # d = [-1,1,-1,1] -> d^2 = [1,1,1,1] -> sum=4, n=4, denom=4*(16-1)=60
    # rho = 1 - 6*4/60 = 1 - 0.4 = 0.6
    rows = [
        _row("p1", "A", 1, 40.0, 2), _row("p2", "B", 2, 30.0, 1),
        _row("p3", "C", 3, 20.0, 4), _row("p4", "D", 4, 10.0, 3),
    ]
    assert spearman_rank_correlation(rows) == pytest.approx(0.6)


def test_spearman_none_when_fewer_than_two_resolvable_pairs():
    rows = [_row("p1", "A", 1, 20.0, 1), _row("p2", "B", 2, 15.0, None)]
    assert spearman_rank_correlation(rows) is None


def test_spearman_none_when_zero_resolvable_pairs():
    rows = [_row("p1", "A", 1, 20.0, None), _row("p2", "B", 2, 15.0, None)]
    assert spearman_rank_correlation(rows) is None


def test_spearman_ignores_unresolved_rows_computes_over_resolved_only():
    rows = [
        _row("p1", "A", 1, 30.0, 1), _row("p2", "B", 2, 20.0, 2),
        _row("p3", "C", 3, 10.0, None),
    ]
    assert spearman_rank_correlation(rows) == pytest.approx(1.0)


# ---------------------------------------------------------------
# top_n_still_in_contention
# ---------------------------------------------------------------


def test_top_n_partitions_still_in_fallen_out_unresolved():
    rows = [
        _row("p1", "A", 1, 40.0, 5),    # still in (<=20)
        _row("p2", "B", 2, 30.0, 25),   # fallen out (>20)
        _row("p3", "C", 3, 20.0, None), # unresolved
    ]
    result = top_n_still_in_contention(rows, n=3, contention_threshold=20)
    assert result["still_in_contention"] == ["p1"]
    assert result["fallen_out_of_contention"] == ["p2"]
    assert result["unresolved"] == ["p3"]
    assert result["n_players"] == 3


def test_top_n_only_considers_top_n_by_r1_win_rank():
    rows = [
        _row("p1", "A", 1, 50.0, 1),
        _row("p2", "B", 2, 40.0, 2),
        _row("p3", "C", 3, 30.0, 3),  # excluded, outside top 2
    ]
    result = top_n_still_in_contention(rows, n=2, contention_threshold=20)
    assert result["n_players"] == 2
    assert "p3" not in (result["still_in_contention"] + result["fallen_out_of_contention"] + result["unresolved"])


def test_top_n_boundary_equal_to_threshold_counts_as_still_in():
    rows = [_row("p1", "A", 1, 50.0, 20)]
    result = top_n_still_in_contention(rows, n=1, contention_threshold=20)
    assert result["still_in_contention"] == ["p1"]
    assert result["fallen_out_of_contention"] == []


# ---------------------------------------------------------------
# biggest_movements — deterministic ranking + tie-break
# ---------------------------------------------------------------


def test_biggest_movements_risers_and_fallers():
    rows = [
        _row("p1", "A", 5, 10.0, 1),   # moved up 4
        _row("p2", "B", 1, 40.0, 10),  # moved down 9
        _row("p3", "C", 3, 20.0, 3),   # no movement
    ]
    result = biggest_movements(rows, n=1)
    assert result["biggest_risers"][0]["player_code"] == "p1"
    assert result["biggest_risers"][0]["movement"] == 4
    assert result["biggest_fallers"][0]["player_code"] == "p2"
    assert result["biggest_fallers"][0]["movement"] == -9


def test_biggest_movements_excludes_unresolved():
    rows = [_row("p1", "A", 1, 40.0, 1), _row("p2", "B", 2, 30.0, None)]
    result = biggest_movements(rows, n=5)
    codes = {m["player_code"] for m in result["biggest_risers"]} | {m["player_code"] for m in result["biggest_fallers"]}
    assert "p2" not in codes


def test_biggest_movements_deterministic_tie_break_by_player_code():
    rows = [
        _row("p2", "B", 2, 30.0, 1),  # movement = 1
        _row("p1", "A", 2, 40.0, 1),  # movement = 1, same as p2 -> p1 sorts first
    ]
    result = biggest_movements(rows, n=2)
    risers_codes = [m["player_code"] for m in result["biggest_risers"]]
    assert risers_codes == ["p1", "p2"]


# ---------------------------------------------------------------
# win_interim_summary — integration + label
# ---------------------------------------------------------------


def test_summary_always_labeled_interim_never_final():
    rows = [_row("p1", "A", 1, 40.0, 1)]
    summary = win_interim_summary(rows)
    assert summary["label"] == INTERIM_CHECK_LABEL
    assert "INTERIM" in summary["label"]
    assert "NOT FINAL" in summary["label"]


def test_summary_reports_resolved_count_and_correlation():
    rows = [
        _row("p1", "A", 1, 40.0, 1), _row("p2", "B", 2, 30.0, 2),
        _row("p3", "C", 3, 20.0, None),
    ]
    summary = win_interim_summary(rows)
    assert summary["n_r1_players"] == 3
    assert summary["n_with_resolved_r2_position"] == 2
    assert summary["spearman_rank_correlation"] == pytest.approx(1.0)
    assert "top5" in summary and "top10" in summary and "movements" in summary
