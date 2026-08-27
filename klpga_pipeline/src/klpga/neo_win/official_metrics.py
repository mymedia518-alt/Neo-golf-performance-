"""'Validated official performance metric' feature — built from
`official_metric_value` (the season-level KLPGA official record table,
klpga.discovery.season_metric_collector).

======================================================================
WHY "PRIOR SEASON", NEVER "CURRENT SEASON"
======================================================================
`official_metric_value` is a SEASON-level aggregate with no PIT
granularity — a season's row does not say which tournament within that
season it reflects data through (`pit_status` is hardcoded
`PIT_UNVERIFIED` for exactly this reason; see schema.sql section 8).
For a target tournament in season Y, using season Y's OWN official
metrics would risk leaking information from tournaments played AFTER
the target, whenever the target isn't the season's very first event.

Using season (Y-1) instead is unambiguously safe: a completed prior
season fully precedes every tournament in season Y, regardless of
where in season Y the target falls. This is the ONLY season alignment
this module ever uses — see `validate_official_metric_temporal_safety`
in klpga.neo_win.leakage for the automated check that enforces it.

======================================================================
WHY AN ORIENTATION ALLOWLIST, NOT AN ARBITRARY METRIC
======================================================================
Combining a feature into NEO WIN's equal-weight z-score sum (klpga.
neo_win.model) requires knowing whether a HIGHER raw value is better
or worse for winning — get this backwards and the model is silently,
confidently wrong. This project's standing rule is to never guess a
semantic. `_ORIENTATION_ALLOWLIST` below is therefore deliberately
short: every entry is an EXACT label copied verbatim from the real,
committed taxonomy (docs/discovery/KLPGA_RECORD_TAXONOMY_DISCOVERED.json)
whose higher/lower-is-better direction is unambiguous, universally-
understood golf terminology (distance, GIR%, fairways-hit%, putts) —
the same level of domain knowledge this project's own `response_schema.
classify_column_kind` already relies on to interpret "rate" columns.
Deliberately EXCLUDED: variant labels with a parenthetical context
suffix (e.g. "그린 적중률(RTP)", "그린 적중률(페어웨이)") — RTP is
already documented elsewhere in this project as a distinct concept, and
sub-context variants are not confirmed to share the base label's plain
meaning, so they are left out rather than assumed equivalent.

At feature-build time (`select_validated_official_metric`), the FIRST
allowlisted label with real, non-flagged, prior-season numeric values
for at least `MIN_PLAYER_COVERAGE` distinct players is used. If none of
the allowlisted labels are present with adequate coverage, the feature
is cleanly OMITTED for that run — the explicit "missing metric"
treatment for this feature: never guessed, never a different metric
silently substituted.
"""
from __future__ import annotations

import sqlite3

MIN_PLAYER_COVERAGE = 20
"""A deliberately modest, fixed floor (not tuned after seeing results)
— enough players for the shrinkage population statistics in klpga.
models.candidates-style fitting to be meaningful, not a claim about
full field coverage."""

_ORIENTATION_ALLOWLIST: tuple[tuple[str, str], ...] = (
    ("평균 티샷 거리", "higher_is_better"),
    ("그린 적중률", "higher_is_better"),
    ("페어웨이 안착률", "higher_is_better"),
    ("평균 퍼트 수", "lower_is_better"),
    ("평균 퍼트수", "lower_is_better"),
)


def build_prior_season_official_metrics(
    conn: sqlite3.Connection, prior_season: int, *, exclude_flagged: bool = True
) -> dict[str, dict[str, float]]:
    """Pivot: {player_code: {official_label: value}} for `prior_season`
    only. Non-numeric `value_raw` is silently excluded per row (not the
    whole player) — never a fabricated 0. `exclude_flagged=True` (the
    default) skips rows whose response was `validation_status =
    'FLAGGED'`: the real-evidence investigation behind this module
    found FLAGGED is dominated by a rank-column sentinel/tie artifact,
    not proven value corruption for every row, but this feature stays
    conservative and only draws from CLEAN responses — see
    docs/NEO_WIN_V0_1_METHODOLOGY.md for the full investigation."""
    query = (
        "SELECT player_code, official_label, value_raw FROM official_metric_value "
        "WHERE season = ?"
    )
    params: list = [prior_season]
    if exclude_flagged:
        query += " AND validation_status = 'CLEAN'"

    pivot: dict[str, dict[str, float]] = {}
    for player_code, official_label, value_raw in conn.execute(query, params):
        if value_raw is None:
            continue
        cleaned = str(value_raw).replace(",", "").strip()
        try:
            value = float(cleaned)
        except ValueError:
            continue
        pivot.setdefault(player_code, {})[official_label] = value
    return pivot


def select_validated_official_metric(
    pivot: dict[str, dict[str, float]], *, min_coverage: int = MIN_PLAYER_COVERAGE
) -> "tuple[str, str] | None":
    """Returns (official_label, orientation) for the first allowlisted
    metric with >= min_coverage distinct players present in `pivot`, or
    None if no allowlisted metric clears the bar — the explicit
    "feature omitted" outcome."""
    for label, orientation in _ORIENTATION_ALLOWLIST:
        coverage = sum(1 for player_metrics in pivot.values() if label in player_metrics)
        if coverage >= min_coverage:
            return label, orientation
    return None


def oriented_value(raw_value: float, orientation: str) -> float:
    """Flips sign so the result always follows this project's "lower is
    better" combined-score convention (klpga.models.candidates module
    docstring) — a higher raw value for a `higher_is_better` metric
    becomes a LOWER oriented value (more winning-favorable)."""
    return -raw_value if orientation == "higher_is_better" else raw_value
