"""Reusable ranking-comparison statistics -- NEO SITE V5 Mission 5.

These functions are deliberately generic (take plain {player_id: value}
dicts, know nothing about K-Rank/SG/NEO specifically) so the same code
computes K-Rank-vs-SG today and K-Rank-vs-NEO / SG-vs-NEO the moment
NEO Ranking publishes -- no duplicated logic per pair. NEO Ranking is
NOT forced to reproduce K-Rank (per the mission brief); these functions
only ever MEASURE divergence, never penalize or correct for it.
"""
from __future__ import annotations

from dataclasses import dataclass


def _ranks_from_values(values: dict[str, float], *, ascending: bool) -> dict[str, int]:
    """Dense competition ranking (ties share a rank; the next distinct
    value takes the next integer, per real KLPGA/statistical convention
    -- not skip-ranking)."""
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=not ascending)
    ranks: dict[str, int] = {}
    rank = 0
    previous = object()
    for pid, value in ordered:
        if value != previous:
            rank += 1
            previous = value
        ranks[pid] = rank
    return ranks


def spearman_rank_correlation(a: dict[str, float], b: dict[str, float]) -> dict:
    """Spearman's rho over the intersection of two {player_id: value}
    maps. Returns a dict (never a bare float) so the sample size and the
    excluded player_ids are always visible alongside the number -- a
    correlation computed over 8 overlapping players must never be read
    the same way as one over 100."""
    common = sorted(set(a) & set(b))
    excluded_a_only = sorted(set(a) - set(b))
    excluded_b_only = sorted(set(b) - set(a))
    if len(common) < 2:
        return {
            "rho": None, "n": len(common),
            "excluded_a_only": excluded_a_only, "excluded_b_only": excluded_b_only,
            "reason": "fewer than 2 overlapping players" if len(common) < 2 else None,
        }
    rank_a = _ranks_from_values({k: a[k] for k in common}, ascending=True)
    rank_b = _ranks_from_values({k: b[k] for k in common}, ascending=True)
    n = len(common)
    d_squared_sum = sum((rank_a[pid] - rank_b[pid]) ** 2 for pid in common)
    rho = 1 - (6 * d_squared_sum) / (n * (n * n - 1)) if n > 1 else None
    return {
        "rho": rho, "n": n,
        "excluded_a_only": excluded_a_only, "excluded_b_only": excluded_b_only,
        "reason": None,
    }


def topn_overlap(a: dict[str, float], b: dict[str, float], n: int, *,
                  ascending_a: bool = True, ascending_b: bool = True) -> dict:
    """How many of the top-N by `a` are also top-N by `b`. ascending_a/
    ascending_b are independent, since the two metrics being compared
    are rarely both "lower is better": K-Rank's official_rank is
    ascending (1 = best), but an SG mean or a win probability is
    descending (larger = best) -- passing one shared flag for both
    would silently compare "best K-Rank" against "worst SG"."""
    order_a = sorted(a.items(), key=lambda kv: kv[1], reverse=not ascending_a)
    order_b = sorted(b.items(), key=lambda kv: kv[1], reverse=not ascending_b)
    top_a = {pid for pid, _ in order_a[:n]}
    top_b = {pid for pid, _ in order_b[:n]}
    overlap = sorted(top_a & top_b)
    return {
        "n": n, "top_a_count": len(top_a), "top_b_count": len(top_b),
        "overlap_count": len(overlap), "overlap_player_ids": overlap,
        "only_in_a": sorted(top_a - top_b), "only_in_b": sorted(top_b - top_a),
    }


def largest_divergences(a: dict[str, float], b: dict[str, float], *,
                         ascending_a: bool = True, ascending_b: bool = True, top_k: int = 10) -> list[dict]:
    """The top_k players whose rank under `a` differs most from their
    rank under `b`, over the overlapping player set only. See
    topn_overlap() for why ascending_a/ascending_b are independent."""
    common = sorted(set(a) & set(b))
    rank_a = _ranks_from_values({k: a[k] for k in common}, ascending=ascending_a)
    rank_b = _ranks_from_values({k: b[k] for k in common}, ascending=ascending_b)
    rows = [
        {"player_id": pid, "rank_a": rank_a[pid], "rank_b": rank_b[pid], "delta": rank_a[pid] - rank_b[pid]}
        for pid in common
    ]
    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    return rows[:top_k]


@dataclass(frozen=True)
class CalibrationBin:
    lower: float
    upper: float
    predicted_count: int
    actual_positive_count: int

    @property
    def actual_rate(self) -> float | None:
        return self.actual_positive_count / self.predicted_count if self.predicted_count else None


def calibration_bins(predictions: dict[str, float], outcomes: dict[str, bool], *, bin_edges: tuple[float, ...] = (0.0, 0.02, 0.05, 0.1, 0.2, 1.0)) -> list[CalibrationBin]:
    """Bins predicted probabilities against real binary outcomes (e.g.
    predicted win_probability vs. "did this player actually finish T1").
    Only ever computed over players present in both maps -- a player
    with a prediction but no recorded outcome (still to be determined)
    is silently excluded from calibration, never counted as a miss."""
    common = sorted(set(predictions) & set(outcomes))
    bins = []
    for lower, upper in zip(bin_edges, bin_edges[1:]):
        in_bin = [pid for pid in common if lower <= predictions[pid] < upper or (upper == bin_edges[-1] and predictions[pid] == upper)]
        positives = sum(1 for pid in in_bin if outcomes[pid])
        bins.append(CalibrationBin(lower, upper, len(in_bin), positives))
    return bins


def mean_absolute_prediction_error(predictions: dict[str, float], outcomes: dict[str, float]) -> dict:
    """Mean absolute error between a predicted continuous value (e.g.
    win_probability) and its real, later-known continuous or 0/1
    outcome, over the overlapping player set only."""
    common = sorted(set(predictions) & set(outcomes))
    if not common:
        return {"mae": None, "n": 0}
    total = sum(abs(predictions[pid] - outcomes[pid]) for pid in common)
    return {"mae": total / len(common), "n": len(common)}
