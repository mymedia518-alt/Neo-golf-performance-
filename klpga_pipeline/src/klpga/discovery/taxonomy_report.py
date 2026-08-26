"""Phase A output artifacts — KLPGA_RECORD_TAXONOMY_DISCOVERED.json/.csv
and the taxonomy count summary. Pure formatting over an already-built
`DomInspectionResult`; performs no network access itself.
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
    menu2_count: int
    menu3_combination_count: int
    """Total (menu1, menu2, menu3) leaves discovered — includes every
    collision occurrence, not deduplicated."""
    unique_menu3_count: int
    """Distinct menu3 codes alone, regardless of which menu1/menu2
    they appear under."""
    collision_count: int
    """Number of distinct menu3 codes that appear under more than one
    (menu1, menu2) pair."""
    incomplete_menu1_count: int
    """menu1 categories discovered with zero resolved menu3 leaves —
    candidates needing a second, currently-unconfirmed request to
    unfold."""


def compute_counts(dom_result: DomInspectionResult) -> TaxonomyCounts:
    unique_menu2 = {(leaf.menu1, leaf.menu2) for leaf in dom_result.leaves}
    return TaxonomyCounts(
        menu1_count=dom_result.menu1_count,
        menu2_count=len(unique_menu2),
        menu3_combination_count=len(dom_result.leaves),
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
        "menu2_count": counts.menu2_count,
        "menu3_combination_count": counts.menu3_combination_count,
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
                "source_metric_key": leaf.source_metric_key,
                "label_resolution_method": leaf.label_resolution_method,
                "is_menu3_collision": leaf.menu3 in collisions,
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
                leaf.menu3,
                leaf.menu3_label,
                leaf.source_metric_key,
                leaf.label_resolution_method,
                leaf.menu3 in collisions,
            ]
        )
    return buf.getvalue()
