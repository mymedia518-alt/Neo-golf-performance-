"""MISSION V10 (2026-09-25), playerCode=10097 only: Data Quality
Governance -- CI enforcement for build_10097_player_intelligence_report.py's
provenance map (the second half of "Audit every value shown on Player
History and Player Intelligence").

This report is no longer the LIVE page for 10097 (Player History
superseded it -- see test_build_or_placeholder_renders_player_history_for_10097_only
in test_10097_player_intelligence_report.py), but the JSON artifact and
its renderer still exist and are still built, so this mission's scope
explicitly names it. Same enforcement shape as
test_10097_player_history_provenance_v10.py: every leaf value in the
real build() output must have a matching, validly-labeled provenance
entry, and the map must never claim a field that no longer exists.

A slightly larger metadata exclusion list than Player History's, since
this file also carries several fixed methodology-description strings
(evidence_score_method, durability_method, monitoring_protocol_method,
contribution_breakdown_method) that document the BUILD's own formulas,
not a fact about the golfer.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_intelligence_report", ROOT / "scripts" / "build_10097_player_intelligence_report.py")
build_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_script)

from klpga.data_provenance import (  # noqa: E402
    VALID_LABELS,
    orphaned_provenance_patterns,
    uncovered_paths,
    validate_labels,
)

EXCLUDED_METADATA_PATHS = (
    "schema_version", "generated_at", "scope_note", "source_document",
    "evidence_score_method", "durability_method", "monitoring_protocol_method", "contribution_breakdown_method",
)


def _doc():
    return build_script.build()


def test_every_visible_value_has_a_provenance_entry():
    doc = _doc()
    uncovered = uncovered_paths(doc, doc["provenance"], exclude_prefixes=("provenance",) + EXCLUDED_METADATA_PATHS)
    assert not uncovered, f"{len(uncovered)} visible value(s) have no provenance classification: {sorted(uncovered)}"


def test_provenance_map_never_claims_a_field_that_no_longer_exists():
    doc = _doc()
    orphaned = orphaned_provenance_patterns(doc, doc["provenance"], exclude_prefixes=("provenance",) + EXCLUDED_METADATA_PATHS)
    assert not orphaned, f"{len(orphaned)} provenance entries no longer match any real field: {sorted(orphaned)}"


def test_every_provenance_label_is_one_of_the_five_valid_values():
    doc = _doc()
    violations = validate_labels(doc["provenance"])
    assert not violations, f"invalid provenance label(s): {violations}"


def test_provenance_is_exposed_verbatim_in_the_shipped_json():
    doc = _doc()
    assert "provenance" in doc
    assert isinstance(doc["provenance"], dict)
    assert len(doc["provenance"]) > 150


def test_no_provenance_label_is_outside_the_mission_s_five_categories():
    doc = _doc()
    labels_used = {entry["label"] for entry in doc["provenance"].values()}
    assert labels_used <= set(VALID_LABELS)


def test_the_documented_imputed_finding_stays_named_in_its_reason_text():
    """The one real IMPUTED case this audit found (q_win_blueprint's
    current_reading falling back to floor_total) can't be represented
    at the schema level as its own label without mislabeling the other
    ~11 question types that use a real reading -- it is disclosed in
    the reason text instead. This test guards that disclosure from
    being silently deleted, which would make this a hidden gap again."""
    doc = _doc()
    reason = doc["provenance"]["questions[].monitoring_protocol.current_reading"]["reason"]
    assert "q_win_blueprint" in reason
    assert "IMPUTED" in reason.upper() or "imputed" in reason.lower()


def test_explicit_missing_data_disclosures_stay_not_collected():
    doc = _doc()
    p = doc["provenance"]
    for path in (
        "questions[].decision_context",
        "turning_points[].unknown_cause",
        "unsupported_analysis_modules_v12[].reason",
        "repository_intelligence_v7.findings[].player_specific_number_found",
    ):
        assert p[path]["label"] == "NOT_COLLECTED", f"{path} must stay NOT_COLLECTED"


def test_raw_official_stats_stay_measured():
    doc = _doc()
    p = doc["provenance"]
    for path in (
        "performance_funnel.opportunity.gir_rate.raw",
        "performance_funnel.conversion.birdie_rate.raw",
        "career_reconstruction.earliest_season_on_record",
    ):
        assert p[path]["label"] == "MEASURED"


def test_computed_percentiles_and_counts_stay_derived():
    doc = _doc()
    p = doc["provenance"]
    for path in (
        "performance_funnel.opportunity.gir_rate.percentile",
        "win_dna.breakdown[].share_pct",
        "season_by_season_table[].avg_total",
    ):
        assert p[path]["label"] == "DERIVED"
