"""Consistency / downside-risk feature — NOT present in `klpga.backtest.
point_in_time_features` today, so this adds it as a new, point-in-time
-safe sibling computation rather than editing that leakage-critical,
already-tested module.

`neo_consistency_stddev`: population standard deviation of a player's
`round_to_par` values across PRIOR rounds only (same temporal gate as
every other point-in-time feature in this project:
`klpga.backtest.temporal.is_strictly_before`, reusing the already-
loaded `Corpus` from `klpga.backtest.point_in_time_features.load_corpus`
so this never re-queries the DB). A higher stddev means a more erratic
scoring pattern round-to-round — the standard, simplest "consistency"
proxy; it also captures downside risk in the same number (a player who
occasionally implodes to a very bad round has a high stddev even if
their average is fine). This is a disclosed simplification (a true
downside-only measure, e.g. semi-deviation above par, is a candidate
future refinement, not silently assumed better without evidence) —
matching this project's own established style for `klpga.models.
candidates`'s shrinkage formula.

Same missing-data convention as every other point-in-time feature:
`_n` is the actual count of prior rounds used (0 for a rookie or a
player with no round_to_par history — see `point_in_time_features.py`'s
docstring on why round_to_par is genuinely sparse); the value itself is
None when `_n < 2` (a standard deviation needs at least 2 points to be
non-degenerate — a single data point returns None, not a fabricated 0).
"""
from __future__ import annotations

import statistics
from datetime import date
from typing import Optional

from klpga.backtest.point_in_time_features import Corpus
from klpga.backtest.temporal import is_strictly_before


def compute_consistency_feature(
    corpus: Corpus, target_event_id: str, target_effective_date: Optional[date], player_id: str
) -> tuple[Optional[float], int]:
    """Returns (neo_consistency_stddev, neo_consistency_stddev_n)."""
    rounds = corpus.rounds_by_player.get(player_id, [])
    prior_values = [
        r.round_to_par
        for r in rounds
        if r.event_id != target_event_id
        and r.round_to_par is not None
        and is_strictly_before(r.effective_date, target_effective_date)
    ]
    n = len(prior_values)
    if n < 2:
        return None, n
    return round(statistics.stdev(prior_values), 3), n
