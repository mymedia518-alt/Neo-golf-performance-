"""Tests for scripts/110_build_active_tour_player_master.py -- the
ACTIVE_KLPGA_TOUR_PLAYER_MASTER builder (NEO SITE V5 Mission 2).

Core contract under test: never silently classify a player as active
without real, sourced evidence; never truncate by K-Rank; keep the
546-player historical master completely untouched.
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


def test_every_active_player_has_a_real_profile_source_not_a_guess():
    doc = mod.build(attempt_live_fetch=False)
    assert doc["active_players"], "expected at least the bootstrapped OK Open confirmed players"
    for player in doc["active_players"]:
        assert player["tour_status_source"]["official_source"], player
        assert player["tour_status_source"]["official_source"].startswith(
            "https://klpga.co.kr/web/profile/mainRecord"
        )
        assert player["tour_status_source"]["retrieved_at"]


def test_active_classification_rule_is_the_documented_one():
    doc = mod.build(attempt_live_fetch=False)
    for player in doc["active_players"]:
        assert player["tour_status"] in mod.ACTIVE_REGULAR_TOUR_STATUS_VALUES
    for player in doc["non_regular_excluded"]:
        assert player["tour_status"] not in mod.ACTIVE_REGULAR_TOUR_STATUS_VALUES
        assert "exclusion_reason" in player


def test_non_confirmed_candidates_are_pending_never_defaulted():
    doc = mod.build(attempt_live_fetch=False)
    active_ids = {p["player_id"] for p in doc["active_players"]}
    excluded_ids = {p["player_id"] for p in doc["non_regular_excluded"]}
    pending_ids = {p["player_id"] for p in doc["pending_collection"]}
    assert active_ids.isdisjoint(pending_ids)
    assert excluded_ids.isdisjoint(pending_ids)
    assert active_ids.isdisjoint(excluded_ids)
    home_master = json.loads((CONTENT / "HOME_REGULAR_TOUR_PLAYER_MASTER.json").read_text(encoding="utf-8"))
    assert active_ids | excluded_ids | pending_ids == {
        str(r["player_id"]) for r in home_master["records"]
    }


def test_never_uses_k_rank_as_the_classification_signal():
    import inspect
    source = inspect.getsource(mod)
    # k_rank is a displayed field on the record, never part of the
    # active/excluded/pending decision itself.
    classify_block = source[source.index("if evidence.get(\"tour_status\")"):]
    assert "k_rank" not in classify_block.split("\n")[0]


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
    for player in doc["active_players"] + doc["non_regular_excluded"]:
        assert player["official_sponsor"] is None or isinstance(player["official_sponsor"], str)


def test_collection_completeness_is_honestly_partial_without_network():
    doc = mod.build(attempt_live_fetch=False)
    completeness = doc["collection_completeness"]
    assert completeness["pending_collection"] > 0
    assert completeness["status"] == "PARTIAL_PENDING_LIVE_KLPGA_NETWORK_ACCESS"
    assert (
        completeness["candidates_total"]
        == completeness["profile_checked"] + completeness["pending_collection"]
    )


def test_target_scope_note_documents_the_approximately_150_target():
    doc = mod.build(attempt_live_fetch=False)
    assert "150" in doc["target_scope_note"]


def test_artifact_hash_is_a_real_sha256_of_the_player_lists():
    doc = mod.build(attempt_live_fetch=False)
    assert len(doc["artifact_hash"]) == 64
    int(doc["artifact_hash"], 16)  # raises if not valid hex


def test_distinct_from_the_546_player_historical_master_is_documented():
    doc = mod.build(attempt_live_fetch=False)
    assert "546" in doc["distinct_from"]
    assert doc["population_kind"] != "regular_tour_historical_player_master"
