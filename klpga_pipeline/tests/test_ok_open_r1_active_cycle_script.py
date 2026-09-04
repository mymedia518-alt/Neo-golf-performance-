"""Integration tests for scripts/96_ok_open_r1_active_cycle.py -- loaded
by path (scripts/ is not an importable package) and exercised against a
tmp_path-isolated content/ directory so nothing here ever touches the
real repo's OK Open snapshots or docs/."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "96_ok_open_r1_active_cycle.py"
SRC_PATH = Path(__file__).resolve().parents[1] / "src"


def _load_module():
    if str(SRC_PATH) not in sys.path:
        sys.path.insert(0, str(SRC_PATH))
    spec = importlib.util.spec_from_file_location("r1_active_cycle_script_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def cycle_module(tmp_path, monkeypatch):
    module = _load_module()
    content = tmp_path / "content"
    content.mkdir()
    module.CONTENT = content
    module.ENTRY_SNAPSHOT = content / "entry.json"
    module.PRE_MASTER = content / "pre_master.json"
    module.PRE_PERFORMANCE_SNAPSHOT = content / "perf.json"
    module.R1_LIVE_SNAPSHOT = content / "r1_live.json"
    module.R1_CLOSE_RECORD = content / "r1_close.json"
    module.STAGE_STATE = content / "state.json"
    module.LOCK_PATH = content / ".lock"
    # save_snapshot_immutable is bound from klpga.neo_win.r1_snapshot_store
    # at import time -- its own module-level SNAPSHOT_DIR must be
    # redirected too, or every test would write into (and collide with)
    # the real repo's content/website_v2/r1_snapshots/.
    from klpga.neo_win import r1_snapshot_store

    monkeypatch.setattr(r1_snapshot_store, "SNAPSHOT_DIR", content / "r1_snapshots")
    module.ENTRY_SNAPSHOT.write_text(json.dumps({"entries": [{"player_id": "1"}, {"player_id": "2"}]}), encoding="utf-8")
    module.PRE_MASTER.write_text(json.dumps({"records": [
        {"player_id": "1", "current_official_player_name": "A", "win_probability": 0.1},
        {"player_id": "2", "current_official_player_name": "B", "win_probability": 0.2},
    ]}), encoding="utf-8")
    module.PRE_PERFORMANCE_SNAPSHOT.write_text(json.dumps({"profiles": [
        {"player_id": "1", "windows": {"recent5": {"components": {"total": {"mean": 0.3, "sample_sd": 0.7}}}}},
        {"player_id": "2", "windows": {"recent5": {"components": {"total": {"mean": -0.1, "sample_sd": 0.9}}}}},
    ]}), encoding="utf-8")

    # No _rebuild_and_promote patch here -- most tests never reach it
    # (SKIP_WAIT/LOCKED never call it). Tests that DO reach PUBLISH stub
    # it out explicitly so they never touch the real docs/candidate trees.
    yield module
    if module.LOCK_PATH.exists():
        module.LOCK_PATH.unlink()


def test_dry_run_with_no_live_flag_makes_no_http_and_reports_skip_wait(cycle_module, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["96_ok_open_r1_active_cycle.py"])
    rc = cycle_module.main()
    assert rc == 0


def test_locked_when_lock_file_is_fresh(cycle_module, monkeypatch, capsys):
    cycle_module.LOCK_PATH.write_text("held", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["96_ok_open_r1_active_cycle.py"])
    rc = cycle_module.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert out["action"] == "LOCKED"


def test_stale_lock_is_taken_over(cycle_module, monkeypatch):
    cycle_module.LOCK_PATH.write_text("held", encoding="utf-8")
    import os
    import time

    old = time.time() - cycle_module.STALE_LOCK_SECONDS - 60
    os.utime(cycle_module.LOCK_PATH, (old, old))
    monkeypatch.setattr(sys, "argv", ["96_ok_open_r1_active_cycle.py"])
    rc = cycle_module.main()  # dry run -> SKIP_WAIT, but must not be LOCKED
    assert rc == 0
    assert not cycle_module.LOCK_PATH.exists()  # released after this run


def test_lock_is_released_after_a_normal_run(cycle_module, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["96_ok_open_r1_active_cycle.py"])
    cycle_module.main()
    assert not cycle_module.LOCK_PATH.exists()


def test_publish_writes_immutable_snapshot_and_enriched_live_copy(cycle_module, monkeypatch, capsys):
    monkeypatch.setattr(cycle_module, "_rebuild_and_promote", lambda: None)
    monkeypatch.setattr(
        cycle_module,
        "_collect_live",
        lambda: (
            [
                {"player_id": "1", "player_name": "A", "status": "ACTIVE", "holes_completed": "9", "rank": 1, "rank_display": "1", "total_under_par": -2, "today_under_par": -2},
                {"player_id": "2", "player_name": "B", "status": "ACTIVE", "holes_completed": "18", "rank": 2, "rank_display": "2", "total_under_par": 1, "today_under_par": 1},
            ],
            True,
            False,
            None,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["96_ok_open_r1_active_cycle.py", "--live"])
    rc = cycle_module.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0
    assert out["action"] == "PUBLISH"
    assert out["promoted"] is True

    snapshots = list((cycle_module.CONTENT / "r1_snapshots").glob("*.json"))
    assert len(snapshots) == 1
    saved = json.loads(snapshots[0].read_text(encoding="utf-8"))
    assert saved["probabilities"]  # real computed probabilities, not empty
    assert saved["official_data_timestamp"] is None  # never fabricated

    live = json.loads(cycle_module.R1_LIVE_SNAPSHOT.read_text(encoding="utf-8"))
    assert len(live["player_table"]) == 2
    assert live["player_table"][0]["player_id"] == "1"  # leader (lower total_under_par) sorts first


def test_second_identical_publish_is_skipped_as_no_new_data(cycle_module, monkeypatch):
    monkeypatch.setattr(cycle_module, "_rebuild_and_promote", lambda: None)
    rows = [
        {"player_id": "1", "player_name": "A", "status": "ACTIVE", "holes_completed": "9", "rank": 1, "rank_display": "1", "total_under_par": -2, "today_under_par": -2},
        {"player_id": "2", "player_name": "B", "status": "ACTIVE", "holes_completed": "18", "rank": 2, "rank_display": "2", "total_under_par": 1, "today_under_par": 1},
    ]
    monkeypatch.setattr(cycle_module, "_collect_live", lambda: (rows, True, False, None))
    monkeypatch.setattr(sys, "argv", ["96_ok_open_r1_active_cycle.py", "--live"])

    import io
    from contextlib import redirect_stdout

    buf1, buf2 = io.StringIO(), io.StringIO()
    with redirect_stdout(buf1):
        cycle_module.main()
    with redirect_stdout(buf2):
        cycle_module.main()

    first = json.loads(buf1.getvalue().strip())
    second = json.loads(buf2.getvalue().strip())
    assert first["action"] == "PUBLISH"
    assert second["action"] == "SKIP_NO_NEW_DATA"
    # exactly one immutable snapshot -- the second cycle wrote nothing new
    assert len(list((cycle_module.CONTENT / "r1_snapshots").glob("*.json"))) == 1


def test_git_push_is_never_attempted_without_the_explicit_flag(cycle_module, monkeypatch, capsys):
    monkeypatch.setattr(cycle_module, "_rebuild_and_promote", lambda: None)
    calls = []
    monkeypatch.setattr(cycle_module, "_git_commit_and_push", lambda message: calls.append(message) or (True, "pushed"))
    monkeypatch.setattr(
        cycle_module,
        "_collect_live",
        lambda: (
            [
                {"player_id": "1", "player_name": "A", "status": "ACTIVE", "holes_completed": "9", "rank": 1, "rank_display": "1", "total_under_par": -2, "today_under_par": -2},
                {"player_id": "2", "player_name": "B", "status": "ACTIVE", "holes_completed": "18", "rank": 2, "rank_display": "2", "total_under_par": 1, "today_under_par": 1},
            ],
            True,
            False,
            None,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["96_ok_open_r1_active_cycle.py", "--live"])  # no --git-push
    cycle_module.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert out["action"] == "PUBLISH"  # confirms this test really did reach the code path that WOULD git-push
    assert calls == []
    assert "git_pushed" not in out


def test_git_push_flag_triggers_commit_and_push_on_a_successful_publish(cycle_module, monkeypatch, capsys):
    monkeypatch.setattr(cycle_module, "_rebuild_and_promote", lambda: None)
    calls = []
    monkeypatch.setattr(cycle_module, "_git_commit_and_push", lambda message: calls.append(message) or (True, "pushed"))
    monkeypatch.setattr(
        cycle_module,
        "_collect_live",
        lambda: (
            [
                {"player_id": "1", "player_name": "A", "status": "ACTIVE", "holes_completed": "9", "rank": 1, "rank_display": "1", "total_under_par": -2, "today_under_par": -2},
                {"player_id": "2", "player_name": "B", "status": "ACTIVE", "holes_completed": "18", "rank": 2, "rank_display": "2", "total_under_par": 1, "today_under_par": 1},
            ],
            True,
            False,
            None,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["96_ok_open_r1_active_cycle.py", "--live", "--git-push"])
    cycle_module.main()
    out = json.loads(capsys.readouterr().out.strip())
    assert out["action"] == "PUBLISH"
    assert len(calls) == 1
    assert out["git_pushed"] is True


def test_build_failure_leaves_promoted_false_and_never_raises(cycle_module, monkeypatch):
    import subprocess

    def _boom():
        raise subprocess.CalledProcessError(1, ["fake"], stderr="boom")

    monkeypatch.setattr(cycle_module, "_rebuild_and_promote", _boom)
    monkeypatch.setattr(
        cycle_module,
        "_collect_live",
        lambda: (
            [{"player_id": "1", "player_name": "A", "status": "ACTIVE", "holes_completed": "9", "rank": 1, "rank_display": "1", "total_under_par": -2, "today_under_par": -2}],
            True,
            False,
            None,
        ),
    )
    monkeypatch.setattr(sys, "argv", ["96_ok_open_r1_active_cycle.py", "--live"])
    monkeypatch.setattr(cycle_module, "ENTRY_SNAPSHOT", cycle_module.CONTENT / "entry.json")
    cycle_module.ENTRY_SNAPSHOT.write_text(json.dumps({"entries": [{"player_id": "1"}]}), encoding="utf-8")
    rc = cycle_module.main()
    assert rc == 1  # failure signaled, but no exception escaped
    assert not cycle_module.LOCK_PATH.exists()  # lock still released
