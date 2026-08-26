"""Menu-taxonomy discovery for the KLPGA official record interface.

Confirmed so far (see docs/KLPGA_OFFICIAL_DATA_MAP.md, Rounds 1-3):

  POST https://klpga.co.kr/load/record/loadLocationRecord
  form: season, menu1, menu2, menu3

The site's own `getRecord(menu1, menu2, menu3)` JS handler reads these
three identifiers from `data-menu1`/`data-menu2`/`data-menu3` attributes
on clickable menu elements (per the user's captured DevTools evidence).

NOT confirmed, and this module never guesses:
  - which page's HTML actually contains those data-menu* attributes
    (the caller supplies that HTML — this module has no hardcoded URL);
  - whether the full three-level tree is present in one static DOM, or
    whether some/all of it is built up via further AJAX calls as menu1
    or menu2 items are clicked.

`inspect_menu_dom()` reports what it actually found, per menu1 category,
rather than assuming a single global answer. A menu1 category with zero
discovered menu3 descendants is reported as needing further
investigation (a second, currently-unconfirmed endpoint) rather than
silently treated as "this category has no metrics."

Collision handling: per explicit instruction, `menu3` is NOT assumed
globally unique (Round 1 found `menu3=010102` reused under two visibly
different categories). The canonical identity for one discovered leaf
is the full `(menu1, menu2, menu3)` triple; `source_metric_key` below
is that triple joined for use as a dict/report key, and is deliberately
NOT deduplicated against — every occurrence is preserved as its own
`MenuLeaf`, even if two leaves share the same `source_metric_key`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag

_MENU1_ATTR = "data-menu1"
_MENU2_ATTR = "data-menu2"
_MENU3_ATTR = "data-menu3"


def _attr(tag: Tag, name: str) -> Optional[str]:
    """Case-insensitive attribute lookup — browser captures and JS
    dumps aren't always lowercase-consistent, matching this project's
    existing leaderboard_parser.py convention."""
    for key, value in tag.attrs.items():
        if key.lower() == name.lower():
            return value if isinstance(value, str) else " ".join(value)
    return None


def build_source_metric_key(menu1: str, menu2: str, menu3: str) -> str:
    """The `(menu1, menu2, menu3)` identity as a single string key, per
    explicit instruction. NOT globally unique by design — see module
    docstring. Never used to deduplicate discovered leaves."""
    return f"{menu1}::{menu2}::{menu3}"


@dataclass(frozen=True)
class MenuLeaf:
    """One discovered (menu1, menu2, menu3) combination with its
    Korean labels, exactly as found in the DOM — no inferred/guessed
    labels."""

    menu1: str
    menu1_label: str
    menu2: str
    menu2_label: str
    menu3: str
    menu3_label: str
    label_resolution_method: str
    """How menu1_label/menu2_label were resolved: "own_attrs" (all
    three data-menu* attrs plus their labels were on the same tag),
    "ancestor_walk" (menu1/menu2 label came from an ancestor element),
    or "unknown" (a label could not be confidently resolved — left as
    an empty string rather than guessed)."""

    @property
    def source_metric_key(self) -> str:
        return build_source_metric_key(self.menu1, self.menu2, self.menu3)


@dataclass
class Menu1Coverage:
    """Per-menu1-category completeness — the actionable unit for
    "which hierarchy level is missing," rather than one global flag,
    since different top-level categories may not all be at the same
    DOM depth."""

    menu1: str
    menu1_label: str
    leaf_count: int
    has_menu3_leaves: bool


@dataclass
class DomInspectionResult:
    leaves: list[MenuLeaf] = field(default_factory=list)
    menu1_coverage: list[Menu1Coverage] = field(default_factory=list)

    @property
    def menu1_count(self) -> int:
        return len(self.menu1_coverage)

    @property
    def incomplete_menu1_categories(self) -> list[Menu1Coverage]:
        """menu1 categories found in the DOM with zero discovered
        menu3 leaves — these need a second (currently unconfirmed)
        request to unfold, and this module will not guess one."""
        return [c for c in self.menu1_coverage if not c.has_menu3_leaves]

    @property
    def is_fully_static(self) -> bool:
        """True only if every discovered menu1 category also has at
        least one discovered menu3 leaf — i.e. the whole tree was
        present in one static DOM, zero additional requests needed."""
        return self.menu1_count > 0 and not self.incomplete_menu1_categories

    @property
    def unique_menu3_values(self) -> set[str]:
        return {leaf.menu3 for leaf in self.leaves}

    @property
    def collisions(self) -> dict[str, list[MenuLeaf]]:
        """menu3 codes that appear as more than one discovered leaf —
        preserved explicitly, never silently deduplicated. This
        deliberately does NOT require the colliding leaves to differ
        in menu1/menu2: the real Round-1 finding
        (menu3="010102" appearing twice under the SAME menu1/menu2,
        "Tee"/"Tee01", with two different labels) is exactly the case
        this must catch — requiring a different (menu1, menu2) pair
        would miss it entirely. Keyed by the bare menu3 code."""
        by_menu3: dict[str, list[MenuLeaf]] = {}
        for leaf in self.leaves:
            by_menu3.setdefault(leaf.menu3, []).append(leaf)
        return {menu3: leaves for menu3, leaves in by_menu3.items() if len(leaves) > 1}


def _find_ancestor_with_attr(tag: Tag, attr_name: str) -> Optional[Tag]:
    for ancestor in tag.parents:
        if isinstance(ancestor, Tag) and _attr(ancestor, attr_name) is not None:
            return ancestor
    return None


def inspect_menu_dom(html: str) -> DomInspectionResult:
    """Parse the given HTML (the caller fetched it — this function
    never fetches anything itself) for `data-menu1/2/3` attributes and
    build the discovered taxonomy tree.

    Supports two DOM shapes without assuming either:
      1. FLAT: a single clickable element carries all three
         data-menu1/2/3 attributes at once (the most likely shape,
         since the confirmed `getRecord(menu1, menu2, menu3)` handler
         receives all three identifiers together).
      2. NESTED: menu3 is on a leaf element whose menu1/menu2 must be
         resolved by walking up to the nearest ancestor carrying that
         attribute.

    Every discovered leaf records which resolution strategy was used
    (`label_resolution_method`) so ambiguity is visible in the output
    rather than silently assumed.
    """
    soup = BeautifulSoup(html, "lxml")
    all_tags = soup.find_all(True)

    menu1_tags = [t for t in all_tags if _attr(t, _MENU1_ATTR) is not None]
    menu3_tags = [t for t in all_tags if _attr(t, _MENU3_ATTR) is not None]

    leaves: list[MenuLeaf] = []
    for tag in menu3_tags:
        menu3 = _attr(tag, _MENU3_ATTR) or ""
        menu3_label = tag.get_text(strip=True)

        own_menu1 = _attr(tag, _MENU1_ATTR)
        own_menu2 = _attr(tag, _MENU2_ATTR)
        if own_menu1 is not None and own_menu2 is not None:
            leaves.append(
                MenuLeaf(
                    menu1=own_menu1,
                    menu1_label="",  # not resolvable from this tag alone; see note below
                    menu2=own_menu2,
                    menu2_label="",
                    menu3=menu3,
                    menu3_label=menu3_label,
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
                    label_resolution_method="ancestor_walk",
                )
            )
            continue

        # menu3 found but menu1/menu2 could not be resolved either way —
        # do not guess; report the gap explicitly instead of dropping it.
        leaves.append(
            MenuLeaf(
                menu1="",
                menu1_label="",
                menu2="",
                menu2_label="",
                menu3=menu3,
                menu3_label=menu3_label,
                label_resolution_method="unknown",
            )
        )

    # menu1-level coverage: every distinct menu1 value seen anywhere,
    # cross-referenced against which ones have at least one resolved
    # menu3 leaf.
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
        leaf_count = sum(1 for leaf in leaves if leaf.menu1 == menu1)
        coverage.append(
            Menu1Coverage(
                menu1=menu1,
                menu1_label=label,
                leaf_count=leaf_count,
                has_menu3_leaves=leaf_count > 0,
            )
        )

    return DomInspectionResult(leaves=leaves, menu1_coverage=coverage)
