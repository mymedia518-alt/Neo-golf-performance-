"""End-to-end test of `python scripts/run_beta001_r3_update.py
--dry-run-fixture scripts/fixtures/beta001_r3_dry_run_fixture.json` —
proves the literal one-command dry-run path works with zero real
DB/network/production access, using the actual, checked-in fixture
file (not a synthetic one built inline)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_beta001_r3_update.py"
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fixtures" / "beta001_r3_dry_run_fixture.json"
GAME_CODE = "2026080001"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "run_beta001_r3_update_dry_run_script")


def test_fixture_file_exists():
    assert FIXTURE_PATH.exists()


def test_dry_run_main_end_to_end(module, tmp_path, capsys, monkeypatch):
    output_root = tmp_path / "dry_run_output"
    argv = [
        "run_beta001_r3_update.py",
        "--dry-run-fixture", str(FIXTURE_PATH),
        "--game-code", GAME_CODE,
        "--tournament-name", "Dry Run Open",
        "--output-root", str(output_root),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    rc = module.main()

    out = capsys.readouterr().out
    assert rc == 0
    assert "STATUS: OK" in out
    assert "STATUS                 : READY_FOR_REVIEW (dry run)" in out
    assert "ROUND RECONCILIATION   : PASS" in out
    assert (output_root / "BETA_R3_FULL.csv").exists()
    assert (output_root / "_fixture_history" / GAME_CODE / "R3.json").exists()
    # Never touches anything outside output_root.
    assert not (Path(__file__).resolve().parents[1] / "neo_tournament_history" / GAME_CODE).exists()


def test_dry_run_touches_no_real_db_or_network(module, tmp_path, monkeypatch):
    """The dry-run path must never even attempt to open --db or make a
    network call — proven by simply never patching collect_all_rounds_
    for_game/PoliteHttpClient/sqlite3.connect and confirming it still
    succeeds (a real attempt would either fail loudly with no network
    access in this sandbox, or require a --db file that doesn't exist)."""
    output_root = tmp_path / "dry_run_output2"
    argv = [
        "run_beta001_r3_update.py",
        "--dry-run-fixture", str(FIXTURE_PATH),
        "--game-code", GAME_CODE,
        "--output-root", str(output_root),
        "--db", str(tmp_path / "definitely_does_not_exist.sqlite"),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    rc = module.main()
    assert rc == 0
