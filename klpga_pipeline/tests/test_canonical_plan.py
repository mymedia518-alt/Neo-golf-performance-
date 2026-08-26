"""Tests for klpga.discovery.canonical_plan — Phase B1 CLASS 2 fix.
Pure in-memory taxonomy dicts; no real KLPGA_RECORD_TAXONOMY_DISCOVERED.json
exists in this repo (see test_sampler.py's own note)."""
from __future__ import annotations

import json

from klpga.discovery.canonical_plan import (
    build_canonical_plan,
    build_canonical_plan_json,
    build_identity_key_collision_report,
    build_malformed_leaf_report,
    check_sanity_invariants,
    classify_malformation_reason,
    group_counts_by_family,
    to_identity_key_collision_report_csv,
    to_malformed_leaf_report_csv,
)


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


# ---------------------------------------------------------------
# Windows-reported real result: total=283, malformed=272 (~96%),
# navigation=6, requestable_menu2=1, requestable_menu3=4, canonical=5,
# collisions=0. These tests cover the diagnostic tooling built to
# investigate that: reason classification, the CSV report, per-family
# breakdown, and the sanity-invariant safety guard that must FAIL
# loudly on exactly this shape of result.
# ---------------------------------------------------------------


def test_classify_reason_both_blank_matches_pass1_unknown_fallback_signature():
    """The real menu_taxonomy.py Pass-1 "unknown" fallback (an
    unresolvable data-menu3 tag) always produces BOTH menu1="" and
    menu2="" together — never just one alone. This is the signature
    this reason category is built to detect."""
    leaf = {"menu1": "", "menu2": "", "menu3": "999999", "menu3_label": "고아 항목", "leaf_level": "menu3", "source_metric_key": "::999999"}
    assert classify_malformation_reason(leaf) == "missing_menu1_and_menu2"


def test_classify_reason_missing_menu1_only():
    leaf = {"menu1": "", "menu2": "Total", "menu3": None, "leaf_level": "menu2"}
    assert classify_malformation_reason(leaf) == "missing_menu1"


def test_classify_reason_missing_menu2_only():
    leaf = {"menu1": "Sg", "menu2": "", "menu3": None, "leaf_level": "menu2"}
    assert classify_malformation_reason(leaf) == "missing_menu2"


def test_classify_reason_missing_menu3_when_leaf_level_requires_it():
    leaf = {"menu1": "Sg", "menu2": "Total", "menu3": None, "leaf_level": "menu3"}
    assert classify_malformation_reason(leaf) == "missing_menu3_when_required"


def test_classify_reason_legacy_format_missing_leaf_level_key_entirely():
    """The ORIGINAL (pre-Round-3-patch) taxonomy JSON schema never had
    a leaf_level key at all — distinguished from a modern leaf that
    simply has blank menu1/menu2."""
    leaf = {"menu1": "", "menu2": "", "menu3": "999999", "menu3_label": "고아 항목", "source_metric_key": "::999999"}
    assert classify_malformation_reason(leaf) == "legacy_taxonomy_format_missing_leaf_level"


def test_classify_reason_unrecognized_fields_flagged_before_legacy_check():
    leaf = {"menu1": "", "menu2": "", "leaf_level": "menu3", "some_future_field": "??"}
    reason = classify_malformation_reason(leaf)
    assert reason.startswith("unrecognized_fields:")
    assert "some_future_field" in reason


def _real_windows_shaped_taxonomy() -> dict:
    """Mirrors the exact real Windows result's shape at small scale:
    mostly Pass-1-unknown-fallback (blank identity) leaves, a handful
    of navigation containers, and a handful of genuinely requestable
    leaves — proportioned the same way (heavily malformed-dominated)."""
    leaves = []
    for i in range(27):  # 27 blank-identity leaves standing in for the real 272
        leaves.append(
            {
                "menu1": "", "menu1_label": "", "menu2": "", "menu2_label": "",
                "menu3": f"{900000 + i}", "menu3_label": "고아 항목",
                "leaf_level": "menu3", "source_metric_key": f"::{900000 + i}",
            }
        )
    for menu2 in ("Sg", "Tee", "Approach", "Around", "Putt", "Other"):
        leaves.append(
            {
                "menu1": "All", "menu1_label": "All", "menu2": menu2, "menu2_label": "전체",
                "menu3": None, "menu3_label": None, "leaf_level": "menu2", "source_metric_key": f"All::{menu2}",
            }
        )
    leaves.append({"menu1": "Sg", "menu1_label": "SG", "menu2": "Total", "menu2_label": "SG : 전체", "menu3": None, "menu3_label": None, "leaf_level": "menu2", "source_metric_key": "Sg::Total"})
    for i in range(4):
        leaves.append(
            {
                "menu1": "Tee", "menu1_label": "티샷", "menu2": "Tee01", "menu2_label": "",
                "menu3": f"01010{i}", "menu3_label": f"거리 구간 {i}",
                "leaf_level": "menu3", "source_metric_key": f"Tee::Tee01::01010{i}",
            }
        )
    return {"source_url": "https://example.test", "leaves": leaves}


def test_build_malformed_leaf_report_covers_every_malformed_leaf():
    taxonomy = _real_windows_shaped_taxonomy()
    counts, _plan = build_canonical_plan(taxonomy)
    report = build_malformed_leaf_report(taxonomy)
    assert len(report) == counts.malformed_leaf_count == 27
    assert all(row["rejection_reason"] == "missing_menu1_and_menu2" for row in report)
    assert report[0]["original_index"] == 0
    assert report[0]["raw_menu3"] == "900000"
    assert report[0]["identity_key"] == "::::900000"  # carries the menu3 code even with blank menu1/menu2


def test_malformed_leaf_report_preserves_original_index_order():
    taxonomy = _real_windows_shaped_taxonomy()
    report = build_malformed_leaf_report(taxonomy)
    indices = [row["original_index"] for row in report]
    assert indices == sorted(indices)


def test_to_malformed_leaf_report_csv_has_required_columns():
    taxonomy = _real_windows_shaped_taxonomy()
    report = build_malformed_leaf_report(taxonomy)
    csv_text = to_malformed_leaf_report_csv(report)
    header = csv_text.splitlines()[0]
    for col in ["original_index", "raw_menu1", "raw_menu2", "raw_menu3", "leaf_level", "label", "node_type", "identity_key", "rejection_reason"]:
        assert col in header
    assert len(csv_text.splitlines()) == 1 + len(report)


def test_group_counts_by_family_covers_confirmed_families_and_other():
    """Grouping is strictly by each leaf's OWN menu1 value — an
    "All::Sg" navigation entry has menu1="All", not "Sg", so it lands
    in "other" alongside every other All::* entry, never inflating a
    confirmed family's count."""
    taxonomy = _real_windows_shaped_taxonomy()
    families = group_counts_by_family(taxonomy)
    assert families["Sg"] == {"total": 1, "malformed": 0, "requestable_menu2": 1, "requestable_menu3": 0, "navigation_container": 0}
    assert families["Tee"] == {"total": 4, "malformed": 0, "requestable_menu2": 0, "requestable_menu3": 4, "navigation_container": 0}
    assert families["Approach"] == {"total": 0, "malformed": 0, "requestable_menu2": 0, "requestable_menu3": 0, "navigation_container": 0}
    # "other" = 27 orphaned (blank-identity) leaves + all 6 All::* navigation entries
    assert families["other"]["total"] == 27 + 6
    assert families["other"]["malformed"] == 27
    assert families["other"]["navigation_container"] == 6


def test_sanity_invariants_fail_loudly_on_the_real_windows_shaped_result():
    """This is the exact regression the mission demands: a
    ~96%-malformed result must FAIL validation, not be silently
    presented as a successful canonical plan."""
    taxonomy = _real_windows_shaped_taxonomy()
    counts, _plan = build_canonical_plan(taxonomy)
    violations = check_sanity_invariants(counts)
    assert violations  # non-empty — must fail
    assert any("malformed_ratio" in v for v in violations)


def test_sanity_invariants_pass_on_a_clean_result():
    taxonomy = {
        "leaves": [
            {"menu1": "Sg", "menu1_label": "SG", "menu2": "Total", "menu2_label": "SG : 전체", "menu3": None, "menu3_label": None, "leaf_level": "menu2", "source_metric_key": "Sg::Total"},
            {"menu1": "Tee", "menu1_label": "티샷", "menu2": "Tee01", "menu2_label": "", "menu3": "010101", "menu3_label": "평균 티샷 거리", "leaf_level": "menu3", "source_metric_key": "Tee::Tee01::010101"},
        ]
    }
    counts, _plan = build_canonical_plan(taxonomy)
    assert check_sanity_invariants(counts) == []


def test_sanity_invariants_do_not_fire_on_empty_taxonomy():
    counts, _plan = build_canonical_plan({"leaves": []})
    assert check_sanity_invariants(counts) == []


# ---------------------------------------------------------------
# Round 10 — identity_key duplication: the B2 Stage 1 blocker.
#
# Mechanism confirmed by reading build_canonical_plan directly (no
# live data needed): the exact-duplicate dedup key is
# (identity_tuple, label) — NOT identity_tuple alone. Two DOM leaves
# sharing the exact same menu1/menu2/menu3 but carrying DIFFERENT
# labels are therefore NOT deduplicated: both survive into the
# canonical plan, both carrying the SAME identity_key string (derived
# from identity_tuple only, never label). This is a different
# mechanism from menu3_collision_count, which only tracks BARE menu3
# codes shared across DIFFERENT menu1/menu2 paths (a menu2-level leaf
# has no menu3 to collide on at all, and two entries can share a bare
# menu3 code while having completely different, non-colliding
# identity_keys).
# ---------------------------------------------------------------


def test_same_identity_different_label_is_not_deduplicated_and_shares_identity_key():
    """The exact mechanism behind the real 30-group/33-entry finding:
    same (menu1, menu2, menu3), two different labels."""
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee05", "010301", "menu3", "라벨 A"),
            _leaf("Tee", "Tee05", "010301", "menu3", "라벨 B"),
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.exact_duplicate_count == 0  # NOT an exact (identity, label) duplicate
    assert counts.canonical_requestable_metric_count == 2  # both entries survive
    assert counts.unique_identity_key_count == 1
    assert counts.duplicate_identity_key_group_count == 1
    identity_keys = {p["identity_key"] for p in plan}
    assert identity_keys == {"Tee::Tee05::010301"}
    assert {p["label"] for p in plan} == {"라벨 A", "라벨 B"}


def test_same_identity_same_label_cannot_reach_duplicate_identity_key_count():
    """Category A (same identity_key AND same label) is structurally
    IMPOSSIBLE to reach duplicate_identity_key_group_count — it is
    collapsed by the exact-duplicate dedup step first."""
    taxonomy = {
        "leaves": [
            _leaf("Tee", "Tee05", "010301", "menu3", "동일 라벨"),
            _leaf("Tee", "Tee05", "010301", "menu3", "동일 라벨"),
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.exact_duplicate_count == 1
    assert counts.canonical_requestable_metric_count == 1
    assert counts.unique_identity_key_count == 1
    assert counts.duplicate_identity_key_group_count == 0


def test_menu2_level_identity_key_collision_is_detected():
    """menu3_collision_count structurally cannot see this (a menu2-
    level leaf has no menu3) — duplicate_identity_key_group_count must
    still catch it, since it operates on identity_key directly."""
    taxonomy = {
        "leaves": [
            _leaf("Sg", "Total", None, "menu2", "SG : 전체 A"),
            _leaf("Sg", "Total", None, "menu2", "SG : 전체 B"),
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.menu3_collision_count == 0  # blind to menu2-level collisions, by design
    assert counts.duplicate_identity_key_group_count == 1
    assert counts.unique_identity_key_count == 1
    assert len(plan) == 2


def test_unique_identity_key_count_on_the_real_evidence_taxonomy():
    """The shared fixture's cross-family menu3 collision ("010102"
    under both Tee and Approach) produces DIFFERENT identity_keys
    (Tee::Tee01::010102 vs Approach::Approach02::010102) — it must NOT
    be counted as an identity_key duplicate, confirming the two
    mechanisms are genuinely independent."""
    counts, plan = build_canonical_plan(_real_evidence_taxonomy())
    assert counts.menu3_collision_count == 1
    assert counts.duplicate_identity_key_group_count == 0
    assert counts.unique_identity_key_count == counts.canonical_requestable_metric_count == len(plan)


def test_build_identity_key_collision_report_empty_when_no_collisions():
    assert build_identity_key_collision_report(_real_evidence_taxonomy()) == []


def test_build_identity_key_collision_report_covers_every_field_and_is_grouped():
    taxonomy = {
        "leaves": [
            _leaf("Sg", "Total", None, "menu2", "SG : 전체 A"),
            {**_leaf("Sg", "Total", None, "menu2", "SG : 전체 B"), "label_resolution_method": "ancestor_walk"},
            _leaf("Tee", "Tee01", "010101", "menu3", "고유 라벨"),  # not part of any collision
        ]
    }
    rows = build_identity_key_collision_report(taxonomy)
    assert len(rows) == 2  # only the colliding Sg::Total pair — the unique Tee entry is excluded
    assert {r["identity_key"] for r in rows} == {"Sg::Total"}
    assert all(r["group_size"] == 2 for r in rows)
    labels = sorted(r["label"] for r in rows)
    assert labels == ["SG : 전체 A", "SG : 전체 B"]
    required_keys = {
        "identity_key", "group_size", "menu1", "menu2", "menu3", "leaf_level",
        "label", "node_type", "evidence_source", "label_resolution_method", "is_menu3_collision",
    }
    for row in rows:
        assert required_keys.issubset(row.keys())
    # Provenance from the ORIGINAL raw taxonomy leaf is preserved when present.
    method_row = next(r for r in rows if r["label"] == "SG : 전체 B")
    assert method_row["label_resolution_method"] == "ancestor_walk"


def test_to_identity_key_collision_report_csv_has_required_columns():
    taxonomy = {
        "leaves": [
            _leaf("Sg", "Total", None, "menu2", "라벨 A"),
            _leaf("Sg", "Total", None, "menu2", "라벨 B"),
        ]
    }
    rows = build_identity_key_collision_report(taxonomy)
    csv_text = to_identity_key_collision_report_csv(rows)
    header = csv_text.splitlines()[0]
    for column in ("identity_key", "group_size", "menu1", "menu2", "menu3", "label", "node_type", "evidence_source"):
        assert column in header
