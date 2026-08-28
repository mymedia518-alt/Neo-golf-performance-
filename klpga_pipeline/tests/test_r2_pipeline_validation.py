"""Tests for klpga.neo_win.r2_pipeline_validation — Section K of the
R1->R2 evaluation pipeline. Each check is exercised for both a passing
and a failing synthetic case."""
from __future__ import annotations

import hashlib

from klpga.neo_win.cut_evaluation import CUT_OUTCOME_MADE, CUT_OUTCOME_MISSED, PlayerCutEvaluationRow
from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
from klpga.neo_win.r2_pipeline_validation import (
    check_calibration_buckets_sum_to_evaluated,
    check_cut_probability_in_0_100_range,
    check_frozen_r1_values_unchanged,
    check_no_null_cut_probability_among_evaluated,
    check_player_codes_unique,
    check_r1_historical_html_unchanged,
    check_r2_path_never_overwrites_r1,
    check_unavailable_players_explicitly_handled,
    check_wd_dq_explicitly_handled,
    check_win_probability_in_0_100_range,
    check_win_sums_to_100_among_cutmakers,
    run_all_validations,
)


def _cut_row(code, pct, outcome):
    return PlayerCutEvaluationRow(
        player_code=code, player_name=f"P{code}", r1_rank=1, r1_score_to_par=-1.0,
        r1_make_cut_pct=pct, r2_outcome=outcome,
    )


def _frozen(code, rank=1, win=5.0, cut=80.0):
    return PlayerR1Frozen(
        tournament_id="t", player_code=code, player_name="A", r1_actual_rank=rank,
        r1_actual_score_to_par=-1.0, r1_win_probability_pct=win, r1_make_cut_probability_pct=cut,
        model_version="001-C-R1", prediction_generated_at="t",
    )


def test_r1_historical_html_unchanged_passes_when_hash_matches(tmp_path):
    path = tmp_path / "r1.html"
    path.write_text("frozen content", encoding="utf-8")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    result = check_r1_historical_html_unchanged(path, expected)
    assert result["passed"] is True


def test_r1_historical_html_unchanged_fails_when_modified(tmp_path):
    path = tmp_path / "r1.html"
    path.write_text("frozen content", encoding="utf-8")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_text("MODIFIED", encoding="utf-8")
    result = check_r1_historical_html_unchanged(path, expected)
    assert result["passed"] is False


def test_r1_historical_html_unchanged_fails_when_missing(tmp_path):
    result = check_r1_historical_html_unchanged(tmp_path / "nope.html", "abc")
    assert result["passed"] is False


def test_frozen_r1_values_unchanged_passes_for_identical_rows():
    rows = [_frozen("p1")]
    result = check_frozen_r1_values_unchanged(rows, rows)
    assert result["passed"] is True


def test_frozen_r1_values_unchanged_fails_on_drift():
    before = [_frozen("p1", win=5.0)]
    after = [_frozen("p1", win=99.0)]
    result = check_frozen_r1_values_unchanged(before, after)
    assert result["passed"] is False


def test_player_codes_unique_fails_on_duplicate():
    rows = [_cut_row("p1", 50.0, CUT_OUTCOME_MADE), _cut_row("p1", 60.0, CUT_OUTCOME_MISSED)]
    result = check_player_codes_unique(rows)
    assert result["passed"] is False
    assert "p1" in result["detail"]


def test_player_codes_unique_passes_when_distinct():
    rows = [_cut_row("p1", 50.0, CUT_OUTCOME_MADE), _cut_row("p2", 60.0, CUT_OUTCOME_MISSED)]
    assert check_player_codes_unique(rows)["passed"] is True


def test_no_null_cut_probability_among_evaluated_passes():
    rows = [_cut_row("p1", 50.0, CUT_OUTCOME_MADE)]
    assert check_no_null_cut_probability_among_evaluated(rows)["passed"] is True


def test_cut_probability_in_range_fails_out_of_bounds():
    rows = [_cut_row("p1", 150.0, CUT_OUTCOME_MADE)]
    result = check_cut_probability_in_0_100_range(rows)
    assert result["passed"] is False


def test_win_probability_in_range_passes_and_fails():
    good = [{"player_code": "p1", "win_pct": 50.0}]
    bad = [{"player_code": "p1", "win_pct": 150.0}]
    assert check_win_probability_in_0_100_range(good)["passed"] is True
    assert check_win_probability_in_0_100_range(bad)["passed"] is False


def test_win_sums_to_100_among_cutmakers():
    entrants = [
        {"player_code": "p1", "win_pct": 60.0, "make_cut_pct": 100.0},
        {"player_code": "p2", "win_pct": 40.0, "make_cut_pct": 100.0},
        {"player_code": "p3", "win_pct": 0.0, "make_cut_pct": 0.0},
    ]
    result = check_win_sums_to_100_among_cutmakers(entrants)
    assert result["passed"] is True


def test_win_sums_to_100_fails_when_off():
    entrants = [{"player_code": "p1", "win_pct": 50.0, "make_cut_pct": 100.0}]
    result = check_win_sums_to_100_among_cutmakers(entrants)
    assert result["passed"] is False


def test_wd_dq_explicitly_handled_passes_with_required_keys():
    summary = {"new_wd": 1, "new_dq": 0, "cut": 2, "made_cut": 5, "missing": 0}
    assert check_wd_dq_explicitly_handled(summary)["passed"] is True


def test_wd_dq_explicitly_handled_fails_missing_keys():
    assert check_wd_dq_explicitly_handled({})["passed"] is False


def test_unavailable_players_explicitly_handled():
    result = check_unavailable_players_explicitly_handled(["p9"], {"missing": 1})
    assert result["passed"] is True


def test_calibration_buckets_sum_to_evaluated():
    buckets = [{"n": 2}, {"n": 3}]
    assert check_calibration_buckets_sum_to_evaluated(buckets, 5)["passed"] is True
    assert check_calibration_buckets_sum_to_evaluated(buckets, 6)["passed"] is False


def test_r2_path_never_overwrites_r1(tmp_path):
    r1 = tmp_path / "r1" / "index.html"
    r2 = tmp_path / "r2" / "index.html"
    assert check_r2_path_never_overwrites_r1(r1, r2)["passed"] is True
    assert check_r2_path_never_overwrites_r1(r1, r1)["passed"] is False


def test_run_all_validations_aggregates_pass_and_fail():
    checks = [{"check": "A", "passed": True}, {"check": "B", "passed": False}]
    result = run_all_validations(checks)
    assert result["all_passed"] is False
    assert result["failed"] == ["B"]


def test_run_all_validations_all_pass():
    checks = [{"check": "A", "passed": True}, {"check": "B", "passed": True}]
    result = run_all_validations(checks)
    assert result["all_passed"] is True
    assert result["failed"] == []
