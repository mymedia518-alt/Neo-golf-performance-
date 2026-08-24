"""Idempotent UPSERT helpers for loading collector output into
klpga.sqlite, plus collection_runs audit logging.

Re-running a collection step is safe: every write here is
INSERT ... ON CONFLICT (<natural key>) DO UPDATE, so the same row
collected twice just overwrites itself rather than duplicating.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Iterable, Mapping


def _upsert(
    conn: sqlite3.Connection,
    table: str,
    row: Mapping[str, Any],
    conflict_cols: Iterable[str],
) -> None:
    cols = list(row.keys())
    if not cols:
        raise ValueError(f"cannot upsert an empty row into {table}")
    placeholders = ", ".join(f":{c}" for c in cols)
    col_list = ", ".join(cols)
    conflict_cols = list(conflict_cols)
    update_cols = [c for c in cols if c not in conflict_cols]
    conflict_clause = ", ".join(conflict_cols)

    if update_cols:
        update_clause = ", ".join(f"{c}=excluded.{c}" for c in update_cols)
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict_clause}) DO UPDATE SET {update_clause}"
        )
    else:
        # Every column is part of the conflict key — nothing to update.
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
            f"ON CONFLICT({conflict_clause}) DO NOTHING"
        )
    conn.execute(sql, dict(row))


def upsert_tournament(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(conn, "tournament_master", row, conflict_cols=["event_id"])


def upsert_player(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(conn, "player_master", row, conflict_cols=["player_id"])


def upsert_player_event(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(conn, "player_event", row, conflict_cols=["event_id", "player_id"])


def upsert_player_round(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(conn, "player_round", row, conflict_cols=["event_id", "player_id", "round_number"])


def upsert_stats_snapshot(conn: sqlite3.Connection, row: Mapping[str, Any]) -> None:
    _upsert(
        conn,
        "player_stats_snapshot",
        row,
        conflict_cols=["player_id", "season", "as_of_date", "snapshot_type", "related_event_id"],
    )


def start_collection_run(conn: sqlite3.Connection, script_name: str, target: str | None, started_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO collection_runs (script_name, target, started_at, status) "
        "VALUES (:script_name, :target, :started_at, 'running')",
        {"script_name": script_name, "target": target, "started_at": started_at},
    )
    return int(cur.lastrowid)


def finish_collection_run(
    conn: sqlite3.Connection,
    run_id: int,
    status: str,
    finished_at: str,
    rows_written: int | None = None,
    error_message: str | None = None,
) -> None:
    if status not in ("success", "error", "blocked"):
        raise ValueError(f"invalid terminal collection_runs status: {status!r}")
    conn.execute(
        "UPDATE collection_runs SET status=:status, finished_at=:finished_at, "
        "rows_written=:rows_written, error_message=:error_message WHERE run_id=:run_id",
        {
            "status": status,
            "finished_at": finished_at,
            "rows_written": rows_written,
            "error_message": error_message,
            "run_id": run_id,
        },
    )
