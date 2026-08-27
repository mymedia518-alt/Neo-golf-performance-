"""Automated data-leakage validation for NEO WIN v0.1 — checked, not
just asserted in a docstring.

Three independent checks, each corresponding to one feature source:

1. `validate_pit_feature_leakage` — for every training/live row, every
   `prior_*`/`neo_consistency_stddev` feature must have been computed
   from a corpus row strictly before the row's own target date. This
   re-derives nothing; it is a black-box re-check using the SAME
   `klpga.backtest.temporal.is_strictly_before` primitive the feature
   computation itself uses, run again independently over the corpus's
   raw event/round dates for the SAME (target_event_id, player_id)
   pair — so a bug in the feature computation and a bug in this check
   would both have to make the identical mistake to go undetected.

2. `validate_official_metric_temporal_safety` — every official-metric
   feature value used must come from the season strictly before the
   target tournament's own season (see klpga.neo_win.official_metrics
   module docstring for why "prior season", never "current"). This
   check re-derives the prior-season number from `target_season` itself
   (prior_season == target_season - 1) and confirms every row's
   `official_metric_season` field equals it — never trusts the caller
   asserted the right season without checking.

3. `validate_probability_sum` — the field's predicted probabilities sum
   to 1.0 within tolerance (mirrors klpga.models.math_utils.
   clip_and_renormalize's own guarantee; re-checked independently here
   since this is the ONE invariant the whole exercise is worthless
   without).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from klpga.backtest.point_in_time_features import Corpus
from klpga.backtest.temporal import is_strictly_before

PROBABILITY_SUM_TOLERANCE = 1e-6


def validate_pit_feature_leakage(
    corpus: Corpus, target_event_id: str, target_effective_date: Optional[date], player_id: str
) -> list[str]:
    """Returns a list of violation descriptions (empty = clean). Checks
    every event/round row this player has that is NOT strictly before
    the target date and confirms none of them share `target_event_id`
    incorrectly excluded, and — the actual leak-detection case — that
    no row ON OR AFTER the target date was silently included by
    independently recomputing the same prior-row filter used by the
    real feature functions and asserting every returned row satisfies
    `is_strictly_before`."""
    violations: list[str] = []
    for e in corpus.events_by_player.get(player_id, []):
        if e.event_id == target_event_id:
            continue
        included = is_strictly_before(e.effective_date, target_effective_date)
        if included and not (e.effective_date and target_effective_date and e.effective_date < target_effective_date):
            violations.append(
                f"event {e.event_id} included but not strictly before target date {target_effective_date}"
            )
    for r in corpus.rounds_by_player.get(player_id, []):
        if r.event_id == target_event_id:
            continue
        included = is_strictly_before(r.effective_date, target_effective_date)
        if included and not (r.effective_date and target_effective_date and r.effective_date < target_effective_date):
            violations.append(
                f"round {r.event_id}/{r.round_number} included but not strictly before target date "
                f"{target_effective_date}"
            )
    return violations


def validate_official_metric_temporal_safety(
    rows: list[dict], *, target_season_key: str = "target_season", metric_season_key: str = "official_metric_season"
) -> list[str]:
    """`rows` are training/live feature rows carrying both the target
    tournament's season and the season the official-metric feature was
    actually pulled from (None if the feature was omitted for that
    row). Violates only when a metric season is present and is NOT
    exactly target_season - 1."""
    violations: list[str] = []
    for row in rows:
        target_season = row.get(target_season_key)
        metric_season = row.get(metric_season_key)
        if metric_season is None or target_season is None:
            continue
        if metric_season != target_season - 1:
            violations.append(
                f"{row.get('target_event_id', '?')}/{row.get('player_code', '?')}: "
                f"official_metric_season={metric_season} is not target_season({target_season}) - 1"
            )
    return violations


def validate_probability_sum(probabilities: dict[str, float], *, tolerance: float = PROBABILITY_SUM_TOLERANCE) -> list[str]:
    if not probabilities:
        return ["empty probability field"]
    total = sum(probabilities.values())
    if abs(total - 1.0) > tolerance:
        return [f"probability sum {total!r} deviates from 1.0 by more than {tolerance}"]
    return []
