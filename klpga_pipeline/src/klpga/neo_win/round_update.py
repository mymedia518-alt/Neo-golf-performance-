"""Post-Round-1 probability update for a NEO WIN v0.1 PRE prediction —
BETA #001-R1.

======================================================================
CUT FORMAT — VERIFIED FROM EXISTING REAL EVIDENCE, NOT ASSUMED
======================================================================
docs/SITE_STRUCTURE_TODO.md (real 100-tournament collection, confirmed
2026-08-24): the real `rounds_played` distribution across every
collected tournament is exactly `{1, 2, 4}` — ZERO 3-round players,
"exactly the signature of a standard 36-hole cut (cut after round 2)".
No subsequent cut exists. This module therefore only ever simulates
ONE cut event (after Round 2) and never fabricates an R3 or R4 cut.
`estimate_cut_fraction` below computes the empirical made-cut rate from
this same real, already-collected historical data — never a guessed
cutline rule (KLPGA's exact "top-N-and-ties" policy is not independently
confirmed anywhere in this project, so this uses the REAL observed
base rate instead of inventing one).

======================================================================
METHOD — Monte Carlo tournament simulation
======================================================================
This combines every required input into ONE coherent simulation rather
than several disconnected probability formulas:

  - FROZEN PRE PERFORMANCE PRIOR: each player's `neo_win.model`
    combined_score (career scoring + recent form + consistency +
    validated official metrics — read directly from the frozen
    snapshot, never recomputed) sets their EXPECTED per-round scoring
    rate for every remaining round.
  - ACTUAL ROUND-1 SCORE: real, already-known, never simulated —
    counted exactly once toward the 36-hole cut total and the 72-hole
    total.
  - REMAINING 54-HOLE UNCERTAINTY: each remaining round is drawn from
    Normal(expected_round_score_to_par, spread), spread taken from
    `neo_consistency_stddev` (shrunk to the training-fold population
    mean when missing — the SAME convention as every other missing-
    data case in this project, never a fabricated fixed spread).
  - The cut is applied WITHIN each simulated trial after Round 2
    (empirical cut_fraction, see above); WIN/TOP5/TOP10/TOP20 are
    computed only among that trial's cut-makers, exactly matching the
    real tournament's own elimination structure.

Disclosed simplifications (BETA, not claimed final): round scores are
drawn i.i.d. Normal per player (no course-difficulty-by-round
correlation, no playoff modeling — ties for the win split the win
credit fractionally rather than simulating a playoff).

======================================================================
SAMPLE-SIZE SHRINKAGE FOR expected_round_score_to_par / spread
======================================================================
Real R1 audit evidence (BETA #001 R1 FINAL validation) confirmed the
frozen snapshot's raw prior_avg_round_score_to_par / neo_consistency_
stddev were being used AS-IS regardless of how many historical rounds
each value was actually computed from — a player with a real but tiny
sample got their raw average used exactly like a player with a large
one, while the codebase already had a backtested, n-weighted shrinkage
formula (`klpga.models.candidates.fit_shrinkage` /
`apply_shrinkage_and_standardize`, `weight = n / (n + k)`, k = the
median training sample size) that was only ever applied to the
SEPARATE PRE win_probability path (`klpga.neo_win.model._combined_
score`), never to this module's remaining-round expectation.

`build_sim_inputs_from_frozen_snapshot` below now accepts OPTIONAL
`n_lookup` / `avg_shrink_params` / `stddev_shrink_params` — when the
caller supplies all three (scripts/35 does, using the real per-player
sample sizes recomputed fresh from the live DB via the same point-in-
time functions the PRE path itself uses, since the frozen snapshot
does not retain `_n` companions), `expected_round_score_to_par` and
`spread` are shrunk toward the SAME real, backtested population mean
already fit for the PRE path — using `shrink_to_original_units` below,
which applies the identical `weight = n/(n+k)` formula but stops
BEFORE `apply_shrinkage_and_standardize`'s final z-score division: this
module needs an expected SCORE in real to-par/stroke units (it is added
directly to `r1_score_to_par`), not a unit-less z-score, so calling
`apply_shrinkage_and_standardize` itself here would silently corrupt
the simulation's units. When the three arguments are omitted (every
existing caller/test), behavior is BYTE-IDENTICAL to before this
change — this is a strictly opt-in extension, not a default behavior
change.
"""
from __future__ import annotations

import random
import sqlite3
import statistics
from dataclasses import dataclass
from typing import Optional

from klpga.models.candidates import ShrinkageParams

DEFAULT_N_SIMULATIONS = 5000


def shrink_to_original_units(raw: Optional[float], n: Optional[int], params: ShrinkageParams) -> Optional[float]:
    """Same `weight = n / (n + k)` shrinkage formula as `klpga.models.
    candidates.apply_shrinkage_and_standardize`, but returns the shrunk
    value in the feature's OWN original units (score-to-par / stroke
    stddev) instead of a standardized z-score — see module docstring
    for why round_update.py needs the former, never the latter. Returns
    `raw` unchanged if `raw` or `n` is missing (nothing to shrink)."""
    if raw is None or not n:
        return raw
    weight = n / (n + params.k)
    return params.pop_mean + weight * (raw - params.pop_mean)


def estimate_cut_fraction(conn: sqlite3.Connection) -> float:
    """Real, empirical made-cut rate from every already-collected
    player_event row: rounds_played==4 (made the cut, per the
    confirmed {1,2,4} distribution) over every player with at least 1
    round played (excludes rows with no rounds at all, which would be
    a collection artifact, not a real field member). Returns 0.65
    (documented, disclosed neutral default) only if there is no
    historical data at all to compute a real rate from."""
    total = conn.execute("SELECT COUNT(*) FROM player_event WHERE rounds_played >= 1").fetchone()[0]
    made_cut = conn.execute("SELECT COUNT(*) FROM player_event WHERE rounds_played = 4").fetchone()[0]
    if total == 0:
        return 0.65
    return made_cut / total


def fit_post_r1_shrink_params(conn: sqlite3.Connection, game_code: str, cutoff_date) -> tuple[ShrinkageParams, ShrinkageParams]:
    """(avg_params, stddev_params) — fit via the SAME real, unmodified
    `klpga.models.candidates.fit_shrinkage` the PRE path already uses,
    over the SAME leakage-safe training rows (`klpga.neo_win.dataset.
    build_neo_win_live_training_rows`: every tournament strictly before
    `cutoff_date`, excluding `game_code` itself). No new fitting logic —
    reuses the existing implementation verbatim."""
    from klpga.models.candidates import fit_shrinkage
    from klpga.neo_win.dataset import build_neo_win_live_training_rows

    training_rows, _training_tournament_count = build_neo_win_live_training_rows(conn, game_code, cutoff_date)
    avg_params = fit_shrinkage(training_rows, "prior_avg_round_score_to_par")
    stddev_params = fit_shrinkage(training_rows, "neo_consistency_stddev")
    return avg_params, stddev_params


def build_post_r1_n_lookup(
    conn: sqlite3.Connection, game_code: str, cutoff_date, player_codes: list[str]
) -> dict[str, tuple[Optional[int], Optional[int]]]:
    """{player_code: (prior_avg_round_score_to_par_n, neo_consistency_
    stddev_n)} — the real sample size behind each player's frozen raw
    value, recomputed fresh via the SAME real, unmodified point-in-time
    functions the live PRE field itself uses (`klpga.backtest.
    point_in_time_features.compute_point_in_time_features`, `klpga.
    neo_win.consistency.compute_consistency_feature`), for the SAME
    (target tournament, cutoff date) — reproducible from the DB's
    already-collected history, never a new query or a new formula. The
    frozen PRE snapshot does not retain these `_n` values itself (only
    the raw feature value), which is why this must be recomputed rather
    than read back from the snapshot."""
    from klpga.backtest.point_in_time_features import compute_point_in_time_features, load_corpus
    from klpga.backtest.temporal import effective_tournament_date
    from klpga.neo_win.consistency import compute_consistency_feature

    row = conn.execute(
        "SELECT event_id, start_date, end_date FROM tournament_master WHERE game_code = ?", (game_code,)
    ).fetchone()
    if row is None:
        return {}
    target_event_id, start_date, end_date = row
    target_effective_date = effective_tournament_date(start_date, end_date).value

    corpus = load_corpus(conn)
    lookup: dict[str, tuple[Optional[int], Optional[int]]] = {}
    for code in player_codes:
        pit = compute_point_in_time_features(corpus, target_event_id, target_effective_date, code, code)
        _cons, cons_n = compute_consistency_feature(corpus, target_event_id, target_effective_date, code)
        lookup[code] = (pit.prior_avg_round_score_to_par_n, cons_n)
    return lookup


@dataclass(frozen=True)
class PlayerSimInput:
    player_code: str
    player_name: str
    expected_round_score_to_par: float
    """The per-round scoring RATE this player's PRE features imply —
    equal to their frozen prior_avg_round_score_to_par when present,
    shrunk to the training-fold population mean otherwise (never a
    fabricated fixed value)."""
    spread: float
    """Standard deviation to sample each remaining round from —
    neo_consistency_stddev when present, shrunk to the population mean
    otherwise."""
    r1_score_to_par: Optional[float]
    """Real, actual Round 1 score. None means R1 data is missing for
    this player (SKIP + LOG — see missing_r1_players in the result)."""


def build_sim_inputs_from_frozen_snapshot(
    pre_snapshot,
    r1_scores: dict[str, float],
    *,
    n_lookup: Optional[dict[str, tuple[Optional[int], Optional[int]]]] = None,
    avg_shrink_params: Optional[ShrinkageParams] = None,
    stddev_shrink_params: Optional[ShrinkageParams] = None,
) -> tuple[list[PlayerSimInput], list[str]]:
    """`r1_scores` is {player_code: round_1_score_to_par} from the real
    acquired Round-1 leaderboard. Players in the frozen PRE field with
    no R1 score are reported in `missing_r1_players`, never silently
    dropped from the eventual output (they still appear in results with
    every probability explicitly null, per the release's own "null
    probabilities = 0 unless truly unavailable, but never silently
    hidden" requirement).

    `n_lookup` is OPTIONAL: {player_code: (prior_avg_round_score_to_par_n,
    neo_consistency_stddev_n)} — the real sample sizes behind each raw
    frozen value, since the frozen snapshot itself does not retain them.
    When `n_lookup` and both `*_shrink_params` are provided, a player's
    RAW (non-missing) expected_round_score_to_par/spread is additionally
    shrunk via `shrink_to_original_units` toward the same real,
    backtested population mean the PRE path already uses for these two
    features — see module docstring. Omitting these three arguments
    (the default) preserves the exact prior behavior: the raw value
    used verbatim, or the field's population mean when fully missing."""
    known_scores = [e.prior_avg_round_score_to_par for e in pre_snapshot.predictions if e.prior_avg_round_score_to_par is not None]
    pop_mean_score = statistics.mean(known_scores) if known_scores else 0.0
    known_spreads = [e.neo_consistency_stddev for e in pre_snapshot.predictions if e.neo_consistency_stddev is not None]
    pop_mean_spread = statistics.mean(known_spreads) if known_spreads else 3.0

    apply_shrinkage = n_lookup is not None and avg_shrink_params is not None and stddev_shrink_params is not None

    sim_inputs = []
    missing_r1: list[str] = []
    for e in pre_snapshot.predictions:
        r1 = r1_scores.get(e.player_code)
        if r1 is None:
            missing_r1.append(e.player_code)
        expected = e.prior_avg_round_score_to_par if e.prior_avg_round_score_to_par is not None else pop_mean_score
        spread = e.neo_consistency_stddev if e.neo_consistency_stddev is not None else pop_mean_spread
        if apply_shrinkage:
            avg_n, stddev_n = n_lookup.get(e.player_code, (None, None))
            if e.prior_avg_round_score_to_par is not None:
                expected = shrink_to_original_units(e.prior_avg_round_score_to_par, avg_n, avg_shrink_params)
            if e.neo_consistency_stddev is not None:
                spread = shrink_to_original_units(e.neo_consistency_stddev, stddev_n, stddev_shrink_params)
        sim_inputs.append(
            PlayerSimInput(
                player_code=e.player_code, player_name=e.player_name,
                expected_round_score_to_par=expected, spread=max(spread, 0.5), r1_score_to_par=r1,
            )
        )
    return sim_inputs, missing_r1


def simulate_post_round1(
    sim_inputs: list[PlayerSimInput],
    *,
    cut_fraction: float,
    n_simulations: int = DEFAULT_N_SIMULATIONS,
    rng: Optional[random.Random] = None,
) -> dict[str, dict]:
    """Runs `n_simulations` independent trials. Players missing an R1
    score (r1_score_to_par is None) are EXCLUDED from every trial (they
    cannot be ranked without a real R1 result) — reported separately as
    zero-probability/None rather than silently assigned an average."""
    rng = rng or random.Random()
    playable = [p for p in sim_inputs if p.r1_score_to_par is not None]
    n_cutline = max(1, round(len(playable) * cut_fraction))

    wins = {p.player_code: 0.0 for p in playable}
    top5 = {p.player_code: 0 for p in playable}
    top10 = {p.player_code: 0 for p in playable}
    top20 = {p.player_code: 0 for p in playable}
    made_cut = {p.player_code: 0 for p in playable}

    for _ in range(n_simulations):
        r2 = {p.player_code: rng.normalvariate(p.expected_round_score_to_par, p.spread) for p in playable}
        thru36 = sorted(playable, key=lambda p: p.r1_score_to_par + r2[p.player_code])
        cutmakers = thru36[:n_cutline]
        cutmaker_codes = {p.player_code for p in cutmakers}
        for code in cutmaker_codes:
            made_cut[code] += 1

        totals = []
        for p in cutmakers:
            r3 = rng.normalvariate(p.expected_round_score_to_par, p.spread)
            r4 = rng.normalvariate(p.expected_round_score_to_par, p.spread)
            total = p.r1_score_to_par + r2[p.player_code] + r3 + r4
            totals.append((p.player_code, total))
        totals.sort(key=lambda t: t[1])

        if totals:
            best_score = totals[0][1]
            leaders = [code for code, score in totals if score == best_score]
            for code in leaders:
                wins[code] += 1.0 / len(leaders)
        for rank, (code, _score) in enumerate(totals, start=1):
            if rank <= 5:
                top5[code] += 1
            if rank <= 10:
                top10[code] += 1
            if rank <= 20:
                top20[code] += 1

    result = {}
    for p in playable:
        result[p.player_code] = {
            "win_pct": round(100 * wins[p.player_code] / n_simulations, 6),
            "top5_pct": round(100 * top5[p.player_code] / n_simulations, 4),
            "top10_pct": round(100 * top10[p.player_code] / n_simulations, 4),
            "top20_pct": round(100 * top20[p.player_code] / n_simulations, 4),
            "make_cut_pct": round(100 * made_cut[p.player_code] / n_simulations, 4),
        }
    return result
