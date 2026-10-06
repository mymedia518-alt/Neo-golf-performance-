"""Tests for klpga.website_v2.stableford_round_level_profile -- the
round-level scoring-ceiling/volatility extractor built for the
three-winner pre-event player profile validation (2026-10-06). Reuses
the same 19/23/23 real prior-tournament captures already SOURCE_PASS-
verified for the 2023/2024/2025 blind backtests -- no new acquisition."""
from __future__ import annotations

from pathlib import Path

from klpga.website_v2.stableford_round_level_profile import (
    compute_scoring_ceiling_profile,
    load_all_round_records,
)

CONTENT_ROOT = Path(__file__).parent.parent / "content" / "website_v2"
EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence"

CASES = [
    ("2023", "STABLEFORD_2023_PRIOR_TOURNAMENT_MANIFEST_V1.json", "stableford_prior_2023", "방신실", 52, 936),
    ("2024", "STABLEFORD_2024_PRIOR_TOURNAMENT_MANIFEST_V1.json", "stableford_prior_2024", "김민별", 62, 1116),
    ("2025", "STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json", "stableford_prior_2025", "김민솔", 32, 576),
]


def _load(manifest_name, prior_name):
    return load_all_round_records(CONTENT_ROOT / manifest_name, EVIDENCE_ROOT / prior_name)


def test_round_count_matches_holes_divided_by_18_for_each_winner():
    """Cross-check against the already-frozen aggregate holes count
    from stableford_blind_backtest -- rounds_n * 18 must equal the
    winner's own frozen pre-event holes total exactly."""
    for year, manifest_name, prior_name, winner, expected_rounds, expected_holes in CASES:
        by_player = _load(manifest_name, prior_name)
        rounds = by_player[winner]
        assert len(rounds) == expected_rounds
        assert sum(r.counts.total_holes for r in rounds) == expected_holes


def test_every_round_record_has_exactly_18_holes_and_a_positive_stroke_total():
    for year, manifest_name, prior_name, winner, _, _ in CASES:
        by_player = _load(manifest_name, prior_name)
        for rounds in by_player.values():
            for r in rounds:
                assert r.counts.total_holes == 18
                assert r.stroke_total > 0


def test_scoring_ceiling_profile_matches_computed_real_values():
    by_player_2025 = _load("STABLEFORD_2025_PRIOR_TOURNAMENT_MANIFEST_V1.json", "stableford_prior_2025")
    profile = compute_scoring_ceiling_profile("김민솔", by_player_2025["김민솔"])
    assert profile.rounds_n == 32
    assert profile.tournaments_n == 9
    assert profile.max_birdies_per_round == 9
    assert profile.avg_birdies_per_round == 3.9688


def test_stableford_points_from_round_record_matches_counts_total_points():
    by_player = _load("STABLEFORD_2023_PRIOR_TOURNAMENT_MANIFEST_V1.json", "stableford_prior_2023")
    for r in by_player["방신실"][:5]:
        assert r.stableford_points == r.counts.total_points()
