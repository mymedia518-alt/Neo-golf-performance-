"""Tests for klpga.discovery.taxonomy_report's Phase B1 CLASS 2
additions: node_type serialization and the requestable/navigation
count split. Uses the same real-evidence-shaped DOM as
test_menu_taxonomy.py (Sg/Total, Sg/TeeToGreen, Tee/Tee01/010101-3,
plus an All/Sg navigation entry)."""
from __future__ import annotations

import json

from klpga.discovery.menu_taxonomy import inspect_menu_dom
from klpga.discovery.taxonomy_report import compute_counts, to_taxonomy_csv, to_taxonomy_json


def _real_evidence_shaped_dom() -> str:
    return """
    <div data-menu1="All"><a data-menu1="All" data-menu2="Sg">전체기록보기</a></div>
    <div data-menu1="Sg">
      <a data-menu1="Sg" data-menu2="Total">SG : 전체</a>
      <a data-menu1="Sg" data-menu2="TeeToGreen">SG : 티투그린</a>
    </div>
    <div data-menu1="Tee" data-menu2="Tee01">
      <a data-menu1="Tee" data-menu2="Tee01" data-menu3="010101">평균 티샷 거리</a>
      <a data-menu1="Tee" data-menu2="Tee01" data-menu3="010102">280야드 이상(RTP)</a>
      <a data-menu1="Tee" data-menu2="Tee01" data-menu3="010103">260~280야드 미만(RTP)</a>
    </div>
    """


def test_compute_counts_separates_requestable_from_navigation():
    dom_result = inspect_menu_dom(_real_evidence_shaped_dom())
    counts = compute_counts(dom_result)
    # 3 menu2-level leaves total (All/Sg, Sg/Total, Sg/TeeToGreen) — 1 is navigation.
    assert counts.menu2_level_leaf_count == 3
    assert counts.requestable_menu2_leaf_count == 2
    assert counts.menu3_level_leaf_count == 3
    assert counts.requestable_menu3_leaf_count == 3  # no All::* at menu3 level in this evidence
    assert counts.navigation_container_count == 1


def test_to_taxonomy_json_includes_node_type_per_leaf():
    dom_result = inspect_menu_dom(_real_evidence_shaped_dom())
    payload = json.loads(to_taxonomy_json(dom_result, source_url="https://example.test", discovered_at="2026-08-26T00:00:00Z"))
    node_types = {leaf["menu1"] + "::" + leaf["menu2"]: leaf["node_type"] for leaf in payload["leaves"] if leaf["leaf_level"] == "menu2"}
    assert node_types["All::Sg"] == "NAVIGATION_CONTAINER"
    assert node_types["Sg::Total"] == "REQUESTABLE_METRIC_LEAF"
    assert node_types["Sg::TeeToGreen"] == "REQUESTABLE_METRIC_LEAF"


def test_to_taxonomy_json_top_level_counts_present():
    dom_result = inspect_menu_dom(_real_evidence_shaped_dom())
    payload = json.loads(to_taxonomy_json(dom_result, source_url="https://example.test", discovered_at="2026-08-26T00:00:00Z"))
    assert payload["requestable_menu2_leaf_count"] == 2
    assert payload["requestable_menu3_leaf_count"] == 3
    assert payload["navigation_container_count"] == 1


def test_to_taxonomy_csv_includes_node_type_column():
    dom_result = inspect_menu_dom(_real_evidence_shaped_dom())
    csv_text = to_taxonomy_csv(dom_result)
    header = csv_text.splitlines()[0]
    assert "node_type" in header
    assert "NAVIGATION_CONTAINER" in csv_text
    assert "REQUESTABLE_METRIC_LEAF" in csv_text
