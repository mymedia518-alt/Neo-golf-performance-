"""Tests for klpga.discovery.menu_taxonomy — all against fixture/inline
HTML, no network access, matching this project's existing test
convention (see test_leaderboard_parser.py / test_entry_list_parser.py)."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.menu_taxonomy import build_source_metric_key, inspect_menu_dom

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_build_source_metric_key_joins_with_double_colon():
    assert build_source_metric_key("Approach", "Approach01", "020104") == "Approach::Approach01::020104"


def test_static_tree_fixture_discovers_all_real_confirmed_leaves():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))

    keys = {leaf.source_metric_key for leaf in result.leaves}
    assert "Sg::Total::" in keys
    assert "Tee::Tee01::010101" in keys
    assert "Approach::Approach01::020104" in keys
    assert "Approach::Approach01::020105" in keys
    assert len(result.leaves) == 4


def test_static_tree_fixture_preserves_korean_labels_verbatim():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    labels = {leaf.source_metric_key: leaf.menu3_label for leaf in result.leaves}
    assert labels["Tee::Tee01::010101"] == "평균 티샷 거리"
    assert labels["Approach::Approach01::020104"] == "그린 적중률 - 160~180야드 미만(RTP)"


def test_static_tree_fixture_is_reported_fully_static():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    assert result.is_fully_static is True
    assert result.incomplete_menu1_categories == []


def test_flat_pattern_uses_own_attrs_resolution_method():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    assert all(leaf.label_resolution_method == "own_attrs" for leaf in result.leaves)


def test_partial_tree_fixture_flags_putting_as_incomplete():
    result = inspect_menu_dom(_read("record_menu_partial_tree_sample.html"))

    assert result.is_fully_static is False
    incomplete_codes = {c.menu1 for c in result.incomplete_menu1_categories}
    assert incomplete_codes == {"Putting"}
    # The categories that DO have leaves must not be flagged incomplete.
    complete_codes = {c.menu1 for c in result.menu1_coverage if c.has_menu3_leaves}
    assert complete_codes == {"Sg", "Tee"}


def test_collision_fixture_reproduces_the_real_010102_finding():
    """Regression test for the exact Round-1 finding: menu3=010102
    under Tee/Tee01 mapped to two visibly different Korean labels.
    Must be preserved as TWO leaves, never deduplicated."""
    result = inspect_menu_dom(_read("record_menu_collision_sample.html"))

    assert len(result.leaves) == 2
    assert result.leaves[0].menu3 == "010102"
    assert result.leaves[1].menu3 == "010102"
    labels = {leaf.menu3_label for leaf in result.leaves}
    assert labels == {"280야드 이상(RTP)", "Par4,5 페어웨이 안착률 - 260~280야드 미만"}

    collisions = result.collisions
    assert "010102" in collisions
    assert len(collisions["010102"]) == 2


def test_no_collision_when_menu3_values_are_all_distinct():
    result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    assert result.collisions == {}


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


def test_empty_dom_yields_empty_result_not_an_error():
    result = inspect_menu_dom("<html><body>no menu here</body></html>")
    assert result.leaves == []
    assert result.menu1_count == 0
    assert result.is_fully_static is False
