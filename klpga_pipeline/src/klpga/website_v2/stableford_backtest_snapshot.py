"""Pre-event blind backtest TEMPORAL SNAPSHOT builder (HJ 2026100004
gap, continued 2026-10-06, steps 1-2 of the pre-event backtest task).

Builds, for one historical Stableford event, a per-player snapshot
using ONLY information available strictly before that event's own
real start date (klpga.website_v2.stableford_historical_dates) --
never same-event or post-event information.

======================================================================
WHAT REAL PRE-EVENT DATA THIS PROJECT ACTUALLY HAS (investigated this
turn, not assumed) -- see each field's own comment for exactly which
real file backs it:
======================================================================

  FIELD IDENTITY (who is in the 108-player field): 108/108/108 for all
  3 events -- real, from each event's own scoreRecord 1R table NAME
  column only (klpga.collectors.score_record.extract_hole_outcomes).
  Pulling a player's NAME from the event's own page is not a leakage
  violation by itself -- entry lists are genuinely knowable before day
  1 -- but no SCORE/outcome field from that same row is ever read here.

  SEASON-TO-DATE STROKES GAINED (prior_sg_total / 4 components): a
  REAL per-player, per-tournament warehouse exists --
  klpga_pipeline/content/website_v2/historical_sg_warehouse_corrected_v2
  .json (46,192 records, 108 distinct tournaments, seasons 2023-2026,
  scraped from the official klpga.co.kr Strokes Gained detail page +
  round leaderboard, each row self-validated against a computed total
  within tolerance). None of the 3 exact target gameCodes appear in it
  (confirmed by direct lookup), but every OTHER same-season tournament
  strictly in an EARLIER CALENDAR MONTH does. Coverage (tournament_
  cumulative rows, month < 10, name-string match only -- see below):
    2023100002: 102/108 players (94.4%), median 21 prior tournaments
    2024100009: 105/108 players (97.2%), median 21 prior tournaments
    2025100001: 103/108 players (95.4%), median 22 prior tournaments
  CAVEAT (disclosed, not hidden): this warehouse has no exact calendar
  DATE per record, only a game_code encoding (season, month). This
  module's leakage rule is therefore CONSERVATIVE AT MONTH GRANULARITY:
  a record counts as "prior" only if its game_code's month is strictly
  less than the target event's own month (October, month=10 for all 3
  events) -- any same-month-as-target record (there are some in this
  warehouse) is EXCLUDED entirely, even though some of those same-
  October tournaments may genuinely have happened earlier in the month
  than the target -- this project cannot prove that without an exact
  date, so it is conservatively discarded rather than risked. The
  handful of uncovered players (5-6 per event) are disambiguated/
  foreign-format names (e.g. "이정민2", "리 슈잉(I)", "박조은 0806(A)")
  that likely DO have real warehouse rows under a slightly different
  name string -- true coverage is probably somewhat higher than the
  name-string-match numbers above, but this module does not attempt a
  fuzzy match, so it reports the conservative (possibly undercounted)
  figure rather than guessing a correction.

  PER-HOLE OUTCOME RATES (birdie/eagle/par/bogey/double-or-worse rate
  -- the exact inputs klpga.website_v2.stableford_player_value's
  official formula needs): ZERO real pre-event coverage found anywhere
  in this repo or session. klpga_pipeline/data/klpga.sqlite's
  player_round table HAS birdies/eagles/pars/bogeys/double_bogey_plus
  COLUMNS (the schema already anticipated this need) but 0 ROWS --
  confirmed directly via sqlite3. The SG warehouse above has no
  birdie-count field at all (it is Strokes Gained, not outcome
  counts). The k-ranking snapshots (historical_kranking_snapshots_v1)
  are rank/points only. The r1-groupings evidence
  (historical_r1_groupings_blocker_resolution_v1) is tee-time pairing
  only, no scores at all, and doesn't even cover these 3 gameCodes'
  neighbors precisely. This is the single most important real gap:
  klpga.website_v2.stableford_player_value.from_season_rates cannot be
  run on any real player for any of these 3 events with real pre-event
  rates -- there is nothing to feed it.

  COURSE/HISTORY INFORMATION: not attempted this turn -- see
  klpga.website_v2.stableford_backtest's module docstring and this
  module's own course_constraint note: 2023-2025 were at Iksan CC,
  2026 is at A-One CC, so even if Iksan-specific course history
  existed, it must never be transplanted to A-One per explicit
  instruction. Out of scope for the 2023-2025 historical validation
  itself (which only needs each YEAR's own course, not A-One).

  SG COMPONENTS: see above -- real, 94-97% coverage, timestamp-safe at
  month granularity.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from klpga.website_v2.stableford_historical_dates import HISTORICAL_EVENT_DATES

SG_WAREHOUSE_PATH = (
    Path(__file__).resolve().parents[3]  # .../klpga_pipeline
    / "content" / "website_v2" / "historical_sg_warehouse_corrected_v2.json"
)


@dataclass(frozen=True)
class PlayerSnapshot:
    player_name: str
    prior_tournament_count: int
    prior_game_codes: tuple[str, ...]  # sorted, informational -- not a feature itself
    prior_sg_total_mean: float | None
    prior_sg_tee_to_green_mean: float | None
    prior_sg_off_the_tee_mean: float | None
    prior_sg_approach_mean: float | None
    prior_sg_around_green_mean: float | None
    prior_sg_putting_mean: float | None
    # Explicitly None, never fabricated -- see module docstring. A
    # future real source must populate these before
    # stableford_player_value can be run on real players.
    birdie_rate: None = None
    eagle_rate: None = None
    par_rate: None = None
    bogey_rate: None = None
    double_or_worse_rate: None = None


@dataclass(frozen=True)
class EventSnapshot:
    game_code: str
    event_start_date: str  # ISO date, informational
    field_size: int
    players: dict[str, PlayerSnapshot] = field(default_factory=dict)
    leakage_assertions_passed: bool = False


def _load_sg_records() -> list[dict]:
    return json.loads(SG_WAREHOUSE_PATH.read_text(encoding="utf-8"))["records"]


def assert_no_leakage(game_codes: list[str], target_season: int, target_month: int) -> None:
    """Fails loudly if any source game_code is NOT strictly before the
    target's (season, month) -- the automated leakage assertion the
    task requires. Month granularity, see module docstring for why."""
    for gc in game_codes:
        season = int(gc[:4])
        month = int(gc[4:6])
        if season > target_season or (season == target_season and month >= target_month):
            raise AssertionError(
                f"LEAKAGE: source game_code {gc!r} (season={season}, month={month}) "
                f"is not strictly before target (season={target_season}, month={target_month})"
            )


def build_event_snapshot(game_code: str, field_names: set[str]) -> EventSnapshot:
    """field_names: the real 108-player field, from extract_hole_outcomes's
    1R table NAME column only (caller's responsibility to have sourced
    it that way -- this function does not read scores)."""
    event_dates = HISTORICAL_EVENT_DATES[game_code]
    target_season = event_dates.event_start_date.year
    target_month = event_dates.event_start_date.month

    records = _load_sg_records()
    by_player: dict[str, list[dict]] = {}
    for r in records:
        if r["season"] != target_season or r["scope"] != "tournament_cumulative":
            continue
        gc = r["game_code"]
        if int(gc[4:6]) >= target_month:
            continue  # same-month-or-later: conservatively excluded, see module docstring
        by_player.setdefault(r["player"], []).append(r)

    all_used_game_codes = sorted({r["game_code"] for rows in by_player.values() for r in rows})
    assert_no_leakage(all_used_game_codes, target_season, target_month)

    players: dict[str, PlayerSnapshot] = {}
    for name in sorted(field_names):
        rows = by_player.get(name, [])
        if not rows:
            players[name] = PlayerSnapshot(
                player_name=name, prior_tournament_count=0, prior_game_codes=(),
                prior_sg_total_mean=None, prior_sg_tee_to_green_mean=None,
                prior_sg_off_the_tee_mean=None, prior_sg_approach_mean=None,
                prior_sg_around_green_mean=None, prior_sg_putting_mean=None,
            )
            continue

        def _mean(key: str) -> float:
            return round(sum(r[key] for r in rows) / len(rows), 3)

        players[name] = PlayerSnapshot(
            player_name=name,
            prior_tournament_count=len(rows),
            prior_game_codes=tuple(sorted(r["game_code"] for r in rows)),
            prior_sg_total_mean=_mean("total"),
            prior_sg_tee_to_green_mean=_mean("tee_to_green"),
            prior_sg_off_the_tee_mean=_mean("off_the_tee"),
            prior_sg_approach_mean=_mean("approach"),
            prior_sg_around_green_mean=_mean("around_green"),
            prior_sg_putting_mean=_mean("putting"),
        )

    return EventSnapshot(
        game_code=game_code,
        event_start_date=event_dates.event_start_date.isoformat(),
        field_size=len(field_names),
        players=players,
        leakage_assertions_passed=True,  # reached only if assert_no_leakage above didn't raise
    )
