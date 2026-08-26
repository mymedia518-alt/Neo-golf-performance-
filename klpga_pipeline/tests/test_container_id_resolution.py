"""Round 4 regression tests — the real literal Phase A source-page HTML
(Windows PowerShell extraction, 2026-08-26) proved TWO defects in the
old resolver, both against
tests/fixtures/record_menu_confirmed_container_structure_sample.html
(built from that literal evidence, not a hypothesis):

DEFECT 1: a tag's own, reliable `data-menu2` (and `data-menu3`) was
discarded entirely whenever `data-menu1` happened to be absent from
the SAME tag, because the old own_attrs check required both together.
Real example: `<button data-menu2="Approach02" data-menu3="020201">`
had its own correct "Approach02" thrown away and re-derived from the
PREVIOUS sibling tab's own data-menu2 ("Approach01") — a proven
"menu2 off-by-one" bug across the whole Approach group.

DEFECT 2: whatever was still missing was resolved via
`_find_nearest_preceding_attr`, an UNBOUNDED document-order backward
scan with no structural relationship requirement at all. Real example:
a `data-menu3="010102"` button genuinely nested inside
`<div id="Tee01">` resolved as `All::Putt08::010102` — "All" borrowed
from a distant, unrelated top-nav button and "Putt08" from an
unrelated earlier tab, neither of which is any ancestor of the tag.

The fix (menu_taxonomy.py, Round 4): preserve whichever own attribute
IS present; resolve ONLY the missing component(s), and ONLY from a
genuine ancestor relationship — first an ancestor's own
`data-menu1`/`data-menu2` attribute (existing `_find_ancestor_with_attr`,
unchanged), then a genuine ancestor `<div id="...">` container id chain
(new `_find_ancestor_ids`) — confirmed by the real `id="Sg"` /
`id="Tee01"` container-nesting evidence. `preceding_context` (the
unbounded scan) has been removed entirely, from both Pass 1 (menu3-
level leaves) and Pass 2 (menu2-level leaves, which the real `id="Sg"`
evidence proved has the identical structural shape)."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.menu_taxonomy import (
    LEAF_LEVEL_MENU2,
    LEAF_LEVEL_MENU3,
    NODE_TYPE_NAVIGATION_CONTAINER,
    NODE_TYPE_REQUESTABLE_METRIC_LEAF,
    inspect_menu_dom,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _result():
    return inspect_menu_dom(_read("record_menu_confirmed_container_structure_sample.html"))


def _leaf(result, menu3):
    return next(leaf for leaf in result.leaves if leaf.leaf_level == LEAF_LEVEL_MENU3 and leaf.menu3 == menu3)


# ---------------------------------------------------------------
# A. Outer tab: own data-menu2 + data-menu3, missing data-menu1 —
#    own menu2 must be PRESERVED, never replaced via a sibling.
# ---------------------------------------------------------------


def test_approach02_tab_retains_its_own_menu2_not_the_previous_siblings():
    """The proven real bug: Approach02's own tab must resolve as
    menu2="Approach02", never "Approach01" (the off-by-one)."""
    leaf = _leaf(_result(), "020201")
    assert leaf.menu2 == "Approach02"
    assert leaf.menu1 == "Approach"
    assert leaf.menu3_label == "그린 적중 시 남은 거리"


def test_every_approach_tab_retains_its_own_menu2_no_off_by_one_anywhere():
    """Extends coverage across the whole group — Approach03/04/05 must
    each keep their OWN code too, not their predecessor's."""
    result = _result()
    expected = {
        "020101": "Approach01",
        "020201": "Approach02",
        "020301": "Approach03",
        "020401": "Approach04",
        "020501": "Approach05",
    }
    for menu3, expected_menu2 in expected.items():
        leaf = _leaf(result, menu3)
        assert leaf.menu2 == expected_menu2, f"{menu3}: expected menu2={expected_menu2!r}, got {leaf.menu2!r}"
        assert leaf.menu1 == "Approach"


def test_approach_tab_resolution_method_is_ancestor_walk_not_own_attrs():
    """Own menu2 was preserved, but menu1 still had to come from a
    genuine ancestor — this must be visible in the audit trail."""
    leaf = _leaf(_result(), "020201")
    assert leaf.label_resolution_method == "ancestor_walk"


# ---------------------------------------------------------------
# B. Inner menu3-only button inside <div id="Tee01">, with unrelated
#    All/Putt08 attributes present elsewhere in the document.
# ---------------------------------------------------------------


def test_tee01_detail_button_resolves_via_its_real_container_not_unrelated_tags():
    leaf = _leaf(_result(), "010102")
    assert leaf.menu1 == "Tee"
    assert leaf.menu2 == "Tee01"
    assert leaf.menu3_label == "280야드 이상(RTP)"


def test_tee01_first_detail_item_also_resolves_correctly():
    leaf = _leaf(_result(), "010101")
    assert leaf.menu1 == "Tee"
    assert leaf.menu2 == "Tee01"


# ---------------------------------------------------------------
# C. The resolver can NEVER produce the false All::Putt08::010102
#    tuple from this exact structure — explicit, direct assertion.
# ---------------------------------------------------------------


def test_resolver_never_produces_the_false_all_putt08_identity():
    result = _result()
    identities = {leaf.identity for leaf in result.leaves}
    assert ("All", "Putt08", "010102") not in identities
    assert ("Tee", "Tee01", "010102") in identities


def test_no_leaf_anywhere_in_the_fixture_borrows_menu1_all_from_the_topnav():
    """Only the genuine top-level navigation buttons (own_attrs,
    menu1="All" directly on themselves) may ever carry menu1="All" —
    no menu3-level leaf resolved via ancestor may inherit it, since
    "All" is never a genuine ancestor id or ancestor data-menu1 value
    for any menu3-bearing tag in this fixture."""
    result = _result()
    menu3_leaves_with_all = [leaf for leaf in result.menu3_level_leaves if leaf.menu1 == "All"]
    assert menu3_leaves_with_all == []


# ---------------------------------------------------------------
# D. Family-level container id correctly supplies menu1 across every
#    family, not just Approach/Tee.
# ---------------------------------------------------------------


def test_around_and_putt_tabs_resolve_menu1_from_their_own_family_container():
    result = _result()
    around_leaf = _leaf(result, "030101")
    assert around_leaf.menu1 == "Around"
    assert around_leaf.menu2 == "Around01"

    putt_leaf = _leaf(result, "040101")
    assert putt_leaf.menu1 == "Putt"
    assert putt_leaf.menu2 == "Putt01"


def test_putt08_own_tab_resolves_to_its_own_real_identity():
    """The tab that the OLD buggy resolver wrongly lent to the Tee01
    button must still resolve correctly for ITSELF."""
    leaf = _leaf(_result(), "080101")
    assert leaf.menu1 == "Putt"
    assert leaf.menu2 == "Putt08"


# ---------------------------------------------------------------
# E. Two-level ancestor id chain: a menu3-only button nested inside a
#    subgroup detail div (itself nested inside the family div) must
#    resolve BOTH menu1 and menu2 from that real nesting.
# ---------------------------------------------------------------


def test_approach02_detail_button_resolves_via_two_level_ancestor_chain():
    leaf = _leaf(_result(), "020203")
    assert leaf.menu1 == "Approach"
    assert leaf.menu2 == "Approach02"
    assert leaf.menu3_label == "180~200야드 미만"


def test_approach02_detail_button_resolution_method_is_ancestor_walk():
    leaf = _leaf(_result(), "020203")
    assert leaf.label_resolution_method == "ancestor_walk"


# ---------------------------------------------------------------
# F. Sg's own menu2-level leaves — Pass 2 needed the identical fix for
#    the identical reason (real evidence: `<div id="Sg">` wrapping
#    `data-menu2`-only sub-tabs with no own data-menu1).
# ---------------------------------------------------------------


def test_sg_menu2_leaves_now_resolve_via_the_family_container_id():
    result = _result()
    sg_total = next(leaf for leaf in result.leaves if leaf.menu1 == "Sg" and leaf.menu2 == "Total")
    sg_ttg = next(leaf for leaf in result.leaves if leaf.menu1 == "Sg" and leaf.menu2 == "TeeToGreen")
    assert sg_total.leaf_level == LEAF_LEVEL_MENU2
    assert sg_total.label_resolution_method == "ancestor_walk"
    assert sg_ttg.label_resolution_method == "ancestor_walk"
    assert sg_total.node_type == NODE_TYPE_REQUESTABLE_METRIC_LEAF


# ---------------------------------------------------------------
# G. All navigation exclusion preserved — the real top-level
#    data-menu1="All" data-menu2="<Family>" buttons remain own_attrs
#    and remain classified NAVIGATION_CONTAINER, unaffected by any of
#    the above.
# ---------------------------------------------------------------


def test_topnav_all_family_buttons_remain_navigation_container():
    result = _result()
    all_leaves = [leaf for leaf in result.leaves if leaf.menu1 == "All"]
    assert len(all_leaves) == 5  # Sg, Tee, Approach, Around, Putt
    assert all(leaf.node_type == NODE_TYPE_NAVIGATION_CONTAINER for leaf in all_leaves)
    assert all(leaf.label_resolution_method == "own_attrs" for leaf in all_leaves)
    assert all(leaf.leaf_level == LEAF_LEVEL_MENU2 for leaf in all_leaves)


def test_requestable_leaves_excludes_all_five_navigation_buttons_only():
    result = _result()
    assert all(leaf.menu1 != "All" for leaf in result.requestable_leaves)
    assert len(result.leaves) - len(result.requestable_leaves) == 5


# ---------------------------------------------------------------
# H. Genuinely unresolvable leaves still fall back to "unknown" safely
#    rather than fabricating a partial/wrong identity — the
#    safe-by-construction property the new mechanism relies on.
# ---------------------------------------------------------------


def test_leaf_with_no_ancestor_id_or_ancestor_attr_anywhere_stays_unknown():
    html = '<button data-menu3="999999">완전히 고립됨</button>'
    result = inspect_menu_dom(html)
    assert len(result.leaves) == 1
    assert result.leaves[0].label_resolution_method == "unknown"
    assert result.leaves[0].menu1 == ""
    assert result.leaves[0].menu2 == ""


def test_own_menu2_preserved_in_the_audit_trail_even_when_menu1_cant_resolve():
    """A tag with own menu2+menu3 but no own menu1 AND no ancestor of
    any kind (data-attr or id) for menu1 must be classified "unknown"
    as a WHOLE leaf (never safe to request — sampler.py rejects any
    blank menu1/menu2), but the genuinely-known own menu2 value is
    still preserved rather than blanked out, per this module's
    "preserve every discovered thing" discipline."""
    html = '<button data-menu2="Orphan01" data-menu3="999999">고립된 그룹</button>'
    result = inspect_menu_dom(html)
    assert len(result.leaves) == 1
    assert result.leaves[0].label_resolution_method == "unknown"
    assert result.leaves[0].menu1 == ""
    assert result.leaves[0].menu2 == "Orphan01"
