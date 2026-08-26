"""Phase A output artifacts — KLPGA_RECORD_TAXONOMY_DISCOVERED.json/.csv
and the taxonomy count summary. Pure formatting over an already-built
`DomInspectionResult`; performs no network access itself.

Round 3 patch: counts are reported at BOTH levels so results stay
auditable across the schema change — "menu3 combinations" (the
OLD-style count, menu3-level leaves only) alongside "total metric
leaves" (menu2-level + menu3-level, the NEW complete count).
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass

from klpga.discovery.menu_taxonomy import DomInspectionResult


@dataclass
class TaxonomyCounts:
    menu1_count: int
    menu2_node_count: int
    """Distinct (menu1, menu2) pairs across ALL leaves — a structural
    count, not the same as menu2_level_leaf_count below."""
    menu2_level_leaf_count: int
    """Metric leaves that terminate at menu2 (no menu3) — e.g. the
    confirmed SG Total case."""
    menu3_level_leaf_count: int
    """Metric leaves that terminate at menu3. This is the OLD-style
    "menu3 combinations found" count from the original Round 3
    implementation, unchanged in meaning."""
    total_leaf_count: int
    """menu2_level_leaf_count + menu3_level_leaf_count — the NEW
    complete metric-leaf count."""
    unique_menu3_count: int
    """Distinct menu3 codes alone, among menu3-level leaves only."""
    collision_count: int
    """Number of distinct menu3 codes that appear as more than one
    menu3-level leaf."""
    incomplete_menu1_count: int
    """menu1 categories with NEITHER a resolved menu2-level NOR a
    resolved menu3-level leaf — candidates needing further live
    investigation."""


def compute_counts(dom_result: DomInspectionResult) -> TaxonomyCounts:
    menu2_count = len(dom_result.menu2_level_leaves)
    menu3_count = len(dom_result.menu3_level_leaves)
    return TaxonomyCounts(
        menu1_count=dom_result.menu1_count,
        menu2_node_count=dom_result.menu2_node_count,
        menu2_level_leaf_count=menu2_count,
        menu3_level_leaf_count=menu3_count,
        total_leaf_count=menu2_count + menu3_count,
        unique_menu3_count=len(dom_result.unique_menu3_values),
        collision_count=len(dom_result.collisions),
        incomplete_menu1_count=len(dom_result.incomplete_menu1_categories),
    )


def to_taxonomy_json(
    dom_result: DomInspectionResult,
    *,
    source_url: str,
    discovered_at: str,
) -> str:
    counts = compute_counts(dom_result)
    collisions = dom_result.collisions
    payload = {
        "discovered_at": discovered_at,
        "source_url": source_url,
        "discovery_method": "static_dom" if dom_result.is_fully_static else "partial_static_dom",
        "menu1_count": counts.menu1_count,
        "menu2_node_count": counts.menu2_node_count,
        "menu2_level_leaf_count": counts.menu2_level_leaf_count,
        "menu3_level_leaf_count": counts.menu3_level_leaf_count,
        "menu3_combination_count": counts.menu3_level_leaf_count,  # OLD-style name, same value, kept for auditability
        "total_leaf_count": counts.total_leaf_count,
        "unique_menu3_count": counts.unique_menu3_count,
        "collision_count": counts.collision_count,
        "incomplete_menu1_count": counts.incomplete_menu1_count,
        "incomplete_menu1_categories": [
            {"menu1": c.menu1, "menu1_label": c.menu1_label}
            for c in dom_result.incomplete_menu1_categories
        ],
        "leaves": [
            {
                "menu1": leaf.menu1,
                "menu1_label": leaf.menu1_label,
                "menu2": leaf.menu2,
                "menu2_label": leaf.menu2_label,
                "menu3": leaf.menu3,
                "menu3_label": leaf.menu3_label,
                "leaf_level": leaf.leaf_level,
                "source_metric_key": leaf.source_metric_key,
                "label_resolution_method": leaf.label_resolution_method,
                "is_menu3_collision": leaf.menu3 in collisions if leaf.menu3 is not None else False,
            }
            for leaf in dom_result.leaves
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def to_taxonomy_csv(dom_result: DomInspectionResult) -> str:
    collisions = dom_result.collisions
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "menu1",
            "menu1_label",
            "menu2",
            "menu2_label",
            "menu3",
            "menu3_label",
            "leaf_level",
            "source_metric_key",
            "label_resolution_method",
            "is_menu3_collision",
        ]
    )
    for leaf in dom_result.leaves:
        writer.writerow(
            [
                leaf.menu1,
                leaf.menu1_label,
                leaf.menu2,
                leaf.menu2_label,
                leaf.menu3 or "",  # nullable menu3 serializes as an empty CSV field, never a fabricated value
                leaf.menu3_label or "",
                leaf.leaf_level,
                leaf.source_metric_key,
                leaf.label_resolution_method,
                (leaf.menu3 in collisions) if leaf.menu3 is not None else False,
            ]
        )
    return buf.getvalue()
