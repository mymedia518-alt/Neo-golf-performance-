"""Tests for src/klpga/validation/ranking_stats.py -- NEO SITE V5 Mission 5.
Uses hand-computed synthetic inputs with known correct answers, plus the
real K-Rank/PRE win-probability data already in the repo as an end-to-end
sanity check.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.validation import ranking_stats as rs  # noqa: E402


def test_spearman_perfect_agreement_is_rho_1():
    a = {"p1": 1, "p2": 2, "p3": 3, "p4": 4}
    b = {"p1": 10, "p2": 20, "p3": 30, "p4": 40}
    result = rs.spearman_rank_correlation(a, b)
    assert result["rho"] == 1.0
    assert result["n"] == 4


def test_spearman_perfect_inversion_is_rho_negative_1():
    a = {"p1": 1, "p2": 2, "p3": 3, "p4": 4}
    b = {"p1": 4, "p2": 3, "p3": 2, "p4": 1}
    result = rs.spearman_rank_correlation(a, b)
    assert result["rho"] == -1.0


def test_spearman_reports_excluded_non_overlapping_players():
    a = {"p1": 1, "p2": 2, "only_a": 5}
    b = {"p1": 1, "p2": 2, "only_b": 5}
    result = rs.spearman_rank_correlation(a, b)
    assert result["n"] == 2
    assert result["excluded_a_only"] == ["only_a"]
    assert result["excluded_b_only"] == ["only_b"]


def test_spearman_under_two_overlapping_players_returns_none_not_a_number():
    result = rs.spearman_rank_correlation({"p1": 1}, {"p1": 1, "p2": 2})
    assert result["rho"] is None
    assert result["n"] == 1
    assert result["reason"]


def test_topn_overlap_full_overlap():
    a = {"p1": 1, "p2": 2, "p3": 3}
    b = {"p1": 10, "p2": 20, "p3": 30}
    result = rs.topn_overlap(a, b, n=2)
    assert result["overlap_count"] == 2
    assert set(result["overlap_player_ids"]) == {"p1", "p2"}


def test_topn_overlap_zero_overlap():
    a = {"p1": 1, "p2": 2, "p3": 3, "p4": 4}
    b = {"p1": 4, "p2": 3, "p3": 2, "p4": 1}
    result = rs.topn_overlap(a, b, n=1)
    assert result["overlap_count"] == 0
    assert result["only_in_a"] == ["p1"]
    assert result["only_in_b"] == ["p4"]


def test_topn_overlap_independent_ascending_flags_for_differently_oriented_metrics():
    # K-Rank: lower official_rank = better (ascending_a=True).
    k_rank = {"p1": 1, "p2": 2, "p3": 3}
    # SG: higher mean = better (ascending_b=False) -- and p1 IS the best
    # player under both metrics here, so a correct comparison must find
    # p1 in the overlap.
    sg = {"p1": 3.0, "p2": 2.0, "p3": 1.0}
    correct = rs.topn_overlap(k_rank, sg, n=1, ascending_a=True, ascending_b=False)
    assert correct["overlap_count"] == 1
    assert correct["overlap_player_ids"] == ["p1"]
    # Using the same (wrong) orientation for both would silently compare
    # "best K-Rank" against "worst SG" and miss the real agreement.
    wrong = rs.topn_overlap(k_rank, sg, n=1, ascending_a=True, ascending_b=True)
    assert wrong["overlap_count"] == 0


def test_largest_divergences_identifies_the_biggest_rank_swap():
    a = {"p1": 1, "p2": 2, "p3": 3, "p4": 4}
    b = {"p1": 1, "p2": 2, "p3": 4, "p4": 3}
    result = rs.largest_divergences(a, b, top_k=2)
    top = result[0]
    assert top["player_id"] in {"p3", "p4"}
    assert abs(top["delta"]) == 1


def test_largest_divergences_zero_delta_when_identical():
    a = {"p1": 1, "p2": 2}
    b = {"p1": 1, "p2": 2}
    result = rs.largest_divergences(a, b, top_k=5)
    assert all(row["delta"] == 0 for row in result)


def test_calibration_bins_perfect_calibration():
    # 10 players predicted at 0.5, exactly 5 actually win.
    predictions = {f"p{i}": 0.5 for i in range(10)}
    outcomes = {f"p{i}": i < 5 for i in range(10)}
    bins = rs.calibration_bins(predictions, outcomes, bin_edges=(0.0, 0.5, 1.0))
    high_bin = [b for b in bins if b.lower == 0.5][0]
    assert high_bin.predicted_count == 10
    assert high_bin.actual_positive_count == 5
    assert high_bin.actual_rate == 0.5


def test_calibration_bins_excludes_players_missing_an_outcome():
    predictions = {"p1": 0.1, "p2": 0.1}
    outcomes = {"p1": True}  # p2's outcome not yet known
    bins = rs.calibration_bins(predictions, outcomes, bin_edges=(0.0, 1.0))
    assert bins[0].predicted_count == 1


def test_mean_absolute_prediction_error_exact():
    predictions = {"p1": 0.1, "p2": 0.5}
    outcomes = {"p1": 0.0, "p2": 1.0}
    result = rs.mean_absolute_prediction_error(predictions, outcomes)
    assert abs(result["mae"] - 0.3) < 1e-9
    assert result["n"] == 2


def test_mean_absolute_prediction_error_empty_overlap_returns_none():
    result = rs.mean_absolute_prediction_error({"p1": 0.1}, {"p2": 1.0})
    assert result["mae"] is None
    assert result["n"] == 0


# ------------------------------------------------- real-data sanity check


def test_real_k_rank_vs_sg_total_rank_end_to_end():
    import json
    k_rank_doc = json.loads((ROOT / "content" / "website_v2" / "OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json").read_text(encoding="utf-8"))
    current_master = json.loads((ROOT / "content" / "website_v2" / "OK_OPEN_2026_CURRENT_PLAYER_MASTER.json").read_text(encoding="utf-8"))
    k_rank = {str(r["player_id"]): r["official_rank"] for r in k_rank_doc["records"] if r.get("official_rank") is not None}
    sg_rank = {str(r["player_id"]): r["sg_total_rank"] for r in current_master["records"] if r.get("sg_total_rank") is not None}
    result = rs.spearman_rank_correlation(k_rank, sg_rank)
    assert result["n"] > 50  # real overlap, not a trivial handful
    assert -1.0 <= result["rho"] <= 1.0
    # Both are already stored as ranks (1 = best) in these two artifacts,
    # so both are ascending here.
    overlap = rs.topn_overlap(k_rank, sg_rank, n=20, ascending_a=True, ascending_b=True)
    assert 0 <= overlap["overlap_count"] <= 20
