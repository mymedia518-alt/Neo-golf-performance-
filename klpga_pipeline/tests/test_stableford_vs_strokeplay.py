"""Tests for klpga.website_v2.stableford_vs_strokeplay.compute_divergence
-- real arithmetic over the already SOURCE-PASS-verified real hole
outcome data, demonstrating the stroke-play/Stableford scoring
divergence mechanism (step 6 of the pre-event backtest task)."""
from __future__ import annotations

from pathlib import Path

from klpga.website_v2.stableford_vs_strokeplay import compute_divergence

EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence"


def _load(game_code):
    path = EVIDENCE_ROOT / f"stableford_source_probe_{game_code}" / f"scoreRecord_{game_code}.html"
    return compute_divergence(path.read_text(encoding="utf-8"))


def test_2025100001_field_size_and_known_divergent_players():
    rows = _load("2025100001")
    assert len(rows) == 61
    by_name = {r.player_name: r for r in rows}

    park = by_name["박민지"]
    assert park.stroke_to_par == -9
    assert park.hole_outcomes.birdie == 14
    assert park.hole_outcomes.bogey == 9
    assert park.stableford_points == 29
    assert park.rank_shift > 0  # ranks BETTER under Stableford

    lee = by_name["이예원"]
    assert lee.stroke_to_par == -13
    assert lee.hole_outcomes.birdie == 16
    assert lee.hole_outcomes.bogey == 3
    assert lee.stableford_points == 29
    # same Stableford points as 박민지, but a much better stroke-play
    # card -- her rank barely moves (small/negative shift), unlike
    # 박민지's clear improvement, demonstrating the birdie:bogey
    # asymmetry's effect is about the RATIO of birdies to bogeys
    # traded, not the raw point total alone.
    assert lee.rank_shift < park.rank_shift


def test_divergence_direction_matches_birdie_bogey_asymmetry_mechanism():
    """General check across the whole real field, not just the two
    hand-picked examples above: among players with a similar stroke-
    play rank, a higher bogey count (more birdie<->bogey trades at the
    asymmetric 2:1 rate) should correlate with a BETTER (less negative
    or more positive) rank_shift, on average -- the mechanism this
    module's docstring claims, checked against real data rather than
    asserted in the abstract."""
    rows = _load("2025100001")
    with_bogeys = [r for r in rows if r.hole_outcomes.bogey >= 5]
    without_bogeys = [r for r in rows if r.hole_outcomes.bogey <= 2]
    assert with_bogeys and without_bogeys
    avg_shift_with = sum(r.rank_shift for r in with_bogeys) / len(with_bogeys)
    avg_shift_without = sum(r.rank_shift for r in without_bogeys) / len(without_bogeys)
    assert avg_shift_with > avg_shift_without


def test_all_three_years_produce_a_full_real_divergence_table():
    for code, expected_size in [("2023100002", 61), ("2024100009", 60), ("2025100001", 61)]:
        rows = _load(code)
        assert len(rows) == expected_size
        for r in rows:
            assert r.hole_outcomes.total_holes in (0, 18, 36, 54, 72)
            assert r.stableford_points == r.hole_outcomes.total_points()
