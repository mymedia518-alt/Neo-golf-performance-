"""Tests for klpga.website_v2.stableford_player_value -- the
decomposed Stableford expected-value breakdown (positive scoring
contribution / bogey cost / double+ downside / net expectation), and
the explicit refusal to accept an un-sourced albatross rate."""
from __future__ import annotations

import pytest

from klpga.website_v2.stableford_player_value import from_season_rates


def test_net_expectation_matches_the_official_formula_components_summed():
    b = from_season_rates(eagle_rate=0.02, birdie_rate=0.20, par_rate=0.60, bogey_rate=0.15, double_or_worse_rate=0.03)
    expected = 5 * 0.02 + 2 * 0.20 - 1 * 0.15 - 3 * 0.03
    assert abs(b.net_expectation - expected) < 1e-9
    assert abs(b.positive_scoring_contribution + b.bogey_cost + b.double_plus_downside - b.net_expectation) < 1e-9


def test_components_are_separately_signed_and_explainable():
    b = from_season_rates(eagle_rate=0.02, birdie_rate=0.20, par_rate=0.60, bogey_rate=0.15, double_or_worse_rate=0.03)
    assert b.positive_scoring_contribution > 0
    assert b.bogey_cost < 0
    assert b.double_plus_downside < 0


def test_albatross_rate_zero_by_default_no_source_required():
    b = from_season_rates(eagle_rate=0.0, birdie_rate=0.0, par_rate=1.0, bogey_rate=0.0, double_or_worse_rate=0.0)
    assert b.probabilities.albatross == 0.0
    assert b.albatross_source is None


def test_nonzero_albatross_without_source_is_refused():
    with pytest.raises(ValueError, match="albatross"):
        from_season_rates(
            eagle_rate=0.0, birdie_rate=0.0, par_rate=0.99, bogey_rate=0.0,
            double_or_worse_rate=0.0, albatross_rate=0.01,
        )


def test_nonzero_albatross_with_a_named_source_is_accepted():
    b = from_season_rates(
        eagle_rate=0.0, birdie_rate=0.0, par_rate=0.99, bogey_rate=0.0,
        double_or_worse_rate=0.0, albatross_rate=0.01,
        albatross_source="hypothetical test source -- not used anywhere in the real 2023-2025 reconstruction",
    )
    assert b.probabilities.albatross == 0.01
    assert b.albatross_source is not None


def test_rates_must_sum_to_one_same_as_the_underlying_probabilities_class():
    with pytest.raises(ValueError):
        from_season_rates(eagle_rate=0.5, birdie_rate=0.5, par_rate=0.5, bogey_rate=0.0, double_or_worse_rate=0.0)
