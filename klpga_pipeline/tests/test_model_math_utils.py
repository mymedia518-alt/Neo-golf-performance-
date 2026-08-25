"""Tests for klpga.models.math_utils — the deterministic optimizer,
softmax, clipping floor, and Wilcoxon signed-rank test."""
from __future__ import annotations

import math

from klpga.models.math_utils import (
    clip_and_renormalize,
    grid_refine_search,
    normal_cdf,
    softmax_from_logits,
    wilcoxon_signed_rank_test,
)


def test_softmax_sums_to_one_and_is_positive():
    probs = softmax_from_logits({"a": 5.0, "b": -3.0, "c": 0.0})
    assert abs(sum(probs.values()) - 1.0) < 1e-12
    assert all(p > 0 for p in probs.values())


def test_softmax_equal_logits_gives_uniform():
    probs = softmax_from_logits({"a": 2.0, "b": 2.0, "c": 2.0})
    assert all(abs(p - 1 / 3) < 1e-12 for p in probs.values())


def test_softmax_extreme_logit_spread_does_not_crash():
    # A pathologically large spread should not overflow/NaN thanks to
    # the max-subtraction stability trick.
    probs = softmax_from_logits({"a": 1000.0, "b": -1000.0})
    assert math.isfinite(probs["a"]) and math.isfinite(probs["b"])
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_clip_and_renormalize_floors_zero_probability():
    probs = clip_and_renormalize({"a": 0.0, "b": 1.0}, epsilon=1e-6)
    # Clipped to ~epsilon, then renormalized (dividing by the post-clip
    # total) — the exact value can land a hair below epsilon itself,
    # but must be a small positive floor, never literally 0.
    assert 0 < probs["a"] < 1e-5
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_clip_and_renormalize_all_zero_falls_back_to_uniform():
    probs = clip_and_renormalize({"a": 0.0, "b": 0.0}, epsilon=1e-9)
    assert probs == {"a": 0.5, "b": 0.5}


def test_grid_refine_search_1d_finds_known_maximum():
    (x,), value = grid_refine_search(lambda t: -((t - 3.0) ** 2), [(-10.0, 10.0)], n_points=15, rounds=4)
    assert abs(x - 3.0) < 5e-3


def test_grid_refine_search_2d_finds_known_maximum():
    (x, y), value = grid_refine_search(
        lambda a, b: -((a - 1.0) ** 2) - ((b + 2.0) ** 2), [(-10.0, 10.0), (-10.0, 10.0)], n_points=11, rounds=4
    )
    assert abs(x - 1.0) < 5e-2
    assert abs(y - (-2.0)) < 5e-2


def test_normal_cdf_known_values():
    assert abs(normal_cdf(0.0) - 0.5) < 1e-9
    assert normal_cdf(-5.0) < 0.001
    assert normal_cdf(5.0) > 0.999


def test_wilcoxon_all_negative_differences_gives_small_p_value():
    diffs = [-0.1 - 0.01 * i for i in range(30)]
    result = wilcoxon_signed_rank_test(diffs)
    assert result["p_value"] < 0.01
    assert result["mean_diff"] < 0
    assert result["n"] == 30


def test_wilcoxon_symmetric_differences_gives_large_p_value():
    diffs = ([0.1, -0.1] * 15)
    result = wilcoxon_signed_rank_test(diffs)
    assert result["p_value"] > 0.5


def test_wilcoxon_drops_zero_differences():
    diffs = [0.0, 0.0, 0.5, -0.5, 0.3, -0.4]
    result = wilcoxon_signed_rank_test(diffs)
    assert result["n"] == 4  # the two zeros are dropped


def test_wilcoxon_empty_input_does_not_crash():
    result = wilcoxon_signed_rank_test([])
    assert result["n"] == 0
    assert result["p_value"] == 1.0
