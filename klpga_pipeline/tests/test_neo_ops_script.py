"""Tests for scripts/neo_ops.py -- the NEO ZERO-TOUCH OPS unified
operator CLI. The real preflight (scripts/final_close_preflight.py) is
already covered by its own dedicated test file; this file only checks
neo_ops.py's own wiring: does it invoke the preflight as a subprocess,
stream+save its output, map the resulting verdict to the right exit
code, notify Discord, trigger the exception-agent only on WARN/
HARD_STOP, and never import anything that could freeze history/
evaluation or touch docs/index.html.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "neo_ops.py"
MODULE_NAME = "neo_ops_script_under_test"
GAME_CODE = "2026080001"


def _load():
    spec = importlib.util.spec_from_file_location(MODULE_NAME, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load()


class FakePopen:
    """Stands in for subprocess.Popen(scripts/final_close_preflight.py ...).

    As a side effect of construction it writes the requested
    --json-out summary (so the real json.loads(...) read-back path in
    neo_ops.py is exercised), and exposes .stdout as an iterable of
    fake preflight output lines plus a no-op .wait().
    """

    def __init__(self, cmd, stdout=None, stderr=None, text=None, bufsize=None, verdict="GO", extra_summary=None):
        self.cmd = cmd
        json_out = None
        for i, arg in enumerate(cmd):
            if arg == "--json-out":
                json_out = Path(cmd[i + 1])
                break
        assert json_out is not None, "neo_ops.py must always pass --json-out to the preflight"

        summary = {"verdict": verdict, "hard_stop_reasons": [], "warn_reasons": []}
        if extra_summary:
            summary.update(extra_summary)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(summary), encoding="utf-8")

        self.stdout = [f"=== FAKE PREFLIGHT OUTPUT ===\n", f"VERDICT: {verdict}\n"]

    def wait(self):
        return 0


def _make_fake_popen_factory(verdict="GO", extra_summary=None):
    def factory(cmd, stdout=None, stderr=None, text=None, bufsize=None):
        return FakePopen(cmd, stdout, stderr, text, bufsize, verdict=verdict, extra_summary=extra_summary)

    return factory


@pytest.mark.parametrize(
    "verdict,expected_exit_code",
    [("GO", 0), ("WARN", 1), ("HARD_STOP", 2), ("SOMETHING_UNEXPECTED", 3)],
)
def test_verdict_maps_to_expected_exit_code(module, tmp_path, verdict, expected_exit_code, capsys):
    with patch(f"{MODULE_NAME}.subprocess.Popen", side_effect=_make_fake_popen_factory(verdict=verdict)):
        with patch(f"{MODULE_NAME}.send_discord_notification", return_value=False) as mock_discord:
            with patch(f"{MODULE_NAME}.trigger_exception_agent", return_value="DISABLED") as mock_agent:
                exit_code = module.run_final_close(
                    db="fake.sqlite", season="2026", game_code=GAME_CODE, expected_final_round="4",
                    finalists="fake_finalists.csv", out_dir=tmp_path,
                )

    assert exit_code == expected_exit_code
    mock_discord.assert_called_once()
    if verdict in ("WARN", "HARD_STOP"):
        mock_agent.assert_called_once()
    else:
        mock_agent.assert_not_called()


def test_latest_txt_and_json_written(module, tmp_path):
    with patch(f"{MODULE_NAME}.subprocess.Popen", side_effect=_make_fake_popen_factory(verdict="GO")):
        with patch(f"{MODULE_NAME}.send_discord_notification", return_value=False):
            module.run_final_close(
                db="fake.sqlite", season="2026", game_code=GAME_CODE, expected_final_round="4",
                finalists="fake_finalists.csv", out_dir=tmp_path,
            )

    txt_path = tmp_path / "latest.txt"
    json_path = tmp_path / "latest.json"
    assert txt_path.exists()
    assert "VERDICT: GO" in txt_path.read_text(encoding="utf-8")
    assert json_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["verdict"] == "GO"


def test_discord_notification_content_includes_verdict_and_reasons(module, tmp_path):
    extra = {"hard_stop_reasons": ["missing canonical snapshot"], "warn_reasons": []}
    with patch(f"{MODULE_NAME}.subprocess.Popen", side_effect=_make_fake_popen_factory(verdict="HARD_STOP", extra_summary=extra)):
        with patch(f"{MODULE_NAME}.send_discord_notification", return_value=True) as mock_discord:
            with patch(f"{MODULE_NAME}.trigger_exception_agent", return_value="NOT_IMPLEMENTED"):
                module.run_final_close(
                    db="fake.sqlite", season="2026", game_code=GAME_CODE, expected_final_round="4",
                    finalists="fake_finalists.csv", out_dir=tmp_path,
                )

    content = mock_discord.call_args[0][0]
    assert GAME_CODE in content
    assert "HARD STOP" in content
    assert "missing canonical snapshot" in content


def test_exception_agent_receives_verdict_and_summary(module, tmp_path):
    with patch(f"{MODULE_NAME}.subprocess.Popen", side_effect=_make_fake_popen_factory(verdict="WARN")):
        with patch(f"{MODULE_NAME}.send_discord_notification", return_value=False):
            with patch(f"{MODULE_NAME}.trigger_exception_agent", return_value="DISABLED") as mock_agent:
                module.run_final_close(
                    db="fake.sqlite", season="2026", game_code=GAME_CODE, expected_final_round="4",
                    finalists="fake_finalists.csv", out_dir=tmp_path,
                )

    args, _ = mock_agent.call_args
    assert args[0] == "WARN"
    assert args[1]["verdict"] == "WARN"


def test_cli_final_close_defaults_and_dispatch(module, tmp_path):
    captured = {}

    def fake_run_final_close(**kwargs):
        captured.update(kwargs)
        return 0

    argv = ["neo_ops.py", "final-close", "--game-code", GAME_CODE, "--season", "2026"]
    with patch(f"{MODULE_NAME}.run_final_close", side_effect=fake_run_final_close):
        with patch("sys.argv", argv):
            rc = module.main()

    assert rc == 0
    assert captured["game_code"] == GAME_CODE
    assert captured["season"] == "2026"
    assert captured["expected_final_round"] == "4"


def test_module_never_imports_history_or_homepage_writers():
    """Mirrors the equivalent guard in
    test_final_close_preflight_script.py -- neo_ops.py only ever
    invokes final_close_preflight.py as a subprocess, so it must never
    itself import anything that could freeze history/evaluation or
    write docs/index.html."""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "write_or_supersede_history_stage", "write_evaluation_atomic",
        "write_prediction_snapshot_atomic", "klpga.neo_win.tournament_history",
        "klpga.neo_win.r3_r4_evaluation_archive", "klpga.site",
        "evaluate_r3_to_r4",
    )
    for forbidden in forbidden_imports:
        assert forbidden not in source, f"{forbidden!r} must never be imported by neo_ops.py"
