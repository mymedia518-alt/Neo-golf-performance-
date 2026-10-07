"""HJ중공업·동부건설 챔피언십 (gameCode=2026100004) -- EXPERIMENTAL
Stableford Monte Carlo engine (2026-10-07, operator instruction).

THIS IS NOT THE PUBLIC MODEL. It does not modify, replace, or read
from anything that writes to STABLEFORD_2026_FROZEN_PREEVENT_SNAPSHOT_V1
.json -- it only READS that file's own already-frozen, already-leakage-
verified per-player real pre-event hole-outcome COUNTS (the exact same
counts V1's own net_expected_value/pre_event_rank were computed from,
via klpga.website_v2.stableford_player_value.from_season_rates) and
turns them into a per-hole categorical draw distribution for a full
108-player x 4-round x 18-hole tournament simulation. V1's own rank/
formula/weights are never touched, never re-derived, never tuned here.

Reuses klpga.website_v2.stableford_scoring's OUTCOMES/SCORING_TABLE/
HoleOutcomeProbabilities unchanged -- the one authoritative place the
official modified-Stableford point table (albatross +8, eagle +5,
birdie +2, par 0, bogey -1, double-bogey-or-worse -3) is defined in
this codebase. This module adds no new scoring rule.

Two distinct things a caller must not conflate:
  - PlayerDistribution.prior_source: "own_sample" (real, personal,
    leakage-verified counts) vs "field_neutral_prior" (a SYNTHETIC
    stand-in -- the holes-weighted average of every OTHER player's own
    real counts -- used ONLY for the 2 real entrants who have zero
    matched prior-tournament data, so the simulated field still has
    108 real bodies for cut-line mechanics; never presented as that
    player's own measured skill).
  - SimulationResult's per-player Win/TopN/MakeCut/median/P10/P90 are
    always computed for whichever field was actually simulated; a
    caller reporting these for a "field_neutral_prior" player MUST
    label them DATA LIMITED (see data_status) -- this module does not
    silently do that labeling for the caller.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

from klpga.website_v2.stableford_scoring import OUTCOMES, SCORING_TABLE, HoleOutcomeProbabilities

TARGET_GAME_CODE = "2026100004"
TARGET_CUTOFF = date.fromisoformat("2026-10-08")  # the tournament's own real start_date

POINTS_VECTOR = np.array([SCORING_TABLE[o] for o in OUTCOMES], dtype=np.int64)
assert list(SCORING_TABLE[o] for o in OUTCOMES) == [8, 5, 2, 0, -1, -3], (
    "OUTCOMES/SCORING_TABLE order drifted from the required "
    "albatross/eagle/birdie/par/bogey/double_or_worse -> 8/5/2/0/-1/-3 order"
)

NO_PRIOR_DATA_STATUS = "DATA_LIMITED_NO_PRIOR_DATA"


@dataclass(frozen=True)
class PlayerDistribution:
    player_code: str
    player_name: str
    nationality: str | None
    official_sponsor: str
    v1_pre_event_rank: int | None
    data_status: str
    sample_rounds: int | None
    sample_holes: int | None
    category_counts: tuple[int, ...]  # in OUTCOMES order; the counts this player's own probabilities are built from
    prior_source: str  # "own_sample" | "field_neutral_prior"
    probabilities: tuple[float, ...] = field(default=())  # in OUTCOMES order, filled in __post_init__

    def __post_init__(self):
        total = sum(self.category_counts)
        if total <= 0:
            raise ValueError(f"{self.player_name}: zero-total category_counts, cannot build a distribution")
        probs = tuple(c / total for c in self.category_counts)
        object.__setattr__(self, "probabilities", probs)

    def expected_points_per_hole(self) -> float:
        hp = HoleOutcomeProbabilities(**dict(zip(OUTCOMES, self.probabilities)))
        return hp.expected_points()


def _load_snapshot(snapshot_path: Path) -> dict:
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot["target_game_code"] != TARGET_GAME_CODE:
        raise ValueError(f"snapshot target_game_code {snapshot['target_game_code']!r} != {TARGET_GAME_CODE!r}")
    snapshot_cutoff = date.fromisoformat(snapshot["target_start_date"])
    if snapshot_cutoff != TARGET_CUTOFF:
        raise ValueError(f"snapshot target_start_date {snapshot_cutoff} != expected cutoff {TARGET_CUTOFF}")
    forbidden_keys = {"leaderboard", "scoreRecord", "actual_result", "r1", "r2", "r3", "fr", "final_result"}
    present = forbidden_keys & set(snapshot.keys())
    if present:
        raise ValueError(f"snapshot carries forbidden post-event key(s) {present} -- target leakage risk")
    for r in snapshot["records"]:
        present_rec = forbidden_keys & set(r.keys())
        if present_rec:
            raise ValueError(f"{r['player_name']}: record carries forbidden post-event key(s) {present_rec}")
    return snapshot


def field_neutral_prior_counts(snapshot_records: list[dict]) -> tuple[int, ...]:
    """Holes-weighted sum of every non-NO_PRIOR_DATA player's own real
    category counts -- a data-driven "average tour player" distribution,
    never reverse-engineered from V1's own published ranking order (this
    function never even looks at that ranking field)."""
    totals = [0] * len(OUTCOMES)
    for r in snapshot_records:
        if r["data_status"] == NO_PRIOR_DATA_STATUS:
            continue
        for i, o in enumerate(OUTCOMES):
            totals[i] += r[o]
    if sum(totals) == 0:
        raise ValueError("field_neutral_prior_counts: no eligible player data found")
    return tuple(totals)


def load_field(
    snapshot_path: Path,
    *,
    no_prior_data_policy: str = "field_neutral_prior",
) -> list[PlayerDistribution]:
    """no_prior_data_policy:
      "field_neutral_prior" -- the 2 real entrants with zero matched
        prior data get the field-wide average distribution (PRIMARY run).
      "exclude" -- those 2 entrants are left OUT of the returned list
        entirely (SENSITIVITY run, field shrinks to 106)."""
    if no_prior_data_policy not in ("field_neutral_prior", "exclude"):
        raise ValueError(f"unknown no_prior_data_policy {no_prior_data_policy!r}")
    snapshot = _load_snapshot(snapshot_path)
    records = snapshot["records"]
    if len(records) != snapshot["field_size"]:
        raise ValueError(f"record count {len(records)} != declared field_size {snapshot['field_size']}")
    neutral_counts = field_neutral_prior_counts(records)

    players: list[PlayerDistribution] = []
    seen_codes: set[str] = set()
    for r in records:
        code = r["player_code"]
        if code in seen_codes:
            raise ValueError(f"duplicate player_code {code} in snapshot")
        seen_codes.add(code)

        if r["data_status"] == NO_PRIOR_DATA_STATUS:
            if no_prior_data_policy == "exclude":
                continue
            counts = neutral_counts
            prior_source = "field_neutral_prior"
        else:
            counts = tuple(r[o] for o in OUTCOMES)
            prior_source = "own_sample"

        players.append(PlayerDistribution(
            player_code=code,
            player_name=r["player_name"],
            nationality=r.get("nationality"),
            official_sponsor=r.get("official_sponsor") or "",
            v1_pre_event_rank=r.get("pre_event_rank"),
            data_status=r["data_status"],
            sample_rounds=r.get("rounds"),
            sample_holes=r.get("holes"),
            category_counts=counts,
            prior_source=prior_source,
        ))
    return players


@dataclass(frozen=True)
class SimulationConfig:
    n_sims: int = 60_000
    seed: int = 20261007
    cut_size: int = 60
    n_rounds: int = 4
    holes_per_round: int = 18
    cut_after_round: int = 2


@dataclass
class SimulationResult:
    config: SimulationConfig
    player_codes: list[str]
    win_pct: np.ndarray
    top5_pct: np.ndarray
    top10_pct: np.ndarray
    top20_pct: np.ndarray
    make_cut_pct: np.ndarray
    median_final_points: np.ndarray
    p10_final_points: np.ndarray
    p90_final_points: np.ndarray
    expected_points_per_hole: np.ndarray
    expected_72_hole_points: np.ndarray
    # raw arrays kept for validation/red-team re-analysis, not for the public report
    final_points: np.ndarray = field(repr=False)   # (n_players, n_sims)
    made_cut: np.ndarray = field(repr=False)        # (n_players, n_sims) bool
    cum36: np.ndarray = field(repr=False)            # (n_players, n_sims)


def run_monte_carlo(players: list[PlayerDistribution], config: SimulationConfig) -> SimulationResult:
    n = len(players)
    rng = np.random.default_rng(config.seed)

    round_points = np.zeros((config.n_rounds, n, config.n_sims), dtype=np.int32)
    # Fixed iteration order (players already arrive in a fixed snapshot
    # order; rounds 1..n_rounds in order) so the exact same seed always
    # produces the exact same draw sequence -- the reproducibility
    # contract this module's own tests check.
    for p_idx, player in enumerate(players):
        probs = np.array(player.probabilities, dtype=float)
        probs = probs / probs.sum()  # defensive renormalization against float drift; raw sum is validated separately
        for round_idx in range(config.n_rounds):
            counts = rng.multinomial(config.holes_per_round, probs, size=config.n_sims)  # (n_sims, 6)
            round_points[round_idx, p_idx, :] = counts @ POINTS_VECTOR

    cum36 = round_points[0] + round_points[1]  # (n, n_sims) -- after cut_after_round=2 rounds
    cum72 = cum36 + round_points[2] + round_points[3]

    # CUT: top cut_size + ties, by cumulative points after cut_after_round rounds.
    sorted_desc_36 = -np.sort(-cum36, axis=0)  # (n, n_sims)
    cutline = sorted_desc_36[config.cut_size - 1, :]  # (n_sims,)
    made_cut = cum36 >= cutline[None, :]

    final_points = np.where(made_cut, cum72, cum36)

    ranking_score = np.where(made_cut, cum72, np.iinfo(np.int32).min // 2)
    sorted_desc_rank = -np.sort(-ranking_score, axis=0)

    max_score = sorted_desc_rank[0, :]
    is_leader = (ranking_score == max_score[None, :]) & made_cut
    n_leaders = is_leader.sum(axis=0)  # always >= 1: made_cut guarantees >= cut_size real finishers per sim
    credit_per_sim = 1.0 / n_leaders
    win_credit = is_leader * credit_per_sim[None, :]

    def _topN_pct(N: int) -> np.ndarray:
        boundary = sorted_desc_rank[N - 1, :]
        topN = (ranking_score >= boundary[None, :]) & made_cut
        return topN.mean(axis=1)

    expected_points_per_hole = np.array([p.expected_points_per_hole() for p in players])

    return SimulationResult(
        config=config,
        player_codes=[p.player_code for p in players],
        win_pct=win_credit.mean(axis=1),
        top5_pct=_topN_pct(5),
        top10_pct=_topN_pct(10),
        top20_pct=_topN_pct(20),
        make_cut_pct=made_cut.mean(axis=1),
        median_final_points=np.median(final_points, axis=1),
        p10_final_points=np.percentile(final_points, 10, axis=1),
        p90_final_points=np.percentile(final_points, 90, axis=1),
        expected_points_per_hole=expected_points_per_hole,
        expected_72_hole_points=expected_points_per_hole * config.n_rounds * config.holes_per_round,
        final_points=final_points,
        made_cut=made_cut,
        cum36=cum36,
    )


# ---------------------------------------------------------------- validation
# Section 10 ("VALIDATION") sanity checks, kept as small, independently
# callable functions so both the CLI script and the test suite exercise
# the exact same checks -- never two copies that can drift apart.

class ValidationError(AssertionError):
    pass


def validate_scoring_table() -> None:
    expected = {"albatross": 8, "eagle": 5, "birdie": 2, "par": 0, "bogey": -1, "double_or_worse": -3}
    if SCORING_TABLE != expected:
        raise ValidationError(f"SCORING_TABLE drifted: {SCORING_TABLE} != {expected}")
    if OUTCOMES != ("albatross", "eagle", "birdie", "par", "bogey", "double_or_worse"):
        raise ValidationError(f"OUTCOMES order drifted: {OUTCOMES}")


def validate_probability_vectors(players: list[PlayerDistribution]) -> None:
    for p in players:
        total = sum(p.probabilities)
        if not (0.999999 <= total <= 1.000001):
            raise ValidationError(f"{p.player_name}: probability vector sums to {total}, not 1.0")
        if any(v < 0 for v in p.probabilities):
            raise ValidationError(f"{p.player_name}: negative probability in {p.probabilities}")


def validate_field_identity(players: list[PlayerDistribution], *, expected_size: int) -> None:
    if len(players) != expected_size:
        raise ValidationError(f"field has {len(players)} players, expected {expected_size}")
    codes = [p.player_code for p in players]
    if len(set(codes)) != len(codes):
        dupes = {c for c in codes if codes.count(c) > 1}
        raise ValidationError(f"duplicate player_code(s): {dupes}")


def validate_target_leakage(snapshot_path: Path) -> None:
    """Re-verifies, independently of whatever upstream already checked,
    that the snapshot this module reads carries zero post-event signal
    for the target tournament. Raises on any violation; silent pass
    otherwise (no return value to misread as a score)."""
    _load_snapshot(snapshot_path)  # raises ValidationError-compatible ValueError on any violation
    repo_root = Path(__file__).resolve().parents[4]
    forbidden_patterns = ("LEADERBOARD", "SCORERECORD", "ACTUAL_RESULT", "_R1_", "_R2_", "_R3_", "_FR_", "_FINAL_RESULT")
    for path in (repo_root / "klpga_pipeline" / "content" / "website_v2").glob(f"{TARGET_GAME_CODE}_*"):
        name_upper = path.name.upper()
        if any(pat in name_upper for pat in forbidden_patterns):
            raise ValidationError(f"found a target post-event artifact on disk: {path}")


def validate_no_impossible_outcome(result: SimulationResult, *, n_rounds: int = 4, holes_per_round: int = 18) -> None:
    min_round = -3 * holes_per_round
    max_round = 8 * holes_per_round
    if result.final_points.min() < min_round * n_rounds or result.final_points.max() > max_round * n_rounds:
        raise ValidationError(
            f"final_points out of theoretically-possible range: "
            f"[{result.final_points.min()}, {result.final_points.max()}] vs "
            f"[{min_round * n_rounds}, {max_round * n_rounds}]"
        )
    if result.cum36.min() < min_round * 2 or result.cum36.max() > max_round * 2:
        raise ValidationError(f"cum36 out of theoretically-possible range: [{result.cum36.min()}, {result.cum36.max()}]")


def validate_cut_rule(result: SimulationResult, *, cut_size: int) -> None:
    made_cut_counts = result.made_cut.sum(axis=0)
    if (made_cut_counts < cut_size).any():
        raise ValidationError(f"a simulation advanced fewer than {cut_size} players: min={made_cut_counts.min()}")
    # every made-cut player's cum36 score must be >= every missed-cut player's score, per sim
    cutline = np.where(result.made_cut, result.cum36, np.iinfo(np.int32).max).min(axis=0)
    missed_max = np.where(~result.made_cut, result.cum36, np.iinfo(np.int32).min).max(axis=0)
    if (missed_max > cutline).any():
        raise ValidationError("a missed-cut player's cum36 exceeds a made-cut player's cum36 in some sim")


def validate_probability_sums_exactly(result: SimulationResult) -> None:
    total_pct = result.win_pct.sum()
    if not (0.999 <= total_pct <= 1.001):
        raise ValidationError(f"win_pct across the field sums to {total_pct}, not ~1.0")


def validate_reproducibility(players: list[PlayerDistribution], config: SimulationConfig) -> None:
    r1 = run_monte_carlo(players, config)
    r2 = run_monte_carlo(players, config)
    if not np.array_equal(r1.final_points, r2.final_points):
        raise ValidationError("same seed produced different final_points -- not reproducible")
    if not np.array_equal(r1.win_pct, r2.win_pct):
        raise ValidationError("same seed produced different win_pct -- not reproducible")
