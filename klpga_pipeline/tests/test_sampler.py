"""Tests for klpga.discovery.sampler. Pure in-memory taxonomy dicts —
no real KLPGA_RECORD_TAXONOMY_DISCOVERED.json exists in this repo (the
live Windows run's output was never pushed here), so these use small,
representative synthetic taxonomies covering multiple families."""
from __future__ import annotations

from klpga.discovery.sampler import find_duplicate_identities, select_representative_sample


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
