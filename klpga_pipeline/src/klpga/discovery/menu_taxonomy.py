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

**Phase B1.1 note**: Pass 1's fallback branch (an unresolvable
`data-menu3` tag — no own attrs, no resolvable ancestor) preserves the
leaf with `menu1=""`/`menu2=""` rather than dropping it, per this
module's own "never silently drop a discovered thing" discipline (see
`test_unresolvable_menu3_is_preserved_not_dropped`). A live Windows run
surfaced exactly this shape twice for the same menu3 code (likely two
independently-orphaned DOM nodes, e.g. a desktop+mobile nav duplicate)
and it was initially misreported as a *sampler* bug. It is not: this
module's preservation is correct as an audit trail of what the DOM
scan could not resolve. The actual fix belongs at the sampling
boundary — see `klpga.discovery.sampler.reject_malformed_leaves`,
which excludes any blank-menu1/menu2 leaf before it can ever become a
live request.

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

NODE_TYPE_REQUESTABLE_METRIC_LEAF = "REQUESTABLE_METRIC_LEAF"
NODE_TYPE_NAVIGATION_CONTAINER = "NAVIGATION_CONTAINER"

CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES = frozenset({"All"})
"""CONFIRMED by direct live-response evidence (Phase B1 — see
docs/KLPGA_OFFICIAL_DATA_MAP.md's CLASS 2 root-cause section): a
request with menu1="All", menu2="Sg", **menu3=None** (a menu2-level
request — no menu3 field at all, the same request shape as the
confirmed SG Total case) returned HTTP 200, 33543 bytes, ZERO player
rows — and the response BODY ITSELF contained the full record
navigation menu tree (data-menu1/menu2/menu3 attributes spanning every
confirmed family: Sg/Total, Sg/TeeToGreen, Tee/Tee01/010101,
Tee/Tee01/010102, Tee/Tee01/010103, ...). That is a navigation/
container page, not player data.

**Scoped precisely to that confirmed request SHAPE — menu1="All" AND
leaf_level="menu2" (menu3=None) — never to menu1="All" alone.** A
menu3-level leaf (e.g. "All"::"Sg"::"<code>") has NEVER been
independently confirmed to behave the same way; no live request of
that shape has ever been made or evidenced. This distinction was
added after a real Phase A run against the fixed `preceding_context`
resolver (see the DOM-ancestry-fix round) showed why it matters: 272
genuine, menu3-level metric leaves structurally resolved their nearest
preceding `data-menu1` to a shared page-level element ALSO carrying
"All" — an artifact of the real page apparently wrapping its entire
metric-link listing in one such container, unrelated to the
CONFIRMED navigation-request evidence, which was specifically about a
menu2-level ("All"/family, no menu3) request. Classifying those 272
menu3-level leaves as NAVIGATION_CONTAINER purely because their
structurally-resolved menu1 field happened to read "All" would have
been exactly the "affirmative structural evidence" this project's own
discipline requires NOT to skip — the confirmed evidence never covered
that shape, so it must not exclude it. No other menu1 family has
equivalent navigation evidence either, at any leaf_level."""


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
    """How the identifiers were resolved: "own_attrs" (every
    identifier the leaf needed was present directly on the tag
    itself), "ancestor_walk" (at least one identifier came from a
    genuine ANCESTOR — either an ancestor's own `data-menu1`/
    `data-menu2` attribute, or an ancestor `<div id="...">` container's
    `id` value; see `_find_ancestor_with_attr`/`_find_ancestor_ids`),
    or "unknown" (could not be confidently resolved by either of the
    above — left empty rather than guessed). Round 4 removed the
    earlier "preceding_context" method (an unbounded document-order
    backward scan) after real evidence proved it could independently
    borrow menu1 and menu2 from two unrelated tags with no structural
    relationship to the leaf or each other — see
    docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 4 section."""

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

    @property
    def node_type(self) -> str:
        """REQUESTABLE_METRIC_LEAF or NAVIGATION_CONTAINER — see
        `CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES`'s docstring for
        the real evidence backing this classification, AND why it is
        scoped to `leaf_level == LEAF_LEVEL_MENU2` specifically: the
        confirmed navigation-page evidence was for a menu2-level
        ("All"/family, no menu3) request only. A menu3-level leaf is
        NEVER auto-excluded merely because its structurally-resolved
        `menu1` happens to read "All" — that shape has no confirming
        evidence, and per this project's own discipline, absence of
        evidence must not become an exclusion. Derived purely from
        `menu1` + `leaf_level`, never from `menu3` being fabricated or
        guessed, and never from labels or golf semantics."""
        if self.leaf_level == LEAF_LEVEL_MENU2 and self.menu1 in CONFIRMED_NAVIGATION_CONTAINER_MENU1_VALUES:
            return NODE_TYPE_NAVIGATION_CONTAINER
        return NODE_TYPE_REQUESTABLE_METRIC_LEAF


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
    def requestable_leaves(self) -> list[MenuLeaf]:
        """Leaves whose node_type is REQUESTABLE_METRIC_LEAF — see
        MenuLeaf.node_type. Never includes a NAVIGATION_CONTAINER leaf
        such as any menu1="All" entry."""
        return [leaf for leaf in self.leaves if leaf.node_type == NODE_TYPE_REQUESTABLE_METRIC_LEAF]

    @property
    def navigation_container_leaves(self) -> list[MenuLeaf]:
        return [leaf for leaf in self.leaves if leaf.node_type == NODE_TYPE_NAVIGATION_CONTAINER]

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


def _find_ancestor_ids(tag: Tag) -> list[str]:
    """Ordered list (nearest to farthest) of the literal `id` attribute
    value on every ANCESTOR of `tag` that carries a non-blank `id` —
    real BeautifulSoup ancestor relationships via `tag.parents`, never
    a document-order/positional guess.

    **Round 4 fix — replaces the removed `_find_nearest_preceding_attr`
    ("preceding_context") tier.** Real literal HTML evidence (Windows
    capture of the actual `locationRecord` source page, 2026-08-26; see
    docs/KLPGA_OFFICIAL_DATA_MAP.md's Round 4 section) proved
    `preceding_context`'s unbounded document-order backward scan was
    unsound: it independently resolved `menu1` and `menu2` from two
    UNRELATED tags with no structural relationship to `tag` or to each
    other, producing synthetic identities that never exist in the real
    DOM (confirmed case: a `data-menu3="010102"` button genuinely
    nested inside `<div id="Tee01">` resolved as `menu1="All"` from a
    distant top-level navigation button and `menu2="Putt08"` from an
    unrelated earlier sibling tab — neither of which is any ancestor of
    this tag at all).

    The confirmed real structure instead nests each menu level inside a
    `<div id="...">` wrapper: a family-level container (e.g.
    `<div id="Sg">`, confirmed directly) and, for families with a third
    menu level, a subgroup-level container nested inside it (e.g.
    `<div id="Tee01">`, confirmed directly, itself presumed nested
    inside a bare `<div id="Tee">` family container by direct structural
    analogy with the confirmed `Sg` shape — not yet independently
    observed for every family, which is why this is used only as a
    FALLBACK after `_find_ancestor_with_attr`, and only for whichever
    identity component is still missing; if the analogy is wrong for a
    given leaf, the missing component simply stays unresolved rather
    than being guessed, since nothing here reads `id` values further
    than their presence and nesting order).

    Nothing about the `id` VALUES themselves (their text, digit
    suffixes, or naming pattern) is inspected or matched against any
    known list — only genuine ancestor presence and nesting order."""
    ids: list[str] = []
    for ancestor in tag.parents:
        if isinstance(ancestor, Tag):
            value = ancestor.get("id")
            if value:
                ids.append(value if isinstance(value, str) else " ".join(value))
    return ids


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

        # Round 4 fix (DEFECT 1) — a `data-menu2` value the tag carries
        # ON ITSELF is authoritative and must NEVER be thrown away
        # merely because `data-menu1` happens to be absent from the
        # SAME tag. The old code required BOTH own attrs together or
        # discarded both, which is exactly what caused the proven
        # "menu2 off-by-one" bug: a real page's menu2-level sub-tab
        # (e.g. `<button data-menu2="Approach02" data-menu3="020201">`)
        # had its own correct `data-menu2` discarded, then re-derived
        # from the wrong (preceding sibling's) tag. Each missing
        # component is now resolved independently and only from a
        # genuine structural relationship — never by discarding a
        # reliable value already sitting on the tag itself.
        resolved_menu1 = own_menu1
        resolved_menu2 = own_menu2
        used_ancestor = False

        if resolved_menu1 is None:
            menu1_ancestor = _find_ancestor_with_attr(tag, _MENU1_ATTR)
            if menu1_ancestor is not None:
                resolved_menu1 = _attr(menu1_ancestor, _MENU1_ATTR) or ""
                used_ancestor = True

        if resolved_menu2 is None:
            menu2_ancestor = _find_ancestor_with_attr(tag, _MENU2_ATTR)
            if menu2_ancestor is not None:
                resolved_menu2 = _attr(menu2_ancestor, _MENU2_ATTR) or ""
                used_ancestor = True

        # Round 4 fix (DEFECT 2) — replaces the removed unbounded
        # document-order `preceding_context` scan, which independently
        # borrowed menu1/menu2 from two UNRELATED tags with no
        # structural relationship to this leaf or each other (proven
        # real case: a `data-menu3="010102"` button genuinely nested
        # inside `<div id="Tee01">` was resolved as
        # `All::Putt08::010102` — neither "All" nor "Putt08" came from
        # anything related to this tag at all). Whatever is STILL
        # missing after real ancestor data-attributes is resolved from
        # the genuine ancestor `<div id="...">` container chain instead
        # — see `_find_ancestor_ids`'s docstring for the confirmed
        # real container-nesting evidence this is grounded in. The
        # nearest ancestor id fills whichever slot is still open first
        # (menu2, being the more deeply nested level), the next
        # ancestor id further up fills menu1 if that is also still
        # open — never the other way around, and never more ids than
        # there are missing slots.
        if resolved_menu1 is None or resolved_menu2 is None:
            ancestor_ids = _find_ancestor_ids(tag)
            idx = 0
            if resolved_menu2 is None and idx < len(ancestor_ids):
                resolved_menu2 = ancestor_ids[idx]
                idx += 1
                used_ancestor = True
            if resolved_menu1 is None and idx < len(ancestor_ids):
                resolved_menu1 = ancestor_ids[idx]
                used_ancestor = True

        if resolved_menu1 is not None and resolved_menu2 is not None:
            leaves.append(
                MenuLeaf(
                    menu1=resolved_menu1,
                    menu1_label="",
                    menu2=resolved_menu2,
                    menu2_label="",
                    menu3=menu3,
                    menu3_label=menu3_label,
                    leaf_level=LEAF_LEVEL_MENU3,
                    label_resolution_method="ancestor_walk" if used_ancestor else "own_attrs",
                )
            )
            continue

        # Neither component fully resolved together — the leaf as a
        # whole is "unknown" (never safe to request: sampler.py rejects
        # any blank menu1/menu2 before a live request), but per this
        # module's "preserve every discovered thing" discipline,
        # whichever single component WAS genuinely resolved (e.g. a
        # real own `data-menu2` with no ancestor able to supply menu1)
        # is still preserved in the audit trail rather than blanked out.
        leaves.append(
            MenuLeaf(
                menu1=resolved_menu1 or "",
                menu1_label="",
                menu2=resolved_menu2 or "",
                menu2_label="",
                menu3=menu3,
                menu3_label=menu3_label,
                leaf_level=LEAF_LEVEL_MENU3,
                label_resolution_method="unknown",
            )
        )

    # --- Pass 2: menu2-level leaves ---
    for tag in all_tags:
        if not _has_value(tag, _MENU2_ATTR):
            continue
        if _has_value(tag, _MENU3_ATTR):
            continue  # already handled as a menu3-level leaf above
        if _has_menu3_descendant(tag):
            continue  # a container wrapping real menu3-level buttons, not a leaf itself

        own_menu1 = _attr(tag, _MENU1_ATTR)
        own_menu2 = _attr(tag, _MENU2_ATTR) or ""

        # Same DEFECT 1/2 fix as Pass 1, applied to menu2-level leaves —
        # real evidence (the confirmed `<div id="Sg">` family container
        # wrapping `<button data-menu2="Total">`/`data-menu2=
        # "TeeToGreen">`/`data-menu2="All">` with NO own `data-menu1` on
        # any of them) proved this level has the identical structural
        # shape as Pass 1's menu3-level tags, not just the "All"
        # navigation buttons this pass was originally written for.
        resolved_menu1 = own_menu1
        used_ancestor = False
        if resolved_menu1 is None:
            menu1_ancestor = _find_ancestor_with_attr(tag, _MENU1_ATTR)
            if menu1_ancestor is not None:
                resolved_menu1 = _attr(menu1_ancestor, _MENU1_ATTR) or ""
                used_ancestor = True
        if resolved_menu1 is None:
            ancestor_ids = _find_ancestor_ids(tag)
            if ancestor_ids:
                resolved_menu1 = ancestor_ids[0]
                used_ancestor = True

        if resolved_menu1 is None:
            # Genuinely unresolvable menu1 for this menu2-level leaf —
            # matches the prior behavior of skipping rather than
            # fabricating (Pass 2 has no "unknown" leaf slot; a
            # menu2-level leaf with no identity at all is not a useful
            # audit entry the way a menu3-level one is, since it has no
            # menu3 code to preserve either).
            continue

        leaves.append(
            MenuLeaf(
                menu1=resolved_menu1,
                menu1_label="",
                menu2=own_menu2,
                menu2_label=tag.get_text(strip=True),
                menu3=None,
                menu3_label=None,
                leaf_level=LEAF_LEVEL_MENU2,
                label_resolution_method="own_attrs" if not used_ancestor else "ancestor_walk",
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
