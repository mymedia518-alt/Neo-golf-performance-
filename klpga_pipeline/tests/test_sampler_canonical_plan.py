"""Phase B1 (canonical-plan-as-source-of-truth round) — tests for
sampler.select_representative_sample_from_canonical_plan and its
_canonical_entry_to_leaf_dict adapter.

Context: the real Windows run confirmed Phase A's canonical request
plan (docs/discovery/KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json) is now
correct — 277 canonical requestable metrics, 31 real menu3 collisions,
0 malformed leaves, sanity check passed. Per instruction, Phase B1
sampling must use that canonical plan as its source of truth (rather
than re-deriving malformed/navigation rejection from a raw taxonomy),
and the sample must deterministically cover at least one colliding and
one non-colliding menu3 identity. These tests use small, in-memory
canonical-plan entry lists — no real
KLPGA_CANONICAL_METRIC_REQUEST_PLAN.json exists in this repo (the real
Windows output was never pushed here)."""
from __future__ import annotations

from klpga.discovery.canonical_plan import build_canonical_plan
from klpga.discovery.sampler import (
    _canonical_entry_to_leaf_dict,
    find_duplicate_identities,
    select_full_canonical_plan,
    select_representative_sample_from_canonical_plan,
)


def _entry(menu1, menu2, menu3, leaf_level, label, evidence_source=None):
    identity_key = f"{menu1}::{menu2}" + (f"::{menu3}" if leaf_level == "menu3" else "")
    return {
        "menu1": menu1,
        "menu2": menu2,
        "menu3": menu3,
        "leaf_level": leaf_level,
        "identity_key": identity_key,
        "label": label,
        "node_type": "REQUESTABLE_METRIC_LEAF",
        "evidence_source": evidence_source or identity_key,
    }


# ---------------------------------------------------------------
# A. Adapter correctness — every field traces directly to the
#    canonical-plan entry, nothing invented.
# ---------------------------------------------------------------


def test_adapter_maps_menu3_level_entry_fields():
    entry = _entry("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")
    leaf_dict = _canonical_entry_to_leaf_dict(entry)
    assert leaf_dict["menu1"] == "Tee"
    assert leaf_dict["menu2"] == "Tee01"
    assert leaf_dict["menu3"] == "010101"
    assert leaf_dict["leaf_level"] == "menu3"
    assert leaf_dict["menu3_label"] == "평균 티샷 거리"
    assert leaf_dict["menu2_label"] == ""
    assert leaf_dict["source_metric_key"] == "Tee::Tee01::010101"
    assert leaf_dict["node_type"] == "REQUESTABLE_METRIC_LEAF"


def test_adapter_maps_menu2_level_entry_fields():
    entry = _entry("Sg", "Total", None, "menu2", "SG : 전체")
    leaf_dict = _canonical_entry_to_leaf_dict(entry)
    assert leaf_dict["menu2_label"] == "SG : 전체"
    assert leaf_dict["menu3_label"] is None
    assert leaf_dict["menu3"] is None
    assert leaf_dict["leaf_level"] == "menu2"


def test_adapter_falls_back_to_identity_key_when_evidence_source_missing():
    entry = _entry("Sg", "Total", None, "menu2", "SG : 전체")
    del entry["evidence_source"]
    leaf_dict = _canonical_entry_to_leaf_dict(entry)
    assert leaf_dict["source_metric_key"] == entry["identity_key"]


# ---------------------------------------------------------------
# B. Only plan entries are ever selected, sample stays deterministic.
# ---------------------------------------------------------------


def _multi_family_plan() -> list[dict]:
    return [
        _entry("Sg", "Total", None, "menu2", "SG : 전체"),
        _entry("Sg", "Tee", None, "menu2", "SG : 티샷"),
        _entry("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
        _entry("Tee", "Tee01", "010102", "menu3", "280야드 이상(RTP)"),
        _entry("Approach", "Approach01", "020104", "menu3", "160~180야드 미만(RTP)"),
        _entry("Around", "Around01", "030101", "menu3", "그린 주변 샷"),
        _entry("Putt", "Putt01", "040101", "menu3", "1퍼트 성공률"),
    ]


def test_only_plan_entries_are_ever_selected():
    plan = _multi_family_plan()
    sample = select_representative_sample_from_canonical_plan(plan, target_count=10)
    valid_keys = {e["identity_key"] for e in plan}
    assert all(leaf.source_metric_key in valid_keys for leaf in sample)


def test_selection_from_canonical_plan_is_deterministic():
    plan = _multi_family_plan()
    sample1 = select_representative_sample_from_canonical_plan(plan, target_count=10)
    sample2 = select_representative_sample_from_canonical_plan(plan, target_count=10)
    assert [s.source_metric_key for s in sample1] == [s.source_metric_key for s in sample2]


def test_empty_plan_yields_empty_sample_not_an_error():
    assert select_representative_sample_from_canonical_plan([], target_count=10) == []


def test_sample_stays_within_bounded_range_for_realistic_target():
    """Instruction: "Keep the sample bounded to approximately 12-20
    representative canonical metrics." The collision/non-collision
    top-up can add at most 2 beyond the base round-robin result — this
    must never blow the sample open."""
    plan = _multi_family_plan() + [
        _entry("Tee", "Tee01", "010101", "menu3", "다른 카테고리 동일 코드"),  # collides with 010101
    ]
    sample = select_representative_sample_from_canonical_plan(plan, target_count=20)
    assert len(sample) <= 20 + 2


# ---------------------------------------------------------------
# C. Collision/non-collision coverage guarantee — the explicit
#    instruction: "Include coverage across ... collision/non-collision
#    identities."
# ---------------------------------------------------------------


def _plan_with_one_collision_buried_out_of_reach() -> list[dict]:
    """A small target_count and a large per-family cap conspire so the
    plain round-robin sampler would naturally miss the single colliding
    pair (Around/Around01/030101 vs Putt/Putt01/030101) because Around
    and Putt each contribute only one candidate slot before the other
    families already fill the sample."""
    plan = [
        _entry("Sg", "Total", None, "menu2", "SG : 전체"),
        _entry("Sg", "Tee", None, "menu2", "SG : 티샷"),
        _entry("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
        _entry("Tee", "Tee01", "010102", "menu3", "280야드 이상(RTP)"),
        _entry("Approach", "Approach01", "020104", "menu3", "160~180야드 미만(RTP)"),
        _entry("Approach", "Approach02", "020201", "menu3", "다른 지표"),
        # The genuine collision pair — same menu3 code, different menu1/menu2 parents.
        _entry("Around", "Around01", "030101", "menu3", "그린 주변 샷"),
        _entry("Putt", "Putt01", "030101", "menu3", "우연히 같은 코드"),
    ]
    return plan


def test_sample_includes_at_least_one_colliding_menu3_identity():
    plan = _plan_with_one_collision_buried_out_of_reach()
    sample = select_representative_sample_from_canonical_plan(plan, target_count=20)
    menu3_counts: dict[str, int] = {}
    for e in plan:
        if e["leaf_level"] == "menu3":
            menu3_counts[e["menu3"]] = menu3_counts.get(e["menu3"], 0) + 1
    colliding = {code for code, count in menu3_counts.items() if count > 1}
    assert any(leaf.leaf_level == "menu3" and leaf.menu3 in colliding for leaf in sample)


def test_sample_includes_at_least_one_non_colliding_menu3_identity():
    plan = _plan_with_one_collision_buried_out_of_reach()
    sample = select_representative_sample_from_canonical_plan(plan, target_count=20)
    menu3_counts: dict[str, int] = {}
    for e in plan:
        if e["leaf_level"] == "menu3":
            menu3_counts[e["menu3"]] = menu3_counts.get(e["menu3"], 0) + 1
    non_colliding = {code for code, count in menu3_counts.items() if count == 1}
    assert any(leaf.leaf_level == "menu3" and leaf.menu3 in non_colliding for leaf in sample)


def test_collision_topup_never_introduces_a_duplicate_identity():
    plan = _plan_with_one_collision_buried_out_of_reach()
    sample = select_representative_sample_from_canonical_plan(plan, target_count=20)
    assert find_duplicate_identities(sample) == []


def test_no_collision_present_in_plan_is_not_an_error():
    """When the plan genuinely has zero menu3 collisions, the top-up
    must be a no-op — never fabricate a fake collision."""
    plan = [
        _entry("Sg", "Total", None, "menu2", "SG : 전체"),
        _entry("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리"),
    ]
    sample = select_representative_sample_from_canonical_plan(plan, target_count=10)
    assert len(sample) == 2


# ---------------------------------------------------------------
# D. End-to-end: real canonical_plan.build_canonical_plan output feeds
#    directly into the new sampler function without adaptation.
# ---------------------------------------------------------------


def test_end_to_end_from_build_canonical_plan_output():
    taxonomy = {
        "leaves": [
            {"menu1": "Sg", "menu2": "Total", "menu3": None, "menu2_label": "SG : 전체", "menu3_label": None, "leaf_level": "menu2", "source_metric_key": "Sg::Total"},
            {"menu1": "Tee", "menu2": "Tee01", "menu3": "010101", "menu2_label": "", "menu3_label": "평균 티샷 거리", "leaf_level": "menu3", "source_metric_key": "Tee::Tee01::010101"},
            {"menu1": "Approach", "menu2": "Approach01", "menu3": "010102", "menu2_label": "", "menu3_label": "라벨A", "leaf_level": "menu3", "source_metric_key": "Approach::Approach01::010102"},
            {"menu1": "Around", "menu2": "Around01", "menu3": "010102", "menu2_label": "", "menu3_label": "라벨B", "leaf_level": "menu3", "source_metric_key": "Around::Around01::010102"},
            {"menu1": "All", "menu2": "Sg", "menu3": None, "menu2_label": "전체", "menu3_label": None, "leaf_level": "menu2", "source_metric_key": "All::Sg"},
        ]
    }
    counts, plan = build_canonical_plan(taxonomy)
    assert counts.menu3_collision_count == 1
    sample = select_representative_sample_from_canonical_plan(plan, target_count=10)
    assert all(leaf.menu1 != "All" for leaf in sample)
    assert len(sample) >= 1


# ---------------------------------------------------------------
# E. Phase B2 (Round 9 follow-up) — select_full_canonical_plan: every
#    entry, no per_family_cap, deterministic order.
# ---------------------------------------------------------------


def test_full_canonical_plan_returns_every_entry_not_a_sample():
    """A family with MORE than select_representative_sample_from_
    canonical_plan's per_family_cap (4) worth of entries must still
    return ALL of them — this is the whole point of the B2 full sweep
    versus the B1 representative sample."""
    plan = [_entry("Sg", "Total", None, "menu2", "SG : 전체")] + [
        _entry("Sg", f"Sub{i}", f"00000{i}", "menu3", f"라벨{i}") for i in range(6)
    ]
    assert len(plan) == 7  # 1 more than the B1 per_family_cap of 4, plus 2 extra to be sure

    full = select_full_canonical_plan(plan)
    assert len(full) == 7

    capped_sample = select_representative_sample_from_canonical_plan(plan, target_count=20)
    assert len(capped_sample) < len(full)  # proves the B1 path really would have dropped some


def test_full_canonical_plan_deterministic_order_by_menu1_menu2_menu3():
    plan = [
        _entry("Tee", "Tee02", "010102", "menu3", "라벨"),
        _entry("Sg", "Total", None, "menu2", "SG : 전체"),
        _entry("Tee", "Tee01", "010101", "menu3", "라벨"),
        _entry("Approach", "Approach01", "020101", "menu3", "라벨"),
    ]
    full = select_full_canonical_plan(plan)
    assert [leaf.source_metric_key for leaf in full] == [
        "Approach::Approach01::020101",
        "Sg::Total",
        "Tee::Tee01::010101",
        "Tee::Tee02::010102",
    ]

    # Re-running against the SAME plan (even if the caller passes it
    # in a different order) always produces the identical sequence —
    # required for the B2 checkpoint's resume logic to be meaningful.
    shuffled_plan = [plan[3], plan[1], plan[0], plan[2]]
    full_again = select_full_canonical_plan(shuffled_plan)
    assert [leaf.source_metric_key for leaf in full_again] == [leaf.source_metric_key for leaf in full]


def test_full_canonical_plan_never_invents_a_navigation_rejection_pass():
    """Unlike the raw-taxonomy sampling path, the canonical plan is
    already malformed-free/navigation-free by construction — this
    function must not filter anything further."""
    plan = [_entry("All", "Sg", None, "menu2", "전체기록보기")]
    full = select_full_canonical_plan(plan)
    assert len(full) == 1
    assert full[0].menu1 == "All"
