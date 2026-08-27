"""'Validated official performance metric' features — built from
`official_metric_value` (the season-level KLPGA official record table,
klpga.discovery.season_metric_collector).

======================================================================
WHY "PRIOR SEASON", NEVER "CURRENT SEASON"
======================================================================
`official_metric_value` is a SEASON-level aggregate with no PIT
granularity — a season's row does not say which tournament within that
season it reflects data through (`pit_status` is hardcoded
`PIT_UNVERIFIED`; see schema.sql section 8). For a target tournament in
season Y, using season Y's OWN official metrics would risk leaking
information from tournaments played AFTER the target. Season (Y-1)
is unambiguously safe: a completed prior season fully precedes every
tournament in season Y. This is the ONLY season alignment this module
ever uses — see `validate_official_metric_temporal_safety` in
klpga.neo_win.leakage for the automated check enforcing it.

======================================================================
FOUR NAMED SKILL SLOTS, NOT "ALL AVAILABLE METRICS"
======================================================================
Round 15 (this module) expands from a single official-metric feature to
FOUR, one per golf skill dimension — "Prefer... SG Total, Tee, Approach,
Around, Putting, GIR" per the explicit release request — while still
refusing to "pretend every one of the 248 identities is an independent
predictive variable" or include duplicate representations of the same
skill (e.g. never both SG-Approach and raw GIR% in the same run: within
a slot, only the FIRST candidate with adequate coverage is used, the
rest of that slot's candidates are simply not needed).

Each slot has its own ordered candidate list (Strokes Gained preferred
when present — it's already opponent-relative and error-adjusted — with
a raw-stat fallback):

  overall_skill: SG Total only (no raw-stat equivalent exists)
  driving:       SG Tee -> average tee shot distance
  short_game:    SG Approach -> SG Around-the-green -> GIR%
  putting:       SG Putting -> average putts

At feature-build time, EVERY slot independently checks real, non-
flagged, prior-season coverage against `MIN_PLAYER_COVERAGE` before
being included — a slot with no qualifying candidate contributes
NOTHING (explicit omission, the missing-metric treatment for this
feature family: never guessed, never a different metric silently
substituted). Every label is an EXACT string copied verbatim from the
real, committed taxonomy (docs/discovery/KLPGA_RECORD_TAXONOMY_
DISCOVERED.json) — deliberately excluding parenthetical-context
variants (e.g. "그린 적중률(RTP)") not confirmed to share the base
label's meaning. Orientation ("higher_is_better"/"lower_is_better") is
universal, unambiguous golf terminology (Strokes Gained: higher always
better by definition; distance/GIR%/fairway%: higher better; putts:
lower better) — the same level of domain knowledge this project's own
`response_schema.classify_column_kind` already relies on.
"""
from __future__ import annotations

import sqlite3

MIN_PLAYER_COVERAGE = 20
"""A deliberately modest, fixed floor (not tuned after seeing results)
— enough players for shrinkage population statistics to be meaningful,
not a claim about full field coverage."""

# name -> ordered (label, orientation) candidates, first-with-coverage wins.
OFFICIAL_METRIC_SLOTS: "dict[str, tuple[tuple[str, str], ...]]" = {
    "overall_skill": (("SG : 전체", "higher_is_better"),),
    "driving": (
        ("SG : 티샷", "higher_is_better"),
        ("평균 티샷 거리", "higher_is_better"),
    ),
    "short_game": (
        ("SG : 어프로치", "higher_is_better"),
        ("SG : 그린주변", "higher_is_better"),
        ("그린 적중률", "higher_is_better"),
    ),
    "putting": (
        ("SG : 퍼팅", "higher_is_better"),
        ("평균 퍼트 수", "lower_is_better"),
        ("평균 퍼트수", "lower_is_better"),
    ),
}

FEATURE_NAME_BY_SLOT: dict[str, str] = {slot: f"neo_official_metric_{slot}" for slot in OFFICIAL_METRIC_SLOTS}


def build_prior_season_official_metrics(
    conn: sqlite3.Connection,
    prior_season: int,
    *,
    exclude_flagged: bool = True,
    alias_map: "dict[str, str] | None" = None,
) -> dict[str, dict[str, float]]:
    """Pivot: {player_master_id: {official_label: value}} for
    `prior_season` only. Non-numeric `value_raw` is silently excluded
    per row (not the whole player) — never a fabricated 0.
    `exclude_flagged=True` (the default) skips rows whose response was
    `validation_status = 'FLAGGED'`: real-evidence investigation
    (docs/NEO_WIN_V0_1_METHODOLOGY.md) found FLAGGED is dominated by a
    rank-column duplicate/sentinel artifact, not proven value
    corruption for every row, but this feature family stays
    conservative and only draws from CLEAN responses.

    `alias_map` (from klpga.neo_win.identity_resolution.build_identity_
    alias_map) re-keys each row from its raw `official_metric_value.
    player_code` to the RESOLVED `player_master.player_id` — a code
    with NO entry in `alias_map` (genuinely unresolved) is dropped from
    the pivot, never guessed. Omit `alias_map` to key by the raw code
    directly (only safe when the caller has independently confirmed
    identity-space equality for the codes it will look up)."""
    query = "SELECT player_code, official_label, value_raw FROM official_metric_value WHERE season = ?"
    params: list = [prior_season]
    if exclude_flagged:
        query += " AND validation_status = 'CLEAN'"

    pivot: dict[str, dict[str, float]] = {}
    for player_code, official_label, value_raw in conn.execute(query, params):
        if value_raw is None:
            continue
        if alias_map is not None:
            resolved_id = alias_map.get(player_code)
            if resolved_id is None:
                continue
        else:
            resolved_id = player_code
        cleaned = str(value_raw).replace(",", "").strip()
        try:
            value = float(cleaned)
        except ValueError:
            continue
        pivot.setdefault(resolved_id, {})[official_label] = value
    return pivot


def select_validated_official_metrics(
    pivot: dict[str, dict[str, float]], *, min_coverage: int = MIN_PLAYER_COVERAGE
) -> dict[str, tuple[str, str]]:
    """Returns {slot_name: (official_label, orientation)} for every
    slot with at least one candidate clearing `min_coverage` distinct
    players in `pivot`. A slot absent from the result contributed
    nothing this run — the explicit "feature omitted" outcome, never a
    guess."""
    selected: dict[str, tuple[str, str]] = {}
    for slot, candidates in OFFICIAL_METRIC_SLOTS.items():
        for label, orientation in candidates:
            coverage = sum(1 for player_metrics in pivot.values() if label in player_metrics)
            if coverage >= min_coverage:
                selected[slot] = (label, orientation)
                break
    return selected


def oriented_value(raw_value: float, orientation: str) -> float:
    """Flips sign so the result always follows this project's "lower is
    better" combined-score convention (klpga.models.candidates module
    docstring) — a higher raw value for a `higher_is_better` metric
    becomes a LOWER oriented value (more winning-favorable)."""
    return -raw_value if orientation == "higher_is_better" else raw_value
