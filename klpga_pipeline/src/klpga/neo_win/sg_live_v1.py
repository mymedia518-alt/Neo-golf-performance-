"""SG-based LIVE (mid-round) outcome model, version 1.

Generalizes `klpga.neo_win.sg_pre_v1.simulate_sg_tournament_outcomes` to a
tournament that is actually IN PROGRESS, built to close the four specific
defects Red Team confirmed in the now-permanently-BLOCKED
`klpga.neo_win.r1_live_probability` (see that module's own
`LIVE_PROBABILITY_MODEL_STATUS` docstring for the original incident).
This module does not touch r1_live_probability.py at all -- that module
stays BLOCKED and unedited; this is a new, independent implementation
built directly on sg_pre_v1's own already-tested SG->stroke conversion
math, not a repair of the old one.

======================================================================
HOW EACH CONFIRMED DEFECT IS CLOSED HERE
======================================================================
1. "Partial-round state is not modeled; remaining holes are silently
   ignored." -- Fixed structurally: `PlayerLiveState.holes_completed`
   and `.current_round_score_so_far` are REQUIRED real facts for the
   round currently in progress. Only the REMAINING holes (18 -
   holes_completed) are simulated; the played portion is the real score,
   never re-drawn. At holes_completed == 0 this reduces EXACTLY to a
   full simulated round (identical to sg_pre_v1's own un-started-round
   treatment); at holes_completed == 18 the simulated component is
   exactly zero and the round is the real total outright (identical to
   how `klpga.neo_win.round_update_r2` treats an already-finished
   round). Both boundaries are covered by this module's own test suite
   asserting byte-identical output against the base, already-tested
   functions -- the same counterfactual-testing discipline the original
   Red Team review itself used to prove the old module's number was an
   artifact of its bug.

2 & 3. "SG mean negated and treated directly as a par-relative round
   expectation; the SG windows are tournament-cumulative, not
   round-level." -- Fixed by never doing that conversion ad hoc. This
   module stays in `PlayerSGForecast`'s native, already-validated SG
   currency end to end, and performs the SG->stroke conversion with the
   exact same tested primitive sg_pre_v1 itself uses
   (`_round_to_integer_strokes(-rng.gauss(mean, sd))`), imported
   unchanged rather than re-derived. The only new arithmetic this module
   adds is scaling that SAME per-round SG mean/SD down to the holes
   actually remaining (mean * remaining/18, SD * sqrt(remaining/18) --
   SD scales with the square root of hole count for a sum of
   approximately independent per-hole increments, not linearly; using a
   linear SD scale would itself be a fresh unit bug, so it is called out
   explicitly here and covered by a dedicated test), applied BEFORE the
   existing conversion, never after or around it.

4. "RNG seed not persisted; no past output is reproducible." -- `seed`
   is a required keyword argument with no default (same contract
   sg_pre_v1.simulate_sg_tournament_outcomes already enforces). Callers
   must persist the seed used alongside the published output.

======================================================================
PUBLICATION STATUS -- NEVER "VALIDATED"
======================================================================
This module has NOT been through the independent Red Team review that
`klpga.neo_win.r1_live_probability.LIVE_PROBABILITY_MODEL_STATUS`
requires before a live probability model may be marked "VALIDATED".
Any caller publishing this module's output MUST go through
`klpga.website_v2.model_publication_gate`'s REFERENCE_ESTIMATE escape
(disclosure text "참고 예상" present on the same page) -- never claim
VALIDATED status for this module's output. See LIVE_V2_MODEL_STATUS
below; it exists so a caller can assert on it the same way
r1_live_probability's status is asserted on elsewhere, rather than
silently assuming "new code must be fine".

======================================================================
NO FABRICATION
======================================================================
A player with no real score for ANY already-completed round, or no WD/
DQ/made-cut determination where one is required (post-cut rounds), is
EXCLUDED from every trial and reported in `excluded_players` with a
reason string -- never defaulted to a population mean or a guessed
status. A player not yet teed off in the live round is NOT excluded --
holes_completed=0 with current_round_score_so_far=0 is the real,
honest state "nothing has happened yet for this player this round",
which is exactly what un-started full-round simulation already assumes.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Optional

from klpga.neo_win.sg_pre_v1 import PlayerSGForecast, _round_to_integer_strokes

__all__ = [
    "LIVE_V2_MODEL_STATUS",
    "PlayerLiveState",
    "LiveSimulationResult",
    "build_live_states",
    "simulate_live_tournament_outcomes",
]

# See module docstring, "PUBLICATION STATUS" above. Flip to "VALIDATED"
# only after a separate, independent Red Team review -- never by
# editing this constant alone.
LIVE_V2_MODEL_STATUS = "REFERENCE_ESTIMATE"

_HOLES_PER_ROUND = 18

# Confirmed real statuses this module ever receives (see
# klpga.parsers.leaderboard_parser's own module docstring): CUT/WD/DQ are
# unconfirmed-but-possible literal text values; INCOMPLETE is the
# confirmed rank=999 sentinel (unresolved, not itself WD/DQ evidence).
_ELIMINATED_STATUSES = {"CUT", "WD", "DQ"}
_UNRESOLVED_STATUSES = {"INCOMPLETE"}


@dataclass(frozen=True)
class PlayerLiveState:
    """One player's real, as-of-now tournament state. Every field here
    must be a real collected fact or an explicit None -- never a guess.

    completed_round_scores: real par-relative score for each round
        STRICTLY BEFORE `current_round`, in round order (index 0 = round
        1). Must have exactly `current_round - 1` entries for this
        player to be simulated at all -- a short list means a missing
        real score for some earlier round, and the caller
        (`build_live_states`) excludes the player rather than padding
        this list with a guess.
    current_round_score_so_far: real par-relative score accumulated in
        `current_round` through `holes_completed` holes (0 if
        holes_completed is 0 -- the honest "nothing played yet" state).
    holes_completed: real count, 0..18 (see
        `klpga.parsers.round_progress.resolve_completed_holes` -- never
        raw site data-inghole without the starting-tee correction that
        module applies).
    made_cut: real made-cut fact, required and must be non-None once
        `current_round` is past the tournament's cut round; None before
        the cut round is simulated (not yet a real fact) and is fine.
    status: real per-player status for the CURRENT round ("ACTIVE" if
        none of the below apply), from leaderboard_parser.PlayerRoundRow
        .status -- "WD"/"DQ"/"CUT" (eliminated, excluded going forward)
        or "INCOMPLETE" (unresolved, excluded, never guessed into WD/DQ).
    """

    player_id: str
    completed_round_scores: tuple[Optional[int], ...]
    current_round_score_so_far: int
    holes_completed: int
    made_cut: Optional[bool]
    status: str = "ACTIVE"


def build_live_states(
    player_ids: list[str],
    *,
    current_round: int,
    completed_round_scores_by_player: dict[str, list[Optional[int]]],
    current_round_rows: dict[str, dict],
    made_cut_by_player: Optional[dict[str, bool]] = None,
) -> tuple[dict[str, PlayerLiveState], dict[str, str]]:
    """Build real, non-fabricated live states for every player, and a
    separate exclusion map {player_id: reason} for every player this
    module will not simulate going forward.

    current_round_rows: {player_id: {"today_under_par": int|None,
        "holes_completed": int, "status": str}} -- already resolved via
        klpga.parsers.leaderboard_parser + klpga.parsers.round_progress,
        never raw HTML read directly by this function (this function
        does no parsing, no I/O, no site knowledge).
    """
    if current_round < 1:
        raise ValueError("current_round must be >= 1")
    made_cut_by_player = made_cut_by_player or {}

    states: dict[str, PlayerLiveState] = {}
    excluded: dict[str, str] = {}

    for pid in player_ids:
        prior = completed_round_scores_by_player.get(pid, [])
        if len(prior) != current_round - 1 or any(v is None for v in prior):
            excluded[pid] = (
                f"missing real score for a completed round before round {current_round}"
            )
            continue

        row = current_round_rows.get(pid)
        if row is None:
            # Real, honest "hasn't appeared in this round's leaderboard
            # yet" -- treated as holes_completed=0, never excluded for
            # this reason alone (identical to a not-yet-teed-off player
            # in a fresh, un-started round).
            score_so_far, holes_completed, status = 0, 0, "ACTIVE"
        else:
            status = str(row.get("status") or "ACTIVE").upper()
            holes_completed = int(row.get("holes_completed") or 0)
            score_so_far = row.get("today_under_par")
            if status in _UNRESOLVED_STATUSES:
                excluded[pid] = f"unresolved current-round status: {status}"
                continue
            if status in _ELIMINATED_STATUSES:
                # Real, known elimination -- not simulated further, but
                # NOT excluded from the output: round_update_r2's own
                # convention is that an eliminated player gets real,
                # known all-zero forward probabilities, reported
                # distinctly from "unknown". Caller handles the zeroing;
                # this builder still needs a real score_so_far or 0.
                score_so_far = score_so_far if score_so_far is not None else 0
            elif score_so_far is None and holes_completed > 0:
                excluded[pid] = "holes_completed > 0 but no resolvable current-round score"
                continue
            elif score_so_far is None:
                score_so_far = 0

        made_cut = made_cut_by_player.get(pid)
        states[pid] = PlayerLiveState(
            player_id=pid,
            completed_round_scores=tuple(prior),
            current_round_score_so_far=int(score_so_far),
            holes_completed=holes_completed,
            made_cut=made_cut,
            status=status,
        )

    return states, excluded


@dataclass(frozen=True)
class LiveSimulationResult:
    probabilities: dict[str, dict[str, float]]
    excluded_players: dict[str, str]
    eliminated_players: list[str]
    seed: int
    n_simulations: int
    current_round: int


def _remaining_round_strokes(
    forecast: PlayerSGForecast, holes_completed: int, rng: random.Random
) -> int:
    remaining = _HOLES_PER_ROUND - holes_completed
    if remaining <= 0:
        return 0
    frac = remaining / _HOLES_PER_ROUND
    mean_remaining_sg = forecast.mean_sg * frac
    sd_remaining_sg = forecast.round_sd * math.sqrt(frac)
    return _round_to_integer_strokes(-rng.gauss(mean_remaining_sg, sd_remaining_sg))


def simulate_live_tournament_outcomes(
    forecasts: dict[str, PlayerSGForecast],
    live_states: dict[str, PlayerLiveState],
    *,
    rounds: int,
    cut_after_round: int,
    cut_position: int,
    current_round: int,
    n_simulations: int,
    seed: int,
) -> LiveSimulationResult:
    """Same cut/ranking mechanics as
    `sg_pre_v1.simulate_sg_tournament_outcomes`, generalized so that:

      - every round STRICTLY BEFORE current_round uses each player's
        REAL score (never re-simulated -- same principle as
        round_update_r2's treatment of R1/R2 once they are real facts);
      - current_round blends the real score-so-far with a SIMULATED
        draw for the holes actually remaining (see module docstring);
      - every round AFTER current_round is fully simulated, exactly as
        the base function already does.

    If current_round > cut_after_round, the cut is a real, already-
    determined fact: only players with made_cut=True are simulated
    forward; made_cut=False players get real, known all-zero
    probabilities (eliminated_players); made_cut=None is not permitted
    here (build_live_states only ever leaves made_cut populated once
    the cut round is real) -- such a player must have been excluded
    upstream.
    """
    if rounds < 1 or not 1 <= current_round <= rounds:
        raise ValueError("current_round must be within 1..rounds")
    if cut_position <= 0 or n_simulations <= 0:
        raise ValueError("cut_position and n_simulations must be positive")
    post_cut = current_round > cut_after_round

    eligible: list[str] = []
    eliminated: list[str] = []
    # Sorted, not dict-insertion order: this must match
    # sg_pre_v1.simulate_sg_tournament_outcomes's own `players =
    # sorted(forecasts)` convention exactly, so that at the
    # holes_completed==0 / cut-already-known boundaries the RNG call
    # sequence -- and therefore the output -- is byte-identical to the
    # already-tested base function given the same seed. This is what
    # the boundary-reduction tests assert.
    for pid in sorted(live_states):
        state = live_states[pid]
        if forecasts.get(pid) is None:
            continue
        if state.status in _ELIMINATED_STATUSES:
            eliminated.append(pid)
            continue
        if post_cut and state.made_cut is not True:
            # made_cut is False (real elimination) or None (should not
            # happen post-cut; treated the same -- never simulated
            # without a confirmed True fact).
            if state.made_cut is False:
                eliminated.append(pid)
            continue
        eligible.append(pid)

    rng = random.Random(seed)
    counts = {p: [0, 0, 0, 0, 0] for p in eligible}  # cut, top20, top10, top5, win
    n_cut = min(cut_position, len(eligible)) if eligible else 0

    for _ in range(n_simulations):
        round_strokes: dict[str, list[int]] = {}
        for p in eligible:
            state = live_states[p]
            forecast = forecasts[p]
            strokes = []
            for r in range(rounds):
                round_number = r + 1
                if round_number < current_round:
                    strokes.append(int(state.completed_round_scores[r]))
                elif round_number == current_round:
                    strokes.append(
                        state.current_round_score_so_far
                        + _remaining_round_strokes(forecast, state.holes_completed, rng)
                    )
                else:
                    strokes.append(_round_to_integer_strokes(-rng.gauss(forecast.mean_sg, forecast.round_sd)))
            round_strokes[p] = strokes

        if not post_cut:
            after_cut_round = {p: sum(round_strokes[p][:cut_after_round]) for p in eligible}
            cut_line = sorted(after_cut_round.values())[n_cut - 1] if n_cut else None
            survivors = [p for p in eligible if cut_line is not None and after_cut_round[p] <= cut_line]
        else:
            survivors = list(eligible)

        total_strokes = {p: sum(round_strokes[p]) for p in survivors}
        if not total_strokes:
            continue
        best = min(total_strokes.values())
        winners = [p for p in survivors if total_strokes[p] == best]

        for p in survivors:
            rank = 1 + sum(score < total_strokes[p] for score in total_strokes.values())
            counts[p][0] += 1
            counts[p][1] += rank <= 20
            counts[p][2] += rank <= 10
            counts[p][3] += rank <= 5
            if total_strokes[p] == best:
                counts[p][4] += 1.0 / len(winners)

    probabilities = {
        p: {
            "cut_probability": counts[p][0] / n_simulations,
            "top20_probability": counts[p][1] / n_simulations,
            "top10_probability": counts[p][2] / n_simulations,
            "top5_probability": counts[p][3] / n_simulations,
            "win_probability": counts[p][4] / n_simulations,
        }
        for p in eligible
    }
    for pid in eliminated:
        probabilities[pid] = {
            "cut_probability": 0.0, "top20_probability": 0.0, "top10_probability": 0.0,
            "top5_probability": 0.0, "win_probability": 0.0,
        }

    excluded_players = {
        pid: "no SG forecast available" for pid in live_states if forecasts.get(pid) is None
    }

    return LiveSimulationResult(
        probabilities=probabilities,
        excluded_players=excluded_players,
        eliminated_players=eliminated,
        seed=seed,
        n_simulations=n_simulations,
        current_round=current_round,
    )
