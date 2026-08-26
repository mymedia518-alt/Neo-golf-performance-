"""Mission 8 regression tests for the "272 malformed leaves"
investigation (Phase B1, follow-up round). Real evidence:
KLPGA_MALFORMED_LEAF_REPORT.csv from a live Windows run reported 272
real menu3-level DOM nodes with CORRECT menu3 codes/labels but BLANK
menu1/menu2 — ancestor-walk alone could not resolve them. This tests
the new `_find_nearest_preceding_attr`-based "preceding_context"
resolution tier against
tests/fixtures/record_menu_preceding_context_sample.html, a fixture
built from those real code/label pairs plus a sibling-header DOM shape
(not simplified ancestor nesting) per explicit instruction."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.menu_taxonomy import LEAF_LEVEL_MENU3, NODE_TYPE_NAVIGATION_CONTAINER, inspect_menu_dom

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _result():
    return inspect_menu_dom(_read("record_menu_preceding_context_sample.html"))


def _leaf(result, menu3):
    return next(leaf for leaf in result.leaves if leaf.leaf_level == LEAF_LEVEL_MENU3 and leaf.menu3 == menu3)


# ---------------------------------------------------------------
# 1. menu3 sibling/section relationship resolves correctly
# ---------------------------------------------------------------


def test_menu3_sibling_header_relationship_resolves_via_preceding_context():
    """010101 ("Par4,5 티샷 비율" — a real reported malformed-report
    row) sits under a PRECEDING SIBLING header carrying data-menu1=
    "Tee"/data-menu2="Tee01", not an ancestor. Ancestor-walk alone
    would fail this; preceding_context must succeed."""
    leaf = _leaf(_result(), "010101")
    assert leaf.menu1 == "Tee"
    assert leaf.menu2 == "Tee01"
    assert leaf.menu3_label == "Par4,5 티샷 비율"
    assert leaf.label_resolution_method == "preceding_context"


def test_second_tee_leaf_under_the_same_sibling_header_also_resolves():
    """010109 ("Par4,5 페어웨이 안착률") — the second real reported
    row under the same Tee01 header — must resolve identically."""
    leaf = _leaf(_result(), "010109")
    assert leaf.menu1 == "Tee"
    assert leaf.menu2 == "Tee01"
    assert leaf.menu3_label == "Par4,5 페어웨이 안착률"


# ---------------------------------------------------------------
# 2. transitions between menu2 groups do not leak the previous group
# ---------------------------------------------------------------


def test_menu2_group_transition_does_not_leak_previous_group():
    """010201 ("Par5 티샷 비율") sits under a NEW Tee02 sibling
    header, appearing AFTER the Tee01 group — it must pick up Tee02,
    never the stale Tee01 from the earlier group."""
    leaf = _leaf(_result(), "010201")
    assert leaf.menu1 == "Tee"
    assert leaf.menu2 == "Tee02"  # NOT "Tee01" — no leak
    assert leaf.menu3_label == "Par5 티샷 비율"


def test_approach_menu2_group_transition_also_does_not_leak():
    """020301 ("그린 적중률(페어웨이)") sits under Approach02, after
    Approach01's group — must not leak Approach01."""
    leaf = _leaf(_result(), "020301")
    assert leaf.menu2 == "Approach02"  # NOT "Approach01"


# ---------------------------------------------------------------
# 3. transitions between menu1 families do not leak ancestry
# ---------------------------------------------------------------


def test_menu1_family_transition_does_not_leak_ancestry():
    """020101 ("그린 적중률") sits under the Approach family, which
    appears AFTER the entire Tee family in document order — it must
    resolve menu1="Approach", never a stale "Tee"."""
    leaf = _leaf(_result(), "020101")
    assert leaf.menu1 == "Approach"  # NOT "Tee" — no leak
    assert leaf.menu2 == "Approach01"
    assert leaf.menu3_label == "그린 적중률"


def test_around_and_putt_families_do_not_leak_from_approach():
    around_leaf = _leaf(_result(), "030101")
    assert around_leaf.menu1 == "Around"
    assert around_leaf.menu2 == "Around01"

    putt_leaf = _leaf(_result(), "040101")
    assert putt_leaf.menu1 == "Putt"
    assert putt_leaf.menu2 == "Putt01"


# ---------------------------------------------------------------
# 4. Sg menu2 leaves remain intact (own_attrs, unregressed)
# ---------------------------------------------------------------


def test_sg_menu2_leaves_remain_intact_and_unaffected_by_the_new_resolution_tier():
    result = _result()
    sg_total = next(leaf for leaf in result.leaves if leaf.menu1 == "Sg" and leaf.menu2 == "Total")
    sg_ttg = next(leaf for leaf in result.leaves if leaf.menu1 == "Sg" and leaf.menu2 == "TeeToGreen")
    assert sg_total.label_resolution_method == "own_attrs"
    assert sg_ttg.label_resolution_method == "own_attrs"
    assert sg_total.leaf_level != LEAF_LEVEL_MENU3  # still a menu2-level leaf, untouched by Pass 1's change


# ---------------------------------------------------------------
# 5. All navigation nodes remain excluded
# ---------------------------------------------------------------


def test_all_navigation_leaf_still_classified_correctly():
    result = _result()
    all_leaf = next(leaf for leaf in result.leaves if leaf.menu1 == "All")
    assert all_leaf.node_type == NODE_TYPE_NAVIGATION_CONTAINER


def test_requestable_leaves_property_excludes_the_all_entry_in_this_fixture():
    result = _result()
    assert all(leaf.menu1 != "All" for leaf in result.requestable_leaves)


# ---------------------------------------------------------------
# 6. duplicate menu3 codes under different parents remain distinct
#    (canonical identity is never collapsed to menu3 alone)
# ---------------------------------------------------------------


def test_same_menu3_code_under_different_parents_stays_distinct_not_deduplicated():
    """Not literally present in this fixture's real evidence (which
    has no reused code), so this constructs a targeted case using two
    of the SAME real preceding-header pattern with the SAME menu3 code
    reused under different menu1/menu2 — must remain two distinct
    MenuLeaf entries with two distinct identities, exactly like the
    real Round-1 010102 collision finding."""
    html = """
    <div data-menu1="Tee">티샷</div>
    <div data-menu2="Tee01">그룹A</div>
    <ul><li><a data-menu3="010102">280야드 이상(RTP)</a></li></ul>
    <div data-menu1="Approach">어프로치</div>
    <div data-menu2="Approach02">그룹B</div>
    <ul><li><a data-menu3="010102">다른 지표</a></li></ul>
    """
    result = inspect_menu_dom(html)
    leaves_010102 = [leaf for leaf in result.leaves if leaf.menu3 == "010102"]
    assert len(leaves_010102) == 2
    identities = {leaf.identity for leaf in leaves_010102}
    assert identities == {("Tee", "Tee01", "010102"), ("Approach", "Approach02", "010102")}
    assert "010102" in result.collisions  # preserved, never silently resolved


# ---------------------------------------------------------------
# 7. malformed leaves remain malformed when DOM evidence truly
#    provides no parent context at all
# ---------------------------------------------------------------


def test_leaf_with_no_preceding_context_anywhere_stays_unknown():
    """The orphaned data-menu3 tag placed before ANY menu1/menu2
    context exists anywhere in the document — genuinely nothing to
    resolve from, must stay unknown, never fabricated."""
    leaf = _leaf(_result(), "999999")
    assert leaf.menu1 == ""
    assert leaf.menu2 == ""
    assert leaf.label_resolution_method == "unknown"


def test_standalone_document_still_falls_through_to_unknown():
    """Regression guard: a single-tag document (the ORIGINAL Round-1
    test case) must still resolve to unknown — the new preceding-
    context search must not accidentally invent a match from nothing."""
    result = inspect_menu_dom('<a data-menu3="888888">완전히 고립됨</a>')
    assert len(result.leaves) == 1
    assert result.leaves[0].label_resolution_method == "unknown"
    assert result.leaves[0].menu1 == ""
    assert result.leaves[0].menu2 == ""


# ---------------------------------------------------------------
# Overall malformed-ratio sanity check on this fixture
# ---------------------------------------------------------------


def test_malformed_ratio_collapses_dramatically_on_this_fixture():
    """Structural validation target, per explicit instruction — NOT a
    hardcoded expected metric count. This fixture has 1 genuinely
    unresolvable leaf out of 12 total; the ratio must be small, not
    anywhere near the real run's reported 96%."""
    result = _result()
    total = len(result.leaves)
    malformed = sum(1 for leaf in result.leaves if not leaf.menu1 or not leaf.menu2)
    assert total > 0
    assert malformed / total < 0.20
