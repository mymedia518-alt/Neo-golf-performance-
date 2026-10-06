"""Tests for scripts/211_analyze_official_season_stats.py -- the
single-tournament-scope finding and the winner metric/percentile
report, run against the real evidence pushed from the Windows
acquisition run (evidence/stableford_official_stats_<year>/
ACQUISITION_REPORT.json)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "211_analyze_official_season_stats.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("analyze_211", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["analyze_211"] = module
    spec.loader.exec_module(module)
    return module


def test_percentile_of_matches_manual_rank():
    mod = _load_module()
    field = [10.0, 20.0, 30.0, 40.0, 50.0]
    # higher-is-better: value 40 beats-or-ties 4 of 5 (40,30,20,10) -> 80.0
    assert mod.percentile_of(40.0, field, lower_is_better=False) == 80.0
    # lower-is-better: value 20 beats-or-ties 4 of 5 (20,30,40,50) -> 80.0
    assert mod.percentile_of(20.0, field, lower_is_better=True) == 80.0


def test_every_winner_year_shows_single_tournament_scope_not_season_cumulative():
    """The core finding: the last_pre_cutoff_game_code call returns a
    single tournament's round count (1-4), never a season total (the
    winners' real pre-cutoff seasons are 32-62 rounds) -- confirmed
    across all 102/103/102 acquired players in every year."""
    mod = _load_module()
    for year in ("2023", "2024", "2025"):
        report = mod.winner_metric_report(year)
        scope = report["single_tournament_scope_check"]
        assert scope["max"] <= 4
        assert scope["n"] >= 100


def test_winner_metrics_present_and_percentiles_in_range():
    mod = _load_module()
    for year in ("2023", "2024", "2025"):
        report = mod.winner_metric_report(year)
        for metric in ("driving_distance", "fairway_accuracy", "gir", "average_score", "par5_scoring"):
            m = report["metrics"][metric]
            assert m is not None
            assert 0.0 <= m["percentile"] <= 100.0


def test_2023_banshinsil_real_values_match_acquired_evidence():
    mod = _load_module()
    report = mod.winner_metric_report("2023")
    assert report["winner"] == "방신실"
    assert report["metrics"]["driving_distance"]["value"] == 256.2581
    assert report["metrics"]["driving_distance"]["percentile"] == 99.02
    assert report["metrics"]["fairway_accuracy"]["value"] == 51.7857
    assert report["metrics"]["gir"]["value"] == 63.8889
