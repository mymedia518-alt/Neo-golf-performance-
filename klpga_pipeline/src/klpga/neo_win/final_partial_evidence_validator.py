"""4R FINAL BUILD (operator-unblocked, partial field): forecast-vs-actual
validation supported ONLY by OPERATOR_REPORTED_EXTERNAL_CROSS_VERIFIED
evidence (content/website_v2/KB_2026090003_OPERATOR_REPORTED_FINAL_
EVIDENCE_V1.json) -- explicitly NOT the full official FINAL Truth
(final_truth.py), because the complete 70-player field is not
recovered. Deliberately kept SEPARATE from final_validator.py /
final_truth.py's write-once official path: writing this partial,
operator-tier evidence into that immutable slot would permanently block
a later real, complete official ingestion from ever using it.

What IS reused, unchanged, from the existing generic library: every
probability metric (klpga.models.metrics) that only requires the full
70-player predicted-probability vector (already known, frozen, and
unmodified) plus the WINNER's identity (now confirmed) -- log loss,
normalized Brier, winner_rank, reciprocal_rank, top-k hit-for-winner.
These do NOT require knowing the full FINAL leaderboard, only the
winner, so they are fully supportable today. Anything that genuinely
needs the complete field (Top10/Top20 SET precision/recall, full
postmortem accumulation) is explicitly reported BLOCKED, never
guessed.
"""
from __future__ import annotations

from dataclasses import dataclass

from klpga.models.metrics import (
    brier_norm,
    log_loss,
    make_prediction,
    reciprocal_rank,
    top_k_hit,
    winner_rank,
)
from klpga.neo_win.final_pre_freeze import load_pre_final_snapshot
from klpga.tournament_context import TournamentContext


class PartialEvidenceBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class ConfirmedPlayerComparison:
    player_id: str
    player_name: str
    neo_predicted_rank: int
    neo_win_probability_pct: float
    actual_final_rank: str
    r3_actual_standing_note: str
    actual_position_from: int | None = None
    rank_delta: int | None = None  # neo_predicted_rank - actual_position_from; positive = beat NEO's prediction


@dataclass(frozen=True)
class PartialFinalComparison:
    winner_player_id: str
    winner_name: str
    winner_neo_win_probability_pct: float
    winner_neo_probability_rank: int
    winner_hit: bool
    brier_norm: float
    log_loss: float
    reciprocal_rank: float
    top5_hit_for_winner: bool
    top10_hit_for_winner: bool
    field_size: int
    predicted_top5_by_neo_rank: list
    actual_top5_confirmed: list
    top5_set_hits: list
    top5_set_predicted_only: list
    top5_set_actual_only: list
    top5_precision: float
    top5_recall: float
    confirmed_players: list  # list[ConfirmedPlayerComparison]
    blocked_metrics: list


def run_partial_comparison(context: TournamentContext, operator_evidence: dict) -> PartialFinalComparison:
    if operator_evidence.get("full_field_recovered"):
        raise PartialEvidenceBlocked(
            "this module is for PARTIAL (operator-tier, incomplete-field) evidence only -- "
            "a full-field recovery should go through final_truth.py / final_validator.py instead"
        )

    snapshot = load_pre_final_snapshot(context)
    forecast_by_id = {str(r["player_id"]): r for r in snapshot["records"]}

    confirmed = operator_evidence.get("confirmed_records") or []
    if not confirmed:
        raise PartialEvidenceBlocked("operator evidence has zero confirmed records")

    winner_records = [r for r in confirmed if str(r.get("final_rank")) == "1"]
    if len(winner_records) != 1:
        raise PartialEvidenceBlocked(f"expected exactly one confirmed winner (final_rank=1), found {len(winner_records)}")
    winner = winner_records[0]
    winner_id = str(winner["player_id"])
    if winner_id not in forecast_by_id:
        raise PartialEvidenceBlocked(f"confirmed winner player_id={winner_id!r} has no entry in the frozen R3 forecast")

    # Winner-centric metrics: these need only the FULL probability
    # vector (already known/frozen for all 70 players) + the winner's
    # identity -- never require the rest of the FINAL leaderboard.
    raw_probabilities = {pid: float(r["win_pct"]) / 100.0 for pid, r in forecast_by_id.items()}
    prediction = make_prediction(
        target_event_id=context.game_code,
        target_game_code=context.game_code,
        target_start_date=context.start_date,
        raw_probabilities=raw_probabilities,
        winner=winner_id,
        prior_events_n_by_player={},
    )

    confirmed_comparisons = []
    for rec in confirmed:
        pid = str(rec["player_id"])
        fr = forecast_by_id.get(pid)
        if fr is None:
            raise PartialEvidenceBlocked(f"confirmed player_id={pid!r} ({rec.get('player_name')}) has no entry in the frozen R3 forecast")
        confirmed_comparisons.append(ConfirmedPlayerComparison(
            player_id=pid,
            player_name=rec.get("player_name", fr.get("player_name", "")),
            neo_predicted_rank=int(fr["neo_final_rank"]),
            neo_win_probability_pct=float(fr["win_pct"]),
            actual_final_rank=str(rec.get("final_rank")),
            r3_actual_standing_note=str(rec.get("r3_actual_standing_rank_this_repo", "")),
        ))

    # Discrete Top5 SET comparison -- valid because the operator
    # evidence names the FULL, exact set of players occupying real
    # leaderboard positions 1 through 5 (including the T2 tie group),
    # not merely "some Top5 players".
    predicted_top5 = sorted(
        [{"player_id": pid, "player_name": r["player_name"], "neo_final_rank": int(r["neo_final_rank"])}
         for pid, r in forecast_by_id.items() if int(r["neo_final_rank"]) <= 5],
        key=lambda d: d["neo_final_rank"],
    )
    predicted_top5_ids = {d["player_id"] for d in predicted_top5}
    actual_top5_ids = {str(rec["player_id"]) for rec in confirmed}  # all 5 confirmed records ARE the actual top5
    hits = sorted(predicted_top5_ids & actual_top5_ids)
    predicted_only = sorted(predicted_top5_ids - actual_top5_ids)
    actual_only = sorted(actual_top5_ids - predicted_top5_ids)
    precision = len(hits) / len(predicted_top5_ids) if predicted_top5_ids else 0.0
    recall = len(hits) / len(actual_top5_ids) if actual_top5_ids else 0.0

    name_by_id = {pid: r["player_name"] for pid, r in forecast_by_id.items()}
    name_by_id.update({str(rec["player_id"]): rec.get("player_name") for rec in confirmed})

    return PartialFinalComparison(
        winner_player_id=winner_id,
        winner_name=name_by_id.get(winner_id, ""),
        winner_neo_win_probability_pct=float(forecast_by_id[winner_id]["win_pct"]),
        winner_neo_probability_rank=int(forecast_by_id[winner_id]["neo_final_rank"]),
        winner_hit=top_k_hit(prediction, 1),
        brier_norm=brier_norm(prediction),
        log_loss=log_loss(prediction),
        reciprocal_rank=reciprocal_rank(prediction),
        top5_hit_for_winner=top_k_hit(prediction, 5),
        top10_hit_for_winner=top_k_hit(prediction, 10),
        field_size=prediction.field_size,
        predicted_top5_by_neo_rank=predicted_top5,
        actual_top5_confirmed=[{"player_id": pid, "player_name": name_by_id.get(pid, "")} for pid in sorted(actual_top5_ids)],
        top5_set_hits=[{"player_id": pid, "player_name": name_by_id.get(pid, "")} for pid in hits],
        top5_set_predicted_only=[{"player_id": pid, "player_name": name_by_id.get(pid, "")} for pid in predicted_only],
        top5_set_actual_only=[{"player_id": pid, "player_name": name_by_id.get(pid, "")} for pid in actual_only],
        top5_precision=precision,
        top5_recall=recall,
        confirmed_players=confirmed_comparisons,
        blocked_metrics=list(operator_evidence.get("unsupported_full_field_metrics") or []),
    )


# ----------------------------------------------------------------
# Extended comparison: for a richer evidence file that names actual
# leaderboard POSITIONS (position_from/position_to per record, with
# ties spanning a range) rather than assuming "confirmed == exactly
# the top 5". Supports player_id=None (a confirmed position whose
# player identity could not be unambiguously OCR-matched) -- such
# records still count toward position-gap coverage but are excluded
# from any player_id-keyed comparison against the NEO forecast.
# ----------------------------------------------------------------


@dataclass(frozen=True)
class TopKSetComparison:
    k: int
    supported: bool
    reason: str
    predicted_ids: list
    actual_ids: list
    hits: list
    predicted_only: list
    actual_only: list
    precision: float
    recall: float
    unmatched_actual_names: list  # confirmed players occupying this top-k with no player_id match


def _positions_gapless_through(confirmed: list, k: int) -> bool:
    covered = set()
    for rec in confirmed:
        pf, pt = rec.get("position_from"), rec.get("position_to")
        if pf is None or pt is None:
            return False
        covered.update(range(int(pf), int(pt) + 1))
    return all(p in covered for p in range(1, k + 1))


def topk_set_comparison(forecast_by_id: dict, confirmed: list, name_by_id: dict, k: int) -> TopKSetComparison:
    if not _positions_gapless_through(confirmed, k):
        return TopKSetComparison(
            k=k, supported=False,
            reason=f"confirmed positions are not gapless from 1 through {k}",
            predicted_ids=[], actual_ids=[], hits=[], predicted_only=[], actual_only=[],
            precision=0.0, recall=0.0, unmatched_actual_names=[],
        )
    predicted_ids = {pid for pid, r in forecast_by_id.items() if int(r["neo_final_rank"]) <= k}
    in_range = [rec for rec in confirmed if int(rec["position_from"]) <= k]
    actual_ids = {str(rec["player_id"]) for rec in in_range if rec.get("player_id") is not None}
    unmatched_names = [rec["player_name"] for rec in in_range if rec.get("player_id") is None]

    hits = sorted(predicted_ids & actual_ids)
    predicted_only = sorted(predicted_ids - actual_ids)
    actual_only = sorted(actual_ids - predicted_ids)
    precision = len(hits) / len(predicted_ids) if predicted_ids else 0.0
    recall = len(hits) / len(actual_ids) if actual_ids else 0.0

    def _named(ids):
        return [{"player_id": pid, "player_name": name_by_id.get(pid, "")} for pid in ids]

    return TopKSetComparison(
        k=k, supported=True, reason="positions 1..k gapless in confirmed evidence",
        predicted_ids=_named(predicted_ids), actual_ids=_named(actual_ids),
        hits=_named(hits), predicted_only=_named(predicted_only), actual_only=_named(actual_only),
        precision=precision, recall=recall, unmatched_actual_names=unmatched_names,
    )


@dataclass(frozen=True)
class ExtendedFinalComparison:
    winner_player_id: str
    winner_name: str
    winner_neo_win_probability_pct: float
    winner_neo_probability_rank: int
    winner_hit: bool
    brier_norm: float
    log_loss: float
    reciprocal_rank: float
    field_size: int
    positions_confirmed_gapless_through: int
    topk: dict  # {5: TopKSetComparison, 10: ..., 20: ...}
    confirmed_players: list  # ConfirmedPlayerComparison for every ID-matched record
    unmatched_confirmed_names: list  # [{position, name}] for review
    blocked_metrics: list


def run_extended_comparison(context: TournamentContext, operator_evidence: dict) -> ExtendedFinalComparison:
    if operator_evidence.get("full_field_recovered"):
        raise PartialEvidenceBlocked(
            "this module is for PARTIAL (operator-tier, incomplete-field) evidence only -- "
            "a full-field recovery should go through final_truth.py / final_validator.py instead"
        )
    snapshot = load_pre_final_snapshot(context)
    forecast_by_id = {str(r["player_id"]): r for r in snapshot["records"]}

    confirmed = operator_evidence.get("confirmed_records") or []
    if not confirmed:
        raise PartialEvidenceBlocked("operator evidence has zero confirmed records")

    winner_records = [r for r in confirmed if str(r.get("final_rank")) == "1"]
    if len(winner_records) != 1:
        raise PartialEvidenceBlocked(f"expected exactly one confirmed winner (final_rank=1), found {len(winner_records)}")
    winner = winner_records[0]
    winner_id = winner.get("player_id")
    if winner_id is None:
        raise PartialEvidenceBlocked("confirmed winner has no player_id match -- cannot score without identity")
    winner_id = str(winner_id)
    if winner_id not in forecast_by_id:
        raise PartialEvidenceBlocked(f"confirmed winner player_id={winner_id!r} has no entry in the frozen R3 forecast")

    raw_probabilities = {pid: float(r["win_pct"]) / 100.0 for pid, r in forecast_by_id.items()}
    prediction = make_prediction(
        target_event_id=context.game_code, target_game_code=context.game_code,
        target_start_date=context.start_date, raw_probabilities=raw_probabilities,
        winner=winner_id, prior_events_n_by_player={},
    )

    name_by_id = {pid: r["player_name"] for pid, r in forecast_by_id.items()}
    confirmed_comparisons = []
    unmatched = []
    for rec in confirmed:
        pid = rec.get("player_id")
        if pid is None:
            unmatched.append({"position": rec.get("final_rank"), "player_name": rec.get("player_name")})
            continue
        pid = str(pid)
        fr = forecast_by_id.get(pid)
        if fr is None:
            raise PartialEvidenceBlocked(f"confirmed player_id={pid!r} ({rec.get('player_name')}) has no entry in the frozen R3 forecast")
        predicted_rank = int(fr["neo_final_rank"])
        position_from = rec.get("position_from")
        confirmed_comparisons.append(ConfirmedPlayerComparison(
            player_id=pid, player_name=rec.get("player_name", fr.get("player_name", "")),
            neo_predicted_rank=predicted_rank, neo_win_probability_pct=float(fr["win_pct"]),
            actual_final_rank=str(rec.get("final_rank")), r3_actual_standing_note="",
            actual_position_from=int(position_from) if position_from is not None else None,
            rank_delta=(predicted_rank - int(position_from)) if position_from is not None else None,
        ))

    max_position = max(int(r["position_to"]) for r in confirmed if r.get("position_to") is not None)
    gapless_through = 0
    for k in range(1, max_position + 1):
        if _positions_gapless_through(confirmed, k):
            gapless_through = k

    topk = {k: topk_set_comparison(forecast_by_id, confirmed, name_by_id, k) for k in (5, 10, 20)}

    return ExtendedFinalComparison(
        winner_player_id=winner_id, winner_name=name_by_id.get(winner_id, ""),
        winner_neo_win_probability_pct=float(forecast_by_id[winner_id]["win_pct"]),
        winner_neo_probability_rank=int(forecast_by_id[winner_id]["neo_final_rank"]),
        winner_hit=top_k_hit(prediction, 1), brier_norm=brier_norm(prediction), log_loss=log_loss(prediction),
        reciprocal_rank=reciprocal_rank(prediction), field_size=prediction.field_size,
        positions_confirmed_gapless_through=gapless_through, topk=topk,
        confirmed_players=confirmed_comparisons, unmatched_confirmed_names=unmatched,
        blocked_metrics=list(operator_evidence.get("unsupported_full_field_metrics") or []),
    )


def biggest_movers(result: ExtendedFinalComparison, *, n: int = 5) -> tuple[list, list]:
    """(overestimated, underestimated) among ID-matched confirmed
    players only, ranked by |rank_delta|. rank_delta = neo_predicted_rank
    - actual_position_from: negative = NEO ranked them better than they
    actually finished (overestimated); positive = NEO ranked them worse
    than they actually finished (underestimated)."""
    scored = [c for c in result.confirmed_players if c.rank_delta is not None]
    overestimated = sorted([c for c in scored if c.rank_delta < 0], key=lambda c: c.rank_delta)[:n]
    underestimated = sorted([c for c in scored if c.rank_delta > 0], key=lambda c: -c.rank_delta)[:n]
    return overestimated, underestimated
