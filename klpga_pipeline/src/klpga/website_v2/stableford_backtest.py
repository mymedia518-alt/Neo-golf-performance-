"""NEO HJ 2026 (gameCode 2026100004) blind backtest harness -- STILL NOT
RUNNABLE, but tournament identification is now RESOLVED. See
HJ_2026100004_STABLEFORD_GAP.md for the full, current blocker inventory.

RESOLVED this turn (OBSERVED, user relay, KLPGA 공식 역대기록 + 대회 공식
홈페이지 -- Claude's network still cannot independently fetch klpga.co.kr,
confirmed blocked again):
  "과거 이 대회" IS this tournament's own history under an earlier sponsor
  name. This repo's own earlier, independently-confirmed engineering work
  (docs/SITE_STRUCTURE_TODO.md section 1, 2026-08-24 live 100-tournament
  run) already names gameMethod="2" ("Modified Stableford") KLPGA
  tournaments called "동부건설 · 한국토지신탁 챔피언십" at gameCodes
  2023100002, 2024100009, 2025100001 -- matching the user-relayed 2023/
  2024/2025 winners below by year. 2021/2022 gameCodes were not in that
  particular 100-tournament sample (not confirmed as absent -- just not
  observed yet).

    2021  이정민  +51              (26 birdies)
    2022  이가영  +49
    2023  방신실  +43  10/5/15/13  (21 birdies + 1 eagle)
    2024  김민별  +49  13/8/10/18  (26 birdies)
    2025  김민솔  +51  7/14/14/16  (27 birdies)

  All five self-consistent (each round split sums to the reported total;
  checked programmatically, see test_stableford_2026100004.py). These are
  WINNER-ONLY summary statistics across 5 events -- a useful sanity-check
  range for what a winning score/round-split looks like, and nothing more.
  Per explicit instruction: these are validation observations only, never
  fit-to constants. The 60-year-old statistical trap this guards against:
  5 winners is an extreme survivorship-biased sample (no 2nd-108th place
  data at all) -- any model "calibrated" to hit these 5 numbers would
  almost certainly be overfit to noise, not a real fit.

STILL BLOCKED, and this is the load-bearing one:
  Full-field, per-player historical records for these 5 events (or any
  real per-round hole-level data for ANY Modified Stableford tournament)
  cannot currently be collected even with full site access, independent
  of Claude's network block. This repo's own roundLeaderboard collector
  was live-confirmed (2026-08-24, real Windows-PC run against the actual
  endpoint, round=1..8 exhaustively probed) to return ZERO player rows
  for all 3 of the above gameMethod="2" gameCodes -- a genuine upstream
  API limitation of the endpoint this pipeline uses, not a reachability
  problem. A different KLPGA endpoint that DOES serve Modified Stableford
  results (if one exists) has not been identified. See
  HJ_2026100004_STABLEFORD_GAP.md section "다음 단계" for exactly this.
  Local klpga_pipeline/data/klpga.sqlite was checked this turn and holds
  zero tournament_master/player_event/player_round rows -- confirmed
  empty (every collection_runs attempt failed on the same proxy block).

  2021/2022 course (익산CC) effect data: also not obtained -- needed to
  separate "player is Stableford-strong in general" from "player suited
  Iksan CC specifically", per explicit instruction not to transfer it to
  에이원CC (2026's course).

Reuses klpga.backtest.temporal (this repo's existing, model-free,
format-agnostic point-in-time date-ordering utility -- NOT the stroke-play
win-probability model itself, so this does not violate the Red Team
no-stroke-play-model-reuse check) for the one piece of real leakage logic
that COULD be implemented without new data: given any player record with
a date, is_strictly_before() enforces it cannot be on/after the target
tournament's date. Running the backtest end-to-end is still refused below
until the full-field data problem above is solved.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # .../klpga_pipeline/src
from klpga.backtest.temporal import is_strictly_before  # noqa: E402


class BacktestBlockedError(RuntimeError):
    """Raised unconditionally until real full-field historical Stableford
    results and real pre-cutoff player records are supplied -- see module
    docstring. Winner-only summary stats do not satisfy this."""


# OBSERVED, user relay, validation-only -- never fit model constants to these.
KNOWN_HISTORICAL_WINNER_SUMMARIES = [
    {"year": 2021, "game_code": None, "winner": "이정민", "total_points": 51, "rounds": None, "birdies": 26},
    {"year": 2022, "game_code": None, "winner": "이가영", "total_points": 49, "rounds": None, "birdies": None},
    {"year": 2023, "game_code": "2023100002", "winner": "방신실", "total_points": 43,
     "rounds": [10, 5, 15, 13], "birdies": 21, "eagles": 1},
    {"year": 2024, "game_code": "2024100009", "winner": "김민별", "total_points": 49,
     "rounds": [13, 8, 10, 18], "birdies": 26},
    {"year": 2025, "game_code": "2025100001", "winner": "김민솔", "total_points": 51,
     "rounds": [7, 14, 14, 16], "birdies": 27},
]


@dataclass(frozen=True)
class PlayerRecord:
    player_code: str
    record_date: date  # when this stat was true as-of -- must predate the target tournament
    stats: dict


@dataclass(frozen=True)
class BacktestInputs:
    past_game_code: str
    past_tournament_date: date
    past_course_name: str
    past_results: list  # real per-player, per-hole Stableford results (full field, not just the winner)
    pre_cutoff_player_records: list[PlayerRecord]  # real player stats, each with its own record_date
    confirm_real_data: bool = False


def _leaked_records(inputs: BacktestInputs) -> list[PlayerRecord]:
    """Real check (not a stub): any record whose date is NOT strictly
    before the target tournament's date is leakage, full stop."""
    return [
        r for r in inputs.pre_cutoff_player_records
        if not is_strictly_before(r.record_date, inputs.past_tournament_date)
    ]


MIN_FIELD_SIZE = 90  # mirrors stableford_monte_carlo.py -- a handful of rows isn't a field


def run_blind_backtest(inputs: BacktestInputs):
    """Re-predicts the past tournament using ONLY pre_cutoff_player_records
    (temporally enforced via is_strictly_before, not just assumed), scores
    the prediction against past_results (both via stableford_scoring.py's
    official point table), and reports calibration. Refuses to run -- see
    guard below -- until the full-field data problem is solved."""
    problems = []
    if not inputs.confirm_real_data:
        problems.append("confirm_real_data=False -- explicit confirmation required")
    if len(inputs.past_results) < MIN_FIELD_SIZE:
        problems.append(
            f"past_results has {len(inputs.past_results)} rows, need >= {MIN_FIELD_SIZE} -- "
            "winner-only summary stats (KNOWN_HISTORICAL_WINNER_SUMMARIES) are not a full-field result set"
        )
    if len(inputs.pre_cutoff_player_records) < MIN_FIELD_SIZE:
        problems.append(
            f"pre_cutoff_player_records has {len(inputs.pre_cutoff_player_records)} rows, "
            f"need >= {MIN_FIELD_SIZE} -- no real pre-tournament full-field player data supplied"
        )
    leaks = _leaked_records(inputs)
    if leaks:
        problems.append(
            f"{len(leaks)} player record(s) dated on/after {inputs.past_tournament_date} "
            "-- future-data leakage, refusing regardless of other inputs"
        )
    if problems:
        raise BacktestBlockedError(
            "REFUSING TO RUN BACKTEST -- " + "; ".join(problems)
            + ". See HJ_2026100004_STABLEFORD_GAP.md for what's needed."
        )
    raise NotImplementedError(
        "Guard passed (this should not happen without real full-field data) -- the "
        "actual re-prediction/scoring/calibration logic is not implemented because "
        "it has never had real data to be implemented against."
    )
