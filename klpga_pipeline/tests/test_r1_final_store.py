from __future__ import annotations

import json

import pytest

from klpga.neo_win import r1_final_store as store
from klpga.neo_win import r1_snapshot_store


@pytest.fixture(autouse=True)
def _isolated_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "RAW_DIR", tmp_path / "raw" / "r1_final")
    monkeypatch.setattr(store, "SNAPSHOT_DIR", tmp_path / "content" / "r1_final_snapshots")
    yield


def test_raw_and_snapshot_dirs_are_never_the_live_collectors_own_dirs():
    # "현재 live snapshot을 수정하지 말고 별도로 저장한다" -- this store
    # must never share a path with the live in-progress collector's own
    # immutable snapshot store.
    assert store.SNAPSHOT_DIR != r1_snapshot_store.SNAPSHOT_DIR
    assert "r1_final" in str(store.RAW_DIR) or "r1_final_snapshots" in str(store.SNAPSHOT_DIR)


def test_save_raw_response_immutable_writes_the_exact_bytes():
    path = store.save_raw_response_immutable("GAME1", "20260905T093000", "<html>raw scoreRecord</html>")
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == "<html>raw scoreRecord</html>"


def test_save_raw_response_immutable_refuses_to_overwrite():
    store.save_raw_response_immutable("GAME1", "K1", "first response")
    with pytest.raises(FileExistsError):
        store.save_raw_response_immutable("GAME1", "K1", "a later response must never replace the first")
    assert store.raw_response_path("GAME1", "K1").read_text(encoding="utf-8") == "first response"


def test_save_snapshot_immutable_writes_a_readable_file():
    path = store.save_snapshot_immutable("GAME1", "K1", {"collected_at": "2026-09-05T00:30:00Z", "rows": []})
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["kind"] == "K1"
    assert data["game_code"] == "GAME1"
    assert data["schema_version"] == store.SNAPSHOT_SCHEMA_VERSION


def test_save_snapshot_immutable_refuses_to_overwrite():
    store.save_snapshot_immutable("GAME1", "K1", {"collected_at": "t1"})
    with pytest.raises(FileExistsError):
        store.save_snapshot_immutable("GAME1", "K1", {"collected_at": "t2 -- must never replace t1"})
    data = json.loads(store.snapshot_path("GAME1", "K1").read_text(encoding="utf-8"))
    assert data["collected_at"] == "t1"


def test_list_snapshots_only_matches_this_game_code():
    store.save_snapshot_immutable("GAME1", "K1", {})
    store.save_snapshot_immutable("GAME2", "K1", {})
    assert len(store.list_snapshots("GAME1")) == 1
