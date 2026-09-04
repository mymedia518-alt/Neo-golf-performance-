from __future__ import annotations

import json

import pytest

from klpga.neo_win import r1_snapshot_store as store


@pytest.fixture(autouse=True)
def _isolated_snapshot_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "SNAPSHOT_DIR", tmp_path / "r1_snapshots")
    yield


def test_save_snapshot_immutable_writes_a_readable_file():
    path = store.save_snapshot_immutable("GAME1", "R1_1000", {"collected_at": "2026-09-04T01:00:00Z", "round": 1})
    assert path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["kind"] == "R1_1000"
    assert data["game_code"] == "GAME1"
    assert data["round"] == 1


def test_save_snapshot_immutable_refuses_to_overwrite_an_existing_snapshot():
    store.save_snapshot_immutable("GAME1", "R1_1000", {"collected_at": "t1"})
    with pytest.raises(FileExistsError):
        store.save_snapshot_immutable("GAME1", "R1_1000", {"collected_at": "t2 -- must never replace t1"})
    # the original is untouched
    data = json.loads(store.snapshot_path("GAME1", "R1_1000").read_text(encoding="utf-8"))
    assert data["collected_at"] == "t1"


def test_save_snapshot_immutable_allows_different_kinds_for_the_same_game():
    store.save_snapshot_immutable("GAME1", "R1_1000", {"collected_at": "t1"})
    store.save_snapshot_immutable("GAME1", "R1_1030", {"collected_at": "t2"})
    assert len(store.list_snapshots("GAME1")) == 2


def test_leaderboard_state_signature_is_order_independent():
    a = [{"player_id": "1", "total_under_par": -2, "holes_completed": "9", "status": "ACTIVE"}, {"player_id": "2", "total_under_par": 1, "holes_completed": "18", "status": "ACTIVE"}]
    b = list(reversed(a))
    assert store.leaderboard_state_signature(a) == store.leaderboard_state_signature(b)


def test_leaderboard_state_signature_changes_when_a_real_value_changes():
    a = [{"player_id": "1", "total_under_par": -2, "holes_completed": "9", "status": "ACTIVE"}]
    b = [{"player_id": "1", "total_under_par": -2, "holes_completed": "10", "status": "ACTIVE"}]
    assert store.leaderboard_state_signature(a) != store.leaderboard_state_signature(b)


def test_latest_snapshot_picks_the_most_recent_by_collected_at_not_filename_order():
    store.save_snapshot_immutable("GAME1", "R1_0900", {"collected_at": "2026-09-04T03:00:00Z"})
    store.save_snapshot_immutable("GAME1", "R1_0830", {"collected_at": "2026-09-04T05:00:00Z"})  # filename sorts earlier, timestamp is later
    latest = store.latest_snapshot("GAME1")
    assert latest["collected_at"] == "2026-09-04T05:00:00Z"


def test_latest_snapshot_returns_none_when_nothing_saved():
    assert store.latest_snapshot("GAME_NOTHING") is None
