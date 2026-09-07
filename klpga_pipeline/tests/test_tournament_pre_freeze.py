"""Tests for scripts/112_build_tournament_pre_freeze.py -- NEO SITE V5
Mission 3 (TOURNAMENT_PRE_FREEZE.json)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "build_tournament_pre_freeze", ROOT / "scripts" / "112_build_tournament_pre_freeze.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)  # type: ignore[union-attr]

REQUIRED_TOP_LEVEL_FIELDS = {
    "game_code", "tournament_name", "field", "player_ids", "entry_source",
    "entry_source_timestamp", "k_rank_snapshot", "neo_input_snapshot",
    "model_version", "generated_at", "freeze_timestamp", "source_provenance",
    "validation_status", "artifact_hash",
}


def test_all_mission_required_fields_present():
    doc = mod.build()
    assert REQUIRED_TOP_LEVEL_FIELDS <= set(doc)


def test_field_identity_match_is_clean_for_the_real_ok_open_entry_list():
    doc = mod.build()
    assert doc["identity_match_summary"]["entrants_total"] == 120
    assert doc["identity_match_summary"]["unmatched"] == 0
    assert doc["validation_status"] == "FIELD_IDENTITY_CLEAN"
    assert doc["unmatched_field"] == []


def test_player_ids_are_sorted_and_match_field_length():
    doc = mod.build()
    assert doc["player_ids"] == sorted(doc["player_ids"], key=int)
    assert len(doc["player_ids"]) == len(doc["field"])


def test_hash_is_deterministic_across_reruns_of_identical_inputs():
    first = mod.build()
    second = mod.build()
    assert first["artifact_hash"] == second["artifact_hash"]


def test_hash_excludes_generated_at_but_covers_the_field():
    doc = mod.build()
    tampered = dict(doc)
    tampered["generated_at"] = "2099-01-01T00:00:00Z"
    hash_payload = {k: v for k, v in tampered.items() if k not in ("generated_at", "artifact_hash")}
    import hashlib
    recomputed = hashlib.sha256(
        json.dumps(hash_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert recomputed == doc["artifact_hash"]


def test_never_marked_retrospective_when_only_pre_sources_are_read():
    doc = mod.build()
    assert doc["is_retrospective_research"] is False


def test_never_reads_any_result_stage_artifact():
    import inspect
    source = inspect.getsource(mod)
    for forbidden in ("R1_LIVE_SNAPSHOT", "R1_FINAL", "FINAL_", "_RESULT", "post_r"):
        assert forbidden not in source, f"PRE freeze builder must never reference a result artifact: {forbidden}"


def test_k_rank_snapshot_scoped_to_the_frozen_field_only():
    doc = mod.build()
    field_ids = set(doc["player_ids"])
    for rec in doc["k_rank_snapshot"]["records"]:
        assert rec["player_id"] in field_ids


def test_neo_input_snapshot_carries_future_data_excluded_true():
    doc = mod.build()
    assert doc["neo_input_snapshot"]["future_data_excluded"] is True


def test_artifact_sha256_fields_are_real_hashes_of_real_files():
    doc = mod.build()
    assert len(doc["entry_source"]["artifact_sha256"]) == 64
    assert len(doc["k_rank_snapshot"]["artifact_sha256"]) == 64
    assert len(doc["neo_input_snapshot"]["artifact_sha256"]) == 64


def test_freeze_timestamp_matches_the_neo_input_cutoff():
    doc = mod.build()
    assert doc["freeze_timestamp"] == doc["neo_input_snapshot"]["cutoff"]
