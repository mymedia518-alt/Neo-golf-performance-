from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.neo_win.monte_carlo_summary import summarize_normal_draw, summarize_trials  # noqa: E402


def test_summarize_trials_basic_stats():
    summary = summarize_trials(n_simulations=5, seed=1, trials=[1.0, 2.0, 3.0, 4.0, 5.0])
    assert summary.mean == 3.0
    assert summary.median == 3.0
    assert summary.stddev == pytest.approx(1.5811, abs=1e-3)
    assert summary.ci95_low < summary.mean < summary.ci95_high


def test_summarize_trials_rejects_empty():
    with pytest.raises(ValueError):
        summarize_trials(n_simulations=0, seed=1, trials=[])


def test_summarize_normal_draw_reproducible_same_seed():
    a = summarize_normal_draw(expected=-2.0, spread=1.5, n_simulations=10000, seed=42)
    b = summarize_normal_draw(expected=-2.0, spread=1.5, n_simulations=10000, seed=42)
    assert a == b


def test_summarize_normal_draw_mean_close_to_expected():
    summary = summarize_normal_draw(expected=-2.0, spread=1.5, n_simulations=200000, seed=42)
    assert summary.mean == pytest.approx(-2.0, abs=0.02)
    assert summary.stddev == pytest.approx(1.5, abs=0.02)


def test_summarize_normal_draw_different_seed_differs():
    a = summarize_normal_draw(expected=0.0, spread=1.0, n_simulations=1000, seed=1)
    b = summarize_normal_draw(expected=0.0, spread=1.0, n_simulations=1000, seed=2)
    assert a.mean != b.mean
