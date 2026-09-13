"""4R FINAL PRE-BUILD Phase 7: the machine-readable FINAL report.

Pure assembly over final_validator.run_final_validation +
final_course_deep_dive.connect_course_deep_dive -- computes nothing of
its own. STATUS is never PASS/VALIDATION_COMPLETE unless the validator
itself succeeded on real (non-synthetic) FINAL truth; a validator block
or a BLOCKED course connection is surfaced explicitly, never silently
dropped or replaced with a fabricated "n/a".
"""
from __future__ import annotations

from klpga.neo_win.final_course_deep_dive import connect_course_deep_dive
from klpga.neo_win.final_truth import load_final_truth
from klpga.neo_win.final_validator import (
    FinalValidationBlocked,
    biggest_surprises,
    run_final_validation,
)
from klpga.tournament_context import TournamentContext

STATUS_COMPLETE = "VALIDATION_COMPLETE"
STATUS_BLOCKED = "BLOCKED"
STATUS_PARTIAL = "PARTIAL"


def _surprise_to_dict(s) -> dict:
    return {
        "player_id": s.player_id,
        "player_name": s.player_name,
        "predicted_rank": s.predicted_rank,
        "final_rank": s.final_rank,
        "rank_delta": s.rank_delta,
        "win_probability": s.win_probability,
        "top5_probability": s.top5_probability,
        "top10_probability": s.top10_probability,
        "top20_probability": s.top20_probability,
        "actual_outcome": s.actual_outcome,
        "quadrant": s.quadrant,
    }


def build_final_report(context: TournamentContext) -> dict:
    try:
        result = run_final_validation(context)
    except FinalValidationBlocked as exc:
        return {
            "schema_version": "neo_final_report_v1",
            "game_code": context.game_code,
            "tournament_name": context.tournament_name,
            "status": STATUS_BLOCKED,
            "blocked_reason": str(exc),
        }

    truth = load_final_truth(context)
    winner_record = next(r for r in truth["records"] if str(r["player_id"]) == result.winner_player_id)
    positive, negative = biggest_surprises(result)

    deep_dive = connect_course_deep_dive(context)
    overall_status = STATUS_COMPLETE if deep_dive.status == "CONNECTED" else STATUS_PARTIAL

    findings_missed = []
    if deep_dive.status != "CONNECTED":
        findings_missed.append(
            "course Deep Dive connection unavailable (see COURSE_CONNECTION) -- "
            "no causal course/leaderboard claim is made without it"
        )

    return {
        "schema_version": "neo_final_report_v1",
        "game_code": context.game_code,
        "tournament_name": context.tournament_name,
        "status": overall_status,
        "event_summary": {
            "winner_player_id": result.winner_player_id,
            "winner_name": winner_record.get("player_name"),
            "winning_score": winner_record.get("final_score"),
            "runner_up": next(
                (r.get("player_name") for r in truth["records"] if str(r.get("final_rank")) == "2"),
                None,
            ),
            "field_status_counts": truth.get("status_counts"),
        },
        "neo_pre_final_forecast": {
            "top_candidates": sorted(
                [_surprise_to_dict(s) for s in result.surprises],
                key=lambda d: d["predicted_rank"],
            )[:5],
        },
        "forecast_performance": {
            "winner_hit": result.winner_hit,
            "winner_predicted_probability_pct": result.winner_predicted_probability_pct,
            "brier_norm": result.brier_norm,
            "log_loss": result.log_loss,
            "rank_mae": result.rank_mae,
            "top5_hit": result.top5_hit,
            "top10_hit": result.top10_hit,
            "top20_hit": result.top20_hit,
            "reciprocal_rank": result.reciprocal_rank,
            "field_size": result.field_size,
            "calibration": result.calibration,
            "calibration_note": result.calibration_note,
        },
        "biggest_positive_surprises": [_surprise_to_dict(s) for s in positive],
        "biggest_negative_surprises": [_surprise_to_dict(s) for s in negative],
        "course_connection": {
            "status": deep_dive.status,
            "reason": deep_dive.reason,
            "data": deep_dive.data,
        },
        "model_findings": {
            "well_predicted": [
                _surprise_to_dict(s) for s in result.surprises if s.quadrant == "A_NEO_HIGH_ACTUAL_HIGH"
            ][:5],
            "missed": [
                _surprise_to_dict(s) for s in result.surprises
                if s.quadrant in ("B_NEO_HIGH_ACTUAL_LOW", "C_NEO_LOW_ACTUAL_HIGH")
            ][:10],
            "not_determinable": findings_missed,
        },
        "status_note": (
            "PARTIAL: forecast-vs-actual validation is complete and real; only the course "
            "Deep Dive connection is unavailable" if overall_status == STATUS_PARTIAL else
            "all sections backed by real, joined forecast + FINAL truth data"
        ),
    }
