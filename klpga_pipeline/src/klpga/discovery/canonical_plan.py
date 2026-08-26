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
