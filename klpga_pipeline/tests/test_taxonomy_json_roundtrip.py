"""Mission 3 round-trip regression tests — DOM -> MenuLeaf ->
taxonomy JSON serialization -> deserialization -> canonical-plan /
sampler classification. Proves the serializer (taxonomy_report.py)
and the two readers (canonical_plan.py, sampler.py) agree on field
names end-to-end, for both menu2-level and menu3-level identity.

This is the direct code-level check for Mission 1's question ("does
the serializer match what the readers expect?") — run against this
project's OWN current pipeline, not the user's real (older-schema)
taxonomy file, which this session does not have access to."""
from __future__ import annotations

import json

from klpga.discovery.canonical_plan import build_canonical_plan
from klpga.discovery.menu_taxonomy import inspect_menu_dom
from klpga.discovery.sampler import reject_malformed_leaves, reject_navigation_container_leaves, select_representative_sample
from klpga.discovery.taxonomy_report import to_taxonomy_json


def _real_evidence_shaped_dom() -> str:
    """Same evidence-grounded DOM used elsewhere in this project's
    test suite: an All/Sg navigation entry, two real Sg menu2-level
    leaves, and three real Tee menu3-level leaves."""
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


def _serialize_and_reload() -> dict:
    dom_result = inspect_menu_dom(_real_evidence_shaped_dom())
    json_text = to_taxonomy_json(dom_result, source_url="https://example.test", discovered_at="2026-08-26T00:00:00Z")
    return json.loads(json_text)


def test_roundtrip_menu2_level_identity_survives_unchanged():
    taxonomy = _serialize_and_reload()
    sg_total = next(leaf for leaf in taxonomy["leaves"] if leaf["menu1"] == "Sg" and leaf["menu2"] == "Total")
    assert sg_total["leaf_level"] == "menu2"
    assert sg_total["menu3"] is None
    assert sg_total["menu1"] == "Sg"
    assert sg_total["menu2"] == "Total"


def test_roundtrip_menu3_level_identity_survives_unchanged():
    taxonomy = _serialize_and_reload()
    tee_leaf = next(leaf for leaf in taxonomy["leaves"] if leaf["menu1"] == "Tee" and leaf["menu3"] == "010101")
    assert tee_leaf["leaf_level"] == "menu3"
    assert tee_leaf["menu1"] == "Tee"
    assert tee_leaf["menu2"] == "Tee01"
    assert tee_leaf["menu3"] == "010101"


def test_roundtrip_no_malformed_leaves_from_this_project_own_serializer():
    """The serializer/deserializer pair, run against this project's
    OWN current schema, must never itself introduce a malformed
    (blank-identity) leaf — any malformed leaf must come from genuine
    unresolvable DOM evidence, never from a field-name mismatch."""
    taxonomy = _serialize_and_reload()
    valid, rejected = reject_malformed_leaves(taxonomy["leaves"])
    assert rejected == []
    assert len(valid) == len(taxonomy["leaves"])


def test_roundtrip_navigation_container_still_recognized_after_serialization():
    """node_type must survive the JSON round-trip so the reader never
    has to fall back to the bare-menu1 heuristic for a taxonomy this
    project's own current script 26 produced."""
    taxonomy = _serialize_and_reload()
    all_leaf = next(leaf for leaf in taxonomy["leaves"] if leaf["menu1"] == "All")
    assert all_leaf["node_type"] == "NAVIGATION_CONTAINER"
    valid, rejected = reject_navigation_container_leaves(taxonomy["leaves"])
    assert len(rejected) == 1
    assert rejected[0]["menu1"] == "All"


def test_roundtrip_sampler_selects_only_real_requestable_leaves():
    taxonomy = _serialize_and_reload()
    sample = select_representative_sample(taxonomy, target_count=20)
    assert all(leaf.menu1 != "All" for leaf in sample)
    families = {leaf.menu1 for leaf in sample}
    assert families == {"Sg", "Tee"}


def test_roundtrip_canonical_plan_matches_the_known_real_shape():
    """This project's OWN pipeline, round-tripped through JSON, must
    produce EXACTLY the expected canonical counts — zero malformed
    leaves, the navigation entry excluded, both real families present.
    A regression here would mean the serializer/reader pair have
    drifted apart."""
    taxonomy = _serialize_and_reload()
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.malformed_leaf_count == 0
    assert counts.navigation_container_count == 1
    assert counts.requestable_menu2_leaf_count == 2  # Sg::Total, Sg::TeeToGreen
    assert counts.requestable_menu3_leaf_count == 3  # Tee 010101/010102/010103
    assert counts.canonical_requestable_metric_count == 5
    assert all(entry["menu1"] != "All" for entry in plan)


def test_roundtrip_identity_tuple_matches_before_and_after_serialization():
    """The literal (menu1, menu2[, menu3]) tuple computed from the
    live MenuLeaf objects must equal the tuple recomputed from the
    round-tripped JSON dicts — the actual "identity survives
    unchanged" assertion Mission 3 asks for, checked both ways."""
    dom_result = inspect_menu_dom(_real_evidence_shaped_dom())
    live_identities = {leaf.identity for leaf in dom_result.requestable_leaves}

    taxonomy = json.loads(
        to_taxonomy_json(dom_result, source_url="https://example.test", discovered_at="2026-08-26T00:00:00Z")
    )
    sample = select_representative_sample(taxonomy, target_count=20)
    reloaded_identities = {leaf.identity for leaf in sample}

    assert live_identities == reloaded_identities
