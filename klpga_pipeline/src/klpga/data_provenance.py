"""MISSION V10 (2026-09-25): Data Quality Governance -- the one shared
provenance-classification utility. "Every number shown on NEO can always
answer 'where did this come from?'" Any module that exposes a
`provenance` map for a JSON report (Player History, Player Intelligence,
and any future report) builds and validates it through the functions
here, so the 5-label vocabulary and the leaf-coverage check never drift
between reports.

The five labels this mission defines -- no sixth label is ever valid:

  MEASURED      A real, directly-collected raw data point. No arithmetic
                was applied to produce this exact value (a rank pulled
                from a leaderboard record, a raw SG value read from the
                warehouse, a real date string from the official schedule).

  DERIVED       Computed via a deterministic formula/aggregation FROM one
                or more MEASURED (or other DERIVED) values -- an average,
                a delta, a percentile, a peak/min over a list, a count,
                a sparkline's plotted points. Always traceable to real
                inputs; never a guess.

  IMPUTED       A value that stands in for missing data via estimation,
                interpolation, or a fallback default -- never silently
                treated as if it were real. As of this mission, neither
                10097 report builder contains a single IMPUTED value
                (see the provenance report): every gap in this pipeline
                is disclosed as NOT_COLLECTED/NOT_AVAILABLE rather than
                filled in. The label exists so a future addition that DOES
                impute a value has nowhere to hide -- it must be declared,
                not left MEASURED/DERIVED by omission.

  NOT_COLLECTED The pipeline is capable of having this data (KLPGA may
                well publish it) but NEO's own collection has not
                ingested it for this specific case. Never implies KLPGA
                itself lacks the data merely because this repository has
                not.

  NOT_AVAILABLE Data that fundamentally is not obtainable in this
                pipeline's current environment/design -- a field with no
                real path to a value yet (e.g. hole-by-hole history exists
                for only one tournament; hardware/network access this
                sandbox does not have).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

VALID_LABELS = ("MEASURED", "DERIVED", "IMPUTED", "NOT_COLLECTED", "NOT_AVAILABLE")


@dataclass(frozen=True)
class ProvenanceEntry:
    label: str
    reason: str
    depends_on: tuple = ()  # JSON-path-pattern(s) this DERIVED value is computed from -- empty for MEASURED/IMPUTED/NOT_COLLECTED/NOT_AVAILABLE

    def __post_init__(self):
        if self.label not in VALID_LABELS:
            raise ValueError(f"invalid provenance label {self.label!r} -- must be one of {VALID_LABELS}")
        if self.label != "DERIVED" and self.depends_on:
            raise ValueError(f"depends_on is only meaningful for DERIVED entries, got label={self.label!r}")


def build_provenance_map(entries: dict) -> dict:
    """entries: {path_pattern: (label, reason)} or {path_pattern: (label, reason, depends_on_tuple)}.
    Returns {path_pattern: {"label": ..., "reason": ..., "depends_on": [...]}}
    -- the exact shape written into the report JSON's own "provenance" key,
    plain dicts (not dataclasses) so it round-trips through json.dump
    unmodified. Validates every entry through ProvenanceEntry, so a typo'd
    label fails at build time, not silently in the shipped artifact."""
    out = {}
    for path, spec in entries.items():
        if len(spec) == 2:
            label, reason = spec
            depends_on: tuple = ()
        else:
            label, reason, depends_on = spec
        pe = ProvenanceEntry(label=label, reason=reason, depends_on=tuple(depends_on))
        out[path] = {"label": pe.label, "reason": pe.reason, "depends_on": list(pe.depends_on)}
    return out


def leaf_paths(value, prefix: str = "") -> set:
    """Walk a JSON-like nested dict/list structure and return the set of
    path patterns for every LEAF (non-dict, non-list) value present.
    Lists are collapsed to one `[]` wildcard segment -- provenance is a
    property of a field's SCHEMA, not of each individual row instance,
    so `tournament_history[].sg_total` covers all ~96 rows with one
    entry, not 96. An empty list/dict contributes no leaves (nothing to
    classify if nothing is there), which is correct: a genuinely empty
    collection shows the reader nothing, so it needs no provenance."""
    paths: set = set()

    def _walk(v, p: str):
        if isinstance(v, dict):
            for k, sub in v.items():
                _walk(sub, f"{p}.{k}" if p else k)
        elif isinstance(v, (list, tuple)):
            if v:
                for item in v:
                    _walk(item, f"{p}[]" if p else "[]")
        else:
            paths.add(p)

    _walk(value, prefix)
    return paths


def _pattern_matches(pattern: str, path: str) -> bool:
    return pattern == path


def uncovered_paths(doc: dict, provenance_map: dict, *, exclude_prefixes: tuple = ("provenance",)) -> set:
    """Every real leaf path in `doc` (excluding the provenance map's own
    key, and any other explicitly excluded top-level key, e.g. raw
    reconciliation/debug payloads this mission does not classify) that
    has no matching entry in `provenance_map`. Empty result == "no
    visible value without provenance" holds for this document."""
    present = leaf_paths(doc)
    present = {p for p in present if not any(p == pre or p.startswith(pre + ".") or p.startswith(pre + "[]") for pre in exclude_prefixes)}
    covered_patterns = set(provenance_map.keys())
    uncovered = set()
    for p in present:
        if not any(_pattern_matches(pattern, p) for pattern in covered_patterns):
            uncovered.add(p)
    return uncovered


def orphaned_provenance_patterns(doc: dict, provenance_map: dict, *, exclude_prefixes: tuple = ("provenance",)) -> set:
    """The inverse check: provenance-map entries that no longer match
    any real leaf in `doc` -- catches a stale entry left behind after a
    field was renamed or removed, so the map never silently drifts out
    of sync with the code it describes."""
    present = leaf_paths(doc)
    present = {p for p in present if not any(p == pre or p.startswith(pre + ".") or p.startswith(pre + "[]") for pre in exclude_prefixes)}
    return {pattern for pattern in provenance_map if pattern not in present}


def validate_labels(provenance_map: dict) -> list:
    """Every entry's label must be one of VALID_LABELS. Returns the list
    of (path, bad_label) violations -- empty means the map is clean.
    build_provenance_map() already enforces this at construction time;
    this exists so a provenance map assembled by hand (or from a JSON
    file already on disk, not freshly built) can still be checked."""
    bad = []
    for path, entry in provenance_map.items():
        label = entry["label"] if isinstance(entry, dict) else entry
        if label not in VALID_LABELS:
            bad.append((path, label))
    return bad


def dependency_graph(provenance_map: dict) -> dict:
    """{path: [depends_on paths]} for every DERIVED entry -- the plain
    adjacency-list representation the dependency-graph report is built
    from (a data structure, not a rendered chart/diagram -- this mission
    explicitly forbids building UI/charts)."""
    return {
        path: list(entry["depends_on"])
        for path, entry in provenance_map.items()
        if entry.get("label") == "DERIVED" and entry.get("depends_on")
    }
