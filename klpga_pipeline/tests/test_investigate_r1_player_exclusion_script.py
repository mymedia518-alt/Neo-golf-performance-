"""Tests for scripts/48_investigate_r1_player_exclusion.py — a narrow,
read-only, single-player deep dive into WHY a player_code with a real
round_number=1 row is absent from the frozen BETA #001-C PRE field.
Reuses klpga.neo_win.r1_provenance (same module scripts/45 uses) —
these tests exercise the NEW entry-list-cache-evidence functions added
there (find_entry_list_cache_file / real_entry_field_codes_from_cached_html)
through the script's own CLI surface.

Player codes here are numeric strings (e.g. "101", "999"), matching
klpga.parsers.entry_list_parser's real, confirmed playerCode=(\\d+)
regex — a non-numeric code would never match a real KLPGA entry-list
page and would silently fall into that parser's own unparsed-row
path, which is not what these tests are exercising."""
from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "48_investigate_r1_player_exclusion.py"
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "src" / "klpga" / "db" / "schema.sql"
GAME_CODE = "EXCLTEST"
CUTOFF_DATE = "2027-01-01"
PLAYERS = ["101", "102", "103", "104", "105"]
UNEXPLAINED_CODE = "999"
PRE_CREATED_AT_UTC = "2027-01-01T00:00:00Z"

_FUTURE_EPOCH = time.mktime(time.strptime("2027-06-01T00:00:00", "%Y-%m-%dT%H:%M:%S"))
_PAST_EPOCH = time.mktime(time.strptime("2020-01-01T00:00:00", "%Y-%m-%dT%H:%M:%S"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load(SCRIPT_PATH, "investigate_r1_player_exclusion_script")


@pytest.fixture()
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) "
        "VALUES (?, ?, 'Live Test Open', 2026, '2027-01-01', '2027-01-04')",
        (GAME_CODE, GAME_CODE),
    )
    for p in PLAYERS:
        conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (p, p))
    conn.commit()
    conn.close()
    return path


def _freeze_pre_c(c_predictions_dir, players=PLAYERS):
    from klpga.neo_win.beta001c_archive import (
        NeoWinCEntrantSnapshot,
        NeoWinCPredictionSnapshot,
        RECORD_KIND as C_RECORD_KIND,
        write_neo_win_c_snapshot_atomic,
    )

    n = len(players)
    entrants = tuple(
        NeoWinCEntrantSnapshot(
            rank=i + 1, player_code=p, player_name=p, win_probability=1.0 / n, prior_events_n=10,
            feature_values={"prior_avg_round_score_to_par": -1.0 - i * 0.2, "neo_consistency_stddev": 2.0},
        )
        for i, p in enumerate(players)
    )
    snapshot = NeoWinCPredictionSnapshot(
        prediction_id="001-C-FINAL", created_at_utc=PRE_CREATED_AT_UTC, record_kind=C_RECORD_KIND,
        game_code=GAME_CODE, tournament_name="Live Test Open", cutoff_date=CUTOFF_DATE,
        cutoff_source="explicit_arg", selected_model_id="MODEL_A",
        model_features=("prior_avg_round_score_to_par", "neo_consistency_stddev"),
        selection_decision={"selected_model_id": "MODEL_A"}, training_tournament_count=8,
        field_size=n, entrants_predicted=n, probability_sum=1.0,
        minimum_probability=1.0 / n, maximum_probability=1.0 / n,
        duplicate_count=0, null_count=0, non_field_count=0, known_limitations=(),
        predictions=entrants,
    )
    write_neo_win_c_snapshot_atomic(snapshot, c_predictions_dir)
    return snapshot


def _entry_list_html(player_codes_and_names):
    rows = "".join(
        f'<tr><td><a class="col-7" href="/x?playerCode={code}">{name}</a></td><td></td></tr>'
        for code, name in player_codes_and_names
    )
    return f"<html><body><h2>전체 선수</h2><table><tbody>{rows}</tbody></table></body></html>"


def _write_entry_list_cache(cache_dir, game_code, player_codes_and_names, *, mtime_epoch=None):
    """Writes the cache file exactly like klpga.http_client.PoliteHttpClient
    does for the real entry-list GET request, then optionally backdates/
    forward-dates its mtime to simulate a specific real-fetch time."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    from klpga import config

    body = {
        "url": config.ENTRY_LIST_ENDPOINT,
        "params": {"gameCode": game_code},
        "body_text": _entry_list_html(player_codes_and_names),
    }
    cache_file = cache_dir / "entrylist_cache.json"
    cache_file.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    if mtime_epoch is not None:
        os.utime(cache_file, (mtime_epoch, mtime_epoch))
    return cache_file


def _base_argv(db_path, c_predictions_dir, player_code, raw_cache_dir):
    return [
        "48_investigate_r1_player_exclusion.py",
        "--db", str(db_path), "--game-code", GAME_CODE, "--pre-cutoff-date", CUTOFF_DATE,
        "--c-predictions-dir", str(c_predictions_dir), "--pre-prediction-id", "001-C-FINAL",
        "--player-code", player_code, "--raw-cache-dir", str(raw_cache_dir),
    ]


def _run(module, argv):
    argv_backup = sys.argv
    sys.argv = argv
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    return rc


def _insert_r1_row(db_path, player_code, player_name, *, in_entry_field=True):
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT OR IGNORE INTO player_master (player_id, player_name) VALUES (?, ?)", (player_code, player_name))
    if in_entry_field:
        conn.execute(
            "INSERT INTO tournament_entry (game_code, player_code, player_name_display, source, collected_at) "
            "VALUES (?, ?, ?, 'test', '2027-01-05T00:00:00Z')",
            (GAME_CODE, player_code, player_name),
        )
    conn.execute(
        "INSERT INTO player_round (event_id, game_code, season, round_number, player_id, player_name, "
        "round_score, round_to_par) VALUES (?, ?, 2026, 1, ?, ?, 68, -4)",
        (GAME_CODE, GAME_CODE, player_code, player_name),
    )
    conn.commit()
    conn.close()


def test_no_entry_list_cache_is_unresolved_and_not_safe_to_close(module, db_path, tmp_path, capsys):
    _insert_r1_row(db_path, UNEXPLAINED_CODE, "Ghost")
    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    _freeze_pre_c(c_predictions_dir)
    raw_cache_dir = tmp_path / "raw_cache_http"  # never created — no cache file exists

    rc = _run(module, _base_argv(db_path, c_predictions_dir, UNEXPLAINED_CODE, raw_cache_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert f"=== {UNEXPLAINED_CODE} PRE-FIELD-EXCLUSION INVESTIGATION (READ-ONLY) ===" in out
    assert f"{UNEXPLAINED_CODE} ROOT CAUSE: UNRESOLVED" in out
    assert "PLAYER REPLACED/DIFFERENCE: UNKNOWN" in out
    assert "R1 AUDIT SAFE TO CLOSE: NO" in out


def test_cache_fetched_after_pre_freeze_is_late_entry_and_safe_to_close(module, db_path, tmp_path, capsys):
    _insert_r1_row(db_path, UNEXPLAINED_CODE, "Ghost")
    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    _freeze_pre_c(c_predictions_dir)
    raw_cache_dir = tmp_path / "raw_cache_http"
    # Real cached field: same 5 players but 104 swapped for 999 — a real late substitution.
    _write_entry_list_cache(
        raw_cache_dir, GAME_CODE,
        [("101", "101"), ("102", "102"), ("103", "103"), ("999", "Ghost"), ("105", "105")],
        mtime_epoch=_FUTURE_EPOCH,  # after PRE_CREATED_AT_UTC (2027-01-01)
    )

    rc = _run(module, _base_argv(db_path, c_predictions_dir, UNEXPLAINED_CODE, raw_cache_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert f"{UNEXPLAINED_CODE} ROOT CAUSE: LATE_ENTRY" in out
    assert "in PRE but NOT in real cached field (candidate replaced/removed players): ['104']" in out
    assert "PLAYER REPLACED/DIFFERENCE: 104 ('104') is in PRE's 120 but NOT in the real cached entry-list field" in out
    assert "R1 AUDIT SAFE TO CLOSE: YES" in out


def test_cache_fetched_before_pre_freeze_is_collector_omission_not_safe_to_close(module, db_path, tmp_path, capsys):
    _insert_r1_row(db_path, UNEXPLAINED_CODE, "Ghost")
    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    _freeze_pre_c(c_predictions_dir)
    raw_cache_dir = tmp_path / "raw_cache_http"
    # Real cached field already had 999 at a time BEFORE PRE was frozen — a real omission bug in PRE's own selection.
    _write_entry_list_cache(
        raw_cache_dir, GAME_CODE,
        [("101", "101"), ("102", "102"), ("103", "103"), ("104", "104"), ("105", "105"), ("999", "Ghost")],
        mtime_epoch=_PAST_EPOCH,  # before PRE_CREATED_AT_UTC (2027-01-01)
    )

    rc = _run(module, _base_argv(db_path, c_predictions_dir, UNEXPLAINED_CODE, raw_cache_dir))
    assert rc == 0
    out = capsys.readouterr().out
    assert f"{UNEXPLAINED_CODE} ROOT CAUSE: COLLECTOR_OMISSION" in out
    assert "real code-defect candidate in PRE's own field-selection logic" in out
    assert "PLAYER REPLACED/DIFFERENCE: NONE" in out
    assert "R1 AUDIT SAFE TO CLOSE: NO" in out


def test_never_writes_frozen_files_read_only(module, db_path, tmp_path, capsys):
    """This script only ever opens the DB in read-only mode and never
    touches any prediction/history artifact."""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "mode=ro" in source
    _insert_r1_row(db_path, UNEXPLAINED_CODE, "Ghost")
    c_predictions_dir = tmp_path / "neo_win_c_predictions"
    _freeze_pre_c(c_predictions_dir)
    from klpga.neo_win.beta001c_archive import archive_paths as c_archive_paths
    pre_json_path, _ = c_archive_paths(c_predictions_dir, "001-C-FINAL", GAME_CODE, CUTOFF_DATE)
    before = pre_json_path.read_bytes()

    raw_cache_dir = tmp_path / "raw_cache_http"
    _run(module, _base_argv(db_path, c_predictions_dir, UNEXPLAINED_CODE, raw_cache_dir))

    after = pre_json_path.read_bytes()
    assert before == after
