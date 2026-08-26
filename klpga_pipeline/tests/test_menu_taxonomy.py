"""Tests for klpga.discovery.menu_taxonomy — all against fixture/inline
HTML, no network access, matching this project's existing test
convention (see test_leaderboard_parser.py / test_entry_list_parser.py).

Round 3 patch coverage: metric leaves can terminate at menu2, not only
menu3 — see menu_taxonomy.py's module docstring for the directly
confirmed SG evidence this patch is built from."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.menu_taxonomy import (
    LEAF_LEVEL_MENU2,
    LEAF_LEVEL_MENU3,
    build_source_metric_key,
    inspect_menu_dom,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_build_source_metric_key_joins_with_double_colon():
    assert build_source_metric_key("Approach", "Approach01", "020104") == "Approach::Approach01::020104"


def test_build_source_metric_key_omits_trailing_segment_when_menu3_is_none():
    assert build_source_metric_key("Sg", "Total", None) == "Sg::Total"


# ---------------------------------------------------------------
# TEST 1 — Sg/Total with no menu3 at all is a valid menu2-level leaf
# ---------------------------------------------------------------


def test_sg_total_with_absent_menu3_attribute_is_a_menu2_level_leaf():
    result = inspect_menu_dom(_read("record_menu_sg_menu2_leaf_sample.html"))

    sg_total = next(leaf for leaf in result.leaves if leaf.menu2 == "Total")
    assert sg_total.menu1 == "Sg"
    assert sg_total.leaf_level == LEAF_LEVEL_MENU2
    assert sg_total.menu3 is None
    assert sg_total.menu3_label is None
    assert sg_total.menu2_label == "SG : 전체"
    assert sg_total.identity == ("Sg", "Total")
    assert sg_total.source_metric_key == "Sg::Total"


def test_sg_category_resolves_via_multiple_menu2_level_leaves():
    result = inspect_menu_dom(_read("record_menu_sg_menu2_leaf_sample.html"))
    sg_coverage = next(c for c in result.menu1_coverage if c.menu1 == "Sg")
    assert sg_coverage.menu2_leaf_count == 2
    assert sg_coverage.menu3_leaf_count == 0
    assert sg_coverage.has_resolved_leaves is True


def test_blank_menu3_attribute_also_resolves_as_menu2_level_leaf():
    """The static-tree fixture's Sg/Total uses data-menu3="" (present
    but blank) rather than the attribute being fully absent — both
    forms must resolve identically."""
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    sg_total = next(leaf for leaf in result.leaves if leaf.menu1 == "Sg")
    assert sg_total.leaf_level == LEAF_LEVEL_MENU2
    assert sg_total.menu3 is None


# ---------------------------------------------------------------
# TEST 2 / 3 — Approach 020104/020105 remain distinct menu3-level leaves
# ---------------------------------------------------------------


def test_static_tree_fixture_discovers_all_real_confirmed_leaves():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))

    keys = {leaf.source_metric_key for leaf in result.leaves}
    assert "Sg::Total" in keys  # menu2-level — no trailing "::" segment
    assert "Tee::Tee01::010101" in keys
    assert "Approach::Approach01::020104" in keys
    assert "Approach::Approach01::020105" in keys
    assert len(result.leaves) == 4


def test_approach_leaves_remain_menu3_level_and_distinct():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    approach_leaves = [leaf for leaf in result.leaves if leaf.menu1 == "Approach"]
    assert len(approach_leaves) == 2
    assert all(leaf.leaf_level == LEAF_LEVEL_MENU3 for leaf in approach_leaves)
    codes = {leaf.menu3 for leaf in approach_leaves}
    assert codes == {"020104", "020105"}


def test_static_tree_fixture_preserves_korean_labels_verbatim():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    labels = {leaf.source_metric_key: leaf.menu3_label for leaf in result.leaves if leaf.leaf_level == LEAF_LEVEL_MENU3}
    assert labels["Tee::Tee01::010101"] == "평균 티샷 거리"
    assert labels["Approach::Approach01::020104"] == "그린 적중률 - 160~180야드 미만(RTP)"


def test_static_tree_fixture_is_reported_fully_static():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    assert result.is_fully_static is True
    assert result.incomplete_menu1_categories == []


def test_flat_pattern_uses_own_attrs_resolution_method():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    assert all(leaf.label_resolution_method == "own_attrs" for leaf in result.leaves)


# ---------------------------------------------------------------
# TEST 4 — a category with only menu2-level leaves is NOT "incomplete"
# ---------------------------------------------------------------


def test_category_with_only_menu2_level_leaves_is_not_incomplete():
    result = inspect_menu_dom(_read("record_menu_sg_menu2_leaf_sample.html"))
    assert result.incomplete_menu1_categories == []
    assert result.is_fully_static is True


def test_partial_tree_fixture_flags_putting_as_incomplete():
    result = inspect_menu_dom(_read("record_menu_partial_tree_sample.html"))

    assert result.is_fully_static is False
    incomplete_codes = {c.menu1 for c in result.incomplete_menu1_categories}
    assert incomplete_codes == {"Putting"}
    # "Sg" resolves via a menu2-level leaf (blank menu3), NOT a menu3
    # leaf — it must still count as resolved, not incomplete.
    complete_codes = {c.menu1 for c in result.menu1_coverage if c.has_resolved_leaves}
    assert complete_codes == {"Sg", "Tee"}
    sg_coverage = next(c for c in result.menu1_coverage if c.menu1 == "Sg")
    assert sg_coverage.menu2_leaf_count == 1
    assert sg_coverage.menu3_leaf_count == 0


# ---------------------------------------------------------------
# TEST 5 — menu3 collisions are still detected
# ---------------------------------------------------------------


def test_collision_fixture_reproduces_the_real_010102_finding():
    """Regression test for the exact Round-1 finding: menu3=010102
    under Tee/Tee01 mapped to two visibly different Korean labels.
    Must be preserved as TWO leaves, never deduplicated."""
    result = inspect_menu_dom(_read("record_menu_collision_sample.html"))

    assert len(result.leaves) == 2
    assert result.leaves[0].menu3 == "010102"
    assert result.leaves[1].menu3 == "010102"
    assert all(leaf.leaf_level == LEAF_LEVEL_MENU3 for leaf in result.leaves)
    labels = {leaf.menu3_label for leaf in result.leaves}
    assert labels == {"280야드 이상(RTP)", "Par4,5 페어웨이 안착률 - 260~280야드 미만"}

    collisions = result.collisions
    assert "010102" in collisions
    assert len(collisions["010102"]) == 2


def test_no_collision_when_menu3_values_are_all_distinct():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    assert result.collisions == {}


def test_menu2_level_leaves_never_participate_in_menu3_collisions():
    """A menu2-level leaf has no menu3 at all — it must never appear
    in the collisions dict, and two menu2-level leaves sharing a menu1
    (like the two Sg leaves) must not be misreported as a menu3
    collision."""
    result = inspect_menu_dom(_read("record_menu_sg_menu2_leaf_sample.html"))
    assert result.collisions == {}


# ---------------------------------------------------------------
# TEST 6 — canonical identity does not rely on menu3 alone
# ---------------------------------------------------------------


def test_menu3_level_identity_is_the_full_triple():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    leaf = next(leaf for leaf in result.leaves if leaf.menu3 == "020104")
    assert leaf.identity == ("Approach", "Approach01", "020104")


def test_menu2_level_identity_is_the_pair_not_menu3_alone():
    result = inspect_menu_dom(_read("record_menu_sg_menu2_leaf_sample.html"))
    leaf = next(leaf for leaf in result.leaves if leaf.menu2 == "Total")
    assert leaf.identity == ("Sg", "Total")


def test_identity_distinguishes_leaves_that_would_collide_on_menu3_alone():
    """Two menu3-level leaves under DIFFERENT (menu1, menu2) pairs that
    happen to share the same bare menu3 code must have DIFFERENT
    identities — proving identity never relies on menu3 alone. (The
    real 010102 finding is the opposite case — same menu1/menu2,
    different label — covered separately by the code_to_labels
    collision check, since `identity` intentionally excludes the
    label.)"""
    html = """
    <a data-menu1="Tee" data-menu2="Tee01" data-menu3="999">A</a>
    <a data-menu1="Approach" data-menu2="Approach01" data-menu3="999">B</a>
    """
    result = inspect_menu_dom(html)
    identities = {leaf.identity for leaf in result.leaves}
    assert len(identities) == 2  # would be 1 if identity were menu3-only

    # Sanity check: identity does NOT disambiguate the real 010102 case
    # (same menu1/menu2, different label) — that's what code_to_labels
    # is for, not identity.
    real_case = inspect_menu_dom(_read("record_menu_collision_sample.html"))
    real_identities = {leaf.identity for leaf in real_case.leaves}
    assert len(real_identities) == 1


# ---------------------------------------------------------------
# Pre-existing coverage (ancestor-walk, unresolved, empty DOM)
# ---------------------------------------------------------------


def test_ancestor_walk_resolution_when_menu1_menu2_are_on_a_parent():
    html = """
    <div data-menu1="Approach">
      <div data-menu2="Approach01">
        <a data-menu3="020104">그린 적중률 - 160~180야드 미만(RTP)</a>
      </div>
    </div>
    """
    result = inspect_menu_dom(html)
    assert len(result.leaves) == 1
    leaf = result.leaves[0]
    assert leaf.menu1 == "Approach"
    assert leaf.menu2 == "Approach01"
    assert leaf.menu3 == "020104"
    assert leaf.leaf_level == LEAF_LEVEL_MENU3
    assert leaf.label_resolution_method == "ancestor_walk"


def test_unresolvable_menu3_is_preserved_not_dropped():
    """A data-menu3 element with no discoverable menu1/menu2 anywhere
    (own attrs or ancestors) must still show up in the result, flagged
    unknown — never silently dropped."""
    html = '<a data-menu3="999999">고아 항목</a>'
    result = inspect_menu_dom(html)
    assert len(result.leaves) == 1
    assert result.leaves[0].label_resolution_method == "unknown"
    assert result.leaves[0].menu1 == ""


def test_menu3_container_with_no_own_menu3_is_not_a_spurious_menu2_leaf():
    """A wrapper element carrying data-menu1/data-menu2 that CONTAINS
    real menu3-level buttons must not itself be double-counted as an
    extra menu2-level leaf."""
    html = """
    <div data-menu1="Approach" data-menu2="Approach01">
      <a data-menu1="Approach" data-menu2="Approach01" data-menu3="020104">그린 적중률 - 160~180야드 미만(RTP)</a>
    </div>
    """
    result = inspect_menu_dom(html)
    assert len(result.leaves) == 1
    assert result.leaves[0].leaf_level == LEAF_LEVEL_MENU3


def test_empty_dom_yields_empty_result_not_an_error():
    result = inspect_menu_dom("<html><body>no menu here</body></html>")
    assert result.leaves == []
    assert result.menu1_count == 0
    assert result.is_fully_static is False
