"""Walk-forward modeling/backtest dataset construction, plus an
eligibility trade-off report over how much prior history is required.

No probability model, feature weight, probability cap, or calibration
constant lives anywhere in this module or this package — see
klpga.backtest's package docstring. This module only assembles the
FEATURES + LABELS dataset a future model would be fit/evaluated on.

======================================================================
DATASET SHAPE
======================================================================
One row per (target tournament, field member) — see
klpga.backtest.historical_field for exactly how "field member" is
reconstructed for a historical tournament (and its documented
limitation: a RESULT field, not a confirmed pre-tournament ENTRY list).

  target_game_code, target_event_id, target_start_date,
  target_start_date_is_exact, player_code, player_name,
  <every FEATURE_COLUMNS field from klpga.backtest.point_in_time_features>,
  label_finish_position, label_finish_position_numeric,
  label_made_cut, label_is_winner

Every `label_*` column comes from the TARGET tournament's own outcome —
it is a training/evaluation LABEL, never a feature, and
klpga.backtest.point_in_time_features never reads it when building the
feature columns above (see that module's docstring — historical_field's
FieldMember keeps them in physically separate dataclass fields for
exactly this reason).

======================================================================
ELIGIBILITY / MINIMUM-HISTORY TRADE-OFF (red-team requirement #8)
======================================================================
There is no single correct "minimum prior history" cutoff for a
walk-forward backtest, and this module does not choose one — that is a
downstream modeling decision for a human to make once this dataset
exists, not something to bake into the data layer. Instead,
`eligibility_sweep` reports, across a range of candidate thresholds k
("this target tournament must have at least k OTHER validated
tournaments strictly earlier in the corpus"), both:
  - how many target tournaments qualify at that threshold (fewer as k
    grows — the tournaments earliest in this project's 100-tournament
    corpus always have the least trailing history, structurally, no
    matter what feature is examined), and
  - the resulting quality of the retained tournaments' fields (mean/
    median per-player prior_events_n, and the fraction of field-rows
    that are still zero-history/rookie rows) — this typically improves
    as k grows, since later tournaments' fields include more players
    who by then have real prior-event history in the corpus.
This is the actual trade-off the red-team requirement asks to see
surfaced, not resolved.
"""
from __future__ import annotations

import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from klpga.backtest.historical_field import reconstruct_historical_field
from klpga.backtest.point_in_time_features import (
    Corpus,
    compute_point_in_time_features,
    features_as_flat_dict,
    load_corpus,
)
from klpga.backtest.temporal import EffectiveDate, effective_tournament_date

# A representative sweep of candidate thresholds to DISPLAY, not a
# chosen cutoff — see module docstring. Roughly log-spaced so both the
# low end (almost every tournament qualifies) and high end (only
# tournaments deep into the corpus qualify) are visible.
DEFAULT_ELIGIBILITY_THRESHOLDS = (0, 1, 2, 3, 5, 8, 10, 15, 20, 30, 40, 50)


@dataclass(frozen=True)
class TargetTournament:
    event_id: str
    game_code: str
    event_name: Optional[str]
    effective_date: date
    date_is_exact: bool
    rank: int  # 0-based position among usable targets, ascending by effective_date
    # count of OTHER usable target tournaments strictly earlier than
    # this one in the corpus — identical to `rank` by construction, but
    # named separately so eligibility_sweep's meaning is self-evident.
    prior_tournament_count: int


@dataclass
class WalkForwardDatasetResult:
    rows: list[dict] = field(default_factory=list)
    target_order: list[TargetTournament] = field(default_factory=list)
    # event_ids excluded because no resolvable effective date exists
    # (neither start_date nor end_date parsed) — never silently dropped,
    # always reported.
    skipped_no_date_event_ids: list[str] = field(default_factory=list)
    # event_ids excluded because they have zero player_event rows at
    # all (an empty reconstructed field — nothing to build a row for).
    skipped_empty_field_event_ids: list[str] = field(default_factory=list)


def _ordered_target_tournaments(conn: sqlite3.Connection) -> tuple[list[TargetTournament], list[str]]:
    raw = conn.execute(
        "SELECT event_id, game_code, event_name, start_date, end_date FROM tournament_master"
    ).fetchall()

    dated: list[tuple[str, str, Optional[str], EffectiveDate]] = []
    skipped: list[str] = []
    for event_id, game_code, event_name, start_date, end_date in raw:
        eff = effective_tournament_date(start_date, end_date)
        if eff.value is None:
            skipped.append(event_id)
            continue
        dated.append((event_id, game_code, event_name, eff))

    dated.sort(key=lambda t: t[3].value)

    ordered = [
        TargetTournament(
            event_id=event_id,
            game_code=game_code,
            event_name=event_name,
            effective_date=eff.value,
            date_is_exact=eff.is_exact,
            rank=rank,
            prior_tournament_count=rank,
        )
        for rank, (event_id, game_code, event_name, eff) in enumerate(dated)
    ]
    return ordered, skipped


def build_walk_forward_dataset(conn: sqlite3.Connection, corpus: Optional[Corpus] = None) -> WalkForwardDatasetResult:
    """Builds the full modeling/backtest dataset — one row per (target
    tournament, field member), features strictly point-in-time (see
    klpga.backtest.point_in_time_features), labels from the target
    tournament's own outcome. Pass a pre-loaded `corpus` to reuse across
    calls (e.g. from eligibility_sweep) instead of re-querying the DB."""
    if corpus is None:
        corpus = load_corpus(conn)

    target_order, skipped_no_date = _ordered_target_tournaments(conn)

    rows: list[dict] = []
    skipped_empty_field: list[str] = []
    for target in target_order:
        field_result = reconstruct_historical_field(conn, target.event_id)
        if not field_result.members:
            skipped_empty_field.append(target.event_id)
            continue

        for member in field_result.members:
            features = compute_point_in_time_features(
                corpus, target.event_id, target.effective_date, member.player_code, member.player_name
            )
            row = {
                "target_game_code": target.game_code,
                "target_event_id": target.event_id,
                "target_start_date": target.effective_date.isoformat(),
                "target_start_date_is_exact": target.date_is_exact,
                "player_code": member.player_code,
                "player_name": member.player_name,
                **features_as_flat_dict(features),
                "label_finish_position": member.label_finish_position,
                "label_finish_position_numeric": member.label_finish_position_numeric,
                "label_made_cut": member.label_made_cut,
                "label_is_winner": member.label_is_winner,
            }
            rows.append(row)

    return WalkForwardDatasetResult(
        rows=rows,
        target_order=target_order,
        skipped_no_date_event_ids=skipped_no_date,
        skipped_empty_field_event_ids=skipped_empty_field,
    )


def eligibility_sweep(
    result: WalkForwardDatasetResult,
    thresholds: tuple[int, ...] = DEFAULT_ELIGIBILITY_THRESHOLDS,
) -> list[dict]:
    """For each threshold k in `thresholds`: how many target tournaments
    have prior_tournament_count >= k, and — among that eligible set's
    field rows — the resulting distribution of prior_events_n (mean,
    median, fraction with zero prior events). See module docstring: this
    reports the trade-off, it does not pick a threshold."""
    rows_by_target: dict[str, list[dict]] = {}
    for row in result.rows:
        rows_by_target.setdefault(row["target_event_id"], []).append(row)

    report = []
    for k in thresholds:
        eligible_targets = [t for t in result.target_order if t.prior_tournament_count >= k]
        eligible_event_ids = {t.event_id for t in eligible_targets}
        eligible_rows = [
            row for event_id in eligible_event_ids for row in rows_by_target.get(event_id, [])
        ]
        prior_ns = [row["prior_events_n"] for row in eligible_rows]

        report.append(
            {
                "threshold": k,
                "eligible_tournament_count": len(eligible_targets),
                "eligible_field_row_count": len(eligible_rows),
                "mean_prior_events_n": round(statistics.mean(prior_ns), 2) if prior_ns else None,
                "median_prior_events_n": statistics.median(prior_ns) if prior_ns else None,
                "pct_zero_prior_events": (
                    round(100 * sum(1 for n in prior_ns if n == 0) / len(prior_ns), 1) if prior_ns else None
                ),
            }
        )
    return report
