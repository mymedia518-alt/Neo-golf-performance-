"""Mission 4 regression tests — the real Windows result after the
preceding_context fix (283 valid identity nodes, 0 malformed) revealed
that node_type=NAVIGATION_CONTAINER was overbroad: 278 of 283 nodes
were classified navigation, because the classifier only checked
`menu1 == "All"` with no leaf_level restriction, and 272 genuine
menu3-level metric leaves structurally resolved their nearest
preceding data-menu1 to a shared "All"-tagged container.

Fix: NAVIGATION_CONTAINER is now scoped to the exact CONFIRMED
evidence shape — menu1="All" AND leaf_level="menu2" (menu3 absent).
A menu3-level leaf is never excluded on menu1 value alone, at any
resolution method, regardless of appearing anywhere inside navigation
DOM structure.

These tests are numbered to match Mission 4's own list."""
from __future__ import annotations

from klpga.discovery.canonical_plan import build_canonical_plan
from klpga.discovery.menu_taxonomy import (
    NODE_TYPE_NAVIGATION_CONTAINER,
    NODE_TYPE_REQUESTABLE_METRIC_LEAF,
    inspect_menu_dom,
)
from klpga.discovery.sampler import reject_navigation_container_leaves, select_representative_sample


# ---------------------------------------------------------------
# A. Confirmed All::* navigation/container nodes remain excluded
#    (the exact confirmed shape: menu2-level, no menu3)
# ---------------------------------------------------------------


def test_menu2_level_all_leaf_still_classified_as_navigation_container():
    html = '<a data-menu1="All" data-menu2="Sg">전체기록보기</a>'
    result = inspect_menu_dom(html)
    leaf = result.leaves[0]
    assert leaf.leaf_level == "menu2"
    assert leaf.node_type == NODE_TYPE_NAVIGATION_CONTAINER


def test_all_menu2_leaf_still_rejected_by_sampler():
    taxonomy = {
        "leaves": [
            {"menu1": "All", "menu2": "Sg", "menu3": None, "leaf_level": "menu2", "node_type": "NAVIGATION_CONTAINER", "source_metric_key": "All::Sg"},
        ]
    }
    sample = select_representative_sample(taxonomy, target_count=20)
    assert sample == []
    valid, rejected = reject_navigation_container_leaves(taxonomy["leaves"])
    assert valid == []
    assert len(rejected) == 1


def test_all_menu2_leaf_still_excluded_from_canonical_plan():
    taxonomy = {
        "leaves": [
            {"menu1": "All", "menu2": "Sg", "menu3": None, "menu2_label": "전체", "menu3_label": None, "leaf_level": "menu2", "source_metric_key": "All::Sg"},
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.navigation_container_count == 1
    assert plan == []


# ---------------------------------------------------------------
# B. A menu3-bearing clickable link with data-menu1/menu2/menu3
#    (own_attrs — the site's actual getRecord click mechanism) is
#    REQUESTABLE_METRIC_LEAF even when its own menu1 reads "All"
# ---------------------------------------------------------------


def test_menu3_level_own_attrs_leaf_with_menu1_all_is_requestable_not_navigation():
    """Direct regression for the real bug: a genuine metric-request
    anchor carrying data-menu1="All" data-menu2="Sg" data-menu3="X"
    directly (own_attrs — the confirmed getRecord(menu1, menu2, menu3)
    click shape) must be REQUESTABLE_METRIC_LEAF, never excluded
    merely because menu1 happens to be "All"."""
    html = '<a data-menu1="All" data-menu2="Sg" data-menu3="010101">Par4,5 티샷 비율</a>'
    result = inspect_menu_dom(html)
    leaf = result.leaves[0]
    assert leaf.leaf_level == "menu3"
    assert leaf.menu1 == "All"
    assert leaf.node_type == NODE_TYPE_REQUESTABLE_METRIC_LEAF


def test_menu3_level_leaf_survives_sampling_even_with_menu1_all():
    taxonomy = {
        "leaves": [
            {
                "menu1": "All", "menu2": "Sg", "menu3": "010101", "menu2_label": "", "menu3_label": "Par4,5 티샷 비율",
                "leaf_level": "menu3", "node_type": "REQUESTABLE_METRIC_LEAF", "source_metric_key": "All::Sg::010101",
            },
        ]
    }
    sample = select_representative_sample(taxonomy, target_count=20)
    assert len(sample) == 1
    assert sample[0].identity == ("All", "Sg", "010101")


# ---------------------------------------------------------------
# C. menu2-level SG metric links are classified correctly
# ---------------------------------------------------------------


def test_sg_menu2_leaf_still_requestable():
    html = '<a data-menu1="Sg" data-menu2="Total">SG : 전체</a>'
    result = inspect_menu_dom(html)
    assert result.leaves[0].node_type == NODE_TYPE_REQUESTABLE_METRIC_LEAF


# ---------------------------------------------------------------
# D. Ancestor-container-id-resolved menu3 leaves do not become
#    NAVIGATION_CONTAINER merely because a genuine ancestor id happens
#    to be a family name — and, per the Round 4 resolver rewrite (see
#    tests/test_container_id_resolution.py for the full regression
#    suite), a menu3-level leaf can no longer resolve menu1="All" at
#    all unless that value is genuinely present as its own attribute
#    or a genuine ancestor's — the old sibling-header
#    `preceding_context` shape these tests used to model here has been
#    proven, by real page evidence, to never have existed on the real
#    site; the two `inspect_menu_dom`-level tests that used to live
#    here were removed for that reason. This one stays: it exercises
#    `canonical_plan.py` directly (a layer this round did not touch)
#    against an already-resolved taxonomy dict, independent of HOW
#    that resolution happened.
# ---------------------------------------------------------------


def test_canonical_plan_no_longer_bulk_excludes_preceding_context_all_leaves():
    """End-to-end: the canonical-plan builder must count these as
    requestable menu3 metrics, not navigation containers."""
    taxonomy = {
        "leaves": [
            {
                "menu1": "All", "menu2": "Sg", "menu3": "010101", "menu2_label": "", "menu3_label": "Par4,5 티샷 비율",
                "leaf_level": "menu3", "node_type": "REQUESTABLE_METRIC_LEAF", "source_metric_key": "All::Sg::010101",
            },
            {
                "menu1": "All", "menu2": "Sg", "menu3": None, "menu2_label": "전체", "menu3_label": None,
                "leaf_level": "menu2", "node_type": "NAVIGATION_CONTAINER", "source_metric_key": "All::Sg",
            },
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.navigation_container_count == 1
    assert counts.requestable_menu3_leaf_count == 1
    assert counts.canonical_requestable_metric_count == 1
    assert plan[0]["identity_key"] == "All::Sg::010101"


# ---------------------------------------------------------------
# E. Exact duplicates and collisions remain handled separately,
#    unaffected by this fix
# ---------------------------------------------------------------


def test_exact_duplicate_dedup_still_works_after_the_fix():
    taxonomy = {
        "leaves": [
            {
                "menu1": "All", "menu2": "Sg", "menu3": "010101", "menu2_label": "", "menu3_label": "Par4,5 티샷 비율",
                "leaf_level": "menu3", "node_type": "REQUESTABLE_METRIC_LEAF", "source_metric_key": "All::Sg::010101",
            },
            {
                "menu1": "All", "menu2": "Sg", "menu3": "010101", "menu2_label": "", "menu3_label": "Par4,5 티샷 비율",
                "leaf_level": "menu3", "node_type": "REQUESTABLE_METRIC_LEAF", "source_metric_key": "All::Sg::010101",
            },
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.exact_duplicate_count == 1
    assert counts.canonical_requestable_metric_count == 1
    assert len(plan) == 1


def test_menu3_collision_still_preserved_across_different_parents_after_the_fix():
    taxonomy = {
        "leaves": [
            {
                "menu1": "All", "menu2": "Sg", "menu3": "010102", "menu2_label": "", "menu3_label": "라벨A",
                "leaf_level": "menu3", "node_type": "REQUESTABLE_METRIC_LEAF", "source_metric_key": "All::Sg::010102",
            },
            {
                "menu1": "All", "menu2": "Tee", "menu3": "010102", "menu2_label": "", "menu3_label": "라벨B",
                "leaf_level": "menu3", "node_type": "REQUESTABLE_METRIC_LEAF", "source_metric_key": "All::Tee::010102",
            },
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.menu3_collision_count == 1
    assert len(plan) == 2  # both preserved, never deduplicated by menu3 alone
