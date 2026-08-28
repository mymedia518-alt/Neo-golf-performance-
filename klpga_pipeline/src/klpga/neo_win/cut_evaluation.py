"""BETA #001 R1 MAKE CUT probability evaluation against real R2 outcomes.

======================================================================
WHY THIS DOES NOT REUSE klpga.models.metrics
======================================================================
`klpga.models.metrics` (log_loss/brier_raw/brier_norm/calibration_report)
is built around `TournamentPrediction`: ONE categorical event per
tournament (a single real winner), probabilities normalized to sum to
1 across the field. MAKE CUT is a different mathematical object — N
INDEPENDENT per-player Bernoulli predictions (many players can, and
usually do, simultaneously make the cut; there is no "sums to 1"
constraint). Forcing MAKE CUT evaluation through `TournamentPrediction`
would require fabricating a fake single "winner" and re-normalizing
probabilities that were never meant to be mutually exclusive — this
module instead implements the standard, simple binary-classification
formulas directly.

======================================================================
WD/DQ/UNRESOLVED POLICY — explicit, never silent
======================================================================
Per explicit product requirement: WD and DQ are NEVER silently folded
into "missed cut". A player's R2 outcome is one of:
  MADE_CUT   -> actual_cut = 1
  MISSED_CUT -> actual_cut = 0
  WD         -> actual_cut = None (excluded from headline metrics;
                counted and reported separately)
  DQ         -> actual_cut = None (same treatment as WD)
  UNRESOLVED -> actual_cut = None (real R2 status genuinely unknown —
                e.g. the 999/INCOMPLETE sentinel, or the player has no
                R2 row at all — never guessed)
Every summary this module produces reports the WD/DQ/UNRESOLVED counts
explicitly alongside the evaluated-player metrics, never hides them by
omission.

======================================================================
CALIBRATION BUCKET BOUNDARIES — deterministic, documented
======================================================================
Buckets are half-open [lo, hi) except the final bucket, which is
closed on both ends [80, 100] so a predicted 100.0% has a bucket to
land in. A predicted probability of exactly 20.0, 40.0, 60.0, or 80.0
belongs to the HIGHER bucket (e.g. 40.0 -> the 40-60 bucket, not
20-40) — the same convention as a standard right-open histogram bin.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

CUT_OUTCOME_MADE = "MADE_CUT"
CUT_OUTCOME_MISSED = "MISSED_CUT"
CUT_OUTCOME_WD = "WD"
CUT_OUTCOME_DQ = "DQ"
CUT_OUTCOME_UNRESOLVED = "UNRESOLVED"
CUT_OUTCOME_WD_AFTER_R1_START = "WD_AFTER_R1_START"
"""A player who withdrew after Round 1 had already started (real,
human-verified evidence — e.g. explicit "WD" status text observed
directly on the official leaderboard, not inferred from a missing/
ambiguous Round 2 row). Treated identically to CUT_OUTCOME_WD for
scoring purposes (excluded from every headline metric — see
actual_cut_from_outcome), but tracked as its own count so it is never
conflated with a generic WD and never with the SEPARATE population of
players who were already unavailable/excluded before Round 1 even
began (no frozen R1 prediction exists for those at all, so they never
reach this module in the first place)."""

_VALID_OUTCOMES = frozenset(
    {
        CUT_OUTCOME_MADE, CUT_OUTCOME_MISSED, CUT_OUTCOME_WD, CUT_OUTCOME_DQ,
        CUT_OUTCOME_UNRESOLVED, CUT_OUTCOME_WD_AFTER_R1_START,
    }
)

DEFAULT_CUT_THRESHOLD_PCT = 50.0
CALIBRATION_BUCKETS: tuple[tuple[float, float], ...] = ((0, 20), (20, 40), (40, 60), (60, 80), (80, 100))
_LOG_LOSS_EPS = 1e-15
"""Standard log-loss clipping epsilon — predicted probabilities of
exactly 0% or 100% would otherwise make log_loss infinite for a single
wrong case; clipped to [eps, 1-eps] before taking the log, matching
scikit-learn's own default convention. Documented here, not silent."""


def actual_cut_from_outcome(outcome: str) -> Optional[int]:
    """See module docstring's WD/DQ/UNRESOLVED policy. Raises on an
    outcome string outside the closed, real vocabulary above — never
    silently treats an unrecognized status as anything."""
    if outcome not in _VALID_OUTCOMES:
        raise ValueError(f"Unknown R2 outcome {outcome!r} — must be one of {sorted(_VALID_OUTCOMES)}")
    if outcome == CUT_OUTCOME_MADE:
        return 1
    if outcome == CUT_OUTCOME_MISSED:
        return 0
    return None  # WD, DQ, UNRESOLVED


@dataclass(frozen=True)
class PlayerCutEvaluationRow:
    player_code: str
    player_name: str
    r1_rank: Optional[int]
    r1_score_to_par: Optional[float]
    r1_make_cut_pct: float
    """The frozen R1 post_r1_make_cut_pct, 0-100. Never recalculated."""
    r2_outcome: str
    """One of CUT_OUTCOME_*."""
    actual_cut: Optional[int] = None
    predicted_cut_at_50: int = 0
    absolute_probability_error: Optional[float] = None

    def __post_init__(self):
        object.__setattr__(self, "actual_cut", actual_cut_from_outcome(self.r2_outcome))
        object.__setattr__(
            self, "predicted_cut_at_50", 1 if self.r1_make_cut_pct >= DEFAULT_CUT_THRESHOLD_PCT else 0
        )
        if self.actual_cut is not None:
            object.__setattr__(
                self, "absolute_probability_error", abs(self.r1_make_cut_pct / 100.0 - self.actual_cut)
            )


def _evaluated(rows: list[PlayerCutEvaluationRow]) -> list[PlayerCutEvaluationRow]:
    return [r for r in rows if r.actual_cut is not None]


def binary_brier_score(rows: list[PlayerCutEvaluationRow]) -> Optional[float]:
    """Standard binary Brier score: mean((p - y)^2) over evaluated
    players only (WD/DQ/UNRESOLVED excluded, per module policy). p is
    the frozen R1 probability as a 0-1 fraction, y is the real 0/1
    outcome. Returns None if there are zero evaluated players (never a
    fabricated 0.0)."""
    evaluated = _evaluated(rows)
    if not evaluated:
        return None
    return sum((r.r1_make_cut_pct / 100.0 - r.actual_cut) ** 2 for r in evaluated) / len(evaluated)


def binary_log_loss(rows: list[PlayerCutEvaluationRow], eps: float = _LOG_LOSS_EPS) -> Optional[float]:
    """Standard binary log loss, clipped to [eps, 1-eps] (see module
    docstring). Returns None if there are zero evaluated players."""
    evaluated = _evaluated(rows)
    if not evaluated:
        return None
    total = 0.0
    for r in evaluated:
        p = min(max(r.r1_make_cut_pct / 100.0, eps), 1 - eps)
        y = r.actual_cut
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(evaluated)


def threshold_accuracy(rows: list[PlayerCutEvaluationRow], threshold_pct: float = DEFAULT_CUT_THRESHOLD_PCT) -> Optional[dict]:
    """Accuracy of the binary call "predicted make-cut if r1_make_cut_pct
    >= threshold_pct" against the real actual_cut, over evaluated
    players only. Returns None if there are zero evaluated players."""
    evaluated = _evaluated(rows)
    if not evaluated:
        return None
    correct = sum(
        1 for r in evaluated
        if (1 if r.r1_make_cut_pct >= threshold_pct else 0) == r.actual_cut
    )
    return {
        "threshold_pct": threshold_pct,
        "n_evaluated": len(evaluated),
        "correct": correct,
        "accuracy": correct / len(evaluated),
    }


def _bucket_for(pct: float, buckets: tuple[tuple[float, float], ...]) -> Optional[tuple[float, float]]:
    for lo, hi in buckets:
        is_last = (lo, hi) == buckets[-1]
        if lo <= pct < hi or (is_last and pct == hi):
            return (lo, hi)
    return None


def calibration_report(
    rows: list[PlayerCutEvaluationRow], buckets: tuple[tuple[float, float], ...] = CALIBRATION_BUCKETS
) -> list[dict]:
    """One dict per bucket, in `buckets` order — ALWAYS one row per
    configured bucket, even if n=0 for that bucket (never silently
    dropped), so callers can rely on len(result) == len(buckets)."""
    evaluated = _evaluated(rows)
    result = []
    for lo, hi in buckets:
        members = [r for r in evaluated if _bucket_for(r.r1_make_cut_pct, buckets) == (lo, hi)]
        n = len(members)
        if n == 0:
            result.append({
                "bucket": f"{lo:g}-{hi:g}%", "n": 0, "avg_predicted_pct": None,
                "made_cut_count": None, "missed_cut_count": None,
                "actual_made_cut_rate_pct": None, "calibration_gap_pct": None,
            })
            continue
        avg_predicted = sum(r.r1_make_cut_pct for r in members) / n
        made = sum(1 for r in members if r.actual_cut == 1)
        missed = n - made
        actual_rate = 100.0 * made / n
        result.append({
            "bucket": f"{lo:g}-{hi:g}%", "n": n, "avg_predicted_pct": round(avg_predicted, 4),
            "made_cut_count": made, "missed_cut_count": missed,
            "actual_made_cut_rate_pct": round(actual_rate, 4),
            "calibration_gap_pct": round(actual_rate - avg_predicted, 4),
        })
    return result


def best_and_worst_predictions(
    rows: list[PlayerCutEvaluationRow], n: int = 5
) -> tuple[list[PlayerCutEvaluationRow], list[PlayerCutEvaluationRow]]:
    """(best, worst) — ranked by absolute_probability_error ascending
    (best) / descending (worst), evaluated players only, ties broken
    deterministically by player_code so re-running never reorders ties.
    This is the ONLY ranking rule used — never a manually curated list."""
    evaluated = _evaluated(rows)
    ranked = sorted(evaluated, key=lambda r: (r.absolute_probability_error, r.player_code))
    best = ranked[:n]
    worst = list(reversed(ranked[-n:])) if len(ranked) >= n else list(reversed(ranked))
    return best, worst


def summarize_cut_evaluation(rows: list[PlayerCutEvaluationRow]) -> dict:
    evaluated = _evaluated(rows)
    made = sum(1 for r in evaluated if r.actual_cut == 1)
    missed = len(evaluated) - made
    acc = threshold_accuracy(rows)
    return {
        "n_r1_players": len(rows),
        "n_evaluated": len(evaluated),
        "actual_made_cut_count": made,
        "actual_missed_cut_count": missed,
        "wd_count": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_WD),
        "wd_after_r1_start_count": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_WD_AFTER_R1_START),
        "dq_count": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_DQ),
        "unresolved_count": sum(1 for r in rows if r.r2_outcome == CUT_OUTCOME_UNRESOLVED),
        "threshold_accuracy_pct": round(100 * acc["accuracy"], 4) if acc else None,
        "brier_score": round(binary_brier_score(rows), 6) if evaluated else None,
        "log_loss": round(binary_log_loss(rows), 6) if evaluated else None,
        "mean_predicted_cut_pct": round(sum(r.r1_make_cut_pct for r in evaluated) / len(evaluated), 4) if evaluated else None,
        "actual_cut_rate_pct": round(100 * made / len(evaluated), 4) if evaluated else None,
    }
