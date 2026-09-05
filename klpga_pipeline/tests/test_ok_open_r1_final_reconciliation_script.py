"""Integration tests for scripts/98_ok_open_r1_final_reconciliation.py
-- loaded by path and exercised against a tmp_path-isolated content/
directory so nothing here ever touches the real repo's OK Open state
or snapshots. _fetch_score_record/_parse_score_record are monkeypatched
directly rather than hitting real network or a real (not yet written)
parser -- see klpga.collectors.score_record."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "98_ok_open_r1_final_reconciliation.py"
SRC_PATH = Path(__file__).resolve().parents[1] / "src"


def _load_module():
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))
    spec = importlib.util.spec_from_file_location("r1_final_reconciliation_script_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def reco_module(tmp_path, monkeypatch):
    module = _load_module()
    content = tmp_path / "content"
    content.mkdir()
    module.ENTRY_SNAPSHOT = content / "entry.json"
    module.STAGE_STATE = content / "state.json"
    module.ENTRY_SNAPSHOT.write_text(json.dumps({"entries": [{"player_id": "1"}, {"player_id": "2"}]}), encoding="utf-8")

    from klpga.neo_win import r1_final_store

    monkeypatch.setattr(r1_final_store, "RAW_DIR", content / "raw_r1_final")
    monkeypatch.setattr(r1_final_store, "SNAPSHOT_DIR", content / "r1_final_snapshots")
    yield module


def test_dry_run_makes_no_fetch_and_touches_nothing(reco_module, monkeypatch, capsys):
    def _boom():
        raise AssertionError("dry run must never call _fetch_score_record")

    monkeypatch.setattr(reco_module, "_fetch_score_record", _boom)
    monkeypatch.setattr(sys, "argv", ["98_ok_open_r1_final_reconciliation.py"])
    rc = reco_module.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert out["action"] == "DRY_RUN"
    assert out["expected_player_count"] == 2
    assert not reco_module.STAGE_STATE.exists()


def test_live_with_malformed_score_record_saves_raw_but_never_touches_stage_state(reco_module, monkeypatch, capsys):
    monkeypatch.setattr(reco_module, "_fetch_score_record", lambda: (200, "<html>real raw scoreRecord response</html>"))
    monkeypatch.setattr(sys, "argv", ["98_ok_open_r1_final_reconciliation.py", "--live"])
    rc = reco_module.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 1
    assert out["action"] == "PARSER_FAILED"
    raw_path = Path(reco_module.__file__).resolve().parents[1] / out["raw_response_path"]
    assert raw_path.read_text(encoding="utf-8") == "<html>real raw scoreRecord response</html>"
    assert not reco_module.STAGE_STATE.exists()


def test_live_reconciliation_pass_sets_r1_complete_and_r2_ready(reco_module, monkeypatch, capsys):
    monkeypatch.setattr(reco_module, "_fetch_score_record", lambda: (200, "<html>raw</html>"))
    monkeypatch.setattr(reco_module, "_parse_score_record", lambda html: [
        {"player_id": "1", "official_status": None, "final_score": -4, "rank_display": "1"},
        {"player_id": "2", "official_status": "WD", "final_score": None, "rank_display": None},
    ])
    monkeypatch.setattr(sys, "argv", ["98_ok_open_r1_final_reconciliation.py", "--live"])
    rc = reco_module.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert out["action"] == "FINAL_RECONCILED"
    assert out["r1_complete"] is True
    assert out["r2_ready"] is True

    state = json.loads(reco_module.STAGE_STATE.read_text(encoding="utf-8"))
    assert state["r1_complete"] is True
    assert state["r2_ready"] is True
    assert state["stages"]["r1"]["final_reconciliation"]["passed"] is True


def test_live_reconciliation_fail_never_touches_r1_complete_or_r2_ready(reco_module, monkeypatch, capsys):
    monkeypatch.setattr(reco_module, "_fetch_score_record", lambda: (200, "<html>raw</html>"))
    monkeypatch.setattr(reco_module, "_parse_score_record", lambda html: [
        {"player_id": "1", "official_status": None, "final_score": None, "rank_display": "1"},  # normal player, missing final score
        {"player_id": "2", "official_status": None, "final_score": 1, "rank_display": "2"},
    ])
    monkeypatch.setattr(sys, "argv", ["98_ok_open_r1_final_reconciliation.py", "--live"])
    rc = reco_module.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 1
    assert out["action"] == "RECONCILIATION_FAILED"
    assert out["reconciliation"]["passed"] is False
    assert not reco_module.STAGE_STATE.exists()


def test_live_reconciliation_fail_preserves_a_prior_pass_never_clears_it(reco_module, monkeypatch, capsys):
    # A later run failing (e.g. re-run against a corrupted response)
    # must never silently revoke a previously PASSED official
    # completion -- this script only ever moves the flags forward on a
    # real PASS, never backward on a later FAIL.
    reco_module.STAGE_STATE.write_text(json.dumps({"stages": {"r1": {}}, "r1_complete": True, "r2_ready": True}), encoding="utf-8")
    monkeypatch.setattr(reco_module, "_fetch_score_record", lambda: (200, "<html>raw</html>"))
    monkeypatch.setattr(reco_module, "_parse_score_record", lambda html: [
        {"player_id": "1", "official_status": None, "final_score": None, "rank_display": "1"},
        {"player_id": "2", "official_status": None, "final_score": 1, "rank_display": "2"},
    ])
    monkeypatch.setattr(sys, "argv", ["98_ok_open_r1_final_reconciliation.py", "--live"])
    rc = reco_module.main()
    assert rc == 1
    state = json.loads(reco_module.STAGE_STATE.read_text(encoding="utf-8"))
    assert state["r1_complete"] is True
    assert state["r2_ready"] is True


def test_incomplete_status_from_a_bad_parser_never_passes_reconciliation(reco_module, monkeypatch, capsys):
    # Guards the "INCOMPLETE를 WD로 추론하지 않는다" requirement
    # end-to-end through the actual script, not just the pure function.
    monkeypatch.setattr(reco_module, "_fetch_score_record", lambda: (200, "<html>raw</html>"))
    monkeypatch.setattr(reco_module, "_parse_score_record", lambda html: [
        {"player_id": "1", "official_status": "INCOMPLETE", "final_score": None, "rank_display": "1"},
        {"player_id": "2", "official_status": None, "final_score": 1, "rank_display": "2"},
    ])
    monkeypatch.setattr(sys, "argv", ["98_ok_open_r1_final_reconciliation.py", "--live"])
    rc = reco_module.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 1
    assert out["reconciliation"]["passed"] is False
    assert "unrecognized" in out["reconciliation"]["reason"]
    assert not reco_module.STAGE_STATE.exists()
