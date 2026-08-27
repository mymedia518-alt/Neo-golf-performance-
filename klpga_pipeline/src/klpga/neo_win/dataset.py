"""Row builders for NEO WIN v0.1 — layers the new features
(klpga.neo_win.consistency, klpga.neo_win.official_metrics) onto rows
already shaped by the existing, unmodified backtest/inference machinery
(`build_walk_forward_dataset`, `klpga.models.inference._build_training_
rows`, `fetch_tournament_entry`), and resolves official_metric_value's
player_code identity space against player_master before ever joining on
it (klpga.neo_win.identity_resolution) — nothing here re-derives
point-in-time event/round filtering; every date check is delegated to
the already-tested primitives those functions already call.
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
from klpga.neo_win.identity_resolution import build_identity_alias_map
from klpga.neo_win.official_metrics import (
    FEATURE_NAME_BY_SLOT,
    build_prior_season_official_metrics,
    oriented_value,
    select_validated_official_metrics,
)


def _season_by_event(conn: sqlite3.Connection) -> dict[str, int]:
    return {event_id: season for event_id, season in conn.execute("SELECT event_id, season FROM tournament_master")}


class _OfficialMetricSource:
    """Caches per-(prior_season) pivots/slot-selections and the
    identity alias map across many row augmentations in one run — the
    alias map and each season's pivot are each computed once, not once
    per player-row."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._alias_report = build_identity_alias_map(conn)
        self._pivot_cache: dict[int, dict[str, dict[str, float]]] = {}
        self._selection_cache: dict[int, dict[str, tuple[str, str]]] = {}

    @property
    def alias_report(self) -> dict:
        return self._alias_report

    def slots_for_season(self, prior_season: int) -> tuple[dict[str, dict[str, float]], dict[str, tuple[str, str]]]:
        if prior_season not in self._pivot_cache:
            pivot = build_prior_season_official_metrics(
                self._conn, prior_season, alias_map=self._alias_report["alias_map"]
            )
            self._pivot_cache[prior_season] = pivot
            self._selection_cache[prior_season] = select_validated_official_metrics(pivot)
        return self._pivot_cache[prior_season], self._selection_cache[prior_season]

    def features_for_player(self, player_code: str, target_season: Optional[int]) -> dict:
        """Returns a dict of every neo_official_metric_<slot>(/_n)
        column plus official_metric_season, using ONLY the season
        strictly before `target_season`."""
        out: dict = {}
        official_season = target_season - 1 if target_season is not None else None
        pivot, selection = self.slots_for_season(official_season) if official_season is not None else ({}, {})
        player_metrics = pivot.get(player_code, {})
        for slot, feature_name in FEATURE_NAME_BY_SLOT.items():
            if slot in selection:
                identity_key, label, orientation = selection[slot]
                metric_key = (identity_key, label)
                if metric_key in player_metrics:
                    out[feature_name] = oriented_value(player_metrics[metric_key], orientation)
                    out[f"{feature_name}_n"] = 1
                    continue
            out[feature_name] = None
            out[f"{feature_name}_n"] = 0
        out["official_metric_season"] = official_season if selection else None
        return out


def augment_rows_with_neo_features(
    conn: sqlite3.Connection,
    rows: list[dict],
    corpus: Corpus,
    *,
    season_by_event: Optional[dict[str, int]] = None,
    official_metric_source: Optional[_OfficialMetricSource] = None,
) -> list[dict]:
    """`rows` must already have `target_event_id`, `target_start_date`
    (ISO date string), `player_code` — the shape `build_walk_forward_
    dataset`/`_build_training_rows` rows already have. Returns NEW dicts
    (never mutates `rows` in place) with `target_season`,
    `neo_consistency_stddev(_n)`, one `neo_official_metric_<slot>(_n)`
    per slot in klpga.neo_win.official_metrics.OFFICIAL_METRIC_SLOTS,
    and `official_metric_season` added."""
    if season_by_event is None:
        season_by_event = _season_by_event(conn)
    if official_metric_source is None:
        official_metric_source = _OfficialMetricSource(conn)

    augmented: list[dict] = []
    for row in rows:
        target_event_id = row["target_event_id"]
        target_season = season_by_event.get(target_event_id)
        target_effective_date = date.fromisoformat(row["target_start_date"])
        consistency, consistency_n = compute_consistency_feature(
            corpus, target_event_id, target_effective_date, row["player_code"]
        )

        new_row = dict(row)
        new_row["target_season"] = target_season
        new_row["neo_consistency_stddev"] = consistency
        new_row["neo_consistency_stddev_n"] = consistency_n
        new_row.update(official_metric_source.features_for_player(row["player_code"], target_season))
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
    the model needs, keyed by player_code."""
    corpus = load_corpus(conn)
    entrants = fetch_tournament_entry(conn, game_code)
    official_source = _OfficialMetricSource(conn)

    season_row = conn.execute("SELECT season FROM tournament_master WHERE game_code = ?", (game_code,)).fetchone()
    target_season = season_row[0] if season_row else cutoff_date_obj.year
    prior_season = target_season - 1
    _pivot, selection = official_source.slots_for_season(prior_season)

    field_rows: list[dict] = []
    for entrant in entrants:
        features = compute_point_in_time_features(
            corpus, game_code, cutoff_date_obj, entrant.player_code, entrant.player_name_display
        )
        flat = features_as_flat_dict(features)
        consistency, consistency_n = compute_consistency_feature(corpus, game_code, cutoff_date_obj, entrant.player_code)

        field_rows.append(
            {
                "player_code": entrant.player_code,
                "player_name": entrant.player_name_display,
                "in_player_master": entrant.in_player_master,
                "target_season": target_season,
                **flat,
                "neo_consistency_stddev": consistency,
                "neo_consistency_stddev_n": consistency_n,
                **official_source.features_for_player(entrant.player_code, target_season),
            }
        )

    return {
        "field_rows": field_rows,
        "entrants": entrants,
        "official_metric_context": {
            "target_season": target_season,
            "prior_season": prior_season,
            "selected_slots": {slot: label for slot, (_identity_key, label, _orientation) in selection.items()},
            "omitted_slots": [slot for slot in FEATURE_NAME_BY_SLOT if slot not in selection],
            "identity_resolution": {
                "direct_match_count": official_source.alias_report["direct_match_count"],
                "resolved_by_name_count": official_source.alias_report["resolved_by_name_count"],
                "unresolved_codes": official_source.alias_report["unresolved_codes"],
            },
        },
    }
