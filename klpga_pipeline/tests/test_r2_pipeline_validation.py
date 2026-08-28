"""Tests for klpga.neo_win.r2_pipeline_validation — Section K of the
R1->R2 evaluation pipeline. Each check is exercised for both a passing
and a failing synthetic case."""
from __future__ import annotations

import hashlib

from klpga.neo_win.cut_evaluation import (
    CUT_OUTCOME_DQ,
    CUT_OUTCOME_MADE,
    CUT_OUTCOME_MISSED,
    CUT_OUTCOME_UNRESOLVED,
    CUT_OUTCOME_WD_AFTER_R1_START,
    PlayerCutEvaluationRow,
    summarize_cut_evaluation,
)
from klpga.neo_win.r1_frozen_snapshot import PlayerR1Frozen
from klpga.neo_win.r2_pipeline_validation import (
    check_calibration_buckets_sum_to_evaluated,
    check_cut_probability_in_0_100_range,
    check_eligibility_population_is_mechanical,
    check_frozen_r1_values_unchanged,
    check_made_plus_missed_equals_n_evaluated,
    check_missed_cut_count_plausible_after_completed_cut,
    check_no_null_cut_probability_among_evaluated,
    check_no_wd_dq_unresolved_enters_scoring,
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


def test_r1_historical_html_unchanged_tolerates_raw_certutil_output(tmp_path):
    """Real-world fix: Windows `certutil -hashfile <path> SHA256` prints
    the hash surrounded by header/footer lines. Pasting that raw output
    in must not produce a false mismatch when the file genuinely never
    changed."""
    path = tmp_path / "r1.html"
    path.write_text("frozen content", encoding="utf-8")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    raw_certutil_output = (
        f"SHA256 hash of {path}:\n{expected}\nCertUtil: -hashfile command completed successfully."
    )
    result = check_r1_historical_html_unchanged(path, raw_certutil_output)
    assert result["passed"] is True


def test_r1_historical_html_unchanged_tolerates_uppercase_and_whitespace(tmp_path):
    path = tmp_path / "r1.html"
    path.write_text("frozen content", encoding="utf-8")
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    result = check_r1_historical_html_unchanged(path, f"  {expected.upper()}  \r\n")
    assert result["passed"] is True


def test_r1_historical_html_unchanged_reports_distinct_failure_for_malformed_expected(tmp_path):
    path = tmp_path / "r1.html"
    path.write_text("frozen content", encoding="utf-8")
    result = check_r1_historical_html_unchanged(path, "not-a-real-hash")
    assert result["passed"] is False
    assert "no real 64-character SHA-256" in result["detail"]


def test_r1_historical_html_unchanged_still_fails_on_a_genuinely_different_hash(tmp_path):
    """The tolerant parsing must never mask a real difference."""
    path = tmp_path / "r1.html"
    path.write_text("frozen content", encoding="utf-8")
    wrong_hash = "0" * 64
    result = check_r1_historical_html_unchanged(path, wrong_hash)
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


def test_missed_cut_count_fails_when_zero_missed_among_a_real_evaluated_field():
    """Regression test for the real Windows bug: a completed-R2
    evaluation reporting 0 missed cuts among a real, non-trivial
    evaluated field is an impossible state and must fail STEP10."""
    cut_summary = {"n_evaluated": 110, "actual_missed_cut_count": 0, "actual_made_cut_count": 110}
    result = check_missed_cut_count_plausible_after_completed_cut(cut_summary)
    assert result["passed"] is False


def test_missed_cut_count_passes_when_real_missed_cuts_present():
    cut_summary = {"n_evaluated": 110, "actual_missed_cut_count": 40, "actual_made_cut_count": 70}
    result = check_missed_cut_count_plausible_after_completed_cut(cut_summary)
    assert result["passed"] is True


def test_missed_cut_count_passes_when_nothing_evaluated_yet():
    """Zero evaluated players (e.g. Round 2 hasn't been reconciled at
    all) is a genuinely different, already-reported state — this
    check must not fire for it."""
    cut_summary = {"n_evaluated": 0, "actual_missed_cut_count": 0, "actual_made_cut_count": 0}
    result = check_missed_cut_count_plausible_after_completed_cut(cut_summary)
    assert result["passed"] is True


# ---------------------------------------------------------------
# check_made_plus_missed_equals_n_evaluated
# ---------------------------------------------------------------


def test_made_plus_missed_equals_n_evaluated_passes_by_construction():
    rows = [_cut_row("p1", 80.0, CUT_OUTCOME_MADE), _cut_row("p2", 20.0, CUT_OUTCOME_MISSED)]
    summary = summarize_cut_evaluation(rows)
    assert check_made_plus_missed_equals_n_evaluated(summary)["passed"] is True


def test_made_plus_missed_equals_n_evaluated_fails_on_tampered_summary():
    result = check_made_plus_missed_equals_n_evaluated(
        {"n_evaluated": 10, "actual_made_cut_count": 5, "actual_missed_cut_count": 3}
    )
    assert result["passed"] is False


# ---------------------------------------------------------------
# check_no_wd_dq_unresolved_enters_scoring
# ---------------------------------------------------------------


def test_no_wd_dq_unresolved_enters_scoring_passes_for_correctly_excluded_rows():
    rows = [
        _cut_row("p1", 80.0, CUT_OUTCOME_MADE),
        _cut_row("p2", 20.0, CUT_OUTCOME_WD_AFTER_R1_START),
        _cut_row("p3", 30.0, CUT_OUTCOME_DQ),
        _cut_row("p4", 40.0, CUT_OUTCOME_UNRESOLVED),
    ]
    assert check_no_wd_dq_unresolved_enters_scoring(rows)["passed"] is True


def test_no_wd_dq_unresolved_enters_scoring_fails_if_a_wd_row_carries_a_real_outcome():
    row = _cut_row("p1", 20.0, CUT_OUTCOME_WD_AFTER_R1_START)
    object.__setattr__(row, "actual_cut", 0)  # simulate a regression bypassing cut_evaluation's own mapping
    result = check_no_wd_dq_unresolved_enters_scoring([row])
    assert result["passed"] is False
    assert "p1" in result["detail"]


# ---------------------------------------------------------------
# check_eligibility_population_is_mechanical
# ---------------------------------------------------------------


def test_eligibility_population_is_mechanical_passes_when_matching():
    frozen = [_frozen("p1"), _frozen("p2"), PlayerR1Frozen(
        tournament_id="t", player_code="p3", player_name="C", r1_actual_rank=3,
        r1_actual_score_to_par=0.0, r1_win_probability_pct=1.0, r1_make_cut_probability_pct=None,
        model_version="v", prediction_generated_at="t",
    )]
    eval_rows = [_cut_row("p1", 80.0, CUT_OUTCOME_MADE), _cut_row("p2", 20.0, CUT_OUTCOME_MISSED)]
    result = check_eligibility_population_is_mechanical(eval_rows, frozen)
    assert result["passed"] is True  # p3 correctly excluded (no real cut probability)


def test_eligibility_population_is_mechanical_fails_when_hand_curated():
    frozen = [_frozen("p1"), _frozen("p2")]
    eval_rows = [_cut_row("p1", 80.0, CUT_OUTCOME_MADE)]  # p2 dropped without a real reason
    result = check_eligibility_population_is_mechanical(eval_rows, frozen)
    assert result["passed"] is False
    assert "p2" in result["detail"]
