"""4R FINAL PRE-BUILD Phase 4-5: PRE-FINAL forecast vs FINAL truth
validator, plus per-player surprise classification.

Reuses klpga.models.metrics for every probability metric (log loss,
normalized Brier, winner rank, top-k hit, reciprocal rank, calibration)
-- no new scoring formula is invented here. Joins the frozen PRE-FINAL
snapshot (final_pre_freeze.py) against FINAL truth (final_truth.py)
STRICTLY by player_id, never by name (klpga.models.metrics.
TournamentPrediction.probabilities is itself keyed by player_id).

Fails closed: raises FinalValidationBlocked (never returns a partial or
fabricated result) if the freeze manifest, FINAL truth, or the winner's
own forecast entry is missing, or if the frozen snapshot has drifted
since it was frozen.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from klpga.models.metrics import (
    CalibrationBin,
    TournamentPrediction,
    brier_norm,
    calibration_report,
    log_loss,
    make_prediction,
    reciprocal_rank,
    top_k_hit,
    winner_rank,
)
from klpga.neo_win.final_pre_freeze import (
    SURPRISE_CLASSIFICATION_RULE,
    detect_snapshot_drift,
    load_freeze_manifest,
    load_pre_final_snapshot,
)
from klpga.neo_win.final_truth import load_final_truth
from klpga.tournament_context import TournamentContext

NEO_HIGH_RANK_THRESHOLD = 10  # matches SURPRISE_CLASSIFICATION_RULE
ACTUAL_HIGH_RANK_THRESHOLD = 10


class FinalValidationBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class PlayerSurprise:
    player_id: str
    player_name: str
    predicted_rank: int
    final_rank: int
    rank_delta: int  # predicted_rank - final_rank; positive = did better than NEO predicted
    win_probability: float
    top5_probability: float
    top10_probability: float
    top20_probability: float
    actual_outcome: str  # official status ("ACTIVE"/"WD"/"DQ"/"DNS")
    quadrant: str  # one of A/B/C/D per SURPRISE_CLASSIFICATION_RULE


@dataclass(frozen=True)
class FinalValidationResult:
    game_code: str
    tournament_name: str
    winner_player_id: str
    winner_predicted_probability_pct: float
    winner_hit: bool
    brier_norm: float
    log_loss: float
    rank_mae: float
    top5_hit: bool
    top10_hit: bool
    top20_hit: bool
    reciprocal_rank: float
    field_size: int
    calibration: list  # list of dict (CalibrationBin, single-tournament sample)
    calibration_note: str
    surprises: list  # list of PlayerSurprise
    surprise_classification_rule: dict
    neo_final_rank_is_derived_proxy: bool
    rank_proxy_note: str


def _require(context: TournamentContext):
    manifest = load_freeze_manifest(context)
    if manifest is None:
        raise FinalValidationBlocked(
            "no PRE-FINAL freeze manifest -- run final_pre_freeze.write_freeze_manifest_if_absent first"
        )
    if detect_snapshot_drift(context):
        raise FinalValidationBlocked(
            "PRE-FINAL snapshot has drifted since it was frozen -- refusing to validate against "
            "a forecast that no longer matches its own recorded hash"
        )
    truth = load_final_truth(context)
    if truth is None:
        raise FinalValidationBlocked(
            "no FINAL truth exists yet -- official FR/R4 result has not been ingested"
        )
    if truth.get("synthetic_test_only"):
        raise FinalValidationBlocked(
            "FINAL truth is marked synthetic_test_only -- refusing to treat a test fixture as real"
        )
    return manifest, truth


def _quadrant(neo_high: bool, actual_high: bool) -> str:
    if neo_high and actual_high:
        return "A_NEO_HIGH_ACTUAL_HIGH"
    if neo_high and not actual_high:
        return "B_NEO_HIGH_ACTUAL_LOW"
    if not neo_high and actual_high:
        return "C_NEO_LOW_ACTUAL_HIGH"
    return "D_NEO_LOW_ACTUAL_LOW"


def run_final_validation(context: TournamentContext) -> FinalValidationResult:
    manifest, truth = _require(context)
    snapshot = load_pre_final_snapshot(context)

    forecast_records = {str(r["player_id"]): r for r in snapshot.get("records") or []}
    truth_records = {str(r["player_id"]): r for r in truth.get("records") or []}

    common_ids = set(forecast_records) & set(truth_records)
    if not common_ids:
        raise FinalValidationBlocked("forecast and FINAL truth share zero player_ids -- cannot join")

    raw_win_probabilities = {pid: float(forecast_records[pid]["win_pct"]) / 100.0 for pid in forecast_records}

    # neo_final_rank is either the forecast's own native per-simulation
    # output (KB's PRE-FINAL forecast) or, for a tournament whose
    # PRE-FINAL snapshot was assembled by a schema-compatibility bridge
    # over a probability-only forecast (see e.g.
    # scripts/180_build_hana_post_r3_forecast_compat.py), a post-hoc
    # derived probability-rank proxy that did not exist at forecast
    # time. The bridge marks every record it derives with
    # neo_final_rank_source; a native forecast never sets this field.
    # rank_mae and the surprise/quadrant classification below both key
    # off neo_final_rank, so whichever case applies here determines
    # whether those diagnostics are on the same evidentiary footing as
    # the probability-native metrics (Brier/log loss/reciprocal rank/
    # top-k hit) or a separate, weaker-footing diagnostic layer.
    is_derived_rank_proxy = any(
        bool(forecast_records[pid].get("neo_final_rank_source")) for pid in forecast_records
    )
    rank_proxy_note = (
        "neo_final_rank for this tournament is a post-hoc derived probability-rank proxy "
        "(sorted by win_pct/top10_pct/top5_pct/top20_pct, tie-broken by player_id) -- it did "
        "not exist in the original PRE-FINAL forecast. rank_mae, predicted_rank, rank_delta, "
        "and the surprise/quadrant classification all depend on it and are diagnostics on a "
        "different evidentiary footing than winner_hit/brier_norm/log_loss/top5_hit/top10_hit/"
        "top20_hit/reciprocal_rank, which are computed directly from the frozen forecast's own "
        "win/topN probabilities."
        if is_derived_rank_proxy else
        "neo_final_rank for this tournament is the forecast's own native per-simulation output, "
        "not a post-hoc proxy."
    )

    winner_id = str(truth["winner_player_id"])
    if winner_id not in raw_win_probabilities:
        raise FinalValidationBlocked(
            f"official winner player_id={winner_id!r} has no forecast entry -- cannot score a "
            "prediction that never covered the eventual winner"
        )

    prediction = make_prediction(
        target_event_id=context.game_code,
        target_game_code=context.game_code,
        target_start_date=context.start_date,
        raw_probabilities=raw_win_probabilities,
        winner=winner_id,
        prior_events_n_by_player={},
    )

    rank_errors = []
    surprises: list[PlayerSurprise] = []
    for pid in sorted(common_ids):
        fr = forecast_records[pid]
        tr = truth_records[pid]
        status = str(tr.get("status", "ACTIVE"))
        predicted_rank = int(fr["neo_final_rank"])
        if status != "ACTIVE":
            # WD/DQ/DNS carry no meaningful finishing rank (mirrors the
            # public page's own WD/DQ/DNS handling -- see
            # r3_real_page.STATUS_LABEL) -- excluded from rank-based
            # scoring, never coerced into a fabricated numeric rank.
            continue
        final_rank = int(tr["final_rank"])
        rank_errors.append(abs(predicted_rank - final_rank))

        neo_high = predicted_rank <= NEO_HIGH_RANK_THRESHOLD
        actual_high = final_rank <= ACTUAL_HIGH_RANK_THRESHOLD
        surprises.append(PlayerSurprise(
            player_id=pid,
            player_name=str(fr.get("player_name", tr.get("player_name", ""))),
            predicted_rank=predicted_rank,
            final_rank=final_rank,
            rank_delta=predicted_rank - final_rank,
            win_probability=float(fr["win_pct"]),
            top5_probability=float(fr["top5_pct"]),
            top10_probability=float(fr["top10_pct"]),
            top20_probability=float(fr["top20_pct"]),
            actual_outcome=str(tr.get("status", "ACTIVE")),
            quadrant=_quadrant(neo_high, actual_high),
        ))

    calibration_bins = calibration_report([prediction])

    return FinalValidationResult(
        game_code=context.game_code,
        tournament_name=context.tournament_name,
        winner_player_id=winner_id,
        winner_predicted_probability_pct=raw_win_probabilities[winner_id] * 100.0,
        winner_hit=top_k_hit(prediction, 1),
        brier_norm=brier_norm(prediction),
        log_loss=log_loss(prediction),
        rank_mae=statistics.mean(rank_errors) if rank_errors else float("nan"),
        top5_hit=top_k_hit(prediction, 5),
        top10_hit=top_k_hit(prediction, 10),
        top20_hit=top_k_hit(prediction, 20),
        reciprocal_rank=reciprocal_rank(prediction),
        field_size=prediction.field_size,
        calibration=[_bin_to_dict(b) for b in calibration_bins],
        calibration_note=(
            "single-tournament sample -- bootstrap CIs reflect within-event resampling only, "
            "not cross-event calibration; not over-interpreted as production calibration evidence"
        ),
        surprises=surprises,
        surprise_classification_rule=dict(SURPRISE_CLASSIFICATION_RULE),
        neo_final_rank_is_derived_proxy=is_derived_rank_proxy,
        rank_proxy_note=rank_proxy_note,
    )


def _bin_to_dict(b: CalibrationBin) -> dict:
    return {
        "lo": b.lo,
        "hi": b.hi,
        "row_count": b.row_count,
        "expected_wins": b.expected_wins,
        "actual_wins": b.actual_wins,
        "contributing_tournament_count": b.contributing_tournament_count,
        "expected_wins_ci": b.expected_wins_ci,
        "actual_wins_ci": b.actual_wins_ci,
    }


def biggest_surprises(result: FinalValidationResult, *, n: int = 5) -> tuple[list, list]:
    """(positive, negative) -- ranked by rank_delta magnitude. Positive
    = finished better than NEO's predicted rank; negative = finished
    worse. Ties broken by player_id for determinism."""
    ordered = sorted(result.surprises, key=lambda s: (-s.rank_delta, s.player_id))
    positive = [s for s in ordered if s.rank_delta > 0][:n]
    negative = sorted(
        [s for s in result.surprises if s.rank_delta < 0],
        key=lambda s: (s.rank_delta, s.player_id),
    )[:n]
    return positive, negative
