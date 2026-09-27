"""MISSION V10 (2026-09-25): unit tests for the shared provenance
utility itself (klpga.data_provenance) -- independent of any one
report's field list, which is covered by its own report-specific
provenance test file."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from klpga.data_provenance import (  # noqa: E402
    ProvenanceEntry,
    build_provenance_map,
    dependency_graph,
    leaf_paths,
    orphaned_provenance_patterns,
    uncovered_paths,
    validate_labels,
)


def test_valid_label_is_accepted():
    ProvenanceEntry(label="MEASURED", reason="x")


def test_invalid_label_is_rejected():
    with pytest.raises(ValueError):
        ProvenanceEntry(label="ESTIMATED", reason="not a real label")


def test_depends_on_only_allowed_for_derived():
    with pytest.raises(ValueError):
        ProvenanceEntry(label="MEASURED", reason="x", depends_on=("a.b",))
    ProvenanceEntry(label="DERIVED", reason="x", depends_on=("a.b",))  # does not raise


def test_build_provenance_map_validates_every_entry():
    with pytest.raises(ValueError):
        build_provenance_map({"a.b": ("NOT_A_REAL_LABEL", "reason")})


def test_leaf_paths_collapses_lists_to_one_wildcard():
    doc = {"rows": [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]}
    assert leaf_paths(doc) == {"rows[].x", "rows[].y"}


def test_leaf_paths_handles_nested_dicts():
    doc = {"a": {"b": {"c": 1}}, "d": 2}
    assert leaf_paths(doc) == {"a.b.c", "d"}


def test_leaf_paths_empty_list_contributes_no_leaves():
    assert leaf_paths({"rows": []}) == set()


def test_uncovered_paths_catches_a_real_gap():
    doc = {"a": 1, "b": 2}
    provenance = build_provenance_map({"a": ("MEASURED", "x")})
    assert uncovered_paths(doc, provenance) == {"b"}


def test_uncovered_paths_empty_when_fully_covered():
    doc = {"a": 1, "b": {"c": 2}}
    provenance = build_provenance_map({"a": ("MEASURED", "x"), "b.c": ("DERIVED", "y")})
    assert uncovered_paths(doc, provenance) == set()


def test_uncovered_paths_excludes_the_provenance_key_itself():
    doc = {"a": 1, "provenance": {"a": {"label": "MEASURED"}}}
    provenance = build_provenance_map({"a": ("MEASURED", "x")})
    assert uncovered_paths(doc, provenance) == set()


def test_orphaned_provenance_patterns_catches_a_stale_entry():
    doc = {"a": 1}
    provenance = build_provenance_map({"a": ("MEASURED", "x"), "removed_field": ("MEASURED", "y")})
    assert orphaned_provenance_patterns(doc, provenance) == {"removed_field"}


def test_validate_labels_flags_a_hand_assembled_bad_map():
    bad_map = {"a": {"label": "GUESSED", "reason": "x"}}
    violations = validate_labels(bad_map)
    assert violations == [("a", "GUESSED")]


def test_dependency_graph_only_includes_derived_entries_with_deps():
    provenance = build_provenance_map({
        "raw": ("MEASURED", "x"),
        "avg": ("DERIVED", "mean of raw[]", ("raw[]",)),
        "note": ("NOT_AVAILABLE", "no source"),
    })
    graph = dependency_graph(provenance)
    assert graph == {"avg": ["raw[]"]}
