"""Point-in-time feature engine — for a given (target tournament,
player), computes every feature using ONLY that player's OTHER
tournaments strictly before the target's effective start date (see
klpga.backtest.temporal). This is the single leakage-critical module in
this package: every other module (walk_forward.py, the diagnostic
script) calls THIS module's `compute_point_in_time_features` rather
than re-implementing any date/event filtering itself, so there is
exactly one place a leak could be introduced — and it is covered by the
mandatory adversarial tests in tests/test_point_in_time_features.py.

======================================================================
FEATURE DEFINITIONS (source field, formula, sample size, missing-data
treatment for every feature — mirrors klpga.analytics.player_stats's
documentation convention)
======================================================================

All "prior_*" features below are computed over `prior_events` — every
player_event row for this player_id, for a DIFFERENT event_id than the
target, whose tournament's effective date is STRICTLY before the
target's effective date (temporal.is_strictly_before). No feature ever
reads a row belonging to the target event_id itself, regardless of
date, and no feature is padded to a fixed window size if fewer prior
events exist — every windowed feature carries a companion `_n` giving
the actual count used (0 for a rookie with no prior events; the feature
value itself is None in that case, never a fabricated placeholder).

prior_events_n
    COUNT of prior_events. 0 for a debuting/rookie player — the player
    still appears as a row in the walk-forward dataset (see
    walk_forward.py), just with prior_events_n=0 and every other prior_*
    feature None/0.

prior_wins / prior_top5 / prior_top10 / prior_made_cuts / prior_cut_rate
    Source: player_event.finish_position_numeric / made_cut, restricted
    to prior_events. Same formulas as
    klpga.analytics.player_stats.compute_player_stats's derived_wins/
    derived_top5/derived_top10/derived_made_cuts/derived_cut_rate,
    just computed over the point-in-time-restricted event set instead
    of the player's full history. prior_cut_rate is
    prior_made_cuts / prior_events_n, rounded to 2dp, None if
    prior_events_n is 0.

prior_avg_round_score_to_par / prior_avg_round_score_to_par_n
    Source: player_event.score_to_par and rounds_played over
    prior_events with both present. Same rate formula as
    klpga.analytics.player_stats's derived_avg_round_score_to_par —
    sum(score_to_par)/sum(rounds_played), a rounds-weighted per-round
    rate, NOT an average of per-event totals. _n is the summed
    rounds_played denominator itself (see that module's docstring for
    why this formula, not a raw average of the sparse real
    round_to_par field, was chosen as the "career" scoring feature).

prior_recent_form_{5,10,20} / prior_recent_form_{5,10,20}_n
    Source: player_event.score_to_par over prior_events, ordered
    newest-to-oldest by effective date, taking up to the N most recent
    with a non-NULL score_to_par (same windowing convention as
    klpga.analytics.player_stats's derived_recent_event_form_N). Never
    padded — _n is the actual count used, <= N.

prior_avg_round_to_par / prior_avg_round_to_par_n
    Source: player_round.round_to_par (the site's real per-round
    `data-todayunderpar` figure) over prior rounds. UNLIKE
    prior_avg_round_score_to_par above, this reads the field directly
    rather than deriving a rate from score_to_par/rounds_played — and
    is therefore genuinely SPARSE: round_to_par is only ever collected
    for a round klpga.collectors.leaderboard queried directly (round 1
    and the tournament's final round always; other rounds only when at
    least one player dropped out before the final round — see that
    module's docstring). A player with a real prior_avg_round_to_par_n
    of 0 does NOT mean "no rounds played" (see prior_events_n /
    prior_avg_round_score_to_par_n for that) — it means none of this
    player's prior ROUNDS happened to be one this project directly
    queried for round_to_par. Never fabricated to fill this gap.

prior_avg_field_relative_round_score / prior_avg_field_relative_round_score_n
    Source: player_round.round_score (well-covered — one row per round
    actually played, real strokes; NOT the sparse round_to_par field
    above) for prior rounds, compared against a LEAVE-ONE-OUT field
    average round_score for that SAME (event_id, round_number) —
    computed from every OTHER player's round_score in that same past
    round (excluding this player's own score from the average). Since
    that past event/round is, by construction, strictly before the
    target (the row was only included in prior_rounds after that
    check), using ANY other player's data from within that same past
    event is not a leak of any kind — it is a property of an event
    that has already fully completed, unrelated to the target
    tournament's outcome. A round is skipped (not counted toward this
    feature) if fewer than 2 total players have a real round_score for
    that (event_id, round_number) — a "field" of 1 has no meaningful
    average to compare against. This is a plain per-round scoring
    deviation, NOT a proxy for Strokes Gained (which needs shot-level
    distance-to-hole/lie data this project has never collected — see
    klpga.analytics.player_stats's module docstring) and must never be
    called that.

Deliberately NOT implemented, per explicit instruction: any SG/GIR/
driving-distance/driving-accuracy/putting/course-par proxy, and any
probability, weight, cap, or calibration constant.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from klpga.backtest.temporal import EffectiveDate, effective_tournament_date, is_strictly_before

RECENT_FORM_WINDOWS = (5, 10, 20)


def _round2(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 2)


@dataclass(frozen=True)
class EventHistoryRow:
    event_id: str
    player_id: str
    effective_date: Optional[date]
    date_is_exact: bool
    made_cut: bool
    finish_position_numeric: Optional[int]
    score_to_par: Optional[int]
    rounds_played: Optional[int]


@dataclass(frozen=True)
class RoundHistoryRow:
    event_id: str
    player_id: str
    round_number: int
    effective_date: Optional[date]
    round_score: Optional[int]
    round_to_par: Optional[int]


@dataclass
class Corpus:
    """Every player_event / player_round row across the WHOLE dataset,
    loaded once. Deliberately unfiltered by any target tournament —
    filtering happens inside compute_point_in_time_features for exactly
    one (target, player) pair at a time, which is what the adversarial
    leakage tests exercise: inserting extra rows into this corpus and
    confirming a given target's computed features don't change."""

    events_by_player: dict[str, list[EventHistoryRow]] = field(default_factory=dict)
    rounds_by_player: dict[str, list[RoundHistoryRow]] = field(default_factory=dict)
    # (event_id, round_number) -> (sum(round_score) over every player
    # with a real round_score in that round, count). Used for a
    # leave-one-out field average — see prior_avg_field_relative_round_score.
    round_field_sums: dict[tuple[str, int], tuple[int, int]] = field(default_factory=dict)
    tournament_dates: dict[str, EffectiveDate] = field(default_factory=dict)


def load_corpus(conn: sqlite3.Connection) -> Corpus:
    tournament_dates: dict[str, EffectiveDate] = {}
    for event_id, start_date, end_date in conn.execute(
        "SELECT event_id, start_date, end_date FROM tournament_master"
    ):
        tournament_dates[event_id] = effective_tournament_date(start_date, end_date)

    events_by_player: dict[str, list[EventHistoryRow]] = {}
    for player_id, event_id, made_cut, finish_position_numeric, score_to_par, rounds_played in conn.execute(
        "SELECT player_id, event_id, made_cut, finish_position_numeric, score_to_par, rounds_played "
        "FROM player_event"
    ):
        eff = tournament_dates.get(event_id, EffectiveDate(None, False))
        events_by_player.setdefault(player_id, []).append(
            EventHistoryRow(
                event_id=event_id,
                player_id=player_id,
                effective_date=eff.value,
                date_is_exact=eff.is_exact,
                made_cut=bool(made_cut),
                finish_position_numeric=finish_position_numeric,
                score_to_par=score_to_par,
                rounds_played=rounds_played,
            )
        )

    rounds_by_player: dict[str, list[RoundHistoryRow]] = {}
    round_field_sums: dict[tuple[str, int], tuple[int, int]] = {}
    for player_id, event_id, round_number, round_score, round_to_par in conn.execute(
        "SELECT player_id, event_id, round_number, round_score, round_to_par FROM player_round"
    ):
        eff = tournament_dates.get(event_id, EffectiveDate(None, False))
        rounds_by_player.setdefault(player_id, []).append(
            RoundHistoryRow(
                event_id=event_id,
                player_id=player_id,
                round_number=round_number,
                effective_date=eff.value,
                round_score=round_score,
                round_to_par=round_to_par,
            )
        )
        if round_score is not None:
            key = (event_id, round_number)
            prev_sum, prev_n = round_field_sums.get(key, (0, 0))
            round_field_sums[key] = (prev_sum + round_score, prev_n + 1)

    return Corpus(
        events_by_player=events_by_player,
        rounds_by_player=rounds_by_player,
        round_field_sums=round_field_sums,
        tournament_dates=tournament_dates,
    )


@dataclass(frozen=True)
class PointInTimeFeatures:
    player_code: str
    player_name: str
    target_event_id: str
    target_effective_date: Optional[date]

    prior_events_n: int
    prior_wins: int
    prior_top5: int
    prior_top10: int
    prior_made_cuts: int
    prior_cut_rate: Optional[float]

    prior_avg_round_score_to_par: Optional[float]
    prior_avg_round_score_to_par_n: int

    prior_recent_form_5: Optional[float]
    prior_recent_form_5_n: int
    prior_recent_form_10: Optional[float]
    prior_recent_form_10_n: int
    prior_recent_form_20: Optional[float]
    prior_recent_form_20_n: int

    prior_avg_round_to_par: Optional[float]
    prior_avg_round_to_par_n: int

    prior_avg_field_relative_round_score: Optional[float]
    prior_avg_field_relative_round_score_n: int

    # ---- audit trace, for scripts/16's diagnostic — never exported
    # into the flat walk-forward dataset row (see walk_forward.py) ----
    prior_event_ids_used: tuple[str, ...] = field(default_factory=tuple)
    recent_form_event_ids_used: dict[int, tuple[str, ...]] = field(default_factory=dict)
    prior_round_keys_used: tuple[tuple[str, int], ...] = field(default_factory=tuple)


def compute_point_in_time_features(
    corpus: Corpus,
    target_event_id: str,
    target_effective_date: Optional[date],
    player_id: str,
    player_name: str,
) -> PointInTimeFeatures:
    all_events = corpus.events_by_player.get(player_id, [])
    prior_events = [
        e for e in all_events
        if e.event_id != target_event_id and is_strictly_before(e.effective_date, target_effective_date)
    ]
    # Safe to sort by effective_date: is_strictly_before already
    # guarantees every row here has a real, non-None date.
    prior_events.sort(key=lambda e: e.effective_date, reverse=True)

    prior_events_n = len(prior_events)
    wins = sum(1 for e in prior_events if e.finish_position_numeric == 1)
    top5 = sum(1 for e in prior_events if e.finish_position_numeric is not None and e.finish_position_numeric <= 5)
    top10 = sum(1 for e in prior_events if e.finish_position_numeric is not None and e.finish_position_numeric <= 10)
    made_cuts = sum(1 for e in prior_events if e.made_cut)
    cut_rate = _round2(made_cuts / prior_events_n) if prior_events_n else None

    rate_events = [e for e in prior_events if e.score_to_par is not None and e.rounds_played]
    rate_num = sum(e.score_to_par for e in rate_events)
    rate_den = sum(e.rounds_played for e in rate_events)
    avg_round_score_to_par = _round2(rate_num / rate_den) if rate_den else None

    recent_form_values: dict[int, tuple[Optional[float], int]] = {}
    recent_form_ids: dict[int, tuple[str, ...]] = {}
    scored_events = [e for e in prior_events if e.score_to_par is not None]
    for window in RECENT_FORM_WINDOWS:
        windowed = scored_events[:window]
        if windowed:
            vals = [e.score_to_par for e in windowed]
            recent_form_values[window] = (_round2(sum(vals) / len(vals)), len(vals))
            recent_form_ids[window] = tuple(e.event_id for e in windowed)
        else:
            recent_form_values[window] = (None, 0)
            recent_form_ids[window] = ()

    all_rounds = corpus.rounds_by_player.get(player_id, [])
    prior_rounds = [
        r for r in all_rounds
        if r.event_id != target_event_id and is_strictly_before(r.effective_date, target_effective_date)
    ]

    rtp_values = [r.round_to_par for r in prior_rounds if r.round_to_par is not None]
    avg_round_to_par = _round2(sum(rtp_values) / len(rtp_values)) if rtp_values else None

    field_relative_values = []
    for r in prior_rounds:
        if r.round_score is None:
            continue
        key = (r.event_id, r.round_number)
        total, n = corpus.round_field_sums.get(key, (0, 0))
        if n < 2:
            continue  # a "field" of 1 (just this player) has no meaningful average to compare against
        field_avg_excluding_self = (total - r.round_score) / (n - 1)
        field_relative_values.append(r.round_score - field_avg_excluding_self)
    avg_field_relative = _round2(sum(field_relative_values) / len(field_relative_values)) if field_relative_values else None

    return PointInTimeFeatures(
        player_code=player_id,
        player_name=player_name,
        target_event_id=target_event_id,
        target_effective_date=target_effective_date,
        prior_events_n=prior_events_n,
        prior_wins=wins,
        prior_top5=top5,
        prior_top10=top10,
        prior_made_cuts=made_cuts,
        prior_cut_rate=cut_rate,
        prior_avg_round_score_to_par=avg_round_score_to_par,
        prior_avg_round_score_to_par_n=rate_den,
        prior_recent_form_5=recent_form_values[5][0],
        prior_recent_form_5_n=recent_form_values[5][1],
        prior_recent_form_10=recent_form_values[10][0],
        prior_recent_form_10_n=recent_form_values[10][1],
        prior_recent_form_20=recent_form_values[20][0],
        prior_recent_form_20_n=recent_form_values[20][1],
        prior_avg_round_to_par=avg_round_to_par,
        prior_avg_round_to_par_n=len(rtp_values),
        prior_avg_field_relative_round_score=avg_field_relative,
        prior_avg_field_relative_round_score_n=len(field_relative_values),
        prior_event_ids_used=tuple(e.event_id for e in prior_events),
        recent_form_event_ids_used=recent_form_ids,
        prior_round_keys_used=tuple((r.event_id, r.round_number) for r in prior_rounds),
    )


# Flat, exported feature-column names for a walk-forward dataset row —
# excludes the audit-trace fields above, which are for
# scripts/16_backtest_diagnostic.py only.
FEATURE_COLUMNS = (
    "prior_events_n",
    "prior_wins",
    "prior_top5",
    "prior_top10",
    "prior_made_cuts",
    "prior_cut_rate",
    "prior_avg_round_score_to_par",
    "prior_avg_round_score_to_par_n",
    "prior_recent_form_5",
    "prior_recent_form_5_n",
    "prior_recent_form_10",
    "prior_recent_form_10_n",
    "prior_recent_form_20",
    "prior_recent_form_20_n",
    "prior_avg_round_to_par",
    "prior_avg_round_to_par_n",
    "prior_avg_field_relative_round_score",
    "prior_avg_field_relative_round_score_n",
)


def features_as_flat_dict(features: PointInTimeFeatures) -> dict:
    return {col: getattr(features, col) for col in FEATURE_COLUMNS}
