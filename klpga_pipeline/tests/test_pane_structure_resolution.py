"""Round 6 regression tests — a Windows PowerShell full-ancestor-chain
extraction of the actual Phase A `locationRecord` source page proved
Round 4's "nearest ancestor id" rule was too broad: the real page
wraps every menu level in GENERIC, shared layout panes too
(`id="nav-scroll"`, `id="menu2"`, `id="menu3"`), and a real regenerated
taxonomy showed `menu1="nav-scroll"` and `menu1="menu3"` — those panes
being wrongly accepted as semantic identities.

The full real ancestor chain also proved something more fundamental:
`<div id="Approach">` (the family's tab-row container) and
`<div id="Approach05">` (that subgroup's own detail-button container)
are SIBLINGS under two DIFFERENT shared panes (`id="menu2"` /
`id="menu3"`) — never nested in each other. There is therefore no
ancestor path AT ALL from a menu3-only detail button to its family
identity; Round 4's two-level ancestor-id-chain assumption was simply
wrong for this shape.

The fix (menu_taxonomy.py, Round 6):
  1. `_collect_known_menu_identity_values` + `_find_ancestor_ids`'
     new filter — an ancestor `id` is only ever treated as a semantic
     menu identity if that exact string ALSO appears elsewhere in the
     document as a real `data-menu1`/`data-menu2` attribute value.
     Generic panes never do — nobody's `data-menu2` is literally
     "menu3". Purely structural, no hardcoded family/generic-id names.
  2. A `subgroup_menu1_registry`, built from Stage 1 (every menu3-level
     tag that DOES carry its own `data-menu2` — which always has a
     genuine ancestor path to its family, confirmed directly): records
     `{own_menu2: resolved_menu1}`. Stage 2 (menu3-only detail buttons,
     which have no ancestor path to their family at all) looks up this
     registry by the subgroup id it DID resolve via ancestry — reusing
     another tag's OWN resolution, never a label or menu3 number.

against tests/fixtures/record_menu_confirmed_pane_structure_sample.html,
built directly from the literal real ancestor chains pasted this
round — not a hypothesis."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.menu_taxonomy import (
    LEAF_LEVEL_MENU2,
    LEAF_LEVEL_MENU3,
    NODE_TYPE_NAVIGATION_CONTAINER,
    inspect_menu_dom,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _result():
    return inspect_menu_dom(_read("record_menu_confirmed_pane_structure_sample.html"))


def _leaves(result, menu3):
    return [leaf for leaf in result.leaves if leaf.leaf_level == LEAF_LEVEL_MENU3 and leaf.menu3 == menu3]


# ---------------------------------------------------------------
# A. Generic layout/infrastructure ids must NEVER be accepted as a
#    semantic menu1 value — the exact real bug this round fixed.
# ---------------------------------------------------------------


def test_no_leaf_anywhere_resolves_menu1_to_a_generic_pane_or_widget_id():
    result = _result()
    generic_ids = {"nav-scroll", "menu1", "menu2", "menu3"}
    offenders = [leaf for leaf in result.leaves if leaf.menu1 in generic_ids]
    assert offenders == [], f"leaves wrongly resolved to a generic id as menu1: {offenders}"


def test_no_leaf_anywhere_resolves_menu2_to_a_generic_pane_or_widget_id():
    result = _result()
    generic_ids = {"nav-scroll", "menu1", "menu2", "menu3"}
    offenders = [leaf for leaf in result.leaves if leaf.menu2 in generic_ids]
    assert offenders == [], f"leaves wrongly resolved to a generic id as menu2: {offenders}"


# ---------------------------------------------------------------
# B. Approach05's outer tab-row entry (own data-menu2, has a genuine
#    ancestor path to its family) resolves correctly.
# ---------------------------------------------------------------


def test_approach05_outer_tab_resolves_via_genuine_ancestor_not_generic_pane():
    leaves = _leaves(_result(), "020501")
    outer = next(leaf for leaf in leaves if leaf.menu3_label == "그린 적중률(러프)")
    assert outer.menu1 == "Approach"
    assert outer.menu2 == "Approach05"
    assert outer.label_resolution_method == "ancestor_walk"


def test_every_approach_outer_tab_keeps_its_own_menu2():
    result = _result()
    expected = {
        "020101": "Approach01",
        "020201": "Approach02",
        "020301": "Approach03",
        "020401": "Approach04",
        "020501": "Approach05",
    }
    for menu3, expected_menu2 in expected.items():
        leaves = [l for l in _leaves(result, menu3) if l.menu2 == expected_menu2]
        assert leaves, f"no leaf for menu3={menu3} kept its own menu2={expected_menu2!r}"
        assert all(l.menu1 == "Approach" for l in leaves)


# ---------------------------------------------------------------
# C. The inner menu3-only detail buttons — no ancestor path to their
#    family at all — resolve via the subgroup_menu1_registry
#    cross-reference, never via a generic pane id.
# ---------------------------------------------------------------


def test_approach05_detail_only_button_resolves_via_registry_not_generic_pane():
    leaves = _leaves(_result(), "020503")
    assert len(leaves) == 1
    leaf = leaves[0]
    assert leaf.menu1 == "Approach"
    assert leaf.menu2 == "Approach05"
    assert leaf.menu3_label == "180~200야드 미만"


def test_tee01_detail_only_button_resolves_to_tee_not_all_or_putt08():
    """The exact real regression case: Tee01's own detail button for
    010102 must resolve to Tee::Tee01::010102 — this is the identity
    that was wrongly synthesized as All::Putt08::010102 two rounds
    ago, and wrongly synthesized as menu1='menu3' last round."""
    leaves = _leaves(_result(), "010102")
    assert len(leaves) == 1
    leaf = leaves[0]
    assert leaf.identity == ("Tee", "Tee01", "010102")
    assert leaf.menu1 != "All"
    assert leaf.menu1 != "Putt08"
    assert leaf.menu1 != "menu3"


def test_no_leaf_anywhere_is_the_false_all_putt08_identity():
    result = _result()
    identities = {leaf.identity for leaf in result.leaves}
    assert ("All", "Putt08", "010102") not in identities


# ---------------------------------------------------------------
# D. Duplicate menu3 occurrences (the real page's confirmed shape:
#    020501 and 010101 each appear twice — once as the outer tab's own
#    code, once as the first item inside the inner detail pane) must
#    both resolve to the SAME true identity, never two different
#    (false) identities.
# ---------------------------------------------------------------


def test_duplicate_020501_occurrences_both_resolve_to_the_same_true_identity():
    leaves = _leaves(_result(), "020501")
    assert len(leaves) == 2  # outer tab-row entry + inner detail-pane entry
    identities = {leaf.identity for leaf in leaves}
    assert identities == {("Approach", "Approach05", "020501")}


def test_duplicate_010101_occurrences_both_resolve_to_the_same_true_identity():
    leaves = _leaves(_result(), "010101")
    assert len(leaves) == 2
    identities = {leaf.identity for leaf in leaves}
    assert identities == {("Tee", "Tee01", "010101")}


def test_duplicate_occurrences_are_reported_as_a_real_collision_never_silently_merged():
    """menu_taxonomy.py's own collision tracking is keyed by bare
    menu3 code (unaware of whether two same-identity leaves are exact
    duplicates or genuinely different parents) — it must still see
    both occurrences, never silently drop one."""
    result = _result()
    assert "020501" in result.collisions
    assert len(result.collisions["020501"]) == 2
    assert "010101" in result.collisions
    assert len(result.collisions["010101"]) == 2


# ---------------------------------------------------------------
# E. Other families resolve correctly too — not just Approach/Tee.
# ---------------------------------------------------------------


def test_around_and_putt_outer_tabs_resolve_via_genuine_ancestor():
    result = _result()
    around = _leaves(result, "030101")[0]
    assert around.menu1 == "Around"
    assert around.menu2 == "Around01"

    putt = _leaves(result, "040101")[0]
    assert putt.menu1 == "Putt"
    assert putt.menu2 == "Putt01"

    putt08 = _leaves(result, "080101")[0]
    assert putt08.menu1 == "Putt"
    assert putt08.menu2 == "Putt08"


# ---------------------------------------------------------------
# F. Sg's Pass 2 (menu2-level) leaves also resolve via the filtered
#    ancestor-id chain, not the generic "menu2" pane.
# ---------------------------------------------------------------


def test_sg_menu2_leaves_resolve_via_genuine_ancestor_not_generic_pane():
    result = _result()
    sg_total = next(leaf for leaf in result.leaves if leaf.menu1 == "Sg" and leaf.menu2 == "Total")
    assert sg_total.leaf_level == LEAF_LEVEL_MENU2
    assert sg_total.label_resolution_method == "ancestor_walk"


# ---------------------------------------------------------------
# G. Top-level "All" navigation buttons remain unaffected.
# ---------------------------------------------------------------


def test_topnav_all_buttons_remain_navigation_container_and_own_attrs():
    result = _result()
    all_leaves = [leaf for leaf in result.leaves if leaf.menu1 == "All"]
    assert len(all_leaves) == 5
    assert all(leaf.node_type == NODE_TYPE_NAVIGATION_CONTAINER for leaf in all_leaves)
    assert all(leaf.label_resolution_method == "own_attrs" for leaf in all_leaves)
