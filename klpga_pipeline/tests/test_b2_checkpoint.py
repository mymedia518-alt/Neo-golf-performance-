"""Tests for klpga.discovery.b2_checkpoint — the Phase B2 explicit
resume-state artifact (Round 9 follow-up, B2_GATE=GO round). No
network access."""
from __future__ import annotations

import json

import pytest

from klpga.discovery.b2_checkpoint import (
    COMPLETION_HTTP_FAILURE,
    COMPLETION_SUCCESS,
    CheckpointEntry,
    load_checkpoint,
    mark_http_failure,
    mark_success,
    write_checkpoint_atomic,
)


def test_load_checkpoint_missing_file_returns_empty_dict(tmp_path):
    assert load_checkpoint(tmp_path / "does_not_exist.json") == {}


def test_mark_success_sets_completion_and_is_complete_true():
    entries: dict[str, CheckpointEntry] = {}
    mark_success(
        entries,
        identity_key="Sg::Total",
        request_params={"season": "2025", "menu1": "Sg", "menu2": "Total"},
        season="2025",
        parse_status="CONFIRMED",
        schema_fingerprint="FP1",
        player_row_count=61,
        timestamp="2026-08-26T00:00:00+00:00",
        sample_record={"identity_key": "Sg::Total"},
        log_entry={
            "timestamp": "2026-08-26T00:00:00+00:00",
            "endpoint": "e",
            "method": "POST",
            "season": "2025",
            "menu1": "Sg",
            "menu2": "Total",
            "menu3": None,
            "canonical_identity": "Sg::Total",
            "http_status": 200,
            "response_size": 123,
            "parse_status": "CONFIRMED",
        },
    )
    entry = entries["Sg::Total"]
    assert entry.completion_status == COMPLETION_SUCCESS
    assert entry.is_complete is True
    assert entry.player_row_count == 61
    assert entry.sample_record == {"identity_key": "Sg::Total"}


def test_mark_http_failure_sets_completion_and_is_complete_false():
    entries: dict[str, CheckpointEntry] = {}
    mark_http_failure(
        entries,
        identity_key="Sg::Around",
        request_params={"season": "2025", "menu1": "Sg", "menu2": "Around"},
        season="2025",
        timestamp="2026-08-26T00:00:01+00:00",
    )
    entry = entries["Sg::Around"]
    assert entry.completion_status == COMPLETION_HTTP_FAILURE
    assert entry.is_complete is False
    assert entry.parse_status is None
    assert entry.sample_record is None


def test_write_then_load_round_trips_all_fields(tmp_path):
    path = tmp_path / "checkpoint.json"
    entries: dict[str, CheckpointEntry] = {}
    mark_success(
        entries,
        identity_key="Sg::Total",
        request_params={"season": "2025", "menu1": "Sg", "menu2": "Total"},
        season="2025",
        parse_status="CONFIRMED",
        schema_fingerprint="FP1",
        player_row_count=61,
        timestamp="t1",
        sample_record={"identity_key": "Sg::Total", "player_row_count": 61},
    )
    mark_http_failure(
        entries,
        identity_key="Sg::Around",
        request_params={"season": "2025", "menu1": "Sg", "menu2": "Around"},
        season="2025",
        timestamp="t2",
    )
    write_checkpoint_atomic(path, entries)

    reloaded = load_checkpoint(path)
    assert set(reloaded) == {"Sg::Total", "Sg::Around"}
    assert reloaded["Sg::Total"].is_complete is True
    assert reloaded["Sg::Total"].sample_record == {"identity_key": "Sg::Total", "player_row_count": 61}
    assert reloaded["Sg::Around"].is_complete is False


def test_write_checkpoint_atomic_leaves_no_leftover_temp_file(tmp_path):
    path = tmp_path / "checkpoint.json"
    entries: dict[str, CheckpointEntry] = {}
    mark_success(
        entries,
        identity_key="Sg::Total",
        request_params={},
        season="2025",
        parse_status="CONFIRMED",
        schema_fingerprint="FP1",
        player_row_count=1,
        timestamp="t1",
    )
    write_checkpoint_atomic(path, entries)
    leftovers = [p for p in tmp_path.iterdir() if p.name != path.name]
    assert leftovers == []


def test_checkpoint_write_is_atomic_original_preserved_on_mid_write_failure(tmp_path, monkeypatch):
    """Simulates a crash AFTER the temp file is created but BEFORE the
    atomic os.replace ever runs — the previously-written checkpoint
    must remain byte-for-byte intact, never partially overwritten."""
    path = tmp_path / "checkpoint.json"
    first: dict[str, CheckpointEntry] = {}
    mark_success(
        first,
        identity_key="Sg::Total",
        request_params={},
        season="2025",
        parse_status="CONFIRMED",
        schema_fingerprint="FP1",
        player_row_count=1,
        timestamp="t1",
    )
    write_checkpoint_atomic(path, first)
    original_bytes = path.read_bytes()

    import klpga.discovery.b2_checkpoint as ckpt_module

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated crash mid-write")

    monkeypatch.setattr(ckpt_module.json, "dump", _boom)

    second: dict[str, CheckpointEntry] = {}
    mark_success(
        second,
        identity_key="Sg::Total",
        request_params={},
        season="2025",
        parse_status="CORRUPTED_WOULD_BE_WRONG",
        schema_fingerprint="FP2",
        player_row_count=999,
        timestamp="t2",
    )
    with pytest.raises(RuntimeError):
        write_checkpoint_atomic(path, second)

    assert path.read_bytes() == original_bytes
    reloaded = load_checkpoint(path)
    assert reloaded["Sg::Total"].parse_status == "CONFIRMED"
    assert reloaded["Sg::Total"].player_row_count == 1

    leftover_tmp_files = [p for p in tmp_path.iterdir() if p.name != path.name]
    assert leftover_tmp_files == []


def test_load_checkpoint_raises_on_genuinely_corrupt_file_not_silently_discarded(tmp_path):
    path = tmp_path / "checkpoint.json"
    path.write_text("{not valid json at all", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_checkpoint(path)
