"""Classifies every canonical KLPGA official metric (up to 281 labels
across 248 request identities, `klpga.discovery.canonical_plan.
build_canonical_plan`) into a golf-performance DOMAIN, and determines
whether it is actually usable as a BETA #001-C model feature — never
"blindly feed all 281 metrics into the model" (explicit release
requirement).

======================================================================
DOMAIN CLASSIFICATION — real menu1/label evidence, never guessed
======================================================================
Uses the taxonomy's own `menu1` grouping (Tee/Approach/Around/Putt/Sg/
All — real, confirmed categories from the discovered DOM structure)
plus real, confirmed label substrings (the same evidence-only
convention `klpga.neo_win.official_metrics`'s allowlist already uses).
A label matching NONE of the known patterns is classified `UNKNOWN`,
never forced into a domain — `usable_for_model` is always False for
`UNKNOWN`.

======================================================================
USABLE_FOR_MODEL — three independent gates, all must pass
======================================================================
1. MAPPED: `identity_mapping.py` confirmed a real response field for
   this exact (identity_key, label) — never a guess.
2. DIRECTION KNOWN: the label is in `klpga.neo_win.official_metrics.
   OFFICIAL_METRIC_SLOTS`'s exact allowlist (higher/lower-is-better
   confirmed by unambiguous golf terminology) — most MAPPED metrics
   are NOT in this short allowlist and are therefore correctly marked
   not usable, with that exact reason.
3. NOT A DUPLICATE REPRESENTATION: SCORING-domain official metrics are
   marked not usable even when technically MAPPED+direction-known,
   because `prior_avg_round_score_to_par` (an existing base feature,
   from player_event results, not official_metric_value) already
   represents career scoring — including a second, official-metric
   scoring signal would be exactly the "duplicate representation" the
   release explicitly warned against.
"""
from __future__ import annotations

from typing import Optional

from klpga.discovery.canonical_plan import build_canonical_plan
from klpga.discovery.identity_mapping import STATUS_MAPPED, MappingRecord, build_identity_metric_mapping
from klpga.neo_win.official_metrics import OFFICIAL_METRIC_SLOTS

DOMAIN_DRIVING = "DRIVING"
DOMAIN_APPROACH = "APPROACH"
DOMAIN_SHORT_GAME = "SHORT_GAME"
DOMAIN_PUTTING = "PUTTING"
DOMAIN_SCORING = "SCORING"
DOMAIN_OVERALL = "OVERALL"
DOMAIN_UNKNOWN = "UNKNOWN"

# (identity_key, label)-in-allowlist -> (domain, orientation) — the
# identity_key+label pair is copied verbatim from OFFICIAL_METRIC_SLOTS
# (single source of truth for orientation; this module never re-derives
# a direction independently, and never matches on label alone — see
# that module's docstring for why a bare label match is unsafe).
_KEY_LABEL_TO_SLOT: dict[tuple[str, str], tuple[str, str]] = {}
for _slot, _candidates in OFFICIAL_METRIC_SLOTS.items():
    for _identity_key, _label, _orientation in _candidates:
        _KEY_LABEL_TO_SLOT[(_identity_key, _label)] = (_slot.upper(), _orientation)

_SLOT_TO_DOMAIN = {
    "OVERALL_SKILL": DOMAIN_OVERALL,
    "DRIVING": DOMAIN_DRIVING,
    "SHORT_GAME": DOMAIN_SHORT_GAME,
    "PUTTING": DOMAIN_PUTTING,
}


def classify_metric_domain(menu1: str, official_label: str, identity_key: "str | None" = None) -> str:
    """Real evidence only: taxonomy menu1 grouping + confirmed label
    substrings. Returns DOMAIN_UNKNOWN rather than guessing. When
    `identity_key` is given and matches an allowlisted (identity_key,
    label) pair exactly, uses that slot's domain directly — a label
    match alone is NOT sufficient (see module docstring: the same
    label can appear at multiple, semantically different identity_keys)."""
    if identity_key is not None and (identity_key, official_label) in _KEY_LABEL_TO_SLOT:
        slot, _orientation = _KEY_LABEL_TO_SLOT[(identity_key, official_label)]
        return _SLOT_TO_DOMAIN.get(slot, DOMAIN_UNKNOWN)
    if menu1 == "Sg":
        if "전체" in official_label:
            return DOMAIN_OVERALL
        if "티샷" in official_label:
            return DOMAIN_DRIVING
        if "어프로치" in official_label:
            return DOMAIN_APPROACH
        if "그린주변" in official_label:
            return DOMAIN_SHORT_GAME
        if "퍼팅" in official_label:
            return DOMAIN_PUTTING
        return DOMAIN_OVERALL
    if menu1 == "Tee" or "티샷" in official_label or "드라이브" in official_label:
        return DOMAIN_DRIVING
    if menu1 == "Approach" or "어프로치" in official_label or "그린 적중" in official_label:
        return DOMAIN_APPROACH
    if menu1 == "Around" or "그린주변" in official_label or "스크램블" in official_label:
        return DOMAIN_SHORT_GAME
    if menu1 == "Putt" or "퍼트" in official_label or "퍼팅" in official_label:
        return DOMAIN_PUTTING
    if "타수" in official_label or "스코어" in official_label:
        return DOMAIN_SCORING
    return DOMAIN_UNKNOWN


def build_metric_feature_map(taxonomy: dict, *, raw_samples_dir, season: str) -> list[dict]:
    """One row per canonical (identity_key, label) pair — see module
    docstring for `usable_for_model`'s three gates."""
    _counts, plan = build_canonical_plan(taxonomy)
    mapping_records = build_identity_metric_mapping(taxonomy, raw_samples_dir=raw_samples_dir, season=season)
    mapping_by_key_label = {(m.identity_key, m.label): m for m in mapping_records}

    rows: list[dict] = []
    for entry in plan:
        identity_key = entry["identity_key"]
        label = entry["label"] or ""
        mapping: Optional[MappingRecord] = mapping_by_key_label.get((identity_key, label))
        domain = classify_metric_domain(entry["menu1"], label, identity_key)

        mapped = mapping is not None and mapping.status == STATUS_MAPPED
        direction_known = (identity_key, label) in _KEY_LABEL_TO_SLOT
        orientation = _KEY_LABEL_TO_SLOT[(identity_key, label)][1] if direction_known else None
        is_duplicate_of_base_feature = domain == DOMAIN_SCORING

        reasons = []
        if not mapped:
            reasons.append("not MAPPED to a confirmed response field")
        if not direction_known:
            reasons.append("no confirmed higher/lower-is-better direction")
        if is_duplicate_of_base_feature:
            reasons.append("SCORING domain already represented by the existing prior_avg_round_score_to_par base feature")
        usable = mapped and direction_known and not is_duplicate_of_base_feature

        rows.append(
            {
                "identity_key": identity_key,
                "official_label": label,
                "canonical_metric": entry["evidence_source"],
                "domain": domain,
                "raw_value_field": mapping.field_name if mapping else None,
                "rank_field": "data-rank (on the record cell)" if mapped else None,
                "direction": orientation,
                "normalization_method": "shrink-to-training-mean z-score" if usable else None,
                "usable_for_model": usable,
                "reason": "; ".join(reasons) if reasons else "usable",
                "PIT_status": "PIT_UNVERIFIED (season-level; leakage-safe only via prior-season convention)",
            }
        )
    return rows
