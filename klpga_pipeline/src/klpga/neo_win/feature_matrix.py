"""BETA #001-C Phase 5 — pre-tournament feature matrix. Combines the
EXISTING, unmodified NEO WIN v0.1 base features
(`klpga.neo_win.dataset.build_neo_win_live_field` — still the one and
only feature source BETA #001 uses, never touched here) with NEW
validated official-metric DOMAIN-aggregate features (neo_driving,
neo_approach, neo_short_game, neo_putting, neo_overall_skill), built
directly from `klpga.neo_win.metric_domain_map`'s usable_for_model gate
rather than `official_metrics.py`'s older 4-slot, first-candidate-wins
design — this keeps BETA #001's own pipeline (official_metrics.py,
archive.py, scripts/33) completely untouched (an explicit BETA #001-C
requirement) while still delivering one score per real golf domain.

======================================================================
neo_scoring IS DELIBERATELY ALWAYS None/EXCLUDED
======================================================================
The release's Phase 5 field list names `neo_scoring` alongside the
other five domain scores, but Phase 4's own instruction — "avoid
duplicate representations" — already ruled SCORING-domain official
metrics unusable specifically because `prior_avg_round_score_to_par`
(an existing base feature, from player_event results, not official_
metric_value) already represents career scoring. Adding a second,
official-metric scoring signal would be exactly the duplicate
representation problem the release warned against, so `neo_scoring`
stays present in the output shape (for a caller expecting the full
named field list) but is always `None`/`_n=0` for every player — never
silently dropped from the column list, never silently populated either.

======================================================================
NO FABRICATED ZEROS, NO THIN-DATA AVERAGING
======================================================================
A domain aggregate is the plain mean of the ORIENTED (oriented_value;
lower = more winning-favorable, this project's combined-score
convention) raw values of every metric in that domain that (a) `klpga.
neo_win.metric_domain_map.build_metric_feature_map` marked
usable_for_model=True, AND (b) clears MIN_PLAYER_COVERAGE distinct
players that season on its own (mirrors official_metrics.py's own
coverage floor — a thinly-covered metric is dropped from the domain
average entirely, never averaged in). A player with zero usable
metrics in a domain that season gets neo_<domain>=None, neo_<domain>_n=
0 — `apply_shrinkage_and_standardize` (klpga.models.candidates,
already used by klpga.neo_win.model) then shrinks that player fully to
the training fold's mean, exactly like every other optional feature in
this codebase. Never an imputed 0.
"""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Optional

from klpga.neo_win.dataset import build_neo_win_live_field
from klpga.neo_win.identity_resolution import build_identity_alias_map
from klpga.neo_win.metric_domain_map import (
    DOMAIN_APPROACH,
    DOMAIN_DRIVING,
    DOMAIN_OVERALL,
    DOMAIN_PUTTING,
    DOMAIN_SCORING,
    DOMAIN_SHORT_GAME,
    build_metric_feature_map,
)
from klpga.neo_win.official_metrics import MIN_PLAYER_COVERAGE, build_prior_season_official_metrics, oriented_value

DOMAIN_FEATURE_NAMES: dict[str, str] = {
    DOMAIN_DRIVING: "neo_driving",
    DOMAIN_APPROACH: "neo_approach",
    DOMAIN_SHORT_GAME: "neo_short_game",
    DOMAIN_PUTTING: "neo_putting",
    DOMAIN_SCORING: "neo_scoring",
    DOMAIN_OVERALL: "neo_overall_skill",
}


def usable_metrics_by_domain(taxonomy: dict, *, raw_samples_dir, season: str) -> dict[str, list[tuple[str, str, str]]]:
    """{domain: [(identity_key, official_label, direction), ...]} for
    every domain — only rows `build_metric_feature_map` marked
    usable_for_model=True, `season`-independent (it's a static
    allowlist derived from the taxonomy + identity mapping evidence,
    not from any season's actual values)."""
    rows = build_metric_feature_map(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    by_domain: dict[str, list[tuple[str, str, str]]] = {}
    for row in rows:
        if not row["usable_for_model"]:
            continue
        by_domain.setdefault(row["domain"], []).append((row["identity_key"], row["official_label"], row["direction"]))
    return by_domain


def compute_domain_aggregate_features(
    pivot: dict[str, dict[tuple[str, str], float]],
    usable_by_domain: dict[str, list[tuple[str, str, str]]],
    *,
    min_metric_coverage: int = MIN_PLAYER_COVERAGE,
) -> dict[str, dict]:
    """Returns {player_master_id: {neo_<domain>: float|None,
    neo_<domain>_n: int, ...}} for every domain in
    DOMAIN_FEATURE_NAMES, keyed over every player appearing anywhere in
    `pivot` (build_prior_season_official_metrics's output — already
    identity-resolved)."""
    out: dict[str, dict] = {player_code: {} for player_code in pivot}
    for domain, feature_name in DOMAIN_FEATURE_NAMES.items():
        if domain == DOMAIN_SCORING:
            for player_code in pivot:
                out[player_code][feature_name] = None
                out[player_code][f"{feature_name}_n"] = 0
            continue

        candidates = usable_by_domain.get(domain, [])
        adequate = [
            (identity_key, label, direction)
            for identity_key, label, direction in candidates
            if sum(1 for player_metrics in pivot.values() if (identity_key, label) in player_metrics)
            >= min_metric_coverage
        ]
        for player_code, player_metrics in pivot.items():
            values = [
                oriented_value(player_metrics[(identity_key, label)], direction)
                for identity_key, label, direction in adequate
                if (identity_key, label) in player_metrics
            ]
            if values:
                out[player_code][feature_name] = sum(values) / len(values)
                out[player_code][f"{feature_name}_n"] = len(values)
            else:
                out[player_code][feature_name] = None
                out[player_code][f"{feature_name}_n"] = 0
    return out


_EMPTY_DOMAIN_ROW: dict = {}
for _domain_name, _feature_name in DOMAIN_FEATURE_NAMES.items():
    _EMPTY_DOMAIN_ROW[_feature_name] = None
    _EMPTY_DOMAIN_ROW[f"{_feature_name}_n"] = 0


def build_beta001c_feature_matrix(
    conn: sqlite3.Connection,
    game_code: str,
    cutoff_date_obj: date,
    *,
    taxonomy: dict,
    raw_samples_dir,
    min_metric_coverage: int = MIN_PLAYER_COVERAGE,
) -> dict:
    """Returns {"field_rows": [one dict per field player — every
    existing NEO WIN v0.1 base-feature key PLUS neo_driving/_approach/
    _short_game/_putting/_scoring/_overall_skill(/_n)], "coverage":
    {domain: {"feature_name", "metrics_used", "players_with_data",
    "field_size"}}, "target_season", "prior_season"}. `field_rows`
    order matches `klpga.neo_win.dataset.build_neo_win_live_field`'s
    (the live tournament_entry field, unchanged)."""
    live_field = build_neo_win_live_field(conn, game_code, cutoff_date_obj)
    target_season = live_field["official_metric_context"]["target_season"]
    prior_season = live_field["official_metric_context"]["prior_season"]

    alias_report = build_identity_alias_map(conn)
    pivot = build_prior_season_official_metrics(conn, prior_season, alias_map=alias_report["alias_map"])
    by_domain = usable_metrics_by_domain(taxonomy, raw_samples_dir=raw_samples_dir, season=str(prior_season))
    domain_features = compute_domain_aggregate_features(pivot, by_domain, min_metric_coverage=min_metric_coverage)

    field_rows: list[dict] = []
    for row in live_field["field_rows"]:
        merged = dict(row)
        merged.update(domain_features.get(row["player_code"], _EMPTY_DOMAIN_ROW))
        field_rows.append(merged)

    field_size = len(field_rows)
    coverage: dict[str, dict] = {}
    for domain, feature_name in DOMAIN_FEATURE_NAMES.items():
        players_with_data = sum(1 for r in field_rows if r.get(f"{feature_name}_n"))
        coverage[domain] = {
            "feature_name": feature_name,
            "metrics_used": (
                [] if domain == DOMAIN_SCORING else [f"{ik}|{label}" for ik, label, _d in by_domain.get(domain, [])]
            ),
            "players_with_data": players_with_data,
            "field_size": field_size,
        }

    return {
        "field_rows": field_rows,
        "coverage": coverage,
        "official_metric_context": live_field["official_metric_context"],
        "target_season": target_season,
        "prior_season": prior_season,
    }
