"""NEO TOURNAMENT PIPELINE item 4: connect the PRE win-forecast to the
generic, already-tested evaluation library (klpga.models.metrics) once
a tournament's final round is actually complete.

Fail-closed generic entry point: no new model/metric logic is invented
here -- this module only assembles real on-disk artifacts (PRE's
win_forecast + the official final round's live snapshot) into the
TournamentPrediction shape klpga.models.metrics already scores, and
raises PostmortemBlocked rather than fabricating a result if the final
round is not yet officially complete or the winner cannot be identified
from real, already-validated data.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from klpga.models.metrics import (
    ModelMetricsSummary,
    TournamentPrediction,
    brier_norm,
    log_loss,
    make_prediction,
    reciprocal_rank,
    summarize_model,
    top_k_hit,
    winner_rank,
)
from klpga.tournament_context import TournamentContext
from klpga.tournament_runtime import NON_CUT_STATUSES


class PostmortemBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class PostmortemResult:
    game_code: str
    tournament_name: str
    prediction: TournamentPrediction
    log_loss: float
    brier_norm: float
    winner_rank: int
    top5_hit: bool
    top10_hit: bool
    reciprocal_rank: float
    summary: ModelMetricsSummary
    output_path: Path


def _holes_completed(player: dict) -> int:
    try:
        return int(player.get("holes_completed"))
    except (TypeError, ValueError):
        return 0


def _final_round_snapshot(context: TournamentContext) -> dict:
    path = context.artifact_path(f"r{context.final_round_number}_live_snapshot")
    if not path.is_file():
        raise PostmortemBlocked(
            f"no final-round (r{context.final_round_number}) live snapshot at {path} -- "
            "postmortem requires the official final round to actually be complete"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _identify_winner(snapshot: dict) -> str:
    players = snapshot.get("player_table") or []
    if not players:
        raise PostmortemBlocked("final round snapshot has zero players")

    still_playing = [
        p for p in players
        if str(p.get("status") or "").strip().upper() not in NON_CUT_STATUSES
        and _holes_completed(p) != 18
    ]
    if still_playing:
        raise PostmortemBlocked(
            f"final round is not complete -- {len(still_playing)} player(s) still in progress; "
            "postmortem refuses to evaluate an unfinished tournament"
        )

    leaders = [p for p in players if str(p.get("rank_display")) == "1"]
    if len(leaders) != 1:
        raise PostmortemBlocked(f"could not identify a single official rank-1 winner (found {len(leaders)})")

    winner = leaders[0]
    player_id = winner.get("player_id") or winner.get("player_code")
    if not player_id:
        raise PostmortemBlocked("winning player row has no player_id/player_code")
    return str(player_id)


def _pre_probabilities(context: TournamentContext) -> dict[str, float]:
    path = context.artifact_path("pre_win_forecast")
    if not path.is_file():
        raise PostmortemBlocked(f"no PRE win forecast at {path} -- nothing to evaluate against")
    pre = json.loads(path.read_text(encoding="utf-8"))
    records = pre.get("records") or []
    if not records:
        raise PostmortemBlocked("PRE win forecast has zero records")

    probabilities: dict[str, float] = {}
    for record in records:
        player_id = str(record.get("player_id"))
        probability = record.get("win_probability")
        if probability is None:
            raise PostmortemBlocked(f"PRE record for player_id={player_id} has null win_probability")
        probabilities[player_id] = float(probability)
    return probabilities


def run_postmortem(context: TournamentContext) -> PostmortemResult:
    """The generic POSTMORTEM lifecycle stage. Raises PostmortemBlocked
    (never returns a partial/fabricated result) if the final round
    isn't officially complete yet, or the winner isn't in the PRE
    field. Writes context.artifact_path("postmortem_report") -- a new
    artifact_type, resolved through the same compatibility-mapping /
    generic-fallback contract as every other artifact."""
    final_snapshot = _final_round_snapshot(context)
    winner = _identify_winner(final_snapshot)
    probabilities = _pre_probabilities(context)

    if winner not in probabilities:
        raise PostmortemBlocked(
            f"official winner player_id={winner!r} is not in the PRE forecast field -- "
            "cannot evaluate a prediction that never covered the eventual winner"
        )

    prediction = make_prediction(
        target_event_id=context.game_code,
        target_game_code=context.game_code,
        target_start_date=context.start_date,
        raw_probabilities=probabilities,
        winner=winner,
        prior_events_n_by_player={},
    )
    summary = summarize_model(context.game_code, [prediction])

    output_path = context.artifact_path("postmortem_report")
    payload = {
        "schema_version": 1,
        "artifact": output_path.stem,
        "game_code": context.game_code,
        "tournament_name": context.tournament_name,
        "final_round_number": context.final_round_number,
        "winner": winner,
        "field_size": prediction.field_size,
        "log_loss": log_loss(prediction),
        "brier_norm": brier_norm(prediction),
        "winner_rank": winner_rank(prediction),
        "top5_hit": top_k_hit(prediction, 5),
        "top10_hit": top_k_hit(prediction, 10),
        "reciprocal_rank": reciprocal_rank(prediction),
        "pre_source": "pre_win_forecast",
        "final_source": f"r{context.final_round_number}_live_snapshot",
        "evaluation_library": "klpga.models.metrics",
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return PostmortemResult(
        game_code=context.game_code,
        tournament_name=context.tournament_name,
        prediction=prediction,
        log_loss=payload["log_loss"],
        brier_norm=payload["brier_norm"],
        winner_rank=payload["winner_rank"],
        top5_hit=payload["top5_hit"],
        top10_hit=payload["top10_hit"],
        reciprocal_rank=payload["reciprocal_rank"],
        summary=summary,
        output_path=output_path,
    )
