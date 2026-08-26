"""Tests for klpga.discovery.collision_report."""
from __future__ import annotations

from pathlib import Path

from klpga.discovery.collision_report import build_collision_report, render_collision_report_markdown
from klpga.discovery.menu_taxonomy import inspect_menu_dom

FIXTURES = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_collision_fixture_produces_one_menu3_collision():
    dom_result = inspect_menu_dom(_read("record_menu_collision_sample.html"))
    report = build_collision_report(dom_result)

    assert "010102" in report.menu3_collisions
    assert len(report.menu3_collisions["010102"]) == 2
    # Both leaves are under the SAME menu1 AND the SAME menu2
    # (Tee/Tee01) — the real Round-1 finding is a same-code-different-
    # label collision, not a cross-menu1/menu2 one, so it must NOT be
    # classified into either of those more specific buckets.
    assert "010102" not in report.menu2_level_collisions
    assert "010102" not in report.menu1_level_collisions


def test_collision_fixture_reports_same_code_multiple_labels():
    dom_result = inspect_menu_dom(_read("record_menu_collision_sample.html"))
    report = build_collision_report(dom_result)

    assert len(report.code_to_labels) == 1
    assert report.code_to_labels[0].code == "010102"
    assert len(report.code_to_labels[0].labels) == 2


def test_static_tree_fixture_has_no_collisions_at_all():
    dom_result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    report = build_collision_report(dom_result)

    assert report.menu3_collisions == {}
    assert report.label_to_codes == []
    assert report.code_to_labels == []


def test_response_hash_section_not_applicable_without_phase_b_data():
    dom_result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    report = build_collision_report(dom_result)  # no response_hashes passed
    assert report.response_hash_check_performed is False
    assert report.response_hash_collisions == []


def test_response_hash_collisions_detected_when_supplied():
    dom_result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    hashes = {
        "Sg::Total::": "abc123",
        "Tee::Tee01::010101": "abc123",  # deliberately identical -> collision
        "Approach::Approach01::020104": "different",
    }
    report = build_collision_report(dom_result, response_hashes=hashes)
    assert report.response_hash_check_performed is True
    assert len(report.response_hash_collisions) == 1
    assert set(report.response_hash_collisions[0].source_metric_keys) == {"Sg::Total::", "Tee::Tee01::010101"}


def test_markdown_report_mentions_the_real_collision_and_not_applicable_hash_section():
    dom_result = inspect_menu_dom(_read("record_menu_collision_sample.html"))
    report = build_collision_report(dom_result)
    markdown = render_collision_report_markdown(report)

    assert "010102" in markdown
    assert "Not applicable" in markdown


def test_markdown_report_says_none_found_when_taxonomy_is_clean():
    dom_result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    report = build_collision_report(dom_result)
    markdown = render_collision_report_markdown(report)
    assert "None found." in markdown


# ---------------------------------------------------------------
# Category C — exact duplicate DOM entries (distinct from category B,
# where the code repeats but the label differs)
# ---------------------------------------------------------------


def test_no_exact_duplicates_in_a_clean_taxonomy():
    dom_result = inspect_menu_dom(_read("record_menu_static_tree_sample.html"))
    report = build_collision_report(dom_result)
    assert report.exact_duplicates == []


def test_true_duplicate_dom_entry_is_flagged_as_category_c_not_category_b():
    """Two leaves with the IDENTICAL (menu1, menu2, menu3, label) —
    a markup artifact — must land in exact_duplicates, NOT in
    code_to_labels (which is for same-code-different-label, category B)."""
    html = """
    <a data-menu1="Tee" data-menu2="Tee01" data-menu3="010101">평균 티샷 거리</a>
    <a data-menu1="Tee" data-menu2="Tee01" data-menu3="010101">평균 티샷 거리</a>
    """
    dom_result = inspect_menu_dom(html)
    report = build_collision_report(dom_result)

    assert len(report.exact_duplicates) == 1
    assert report.exact_duplicates[0].identity == ("Tee", "Tee01", "010101")
    assert report.exact_duplicates[0].count == 2
    # Same label both times -> NOT a category-B (code -> multiple
    # labels) collision.
    assert report.code_to_labels == []


def test_menu2_level_leaf_exact_duplicates_use_menu2_label():
    html = """
    <a data-menu1="Sg" data-menu2="Total">SG : 전체</a>
    <a data-menu1="Sg" data-menu2="Total">SG : 전체</a>
    """
    dom_result = inspect_menu_dom(html)
    report = build_collision_report(dom_result)

    assert len(report.exact_duplicates) == 1
    assert report.exact_duplicates[0].identity == ("Sg", "Total")
    assert report.exact_duplicates[0].label == "SG : 전체"
