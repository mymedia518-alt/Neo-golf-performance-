"""Tests for klpga.neo_win.r1_r2_evaluation_report — Section D of the
R1->R2 pipeline. Synthetic frozen-R1 + reconciled-R2 fixtures only."""
from __future__ import annotations

import csv

from klpga.neo_win.cut_evaluation import CUT_OUTCOME_MADE, CUT_OUTCOME_MISSED, CUT_OUTCOME_UNRESOLVED
from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
from klpga.neo_win.r1_r2_evaluation_report import (
    build_player_cut_evaluation_rows,
    top5_best_and_biggest_misses,
    write_player_evaluation_csv,
)
from klpga.neo_win.r1_to_r2_reconciliation import PlayerR2Reconciled


def _frozen(code, name="A", rank=1, score=-3.0, cut=80.0):
    return PlayerR1Frozen(
        tournament_id="2026080001", player_code=code, player_name=name, r1_actual_rank=rank,
        r1_actual_score_to_par=score, r1_win_probability_pct=5.0, r1_make_cut_probability_pct=cut,
        model_version="001-C-R1", prediction_generated_at="2026-08-27T00:00:00Z",
    )


def _reconciled(code, name="A", position=10, score=-1, outcome=CUT_OUTCOME_MADE):
    return PlayerR2Reconciled(
        player_code=code, player_name=name, r2_position=position, r2_score_to_par=score,
        r2_outcome=outcome, in_frozen_r1=True, in_official_r2=True,
    )


def test_build_rows_joins_by_player_code():
    frozen = [_frozen("p1", cut=90.0), _frozen("p2", cut=20.0)]
    reconciled = [_reconciled("p1", outcome=CUT_OUTCOME_MADE), _reconciled("p2", outcome=CUT_OUTCOME_MISSED)]
    rows, excluded = build_player_cut_evaluation_rows(frozen, reconciled)
    assert excluded == []
    assert len(rows) == 2
    p1 = next(r for r in rows if r.player_code == "p1")
    assert p1.actual_cut == 1
    assert p1.predicted_cut_at_50 == 1


def test_build_rows_excludes_players_missing_r1_probability():
    frozen = [
        PlayerR1Frozen(
            tournament_id="t", player_code="p1", player_name="A", r1_actual_rank=1, r1_actual_score_to_par=-3.0,
            r1_win_probability_pct=5.0, r1_make_cut_probability_pct=None,
            model_version="001-C-R1", prediction_generated_at="t",
        )
    ]
    rows, excluded = build_player_cut_evaluation_rows(frozen, [])
    assert rows == []
    assert excluded == ["p1"]


def test_build_rows_player_absent_from_r2_is_unresolved_not_dropped():
    frozen = [_frozen("p1")]
    rows, excluded = build_player_cut_evaluation_rows(frozen, [])
    assert excluded == []
    assert len(rows) == 1
    assert rows[0].r2_outcome == CUT_OUTCOME_UNRESOLVED
    assert rows[0].actual_cut is None


def test_write_player_evaluation_csv(tmp_path):
    frozen = [_frozen("p1", cut=90.0)]
    reconciled = [_reconciled("p1", outcome=CUT_OUTCOME_MADE)]
    rows, _excluded = build_player_cut_evaluation_rows(frozen, reconciled)
    out_path = tmp_path / "r2" / "player_evaluation.csv"
    write_player_evaluation_csv(rows, out_path)
    assert out_path.exists()
    with open(out_path, newline="", encoding="utf-8") as f:
        csv_rows = list(csv.DictReader(f))
    assert csv_rows[0]["player_code"] == "p1"
    assert csv_rows[0]["actual_r2_status"] == CUT_OUTCOME_MADE
    assert csv_rows[0]["actual_cut"] == "1"


def test_top5_best_and_biggest_misses_uses_deterministic_ranking():
    frozen = [_frozen(f"p{i}", cut=90.0) for i in range(1, 8)]
    # p1 predicted 90 and made cut -> small error; p7 predicted 90 but missed -> large error.
    reconciled = [_reconciled(f"p{i}", outcome=CUT_OUTCOME_MADE) for i in range(1, 7)]
    reconciled.append(_reconciled("p7", outcome=CUT_OUTCOME_MISSED))
    rows, _excluded = build_player_cut_evaluation_rows(frozen, reconciled)
    result = top5_best_and_biggest_misses(rows)
    assert len(result["top5_best"]) == 5
    assert len(result["top5_biggest_misses"]) == 5
    assert result["top5_biggest_misses"][0]["player_code"] == "p7"
