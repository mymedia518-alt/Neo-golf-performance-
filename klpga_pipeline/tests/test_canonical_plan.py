"""Tests for klpga.discovery.canonical_plan — Phase B1 CLASS 2 fix.
Pure in-memory taxonomy dicts; no real KLPGA_RECORD_TAXONOMY_DISCOVERED.json
exists in this repo (see test_sampler.py's own note)."""
from __future__ import annotations

import json

from klpga.discovery.canonical_plan import build_canonical_plan, build_canonical_plan_json


def _leaf(menu1, menu2, menu3, leaf_level, label, node_type=None):
    key = f"{menu1}::{menu2}" + (f"::{menu3}" if leaf_level == "menu3" else "")
    d = {
        "menu1": menu1,
        "menu1_label": menu1,
        "menu2": menu2,
        "menu2_label": label if leaf_level == "menu2" else "",
        "menu3": menu3,
        "menu3_label": label if leaf_level == "menu3" else None,
        "leaf_level": leaf_level,
        "source_metric_key": key,
    }
    if node_type is not None:
        d["node_type"] = node_type
    return d


def _real_evidence_taxonomy() -> dict:
    """Mirrors the exact real evidence quoted across this project's
    Phase A/B1 rounds: five All::* navigation entries, the confirmed
    Sg/Tee/Approach/Around/Putt families, a genuine menu3 collision
    (two different families sharing "010102"), and an exact-duplicate
    DOM entry (the same identity+label appearing twice — a markup
    artifact)."""
    return {
        "source_url": "https://example.test/record",
        "leaves": [
            _leaf("All", "Sg", None, "menu2", "전체기록보기"),
            _leaf("All", "Tee", None, "menu2", "전체기록보기"),
            _leaf("All", "Approach", None, "menu2", "전체기록보기"),
            _leaf("All", "Around", None, "menu2", "전체기록보기"),
            _leaf("All", "Putt", None, "menu2", "전체기록보기"),
            _leaf("Sg", "Total", None, "menu2", "SG : 전체"),
            _leaf("Sg", "TeeToGreen", None, "menu2", "SG : 티투그린"),
            _leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
            _leaf("Tee", "Tee01", "010102", "menu3", "280야드 이상(RTP)"),
            # exact duplicate DOM entry — identical identity+label to the row above
            _leaf("Tee", "Tee01", "010102", "menu3", "280야드 이상(RTP)"),
            # a genuine cross-family menu3 collision on "010102"
            _leaf("Approach", "Approach02", "010102", "menu3", "다른 지표"),
            _leaf("Approach", "Approach01", "020104", "menu3", "그린 적중률"),
            _leaf("Around", "Around01", "030101", "menu3", "그린 주변 샷"),
            _leaf("Putt", "Putt01", "040101", "menu3", "1퍼트 성공률"),
            # a malformed leaf (blank identity) — never requestable
            {
                "menu1": "",
                "menu1_label": "",
                "menu2": "",
                "menu2_label": "",
                "menu3": "999999",
                "menu3_label": "고아 항목",
                "leaf_level": "menu3",
                "source_metric_key": "::999999",
            },
        ],
    }


def test_navigation_containers_excluded_from_canonical_plan():
    counts, plan = build_canonical_plan(_real_evidence_taxonomy())
    assert counts.navigation_container_count == 5
    assert all(p["menu1"] != "All" for p in plan)


def test_malformed_leaf_excluded_and_counted_separately():
    counts, _plan = build_canonical_plan(_real_evidence_taxonomy())
    assert counts.malformed_leaf_count == 1


def test_exact_duplicate_dom_entry_deduplicated_and_counted():
    counts, plan = build_canonical_plan(_real_evidence_taxonomy())
    assert counts.exact_duplicate_count == 1
    tee_010102_entries = [p for p in plan if p["menu1"] == "Tee" and p["menu3"] == "010102"]
    assert len(tee_010102_entries) == 1


def test_menu3_collision_preserved_not_silently_resolved():
    """The genuine cross-family collision (menu3="010102" under BOTH
    Tee and Approach) must survive dedup — it is not an exact
    duplicate (different menu1/menu2/label), so both canonical entries
    must remain in the plan, and the collision count must reflect it."""
    counts, plan = build_canonical_plan(_real_evidence_taxonomy())
    assert counts.menu3_collision_count == 1
    entries_010102 = [p for p in plan if p["menu3"] == "010102"]
    assert len(entries_010102) == 2
    assert {p["menu1"] for p in entries_010102} == {"Tee", "Approach"}


def test_canonical_count_matches_requestable_minus_duplicates():
    counts, plan = build_canonical_plan(_real_evidence_taxonomy())
    assert counts.canonical_requestable_metric_count == len(plan)
    assert counts.canonical_requestable_metric_count == (
        counts.requestable_menu2_leaf_count + counts.requestable_menu3_leaf_count - counts.exact_duplicate_count
    )


def test_total_dom_discovered_nodes_counts_everything_including_navigation_and_malformed():
    counts, _plan = build_canonical_plan(_real_evidence_taxonomy())
    taxonomy = _real_evidence_taxonomy()
    assert counts.total_dom_discovered_nodes == len(taxonomy["leaves"])


def test_plan_entries_match_required_schema():
    _counts, plan = build_canonical_plan(_real_evidence_taxonomy())
    required_keys = {"menu1", "menu2", "menu3", "leaf_level", "identity_key", "label", "node_type", "evidence_source"}
    for entry in plan:
        assert required_keys.issubset(entry.keys())
        assert entry["node_type"] == "REQUESTABLE_METRIC_LEAF"


def test_plan_never_fabricates_a_menu3_value():
    """menu2-level entries must keep menu3=None, never a guessed code."""
    _counts, plan = build_canonical_plan(_real_evidence_taxonomy())
    menu2_entries = [p for p in plan if p["leaf_level"] == "menu2"]
    assert menu2_entries
    assert all(p["menu3"] is None for p in menu2_entries)


def test_node_type_fallback_when_taxonomy_predates_the_field():
    """An older taxonomy JSON with no node_type key at all must still
    classify "All" as NAVIGATION_CONTAINER via the confirmed-menu1
    fallback, matching sampler.py's own fallback behavior."""
    taxonomy = {
        "leaves": [
            {"menu1": "All", "menu2": "Sg", "menu3": None, "leaf_level": "menu2", "menu2_label": "전체", "source_metric_key": "All::Sg"},
            {"menu1": "Sg", "menu2": "Total", "menu3": None, "leaf_level": "menu2", "menu2_label": "SG : 전체", "source_metric_key": "Sg::Total"},
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.navigation_container_count == 1
    assert len(plan) == 1
    assert plan[0]["menu1"] == "Sg"


def test_explicit_node_type_is_respected_over_menu1_heuristic():
    """If a taxonomy explicitly tags a leaf's node_type, that is
    authoritative — even for a menu1 value that happens to be "All"
    (e.g. a hypothetical future distinction within the All family)."""
    taxonomy = {
        "leaves": [
            _leaf("All", "SomethingReal", None, "menu2", "실제 지표", node_type="REQUESTABLE_METRIC_LEAF"),
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.navigation_container_count == 0
    assert len(plan) == 1


def test_build_canonical_plan_json_is_valid_json_with_counts_and_plan():
    payload = json.loads(
        build_canonical_plan_json(_real_evidence_taxonomy(), generated_at="2026-08-26T00:00:00Z", source_taxonomy="test")
    )
    assert payload["counts"]["navigation_container_count"] == 5
    assert isinstance(payload["canonical_requestable_metrics"], list)
    assert len(payload["canonical_requestable_metrics"]) == payload["counts"]["canonical_requestable_metric_count"]
