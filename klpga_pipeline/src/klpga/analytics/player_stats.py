"""Derived (self-computed, NOT official KLPGA Data Center) player
performance aggregates over the validated tournament_master /
player_event / player_round dataset — raw feature inputs for the NEO
GOLF DATA Top-20 / win-probability page.

Every metric here is computed straight from data this project has
already confirmed and collected (see docs/SITE_STRUCTURE_TODO.md
sections 1-2) — nothing here reads data.klpga.co.kr (the official
Performance Statistics data center), which has never been reached from
any environment this project has run in.

True Strokes Gained (needs each shot's distance-to-hole and lie, plus a
field-relative baseline) and GIR (needs hole-by-hole green-in-regulation
data) are NOT computable from this dataset — the confirmed
roundLeaderboard endpoint only ever returns per-round/tournament totals
and a rank, never shot-level or hole-level detail (`data-inghole` was
investigated and found unreliable — see docs/SITE_STRUCTURE_TODO.md
section 2). This module deliberately does NOT attempt a "proxy" for
either metric; player_stats_snapshot's sg_*/gir columns (and the other
official Data Center columns: driving_distance, driving_accuracy,
putting_average, sixties_rate, birdie_average, par_breakers, sand_save,
scrambling) are simply never written here and stay NULL.

Every derived metric below is keyed by player_id, which stores the
confirmed real KLPGA playerCode (`_playerCode`) — never player_name —
per docs/SITE_STRUCTURE_TODO.md section 2.

======================================================================
NAMING CONVENTION (added 2026-08-25, after a red-team check)
======================================================================
A prior version of this module had a single `avg_score_to_par` metric
that averaged `player_event.score_to_par` — the site's own
TOURNAMENT-CUMULATIVE to-par figure (`data-totunderpar`), one value per
whole event, NOT a per-round figure. On the real production dataset
that metric came out around -4 to -5 for strong players, which reads as
implausibly low IF (mis)interpreted as "average round score relative to
par" — a single round in the -4 to -5 range would be an exceptional
round, not a typical one. The number itself wasn't wrong (see the
"RED-TEAM VERIFICATION" section below), but the OLD NAME didn't say
which kind of average it was, so it could be misread. Every column here
now says which kind it is, and this must never regress:
  - `_event_*`  -> one value per EVENT, averaged one-event-one-vote,
                   from player_event.score_to_par (a tournament-
                   cumulative total). Comparable in magnitude to a
                   whole made-cut event's finish (commonly -5 to -15)
                   or a whole missed-cut event's finish (commonly a
                   small positive number over ~2 rounds) — NOT
                   comparable to a single round's performance.
  - `_round_*`  -> either computed directly from real per-round data
                   (player_round.round_score), or expressed as a rate
                   PER ROUND (a sum of event-level totals divided by a
                   sum of rounds played) — comparable in magnitude to
                   what one round typically looks like relative to par
                   (commonly -1 to -3 for a strong player, per the
                   verification below).
Before adding any new derived_* column: if it is built from
player_event.score_to_par (or anything else that is a per-event total,
not a per-round figure), its name MUST say `_event_`. If it is a true
per-round figure or a per-round-normalized rate, its name MUST say
`_round_`. No column name may omit both.

======================================================================
RED-TEAM VERIFICATION: is derived_avg_round_score_to_par mathematically
sound, and is player_round.round_to_par (`data-todayunderpar`) reliable
enough to use directly?
======================================================================
`derived_avg_round_score_to_par` = sum(player_event.score_to_par) /
sum(player_event.rounds_played) across a player's valid events — it
does NOT average real per-round to-par values directly, because
`player_round.round_to_par` (the site's per-round `data-todayunderpar`
figure) is only ever stored for rounds klpga.collectors.leaderboard
actually queried directly (see that module's docstring) — round 1 and
the tournament's final round always, every intermediate round only when
at least one player dropped out of the field before the final round.
Coverage is therefore real but PARTIAL for many players, so an average
built by summing only the round_to_par values that happen to be present
would silently under- or over-weight players/events with better
coverage — a bias `derived_avg_round_score_to_par`'s formula avoids
entirely by working from `score_to_par` (which is populated for every
event with a completed round) and `rounds_played` (a fully-confirmed
count) instead.

`scripts/12_verify_round_to_par_reliability.py` independently checks,
against real production rows, whether this is actually the right thing
to do — i.e. whether `round_to_par` is reliable enough that it WOULD
give the same answer if used directly, wherever there's enough of it to
check:
  1. For players with exactly ONE valid round (rounds_played == 1):
     `round_to_par` for that single round and `score_to_par` for the
     event MUST be identical if both fields mean what this project
     believes they mean — with only one round played, "today" and
     "tournament total so far" are the same thing by definition. This
     needs no additivity assumption at all.
  2. For players whose event has `round_to_par` present on EVERY round
     they played (rounds_played >= 2): if per-round to-par values are
     genuine, independent daily deltas that sum to the tournament
     total, then sum(round_to_par across their rounds) MUST equal
     score_to_par for that event.
  3. Separately, for that same fully-covered subset, the script computes
     derived_avg_round_score_to_par's rate formula
     (sum(score_to_par)/sum(rounds_played)) alongside a DIRECT
     reconstruction from the raw round_to_par values
     (sum(round_to_par)/count(rounds)) and confirms they converge to
     the same figure.
See that script's docstring and docs/SITE_STRUCTURE_TODO.md section 6
for the actual production-data result — this module's formula choice
is not final proof by itself, only the reasoning; the script is the
verification.

======================================================================
METRIC REFERENCE — for each derived_* column: source fields, formula,
sample size, missing-data treatment, and provenance.
======================================================================

derived_tournaments_played (derived, from real data)
    Source: COUNT of player_event rows for a player_id.
    Formula: len(events).
    Sample size: n/a (this IS the count).
    Missing-data treatment: none — includes tournaments where the
    player has a real, confirmed rounds_played=0 (an early exit with no
    valid round score anywhere; see docs/SITE_STRUCTURE_TODO.md section
    5) — they were still in the field, so they count as "played."

derived_rounds_played (derived, from real data)
    Source: SUM(player_event.rounds_played) — a confirmed count,
    including real zeros (never NULL-collapsed; see
    docs/SITE_STRUCTURE_TODO.md section 5).
    Formula: sum of rounds_played across all their tournaments.
    Sample size: n/a. Missing-data treatment: none needed.

derived_made_cuts / derived_cut_rate (derived, from real data)
    Source: player_event.made_cut (1 if the player has a real score for
    the tournament's actual final round — a structural fact, not text
    matching; see docs/SITE_STRUCTURE_TODO.md section 5).
    Formula: made_cuts = SUM(made_cut); cut_rate = made_cuts /
    tournaments_played, rounded to 2dp.
    Sample size: tournaments_played (the denominator).
    Missing-data treatment: cut_rate is NULL only if
    tournaments_played is 0, which cannot happen for a player who
    appears in this table at all.
    Caveat: "made the cut" here means "reached the tournament's actual
    final round," which is the right general definition regardless of
    whether a given event literally used a 36-hole cut.

derived_wins / derived_top5 / derived_top10 / derived_best_finish
(derived, from real/official per-event data)
    Source: player_event.finish_position_numeric (the site's own
    normalized numeric rank parse — e.g. "T2" -> 2).
    Formula: wins = count(finish_position_numeric == 1); top5 =
    count(<= 5); top10 = count(<= 10); best_finish =
    min(finish_position_numeric) across all their events.
    Sample size: tournaments_played.
    Missing-data treatment: events with no numeric finish (NULL —
    e.g. the confirmed "999" incomplete-round sentinel) are excluded
    from all four; best_finish is NULL if every event lacks one.
    Known open question: whether the site ever shows a tied leader as
    rank "T1" before a playoff resolves it (which would parse to
    finish_position_numeric=1, tie_flag=1) has not been specifically
    confirmed against a real playoff case in the collected dataset —
    if so, `wins` would count both tied co-leaders. Flagged, not
    guessed at.

derived_avg_round_score / derived_round_scoring_stddev (derived, from
real per-round data — renamed 2026-08-25 from avg_score/scoring_stddev,
same formula, name now says `_round_` explicitly)
    Source: player_round.round_score (one row per round actually
    played, real strokes — never a placeholder/sentinel value; see
    klpga.parsers.leaderboard_parser._to_stroke_count).
    Formula: avg_round_score = mean(round_score) across every
    player_round row for that player, rounded to 2dp — a true per-round
    scoring average (not per-event). round_scoring_stddev = sample
    standard deviation (statistics.stdev, i.e. n-1 denominator) of the
    same values, rounded to 2dp.
    Sample size: derived_rounds_played (same n).
    Missing-data treatment: avg_round_score is NULL if the player has
    zero player_round rows; round_scoring_stddev is NULL if fewer than
    2 (sample stdev is undefined for n<2).

derived_avg_event_score_to_par + derived_avg_event_score_to_par_n
(derived, from official per-event data — renamed 2026-08-25 from
avg_score_to_par, same formula, name now says `_event_` explicitly)
    Source: player_event.score_to_par (the site's own
    `data-totunderpar` figure per tournament — official, tournament-
    CUMULATIVE, not per-round; see the module-level notes above).
    Formula: mean(score_to_par) across events where it's non-NULL,
    rounded to 2dp — every event counts equally regardless of how many
    rounds it represents (a 2-round missed cut and a 4-round made cut
    each contribute one value to the average).
    Sample size: derived_avg_event_score_to_par_n — count of events
    with a non-NULL score_to_par (<= tournaments_played).
    Missing-data treatment: events with no score_to_par (the
    "INCOMPLETE" 999-sentinel case) are excluded, not treated as 0.
    NULL / 0 if no event has one.

derived_avg_round_score_to_par + derived_avg_round_score_to_par_n
(derived, from official per-event data expressed as a per-round RATE —
NEW 2026-08-25)
    Source: player_event.score_to_par and player_event.rounds_played,
    for events where both are present.
    Formula: sum(score_to_par) / sum(rounds_played) across those
    events, rounded to 2dp — a rounds-WEIGHTED average, so a 4-round
    made-cut event contributes twice the weight of a 2-round missed-cut
    event. This is deliberately NOT the same as averaging
    derived_avg_event_score_to_par by rounds_played after the fact —
    it's computed directly as one sum-of-sums ratio. See the
    "RED-TEAM VERIFICATION" section above and
    scripts/12_verify_round_to_par_reliability.py for why this formula
    (rather than averaging the sparse real round_to_par field directly)
    was chosen, and for the production-data proof that it agrees with
    a direct reconstruction from round_to_par wherever there's enough
    of that field to check.
    Sample size: derived_avg_round_score_to_par_n — the actual sum of
    rounds_played used (the denominator itself, not an event count).
    Missing-data treatment: an event is excluded from both the
    numerator and denominator if its score_to_par is NULL or its
    rounds_played is 0/NULL. NULL / 0 if no event qualifies.

derived_recent_event_form_5 / _10 / _20 and their _n companions
(derived, from official per-event data; project-defined window, not an
official KLPGA concept — renamed 2026-08-25 from recent_form_*, same
formula, name now says `_event_` explicitly)
    Source: player_event.score_to_par, ordered by the player's
    tournaments newest-to-oldest (tournament_master.end_date DESC).
    Formula: unweighted mean of score_to_par over up to the N most
    recent events that HAVE a non-NULL score_to_par (N in {5, 10, 20}),
    rounded to 2dp.
    Sample size: stored explicitly alongside the value, in
    derived_recent_event_form_{N}_n — the actual count of events used
    (<= N, since KLPGA fields are large and most players have far
    fewer than 20 of the 100 validated tournaments). A page displaying
    this MUST show the _n alongside the value (e.g. "recent form: -3.20
    (5 events)") rather than implying a full N-event trend it doesn't
    have.
    Missing-data treatment: value is NULL and _n is 0 if the player has
    no event with a real score_to_par.

derived_weighted_recent_event_form and its _n companion (derived;
project-defined weighting for this page, NOT an official metric —
renamed 2026-08-25 from weighted_recent_form, same formula, name now
says `_event_` explicitly)
    Source: same as recent-event-form above, over the most recent
    _WEIGHTED_FORM_WINDOW (10) events with a non-NULL score_to_par.
    Formula: linearly-decaying weighted mean — if k events are used
    (k <= 10), the most recent gets weight k, the next k-1, ... down to
    weight 1 for the oldest of the k used; weighted_recent_event_form =
    sum(weight_i * score_to_par_i) / sum(weight_i), rounded to 2dp.
    Sample size: derived_weighted_recent_event_form_n (the k actually
    used).
    Missing-data treatment: NULL / 0 if no event has a real
    score_to_par, same as the unweighted recent-form metrics.
"""
from __future__ import annotations

import sqlite3
import statistics
from typing import Optional

# Recent-form window sizes reported per player, and the window used for
# the single weighted-recent-form figure. Project-defined choices for
# this Top-20 page, not an official KLPGA concept — documented above.
RECENT_FORM_WINDOWS = (5, 10, 20)
WEIGHTED_FORM_WINDOW = 10


def _round2(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 2)


def _fetch_player_events(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    """One row per (player, tournament), newest tournament first per
    player (by the tournament's end_date), for every player_id present
    in player_event."""
    rows = conn.execute(
        """
        SELECT pe.player_id, pe.event_id, pe.made_cut, pe.finish_position_numeric,
               pe.score_to_par, pe.rounds_played, tm.end_date
        FROM player_event pe
        INNER JOIN tournament_master tm ON pe.event_id = tm.event_id
        ORDER BY pe.player_id, tm.end_date DESC
        """
    ).fetchall()
    by_player: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_player.setdefault(row["player_id"], []).append(row)
    return by_player


def _fetch_round_scores(conn: sqlite3.Connection) -> dict[str, list[int]]:
    rows = conn.execute(
        "SELECT player_id, round_score FROM player_round WHERE round_score IS NOT NULL"
    ).fetchall()
    by_player: dict[str, list[int]] = {}
    for row in rows:
        by_player.setdefault(row["player_id"], []).append(row["round_score"])
    return by_player


def _recent_event_form(events_newest_first: list[sqlite3.Row], window: int) -> tuple[Optional[float], int]:
    """Unweighted average score_to_par over the player's most recent
    `window` events that have a real (non-NULL) score_to_par. Returns
    (value_or_None, n_events_actually_used) — see module docstring."""
    values = [e["score_to_par"] for e in events_newest_first if e["score_to_par"] is not None][:window]
    if not values:
        return None, 0
    return _round2(sum(values) / len(values)), len(values)


def _weighted_recent_event_form(events_newest_first: list[sqlite3.Row], window: int) -> tuple[Optional[float], int]:
    """Linearly-decaying weighted average score_to_par over the most
    recent `window` events with a real score_to_par — see module
    docstring for the exact weighting formula."""
    values = [e["score_to_par"] for e in events_newest_first if e["score_to_par"] is not None][:window]
    k = len(values)
    if k == 0:
        return None, 0
    weights = list(range(k, 0, -1))
    weighted_sum = sum(w * v for w, v in zip(weights, values))
    return _round2(weighted_sum / sum(weights)), k


def compute_player_stats(conn: sqlite3.Connection) -> list[dict]:
    """One dict per player_id with every derived_* column populated —
    see the module docstring for source fields/formula/sample
    size/missing-data treatment of each. Sets conn.row_factory =
    sqlite3.Row as a side effect. Only players with at least one
    player_event row appear (nothing to compute otherwise)."""
    conn.row_factory = sqlite3.Row
    events_by_player = _fetch_player_events(conn)
    rounds_by_player = _fetch_round_scores(conn)

    results = []
    for player_id, events in events_by_player.items():
        tournaments_played = len(events)
        made_cuts = sum(1 for e in events if e["made_cut"])
        wins = sum(1 for e in events if e["finish_position_numeric"] == 1)
        top5 = sum(
            1 for e in events
            if e["finish_position_numeric"] is not None and e["finish_position_numeric"] <= 5
        )
        top10 = sum(
            1 for e in events
            if e["finish_position_numeric"] is not None and e["finish_position_numeric"] <= 10
        )
        finishes = [e["finish_position_numeric"] for e in events if e["finish_position_numeric"] is not None]
        best_finish = min(finishes) if finishes else None
        rounds_played = sum(e["rounds_played"] or 0 for e in events)

        scores = rounds_by_player.get(player_id, [])
        avg_round_score = _round2(sum(scores) / len(scores)) if scores else None
        round_scoring_stddev = _round2(statistics.stdev(scores)) if len(scores) >= 2 else None

        to_par_values = [e["score_to_par"] for e in events if e["score_to_par"] is not None]
        avg_event_score_to_par = _round2(sum(to_par_values) / len(to_par_values)) if to_par_values else None
        avg_event_score_to_par_n = len(to_par_values)

        rate_events = [e for e in events if e["score_to_par"] is not None and e["rounds_played"]]
        rate_numerator = sum(e["score_to_par"] for e in rate_events)
        rate_denominator = sum(e["rounds_played"] for e in rate_events)
        avg_round_score_to_par = _round2(rate_numerator / rate_denominator) if rate_denominator else None
        avg_round_score_to_par_n = rate_denominator

        cut_rate = _round2(made_cuts / tournaments_played) if tournaments_played else None

        row = {
            "player_id": player_id,
            "derived_tournaments_played": tournaments_played,
            "derived_rounds_played": rounds_played,
            "derived_made_cuts": made_cuts,
            "derived_cut_rate": cut_rate,
            "derived_wins": wins,
            "derived_top5": top5,
            "derived_top10": top10,
            "derived_best_finish": best_finish,
            "derived_avg_round_score": avg_round_score,
            "derived_round_scoring_stddev": round_scoring_stddev,
            "derived_avg_event_score_to_par": avg_event_score_to_par,
            "derived_avg_event_score_to_par_n": avg_event_score_to_par_n,
            "derived_avg_round_score_to_par": avg_round_score_to_par,
            "derived_avg_round_score_to_par_n": avg_round_score_to_par_n,
        }
        for window in RECENT_FORM_WINDOWS:
            value, n = _recent_event_form(events, window)
            row[f"derived_recent_event_form_{window}"] = value
            row[f"derived_recent_event_form_{window}_n"] = n
        wf_value, wf_n = _weighted_recent_event_form(events, WEIGHTED_FORM_WINDOW)
        row["derived_weighted_recent_event_form"] = wf_value
        row["derived_weighted_recent_event_form_n"] = wf_n

        results.append(row)
    return results
