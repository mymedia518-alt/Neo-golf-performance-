"""Tests for scripts/110_build_active_tour_player_master.py -- the
ACTIVE_KLPGA_TOUR_PLAYER_MASTER builder (NEO SITE V5 Mission 2, v2
architecture correction).

Core contract under test: current-season regular-tour PLAYING-RIGHT
status is never proxied by KLPGA '정회원' membership status, never
K-Rank truncated, never defaulted without real evidence; every candidate
is classified explicitly into ACTIVE_CONFIRMED / INACTIVE_CONFIRMED /
PENDING_EVIDENCE with provenance; the 546-player historical master stays
completely untouched.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "build_active_tour_player_master", ROOT / "scripts" / "110_build_active_tour_player_master.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore[union-attr]

CONTENT = ROOT / "content" / "website_v2"
OUT = CONTENT / "ACTIVE_KLPGA_TOUR_PLAYER_MASTER.json"


def _doc() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def test_home_regular_tour_master_is_untouched_by_this_build():
    before = (CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json").read_bytes()
    mod.build(attempt_live_fetch=False)
    after = (CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json").read_bytes()
    assert before == after


def test_membership_status_alone_is_never_the_classification_signal():
    """The v1-era bug: '정회원' membership status used as an active-tour
    proxy. Assert the source no longer classifies on tour_status alone --
    the only positive signal is the entry-list formal-qualification
    evidence."""
    import inspect
    source = inspect.getsource(mod)
    assert "ACTIVE_REGULAR_TOUR_STATUS_VALUES" not in source
    classify_source = inspect.getsource(mod._classify)
    assert "정회원" not in classify_source


def test_every_active_player_has_real_entry_list_qualification_evidence():
    doc = mod.build(attempt_live_fetch=False)
    assert doc["active_players"], "expected real, confirmed active players from collected evidence"
    for player in doc["active_players"]:
        src = player["tour_status_source"]
        assert src["qualification_category"] == mod.FORMAL_QUALIFICATION_CATEGORY
        assert src["qualification_reason"]  # non-empty real KLPGA category label
        assert src["official_source"]
        assert src["retrieved_at"]


def test_discretionary_entry_category_alone_is_not_active_evidence():
    """A player entered only via '추천자'/'초청자' (discretionary,
    tournament-specific invite) with no disclosed season-seed reason must
    NOT be classified ACTIVE_CONFIRMED."""
    doc = mod.build(attempt_live_fetch=False)
    active_ids = {p["player_id"] for p in doc["active_players"]}
    for p in doc["pending_players"]:
        if p.get("reason") == "discretionary_entry_no_season_seed_evidence":
            assert p["player_id"] not in active_ids
            assert p.get("qualification_category") in ("추천자", "초청자")


def test_non_regular_membership_track_without_conflict_is_inactive_confirmed():
    doc = mod.build(attempt_live_fetch=False)
    assert doc["inactive_players"], "expected the real 실기평가 대상자 cases"
    for player in doc["inactive_players"]:
        assert player["profile_membership_track"] in mod.NON_REGULAR_TOUR_MEMBERSHIP_TRACKS
        assert player["reason"] == "non_regular_tour_membership_track"


def test_conflicting_evidence_is_never_silently_resolved():
    """Two real candidates carry BOTH a non-regular membership track AND
    a genuine entry-list season-seed qualification reason. Neither
    evidence source may be silently preferred -- both must land in
    PENDING_EVIDENCE with the conflict spelled out."""
    doc = mod.build(attempt_live_fetch=False)
    conflicts = [p for p in doc["pending_players"] if p.get("reason") == "conflicting_evidence"]
    assert conflicts, "expected the real I-Tour/season-seed conflict cases in the collected data"
    active_ids = {p["player_id"] for p in doc["active_players"]}
    inactive_ids = {p["player_id"] for p in doc["inactive_players"]}
    for c in conflicts:
        assert c["player_id"] not in active_ids
        assert c["player_id"] not in inactive_ids
        eq = c["conflict_evidence"]
        assert eq["profile_membership_track"] in mod.NON_REGULAR_TOUR_MEMBERSHIP_TRACKS
        assert eq["entry_qualification_category"] == mod.FORMAL_QUALIFICATION_CATEGORY
        assert eq["entry_qualification_reason"]


def test_every_candidate_is_classified_into_exactly_one_of_three_states():
    doc = mod.build(attempt_live_fetch=False)
    active_ids = {p["player_id"] for p in doc["active_players"]}
    inactive_ids = {p["player_id"] for p in doc["inactive_players"]}
    pending_ids = {p["player_id"] for p in doc["pending_players"]}
    assert active_ids.isdisjoint(inactive_ids)
    assert active_ids.isdisjoint(pending_ids)
    assert inactive_ids.isdisjoint(pending_ids)
    home_master = json.loads((CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json").read_text(encoding="utf-8"))
    assert active_ids | inactive_ids | pending_ids == {
        str(r["player_id"]) for r in home_master["records"]
    }


def test_candidates_with_no_collected_evidence_are_pending_not_guessed():
    doc = mod.build(attempt_live_fetch=False)
    no_evidence = [p for p in doc["pending_players"] if p["reason"] == "no_collected_evidence"]
    assert len(no_evidence) > 0
    assert doc["counts"]["pending_evidence"] >= len(no_evidence)


def test_never_uses_k_rank_as_the_classification_signal():
    import inspect
    source = inspect.getsource(mod._classify)
    assert "k_rank" not in source


def test_long_term_schema_fields_present_on_every_active_record():
    doc = mod.build(attempt_live_fetch=False)
    required = {
        "player_id", "player_name", "official_sponsor", "tour_status",
        "tour_status_source", "k_rank", "neo_rank", "performance_sg",
        "form", "volatility", "trend", "events", "data_as_of",
    }
    for player in doc["active_players"]:
        assert required <= set(player), player


def test_neo_derived_metrics_are_always_null_never_fabricated():
    doc = mod.build(attempt_live_fetch=False)
    for player in doc["active_players"]:
        for field in ("neo_rank", "performance_sg", "form", "volatility", "trend", "events"):
            assert player[field] is None


def test_sponsor_blank_when_unavailable_never_invented():
    doc = mod.build(attempt_live_fetch=False)
    for player in doc["active_players"]:
        assert player["official_sponsor"] is None or isinstance(player["official_sponsor"], str)


def test_counts_are_never_padded_toward_the_scope_target():
    doc = mod.build(attempt_live_fetch=False)
    counts = doc["counts"]
    assert counts["active_confirmed"] != 150
    assert counts["active_confirmed"] + counts["inactive_confirmed"] + counts["pending_evidence"] == counts["candidates_total"]
    assert counts["status"] == "PARTIAL_PENDING_LIVE_KLPGA_NETWORK_ACCESS"


def test_target_scope_note_is_explicitly_not_a_cutoff():
    doc = mod.build(attempt_live_fetch=False)
    assert "150" in doc["target_scope_note"]
    assert "NOT a cutoff" in doc["target_scope_note"] or "not a cutoff" in doc["target_scope_note"].lower()


def test_artifact_hash_is_a_real_sha256_of_the_player_lists():
    doc = mod.build(attempt_live_fetch=False)
    assert len(doc["artifact_hash"]) == 64
    int(doc["artifact_hash"], 16)  # raises if not valid hex


def test_distinct_from_both_the_546_master_and_a_tournament_field():
    doc = mod.build(attempt_live_fetch=False)
    assert "546" in doc["distinct_from"]
    assert "entry list" in doc["distinct_from"] or "field membership" in doc["distinct_from"]
    assert doc["population_kind"] != "regular_tour_historical_player_master"
