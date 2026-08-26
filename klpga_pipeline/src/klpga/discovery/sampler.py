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
    `reject_malformed_leaves`) are defensively excluded here too, even
    though the caller is expected to have already called
    `reject_malformed_leaves` for its own reporting — belt-and-suspenders,
    since a malformed leaf must never reach a live request regardless
    of whether the caller remembered the separate reporting step.
    """
    valid_leaf_dicts, _rejected = reject_malformed_leaves(taxonomy.get("leaves", []))
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


def find_duplicate_identities(sample: list[SampledLeaf]) -> list[tuple]:
    """Sample-level data-quality check: if the sampler itself ever
    selected the same canonical identity twice, that's a bug in the
    sampler, not a real taxonomy finding — report it rather than
    silently double-counting."""
    seen: dict[tuple, int] = {}
    for leaf in sample:
        seen[leaf.identity] = seen.get(leaf.identity, 0) + 1
    return [identity for identity, count in seen.items() if count > 1]
