"""Phase B1 CLASS 2 fix — the REAL canonical metric request plan.

Operates on an already-produced Phase A taxonomy dict (the same shape
`sampler.py` consumes: `taxonomy["leaves"]`, a list of dicts with
`menu1`/`menu2`/`menu3`/`leaf_level`/`menu2_label`/`menu3_label`/
`source_metric_key`, optionally `node_type`). Pure, offline, no
network access — never fires a request, never fabricates a menu3
value.

Filters out, in order:
  1. Malformed leaves (blank/missing menu1 or menu2 — see
     `sampler.reject_malformed_leaves`'s docstring for why these
     exist at all).
  2. Navigation/container nodes (node_type=NAVIGATION_CONTAINER, e.g.
     every menu1="All" entry — CONFIRMED by real evidence: a live
     request returned 0 rows and a body containing the entire
     navigation menu tree itself, not player data. See
     `klpga.discovery.menu_taxonomy.CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES`).
  3. Exact-duplicate DOM entries (the identical (identity, label) tuple
     appearing more than once — a markup artifact, not a semantic
     collision; see `collision_report.py`'s Category C for the
     equivalent DOM-level check).

What remains is the CANONICAL set of REAL, distinct, requestable KLPGA
metric requests — the answer to "how many real KLPGA metric requests
exist after removing navigation/container nodes?"

A taxonomy JSON produced BEFORE `node_type` existed (no such key on
any leaf) is still handled correctly: `_node_type()` falls back to the
same confirmed-menu1-value check `sampler.py` uses.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass
from typing import Optional

_CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES = frozenset({"All"})
"""Kept in sync with menu_taxonomy.py / sampler.py — see either
module's docstring for the real evidence."""


def _node_type(leaf: dict) -> str:
    explicit = leaf.get("node_type")
    if explicit:
        return explicit
    if leaf.get("menu1") in _CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES:
        return "NAVIGATION_CONTAINER"
    return "REQUESTABLE_METRIC_LEAF"


def _is_malformed(leaf: dict) -> bool:
    return not leaf.get("menu1") or not leaf.get("menu2")


def _identity_key_tuple(leaf: dict) -> tuple:
    if leaf.get("leaf_level") == "menu3":
        return (leaf.get("menu1"), leaf.get("menu2"), leaf.get("menu3"))
    return (leaf.get("menu1"), leaf.get("menu2"))


def _label(leaf: dict) -> Optional[str]:
    return leaf.get("menu3_label") if leaf.get("leaf_level") == "menu3" else leaf.get("menu2_label")


@dataclass
class CanonicalPlanCounts:
    total_dom_discovered_nodes: int
    """Every leaf found by Phase A, of ANY node_type — the raw DOM
    inventory before any filtering."""
    malformed_leaf_count: int
    requestable_menu2_leaf_count: int
    requestable_menu3_leaf_count: int
    navigation_container_count: int
    exact_duplicate_count: int
    """Requestable leaves excluded because an earlier leaf already had
    the identical (identity, label) tuple — a DOM/markup artifact."""
    canonical_requestable_metric_count: int
    """requestable_menu2_leaf_count + requestable_menu3_leaf_count -
    exact_duplicate_count — the REAL answer to "how many distinct,
    requestable KLPGA metrics exist?"."""
    menu3_collision_count: int
    """Distinct menu3 codes shared by more than one CANONICAL
    (post-dedup) requestable menu3-level leaf — never assumed unique,
    per this project's standing evidence discipline."""


def build_canonical_plan(taxonomy: dict) -> tuple[CanonicalPlanCounts, list[dict]]:
    """Returns (counts, plan) — `plan` is the canonical, deduplicated,
    requestable-only leaf list, each entry matching the schema Mission
    3 specifies (menu1/menu2/menu3/leaf_level/identity_key/label/
    node_type/evidence_source)."""
    raw_leaves = taxonomy.get("leaves", [])
    total = len(raw_leaves)

    non_malformed = [leaf for leaf in raw_leaves if not _is_malformed(leaf)]
    malformed_count = total - len(non_malformed)

    requestable = [leaf for leaf in non_malformed if _node_type(leaf) == "REQUESTABLE_METRIC_LEAF"]
    navigation_count = sum(1 for leaf in non_malformed if _node_type(leaf) == "NAVIGATION_CONTAINER")

    seen: dict[tuple, bool] = {}
    canonical_entries: list[dict] = []
    duplicate_count = 0
    for leaf in requestable:
        key = (_identity_key_tuple(leaf), _label(leaf))
        if key in seen:
            duplicate_count += 1
            continue
        seen[key] = True
        canonical_entries.append(leaf)

    canonical_menu2 = [leaf for leaf in canonical_entries if leaf.get("leaf_level") == "menu2"]
    canonical_menu3 = [leaf for leaf in canonical_entries if leaf.get("leaf_level") == "menu3"]

    by_menu3: dict[str, int] = {}
    for leaf in canonical_menu3:
        code = leaf.get("menu3")
        if code:
            by_menu3[code] = by_menu3.get(code, 0) + 1
    menu3_collision_count = sum(1 for count in by_menu3.values() if count > 1)

    counts = CanonicalPlanCounts(
        total_dom_discovered_nodes=total,
        malformed_leaf_count=malformed_count,
        requestable_menu2_leaf_count=sum(1 for leaf in requestable if leaf.get("leaf_level") == "menu2"),
        requestable_menu3_leaf_count=sum(1 for leaf in requestable if leaf.get("leaf_level") == "menu3"),
        navigation_container_count=navigation_count,
        exact_duplicate_count=duplicate_count,
        canonical_requestable_metric_count=len(canonical_entries),
        menu3_collision_count=menu3_collision_count,
    )

    plan = [
        {
            "menu1": leaf.get("menu1"),
            "menu2": leaf.get("menu2"),
            "menu3": leaf.get("menu3"),
            "leaf_level": leaf.get("leaf_level"),
            "identity_key": "::".join(str(part) for part in _identity_key_tuple(leaf)),
            "label": _label(leaf),
            "node_type": _node_type(leaf),
            "evidence_source": leaf.get("source_metric_key", ""),
        }
        for leaf in canonical_menu2 + canonical_menu3
    ]

    return counts, plan


_KNOWN_LEAF_KEYS = {
    "menu1", "menu1_label", "menu2", "menu2_label", "menu3", "menu3_label",
    "leaf_level", "source_metric_key", "label_resolution_method",
    "is_menu3_collision", "node_type",
}
"""The complete set of keys `taxonomy_report.to_taxonomy_json` has
EVER written, across every schema revision this project has shipped
(the original Round 3 leaf shape had no `leaf_level`/`node_type`; both
were added later — see canonical_plan.py's module docstring and
docs/KLPGA_OFFICIAL_DATA_MAP.md's schema-audit section). Used only for
diagnostic reporting (`classify_malformation_reason`), never to alter
`_is_malformed`'s actual rejection rule."""


def classify_malformation_reason(leaf: dict) -> str:
    """Diagnostic-only classification of WHY a leaf is malformed —
    never changes whether it's rejected (`_is_malformed` above remains
    the single source of truth for that). Distinguishes a genuinely
    unresolvable DOM leaf (this project's own Pass-1 "unknown"
    ancestor-walk fallback — see menu_taxonomy.py) from a taxonomy
    JSON produced by an older schema revision this session cannot
    directly inspect."""
    has_menu1 = bool(leaf.get("menu1"))
    has_menu2 = bool(leaf.get("menu2"))
    unknown_keys = set(leaf.keys()) - _KNOWN_LEAF_KEYS
    if unknown_keys:
        return f"unrecognized_fields:{','.join(sorted(unknown_keys))}"
    if "leaf_level" not in leaf:
        return "legacy_taxonomy_format_missing_leaf_level"
    if not has_menu1 and not has_menu2:
        return "missing_menu1_and_menu2"
    if not has_menu1:
        return "missing_menu1"
    if not has_menu2:
        return "missing_menu2"
    if leaf.get("leaf_level") == "menu3" and not leaf.get("menu3"):
        return "missing_menu3_when_required"
    return "other"


def build_malformed_leaf_report(taxonomy: dict) -> list[dict]:
    """One row per rejected (`_is_malformed`) leaf, preserving enough
    raw source information to identify a parser/serialization
    mismatch — see Mission 2's required schema (Phase B1 CLASS 2
    follow-up round)."""
    rows = []
    for index, leaf in enumerate(taxonomy.get("leaves", [])):
        if not _is_malformed(leaf):
            continue
        rows.append(
            {
                "original_index": index,
                "raw_menu1": leaf.get("menu1"),
                "raw_menu2": leaf.get("menu2"),
                "raw_menu3": leaf.get("menu3"),
                "leaf_level": leaf.get("leaf_level"),
                "label": _label(leaf),
                "node_type": _node_type(leaf),
                "identity_key": "::".join(str(part) for part in _identity_key_tuple(leaf)),
                "rejection_reason": classify_malformation_reason(leaf),
            }
        )
    return rows


_MALFORMED_REPORT_CSV_FIELDS = [
    "original_index", "raw_menu1", "raw_menu2", "raw_menu3", "leaf_level",
    "label", "node_type", "identity_key", "rejection_reason",
]


def to_malformed_leaf_report_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_MALFORMED_REPORT_CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in _MALFORMED_REPORT_CSV_FIELDS})
    return buf.getvalue()


_CONFIRMED_STAT_FAMILIES = ("Sg", "Tee", "Approach", "Around", "Putt")


def group_counts_by_family(taxonomy: dict) -> dict[str, dict[str, int]]:
    """Per-menu1-family breakdown (the five confirmed stat families,
    plus "other" for everything else — including "All" and any
    genuinely unrecognized family) of: total nodes, malformed,
    requestable menu2/menu3, navigation/container."""
    families = {f: {"total": 0, "malformed": 0, "requestable_menu2": 0, "requestable_menu3": 0, "navigation_container": 0} for f in _CONFIRMED_STAT_FAMILIES}
    families["other"] = {"total": 0, "malformed": 0, "requestable_menu2": 0, "requestable_menu3": 0, "navigation_container": 0}

    for leaf in taxonomy.get("leaves", []):
        menu1 = leaf.get("menu1") or ""
        family = menu1 if menu1 in _CONFIRMED_STAT_FAMILIES else "other"
        bucket = families[family]
        bucket["total"] += 1
        if _is_malformed(leaf):
            bucket["malformed"] += 1
            continue
        node_type = _node_type(leaf)
        if node_type == "NAVIGATION_CONTAINER":
            bucket["navigation_container"] += 1
        elif leaf.get("leaf_level") == "menu2":
            bucket["requestable_menu2"] += 1
        elif leaf.get("leaf_level") == "menu3":
            bucket["requestable_menu3"] += 1

    return families


def check_sanity_invariants(counts: CanonicalPlanCounts) -> list[str]:
    """Diagnostic safety guards, NOT assumptions about the true final
    count (never used to fabricate or cap a number) — only to stop
    script 28 from presenting a misleading canonical plan as if it
    were trustworthy. Returns a list of violation messages; empty
    means every invariant held."""
    violations: list[str] = []
    valid_leaf_count = counts.total_dom_discovered_nodes - counts.malformed_leaf_count
    malformed_ratio = (
        counts.malformed_leaf_count / counts.total_dom_discovered_nodes
        if counts.total_dom_discovered_nodes
        else 0.0
    )
    if malformed_ratio > 0.10:
        violations.append(
            f"malformed_ratio={malformed_ratio:.1%} exceeds the 10% safety threshold "
            f"({counts.malformed_leaf_count}/{counts.total_dom_discovered_nodes} nodes) — "
            "this taxonomy is likely reflecting a real DOM-resolution or schema problem, "
            "not a small number of genuinely orphaned tags."
        )
    if valid_leaf_count > 0:
        reduction_ratio = 1 - (counts.canonical_requestable_metric_count / valid_leaf_count)
        if reduction_ratio > 0.80:
            violations.append(
                f"canonical_requestable_metric_count ({counts.canonical_requestable_metric_count}) is "
                f"{reduction_ratio:.1%} smaller than valid-identity leaves ({valid_leaf_count}) — "
                "implausibly large reduction relative to what navigation-container filtering and "
                "exact-duplicate dedup alone should account for."
            )
    return violations


def build_canonical_plan_json(taxonomy: dict, *, generated_at: str, source_taxonomy: str) -> str:
    counts, plan = build_canonical_plan(taxonomy)
    payload = {
        "generated_at": generated_at,
        "source_taxonomy": source_taxonomy,
        "note": (
            "Canonical REQUESTABLE metric request plan — navigation/container "
            "nodes (e.g. every menu1=\"All\" entry) and exact-duplicate DOM "
            "entries are excluded. This is Phase A/B1 discovery output only; "
            "it does not authorize firing all listed requests (Phase B2)."
        ),
        "counts": asdict(counts),
        "canonical_requestable_metrics": plan,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
