"""Tests for klpga.website_v2.stableford_2026_preevent -- applying the
frozen Stableford V1 formula (unchanged) to the real 2026 HJ field,
against the real committed evidence (24 prior tournaments, commit
32f293a)."""
from __future__ import annotations

from pathlib import Path

from klpga.website_v2.stableford_2026_preevent import build_2026_field_snapshot

CONTENT_ROOT = Path(__file__).parent.parent / "content" / "website_v2"
EVIDENCE_ROOT = Path(__file__).parent.parent / "evidence"

IDENTITY_PATH = CONTENT_ROOT / "2026100004_CANONICAL_PLAYER_IDENTITY_V1.json"
MANIFEST_PATH = CONTENT_ROOT / "STABLEFORD_2026_PRIOR_TOURNAMENT_MANIFEST_V1.json"
PRIOR_DIR = EVIDENCE_ROOT / "stableford_prior_2026"


def _build():
    return build_2026_field_snapshot(IDENTITY_PATH, MANIFEST_PATH, PRIOR_DIR)


def test_covers_all_108_real_entrants_with_no_drops():
    records = _build()
    assert len(records) == 108
    codes = {r.player_code for r in records}
    assert len(codes) == 108


def test_the_two_brand_new_players_are_data_limited_no_prior_data():
    records = _build()
    by_name = {r.player_name: r for r in records}
    for name in ("김민서3", "이지유 0901(A)"):
        r = by_name[name]
        assert r.data_status == "DATA_LIMITED_NO_PRIOR_DATA"
        assert r.pre_event_rank is None
        assert r.net_expected_value is None


def test_rankable_players_are_sorted_descending_by_net_expected_value():
    records = _build()
    ranked = [r for r in records if r.pre_event_rank is not None]
    assert len(ranked) == 106
    ranked_sorted = sorted(ranked, key=lambda r: r.pre_event_rank)
    values = [r.net_expected_value for r in ranked_sorted]
    assert values == sorted(values, reverse=True)
    assert ranked_sorted[0].pre_event_rank == 1
    assert ranked_sorted[-1].pre_event_rank == 106


def test_thin_sample_players_flagged_but_still_ranked_not_excluded():
    records = _build()
    thin = [r for r in records if r.data_status == "DATA_LIMITED_THIN_SAMPLE"]
    assert len(thin) == 2  # the 2 real players with < 10 prior rounds, per the real data
    for r in thin:
        assert r.rounds < 10
        assert r.pre_event_rank is not None  # ranked anyway, matching the 2023-2025 precedent


def test_net_expected_value_matches_the_frozen_formula_exactly():
    """Regression anchor against the unchanged formula: 8e+5g+2b-p-3d
    (par contributes 0) -- recomputed independently here, not just
    trusting the module's own internal arithmetic."""
    records = _build()
    for r in records:
        if r.net_expected_value is None:
            continue
        # recompute from the RAW counts (matching the module's own internal
        # order of operations exactly) rather than the already-rounded rate
        # fields, to avoid a double-rounding artifact that isn't a real bug.
        expected = (
            8 * (r.albatross / r.holes) + 5 * (r.eagle / r.holes) + 2 * (r.birdie / r.holes)
            - 1 * (r.bogey / r.holes) - 3 * (r.double_or_worse / r.holes)
        )
        assert abs(r.net_expected_value - round(expected, 4)) < 1e-9


def test_no_unmatched_name_silently_fabricated_as_zero_rate():
    """Every DATA_LIMITED_NO_PRIOR_DATA record must carry None, never 0.0,
    for every rate field -- 0.0 would be a fabricated claim ('this
    player made 0% birdies'), not an honest absence."""
    records = _build()
    for r in records:
        if r.data_status == "DATA_LIMITED_NO_PRIOR_DATA":
            assert r.birdie_rate is None
            assert r.bogey_rate is None
            assert r.holes is None
