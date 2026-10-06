"""NEO HJ 2026 (gameCode 2026100004) Stableford Monte Carlo -- NOT RUNNABLE
YET. Status: BLOCKED, and gated behind stableford_backtest passing first
(per the explicit build instruction: "검증 PASS 후에만 실행").

Required, none of which has been obtained this turn:
  1. The full official entry list for 2026100004 (field size, pairings) --
     not relayed; only tournament-level facts (dates/course/purse/scoring
     table) were given.
  2. Per-player Eagle/Birdie/Par/Bogey/Double+ rates for the current
     season, ideally split by par-3/par-4/par-5, plus recent-5/recent-10
     trend -- this is mainRecord-level granularity that has never been
     available on this branch or klpga-tournament-data-collection-k47i28.
  3. A PASSED stableford_backtest run (see that module) establishing the
     outcome-rate -> Stableford-points model is calibrated at all, before
     spending any simulation budget on it.
  4. The remaining 13 (of 18) holes' par/yardage for 에이원CC -- only
     course-level totals and 5 named key holes were relayed (see
     2026100004_TOURNAMENT_INFO.json's explicit note).

Guard below refuses unconditionally -- there is no "signal that it's safe
to run" interpretation of the data gap above.
"""
from __future__ import annotations

from dataclasses import dataclass


class MonteCarloBlockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class MonteCarloInputs:
    entry_list: list            # real, official 2026100004 field
    player_outcome_rates: dict  # real per-player Eagle/Birdie/Par/Bogey/Double+ rates
    course_hole_table: list     # real 18-hole (hole, par, yardage) for 에이원CC
    backtest_passed: bool = False
    n_iterations: int = 60_000
    confirm_real_data: bool = False


MIN_FIELD_SIZE = 90  # a real KLPGA field is ~100-120; a handful of rows is not a field


def run_monte_carlo(inputs: MonteCarloInputs):
    problems = []
    if not inputs.confirm_real_data:
        problems.append("confirm_real_data=False")
    if len(inputs.entry_list) < MIN_FIELD_SIZE:
        problems.append(
            f"entry_list has {len(inputs.entry_list)} players -- need >= {MIN_FIELD_SIZE} "
            "for a real field (official 2026100004 entry list not yet obtained)"
        )
    if len(inputs.player_outcome_rates) < MIN_FIELD_SIZE:
        problems.append(
            f"player_outcome_rates covers {len(inputs.player_outcome_rates)} players -- "
            "per-player Eagle/Birdie/Par/Bogey/Double+ rates not yet obtained for the field"
        )
    if len(inputs.course_hole_table) != 18:
        problems.append(
            f"course_hole_table has {len(inputs.course_hole_table)} holes, need 18 -- "
            "only aggregate par/yardage + 5 named key holes relayed so far, not the full table"
        )
    if not inputs.backtest_passed:
        problems.append("backtest_passed=False -- 검증 PASS 후에만 실행, per explicit instruction")
    if inputs.n_iterations < 60_000:
        problems.append(f"n_iterations={inputs.n_iterations} < required minimum 60,000")
    if problems:
        raise MonteCarloBlockedError(
            "REFUSING TO RUN MONTE CARLO -- " + "; ".join(problems)
            + ". See HJ_2026100004_STABLEFORD_GAP.md for what's needed."
        )
    raise NotImplementedError(
        "Guard passed (unexpected without real data) -- field-draw / cut-line / "
        "R1->R2->CUT->R3->FR simulation logic is not implemented because it has "
        "never had real inputs to implement against."
    )
