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
Expands from a single official-metric feature to FOUR, one per golf
skill dimension, while still refusing to "pretend every one of the 248
identities is an independent predictive variable" or include duplicate
representations of the same skill (within a slot, only the FIRST
candidate with adequate coverage is used).

======================================================================
BETA #001-C FIX — candidates are pinned to a specific identity_key,
never a bare label string
======================================================================
Cross-referencing this allowlist against `klpga.neo_win.metric_domain_
map`'s full 281-metric classification surfaced a real bug: the label
"평균 티샷 거리" is NOT globally unique — it appears at THREE distinct
identity_keys (`Tee::Tee01::010101`, `Tee::Tee03::010201`, `Tee::
Tee05::010301`), because KLPGA reuses the generic label across an
overall tee-shot-distance tab AND two Par-specific sub-tabs (confirmed
from real taxonomy evidence: Tee03/Tee05's SIBLING menu3 label is
"Par5 티샷 비율"/"Par4 티샷 비율" — a Par-qualifier absent from Tee01's
sibling label "티샷", identifying Tee01::010101 as the unqualified,
overall metric). A label-only pivot (the original BETA #001 design)
would have silently picked WHICHEVER of the three the DB happened to
iterate last — non-deterministic AND semantically wrong for two of the
three. Every candidate below is now `(identity_key, label, orientation)`
— the pivot in `build_prior_season_official_metrics` keys on
`(identity_key, label)`, never `label` alone, so this class of bug is
structurally impossible for any future taxonomy entry, not just this
one instance.
"""
from __future__ import annotations

import sqlite3

from klpga.discovery.flag_recovery import REASON_RANK_ONLY, recover_value_validity

MIN_PLAYER_COVERAGE = 20
"""A deliberately modest, fixed floor (not tuned after seeing results)
— enough players for shrinkage population statistics to be meaningful,
not a claim about full field coverage."""

# name -> ordered (identity_key, label, orientation) candidates, first-with-coverage wins.
OFFICIAL_METRIC_SLOTS: "dict[str, tuple[tuple[str, str, str], ...]]" = {
    "overall_skill": (("Sg::Total", "SG : 전체", "higher_is_better"),),
    "driving": (
        ("Sg::Tee", "SG : 티샷", "higher_is_better"),
        ("Tee::Tee01::010101", "평균 티샷 거리", "higher_is_better"),
    ),
    "short_game": (
        ("Sg::Approach", "SG : 어프로치", "higher_is_better"),
        ("Sg::Around", "SG : 그린주변", "higher_is_better"),
        ("Approach::Approach01::020101", "그린 적중률", "higher_is_better"),
    ),
    "putting": (
        ("Sg::Putt", "SG : 퍼팅", "higher_is_better"),
        ("Putt::Putt07::040710", "평균 퍼트 수", "lower_is_better"),
        ("Putt::Putt02::040201", "평균 퍼트수", "lower_is_better"),
    ),
}

FEATURE_NAME_BY_SLOT: dict[str, str] = {slot: f"neo_official_metric_{slot}" for slot in OFFICIAL_METRIC_SLOTS}


def build_prior_season_official_metrics(
    conn: sqlite3.Connection,
    prior_season: int,
    *,
    exclude_flagged: bool = True,
    alias_map: "dict[str, str] | None" = None,
    recover_rank_only_flags: bool = False,
) -> dict[str, dict[tuple[str, str], float]]:
    """Pivot: {player_master_id: {(identity_key, official_label): value}}
    for `prior_season` only — keyed on the FULL (identity_key, label)
    pair, never label alone (see module docstring's BETA #001-C fix).
    Non-numeric `value_raw` is silently excluded per row (not the whole
    player) — never a fabricated 0. `exclude_flagged=True` (the
    default) skips rows whose response was `validation_status =
    'FLAGGED'`: real-evidence investigation (docs/NEO_WIN_V0_1_
    METHODOLOGY.md) found FLAGGED is dominated by a rank-column
    duplicate/sentinel artifact, not proven value corruption for every
    row, but this feature family stays conservative and only draws
    from CLEAN responses by default.

    `recover_rank_only_flags=True` (BETA #001-C) re-checks each FLAGGED
    response via `klpga.discovery.flag_recovery.recover_value_validity`
    — a response whose ONLY nonzero flag is `duplicate_ranks` has its
    VALUES recovered for use; any response with a genuine value-
    affecting flag stays excluded. One recovery check per distinct
    `raw_sample_path` (cheap, not re-parsed per row).

    `alias_map` (from klpga.neo_win.identity_resolution.build_identity_
    alias_map) re-keys each row from its raw `official_metric_value.
    player_code` to the RESOLVED `player_master.player_id` — a code
    with NO entry in `alias_map` (genuinely unresolved) is dropped from
    the pivot, never guessed. Omit `alias_map` to key by the raw code
    directly (only safe when the caller has independently confirmed
    identity-space equality for the codes it will look up)."""
    query = (
        "SELECT player_code, identity_key, official_label, value_raw, validation_status, raw_sample_path "
        "FROM official_metric_value WHERE season = ?"
    )
    params: list = [prior_season]
    if exclude_flagged and not recover_rank_only_flags:
        query += " AND validation_status = 'CLEAN'"

    recovery_cache: dict[str, str] = {}
    pivot: dict[str, dict[tuple[str, str], float]] = {}
    for player_code, identity_key, official_label, value_raw, validation_status, raw_sample_path in conn.execute(
        query, params
    ):
        if value_raw is None:
            continue
        if exclude_flagged and validation_status != "CLEAN":
            if not recover_rank_only_flags or not raw_sample_path:
                continue
            if raw_sample_path not in recovery_cache:
                recovery_cache[raw_sample_path] = recover_value_validity(raw_sample_path)["reason"]
            if recovery_cache[raw_sample_path] != REASON_RANK_ONLY:
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
        pivot.setdefault(resolved_id, {})[(identity_key, official_label)] = value
    return pivot


def select_validated_official_metrics(
    pivot: dict[str, dict[tuple[str, str], float]], *, min_coverage: int = MIN_PLAYER_COVERAGE
) -> dict[str, tuple[str, str, str]]:
    """Returns {slot_name: (identity_key, official_label, orientation)}
    for every slot with at least one candidate clearing `min_coverage`
    distinct players in `pivot`. A slot absent from the result
    contributed nothing this run — the explicit "feature omitted"
    outcome, never a guess."""
    selected: dict[str, tuple[str, str, str]] = {}
    for slot, candidates in OFFICIAL_METRIC_SLOTS.items():
        for identity_key, label, orientation in candidates:
            coverage = sum(1 for player_metrics in pivot.values() if (identity_key, label) in player_metrics)
            if coverage >= min_coverage:
                selected[slot] = (identity_key, label, orientation)
                break
    return selected


def oriented_value(raw_value: float, orientation: str) -> float:
    """Flips sign so the result always follows this project's "lower is
    better" combined-score convention (klpga.models.candidates module
    docstring) — a higher raw value for a `higher_is_better` metric
    becomes a LOWER oriented value (more winning-favorable)."""
    return -raw_value if orientation == "higher_is_better" else raw_value
