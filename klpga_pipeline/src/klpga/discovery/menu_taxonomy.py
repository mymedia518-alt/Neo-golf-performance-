"""Menu-taxonomy discovery for the KLPGA official record interface.

Confirmed so far (see docs/KLPGA_OFFICIAL_DATA_MAP.md, Rounds 1-3):

  POST https://klpga.co.kr/load/record/loadLocationRecord
  form: season, menu1, menu2, menu3

The site's own `getRecord(menu1, menu2, menu3)` JS handler reads these
identifiers from `data-menu1`/`data-menu2`/`data-menu3` attributes on
clickable menu elements (per the user's captured DevTools evidence).

**Round 3 patch — metric leaves can terminate at menu2, not only
menu3.** Directly confirmed via live DevTools capture: the real
request for SG Total is

    season=2025
    menu1=Sg
    menu2=Total

with NO menu3 form field at all — not a missing value, a legitimately
shorter request. The earlier version of this module implicitly assumed
every valid metric required all three levels, which is why a live
Phase A run reported the `Sg` and `All` categories as "incomplete"
when they were actually just menu2-level leaves this module didn't
know how to recognize. Fixed here: a tag with its own
`data-menu1`/`data-menu2` and a blank-or-absent `data-menu3`, which
also has no menu3-bearing descendant (i.e. it isn't a container
wrapping real menu3-level buttons), is now recognized as a genuine
`leaf_level="menu2"` metric leaf.

NOT confirmed, and this module never guesses:
  - which page's HTML actually contains those data-menu* attributes
    (the caller supplies that HTML — this module has no hardcoded URL);
  - whether the full tree is present in one static DOM, or whether
    some/all of it is built up via further AJAX calls;
  - whether "All" (전체기록보기) resolves as a menu2-level leaf, a
    menu1-only leaf, or something this module still can't recognize —
    that is for the next live run to show, not for this module to
    assume.

`inspect_menu_dom()` reports what it actually found, per menu1
category, rather than assuming a single global answer. A menu1
category is only reported incomplete if NEITHER a menu2-level nor a
menu3-level leaf could be resolved for it.

Collision handling: per explicit instruction, `menu3` is NOT assumed
globally unique (a live Round 3 run found 31 collisions among 241
unique menu3 codes). The canonical identity for one discovered leaf is
`(menu1, menu2)` for a menu2-level leaf, `(menu1, menu2, menu3)` for a
menu3-level leaf — see `MenuLeaf.identity`. `source_metric_key` is a
string serialization of that same identity for reporting/dict-keying
only, never used to deduplicate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag

_MENU1_ATTR = "data-menu1"
_MENU2_ATTR = "data-menu2"
_MENU3_ATTR = "data-menu3"

LEAF_LEVEL_MENU2 = "menu2"
LEAF_LEVEL_MENU3 = "menu3"


def _attr(tag: Tag, name: str) -> Optional[str]:
    """Case-insensitive attribute lookup — browser captures and JS
    dumps aren't always lowercase-consistent, matching this project's
    existing leaderboard_parser.py convention."""
    for key, value in tag.attrs.items():
        if key.lower() == name.lower():
            return value if isinstance(value, str) else " ".join(value)
    return None


def _has_value(tag: Tag, name: str) -> bool:
    """True only if the attribute is present AND non-blank. An
    attribute that's absent entirely and one that's present-but-empty
    are treated identically as "no value" — per the directly confirmed
    SG evidence, the real request for Sg/Total carries no menu3 form
    field at all, so this module does not try to distinguish "attribute
    missing" from "attribute empty" as two different signals."""
    return bool(_attr(tag, name))


def build_source_metric_key(menu1: str, menu2: str, menu3: Optional[str] = None) -> str:
    """String serialization of the canonical identity, for
    reporting/dict-keying only — never for deduplication. `menu3=None`
    (or blank) produces a two-part key ("menu1::menu2"); a real menu3
    value produces the full three-part key, unchanged from Round 3's
    original format."""
    parts = [menu1, menu2]
    if menu3:
        parts.append(menu3)
    return "::".join(parts)


@dataclass(frozen=True)
class MenuLeaf:
    """One discovered metric leaf, exactly as found in the DOM — no
    inferred/guessed labels or codes. `menu3`/`menu3_label` are `None`
    for a menu2-level leaf; leaf depth is never flattened away."""

    menu1: str
    menu1_label: str
    menu2: str
    menu2_label: str
    menu3: Optional[str]
    menu3_label: Optional[str]
    leaf_level: str
    """LEAF_LEVEL_MENU2 or LEAF_LEVEL_MENU3 — which level this metric
    request actually terminates at. Never inferred from menu3 being
    merely absent on one tag without confirming no menu3-bearing
    descendant exists (see `_has_menu3_descendant`)."""
    label_resolution_method: str
    """How the labels were resolved: "own_attrs" (identifiers and
    label were on the same tag), "ancestor_walk" (menu1/menu2 label
    came from an ancestor element — menu3-level leaves only), or
    "unknown" (could not be confidently resolved — left empty rather
    than guessed)."""

    @property
    def identity(self) -> tuple:
        """The structured canonical identity. `(menu1, menu2)` for a
        menu2-level leaf, `(menu1, menu2, menu3)` for a menu3-level
        leaf — never menu3 alone, which a live run already proved is
        not globally unique (31 collisions among 241 unique codes)."""
        if self.leaf_level == LEAF_LEVEL_MENU3:
            return (self.menu1, self.menu2, self.menu3)
        return (self.menu1, self.menu2)

    @property
    def source_metric_key(self) -> str:
        return build_source_metric_key(self.menu1, self.menu2, self.menu3 if self.leaf_level == LEAF_LEVEL_MENU3 else None)


@dataclass
class Menu1Coverage:
    """Per-menu1-category completeness — the actionable unit for
    "which hierarchy level is missing," rather than one global flag,
    since different top-level categories may not all be at the same
    DOM depth or even the same leaf depth."""

    menu1: str
    menu1_label: str
    menu2_leaf_count: int
    menu3_leaf_count: int

    @property
    def has_resolved_leaves(self) -> bool:
        """A category is resolved if it has AT LEAST ONE leaf at
        either level — it is emphatically NOT incomplete merely
        because it has zero menu3 leaves (that was the Round 3 bug:
        Sg and All were both wrongly reported incomplete on that
        basis alone)."""
        return self.menu2_leaf_count > 0 or self.menu3_leaf_count > 0


@dataclass
class DomInspectionResult:
    leaves: list[MenuLeaf] = field(default_factory=list)
    menu1_coverage: list[Menu1Coverage] = field(default_factory=list)

    @property
    def menu1_count(self) -> int:
        return len(self.menu1_coverage)

    @property
    def menu2_level_leaves(self) -> list[MenuLeaf]:
        return [leaf for leaf in self.leaves if leaf.leaf_level == LEAF_LEVEL_MENU2]

    @property
    def menu3_level_leaves(self) -> list[MenuLeaf]:
        return [leaf for leaf in self.leaves if leaf.leaf_level == LEAF_LEVEL_MENU3]

    @property
    def menu2_node_count(self) -> int:
        """Distinct (menu1, menu2) pairs across ALL leaves, both
        levels — "menu2 nodes found," a structural count distinct from
        "menu2-level leaves found" (a menu2 node can host menu3-level
        leaves underneath it and never itself be a leaf)."""
        return len({(leaf.menu1, leaf.menu2) for leaf in self.leaves})

    @property
    def incomplete_menu1_categories(self) -> list[Menu1Coverage]:
        """menu1 categories with NEITHER a resolved menu2-level NOR a
        resolved menu3-level leaf — these need further live
        investigation, and this module will not guess a second
        endpoint or a fabricated leaf to fill the gap."""
        return [c for c in self.menu1_coverage if not c.has_resolved_leaves]

    @property
    def is_fully_static(self) -> bool:
        return self.menu1_count > 0 and not self.incomplete_menu1_categories

    @property
    def unique_menu3_values(self) -> set[str]:
        return {leaf.menu3 for leaf in self.menu3_level_leaves}

    @property
    def collisions(self) -> dict[str, list[MenuLeaf]]:
        """menu3 codes that appear as more than one discovered
        menu3-level leaf — preserved explicitly, never silently
        deduplicated. Only meaningful for menu3-level leaves (a
        menu2-level leaf has no menu3 to collide on). This
        deliberately does NOT require the colliding leaves to differ
        in menu1/menu2: the real Round-1 finding (menu3="010102"
        appearing twice under the SAME menu1/menu2 with two different
        labels) is exactly the case this must catch. Keyed by the bare
        menu3 code."""
        by_menu3: dict[str, list[MenuLeaf]] = {}
        for leaf in self.menu3_level_leaves:
            by_menu3.setdefault(leaf.menu3, []).append(leaf)
        return {menu3: leaves for menu3, leaves in by_menu3.items() if len(leaves) > 1}


def _find_ancestor_with_attr(tag: Tag, attr_name: str) -> Optional[Tag]:
    for ancestor in tag.parents:
        if isinstance(ancestor, Tag) and _attr(ancestor, attr_name) is not None:
            return ancestor
    return None


def _has_menu3_descendant(tag: Tag) -> bool:
    """True if ANY descendant carries a data-menu3 attribute at all
    (even blank) — used to tell a real menu2-level leaf apart from a
    container/wrapper element that merely groups menu3-level buttons
    underneath it and is not itself a clickable metric."""
    return tag.find(attrs={_MENU3_ATTR: True}) is not None


def inspect_menu_dom(html: str) -> DomInspectionResult:
    """Parse the given HTML (the caller fetched it — this function
    never fetches anything itself) for `data-menu1/2/3` attributes and
    build the discovered taxonomy tree, at whichever depth each metric
    actually terminates.

    Two independent detection passes, run over the same tag list:
      1. menu3-level leaves — any tag with a NON-BLANK data-menu3,
         resolved via own-attrs first then ancestor-walk (unchanged
         from the original Round 3 implementation).
      2. menu2-level leaves — any tag with its own data-menu1 and
         data-menu2, a blank/absent data-menu3, and no menu3-bearing
         descendant. No ancestor-walk variant exists for this pass
         yet — an unresolved menu2-level leaf embedded via ancestor
         nesting (rather than all attrs on one clickable tag) is a
         known, explicitly flagged gap, not a silently guessed one.
    """
    soup = BeautifulSoup(html, "lxml")
    all_tags = soup.find_all(True)

    menu1_tags = [t for t in all_tags if _attr(t, _MENU1_ATTR) is not None]

    leaves: list[MenuLeaf] = []

    # --- Pass 1: menu3-level leaves ---
    menu3_tags = [t for t in all_tags if _has_value(t, _MENU3_ATTR)]
    for tag in menu3_tags:
        menu3 = _attr(tag, _MENU3_ATTR) or ""
        menu3_label = tag.get_text(strip=True)

        own_menu1 = _attr(tag, _MENU1_ATTR)
        own_menu2 = _attr(tag, _MENU2_ATTR)
        if own_menu1 is not None and own_menu2 is not None:
            leaves.append(
                MenuLeaf(
                    menu1=own_menu1,
                    menu1_label="",
                    menu2=own_menu2,
                    menu2_label="",
                    menu3=menu3,
                    menu3_label=menu3_label,
                    leaf_level=LEAF_LEVEL_MENU3,
                    label_resolution_method="own_attrs",
                )
            )
            continue

        menu1_ancestor = _find_ancestor_with_attr(tag, _MENU1_ATTR)
        menu2_ancestor = _find_ancestor_with_attr(tag, _MENU2_ATTR)
        if menu1_ancestor is not None and menu2_ancestor is not None:
            leaves.append(
                MenuLeaf(
                    menu1=_attr(menu1_ancestor, _MENU1_ATTR) or "",
                    menu1_label=menu1_ancestor.get_text(strip=True),
                    menu2=_attr(menu2_ancestor, _MENU2_ATTR) or "",
                    menu2_label=menu2_ancestor.get_text(strip=True),
                    menu3=menu3,
                    menu3_label=menu3_label,
                    leaf_level=LEAF_LEVEL_MENU3,
                    label_resolution_method="ancestor_walk",
                )
            )
            continue

        leaves.append(
            MenuLeaf(
                menu1="",
                menu1_label="",
                menu2="",
                menu2_label="",
                menu3=menu3,
                menu3_label=menu3_label,
                leaf_level=LEAF_LEVEL_MENU3,
                label_resolution_method="unknown",
            )
        )

    # --- Pass 2: menu2-level leaves ---
    for tag in all_tags:
        if not _has_value(tag, _MENU1_ATTR) or not _has_value(tag, _MENU2_ATTR):
            continue
        if _has_value(tag, _MENU3_ATTR):
            continue  # already handled as a menu3-level leaf above
        if _has_menu3_descendant(tag):
            continue  # a container wrapping real menu3-level buttons, not a leaf itself
        leaves.append(
            MenuLeaf(
                menu1=_attr(tag, _MENU1_ATTR) or "",
                menu1_label="",
                menu2=_attr(tag, _MENU2_ATTR) or "",
                menu2_label=tag.get_text(strip=True),
                menu3=None,
                menu3_label=None,
                leaf_level=LEAF_LEVEL_MENU2,
                label_resolution_method="own_attrs",
            )
        )

    # menu1-level coverage: every distinct menu1 value seen anywhere,
    # cross-referenced against which ones have at least one resolved
    # leaf at EITHER level.
    seen_menu1: dict[str, str] = {}
    for tag in menu1_tags:
        code = _attr(tag, _MENU1_ATTR) or ""
        if code and code not in seen_menu1:
            seen_menu1[code] = tag.get_text(strip=True)
    for leaf in leaves:
        if leaf.menu1 and leaf.menu1 not in seen_menu1:
            seen_menu1[leaf.menu1] = leaf.menu1_label

    coverage = []
    for menu1, label in seen_menu1.items():
        menu2_count = sum(1 for leaf in leaves if leaf.menu1 == menu1 and leaf.leaf_level == LEAF_LEVEL_MENU2)
        menu3_count = sum(1 for leaf in leaves if leaf.menu1 == menu1 and leaf.leaf_level == LEAF_LEVEL_MENU3)
        coverage.append(
            Menu1Coverage(
                menu1=menu1,
                menu1_label=label,
                menu2_leaf_count=menu2_count,
                menu3_leaf_count=menu3_count,
            )
        )

    return DomInspectionResult(leaves=leaves, menu1_coverage=coverage)
