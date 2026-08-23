"""SQLite schema + connection + UPSERT helpers.

Re-running a collection for a tournament that is already in the DB never
creates duplicate rows: every write here is an UPSERT keyed on the table's
primary key.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import config
from .models import Player, PlayerEvent, RoundResult, Tournament

SCHEMA = """
CREATE TABLE IF NOT EXISTS tournaments (
    tournament_id      TEXT PRIMARY KEY,
    tournament_name    TEXT NOT NULL,
    season             INTEGER,
    start_date         TEXT,
    end_date           TEXT,
    course_name        TEXT,
    par                INTEGER,
    yardage            INTEGER,
    rounds_scheduled   INTEGER,
    tournament_type    TEXT,
    status             TEXT,
    in_model_scope     INTEGER,
    source_url         TEXT,
    collected_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS players (
    player_id      TEXT PRIMARY KEY,
    player_name    TEXT NOT NULL,
    collected_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS player_events (
    tournament_id       TEXT NOT NULL,
    player_id           TEXT NOT NULL,
    final_rank          TEXT,
    final_rank_numeric  INTEGER,
    final_score         INTEGER,
    total_strokes        INTEGER,
    rounds_played         INTEGER,
    made_cut               INTEGER,
    win                     INTEGER NOT NULL DEFAULT 0,
    top5                     INTEGER NOT NULL DEFAULT 0,
    top10                     INTEGER NOT NULL DEFAULT 0,
    top20                     INTEGER NOT NULL DEFAULT 0,
    collected_at              TEXT NOT NULL,
    PRIMARY KEY (tournament_id, player_id),
    FOREIGN KEY (tournament_id) REFERENCES tournaments (tournament_id) ON DELETE CASCADE,
    FOREIGN KEY (player_id) REFERENCES players (player_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS rounds (
    tournament_id   TEXT NOT NULL,
    player_id       TEXT NOT NULL,
    round_number    INTEGER NOT NULL,
    round_score     INTEGER,
    strokes         INTEGER,
    round_rank      TEXT,
    collected_at    TEXT NOT NULL,
    PRIMARY KEY (tournament_id, player_id, round_number),
    FOREIGN KEY (tournament_id, player_id)
        REFERENCES player_events (tournament_id, player_id) ON DELETE CASCADE
);

-- Extra official per-player-per-tournament statistics (e.g. Strokes Gained
-- components), only populated once/if a KLPGA adapter confirms the source
-- actually publishes them. Never filled with estimated values.
CREATE TABLE IF NOT EXISTS player_event_stats (
    tournament_id   TEXT NOT NULL,
    player_id       TEXT NOT NULL,
    stat_name       TEXT NOT NULL,
    stat_value      REAL,
    source          TEXT,
    PRIMARY KEY (tournament_id, player_id, stat_name),
    FOREIGN KEY (tournament_id, player_id)
        REFERENCES player_events (tournament_id, player_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS player_features (
    tournament_id       TEXT NOT NULL,
    player_id           TEXT NOT NULL,
    as_of_date          TEXT,
    window_size         INTEGER NOT NULL,
    events_used         INTEGER NOT NULL,
    avg_final_score     REAL,
    win_count           INTEGER,
    win_rate            REAL,
    top5_rate           REAL,
    top10_rate          REAL,
    top20_rate          REAL,
    cut_rate             REAL,
    avg_round_strokes     REAL,
    sub70_rate              REAL,
    volatility_score         REAL,
    sg_total                  REAL,
    sg_ott                     REAL,
    sg_app                      REAL,
    sg_putt                      REAL,
    computed_at                   TEXT NOT NULL,
    PRIMARY KEY (tournament_id, player_id, window_size),
    FOREIGN KEY (tournament_id, player_id)
        REFERENCES player_events (tournament_id, player_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS collection_runs (
    run_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at             TEXT NOT NULL,
    finished_at            TEXT,
    requested_events       INTEGER,
    tournaments_collected  INTEGER,
    players_collected      INTEGER,
    status                 TEXT NOT NULL DEFAULT 'running',
    error_message          TEXT,
    notes                  TEXT
);

CREATE INDEX IF NOT EXISTS idx_player_events_player ON player_events (player_id);
CREATE INDEX IF NOT EXISTS idx_rounds_player ON rounds (player_id);
CREATE INDEX IF NOT EXISTS idx_tournaments_start_date ON tournaments (start_date);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    with conn:
        conn.executescript(SCHEMA)


def upsert_tournament(conn: sqlite3.Connection, t: Tournament) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO tournaments (
                tournament_id, tournament_name, season, start_date, end_date,
                course_name, par, yardage, rounds_scheduled, tournament_type,
                status, in_model_scope, source_url, collected_at
            ) VALUES (:tournament_id, :tournament_name, :season, :start_date, :end_date,
                :course_name, :par, :yardage, :rounds_scheduled, :tournament_type,
                :status, :in_model_scope, :source_url, :collected_at)
            ON CONFLICT(tournament_id) DO UPDATE SET
                tournament_name = excluded.tournament_name,
                season = excluded.season,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                course_name = excluded.course_name,
                par = excluded.par,
                yardage = excluded.yardage,
                rounds_scheduled = excluded.rounds_scheduled,
                tournament_type = excluded.tournament_type,
                status = excluded.status,
                in_model_scope = excluded.in_model_scope,
                source_url = excluded.source_url,
                collected_at = excluded.collected_at
            """,
            {
                "tournament_id": t.tournament_id,
                "tournament_name": t.tournament_name,
                "season": t.season,
                "start_date": t.start_date,
                "end_date": t.end_date,
                "course_name": t.course_name,
                "par": t.par,
                "yardage": t.yardage,
                "rounds_scheduled": t.rounds_scheduled,
                "tournament_type": t.tournament_type,
                "status": t.status,
                "in_model_scope": None if t.in_model_scope is None else int(t.in_model_scope),
                "source_url": t.source_url,
                "collected_at": _now(),
            },
        )


def upsert_player(conn: sqlite3.Connection, p: Player) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO players (player_id, player_name, collected_at)
            VALUES (:player_id, :player_name, :collected_at)
            ON CONFLICT(player_id) DO UPDATE SET
                player_name = excluded.player_name,
                collected_at = excluded.collected_at
            """,
            {"player_id": p.player_id, "player_name": p.player_name, "collected_at": _now()},
        )


def upsert_player_event(conn: sqlite3.Connection, pe: PlayerEvent) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO player_events (
                tournament_id, player_id, final_rank, final_rank_numeric,
                final_score, total_strokes, rounds_played, made_cut,
                win, top5, top10, top20, collected_at
            ) VALUES (:tournament_id, :player_id, :final_rank, :final_rank_numeric,
                :final_score, :total_strokes, :rounds_played, :made_cut,
                :win, :top5, :top10, :top20, :collected_at)
            ON CONFLICT(tournament_id, player_id) DO UPDATE SET
                final_rank = excluded.final_rank,
                final_rank_numeric = excluded.final_rank_numeric,
                final_score = excluded.final_score,
                total_strokes = excluded.total_strokes,
                rounds_played = excluded.rounds_played,
                made_cut = excluded.made_cut,
                win = excluded.win,
                top5 = excluded.top5,
                top10 = excluded.top10,
                top20 = excluded.top20,
                collected_at = excluded.collected_at
            """,
            {
                "tournament_id": pe.tournament_id,
                "player_id": pe.player_id,
                "final_rank": pe.final_rank,
                "final_rank_numeric": pe.final_rank_numeric,
                "final_score": pe.final_score,
                "total_strokes": pe.total_strokes,
                "rounds_played": pe.rounds_played,
                "made_cut": None if pe.made_cut is None else int(pe.made_cut),
                "win": int(pe.win),
                "top5": int(pe.top5),
                "top10": int(pe.top10),
                "top20": int(pe.top20),
                "collected_at": _now(),
            },
        )


def upsert_round(conn: sqlite3.Connection, r: RoundResult) -> None:
    with conn:
        conn.execute(
            """
            INSERT INTO rounds (
                tournament_id, player_id, round_number, round_score,
                strokes, round_rank, collected_at
            ) VALUES (:tournament_id, :player_id, :round_number, :round_score,
                :strokes, :round_rank, :collected_at)
            ON CONFLICT(tournament_id, player_id, round_number) DO UPDATE SET
                round_score = excluded.round_score,
                strokes = excluded.strokes,
                round_rank = excluded.round_rank,
                collected_at = excluded.collected_at
            """,
            {
                "tournament_id": r.tournament_id,
                "player_id": r.player_id,
                "round_number": r.round_number,
                "round_score": r.round_score,
                "strokes": r.strokes,
                "round_rank": r.round_rank,
                "collected_at": _now(),
            },
        )


def start_collection_run(conn: sqlite3.Connection, requested_events: int) -> int:
    with conn:
        cur = conn.execute(
            "INSERT INTO collection_runs (started_at, requested_events, status) VALUES (?, ?, 'running')",
            (_now(), requested_events),
        )
        return cur.lastrowid


def finish_collection_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    tournaments_collected: int,
    players_collected: int,
    status: str,
    error_message: Optional[str] = None,
    notes: Optional[str] = None,
) -> None:
    with conn:
        conn.execute(
            """
            UPDATE collection_runs
            SET finished_at = ?, tournaments_collected = ?, players_collected = ?,
                status = ?, error_message = ?, notes = ?
            WHERE run_id = ?
            """,
            (_now(), tournaments_collected, players_collected, status, error_message, notes, run_id),
        )
