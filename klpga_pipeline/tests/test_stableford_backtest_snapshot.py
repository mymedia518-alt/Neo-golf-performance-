"""Tests for klpga.website_v2.stableford_backtest_snapshot -- the
pre-event temporal snapshot builder, run against the real committed
field names (from the already SOURCE-PASS-verified scoreRecord
captures) and the real historical_sg_warehouse_corrected_v2.json."""
from __future__ import annotations

import sys

import pytest

from klpga.collectors.score_record import extract_hole_outcomes
from klpga.website_v2.stableford_backtest_snapshot import (
    assert_no_leakage,
    build_event_snapshot,
)

sys.path.insert(0, "klpga_pipeline/src")  # harmless no-op if already on path


def _real_field(game_code: str) -> set[str]:
    from pathlib import Path
    path = (
        Path(__file__).parent.parent
        / "evidence" / f"stableford_source_probe_{game_code}" / f"scoreRecord_{game_code}.html"
    )
    html = path.read_text(encoding="utf-8")
    return set(extract_hole_outcomes(html)["1R"].keys())


CASES = [
    ("2023100002", 108, 102),
    ("2024100009", 108, 105),
    ("2025100001", 108, 103),
]


def test_assert_no_leakage_passes_clean_prior_month_codes():
    assert_no_leakage(["2025040001", "2025090004"], target_season=2025, target_month=10)


def test_assert_no_leakage_rejects_same_month_code():
    with pytest.raises(AssertionError, match="LEAKAGE"):
        assert_no_leakage(["2025100001"], target_season=2025, target_month=10)


def test_assert_no_leakage_rejects_later_month_code():
    with pytest.raises(AssertionError, match="LEAKAGE"):
        assert_no_leakage(["2025110001"], target_season=2025, target_month=10)


def test_assert_no_leakage_rejects_later_season_code():
    with pytest.raises(AssertionError, match="LEAKAGE"):
        assert_no_leakage(["2026010001"], target_season=2025, target_month=10)


@pytest.mark.parametrize("game_code,field_size,expected_covered", CASES, ids=[c[0] for c in CASES])
def test_real_snapshot_coverage_matches_investigated_numbers(game_code, field_size, expected_covered):
    field = _real_field(game_code)
    assert len(field) == field_size
    snapshot = build_event_snapshot(game_code, field)
    assert snapshot.leakage_assertions_passed
    assert snapshot.field_size == field_size
    covered = [p for p in snapshot.players.values() if p.prior_tournament_count > 0]
    assert len(covered) == expected_covered


@pytest.mark.parametrize("game_code,_fs,_ec", CASES, ids=[c[0] for c in CASES])
def test_birdie_eagle_bogey_rates_are_none_never_fabricated(game_code, _fs, _ec):
    """The single most important negative result of this investigation:
    no real pre-event birdie/eagle/par/bogey/double rate source exists
    anywhere in this repo (see this module's own docstring for the full
    investigation). Every player's snapshot must carry None for these,
    never an invented placeholder value."""
    field = _real_field(game_code)
    snapshot = build_event_snapshot(game_code, field)
    for p in snapshot.players.values():
        assert p.birdie_rate is None
        assert p.eagle_rate is None
        assert p.par_rate is None
        assert p.bogey_rate is None
        assert p.double_or_worse_rate is None


@pytest.mark.parametrize("game_code,_fs,_ec", CASES, ids=[c[0] for c in CASES])
def test_covered_players_have_a_real_sg_total_mean_and_positive_prior_count(game_code, _fs, _ec):
    field = _real_field(game_code)
    snapshot = build_event_snapshot(game_code, field)
    for p in snapshot.players.values():
        if p.prior_tournament_count > 0:
            assert p.prior_sg_total_mean is not None
            assert len(p.prior_game_codes) == p.prior_tournament_count
        else:
            assert p.prior_sg_total_mean is None
            assert p.prior_game_codes == ()


@pytest.mark.parametrize("game_code,_fs,_ec", CASES, ids=[c[0] for c in CASES])
def test_no_used_game_code_is_same_month_or_later_than_target(game_code, _fs, _ec):
    """Re-derives the leakage check independently of assert_no_leakage's
    own internal call -- walks every player's prior_game_codes and
    confirms none are in the target's own October or later."""
    field = _real_field(game_code)
    snapshot = build_event_snapshot(game_code, field)
    target_season = int(game_code[:4])
    for p in snapshot.players.values():
        for gc in p.prior_game_codes:
            season, month = int(gc[:4]), int(gc[4:6])
            assert season < target_season or (season == target_season and month < 10), (
                f"{game_code}/{p.player_name}: used game_code {gc} is not strictly prior"
            )
