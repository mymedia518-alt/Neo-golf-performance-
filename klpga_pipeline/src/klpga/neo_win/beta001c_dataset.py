"""BETA #001-C row builder — layers Phase 5's domain-aggregate official-
metric features (klpga.neo_win.feature_matrix) and Phase 6's win-feature
candidates (klpga.neo_win.win_features) onto the SAME walk-forward rows
`klpga.backtest.walk_forward.build_walk_forward_dataset` already
produces, exactly the way `klpga.neo_win.dataset.augment_rows_with_neo_
features` layers BETA #001's own features on top of the identical base
— that module is untouched; this is a parallel, independent builder so
BETA #001's own pipeline never changes as a side effect of #001-C work.

Also defines the three MODEL_*_FEATURES tuples Phase 7's backtest
compares:
  MODEL_A_FEATURES = BASE_FEATURES only (the original NEO WIN v0.1 set)
  MODEL_B_FEATURES = A + the 5 domain-aggregate official-metric features
                      (neo_scoring excluded — see feature_matrix.py)
  MODEL_C_FEATURES = B + the 5 win-feature candidates (klpga.neo_win.
                      win_features) — ALL five together, not a hand-
                      picked subset, to avoid any hindsight selection
                      of "whichever one makes a particular player's
                      number look right."
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from klpga.backtest.point_in_time_features import Corpus, load_corpus
from klpga.models.inference import _build_training_rows
from klpga.neo_win.consistency import compute_consistency_feature
from klpga.neo_win.feature_matrix import (
    DOMAIN_APPROACH,
    DOMAIN_DRIVING,
    DOMAIN_FEATURE_NAMES,
    DOMAIN_OVERALL,
    DOMAIN_PUTTING,
    DOMAIN_SHORT_GAME,
    build_beta001c_feature_matrix,
    compute_domain_aggregate_features,
    usable_metrics_by_domain,
)
from klpga.neo_win.identity_resolution import build_identity_alias_map
from klpga.neo_win.model import BASE_FEATURES
from klpga.neo_win.official_metrics import build_prior_season_official_metrics
from klpga.neo_win.win_features import (
    WIN_FEATURE_CANDIDATE_NAMES,
    compute_win_feature_candidates,
    season_by_event as _season_by_event,
)

DOMAIN_METRIC_FEATURE_NAMES: tuple[str, ...] = tuple(
    DOMAIN_FEATURE_NAMES[d] for d in (DOMAIN_DRIVING, DOMAIN_APPROACH, DOMAIN_SHORT_GAME, DOMAIN_PUTTING, DOMAIN_OVERALL)
)
"""Deliberately excludes neo_scoring — always None (duplicate
representation guard, feature_matrix.py) so including it as a "real"
feature column would only ever contribute a wasted, always-zero
shrinkage term."""

MODEL_A_FEATURES: tuple[str, ...] = BASE_FEATURES
MODEL_B_FEATURES: tuple[str, ...] = BASE_FEATURES + DOMAIN_METRIC_FEATURE_NAMES
MODEL_C_FEATURES: tuple[str, ...] = MODEL_B_FEATURES + WIN_FEATURE_CANDIDATE_NAMES

_EMPTY_DOMAIN_ROW: dict = {}
for _fn in DOMAIN_FEATURE_NAMES.values():
    _EMPTY_DOMAIN_ROW[_fn] = None
    _EMPTY_DOMAIN_ROW[f"{_fn}_n"] = 0


class _DomainFeatureSource:
    """Caches per-prior-season pivots/domain-aggregates across many row
    augmentations in one backtest run (potentially hundreds of target
    tournaments) — the taxonomy-derived usable-metric allowlist is
    season-independent and computed once; each season's official-metric
    pivot and domain aggregate is computed once, not once per row."""

    def __init__(self, conn: sqlite3.Connection, *, taxonomy: dict, raw_samples_dir):
        self._conn = conn
        self._taxonomy = taxonomy
        self._raw_samples_dir = raw_samples_dir
        self._alias_report = build_identity_alias_map(conn)
        self._usable_by_domain_cache: dict[str, dict] = {}
        self._domain_features_cache: dict[int, dict] = {}

    def _usable_by_domain(self, season: int) -> dict:
        key = str(season)
        if key not in self._usable_by_domain_cache:
            self._usable_by_domain_cache[key] = usable_metrics_by_domain(
                self._taxonomy, raw_samples_dir=self._raw_samples_dir, season=key
            )
        return self._usable_by_domain_cache[key]

    def features_for_season(self, prior_season: Optional[int]) -> dict:
        if prior_season is None:
            return {}
        if prior_season not in self._domain_features_cache:
            pivot = build_prior_season_official_metrics(
                self._conn, prior_season, alias_map=self._alias_report["alias_map"]
            )
            by_domain = self._usable_by_domain(prior_season)
            self._domain_features_cache[prior_season] = compute_domain_aggregate_features(pivot, by_domain)
        return self._domain_features_cache[prior_season]

    def features_for_player(self, player_code: str, target_season: Optional[int]) -> dict:
        prior_season = target_season - 1 if target_season is not None else None
        season_features = self.features_for_season(prior_season)
        return dict(season_features.get(player_code, _EMPTY_DOMAIN_ROW))


def augment_rows_with_beta001c_features(
    conn: sqlite3.Connection,
    rows: list[dict],
    corpus: Corpus,
    *,
    taxonomy: dict,
    raw_samples_dir,
    season_by_event_map: Optional[dict[str, int]] = None,
    domain_source: Optional[_DomainFeatureSource] = None,
) -> list[dict]:
    """`rows` must already have `target_event_id`, `target_start_date`,
    `player_code` (klpga.backtest.walk_forward.build_walk_forward_
    dataset's own row shape). Returns NEW dicts (never mutates `rows`)
    with target_season, neo_consistency_stddev(_n), every
    DOMAIN_METRIC_FEATURE_NAMES entry(_n), and every WIN_FEATURE_
    CANDIDATE_NAMES entry(_n) added."""
    if season_by_event_map is None:
        season_by_event_map = _season_by_event(conn)
    if domain_source is None:
        domain_source = _DomainFeatureSource(conn, taxonomy=taxonomy, raw_samples_dir=raw_samples_dir)

    augmented: list[dict] = []
    for row in rows:
        target_event_id = row["target_event_id"]
        target_season = season_by_event_map.get(target_event_id)
        target_effective_date = date.fromisoformat(row["target_start_date"])
        player_code = row["player_code"]

        consistency, consistency_n = compute_consistency_feature(
            corpus, target_event_id, target_effective_date, player_code
        )

        new_row = dict(row)
        new_row["target_season"] = target_season
        new_row["neo_consistency_stddev"] = consistency
        new_row["neo_consistency_stddev_n"] = consistency_n
        new_row.update(domain_source.features_for_player(player_code, target_season))
        new_row.update(
            compute_win_feature_candidates(
                corpus, target_event_id, target_effective_date, target_season, player_code, season_by_event_map
            )
        )
        augmented.append(new_row)
    return augmented


def build_beta001c_live_training_rows(
    conn: sqlite3.Connection,
    game_code: str,
    cutoff_date_obj: date,
    *,
    taxonomy: dict,
    raw_samples_dir,
) -> tuple[list[dict], int]:
    """Training rows for a LIVE #001-C prediction — reuses `klpga.
    models.inference._build_training_rows` (already imported,
    unmodified, by klpga.neo_win.dataset.build_neo_win_live_training_
    rows for the same reason: it is the one place that correctly
    excludes both the target game_code and every tournament on/after
    cutoff_date_obj) plus this module's own augmentation."""
    corpus = load_corpus(conn)
    training_rows, training_tournament_count = _build_training_rows(conn, game_code, cutoff_date_obj)
    augmented = augment_rows_with_beta001c_features(
        conn, training_rows, corpus, taxonomy=taxonomy, raw_samples_dir=raw_samples_dir
    )
    return augmented, training_tournament_count


def build_beta001c_live_field(
    conn: sqlite3.Connection,
    game_code: str,
    cutoff_date_obj: date,
    *,
    taxonomy: dict,
    raw_samples_dir,
) -> dict:
    """The live-tournament-field counterpart to `augment_rows_with_
    beta001c_features` (that function augments many historical WALK-
    FORWARD rows; this augments the CURRENT tournament's own field) —
    layers Phase 6's win-feature candidates on top of Phase 5's
    `build_beta001c_feature_matrix` (base + domain-aggregate features),
    so a Phase 9 live prediction can use MODEL_C_FEATURES (or any of
    MODEL_A/B_FEATURES) exactly like a training row can. Returns the
    same shape as `build_beta001c_feature_matrix`, with every
    WIN_FEATURE_CANDIDATE_NAMES key(_n) added to every `field_rows`
    entry."""
    matrix_result = build_beta001c_feature_matrix(
        conn, game_code, cutoff_date_obj, taxonomy=taxonomy, raw_samples_dir=raw_samples_dir
    )
    corpus = load_corpus(conn)
    season_by_event_map = _season_by_event(conn)
    target_season = matrix_result["target_season"]

    field_rows: list[dict] = []
    for row in matrix_result["field_rows"]:
        merged = dict(row)
        merged.update(
            compute_win_feature_candidates(
                corpus, game_code, cutoff_date_obj, target_season, row["player_code"], season_by_event_map
            )
        )
        field_rows.append(merged)

    return {**matrix_result, "field_rows": field_rows}
