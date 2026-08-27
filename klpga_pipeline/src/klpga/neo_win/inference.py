"""NEO WIN v0.1 — the single entry point that ties fitting, live-field
prediction, invariant/leakage validation, and reporting together. Reads
`tournament_entry`, `player_event`, `player_round`, `tournament_master`,
`player_master`, `official_metric_value` — never writes to any of them.
See docs/NEO_WIN_V0_1_METHODOLOGY.md for the full design writeup.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Optional

from klpga.backtest.point_in_time_features import load_corpus
from klpga.models.inference import LiveFieldEntrant, fetch_tournament_entry, resolve_cutoff_date, resolve_tournament_name

from klpga.neo_win.dataset import build_neo_win_live_field, build_neo_win_live_training_rows
from klpga.neo_win.leakage import (
    validate_official_metric_temporal_safety,
    validate_pit_feature_leakage,
    validate_probability_sum,
)
from klpga.neo_win.model import MODEL_ID, fit_neo_win_model, predict_neo_win_model


@dataclass(frozen=True)
class NeoWinEntrantPrediction:
    rank: int
    player_code: str
    player_name: str
    win_probability: float
    prior_events_n: int
    prior_avg_round_score_to_par: Optional[float]
    prior_recent_form_10: Optional[float]
    prior_recent_form_10_n: int
    neo_consistency_stddev: Optional[float]
    neo_consistency_stddev_n: int
    neo_official_metric: Optional[float]
    neo_official_metric_n: int
    is_unmatched: bool


@dataclass(frozen=True)
class NeoWinInferenceResult:
    game_code: str
    tournament_name: Optional[str]
    tournament_name_source: str
    field_size: int
    cutoff_date: str
    cutoff_date_source: str
    training_tournament_count: int
    model_id: str
    model_features: tuple[str, ...]
    predictions: tuple[NeoWinEntrantPrediction, ...]
    sum_probability: float
    min_probability: float
    max_probability: float
    zero_history_count: int
    unmatched_count: int
    predicted_count: int
    entrants_parsed: int
    dropped_entrants: int
    official_metric_context: dict
    leakage_validation: dict
    missing_data_report: dict


def run_neo_win_inference(
    conn: sqlite3.Connection,
    game_code: str,
    cutoff_date_arg: Optional[str] = None,
    tournament_name_arg: Optional[str] = None,
) -> NeoWinInferenceResult:
    """Read-only. Raises ValueError if `tournament_entry` has zero rows
    for `game_code` (same hard failure `fetch_tournament_entry` already
    raises — never silently predicts an empty field)."""
    entrants: list[LiveFieldEntrant] = fetch_tournament_entry(conn, game_code)
    entrants_parsed = len(entrants)

    cutoff_date_str, cutoff_source = resolve_cutoff_date(conn, game_code, cutoff_date_arg)
    cutoff_date_obj = date.fromisoformat(cutoff_date_str)
    tournament_name, tournament_name_source = resolve_tournament_name(conn, game_code, tournament_name_arg)

    training_rows, training_tournament_count = build_neo_win_live_training_rows(conn, game_code, cutoff_date_obj)
    fitted = fit_neo_win_model(training_rows)

    field_data = build_neo_win_live_field(conn, game_code, cutoff_date_obj)
    field_rows = field_data["field_rows"]
    official_metric_context = field_data["official_metric_context"]

    raw_probs = predict_neo_win_model(fitted, field_rows)

    expected_codes = {row["player_code"] for row in field_rows}
    actual_codes = set(raw_probs.keys())
    if actual_codes != expected_codes:
        raise RuntimeError(
            f"NEO WIN v0.1 invariant violation: predicted player_codes {actual_codes} "
            f"!= field player_codes {expected_codes}"
        )

    corpus = load_corpus(conn)
    leakage_violations: list[str] = []
    for row in field_rows:
        leakage_violations.extend(
            validate_pit_feature_leakage(corpus, game_code, cutoff_date_obj, row["player_code"])
        )
    leakage_violations.extend(
        validate_official_metric_temporal_safety(
            [
                {
                    "target_event_id": game_code,
                    "player_code": row["player_code"],
                    "target_season": row["target_season"],
                    "official_metric_season": row["official_metric_season"],
                }
                for row in field_rows
            ]
        )
    )
    leakage_violations.extend(validate_probability_sum(raw_probs))

    ordered = sorted(field_rows, key=lambda row: (-raw_probs[row["player_code"]], row["player_code"]))
    predictions: list[NeoWinEntrantPrediction] = []
    zero_history_count = 0
    unmatched_count = 0
    missing_official_metric_count = 0
    missing_consistency_count = 0
    for rank, row in enumerate(ordered, start=1):
        n = row["prior_events_n"]
        if n == 0:
            zero_history_count += 1
        if not row["in_player_master"]:
            unmatched_count += 1
        if row["neo_official_metric_n"] == 0:
            missing_official_metric_count += 1
        if row["neo_consistency_stddev_n"] < 2:
            missing_consistency_count += 1
        predictions.append(
            NeoWinEntrantPrediction(
                rank=rank,
                player_code=row["player_code"],
                player_name=row["player_name"],
                win_probability=raw_probs[row["player_code"]],
                prior_events_n=n,
                prior_avg_round_score_to_par=row["prior_avg_round_score_to_par"],
                prior_recent_form_10=row["prior_recent_form_10"],
                prior_recent_form_10_n=row["prior_recent_form_10_n"],
                neo_consistency_stddev=row["neo_consistency_stddev"],
                neo_consistency_stddev_n=row["neo_consistency_stddev_n"],
                neo_official_metric=row["neo_official_metric"],
                neo_official_metric_n=row["neo_official_metric_n"],
                is_unmatched=not row["in_player_master"],
            )
        )

    missing_data_report = {
        "zero_prior_events_count": zero_history_count,
        "missing_consistency_feature_count": missing_consistency_count,
        "missing_official_metric_count": missing_official_metric_count,
        "official_metric_feature_omitted_entirely": official_metric_context["official_metric_label"] is None,
        "unmatched_player_master_count": unmatched_count,
        "field_size": len(field_rows),
    }

    probs_values = list(raw_probs.values())
    return NeoWinInferenceResult(
        game_code=game_code,
        tournament_name=tournament_name,
        tournament_name_source=tournament_name_source,
        field_size=len(field_rows),
        cutoff_date=cutoff_date_str,
        cutoff_date_source=cutoff_source,
        training_tournament_count=training_tournament_count,
        model_id=MODEL_ID,
        model_features=fitted.feature_columns,
        predictions=tuple(predictions),
        sum_probability=sum(probs_values),
        min_probability=min(probs_values),
        max_probability=max(probs_values),
        zero_history_count=zero_history_count,
        unmatched_count=unmatched_count,
        predicted_count=len(predictions),
        entrants_parsed=entrants_parsed,
        dropped_entrants=entrants_parsed - len(predictions),
        official_metric_context=official_metric_context,
        leakage_validation={"violations": leakage_violations, "clean": len(leakage_violations) == 0},
        missing_data_report=missing_data_report,
    )
