"""Tests for klpga.neo_win.r1_to_r2_reconciliation — Section B of the
R1->R2 evaluation pipeline. Synthetic frozen-R1 + official-R2 fixtures
only (never live R2 data); pins the exact status->outcome mapping and
the R1_PLAYERS/R2_PLAYERS/NEW_WD/NEW_DQ/CUT/MADE_CUT/MISSING/
UNMATCHED_PLAYER_CODES summary fields the spec requires."""
from __future__ import annotations

from klpga.neo_win.cut_evaluation import (
    CUT_OUTCOME_DQ,
    CUT_OUTCOME_MADE,
    CUT_OUTCOME_MISSED,
    CUT_OUTCOME_UNRESOLVED,
    CUT_OUTCOME_WD,
)
from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
from klpga.neo_win.r1_to_r2_reconciliation import (
    outcome_from_official_r2,
    reconcile_r1_to_r2,
)
from klpga.neo_win.round_reconciliation import NormalizedPlayer


def _frozen(code, name="A", rank=1, score=-3.0, win=10.0, cut=80.0):
    return PlayerR1Frozen(
        tournament_id="2026080001", player_code=code, player_name=name, r1_actual_rank=rank,
        r1_actual_score_to_par=score, r1_win_probability_pct=win, r1_make_cut_probability_pct=cut,
        model_version="001-C-R1", prediction_generated_at="2026-08-27T00:00:00Z",
    )


def _official(code, name="A", position=10, round_score=70, score_to_par=-2, status=None):
    return NormalizedPlayer(
        player_code=code, player_name=name, position_display=str(position) if position else None,
        position=position, round_score=round_score, score_to_par=score_to_par, status=status,
    )


# ---------------------------------------------------------------
# outcome_from_official_r2 — the status -> outcome mapping
# ---------------------------------------------------------------


def test_status_cut_maps_to_missed_cut():
    assert outcome_from_official_r2(_official("p1", status="CUT")) == CUT_OUTCOME_MISSED


def test_status_wd_maps_to_wd():
    assert outcome_from_official_r2(_official("p1", status="WD")) == CUT_OUTCOME_WD


def test_status_dq_maps_to_dq():
    assert outcome_from_official_r2(_official("p1", status="DQ")) == CUT_OUTCOME_DQ


def test_status_incomplete_sentinel_maps_to_unresolved_never_wd_or_dq():
    assert outcome_from_official_r2(_official("p1", status="INCOMPLETE")) == CUT_OUTCOME_UNRESOLVED


def test_no_status_with_real_score_maps_to_made_cut():
    assert outcome_from_official_r2(_official("p1", status=None, round_score=68)) == CUT_OUTCOME_MADE


def test_no_status_and_no_score_maps_to_unresolved():
    o = _official("p1", status=None, round_score=None, score_to_par=None)
    assert outcome_from_official_r2(o) == CUT_OUTCOME_UNRESOLVED


def test_absent_from_official_r2_entirely_maps_to_unresolved_never_guessed():
    assert outcome_from_official_r2(None) == CUT_OUTCOME_UNRESOLVED


def test_unrecognized_status_text_maps_to_unresolved_never_crashes():
    assert outcome_from_official_r2(_official("p1", status="SOME_NEW_UNSEEN_STATUS")) == CUT_OUTCOME_UNRESOLVED


# ---------------------------------------------------------------
# reconcile_r1_to_r2 — full field reconciliation + summary
# ---------------------------------------------------------------


def test_reconcile_full_field_summary_counts():
    frozen = [_frozen("p1"), _frozen("p2"), _frozen("p3"), _frozen("p4"), _frozen("p5")]
    official = {
        "p1": _official("p1", status=None, round_score=68),   # made cut
        "p2": _official("p2", status="CUT"),                   # missed cut
        "p3": _official("p3", status="WD"),
        "p4": _official("p4", status="DQ"),
        # p5 absent from official entirely -> unresolved
    }
    rows, summary = reconcile_r1_to_r2(frozen, official)
    assert summary["r1_players"] == 5
    assert summary["r2_players"] == 4
    assert summary["made_cut"] == 1
    assert summary["cut"] == 1
    assert summary["new_wd"] == 1
    assert summary["new_dq"] == 1
    assert summary["missing"] == 1
    assert summary["unmatched_player_codes"]["only_in_frozen_r1"] == ["p5"]
    assert summary["unmatched_player_codes"]["only_in_official_r2"] == []


def test_reconcile_reports_official_only_players_as_unmatched():
    frozen = [_frozen("p1")]
    official = {"p1": _official("p1", round_score=68), "p9": _official("p9", round_score=70)}
    _rows, summary = reconcile_r1_to_r2(frozen, official)
    assert summary["unmatched_player_codes"]["only_in_official_r2"] == ["p9"]


def test_reconcile_never_merges_by_name_only_by_player_code():
    frozen = [_frozen("p1", name="Same Name")]
    official = {"p2": _official("p2", name="Same Name", round_score=68)}
    rows, summary = reconcile_r1_to_r2(frozen, official)
    codes = {r.player_code for r in rows}
    assert codes == {"p1", "p2"}  # never collapsed into one row by matching names
    assert summary["unmatched_player_codes"]["only_in_frozen_r1"] == ["p1"]
    assert summary["unmatched_player_codes"]["only_in_official_r2"] == ["p2"]


def test_reconcile_row_carries_real_r2_position_and_score():
    frozen = [_frozen("p1")]
    official = {"p1": _official("p1", position=7, round_score=69, score_to_par=-1)}
    rows, _summary = reconcile_r1_to_r2(frozen, official)
    row = rows[0]
    assert row.r2_position == 7
    assert row.r2_score_to_par == -1
    assert row.r2_outcome == CUT_OUTCOME_MADE
    assert row.in_frozen_r1 is True
    assert row.in_official_r2 is True


def test_reconcile_empty_official_r2_reports_all_frozen_players_unresolved():
    frozen = [_frozen("p1"), _frozen("p2")]
    rows, summary = reconcile_r1_to_r2(frozen, {})
    assert summary["r2_players"] == 0
    assert summary["missing"] == 2
    assert all(r.r2_outcome == CUT_OUTCOME_UNRESOLVED for r in rows)
