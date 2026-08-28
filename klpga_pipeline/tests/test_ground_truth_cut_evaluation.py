"""Tests for klpga.neo_win.ground_truth_cut_evaluation — the bridge
from klpga.neo_win.ground_truth_diagnostic's R2 x R3 double-verified
ground truth into klpga.neo_win.r1_to_r2_reconciliation.PlayerR2Reconciled,
so the existing evaluation pipeline consumes it unchanged."""
from __future__ import annotations

import pytest

from klpga.neo_win.cut_evaluation import (
    CUT_OUTCOME_DQ,
    CUT_OUTCOME_MADE,
    CUT_OUTCOME_MISSED,
    CUT_OUTCOME_UNRESOLVED,
    CUT_OUTCOME_WD_AFTER_R1_START,
)
from klpga.neo_win.ground_truth_cut_evaluation import (
    summarize_ground_truth_reconciliation,
    to_player_r2_reconciled_rows,
)
from klpga.neo_win.ground_truth_diagnostic import GroundTruthRow, STATUS_MADE_CUT, STATUS_MISSED_CUT_CANDIDATE, STATUS_REVIEW_REQUIRED, STATUS_WD
from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
from klpga.neo_win.round_reconciliation import NormalizedPlayer


def _gt_row(code, status, name="A", r2_present=True):
    return GroundTruthRow(
        player_code=code, official_name=name, r1_present=True, r2_present=r2_present,
        r2_raw_rank="1", r2_raw_status=None, r2_round_score=70, r2_total_score=140,
        r3_grouping_present=(status == STATUS_MADE_CUT), r3_group=None, r3_tee_time=None, r3_starting_tee=None,
        final_ground_truth_status=status, reason="test",
    )


def _frozen(code, make_cut_pct=60.0):
    return PlayerR1Frozen(
        tournament_id="G1", player_code=code, player_name="A", r1_actual_rank=1, r1_actual_score_to_par=-2,
        r1_win_probability_pct=5.0, r1_make_cut_probability_pct=make_cut_pct,
        model_version="v1", prediction_generated_at="2026-08-28T00:00:00",
    )


def _official_r2(code, position=1):
    return {code: NormalizedPlayer(player_code=code, player_name="A", position_display=str(position), position=position, round_score=70, score_to_par=-2, status=None)}


# ---------------------------------------------------------------
# to_player_r2_reconciled_rows — status mapping
# ---------------------------------------------------------------


def test_made_cut_confirmed_maps_to_made_cut():
    rows, conflicts = to_player_r2_reconciled_rows([_gt_row("p1", STATUS_MADE_CUT)], _official_r2("p1"))
    assert rows[0].r2_outcome == CUT_OUTCOME_MADE
    assert conflicts == []


def test_missed_cut_candidate_maps_to_missed_cut():
    rows, _ = to_player_r2_reconciled_rows([_gt_row("p1", STATUS_MISSED_CUT_CANDIDATE)], {})
    assert rows[0].r2_outcome == CUT_OUTCOME_MISSED


def test_review_required_maps_to_unresolved():
    rows, _ = to_player_r2_reconciled_rows([_gt_row("p1", STATUS_REVIEW_REQUIRED)], {})
    assert rows[0].r2_outcome == CUT_OUTCOME_UNRESOLVED


def test_real_r2_position_and_score_pulled_from_normalized_r2_not_ground_truth():
    rows, _ = to_player_r2_reconciled_rows([_gt_row("p1", STATUS_MADE_CUT)], _official_r2("p1", position=5))
    assert rows[0].r2_position == 5
    assert rows[0].r2_score_to_par == -2


# ---------------------------------------------------------------
# explicit_status_overrides — real, human-verified WD/DQ evidence
# ---------------------------------------------------------------


def test_explicit_wd_override_maps_to_wd_after_r1_start_not_generic_wd():
    rows, conflicts = to_player_r2_reconciled_rows(
        [_gt_row("p1", STATUS_REVIEW_REQUIRED, r2_present=True)], {}, explicit_status_overrides={"p1": "WD"}
    )
    assert rows[0].r2_outcome == CUT_OUTCOME_WD_AFTER_R1_START
    assert conflicts == []


def test_explicit_dq_override():
    rows, _ = to_player_r2_reconciled_rows(
        [_gt_row("p1", STATUS_REVIEW_REQUIRED)], {}, explicit_status_overrides={"p1": "DQ"}
    )
    assert rows[0].r2_outcome == CUT_OUTCOME_DQ


def test_override_conflicting_with_real_r3_presence_is_never_silently_trusted():
    """The core hard gate: real Round 3 grouping presence (MADE_CUT_CONFIRMED)
    conflicting with a human-supplied WD override must stay UNRESOLVED
    and be surfaced as a conflict — never silently pick one side."""
    rows, conflicts = to_player_r2_reconciled_rows(
        [_gt_row("p1", STATUS_MADE_CUT)], _official_r2("p1"), explicit_status_overrides={"p1": "WD"}
    )
    assert rows[0].r2_outcome == CUT_OUTCOME_UNRESOLVED
    assert len(conflicts) == 1
    assert conflicts[0]["player_code"] == "p1"


def test_invalid_override_value_raises():
    with pytest.raises(ValueError, match="WD.*DQ"):
        to_player_r2_reconciled_rows([_gt_row("p1", STATUS_REVIEW_REQUIRED)], {}, explicit_status_overrides={"p1": "MAYBE"})


def test_wd_after_r1_start_never_conflated_with_generic_wd_population():
    """WD (from ground truth's own R1/R2 status text) and
    WD_AFTER_R1_START (from a human-verified override) are reported as
    genuinely separate outcome values, never merged into one count."""
    rows, _ = to_player_r2_reconciled_rows(
        [_gt_row("p1", STATUS_WD), _gt_row("p2", STATUS_REVIEW_REQUIRED)],
        {}, explicit_status_overrides={"p2": "WD"},
    )
    outcomes = {r.player_code: r.r2_outcome for r in rows}
    assert outcomes["p1"] != outcomes["p2"]


# ---------------------------------------------------------------
# summarize_ground_truth_reconciliation — matches reconcile_r1_to_r2's shape
# ---------------------------------------------------------------


def test_summary_has_required_keys_for_existing_hard_gate_checks():
    frozen = [_frozen("p1"), _frozen("p2")]
    rows, _ = to_player_r2_reconciled_rows(
        [_gt_row("p1", STATUS_MADE_CUT), _gt_row("p2", STATUS_MISSED_CUT_CANDIDATE)], _official_r2("p1")
    )
    summary = summarize_ground_truth_reconciliation(frozen, rows, _official_r2("p1"))
    for key in ("new_wd", "new_dq", "cut", "made_cut", "missing"):
        assert key in summary
    assert summary["made_cut"] == 1
    assert summary["cut"] == 1


def test_summary_counts_wd_after_r1_start_under_new_wd():
    frozen = [_frozen("p1")]
    rows, _ = to_player_r2_reconciled_rows(
        [_gt_row("p1", STATUS_REVIEW_REQUIRED)], {}, explicit_status_overrides={"p1": "WD"}
    )
    summary = summarize_ground_truth_reconciliation(frozen, rows, {})
    assert summary["new_wd"] == 1
