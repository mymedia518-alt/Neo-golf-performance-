"""Tests for klpga.discovery.sampler. Pure in-memory taxonomy dicts —
no real KLPGA_RECORD_TAXONOMY_DISCOVERED.json exists in this repo (the
live Windows run's output was never pushed here), so these use small,
representative synthetic taxonomies covering multiple families."""
from __future__ import annotations

from klpga.discovery.sampler import find_duplicate_identities, reject_malformed_leaves, select_representative_sample


def _leaf(menu1, menu1_label, menu2, menu2_label, menu3, menu3_label, leaf_level):
    key = f"{menu1}::{menu2}" + (f"::{menu3}" if leaf_level == "menu3" else "")
    return {
        "menu1": menu1,
        "menu1_label": menu1_label,
        "menu2": menu2,
        "menu2_label": menu2_label,
        "menu3": menu3,
        "menu3_label": menu3_label,
        "leaf_level": leaf_level,
        "source_metric_key": key,
    }


def _multi_family_taxonomy() -> dict:
    leaves = [
        _leaf("Sg", "SG", "Total", "SG : 전체", None, None, "menu2"),
        _leaf("Sg", "SG", "Tee", "SG : 티샷", None, None, "menu2"),
        _leaf("Tee", "티샷", "Tee01", "Par4,5 티샷 비율", "010101", "평균 티샷 거리", "menu3"),
        _leaf("Tee", "티샷", "Tee01", "Par4,5 티샷 비율", "010102", "280야드 이상(RTP)", "menu3"),
        _leaf("Tee", "티샷", "Tee01", "Par4,5 티샷 비율", "010103", "260~280야드 미만(RTP)", "menu3"),
        _leaf("Approach", "어프로치", "Approach01", "그린 적중률", "020104", "160~180야드 미만(RTP)", "menu3"),
        _leaf("Approach", "어프로치", "Approach01", "그린 적중률", "020105", "140~160야드 미만(RTP)", "menu3"),
        _leaf("Approach", "어프로치", "Approach02", "다른 그룹", "020201", "다른 지표", "menu3"),
        _leaf("Putting", "퍼팅", "Putting01", "1퍼트", "030101", "1퍼트 성공률", "menu3"),
        _leaf("Putting", "퍼팅", "Putting01", "1퍼트", "030102", "1퍼트 성공률2", "menu3"),
    ]
    return {"source_url": "https://example.test/record", "leaves": leaves}


def test_only_leaves_present_in_the_taxonomy_are_ever_selected():
    taxonomy = _multi_family_taxonomy()
    sample = select_representative_sample(taxonomy, target_count=6)
    valid_keys = {leaf["source_metric_key"] for leaf in taxonomy["leaves"]}
    assert all(s.source_metric_key in valid_keys for s in sample)


def test_sample_never_exceeds_target_count():
    taxonomy = _multi_family_taxonomy()
    sample = select_representative_sample(taxonomy, target_count=4)
    assert len(sample) <= 4


def test_sample_covers_multiple_families_not_just_the_largest():
    """Approach/Tee have 3 leaves each, Sg/Putting have 2 — a naive
    "first N in taxonomy order" pick could miss smaller families
    entirely. The round-robin-by-family strategy must not."""
    taxonomy = _multi_family_taxonomy()
    sample = select_representative_sample(taxonomy, target_count=6)
    families = {leaf.menu1 for leaf in sample}
    assert len(families) >= 3


def test_menu2_level_leaves_preferred_within_their_family():
    taxonomy = _multi_family_taxonomy()
    sample = select_representative_sample(taxonomy, target_count=2, per_family_cap=2)
    sg_leaves = [leaf for leaf in sample if leaf.menu1 == "Sg"]
    assert all(leaf.leaf_level == "menu2" for leaf in sg_leaves)


def test_selection_is_deterministic_across_repeated_calls():
    taxonomy = _multi_family_taxonomy()
    sample1 = select_representative_sample(taxonomy, target_count=8)
    sample2 = select_representative_sample(taxonomy, target_count=8)
    assert [s.source_metric_key for s in sample1] == [s.source_metric_key for s in sample2]


def test_empty_taxonomy_yields_empty_sample_not_an_error():
    sample = select_representative_sample({"leaves": []}, target_count=10)
    assert sample == []


def test_identity_nullable_menu3_for_menu2_level_leaves():
    taxonomy = _multi_family_taxonomy()
    sample = select_representative_sample(taxonomy, target_count=10)
    sg_total = next(s for s in sample if s.menu1 == "Sg" and s.menu2 == "Total")
    assert sg_total.menu3 is None
    assert sg_total.identity == ("Sg", "Total")


def test_identity_full_triple_for_menu3_level_leaves():
    taxonomy = _multi_family_taxonomy()
    sample = select_representative_sample(taxonomy, target_count=10)
    approach = next(s for s in sample if s.menu1 == "Approach" and s.menu3 == "020104")
    assert approach.identity == ("Approach", "Approach01", "020104")


def test_find_duplicate_identities_detects_a_sampler_bug():
    taxonomy = _multi_family_taxonomy()
    sample = select_representative_sample(taxonomy, target_count=10)
    duplicated_sample = sample + [sample[0]]
    duplicates = find_duplicate_identities(duplicated_sample)
    assert duplicates == [sample[0].identity]


def test_find_duplicate_identities_empty_when_sample_is_clean():
    taxonomy = _multi_family_taxonomy()
    sample = select_representative_sample(taxonomy, target_count=10)
    assert find_duplicate_identities(sample) == []


# ---------------------------------------------------------------
# Phase B1.1 Mission 4 — malformed leaf rejection. Root cause: the
# live Windows run's reported `('', '', '010101')` "duplicate
# identity" was never a sampler bug — it is menu_taxonomy.py's
# `inspect_menu_dom` Pass 1 fallback (an unresolvable data-menu3 tag
# with no discoverable menu1/menu2 ancestor is preserved with blank
# identity, per test_unresolvable_menu3_is_preserved_not_dropped in
# test_menu_taxonomy.py — correct at that layer, an audit trail of
# what the DOM scan could not resolve). The defect was that nothing
# downstream ever rejected such a leaf before it could be sampled into
# a live request. These tests cover the fix: rejection happens here,
# at the sampling boundary.
# ---------------------------------------------------------------


def _malformed_leaf(menu3="010101"):
    return _leaf("", "", "", "", menu3, "고아 항목", "menu3")


def test_reject_malformed_leaves_splits_blank_menu1_menu2_out():
    leaves = [_leaf("Sg", "SG", "Total", "SG : 전체", None, None, "menu2"), _malformed_leaf()]
    valid, rejected = reject_malformed_leaves(leaves)
    assert len(valid) == 1
    assert valid[0]["menu1"] == "Sg"
    assert len(rejected) == 1
    assert rejected[0]["menu3"] == "010101"


def test_reject_malformed_leaves_catches_blank_menu1_or_menu2_alone():
    only_blank_menu1 = _leaf("", "", "Total", "SG : 전체", None, None, "menu2")
    only_blank_menu2 = _leaf("Sg", "SG", "", "", None, None, "menu2")
    valid, rejected = reject_malformed_leaves([only_blank_menu1, only_blank_menu2])
    assert valid == []
    assert len(rejected) == 2


def test_reject_malformed_leaves_empty_when_nothing_malformed():
    leaves = [_leaf("Sg", "SG", "Total", "SG : 전체", None, None, "menu2")]
    valid, rejected = reject_malformed_leaves(leaves)
    assert len(valid) == 1
    assert rejected == []


def test_malformed_leaves_never_reach_the_sample_even_without_pre_filtering():
    """Defense in depth: select_representative_sample must reject a
    malformed leaf itself, even if the caller forgot to call
    reject_malformed_leaves first."""
    taxonomy = _multi_family_taxonomy()
    taxonomy["leaves"].append(_malformed_leaf())
    sample = select_representative_sample(taxonomy, target_count=20)
    assert all(leaf.menu1 and leaf.menu2 for leaf in sample)
    assert ("", "", "010101") not in {leaf.identity for leaf in sample}


def test_duplicate_malformed_leaves_are_rejected_not_reported_as_sampler_duplicates():
    """Two independently-orphaned DOM tags sharing the same menu3 code
    (e.g. a desktop+mobile nav duplicate) must be rejected outright,
    never surfacing as a find_duplicate_identities warning — that
    warning is reserved for genuine sampler bugs, not malformed input."""
    taxonomy = _multi_family_taxonomy()
    taxonomy["leaves"].extend([_malformed_leaf(), _malformed_leaf()])
    sample = select_representative_sample(taxonomy, target_count=20)
    assert find_duplicate_identities(sample) == []


# ---------------------------------------------------------------
# Phase B1.1 Mission 5 — "All"/navigation families must not compete on
# equal footing with the five confirmed stat families for a scarce
# sample slot.
# ---------------------------------------------------------------


def test_confirmed_stat_families_are_prioritized_over_all_navigation_family():
    taxonomy = {
        "source_url": "https://example.test/record",
        "leaves": [
            _leaf("All", "전체기록보기", "AllTotal", "전체", None, None, "menu2"),
            _leaf("Sg", "SG", "Total", "SG : 전체", None, None, "menu2"),
            _leaf("Tee", "티샷", "Tee01", "Par4,5 티샷 비율", "010101", "평균 티샷 거리", "menu3"),
        ],
    }
    # A sample too small to fit every family must still take the three
    # confirmed families before "All" — with target_count=2, only the
    # two priority families should be picked.
    sample = select_representative_sample(taxonomy, target_count=2, per_family_cap=1)
    families = {leaf.menu1 for leaf in sample}
    assert "All" not in families
    assert families == {"Sg", "Tee"}
