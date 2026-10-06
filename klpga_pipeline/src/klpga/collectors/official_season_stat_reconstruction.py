"""Season-to-date CUMULATIVE reconstruction for Driving Distance /
Fairway Accuracy / GIR, built from multiple real per-tournament
`publicRecordSeasonDetail` calls (klpga.collectors.public_record_season_detail),
one per pre-cutoff tournament a player actually played.

WHY THIS EXISTS: scripts/210_acquire_official_season_stats.py's single
gameCode-scoped call was discovered (see STABLEFORD_THREE_WINNER_
PRE_EVENT_PROFILE_V1.md's "Critical finding") to return that ONE
tournament's own stats, never a season-cumulative value. The official
site itself exposes no partial-season-cumulative option -- its own
#searchGame-style dropdown (klpga/config.py's PUBLIC_RECORD_SEASON_
DETAIL_ENDPOINT provenance note) only offers "전체" (gameCode="", the
full season, including post-cutoff tournaments -- leakage) or one
specific tournament. The only temporal-safe path is to replicate, by
hand, exactly what KLPGA's own "전체" aggregation already proves it
does internally -- sum raw numerator/denominator counts, never average
pre-divided percentages -- restricted to our own pre-cutoff tournament
subset.

CONFIRMED AGGREGATION FORMULAS (verified exactly, zero rounding error,
against all 3 winners' real already-acquired single-tournament data --
see scripts/211's output and this module's own tests):
  driving_distance = sum(전체 비거리) / sum(전체 측정 홀)
  fairway_accuracy = sum(페어웨이 안착 수) / sum(전체 측정 홀) * 100
  gir              = sum(그린적중수) / sum(real_rounds_this_tournament * 18) * 100

GIR has no explicit total-holes field in the response; its own displayed
percentage divided back into 그린적중수 reproduces exactly
real_rounds * 18 for every one of the 3 winners' real captures (72, 72,
36 -- i.e. 4, 4, 2 rounds * 18), confirming every hole (not just
non-par-3 holes, unlike fairway) counts as a GIR opportunity.

NEVER average per-tournament percentages (explicitly forbidden -- see
the module docstring's own worked counter-example in the report)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TournamentCallRecord:
    """One per-tournament publicRecordSeasonDetail call result, after
    the scope gate has already run (klpga.collectors.
    official_season_stat_reconstruction.scope_gate_passes)."""
    game_code: str
    gate_passed: bool
    driving_distance_numerator: float | None  # 전체 비거리
    driving_distance_denominator: float | None  # 전체 측정 홀
    fairway_numerator: float | None  # 페어웨이 안착 수
    fairway_denominator: float | None  # 전체 측정 홀
    gir_numerator: float | None  # 그린적중수
    real_rounds_this_tournament: int  # ground truth, from the reconstruction manifest


def scope_gate_passes(returned_rounds: int | None, real_rounds_this_tournament: int) -> bool:
    """The per-call gate (section 3's explicit requirement): a
    gameCode-scoped call is trusted ONLY if its own returned 라운드수
    exactly matches this tournament's independently-known real round
    count for this player (from already-verified scoreRecord data).
    Any mismatch means the response's scope is NOT what was assumed --
    exclude it, never silently sum it in."""
    return returned_rounds is not None and returned_rounds == real_rounds_this_tournament


@dataclass(frozen=True)
class ReconstructedCumulativeMetric:
    value: float | None
    numerator: float
    denominator: float
    n_tournaments_included: int
    n_tournaments_gate_failed: int
    n_tournaments_total: int


def _weighted_aggregate(records: list[TournamentCallRecord], numerator_attr: str, denominator_attr: str,
                         scale: float) -> ReconstructedCumulativeMetric:
    gate_failed = sum(1 for r in records if not r.gate_passed)
    usable = [r for r in records if r.gate_passed and getattr(r, numerator_attr) is not None
              and getattr(r, denominator_attr) is not None]
    numerator = sum(getattr(r, numerator_attr) for r in usable)
    denominator = sum(getattr(r, denominator_attr) for r in usable)
    value = round(numerator / denominator * scale, 4) if denominator else None
    return ReconstructedCumulativeMetric(
        value=value, numerator=numerator, denominator=denominator,
        n_tournaments_included=len(usable), n_tournaments_gate_failed=gate_failed,
        n_tournaments_total=len(records),
    )


def reconstruct_driving_distance(records: list[TournamentCallRecord]) -> ReconstructedCumulativeMetric:
    return _weighted_aggregate(records, "driving_distance_numerator", "driving_distance_denominator", scale=1.0)


def reconstruct_fairway_accuracy(records: list[TournamentCallRecord]) -> ReconstructedCumulativeMetric:
    return _weighted_aggregate(records, "fairway_numerator", "fairway_denominator", scale=100.0)


def reconstruct_gir(records: list[TournamentCallRecord]) -> ReconstructedCumulativeMetric:
    """GIR's denominator (rounds * 18) is derived per-record, not
    carried as a separate response field -- built here via a synthetic
    attribute so _weighted_aggregate's generic sum/sum still applies."""
    augmented = [
        TournamentCallRecord(
            game_code=r.game_code, gate_passed=r.gate_passed,
            driving_distance_numerator=r.gir_numerator,
            driving_distance_denominator=(r.real_rounds_this_tournament * 18) if r.gate_passed else None,
            fairway_numerator=None, fairway_denominator=None, gir_numerator=r.gir_numerator,
            real_rounds_this_tournament=r.real_rounds_this_tournament,
        )
        for r in records
    ]
    return _weighted_aggregate(augmented, "driving_distance_numerator", "driving_distance_denominator", scale=100.0)
