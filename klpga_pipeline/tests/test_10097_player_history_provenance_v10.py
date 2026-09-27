"""MISSION V10 (2026-09-25), playerCode=10097 only: Data Quality
Governance.

"Audit every value shown on Player History and Player Intelligence.
For every visible value classify it as exactly one of: MEASURED,
DERIVED, IMPUTED, NOT_COLLECTED, NOT_AVAILABLE. Expose that
classification in the JSON. Never allow a visible value without
provenance."

This file is the CI enforcement for build_10097_player_history.py's
side of that mission: every leaf value the real build() output
contains must have a matching, validly-labeled entry in
doc["provenance"], and the map must never claim to cover a field that
no longer exists (which would let it silently drift out of sync with
the code). A handful of pure build/pipeline metadata fields
(schema_version, generated_at, scope_note, source_document) are the
one deliberate, explicit exclusion -- see EXCLUDED_METADATA_PATHS.

See klpga_pipeline/docs/NEO_DATA_PROVENANCE_REPORT_10097_V1.md for the
full classification report and methodology notes (including the two
governance gaps this audit surfaced: status.data_completeness/
status.derived_metrics and coverage_matrix.rows are unverified,
hand-authored constants, not live-computed).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_history", ROOT / "scripts" / "build_10097_player_history.py")
build_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_script)

from klpga.data_provenance import (  # noqa: E402
    VALID_LABELS,
    orphaned_provenance_patterns,
    uncovered_paths,
    validate_labels,
)

# Pure build/pipeline metadata -- describes the BUILD, not the golfer,
# so none of the 5 provenance labels honestly applies. This is the
# entire exclusion list; nothing else is exempt.
EXCLUDED_METADATA_PATHS = ("schema_version", "generated_at", "scope_note", "source_document")


def _doc():
    return build_script.build()


def test_every_visible_value_has_a_provenance_entry():
    """The core CI guard: no leaf value in the real build() output may
    be missing from doc["provenance"]. This is what 'never allow a
    visible value without provenance' means in code -- add a field to
    build() without adding it here, and this test fails."""
    doc = _doc()
    uncovered = uncovered_paths(doc, doc["provenance"], exclude_prefixes=("provenance",) + EXCLUDED_METADATA_PATHS)
    assert not uncovered, f"{len(uncovered)} visible value(s) have no provenance classification: {sorted(uncovered)}"


def test_provenance_map_never_claims_a_field_that_no_longer_exists():
    """The inverse guard: a stale entry (left behind after a field was
    renamed/removed) would let the map silently drift out of sync with
    the code it describes -- catch that here, not in a future audit."""
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
    assert len(doc["provenance"]) > 500  # this page has 600+ distinct leaf fields; a near-empty map would be a real regression


def test_no_provenance_label_is_outside_the_mission_s_five_categories():
    doc = _doc()
    labels_used = {entry["label"] for entry in doc["provenance"].values()}
    assert labels_used <= set(VALID_LABELS)


# ---------------------------------------------------------------------------
# Regression pins: specific fields whose classification must never
# silently change. Each one caught a real judgment call during the
# audit -- if a future edit flips one of these without a deliberate
# review, that is exactly the "provenance regression" this mission
# exists to prevent.
# ---------------------------------------------------------------------------

def test_raw_measurements_stay_measured():
    doc = _doc()
    p = doc["provenance"]
    for path in (
        "tournament_history[].sg_total",
        "tournament_history[].game_code",
        "current_snapshot.official_sg_rank",
        "career_overview.latest_tournament.sg_total",
        "hole_history.rounds[].holes[].strokes",
        "player_name",
    ):
        assert p[path]["label"] == "MEASURED", f"{path} must stay MEASURED"


def test_computed_aggregates_stay_derived():
    doc = _doc()
    p = doc["provenance"]
    assert p["current_vs_career.delta_vs_career_average"]["label"] == "DERIVED"
    assert p["current_vs_career.career_average_sg_total"]["label"] == "DERIVED"
    assert p["career_overview.season_rows[].sg_total"]["label"] == "DERIVED", "a season average is a mean over real rows, never a single raw measurement"
    assert p["why_now.lead_component"]["label"] == "DERIVED", "a selection (argmax over deltas) is a derived fact, not a raw measurement"
    assert p["career_dna.career_foundation"]["label"] == "DERIVED"


def test_the_mislabeled_raw_value_field_is_correctly_classified_derived_not_measured():
    """player_dna_radar[].axes[].raw_value is actually a season MEAN
    despite its name -- the audit caught this naming/provenance
    mismatch explicitly. Pinned so a future 'helpful' cleanup doesn't
    quietly reclassify it MEASURED just because the field is named
    'raw_value'."""
    doc = _doc()
    assert doc["provenance"]["player_dna_radar[].axes[].raw_value"]["label"] == "DERIVED"


def test_the_one_real_hole_level_source_is_not_available_for_every_other_tournament():
    doc = _doc()
    assert doc["provenance"]["hole_history.capture_note"]["label"] == "NOT_AVAILABLE"
    p = doc["provenance"]
    for w in ("peak_window", "slump_window", "recovery_window"):
        assert p[f"career_rolling_trend.{w}.decomposition.gir"]["label"] == "NOT_AVAILABLE"
        assert p[f"career_rolling_trend.{w}.decomposition.putts"]["label"] == "NOT_AVAILABLE"


def test_sg_status_and_recent_form_status_stay_derived_classification_flags():
    doc = _doc()
    p = doc["provenance"]
    assert p["recent_form_10[].sg_status"]["label"] == "DERIVED"
    assert p["career_rolling_trend.peak_window.decomposition.birdie_bogey_gir_putts_status"]["label"] == "DERIVED"


def test_not_available_list_items_are_classified_not_available():
    doc = _doc()
    assert doc["provenance"]["not_available[]"]["label"] == "NOT_AVAILABLE"


def test_unverified_hand_authored_constants_are_disclosed_in_their_own_reason_text():
    """status.data_completeness/derived_metrics and every coverage_matrix
    cell are real governance gaps this audit surfaced (hardcoded,
    never actually verified against a live per-run data check). They
    stay MEASURED (a factual assertion, not a formula or a gap), but
    the reason text must say so honestly -- this test guards against
    that disclosure being quietly deleted."""
    doc = _doc()
    p = doc["provenance"]
    assert "not computed from a live" in p["status.data_completeness"]["reason"]
    assert "not computed from a live" in p["status.derived_metrics"]["reason"]
    sample_cell = "coverage_matrix.rows.SG Total.2026"
    assert sample_cell in p
    assert "not computed from a live" in p[sample_cell]["reason"]


def test_dependency_graph_is_non_empty_and_only_covers_derived_entries():
    from klpga.data_provenance import dependency_graph
    doc = _doc()
    graph = dependency_graph(doc["provenance"])
    assert graph, "expected at least one DERIVED entry to declare real dependencies"
    for path, deps in graph.items():
        assert doc["provenance"][path]["label"] == "DERIVED"
        assert deps, f"{path} is in the dependency graph with no dependencies listed"
