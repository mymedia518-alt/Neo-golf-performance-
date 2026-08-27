"""Tests for scripts/run_klpga_season_metrics_collector.py — fully
offline. `--live` is exercised via a fake client double at the module
level (`run()`); the real-`PoliteHttpClient`-construction path is
proven safe via `main()` with a taxonomy that has zero missing
identities, same pattern as run_klpga_collector.py's own tests."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from klpga.db.init_db import SCHEMA_PATH
from klpga.http_client import RateLimitBlockedError

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_klpga_season_metrics_collector.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_klpga_season_metrics_collector_script", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def module():
    return _load_module()


def _leaf(menu1, menu2, menu3, leaf_level, label):
    return {
        "menu1": menu1, "menu1_label": menu1, "menu2": menu2,
        "menu2_label": label if leaf_level == "menu2" else "",
        "menu3": menu3, "menu3_label": label if leaf_level == "menu3" else None,
        "leaf_level": leaf_level,
        "source_metric_key": f"{menu1}::{menu2}" + (f"::{menu3}" if leaf_level == "menu3" else ""),
    }


class _FakeClient:
    def __init__(self, *, html_by_identity=None, raise_by_identity=None):
        self.html_by_identity = html_by_identity or {}
        self.raise_by_identity = raise_by_identity or {}
        self.calls: list[str] = []

    @staticmethod
    def _identity_key_from_form(data):
        menu1, menu2, menu3 = data.get("menu1"), data.get("menu2"), data.get("menu3")
        return f"{menu1}::{menu2}::{menu3}" if menu3 else f"{menu1}::{menu2}"

    def post_text(self, url, data=None, use_cache=True, headers=None):
        key = self._identity_key_from_form(data or {})
        self.calls.append(key)
        if key in self.raise_by_identity:
            raise self.raise_by_identity[key]
        return self.html_by_identity.get(key, "<html><body><table><thead><tr></tr></thead><tbody></tbody></table></body></html>")


def _html(labels):
    ths = "".join(f"<th>{l}</th>" for l in labels)
    tds = "".join(f"<td>{i}</td>" for i in range(len(labels)))
    return f'<table><thead><tr>{ths}</tr></thead><tbody><tr data-record=""><td class="text-start player_name"><a href="/web/profile/mainRecord?playerCode=111">A</a></td><td class="record" data-rank="1">1.0</td></tr></tbody></table>'


def test_preview_makes_zero_http_calls(module, tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    rc = module.run(None, taxonomy, ["2025"], raw_samples_dir=tmp_path, db_path=None, live=False, log=lambda m: None)
    assert rc == module.EXIT_COMPLETE


def test_live_acquires_and_ingests_across_multiple_seasons(module, tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    client = _FakeClient(html_by_identity={"Tee::Tee01::010101": _html(["순위", "선수명", "평균 티샷 거리(yds)"])})
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()

    lines = []
    rc = module.run(
        client, taxonomy, ["2024", "2025"], raw_samples_dir=tmp_path / "raw", db_path=db_path, live=True,
        log=lines.append,
    )
    assert rc == module.EXIT_COMPLETE
    assert set(client.calls) == {"Tee::Tee01::010101"}  # once per season -> 2 calls total, same identity
    assert len(client.calls) == 2

    conn = sqlite3.connect(str(db_path))
    seasons = {r[0] for r in conn.execute("SELECT DISTINCT season FROM official_metric_value")}
    assert seasons == {2024, 2025}
    conn.close()


def test_hard_stop_in_one_season_does_not_block_the_others(module, tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    client = _FakeClient(raise_by_identity={"Tee::Tee01::010101": RateLimitBlockedError("429")})
    rc = module.run(
        client, taxonomy, ["2024", "2025"], raw_samples_dir=tmp_path / "raw", db_path=None, live=True,
        log=lambda m: None,
    )
    assert rc == module.EXIT_HARD_STOP
    # both seasons attempted (each season's acquisition halts only ITS OWN remaining live requests)
    assert len(client.calls) == 2


def test_main_taxonomy_missing_fails_cleanly(module, tmp_path):
    argv_backup = sys.argv
    sys.argv = [
        "run_klpga_season_metrics_collector.py", "--taxonomy", str(tmp_path / "nope.json"), "--seasons", "2025",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_TAXONOMY_LOAD_FAILED


def test_main_live_with_zero_missing_evidence_uses_real_client_safely(module, tmp_path):
    taxonomy = {
        "leaves": [
            {
                "menu1": "Tee", "menu1_label": "Tee", "menu2": "Tee01", "menu2_label": "",
                "menu3": "010101", "menu3_label": "평균 티샷 거리", "leaf_level": "menu3",
                "source_metric_key": "Tee::Tee01::010101",
            }
        ]
    }
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps(taxonomy), encoding="utf-8")
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "Tee__Tee01__010101__2025.html").write_text("<html></html>", encoding="utf-8")

    argv_backup = sys.argv
    sys.argv = [
        "run_klpga_season_metrics_collector.py",
        "--taxonomy", str(taxonomy_path),
        "--seasons", "2025",
        "--raw-samples-dir", str(raw_dir),
        "--cache-dir", str(tmp_path / "cache"),
        "--live",
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_COMPLETE


def test_main_db_path_not_initialized_fails_cleanly(module, tmp_path):
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps({"leaves": []}), encoding="utf-8")
    argv_backup = sys.argv
    sys.argv = [
        "run_klpga_season_metrics_collector.py",
        "--taxonomy", str(taxonomy_path),
        "--seasons", "2025",
        "--db-path", str(tmp_path / "does_not_exist.sqlite"),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_DB_NOT_INITIALIZED


def _insert_tournament(conn, event_id, season):
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) VALUES (?, ?, ?, ?, ?)",
        (event_id, f"G{event_id}", "Test Open", season, "2025-01-01"),
    )


def test_seasons_auto_derived_from_tournament_master_when_omitted(module, tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    client = _FakeClient(html_by_identity={"Tee::Tee01::010101": _html(["순위", "선수명", "평균 티샷 거리(yds)"])})
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _insert_tournament(conn, "E1", 2024)
    _insert_tournament(conn, "E2", 2025)
    conn.commit()
    conn.close()

    lines = []
    rc = module.run(
        client, taxonomy, None, raw_samples_dir=tmp_path / "raw", db_path=db_path, live=True, log=lines.append,
    )
    assert rc == module.EXIT_COMPLETE
    assert len(client.calls) == 2  # one per auto-derived season
    assert any("auto-derived" in line for line in lines)


def test_seasons_none_and_no_db_path_fails_cleanly(module, tmp_path):
    taxonomy = {"leaves": []}
    rc = module.run(
        None, taxonomy, None, raw_samples_dir=tmp_path / "raw", db_path=None, live=False, log=lambda m: None,
    )
    assert rc == module.EXIT_SEASONS_NOT_DERIVABLE


def test_seasons_none_and_empty_tournament_master_fails_cleanly(module, tmp_path):
    taxonomy = {"leaves": []}
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.close()

    rc = module.run(
        None, taxonomy, None, raw_samples_dir=tmp_path / "raw", db_path=db_path, live=False, log=lambda m: None,
    )
    assert rc == module.EXIT_SEASONS_NOT_DERIVABLE


def test_main_seasons_omitted_and_no_db_path_fails_cleanly(module, tmp_path):
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps({"leaves": []}), encoding="utf-8")
    argv_backup = sys.argv
    sys.argv = ["run_klpga_season_metrics_collector.py", "--taxonomy", str(taxonomy_path)]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_SEASONS_NOT_DERIVABLE


def test_final_report_includes_player_identity_and_completeness_sections(module, tmp_path):
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    client = _FakeClient(html_by_identity={"Tee::Tee01::010101": _html(["순위", "선수명", "평균 티샷 거리(yds)"])})
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('111', 'A')")
    conn.commit()
    conn.close()

    lines = []
    rc = module.run(
        client, taxonomy, ["2025"], raw_samples_dir=tmp_path / "raw", db_path=db_path, live=True, log=lines.append,
    )
    assert rc == module.EXIT_COMPLETE
    joined = "\n".join(lines)
    assert "=== PLAYER IDENTITY VERIFICATION ===" in joined
    assert "=== DATABASE COMPLETENESS ===" in joined
    assert "=== POST-ACQUISITION VALIDATION (per season) ===" in joined
    assert "verdict: PLAYER_CODE_IDENTITY_CONFIRMED" in joined
    assert "direct join safe: YES" in joined


_PRE_OFFICIAL_METRIC_VALUE_SHAPE_SQL = """
CREATE TABLE tournament_master (
    event_id TEXT PRIMARY KEY, game_code TEXT NOT NULL UNIQUE,
    event_name TEXT NOT NULL, season INTEGER NOT NULL,
    start_date TEXT, end_date TEXT NOT NULL
);
CREATE TABLE player_master (
    player_id TEXT PRIMARY KEY, player_name TEXT NOT NULL
);
"""


def test_run_against_a_production_db_predating_official_metric_value(module, tmp_path):
    """The real failure reported: a real 100-tournament production DB
    initialized before official_metric_value existed in schema.sql
    raised `sqlite3.OperationalError: no such table:
    official_metric_value` on ingestion. run() must migrate the table
    in additively (never dropping/touching tournament_master or
    player_master) and then ingest successfully."""
    taxonomy = {"leaves": [_leaf("Tee", "Tee01", "010101", "menu3", "평균 티샷 거리")]}
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw_dir.joinpath("Tee__Tee01__010101__2023.html").write_text(
        _html(["순위", "선수명", "평균 티샷 거리(yds)"]), encoding="utf-8"
    )

    db_path = tmp_path / "old_production.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(_PRE_OFFICIAL_METRIC_VALUE_SHAPE_SQL)
    conn.execute(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, end_date) "
        "VALUES ('E1', 'G1', 'Test Open', 2023, '2023-01-01')"
    )
    conn.execute("INSERT INTO player_master (player_id, player_name) VALUES ('111', 'A')")
    conn.commit()
    conn.close()

    lines = []
    rc = module.run(
        None, taxonomy, ["2023"], raw_samples_dir=raw_dir, db_path=db_path, live=False, log=lines.append,
    )
    assert rc == module.EXIT_COMPLETE

    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT COUNT(*) FROM official_metric_value WHERE season = 2023").fetchone()[0] == 1
    # the pre-existing production data is untouched
    assert conn.execute("SELECT COUNT(*) FROM tournament_master").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM player_master").fetchone()[0] == 1
    conn.close()


def test_main_parses_multiple_seasons(module, tmp_path):
    taxonomy_path = tmp_path / "taxonomy.json"
    taxonomy_path.write_text(json.dumps({"leaves": []}), encoding="utf-8")
    argv_backup = sys.argv
    sys.argv = [
        "run_klpga_season_metrics_collector.py",
        "--taxonomy", str(taxonomy_path),
        "--seasons", "2023, 2024,2025",
        "--raw-samples-dir", str(tmp_path / "raw"),
    ]
    try:
        rc = module.main()
    finally:
        sys.argv = argv_backup
    assert rc == module.EXIT_COMPLETE
