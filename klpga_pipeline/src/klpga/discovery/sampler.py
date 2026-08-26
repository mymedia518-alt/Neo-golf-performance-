"""Phase B1 — representative sample selection over an already-produced
Phase A taxonomy (see taxonomy_report.py's JSON shape). Selects a small
(~12-20) diverse subset for response-schema discovery — never the full
discovered taxonomy, and never a fabricated entry: every selected leaf
must come from the taxonomy input itself.

Selection is deterministic (no randomness), so the same taxonomy input
always produces the same sample — required for the discovery log to be
auditable and for tests to be reproducible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SampledLeaf:
    menu1: str
    menu1_label: str
    menu2: str
    menu2_label: str
    menu3: Optional[str]
    menu3_label: Optional[str]
    leaf_level: str
    source_metric_key: str

    @property
    def identity(self) -> tuple:
        if self.leaf_level == "menu3":
            return (self.menu1, self.menu2, self.menu3)
        return (self.menu1, self.menu2)


def _leaf_from_dict(d: dict) -> SampledLeaf:
    return SampledLeaf(
        menu1=d["menu1"],
        menu1_label=d.get("menu1_label", ""),
        menu2=d["menu2"],
        menu2_label=d.get("menu2_label", ""),
        menu3=d.get("menu3"),
        menu3_label=d.get("menu3_label"),
        leaf_level=d["leaf_level"],
        source_metric_key=d["source_metric_key"],
    )


def _is_malformed_leaf_dict(d: dict) -> bool:
    """A leaf with a blank/missing menu1 or menu2 cannot be issued as a
    live request at all (menu1/menu2 are required POST form fields —
    see menu_taxonomy.py's module docstring). This is NOT a sampler bug
    in the sense of the sampler inventing bad data — it comes from
    `inspect_menu_dom`'s Pass 1 fallback (menu_taxonomy.py): a tag
    carrying a non-blank `data-menu3` whose ancestor chain never
    resolves a `data-menu1`/`data-menu2` identity is still recorded as
    a `MenuLeaf` (menu1="", menu2="", label_resolution_method="unknown")
    rather than silently dropped, per this project's "preserve every
    discovered thing rather than deduplicate/drop it away" evidence
    discipline. That preservation is correct for the taxonomy's own
    JSON output (an audit trail of exactly what the DOM scan found,
    including what it could NOT resolve) — but such a leaf is never
    safe to select into a live request, so the sampler must reject it
    here rather than forward it as if it were a genuine, requestable
    metric."""
    return not d.get("menu1") or not d.get("menu2")


def reject_malformed_leaves(raw_leaves: list[dict]) -> tuple[list[dict], list[dict]]:
    """Splits taxonomy["leaves"] into (valid, rejected) BEFORE any
    sampling happens. Returned separately (rather than just filtering
    silently) so a caller can report exactly how many — and which —
    malformed leaves were excluded, per explicit instruction that this
    must never be a silent drop."""
    valid = [d for d in raw_leaves if not _is_malformed_leaf_dict(d)]
    rejected = [d for d in raw_leaves if _is_malformed_leaf_dict(d)]
    return valid, rejected


_CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES = frozenset({"All"})
"""Kept in sync with klpga.discovery.menu_taxonomy's
CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES — duplicated as a plain
frozenset (not imported) so the sampler has zero dependency on the
menu_taxonomy module's DOM-scraping machinery, matching this module's
existing "operates on the already-produced taxonomy dict, nothing
more" scope. See that module's docstring for the real evidence: a
MENU2-LEVEL (no menu3) menu1="All" request returned 0 rows and a body
containing the entire navigation menu tree itself (data-menu1/menu2/
menu3 spanning every confirmed family) — a container/navigation page,
never a requestable metric. Deliberately does NOT cover a menu3-level
leaf whose menu1 happens to read "All" (e.g. via preceding_context
DOM resolution) — no request of that shape has ever been confirmed to
behave the same way; see the fallback's own leaf_level check below."""


def _is_navigation_container_leaf_dict(d: dict) -> bool:
    """True if `node_type` explicitly says NAVIGATION_CONTAINER (a
    taxonomy JSON produced by the current menu_taxonomy.py), OR — for
    an older taxonomy JSON produced before node_type existed — if this
    is a MENU2-LEVEL leaf (menu3 absent — the exact confirmed request
    shape) whose menu1 is one of the specifically-evidenced navigation
    values. A menu3-level leaf is never excluded on menu1 value alone,
    even in this fallback path. Never a broader name-pattern guess."""
    node_type = d.get("node_type")
    if node_type is not None:
        return node_type == "NAVIGATION_CONTAINER"
    return d.get("leaf_level") == "menu2" and d.get("menu1") in _CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES


def reject_navigation_container_leaves(raw_leaves: list[dict]) -> tuple[list[dict], list[dict]]:
    """Splits taxonomy["leaves"] into (valid, rejected) by node_type,
    BEFORE any sampling happens — parallel to `reject_malformed_leaves`
    but a distinct rejection category, never silently merged with it:
    a malformed leaf has no usable identity at all, while a navigation
    container has a perfectly valid identity that simply does not
    point at player data. Confirmed real evidence: `All::Sg` returned
    HTTP 200, 0 rows, and a body containing the full navigation menu
    tree — see menu_taxonomy.py's CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES."""
    valid = [d for d in raw_leaves if not _is_navigation_container_leaf_dict(d)]
    rejected = [d for d in raw_leaves if _is_navigation_container_leaf_dict(d)]
    return valid, rejected


_PRIORITY_FAMILIES = ["Sg", "Tee", "Approach", "Around", "Putt"]
"""Round-robin family priority order — the five confirmed real stat
families this project has directly reported evidence for (see
docs/KLPGA_OFFICIAL_DATA_MAP.md). Any other menu1 family (in
particular "All"/전체기록보기, a navigation/grouping aggregator rather
than an independently useful metric — see the Phase B1.1 live-run
finding) sorts after all five of these, so a small sample's scarce
live-request slots go to substantive stat families first. This is a
selection-order heuristic only — it does not claim "All" produces an
uninteresting schema, only that it should not compete on equal footing
with the five confirmed families for a slot in a small sample."""


def _family_sort_key(menu1: str) -> tuple:
    if menu1 in _PRIORITY_FAMILIES:
        return (0, _PRIORITY_FAMILIES.index(menu1))
    return (1, menu1)


def select_representative_sample(
    taxonomy: dict,
    target_count: int = 16,
    per_family_cap: int = 4,
) -> list[SampledLeaf]:
    """`taxonomy` is a dict matching taxonomy_report.to_taxonomy_json's
    shape (i.e. already loaded from
    docs/discovery/KLPGA_RECORD_TAXONOMY_DISCOVERED.json, or an
    equivalent in-memory structure for testing). Only leaves that
    literally appear in `taxonomy["leaves"]` can ever be selected —
    this function never invents a menu1/menu2/menu3 combination.

    Strategy, deterministic and auditable:
      1. Group discovered leaves by menu1 (family).
      2. Within each family, prefer menu2-level leaves first (rarer,
         structurally distinct — e.g. the confirmed SG Total case),
         then take a spread of menu3-level leaves across DISTINCT
         menu2 groups (so a family with many menu3 leaves under one
         menu2 doesn't crowd out its other menu2 groups), up to
         `per_family_cap` per family.
      3. Stop once `target_count` is reached, cycling through families
         round-robin so no single huge family (e.g. 276 menu3 leaves)
         dominates the sample at the expense of smaller ones.

    Sorted by (menu1, menu2, menu3 or "") throughout for determinism —
    the input list's own order is not relied upon.

    Malformed leaves (blank/missing menu1 or menu2 — see
    `reject_malformed_leaves`) and navigation/container nodes (e.g. any
    menu1="All" entry — see `reject_navigation_container_leaves`) are
    defensively excluded here too, even though the caller is expected
    to have already called both rejection functions for its own
    reporting — belt-and-suspenders, since neither may ever reach a
    live request regardless of whether the caller remembered the
    separate reporting step.
    """
    valid_leaf_dicts, _rejected_malformed = reject_malformed_leaves(taxonomy.get("leaves", []))
    valid_leaf_dicts, _rejected_navigation = reject_navigation_container_leaves(valid_leaf_dicts)
    leaves = [_leaf_from_dict(d) for d in valid_leaf_dicts]

    by_family: dict[str, list[SampledLeaf]] = {}
    for leaf in leaves:
        by_family.setdefault(leaf.menu1, []).append(leaf)

    per_family_candidates: dict[str, list[SampledLeaf]] = {}
    for menu1, family_leaves in by_family.items():
        menu2_level = sorted(
            (l for l in family_leaves if l.leaf_level == "menu2"), key=lambda l: (l.menu2,)
        )
        menu3_level = sorted(
            (l for l in family_leaves if l.leaf_level == "menu3"), key=lambda l: (l.menu2, l.menu3 or "")
        )

        # Spread menu3-level picks across distinct menu2 groups rather
        # than taking the first N in sorted order (which could all be
        # the same menu2).
        menu3_by_menu2: dict[str, list[SampledLeaf]] = {}
        for leaf in menu3_level:
            menu3_by_menu2.setdefault(leaf.menu2, []).append(leaf)
        spread_menu3: list[SampledLeaf] = []
        menu2_groups = sorted(menu3_by_menu2)
        i = 0
        while any(menu3_by_menu2[m2] for m2 in menu2_groups) and len(spread_menu3) < per_family_cap * 2:
            m2 = menu2_groups[i % len(menu2_groups)]
            if menu3_by_menu2[m2]:
                spread_menu3.append(menu3_by_menu2[m2].pop(0))
            i += 1

        candidates = menu2_level + spread_menu3
        per_family_candidates[menu1] = candidates[:per_family_cap]

    sample: list[SampledLeaf] = []
    families = sorted(per_family_candidates, key=_family_sort_key)
    cursors = {f: 0 for f in families}
    while len(sample) < target_count and any(cursors[f] < len(per_family_candidates[f]) for f in families):
        for f in families:
            if len(sample) >= target_count:
                break
            idx = cursors[f]
            if idx < len(per_family_candidates[f]):
                sample.append(per_family_candidates[f][idx])
                cursors[f] = idx + 1

    return sample


def _canonical_entry_to_leaf_dict(entry: dict) -> dict:
    """Adapts one entry of `canonical_plan.build_canonical_plan`'s
    `plan` list (`{menu1, menu2, menu3, leaf_level, identity_key,
    label, node_type, evidence_source}`) into the taxonomy-leaf dict
    shape `_leaf_from_dict`/`select_representative_sample` already
    consume. Every field comes directly from the canonical-plan entry
    — nothing here is inferred or guessed. `label` is placed on
    whichever of menu2_label/menu3_label matches the entry's own
    `leaf_level` (the canonical plan only ever populates one of the
    two, per `canonical_plan._label`), never both."""
    leaf_level = entry.get("leaf_level")
    label = entry.get("label")
    return {
        "menu1": entry.get("menu1"),
        "menu1_label": "",
        "menu2": entry.get("menu2"),
        "menu2_label": label if leaf_level == "menu2" else "",
        "menu3": entry.get("menu3"),
        "menu3_label": label if leaf_level == "menu3" else None,
        "leaf_level": leaf_level,
        "source_metric_key": entry.get("evidence_source") or entry.get("identity_key"),
        "node_type": entry.get("node_type", "REQUESTABLE_METRIC_LEAF"),
    }


def select_representative_sample_from_canonical_plan(
    plan: list[dict],
    target_count: int = 20,
    per_family_cap: int = 4,
) -> list[SampledLeaf]:
    """Phase B1 sampling sourced from the canonical request plan
    (`docs/discovery/KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json`'s
    `canonical_requestable_metrics` list) rather than a raw Phase A
    taxonomy JSON. `plan` is already malformed-free and
    navigation-free by construction (see `canonical_plan.py`'s
    filtering order), so this reuses `select_representative_sample`'s
    existing family round-robin strategy via `_canonical_entry_to_leaf_dict`
    with no separate rejection pass needed.

    On top of that base sample, this deterministically guarantees
    coverage of BOTH a colliding menu3 identity (a menu3 code shared
    by more than one canonical entry — see
    `CanonicalPlanCounts.menu3_collision_count`) and a non-colliding
    one, per explicit instruction that a Phase B1 sample must include
    "collision/non-collision identities." If the base round-robin
    sample already contains one of each, nothing is added. Otherwise
    exactly one entry is appended per missing category — chosen
    deterministically (sorted by (menu1, menu2, menu3)), never at
    random, and never a duplicate of an identity already in the
    sample. This can push the sample very slightly above
    `target_count` (by at most 2), which is expected and stays well
    within the instructed ~12-20 bound for realistic target_count
    values."""
    adapted_leaves = [_canonical_entry_to_leaf_dict(entry) for entry in plan]
    sample = select_representative_sample(
        {"leaves": adapted_leaves}, target_count=target_count, per_family_cap=per_family_cap
    )

    menu3_counts: dict[str, int] = {}
    for entry in plan:
        if entry.get("leaf_level") == "menu3" and entry.get("menu3"):
            menu3_counts[entry["menu3"]] = menu3_counts.get(entry["menu3"], 0) + 1
    colliding_codes = sorted(code for code, count in menu3_counts.items() if count > 1)
    non_colliding_codes = sorted(code for code, count in menu3_counts.items() if count == 1)

    def _has_coverage(colliding: bool) -> bool:
        return any(
            leaf.leaf_level == "menu3" and (menu3_counts.get(leaf.menu3, 0) > 1) == colliding
            for leaf in sample
        )

    def _first_entry_for_menu3(code: str) -> Optional[dict]:
        candidates = sorted(
            (e for e in plan if e.get("leaf_level") == "menu3" and e.get("menu3") == code),
            key=lambda e: (e.get("menu1") or "", e.get("menu2") or "", e.get("menu3") or ""),
        )
        return candidates[0] if candidates else None

    sample_identities = {leaf.identity for leaf in sample}
    for codes, want_colliding in ((colliding_codes, True), (non_colliding_codes, False)):
        if not codes or _has_coverage(want_colliding):
            continue
        entry = _first_entry_for_menu3(codes[0])
        if entry is None:
            continue
        leaf = _leaf_from_dict(_canonical_entry_to_leaf_dict(entry))
        if leaf.identity not in sample_identities:
            sample.append(leaf)
            sample_identities.add(leaf.identity)

    return sample


def select_full_canonical_plan(plan: list[dict]) -> list[SampledLeaf]:
    """Phase B2 (Round 9 follow-up) — returns EVERY entry of the
    canonical request plan as a `SampledLeaf`, with NO sampling and NO
    `per_family_cap`: unlike `select_representative_sample_from_
    canonical_plan` (a deliberately small, round-robin-capped
    REPRESENTATIVE sample for Phase B1), this is the full-sweep source
    of truth for `scripts/29_execute_phase_b2_full_sweep.py`. The
    canonical plan is already malformed-free and navigation-free by
    construction (see `canonical_plan.py`), so no rejection pass runs
    here either.

    Sorted by (menu1, menu2, menu3 or "") for deterministic order —
    the same ordering `select_representative_sample` already uses
    elsewhere in this module — so re-running against the same
    canonical plan always produces the same request sequence, which
    the B2 checkpoint's resume logic and this function's own tests
    both depend on."""
    leaves = [_leaf_from_dict(_canonical_entry_to_leaf_dict(entry)) for entry in plan]
    return sorted(leaves, key=lambda leaf: (leaf.menu1, leaf.menu2, leaf.menu3 or ""))


def find_duplicate_identities(sample: list[SampledLeaf]) -> list[tuple]:
    """Sample-level data-quality check: if the sampler itself ever
    selected the same canonical identity twice, that's a bug in the
    sampler, not a real taxonomy finding — report it rather than
    silently double-counting."""
    seen: dict[tuple, int] = {}
    for leaf in sample:
        seen[leaf.identity] = seen.get(leaf.identity, 0) + 1
    return [identity for identity, count in seen.items() if count > 1]
