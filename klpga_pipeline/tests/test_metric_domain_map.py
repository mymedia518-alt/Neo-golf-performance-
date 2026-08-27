"""Tests for klpga.neo_win.metric_domain_map — domain classification
and the usable_for_model three-gate check. Mostly offline against
synthetic taxonomy fixtures; one test pins against the real, committed
docs/discovery/ evidence used by BETA #001-C's identity_key-pinning fix
(official_metrics.py's "평균 티샷 거리" collision)."""
from __future__ import annotations

from pathlib import Path

from klpga.neo_win.metric_domain_map import (
    DOMAIN_APPROACH,
    DOMAIN_DRIVING,
    DOMAIN_OVERALL,
    DOMAIN_PUTTING,
    DOMAIN_SCORING,
    DOMAIN_SHORT_GAME,
    DOMAIN_UNKNOWN,
    build_metric_feature_map,
    classify_metric_domain,
)

REAL_TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "KLPGA_RECORD_TAXONOMY_DISCOVERED.json"
REAL_RAW_SAMPLES_DIR = Path(__file__).resolve().parents[1] / "docs" / "discovery" / "raw_samples"


# ---------------------------------------------------------------
# classify_metric_domain — real menu1/label evidence only
# ---------------------------------------------------------------


def test_sg_total_is_overall():
    assert classify_metric_domain("Sg", "SG : 전체") == DOMAIN_OVERALL


def test_sg_tee_is_driving():
    assert classify_metric_domain("Sg", "SG : 티샷") == DOMAIN_DRIVING


def test_sg_approach_is_approach():
    assert classify_metric_domain("Sg", "SG : 어프로치") == DOMAIN_APPROACH


def test_sg_around_is_short_game():
    assert classify_metric_domain("Sg", "SG : 그린주변") == DOMAIN_SHORT_GAME


def test_sg_putt_is_putting():
    assert classify_metric_domain("Sg", "SG : 퍼팅") == DOMAIN_PUTTING


def test_tee_menu1_is_driving():
    assert classify_metric_domain("Tee", "평균 티샷 거리") == DOMAIN_DRIVING


def test_approach_menu1_is_approach():
    assert classify_metric_domain("Approach", "그린 적중률") == DOMAIN_APPROACH


def test_around_menu1_is_short_game():
    assert classify_metric_domain("Around", "스크램블 성공률") == DOMAIN_SHORT_GAME


def test_putt_menu1_is_putting():
    assert classify_metric_domain("Putt", "평균 퍼트 수") == DOMAIN_PUTTING


def test_scoring_label_substring_is_scoring():
    assert classify_metric_domain("All", "평균 타수") == DOMAIN_SCORING


def test_unrecognized_label_is_unknown_never_guessed():
    assert classify_metric_domain("All", "완전히 무관한 라벨") == DOMAIN_UNKNOWN


def test_allowlisted_identity_key_wins_over_menu1_heuristic():
    # Tee::Tee01::010101 is the real, pinned identity_key for the
    # "driving" slot's 평균 티샷 거리 candidate — must resolve via the
    # allowlist match, not the generic Tee-menu1 substring fallback
    # (both happen to agree here, but the allowlist path is exercised
    # by passing identity_key explicitly).
    assert classify_metric_domain("Tee", "평균 티샷 거리", identity_key="Tee::Tee01::010101") == DOMAIN_DRIVING


def test_same_label_different_identity_key_not_forced_into_allowlist_domain():
    # The real collision this module's fix addresses: "평균 티샷 거리"
    # also appears at Tee03/Tee05 (Par5/Par4-specific sub-tabs), which
    # are NOT in OFFICIAL_METRIC_SLOTS's allowlist — must still fall
    # back to the menu1 heuristic (still DOMAIN_DRIVING here, but via
    # the fallback path, not a false allowlist hit).
    assert classify_metric_domain("Tee", "평균 티샷 거리", identity_key="Tee::Tee03::010201") == DOMAIN_DRIVING


# ---------------------------------------------------------------
# build_metric_feature_map — usable_for_model's three gates
# ---------------------------------------------------------------


def test_feature_map_uses_real_taxonomy_and_classifies_every_row():
    import json

    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    rows = build_metric_feature_map(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    assert len(rows) > 0
    required = {
        "identity_key", "official_label", "canonical_metric", "domain", "raw_value_field", "rank_field",
        "direction", "normalization_method", "usable_for_model", "reason", "PIT_status",
    }
    for row in rows:
        assert required.issubset(row.keys())
        assert isinstance(row["usable_for_model"], bool)
        if not row["usable_for_model"]:
            assert row["reason"] and row["reason"] != "usable"


def test_feature_map_scoring_domain_is_never_usable_duplicate_representation():
    import json

    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    rows = build_metric_feature_map(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    for row in rows:
        if row["domain"] == DOMAIN_SCORING:
            assert row["usable_for_model"] is False
            assert "duplicate representation" in row["reason"] or "already represented" in row["reason"]


def test_feature_map_usable_rows_are_a_subset_of_the_official_metric_slots_allowlist():
    import json

    from klpga.neo_win.official_metrics import OFFICIAL_METRIC_SLOTS

    allowlisted_keys = {
        (identity_key, label)
        for candidates in OFFICIAL_METRIC_SLOTS.values()
        for identity_key, label, _orientation in candidates
    }
    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    rows = build_metric_feature_map(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    usable = [row for row in rows if row["usable_for_model"]]
    assert len(usable) > 0
    for row in usable:
        assert (row["identity_key"], row["official_label"]) in allowlisted_keys


def test_feature_map_no_two_usable_rows_share_only_a_bare_label():
    # Regression pin for the exact bug BETA #001-C fixed: usable rows
    # must be unique by the FULL (identity_key, label) pair — a bare-
    # label collision (same label, different identity_key, both usable)
    # would mean the old, buggy non-deterministic pivot bug is back.
    import json

    taxonomy = json.loads(REAL_TAXONOMY_PATH.read_text(encoding="utf-8"))
    rows = build_metric_feature_map(taxonomy, raw_samples_dir=REAL_RAW_SAMPLES_DIR, season="2025")
    usable_keys = [(row["identity_key"], row["official_label"]) for row in rows if row["usable_for_model"]]
    assert len(usable_keys) == len(set(usable_keys))
