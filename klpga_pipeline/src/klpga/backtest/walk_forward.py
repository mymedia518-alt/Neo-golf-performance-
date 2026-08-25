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
POPULATION DEFINITIONS (read this before comparing counts across
scripts — see docs/SITE_STRUCTURE_TODO.md section 8's "population
definitions audit" for the full write-up of a real discrepancy report
this section exists to prevent from recurring)
======================================================================
This module has exactly ONE tournament population, produced by
`build_walk_forward_dataset()` and exposed as `result.target_order` /
`result.rows`:

  USABLE target tournament = a `tournament_master` row with a
  resolvable effective date (klpga.backtest.temporal) AND a non-empty
  reconstructed field (klpga.backtest.historical_field) — i.e. NOT in
  `skipped_no_date_event_ids` or `skipped_empty_field_event_ids`. This
  is the population `scripts/21_data_coverage_report.py` reports
  UNCONDITIONALLY (it applies no history-sufficiency filter at all).

  ELIGIBLE-AT-THRESHOLD-k target tournament = a USABLE tournament that
  ALSO has `prior_tournament_count >= k` (i.e. at least k OTHER usable
  tournaments strictly earlier in the corpus — see `eligibility_sweep`
  below). This is a threshold-filtered SUBSET of "usable", reported by
  `scripts/17_eligibility_report.py` for each k in its sweep.

  At k=0 every usable tournament is trivially eligible (rank is always
  >= 0), so `eligibility_sweep(..., thresholds=(0,))` is DEFINITIONALLY
  identical to the full usable population — proven in
  `tests/test_population_definitions.py`. For k>0, "eligible" is a
  strict subset: seeing e.g. 95 eligible tournaments at threshold=5
  against 100 usable tournaments overall is the EXPECTED effect of
  excluding the 5 chronologically-earliest tournaments (each has fewer
  than 5 usable tournaments before it, structurally, regardless of any
  feature), not a bug or a second, inconsistent population — the same
  applies to the row counts, which shrink by exactly those 5
  tournaments' field sizes. Never read "N target tournaments retained"
  from one script's threshold>0 row as if it were the same number as
  another script's unconditional "usable" count — they answer different
  questions on purpose.

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
  - how many target tournaments are ELIGIBLE at that threshold (fewer
    as k grows — the tournaments earliest in this project's
    100-tournament corpus always have the least trailing history,
    structurally, no matter what feature is examined), and
  - the resulting quality of the eligible tournaments' fields (mean/
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
    # Total row count of tournament_master at build time — the "100" in
    # "percentage of the 100 historical tournaments retained" (may
    # differ from 100 on a partially-collected/test DB; always the real
    # count, never assumed).
    total_tournament_count: int = 0


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

    total_tournament_count = conn.execute("SELECT COUNT(*) FROM tournament_master").fetchone()[0]

    return WalkForwardDatasetResult(
        rows=rows,
        target_order=target_order,
        skipped_no_date_event_ids=skipped_no_date,
        skipped_empty_field_event_ids=skipped_empty_field,
        total_tournament_count=total_tournament_count,
    )


def _pct(numerator: int, denominator: int) -> Optional[float]:
    return round(100 * numerator / denominator, 1) if denominator else None


def eligibility_sweep(
    result: WalkForwardDatasetResult,
    thresholds: tuple[int, ...] = DEFAULT_ELIGIBILITY_THRESHOLDS,
) -> list[dict]:
    """For each threshold k in `thresholds`: how many target tournaments
    have prior_tournament_count >= k, and — among that eligible set's
    field rows — the resulting distribution of prior_events_n (mean,
    median, and the fraction with fewer than 5/10/20/zero prior events).
    See module docstring: this reports the trade-off, it does not pick
    a threshold."""
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
        # eligible_targets is a suffix of the ascending target_order (see
        # _ordered_target_tournaments — filtering rank >= k on a list
        # already sorted by rank simply drops the first k entries), so
        # its first element is always the earliest-dated eligible target.
        earliest = eligible_targets[0] if eligible_targets else None

        report.append(
            {
                "threshold": k,
                "eligible_tournament_count": len(eligible_targets),
                "pct_of_corpus_retained": _pct(len(eligible_targets), result.total_tournament_count),
                "eligible_field_row_count": len(eligible_rows),
                "earliest_eligible_target_event_id": earliest.event_id if earliest else None,
                "earliest_eligible_target_game_code": earliest.game_code if earliest else None,
                "earliest_eligible_target_start_date": earliest.effective_date.isoformat() if earliest else None,
                "mean_prior_events_n": round(statistics.mean(prior_ns), 2) if prior_ns else None,
                "median_prior_events_n": statistics.median(prior_ns) if prior_ns else None,
                "pct_zero_prior_events": _pct(sum(1 for n in prior_ns if n == 0), len(prior_ns)),
                "pct_lt_5_prior_events": _pct(sum(1 for n in prior_ns if n < 5), len(prior_ns)),
                "pct_lt_10_prior_events": _pct(sum(1 for n in prior_ns if n < 10), len(prior_ns)),
                "pct_lt_20_prior_events": _pct(sum(1 for n in prior_ns if n < 20), len(prior_ns)),
            }
        )
    return report
