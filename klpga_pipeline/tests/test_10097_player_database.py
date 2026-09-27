"""PLAYER DATABASE GOLD STANDARD V1 -- playerCode=10097 only.

Tests the specific discipline this mission demanded: every one of the
22 requested categories exists as a real table (even if empty), every
NULL value has a matching field_verification row explaining why, known
real facts (96 finished tournaments, 304 rounds, KB's missing SG) are
never silently changed, and nothing is fabricated for categories with
no real backing data (shot, distance_bucket, weather, training_targets).
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_spec = importlib.util.spec_from_file_location("build_10097_player_database", ROOT / "scripts" / "build_10097_player_database.py")
build_db = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_db)


def _conn():
    path = build_db.build()
    conn = sqlite3.connect(path)
    return conn


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


REQUIRED_TABLES = {
    "meta", "player_profile", "career_summary", "season_stats", "season_sg",
    "tournament", "round", "hole", "shot", "distance_bucket", "driving",
    "approach", "putting", "short_game", "scoring", "course", "weather",
    "momentum", "player_identity", "growth", "player_history_timeline",
    "training_targets", "field_verification",
}


def test_every_mission_category_has_a_real_table():
    conn = _conn()
    assert REQUIRED_TABLES <= _tables(conn)


def test_known_real_career_facts_are_exact_not_approximate():
    conn = _conn()
    row = conn.execute("SELECT career_events, career_rounds, wins, top5, top10, top20 FROM career_summary").fetchone()
    assert row == (96, 304, 4, 11, 20, 38)


def test_kb_tournament_sg_is_null_not_zero():
    conn = _conn()
    row = conn.execute("SELECT sg_total, finish_rank FROM tournament WHERE game_code='2026090003'").fetchone()
    assert row[0] is None
    assert row[0] != 0
    assert row[1] == 16


def test_in_progress_tournament_has_no_final_rank_or_sg():
    conn = _conn()
    row = conn.execute("SELECT status, finish_rank, sg_total FROM tournament WHERE game_code='2026120001'").fetchone()
    assert row[0] == "IN_PROGRESS"
    assert row[1] is None
    assert row[2] is None


def test_round_table_row_count_matches_reconciliation():
    conn = _conn()
    n = conn.execute("SELECT COUNT(*) FROM round").fetchone()[0]
    assert n == 304


def test_shot_and_distance_bucket_tables_exist_but_are_never_fabricated():
    """No shot-level or distance-bucket source is reachable from this
    sandbox (see the data-discovery mission) -- these tables must exist
    (mission categories 008/009) but must never contain invented rows."""
    conn = _conn()
    assert conn.execute("SELECT COUNT(*) FROM shot").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM distance_bucket").fetchone()[0] == 0
    statuses = {r[0] for r in conn.execute("SELECT status FROM field_verification WHERE table_name IN ('shot','distance_bucket')")}
    assert statuses == {"BLOCKED"}


def test_every_null_bearing_category_has_a_matching_verification_row():
    conn = _conn()
    for table in ("weather", "training_targets"):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        assert n == 0
        rows = conn.execute("SELECT status FROM field_verification WHERE table_name=?", (table,)).fetchall()
        assert rows, f"{table} has no verification row explaining its emptiness"
        assert all(r[0] in ("NOT_COLLECTED", "BLOCKED", "CONFIRMED_UNAVAILABLE") for r in rows)


def test_technical_stats_2025_are_scoped_to_season_2025_only():
    conn = _conn()
    seasons = {r[0] for r in conn.execute("SELECT DISTINCT season FROM driving")}
    assert seasons == {2025}


def test_player_profile_bio_fields_are_null_and_disclosed_as_not_collected():
    conn = _conn()
    row = conn.execute("SELECT birth, nationality, sponsor, team, height, weight FROM player_profile").fetchone()
    assert all(v is None for v in row)
    note = conn.execute(
        "SELECT status FROM field_verification WHERE table_name='player_profile' AND field_note LIKE '%birth%'"
    ).fetchone()
    assert note == ("NOT_COLLECTED",)


def test_english_name_is_real_and_sourced_from_committed_evidence():
    conn = _conn()
    row = conn.execute("SELECT english_name FROM player_profile").fetchone()
    assert row[0] == "KIM Minsun7"
    src = conn.execute(
        "SELECT repo_path FROM field_verification WHERE table_name='player_profile' AND field_note='english_name'"
    ).fetchone()
    assert "official_sources.zip" in src[0]


def test_k_ranking_is_real_and_dated():
    conn = _conn()
    row = conn.execute("SELECT k_ranking, k_ranking_asof FROM player_profile").fetchone()
    assert row[0] == 10
    assert row[1] == "2026-W36"


def test_no_fabricated_training_targets_without_a_reachable_source():
    conn = _conn()
    assert conn.execute("SELECT COUNT(*) FROM training_targets").fetchone()[0] == 0


def test_field_verification_has_no_orphan_status_values():
    conn = _conn()
    allowed = {"MEASURED", "DERIVED", "PARTIAL", "NOT_COLLECTED", "BLOCKED", "CONFIRMED_UNAVAILABLE"}
    statuses = {r[0] for r in conn.execute("SELECT DISTINCT status FROM field_verification")}
    assert statuses <= allowed
