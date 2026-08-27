"""Row builders for NEO WIN v0.1 — layers the two new features
(klpga.neo_win.consistency, klpga.neo_win.official_metrics) onto rows
already shaped by the existing, unmodified backtest/inference machinery
(`build_walk_forward_dataset`, `klpga.models.inference._build_training_
rows`, `fetch_tournament_entry`). Nothing here re-derives point-in-time
event/round filtering — every date check is delegated to the already-
tested primitives those functions already call.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from klpga.backtest.point_in_time_features import (
    Corpus,
    compute_point_in_time_features,
    features_as_flat_dict,
    load_corpus,
)
from klpga.backtest.walk_forward import build_walk_forward_dataset
from klpga.models.inference import _build_training_rows, fetch_tournament_entry

from klpga.neo_win.consistency import compute_consistency_feature
from klpga.neo_win.official_metrics import build_prior_season_official_metrics, oriented_value, select_validated_official_metric


def _season_by_event(conn: sqlite3.Connection) -> dict[str, int]:
    return {event_id: season for event_id, season in conn.execute("SELECT event_id, season FROM tournament_master")}


def augment_rows_with_neo_features(
    conn: sqlite3.Connection, rows: list[dict], corpus: Corpus, *, season_by_event: Optional[dict[str, int]] = None
) -> list[dict]:
    """`rows` must already have `target_event_id`, `target_start_date`
    (ISO date string), `player_code` — the shape `build_walk_forward_
    dataset`/`_build_training_rows` rows already have. Returns NEW dicts
    (never mutates `rows` in place) with `target_season`,
    `neo_consistency_stddev(_n)`, `neo_official_metric(_n)`,
    `official_metric_season` added."""
    if season_by_event is None:
        season_by_event = _season_by_event(conn)

    pivot_cache: dict[int, dict[str, dict[str, float]]] = {}
    selection_cache: dict[int, "tuple[str, str] | None"] = {}

    augmented: list[dict] = []
    for row in rows:
        target_event_id = row["target_event_id"]
        target_season = season_by_event.get(target_event_id)
        target_effective_date = date.fromisoformat(row["target_start_date"])
        consistency, consistency_n = compute_consistency_feature(
            corpus, target_event_id, target_effective_date, row["player_code"]
        )

        official_value: Optional[float] = None
        official_n = 0
        official_season: Optional[int] = None
        if target_season is not None:
            prior_season = target_season - 1
            if prior_season not in pivot_cache:
                pivot_cache[prior_season] = build_prior_season_official_metrics(conn, prior_season)
                selection_cache[prior_season] = select_validated_official_metric(pivot_cache[prior_season])
            selection = selection_cache[prior_season]
            if selection is not None:
                label, orientation = selection
                player_metrics = pivot_cache[prior_season].get(row["player_code"], {})
                if label in player_metrics:
                    official_value = oriented_value(player_metrics[label], orientation)
                    official_n = 1
                    official_season = prior_season

        new_row = dict(row)
        new_row.update(
            {
                "target_season": target_season,
                "neo_consistency_stddev": consistency,
                "neo_consistency_stddev_n": consistency_n,
                "neo_official_metric": official_value,
                "neo_official_metric_n": official_n,
                "official_metric_season": official_season,
            }
        )
        augmented.append(new_row)
    return augmented


def build_neo_win_training_rows(conn: sqlite3.Connection) -> tuple[list[dict], int]:
    """Full-corpus training rows (every usable historical tournament) —
    used only for offline evaluation/reporting, NOT for a live
    prediction (see build_neo_win_live_training_rows for the cutoff-
    restricted version a real prediction must use)."""
    corpus = load_corpus(conn)
    wf_result = build_walk_forward_dataset(conn, corpus=corpus)
    augmented = augment_rows_with_neo_features(conn, wf_result.rows, corpus)
    return augmented, wf_result.total_tournament_count


def build_neo_win_live_training_rows(
    conn: sqlite3.Connection, game_code: str, cutoff_date_obj: date
) -> tuple[list[dict], int]:
    """Training rows for a LIVE prediction — reuses `klpga.models.
    inference._build_training_rows` (already imported, unmodified, by
    klpga.archive.prediction_archive for the same reason: it is the
    one place that correctly excludes both the target game_code and
    every tournament on/after cutoff_date_obj)."""
    corpus = load_corpus(conn)
    training_rows, training_tournament_count = _build_training_rows(conn, game_code, cutoff_date_obj)
    augmented = augment_rows_with_neo_features(conn, training_rows, corpus)
    return augmented, training_tournament_count


def build_neo_win_live_field(conn: sqlite3.Connection, game_code: str, cutoff_date_obj: date) -> dict:
    """Returns {"field_rows": [...], "entrants": [LiveFieldEntrant,...],
    "official_metric_context": {...}}. `field_rows` carry every feature
    NEO_WIN_FEATURES needs, keyed by player_code."""
    corpus = load_corpus(conn)
    entrants = fetch_tournament_entry(conn, game_code)

    season_row = conn.execute("SELECT season FROM tournament_master WHERE game_code = ?", (game_code,)).fetchone()
    target_season = season_row[0] if season_row else cutoff_date_obj.year
    prior_season = target_season - 1
    pivot = build_prior_season_official_metrics(conn, prior_season)
    selection = select_validated_official_metric(pivot)

    field_rows: list[dict] = []
    for entrant in entrants:
        features = compute_point_in_time_features(
            corpus, game_code, cutoff_date_obj, entrant.player_code, entrant.player_name_display
        )
        flat = features_as_flat_dict(features)
        consistency, consistency_n = compute_consistency_feature(corpus, game_code, cutoff_date_obj, entrant.player_code)

        official_value: Optional[float] = None
        official_n = 0
        official_season: Optional[int] = None
        if selection is not None:
            label, orientation = selection
            player_metrics = pivot.get(entrant.player_code, {})
            if label in player_metrics:
                official_value = oriented_value(player_metrics[label], orientation)
                official_n = 1
                official_season = prior_season

        field_rows.append(
            {
                "player_code": entrant.player_code,
                "player_name": entrant.player_name_display,
                "in_player_master": entrant.in_player_master,
                "target_season": target_season,
                **flat,
                "neo_consistency_stddev": consistency,
                "neo_consistency_stddev_n": consistency_n,
                "neo_official_metric": official_value,
                "neo_official_metric_n": official_n,
                "official_metric_season": official_season,
            }
        )

    return {
        "field_rows": field_rows,
        "entrants": entrants,
        "official_metric_context": {
            "target_season": target_season,
            "prior_season": prior_season,
            "official_metric_label": selection[0] if selection else None,
            "official_metric_orientation": selection[1] if selection else None,
            "official_metric_player_coverage": len(pivot),
        },
    }
