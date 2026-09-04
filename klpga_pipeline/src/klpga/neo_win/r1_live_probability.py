"""OK Open R1 live win/top-N/cut probability engine.

Distinct from klpga.neo_win.round_update (BETA #001/KG Ladies Open's
SQL-DB-backed Monte Carlo engine) -- this project's OK Open pipeline is
JSON-artifact-based (content/website_v2/*.json), not DB-backed, so this
module is a self-contained adapter with its own Monte Carlo loop
(PlayerSimInput dataclass reused unmodified; round_update.py itself is
untouched -- zero risk to BETA #001's existing tested behavior).

METHOD
======================================================================
Each player's PRE performance is read from
OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json's Strokes-Gained windows
(already computed, validated, and used to build this same tournament's
PRE win_probability / neo_performance_band). expected_round_score_to_par
is derived as -1 * (recent-window mean SG total) -- SG total is
already in stroke units relative to the field average, so negating it
converts "strokes gained" into "expected score relative to the field's
average round", the same sign convention round_update.py's
prior_avg_round_score_to_par uses. Window preference: recent5, then
recent10, recent3, season2026, multi_season, current -- the first
window with a real (non-null) SG total mean. A player with NO usable
window anywhere gets the field's own mean (never a fabricated fixed
value), and is flagged in `population_fallback_players`.

spread (the Normal per-round draw's stddev) is the same window's
sample_sd, falling back to population_sd, floored at 0.5 -- identical
floor to round_update.py, for the identical reason (a near-zero
observed spread from a tiny sample must not collapse the simulation to
a near-certainty).

CUT FRACTION -- DISCLOSED NEUTRAL DEFAULT, NOT A GUESSED RULE
======================================================================
round_update.py's estimate_cut_fraction() computes a real empirical
made-cut rate from this project's own collected 100+-tournament corpus
via a live SQL DB -- unavailable in this JSON-only OK Open pipeline
deployment. Rather than invent an OK-Open-specific number with no
evidence behind it, this module uses the SAME documented neutral
default that function itself falls back to when no data exists: 0.65.
This is disclosed everywhere it is used (never presented as a
confirmed fact) and should be replaced with a real fitted value the
moment a live DB backing this tournament exists.

CUT LINE -- A DISTRIBUTION, NEVER A SINGLE CONFIRMED NUMBER
======================================================================
Per NEO's own requirement, a single expected cut line must never be
shown as a determined fact. Every trial's simulated 36-hole cutline
score is retained; simulate_r1_live returns the full sorted list so
callers can present percentiles (see cutline_percentiles) instead of
one point estimate.

NO FABRICATION
======================================================================
Every player who cannot be assigned a real Round-1 score (hasn't teed
off, or the row is otherwise unresolved) is EXCLUDED from every
Monte-Carlo trial's ranking (same convention as
round_update.simulate_post_round1) and reported separately in
`excluded_no_r1_score` -- rendered downstream as "산출 불가", never a
zero or a guess.
"""
from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Optional

from klpga.neo_win.round_update import PlayerSimInput

DEFAULT_N_SIMULATIONS = 5000
DEFAULT_CUT_FRACTION = 0.65
MIN_SPREAD = 0.5
_WINDOW_PREFERENCE = ("recent5", "recent10", "recent3", "season2026", "multi_season", "current")


def _select_expected_and_spread(profile: dict) -> tuple[Optional[float], Optional[float], Optional[str]]:
    windows = (profile or {}).get("windows") or {}
    for key in _WINDOW_PREFERENCE:
        comp = ((windows.get(key) or {}).get("components") or {}).get("total") or {}
        mean = comp.get("mean")
        if mean is None:
            continue
        sd = comp.get("sample_sd")
        if sd is None:
            sd = comp.get("population_sd")
        return -float(mean), (float(sd) if sd is not None else None), key
    return None, None, None


@dataclass(frozen=True)
class R1SimInputResult:
    sim_inputs: list
    population_fallback_players: list
    missing_r1_players: list
    window_used: dict


def build_r1_sim_inputs(pre_records: list, performance_profiles: list, r1_scores: dict) -> R1SimInputResult:
    """pre_records: OK_OPEN_2026_PRE_PUBLIC_MASTER['records'] (player_id,
    current_official_player_name). performance_profiles:
    OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT['profiles'] (player_id,
    windows). r1_scores: {player_id: total_under_par int} from the real
    live R1 leaderboard -- a player absent from this dict has not
    posted a resolvable R1 score yet."""
    profile_by_id = {str(p.get("player_id")): p for p in performance_profiles}

    raw = []
    for rec in pre_records:
        pid = str(rec.get("player_id"))
        name = rec.get("current_official_player_name") or (rec.get("historical_source_names") or [None])[0]
        expected, spread, window = _select_expected_and_spread(profile_by_id.get(pid, {}))
        raw.append((pid, name, expected, spread, window))

    known_expected = [e for _, _, e, _, _ in raw if e is not None]
    known_spread = [s for _, _, _, s, _ in raw if s is not None]
    pop_expected = statistics.mean(known_expected) if known_expected else 0.0
    pop_spread = statistics.mean(known_spread) if known_spread else 3.0

    sim_inputs = []
    population_fallback = []
    missing_r1 = []
    window_used = {}
    for pid, name, expected, spread, window in raw:
        used_fallback = expected is None
        final_expected = expected if expected is not None else pop_expected
        final_spread = max(spread if spread is not None else pop_spread, MIN_SPREAD)
        if used_fallback:
            population_fallback.append(pid)
            window_used[pid] = "POPULATION_FALLBACK"
        else:
            window_used[pid] = window
        r1 = r1_scores.get(pid)
        if r1 is None:
            missing_r1.append(pid)
        sim_inputs.append(
            PlayerSimInput(player_code=pid, player_name=name, expected_round_score_to_par=final_expected, spread=final_spread, r1_score_to_par=r1)
        )

    return R1SimInputResult(sim_inputs, population_fallback, missing_r1, window_used)


@dataclass(frozen=True)
class R1ProbabilityResult:
    probabilities: dict
    cutline_distribution: list
    cut_fraction_used: float
    n_simulations: int
    excluded_no_r1_score: list


def simulate_r1_live(
    sim_inputs: list, *, cut_fraction: float = DEFAULT_CUT_FRACTION, n_simulations: int = DEFAULT_N_SIMULATIONS, rng: Optional[random.Random] = None
) -> R1ProbabilityResult:
    """Monte Carlo: R1 is real (already known); R2/R3/R4 are drawn
    Normal(expected_round_score_to_par, spread) per trial. Cut applied
    at 36 holes (R1+R2) using cut_fraction; WIN/TOP5/TOP10/TOP20 are
    computed only among that trial's cut-makers. Same structure as
    round_update.simulate_post_round1, plus cutline_distribution
    capture (see module docstring)."""
    rng = rng or random.Random()
    playable = [p for p in sim_inputs if p.r1_score_to_par is not None]
    excluded = [p.player_code for p in sim_inputs if p.r1_score_to_par is None]
    n_cutline = max(1, round(len(playable) * cut_fraction))

    wins = {p.player_code: 0.0 for p in playable}
    top5 = {p.player_code: 0 for p in playable}
    top10 = {p.player_code: 0 for p in playable}
    top20 = {p.player_code: 0 for p in playable}
    made_cut = {p.player_code: 0 for p in playable}
    cutline_scores: list = []

    for _ in range(n_simulations):
        r2 = {p.player_code: rng.normalvariate(p.expected_round_score_to_par, p.spread) for p in playable}
        thru36 = sorted(playable, key=lambda p: p.r1_score_to_par + r2[p.player_code])
        if len(thru36) >= n_cutline:
            boundary = thru36[n_cutline - 1]
            cutline_scores.append(round(boundary.r1_score_to_par + r2[boundary.player_code], 2))
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
    cutline_scores.sort()
    return R1ProbabilityResult(result, cutline_scores, cut_fraction, n_simulations, excluded)


def cutline_percentiles(cutline_distribution: list) -> Optional[dict]:
    """{'p10', 'p50', 'p90'} of the simulated 36-hole cutline score --
    a real distribution summary, never collapsed to one asserted
    number. None if the distribution is empty (e.g. fewer real R1
    scores than the cutline position)."""
    if not cutline_distribution:
        return None

    def pct(p: float) -> float:
        idx = min(len(cutline_distribution) - 1, max(0, round(p * (len(cutline_distribution) - 1))))
        return cutline_distribution[idx]

    return {"p10": pct(0.10), "p50": pct(0.50), "p90": pct(0.90)}


@dataclass(frozen=True)
class MoverEntry:
    player_id: str
    player_name: Optional[str]
    metric: str
    pre_value: Optional[float]
    current_value: Optional[float]
    delta: Optional[float]


def compute_neo_movers(pre_records: list, probabilities: dict, sim_inputs: list, *, top_n: int = 5) -> dict:
    """PRE win_probability (0..1) vs current simulated win_pct (0..100)
    -- normalized to the same 0..100 scale before comparing. top10 PRE
    values are frequently None (OK Open's PRE model explicitly marked
    top5/top10/top20 "unsupported" -- no_unsupported_top_probabilities
    in the master) -- a None PRE baseline means no delta can be
    computed for that player/metric, and it is simply excluded from
    that mover list, never defaulted to 0.

    "Cut% 급락" has no PRE cut baseline to drop from (PRE published no
    cut probability at all), so it is reported honestly as: players
    whose PRE neo_performance_band was HIGH/VERY_HIGH (an established,
    real, already-validated skill signal) but whose CURRENT simulated
    make_cut_pct has fallen below 50% -- a genuine "underperforming
    relative to their own established baseline" signal, not a
    fabricated delta from a number that was never computed."""
    pre_by_id = {str(r.get("player_id")): r for r in pre_records}
    sim_by_id = {p.player_code: p for p in sim_inputs}

    win_risers, win_fallers, top10_risers = [], [], []
    cut_droppers, over_expected, under_expected = [], [], []

    for pid, probs in probabilities.items():
        pre = pre_by_id.get(pid, {})
        name = pre.get("current_official_player_name")

        pre_win = pre.get("win_probability")
        cur_win = probs.get("win_pct")
        if pre_win is not None and cur_win is not None:
            delta = cur_win - (pre_win * 100)
            entry = MoverEntry(pid, name, "win_pct", pre_win * 100, cur_win, delta)
            (win_risers if delta >= 0 else win_fallers).append(entry)

        pre_top10 = pre.get("top10_probability")
        cur_top10 = probs.get("top10_pct")
        if pre_top10 is not None and cur_top10 is not None:
            delta = cur_top10 - (pre_top10 * 100)
            top10_risers.append(MoverEntry(pid, name, "top10_pct", pre_top10 * 100, cur_top10, delta))

        cur_cut = probs.get("make_cut_pct")
        band = pre.get("neo_performance_band")
        if cur_cut is not None and cur_cut < 50.0 and band in ("HIGH", "VERY_HIGH"):
            cut_droppers.append(MoverEntry(pid, name, "make_cut_pct_vs_band", None, cur_cut, None))

        sim = sim_by_id.get(pid)
        if sim is not None and sim.r1_score_to_par is not None:
            vs_expected = sim.expected_round_score_to_par - sim.r1_score_to_par
            entry = MoverEntry(pid, name, "vs_expected_strokes", sim.expected_round_score_to_par, sim.r1_score_to_par, vs_expected)
            (over_expected if vs_expected >= 0 else under_expected).append(entry)

    win_risers.sort(key=lambda e: e.delta, reverse=True)
    win_fallers.sort(key=lambda e: e.delta)
    top10_risers.sort(key=lambda e: e.delta, reverse=True)
    cut_droppers.sort(key=lambda e: e.current_value)
    over_expected.sort(key=lambda e: e.delta, reverse=True)
    under_expected.sort(key=lambda e: e.delta)

    return {
        "win_pct_risers": win_risers[:top_n],
        "win_pct_fallers": win_fallers[:top_n],
        "top10_pct_risers": top10_risers[:top_n],
        "cut_pct_droppers_vs_band": cut_droppers[:top_n],
        "beat_expectation": over_expected[:top_n],
        "missed_expectation": under_expected[:top_n],
    }
