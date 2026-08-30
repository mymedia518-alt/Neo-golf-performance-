"""Tests for scripts/04_collect_single_tournament.py's CLI-level
wiring of --force-refresh-round / --expected-final-round through to
klpga.collectors.single_tournament.collect_and_persist_tournament, and
the new HARD-STOP printing path when the discovered round falls short.

collect_and_persist_tournament itself is monkeypatched here (its own
behavior is covered by tests/test_single_tournament_collector.py) --
this file only checks the CLI's argument parsing, exit codes, and that
a HARD STOP never prints the "collected successfully" line.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from klpga.collectors.single_tournament import (
    STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND,
    STATUS_SUCCESS,
    SingleTournamentCollectionResult,
)
from klpga.collectors.tournaments import TournamentListing
from datetime import date

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "04_collect_single_tournament.py"
MODULE_NAME = "collect_single_tournament_script_under_test"
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


def _listing():
    return TournamentListing(
        game_code=GAME_CODE, game_title="Test Open", game_eng_title=None, tour_type="RE",
        course_text=None, course_eng_text=None, out_course_text=None, in_course_text=None,
        start_date=date(2026, 8, 27), start_date_raw="20260827", end_date=date(2026, 8, 30), end_date_raw="20260830",
        game_finish="F", prize_money=None, winner_code="p1", winner_name="Player One", game_method="0",
        season=2026, raw={"gameCode": GAME_CODE},
    )


def _success_result(final_round=3):
    return SingleTournamentCollectionResult(
        status=STATUS_SUCCESS, game_code=GAME_CODE, match=_listing(),
        rounds_data={n: [] for n in range(1, final_round + 1)}, final_round=final_round,
        player_rows=[], player_event_rows=[], player_round_rows=[], winner_score="279",
    )


def _hard_stop_result():
    return SingleTournamentCollectionResult(
        status=STATUS_HARD_STOP_BELOW_EXPECTED_FINAL_ROUND, game_code=GAME_CODE, match=_listing(),
        rounds_data={1: [], 2: [], 3: []}, final_round=3, expected_final_round=4,
        player_rows=[{"player_id": "p1"}], player_event_rows=[], player_round_rows=[],
        reason="discovered final_round=3 < expected_final_round=4",
    )


def test_force_refresh_round_flag_passed_through(module, tmp_path, capsys):
    db_path = tmp_path / "test.sqlite"
    db_path.write_text("")  # existence check only -- collect_and_persist_tournament is mocked

    with patch("sys.argv", [
        "04_collect_single_tournament.py", "--season", "2026", "--game-code", GAME_CODE,
        "--db", str(db_path), "--force-refresh-round", "4",
    ]):
        with patch(f"{MODULE_NAME}.collect_and_persist_tournament", return_value=_success_result()) as fake:
            with patch(f"{MODULE_NAME}.fetch_round_leaderboard_html", return_value="<html></html>"):
                rc = module.main()

    assert rc == 0
    assert fake.call_args.kwargs["force_refresh_rounds"] == frozenset({4})
    assert "collected successfully" in capsys.readouterr().out


def test_expected_final_round_hard_stop_never_prints_success(module, tmp_path, capsys):
    db_path = tmp_path / "test.sqlite"
    db_path.write_text("")

    with patch("sys.argv", [
        "04_collect_single_tournament.py", "--season", "2026", "--game-code", GAME_CODE,
        "--db", str(db_path), "--expected-final-round", "4",
    ]):
        with patch(f"{MODULE_NAME}.collect_and_persist_tournament", return_value=_hard_stop_result()):
            rc = module.main()

    out = capsys.readouterr().out
    assert rc == 6
    assert "collected successfully" not in out
    assert "HARD STOP" in out
    assert "HARD_STOP_BELOW_EXPECTED_FINAL_ROUND" in out


def test_db_and_cache_dir_defaults_honor_neo_data_root(module, monkeypatch, tmp_path):
    external_root = tmp_path / "external_data_root"
    db_path = external_root / "klpga.sqlite"
    external_root.mkdir()
    db_path.write_text("")
    monkeypatch.setenv("NEO_DATA_ROOT", str(external_root))

    with patch("sys.argv", ["04_collect_single_tournament.py", "--season", "2026", "--game-code", GAME_CODE]):
        with patch(f"{MODULE_NAME}.collect_and_persist_tournament", return_value=_success_result()) as fake:
            with patch(f"{MODULE_NAME}.fetch_round_leaderboard_html", return_value="<html></html>"):
                rc = module.main()

    # rc == 0 (rather than the "DB does not exist" exit 2 the script prints when a --db
    # default resolves to the wrong path) is itself proof --db picked up the external
    # NEO_DATA_ROOT db_path.write_text("") above, not the (nonexistent) repo-local default.
    assert rc == 0
    fake.assert_called_once()


def test_db_and_cache_dir_defaults_legacy_repo_local_when_unset(module, monkeypatch):
    monkeypatch.delenv("NEO_DATA_ROOT", raising=False)
    import argparse

    captured = {}
    real_add_argument = argparse.ArgumentParser.add_argument

    def spy_add_argument(self, *a, **kw):
        if a and a[0] in ("--db", "--cache-dir"):
            captured[a[0]] = kw.get("default")
        return real_add_argument(self, *a, **kw)

    with patch.object(argparse.ArgumentParser, "add_argument", spy_add_argument):
        with patch("sys.argv", ["04_collect_single_tournament.py", "--season", "2026", "--game-code", GAME_CODE]):
            with patch(f"{MODULE_NAME}.collect_and_persist_tournament", return_value=_success_result()):
                with patch(f"{MODULE_NAME}.fetch_round_leaderboard_html", return_value="<html></html>"):
                    module.main()

    assert captured["--db"] == str(module.ROOT / "data" / "klpga.sqlite")
    assert captured["--cache-dir"] == str(module.ROOT / "data" / "raw_cache" / "http")


def test_legacy_no_new_flags_still_reports_success(module, tmp_path, capsys):
    db_path = tmp_path / "test.sqlite"
    db_path.write_text("")

    with patch("sys.argv", [
        "04_collect_single_tournament.py", "--season", "2026", "--game-code", GAME_CODE, "--db", str(db_path),
    ]):
        with patch(f"{MODULE_NAME}.collect_and_persist_tournament", return_value=_success_result()) as fake:
            with patch(f"{MODULE_NAME}.fetch_round_leaderboard_html", return_value="<html></html>"):
                rc = module.main()

    assert rc == 0
    assert fake.call_args.kwargs["force_refresh_rounds"] == frozenset()
    assert fake.call_args.kwargs["expected_final_round"] is None
    assert "collected successfully" in capsys.readouterr().out
