"""P0 STALE-DATA INCIDENT -- integration tests proving
scripts/94_promote_top120_to_production.py's promotion gate actually
calls into the freshness checks and hard-stops a promotion, exercising
the REAL `_validate_r1_freshness` function (never a re-implementation).
Fully isolated via monkeypatch on the module's own path/function
attributes -- never touches the real (currently stale) production
content/candidate/docs trees."""
import datetime
import json
from pathlib import Path

import importlib.util

import pytest

SPEC = importlib.util.spec_from_file_location(
    "promoter_under_test", Path(__file__).parents[1] / "scripts" / "94_promote_top120_to_production.py"
)
promoter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(promoter)


def _row(name, holes, status=None):
    return {"player_name": name, "holes_completed": holes, "status": status}


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _r1_page(tmp_path: Path, text: str) -> None:
    page = tmp_path / "tournaments" / "2026" / "ok-savings-bank-open" / "r1" / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"<html><body>{text}</body></html>", encoding="utf-8")


def test_not_tournament_active_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(promoter, "home_mode", lambda: "RANKING_DEFAULT")
    # no stage-state/snapshot files created at all -- must not even try to read them
    promoter._validate_r1_freshness(tmp_path, "t")


def test_no_stage_state_file_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "STAGE_STATE_PATH", tmp_path / "missing_state.json")
    monkeypatch.setattr(promoter, "R1_LIVE_SNAPSHOT_PATH", tmp_path / "missing_snapshot.json")
    promoter._validate_r1_freshness(tmp_path, "t")


def test_fresh_snapshot_with_no_marker_passes(tmp_path, monkeypatch):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshot.json"
    _write(state_path, {"stages": {"r1": {"validated": True}}})
    _write(snapshot_path, {"collected_at": now_iso, "player_table": [_row("A", "9")]})
    _r1_page(tmp_path, "in progress, no delay notice needed")
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("r1", "/x/"))
    monkeypatch.setattr(promoter, "STAGE_STATE_PATH", state_path)
    monkeypatch.setattr(promoter, "R1_LIVE_SNAPSHOT_PATH", snapshot_path)
    promoter._validate_r1_freshness(tmp_path, "t")


def test_stale_snapshot_without_notice_hard_stops_promotion(tmp_path, monkeypatch):
    old_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)).isoformat().replace("+00:00", "Z")
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshot.json"
    _write(state_path, {"stages": {"r1": {"validated": True}}})
    _write(snapshot_path, {"collected_at": old_iso, "player_table": [_row("A", "9")]})
    _r1_page(tmp_path, "라이브 업데이트 주기 30분")  # stale but NOT relabeled -- must be caught
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("r1", "/x/"))
    monkeypatch.setattr(promoter, "STAGE_STATE_PATH", state_path)
    monkeypatch.setattr(promoter, "R1_LIVE_SNAPSHOT_PATH", snapshot_path)
    with pytest.raises(promoter.PromotionError):
        promoter._validate_r1_freshness(tmp_path, "t")


def test_stale_snapshot_with_notice_passes(tmp_path, monkeypatch):
    old_iso = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)).isoformat().replace("+00:00", "Z")
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshot.json"
    _write(state_path, {"stages": {"r1": {"validated": True}}})
    _write(snapshot_path, {"collected_at": old_iso, "player_table": [_row("A", "9")]})
    _r1_page(tmp_path, "데이터 수집 지연 중")  # correctly labeled -- must pass
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("r1", "/x/"))
    monkeypatch.setattr(promoter, "STAGE_STATE_PATH", state_path)
    monkeypatch.setattr(promoter, "R1_LIVE_SNAPSHOT_PATH", snapshot_path)
    promoter._validate_r1_freshness(tmp_path, "t")


def test_completed_round_with_incomplete_holes_hard_stops_promotion(tmp_path, monkeypatch):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshot.json"
    _write(state_path, {"stages": {"r1": {"validated": True}}, "r1_complete": True})
    _write(snapshot_path, {"collected_at": now_iso, "player_table": [_row("A", "9"), _row("B", "18")]})
    _r1_page(tmp_path, "no notice needed, fresh")
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("r1", "/x/"))
    monkeypatch.setattr(promoter, "STAGE_STATE_PATH", state_path)
    monkeypatch.setattr(promoter, "R1_LIVE_SNAPSHOT_PATH", snapshot_path)
    with pytest.raises(promoter.PromotionError, match="A"):
        promoter._validate_r1_freshness(tmp_path, "t")


def test_completed_round_with_all_18_holes_passes(tmp_path, monkeypatch):
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    state_path = tmp_path / "state.json"
    snapshot_path = tmp_path / "snapshot.json"
    _write(state_path, {"stages": {"r1": {"validated": True}}, "r1_complete": True})
    _write(snapshot_path, {"collected_at": now_iso, "player_table": [_row("A", "18"), _row("B", "F"), _row("C", "9", "WD")]})
    _r1_page(tmp_path, "no notice needed, fresh")
    monkeypatch.setattr(promoter, "home_mode", lambda: "TOURNAMENT_ACTIVE")
    monkeypatch.setattr(promoter, "ok_open_latest_available_stage", lambda: ("r1", "/x/"))
    monkeypatch.setattr(promoter, "STAGE_STATE_PATH", state_path)
    monkeypatch.setattr(promoter, "R1_LIVE_SNAPSHOT_PATH", snapshot_path)
    promoter._validate_r1_freshness(tmp_path, "t")
