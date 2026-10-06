"""NEO HJ 2026 (gameCode 2026100004) blind backtest harness -- NOT RUNNABLE
YET. Status: BLOCKED. See HJ_2026100004_STABLEFORD_GAP.md.

Required (per the explicit build instruction, step 5):
  1. The past modified-Stableford tournament's actual results (scored with
     the SAME official point table in stableford_scoring.py) -- which
     tournament, which year, is not yet identified; "과거 이 대회" was
     named but no gameCode/year/results were relayed this turn.
  2. Each entrant's REAL performance record as it stood immediately BEFORE
     that past tournament (no data from on/after its start date) -- the
     same mainRecord-level data (per-tournament, per-hole-type finish
     rates) that has been unavailable for the entire session on this
     branch and the sibling point-seed branch alike.
  3. The past course was 익산CC (Iksan CC), explicitly NOT 에이원CC (A-One
     CC, 2026's course) -- course-effect data for Iksan CC (green speed,
     rough length, hole difficulty by par type) would be needed to
     separate "this player is generally Stableford-strong" from "this
     player suited Iksan CC specifically", and none of that has been
     relayed either.

Running this with invented results or invented "prior" player stats would
make a backtest that always appears to validate -- worse than having no
backtest at all, since it would look like evidence. The guard below
refuses unconditionally until real data is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


class BacktestBlockedError(RuntimeError):
    """Raised unconditionally until real historical Stableford results and
    real pre-cutoff player records are supplied -- see module docstring."""


@dataclass(frozen=True)
class BacktestInputs:
    past_game_code: str
    past_tournament_date: date
    past_course_name: str
    past_results: list  # real per-player, per-hole Stableford results
    pre_cutoff_player_records: list  # real player stats as of strictly before past_tournament_date
    confirm_real_data: bool = False


def run_blind_backtest(inputs: BacktestInputs):
    """Re-predicts the past tournament using ONLY pre_cutoff_player_records
    (nothing dated on/after past_tournament_date), scores the prediction
    against past_results (both via stableford_scoring.py's official point
    table), and reports calibration. Refuses to run -- see guard below --
    until real data replaces every placeholder field."""
    problems = []
    if not inputs.confirm_real_data:
        problems.append("confirm_real_data=False -- explicit confirmation required")
    if not inputs.past_results:
        problems.append("past_results is empty -- no real historical Stableford results supplied")
    if not inputs.pre_cutoff_player_records:
        problems.append("pre_cutoff_player_records is empty -- no real pre-tournament player data supplied")
    if inputs.past_course_name.strip().lower() in ("", "unknown", "익산cc", "iksan cc") and not inputs.past_results:
        problems.append("past course identified as 익산CC but no course-effect data to isolate it from 에이원CC (2026)")
    if problems:
        raise BacktestBlockedError(
            "REFUSING TO RUN BACKTEST -- " + "; ".join(problems)
            + ". See HJ_2026100004_STABLEFORD_GAP.md for what's needed."
        )
    raise NotImplementedError(
        "Guard passed (this should not happen without real data) -- the actual "
        "re-prediction/scoring/calibration logic is not implemented because it "
        "has never had real data to be implemented against. Implement this "
        "function body only once BacktestInputs carries real data."
    )
