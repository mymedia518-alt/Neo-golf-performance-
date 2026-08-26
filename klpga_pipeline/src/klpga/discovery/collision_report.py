"""Collision report — duplicate/ambiguous menu identifiers.

Per explicit instruction: menu3 must never be treated as globally
unique, and any collision must be preserved and reported, never
silently deduplicated. This module distinguishes:

  A. same menu3 reused under different menu1/menu2 paths
  B. same menu3 reused with different labels (the same code mapping to
     more than one Korean label — the real Round-1 finding)
  C. exact duplicate DOM entries — the SAME (menu1, menu2, menu3,
     label) tuple appearing more than once, which is a markup/parsing
     artifact rather than a real taxonomy ambiguity

These are NOT automatically treated as equivalent — a caller reading
this report can tell which situation it's looking at. Only
menu3-level leaves participate in menu3-code collision analysis
(a menu2-level leaf has no menu3 to collide on).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from klpga.discovery.menu_taxonomy import DomInspectionResult, MenuLeaf


@dataclass
class LabelCodeCollision:
    label: str
    codes: list[str]


@dataclass
class CodeLabelCollision:
    code: str
    labels: list[str]


@dataclass
class ExactDuplicateEntry:
    identity: tuple
    label: str
    count: int


@dataclass
class ResponseHashCollision:
    response_hash: str
    source_metric_keys: list[str]


@dataclass
class CollisionReport:
    menu3_collisions: dict[str, list[MenuLeaf]]
    """menu3 -> the >1 leaves it appears under, exactly as found —
    never deduplicated. Category A+B combined; see the more specific
    buckets below to tell them apart."""

    menu2_level_collisions: dict[str, list[MenuLeaf]]
    """Category A subset: same menu3 under different menu2 (same
    menu1)."""

    menu1_level_collisions: dict[str, list[MenuLeaf]]
    """Category A subset: same menu3 crossing different menu1
    entirely."""

    label_to_codes: list[LabelCodeCollision]
    code_to_labels: list[CodeLabelCollision]
    """Category B: same code, multiple labels — e.g. the real
    menu3="010102" finding."""

    exact_duplicates: list[ExactDuplicateEntry]
    """Category C: the identical (menu1, menu2, menu3, label) tuple
    appearing more than once — a markup/DOM artifact, not a semantic
    taxonomy ambiguity."""

    response_hash_collisions: list[ResponseHashCollision]
    response_hash_check_performed: bool
    """False in a Phase-A-only run — no response bodies exist yet to
    hash. True once Phase B response hashes are supplied."""


def _label_code_maps(leaves: list[MenuLeaf]) -> tuple[list[LabelCodeCollision], list[CodeLabelCollision]]:
    """Only meaningful for menu3-level leaves — a menu2-level leaf has
    no menu3 code to collide on."""
    label_to_codes: dict[str, set[str]] = {}
    code_to_labels: dict[str, set[str]] = {}
    for leaf in leaves:
        if leaf.leaf_level != "menu3":
            continue
        label_to_codes.setdefault(leaf.menu3_label, set()).add(leaf.menu3)
        code_to_labels.setdefault(leaf.menu3, set()).add(leaf.menu3_label)

    label_collisions = [
        LabelCodeCollision(label=label, codes=sorted(codes))
        for label, codes in label_to_codes.items()
        if len(codes) > 1 and label
    ]
    code_collisions = [
        CodeLabelCollision(code=code, labels=sorted(labels))
        for code, labels in code_to_labels.items()
        if len(labels) > 1
    ]
    return label_collisions, code_collisions


def _find_exact_duplicates(leaves: list[MenuLeaf]) -> list[ExactDuplicateEntry]:
    by_full_tuple: dict[tuple, int] = {}
    label_by_tuple: dict[tuple, str] = {}
    for leaf in leaves:
        label = leaf.menu3_label if leaf.leaf_level == "menu3" else leaf.menu2_label
        full = (leaf.identity, label)
        by_full_tuple[full] = by_full_tuple.get(full, 0) + 1
        label_by_tuple[full] = label

    return [
        ExactDuplicateEntry(identity=key[0], label=label_by_tuple[key], count=count)
        for key, count in by_full_tuple.items()
        if count > 1
    ]


def build_collision_report(
    dom_result: DomInspectionResult,
    response_hashes: Optional[dict[str, str]] = None,
) -> CollisionReport:
    """`response_hashes`, when supplied, maps source_metric_key ->
    a hash of that metric's response body (Phase B only). Left None
    for a Phase-A-only taxonomy run."""
    menu3_collisions = dom_result.collisions

    menu2_level: dict[str, list[MenuLeaf]] = {}
    menu1_level: dict[str, list[MenuLeaf]] = {}
    for menu3, leaves in menu3_collisions.items():
        menu1_values = {l.menu1 for l in leaves}
        menu2_values = {l.menu2 for l in leaves}
        if len(menu1_values) > 1:
            menu1_level[menu3] = leaves
        elif len(menu2_values) > 1:
            menu2_level[menu3] = leaves

    label_collisions, code_collisions = _label_code_maps(dom_result.leaves)
    exact_duplicates = _find_exact_duplicates(dom_result.leaves)

    hash_collisions: list[ResponseHashCollision] = []
    hash_check_performed = response_hashes is not None
    if response_hashes:
        by_hash: dict[str, list[str]] = {}
        for key, h in response_hashes.items():
            by_hash.setdefault(h, []).append(key)
        hash_collisions = [
            ResponseHashCollision(response_hash=h, source_metric_keys=sorted(keys))
            for h, keys in by_hash.items()
            if len(keys) > 1
        ]

    return CollisionReport(
        menu3_collisions=menu3_collisions,
        menu2_level_collisions=menu2_level,
        menu1_level_collisions=menu1_level,
        label_to_codes=label_collisions,
        code_to_labels=code_collisions,
        exact_duplicates=exact_duplicates,
        response_hash_collisions=hash_collisions,
        response_hash_check_performed=hash_check_performed,
    )


def render_collision_report_markdown(report: CollisionReport) -> str:
    lines = ["# KLPGA Metric Collision Report", ""]
    lines.append(
        "Generated from the discovered menu taxonomy. Nothing here is "
        "silently deduplicated — every collision found is listed with "
        "every leaf it involves. menu2-level leaves (no menu3) never "
        "participate in menu3-code collision checks below."
    )
    lines.append("")

    lines.append("## A. menu3 collisions (any level)")
    lines.append("")
    if not report.menu3_collisions:
        lines.append("None found.")
    else:
        for menu3, leaves in sorted(report.menu3_collisions.items()):
            lines.append(f"- `menu3={menu3}` appears under {len(leaves)} distinct (menu1, menu2) pairs:")
            for leaf in leaves:
                lines.append(
                    f"  - `{leaf.menu1}::{leaf.menu2}::{leaf.menu3}` "
                    f"({leaf.menu1_label} / {leaf.menu2_label} / {leaf.menu3_label})"
                )
    lines.append("")

    lines.append("## A1. Collisions across different menu2 (same menu1)")
    lines.append("")
    if not report.menu2_level_collisions:
        lines.append("None found.")
    else:
        for menu3, leaves in sorted(report.menu2_level_collisions.items()):
            lines.append(f"- `menu3={menu3}`: {[l.source_metric_key for l in leaves]}")
    lines.append("")

    lines.append("## A2. Collisions across different menu1")
    lines.append("")
    if not report.menu1_level_collisions:
        lines.append("None found.")
    else:
        for menu3, leaves in sorted(report.menu1_level_collisions.items()):
            lines.append(f"- `menu3={menu3}`: {[l.source_metric_key for l in leaves]}")
    lines.append("")

    lines.append("## B. Same code, multiple labels")
    lines.append("")
    if not report.code_to_labels:
        lines.append("None found.")
    else:
        for c in report.code_to_labels:
            lines.append(f"- `{c.code}` -> {c.labels}")
    lines.append("")

    lines.append("## B1. Same label, multiple codes")
    lines.append("")
    if not report.label_to_codes:
        lines.append("None found.")
    else:
        for c in report.label_to_codes:
            lines.append(f"- {c.label!r} -> {c.codes}")
    lines.append("")

    lines.append("## C. Exact duplicate DOM entries")
    lines.append("")
    lines.append(
        "The IDENTICAL (menu1, menu2, menu3, label) tuple appearing more "
        "than once — a markup/parsing artifact, not a semantic taxonomy "
        "ambiguity. Distinct from B, where the CODE repeats but the "
        "LABEL differs."
    )
    lines.append("")
    if not report.exact_duplicates:
        lines.append("None found.")
    else:
        for d in report.exact_duplicates:
            lines.append(f"- {d.identity} ({d.label!r}) appears {d.count} times")
    lines.append("")

    lines.append("## Identical response hashes across different source_metric_keys")
    lines.append("")
    if not report.response_hash_check_performed:
        lines.append(
            "Not applicable — this is a Phase A (taxonomy-only) run. No "
            "response bodies were fetched, so there is nothing to hash "
            "yet. This section will populate once Phase B validation "
            "supplies response hashes."
        )
    elif not report.response_hash_collisions:
        lines.append("None found.")
    else:
        for c in report.response_hash_collisions:
            lines.append(f"- hash `{c.response_hash}` shared by: {c.source_metric_keys}")
    lines.append("")

    return "\n".join(lines)
