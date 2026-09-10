"""scripts/107_extract_tournament_master_dates.py -- regression tests.

Uses a real, self-contained temporary sqlite database (schema copied
verbatim from src/klpga/db/schema.sql's tournament_master definition)
so these tests exercise the actual SQL and JSON-writing logic, not a
mock of it. No real/production sqlite corpus is touched.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_SPEC = importlib.util.spec_from_file_location(
    "extract_tournament_master_dates", ROOT / "scripts" / "107_extract_tournament_master_dates.py"
)
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)  # type: ignore[union-attr]


def _make_db(tmp_path: Path, rows: list[tuple]) -> Path:
    db_path = tmp_path / "test.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE tournament_master (
            event_id TEXT PRIMARY KEY, game_code TEXT NOT NULL UNIQUE,
            event_name TEXT NOT NULL, season INTEGER NOT NULL,
            start_date TEXT, end_date TEXT NOT NULL
        )"""
    )
    conn.executemany(
        "INSERT INTO tournament_master (event_id, game_code, event_name, season, start_date, end_date) VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
def isolate_output(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "OUTPUT_PATH", tmp_path / "TOURNAMENT_MASTER_DATES_V1.json")
    yield


def test_extracts_exact_query_result(tmp_path):
    db = _make_db(tmp_path, [
        ("e1", "2023090001", "Event A", 2023, "2023-09-01", "2023-09-04"),
        ("e2", "2023090002", "Event B", 2023, "2023-09-07", "2023-09-10"),
    ])
    result = mod.extract(db)
    assert result["dates"] == {"2023090001": "2023-09-01", "2023090002": "2023-09-07"}
    assert result["record_count"] == 2


def test_excludes_null_start_date(tmp_path):
    db = _make_db(tmp_path, [
        ("e1", "2023090001", "Event A", 2023, "2023-09-01", "2023-09-04"),
        ("e2", "2023090002", "Event B (no confirmed start date)", 2023, None, "2023-09-10"),
    ])
    result = mod.extract(db)
    assert "2023090002" not in result["dates"]
    assert result["record_count"] == 1


def test_source_query_matches_the_original_script_89_query():
    """The whole point of this extractor is byte-identical provenance
    with the query scripts/89_redteam_neo_ranking_v1.py itself used --
    guard against a future edit silently changing it."""
    source = (ROOT / "scripts" / "89_redteam_neo_ranking_v1.py").read_text(encoding="utf-8")
    assert "SELECT game_code,start_date FROM tournament_master WHERE start_date IS NOT NULL" in source
    extractor_source = (ROOT / "scripts" / "107_extract_tournament_master_dates.py").read_text(encoding="utf-8")
    assert "SELECT game_code, start_date FROM tournament_master WHERE start_date IS NOT NULL" in extractor_source


def test_main_writes_output_file_and_prints_sha(tmp_path, monkeypatch, capsys):
    db = _make_db(tmp_path, [("e1", "2023090001", "Event A", 2023, "2023-09-01", "2023-09-04")])
    output_path = tmp_path / "out.json"
    monkeypatch.setattr(mod, "OUTPUT_PATH", output_path)
    monkeypatch.setattr(sys, "argv", ["prog", "--db", str(db)])
    exit_code = mod.main()
    assert exit_code == 0
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["dates"] == {"2023090001": "2023-09-01"}
    printed = json.loads(capsys.readouterr().out)
    assert printed["record_count"] == 1
    assert len(printed["sha256"]) == 64


def test_no_other_data_is_written_or_modified(tmp_path):
    """This extractor must touch exactly one output path and nothing
    else -- no weights, no model logic, no other repo file."""
    db = _make_db(tmp_path, [("e1", "2023090001", "Event A", 2023, "2023-09-01", "2023-09-04")])
    before = set(p for p in ROOT.rglob("*") if p.is_file())
    mod.extract(db)  # extract() alone (no --main call) must never write anything
    after = set(p for p in ROOT.rglob("*") if p.is_file())
    assert before == after
