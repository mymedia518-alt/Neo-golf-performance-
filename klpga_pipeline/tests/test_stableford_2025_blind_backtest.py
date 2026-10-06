"""2025 TRUE BLIND BACKTEST tests -- real data only (the 23 committed
prior-tournament captures + the already SOURCE-PASS-verified
2025100001 reconstruction). Proves the freeze-before-join ordering,
not just claims it."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from klpga.website_v2.stableford_2025_blind_backtest import (
    build_preevent_snapshot,
    freeze_and_hash,
    join_actual_results,
)

RECON_PATH = (
    Path(__file__).parent.parent
    / "evidence" / "stableford_source_probe_2025100001" / "RECONSTRUCTION_2025100001.json"
)


def _actual_points() -> dict[str, int]:
    recon = json.loads(RECON_PATH.read_text(encoding="utf-8"))
    return {a["player_name"]: a["total_points"] for a in recon["full_field_reconstruction_made_cut_players"]}


def test_preevent_snapshot_covers_105_of_108_real_field():
    records = build_preevent_snapshot()
    assert len(records) == 105


def test_every_record_has_a_positive_hole_sample_and_correct_rate_arithmetic():
    records = build_preevent_snapshot()
    for r in records:
        assert r.holes > 0
        assert r.holes % 18 == 0
        total_outcomes = r.albatross + r.eagle + r.birdie + r.par + r.bogey + r.double_or_worse
        assert total_outcomes == r.holes
        rate_sum = r.albatross_rate + r.eagle_rate + r.birdie_rate + r.par_rate + r.bogey_rate + r.double_or_worse_rate
        assert abs(rate_sum - 1.0) < 1e-3


def test_albatross_is_always_exactly_zero_never_inferred():
    records = build_preevent_snapshot()
    for r in records:
        assert r.albatross == 0
        assert r.albatross_rate == 0.0


def test_net_value_equals_sum_of_its_own_three_components():
    records = build_preevent_snapshot()
    for r in records:
        total = r.positive_scoring_contribution + r.bogey_cost + r.double_plus_downside
        assert abs(total - r.net_expected_value) < 1e-3


def test_ranking_is_sorted_descending_by_net_value_with_correct_percentiles():
    records = build_preevent_snapshot()
    for a, b in zip(records, records[1:]):
        assert a.net_expected_value >= b.net_expected_value
        assert a.pre_event_rank < b.pre_event_rank
    assert records[0].pre_event_rank == 1
    assert records[0].percentile == 100.0
    assert records[-1].percentile == 0.0


def test_kim_min_sol_blind_rank_is_reported_exactly_not_adjusted():
    """The headline falsification-test number. Must be exactly 9 of
    105 (92.31 percentile) against the committed real captures -- if
    this fails, something about the real data or pipeline changed and
    must be investigated, never silently "corrected" toward #1."""
    records = build_preevent_snapshot()
    km = next(r for r in records if r.player_name == "김민솔")
    assert km.pre_event_rank == 9
    assert km.percentile == 92.31
    assert km.holes == 576
    assert (km.eagle, km.birdie, km.par, km.bogey, km.double_or_worse) == (4, 127, 359, 73, 13)


def test_freeze_hash_is_deterministic_and_unaffected_by_joining_actual_results():
    """THE ordering proof: compute the frozen hash, THEN join actual
    results, THEN recompute the hash from the SAME records object --
    it must be byte-identical, proving join_actual_results never
    mutates the frozen ranking (frozen dataclasses enforce this at the
    type level too, but this test proves it empirically)."""
    records = build_preevent_snapshot()
    digest_before, payload_before = freeze_and_hash(records)

    actual = _actual_points()
    join_actual_results(records, actual, "김민솔")

    digest_after, payload_after = freeze_and_hash(records)
    assert digest_before == digest_after
    assert payload_before == payload_after


def test_frozen_hash_matches_the_committed_value():
    """Re-derived from the real data by this test, not just hardcoded
    in isolation -- if the 23 captures or the parser ever change, this
    catches the drift rather than silently reporting a stale hash."""
    records = build_preevent_snapshot()
    digest, _ = freeze_and_hash(records)
    assert digest == "232aee3f8e3ac368d5924ceef8b676b2543da8edcd42ec860cd73e38061a26d4"


def test_join_actual_results_covers_all_61_made_cut_finalists():
    records = build_preevent_snapshot()
    actual = _actual_points()
    result = join_actual_results(records, actual, "김민솔")
    assert result.n_joined == 61


def test_winner_evaluation_matches_the_frozen_rank_exactly():
    records = build_preevent_snapshot()
    actual = _actual_points()
    result = join_actual_results(records, actual, "김민솔")
    assert result.winner_pre_event_rank == 9
    assert result.winner_pre_event_percentile == 92.31
    assert result.winner_actual_points == 51


def test_spearman_and_topn_metrics_are_real_and_not_perfect():
    """Sanity bounds, not exact pins (these come from real evaluation
    arithmetic, legitimately somewhat sensitive to minor float
    rounding) -- a real signal exists (positive, moderate correlation)
    but this must never read as a perfect/overfit result."""
    records = build_preevent_snapshot()
    actual = _actual_points()
    result = join_actual_results(records, actual, "김민솔")
    assert 0.3 < result.spearman_correlation < 0.8
    assert 0.0 < result.top10_precision < 1.0
    assert 0.0 < result.top20_precision < 1.0
    assert len(result.predicted_top10_names) == 10
    assert len(result.actual_top10_names) >= 10  # ties may extend it


def test_small_sample_players_are_not_hidden():
    """At least one covered player has a thin (<10 round) pre-event
    sample -- confirms the real data genuinely contains a small-sample
    case this report must flag, not a hypothetical worry."""
    records = build_preevent_snapshot()
    thin = [r for r in records if r.holes < 180]
    assert len(thin) >= 1
    for r in thin:
        assert r.holes > 0  # still a real, nonzero sample -- just a small one, reported as such


def test_missing_players_are_the_real_three_not_silently_dropped():
    records = build_preevent_snapshot()
    covered_names = {r.player_name for r in records}
    from klpga.collectors.score_record import extract_hole_outcomes
    target_html = (
        Path(__file__).parent.parent
        / "evidence" / "stableford_source_probe_2025100001" / "scoreRecord_2025100001.html"
    ).read_text(encoding="utf-8")
    field = set(extract_hole_outcomes(target_html)["1R"].keys())
    missing = field - covered_names
    assert missing == {"박조은 0806(A)", "윤민아", "이지유 0901(A)"}
