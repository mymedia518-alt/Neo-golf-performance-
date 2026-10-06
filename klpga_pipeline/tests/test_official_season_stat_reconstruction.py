"""Tests for klpga.collectors.official_season_stat_reconstruction --
the weighted-sum (never simple-average) season-to-date cumulative
aggregator, and its per-call scope gate."""
from __future__ import annotations

from klpga.collectors.official_season_stat_reconstruction import (
    TournamentCallRecord,
    reconstruct_driving_distance,
    reconstruct_fairway_accuracy,
    reconstruct_gir,
    scope_gate_passes,
)


def test_scope_gate_requires_exact_round_match():
    assert scope_gate_passes(returned_rounds=4, real_rounds_this_tournament=4) is True
    assert scope_gate_passes(returned_rounds=5, real_rounds_this_tournament=4) is False
    assert scope_gate_passes(returned_rounds=None, real_rounds_this_tournament=4) is False


def test_single_record_reproduces_bangshinsil_2023_last_tournament_exactly():
    """Regression anchor: aggregating a SINGLE real already-acquired
    tournament call must exactly reproduce the already-verified single-
    tournament value from scripts/211's output for 방신실 2023
    (driving_distance=256.2581, fairway=51.7857, gir=63.8889)."""
    rec = TournamentCallRecord(
        game_code="2023100001", gate_passed=True,
        driving_distance_numerator=1025.0323, driving_distance_denominator=4,
        fairway_numerator=29, fairway_denominator=56,
        gir_numerator=46, real_rounds_this_tournament=4,
    )
    dd = reconstruct_driving_distance([rec])
    fw = reconstruct_fairway_accuracy([rec])
    gir = reconstruct_gir([rec])
    assert dd.value == 256.2581
    assert fw.value == 51.7857
    assert gir.value == 63.8889


def test_weighted_sum_not_simple_average_of_percentages():
    """The explicit anti-pattern from the user's instructions: summing
    two tournaments with very different sample sizes must NOT equal a
    naive average of their two percentages."""
    big = TournamentCallRecord(
        game_code="A", gate_passed=True,
        driving_distance_numerator=None, driving_distance_denominator=None,
        fairway_numerator=90, fairway_denominator=100,  # 90%
        gir_numerator=None, real_rounds_this_tournament=10,
    )
    small = TournamentCallRecord(
        game_code="B", gate_passed=True,
        driving_distance_numerator=None, driving_distance_denominator=None,
        fairway_numerator=0, fairway_denominator=10,  # 0%
        gir_numerator=None, real_rounds_this_tournament=1,
    )
    result = reconstruct_fairway_accuracy([big, small])
    naive_average = (90.0 + 0.0) / 2  # 45.0 -- WRONG, must not be produced
    weighted = 90 / 110 * 100  # 81.8182 -- correct
    assert result.value != naive_average
    assert result.value == round(weighted, 4)


def test_gate_failed_tournament_excluded_from_aggregate_and_counted():
    passed = TournamentCallRecord(
        game_code="A", gate_passed=True,
        driving_distance_numerator=1000.0, driving_distance_denominator=4,
        fairway_numerator=None, fairway_denominator=None, gir_numerator=None,
        real_rounds_this_tournament=4,
    )
    failed = TournamentCallRecord(
        game_code="B", gate_passed=False,
        driving_distance_numerator=99999.0, driving_distance_denominator=1,  # would wildly distort if included
        fairway_numerator=None, fairway_denominator=None, gir_numerator=None,
        real_rounds_this_tournament=4,
    )
    result = reconstruct_driving_distance([passed, failed])
    assert result.value == 250.0
    assert result.n_tournaments_included == 1
    assert result.n_tournaments_gate_failed == 1
    assert result.n_tournaments_total == 2


def test_no_usable_records_returns_none_value_not_fabricated_zero():
    failed = TournamentCallRecord(
        game_code="A", gate_passed=False,
        driving_distance_numerator=None, driving_distance_denominator=None,
        fairway_numerator=None, fairway_denominator=None, gir_numerator=None,
        real_rounds_this_tournament=4,
    )
    result = reconstruct_driving_distance([failed])
    assert result.value is None
    assert result.n_tournaments_included == 0
