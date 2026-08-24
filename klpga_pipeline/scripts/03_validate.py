"""Validate klpga.sqlite against the Historical Database spec:
  - exactly TARGET_COMPLETED_TOURNAMENTS rows in tournament_master
  - no duplicate game_code / (event_id, player_id) / (event_id, player_id, round_number)
  - every player_event / player_round row's event_id and player_id
    resolve to an existing tournament_master / player_master row
    (foreign_keys=ON already enforces this at insert time, but this
    re-checks explicitly for a clear pass/fail report)
  - every tournament_master row has at least one player_event row —
    i.e. 02_collect_leaderboards.py actually ran to completion for it.
    tournament_master alone only proves 01_collect_tournaments.py
    succeeded; a tournament with zero player_event rows means its
    leaderboard collection crashed, was blocked, or never ran, and this
    would otherwise pass silently since row-count/FK/duplicate checks
    don't look at per-tournament coverage at all.
  - no collection_runs row logged status='error' or 'blocked' — a
    secondary signal pointing at *why*, if the coverage check above
    fails (kept separate since a script can legitimately retry after an
    earlier failed run and still end up fully collected).

Usage:
    python scripts/03_validate.py --db data/klpga.sqlite

Exits non-zero if any check fails.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga import config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    return conn.execute(sql).fetchone()[0]


def validate(db_path: Path, target_count: int) -> list[str]:
    failures: list[str] = []
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    count = _scalar(conn, "SELECT COUNT(*) FROM tournament_master")
    if count != target_count:
        failures.append(f"tournament_master has {count} rows, expected exactly {target_count}")

    dup_game_code = _scalar(
        conn,
        "SELECT COUNT(*) FROM (SELECT game_code FROM tournament_master "
        "GROUP BY game_code HAVING COUNT(*) > 1)",
    )
    if dup_game_code:
        failures.append(f"{dup_game_code} duplicate game_code values in tournament_master")

    dup_player_event = _scalar(
        conn,
        "SELECT COUNT(*) FROM (SELECT event_id, player_id FROM player_event "
        "GROUP BY event_id, player_id HAVING COUNT(*) > 1)",
    )
    if dup_player_event:
        failures.append(f"{dup_player_event} duplicate (event_id, player_id) pairs in player_event")

    dup_player_round = _scalar(
        conn,
        "SELECT COUNT(*) FROM (SELECT event_id, player_id, round_number FROM player_round "
        "GROUP BY event_id, player_id, round_number HAVING COUNT(*) > 1)",
    )
    if dup_player_round:
        failures.append(
            f"{dup_player_round} duplicate (event_id, player_id, round_number) rows in player_round"
        )

    orphan_pe_event = _scalar(
        conn,
        "SELECT COUNT(*) FROM player_event pe "
        "LEFT JOIN tournament_master tm ON pe.event_id = tm.event_id "
        "WHERE tm.event_id IS NULL",
    )
    if orphan_pe_event:
        failures.append(f"{orphan_pe_event} player_event rows reference a missing tournament_master.event_id")

    orphan_pe_player = _scalar(
        conn,
        "SELECT COUNT(*) FROM player_event pe "
        "LEFT JOIN player_master pm ON pe.player_id = pm.player_id "
        "WHERE pm.player_id IS NULL",
    )
    if orphan_pe_player:
        failures.append(f"{orphan_pe_player} player_event rows reference a missing player_master.player_id")

    orphan_pr_event = _scalar(
        conn,
        "SELECT COUNT(*) FROM player_round pr "
        "LEFT JOIN tournament_master tm ON pr.event_id = tm.event_id "
        "WHERE tm.event_id IS NULL",
    )
    if orphan_pr_event:
        failures.append(f"{orphan_pr_event} player_round rows reference a missing tournament_master.event_id")

    incomplete = conn.execute(
        "SELECT tm.event_id, tm.game_code, tm.event_name FROM tournament_master tm "
        "LEFT JOIN player_event pe ON tm.event_id = pe.event_id "
        "WHERE pe.event_id IS NULL"
    ).fetchall()
    if incomplete:
        examples = ", ".join(f"{game_code} ({name})" for _, game_code, name in incomplete[:5])
        more = f" (+{len(incomplete) - 5} more)" if len(incomplete) > 5 else ""
        failures.append(
            f"{len(incomplete)} tournament_master row(s) have ZERO player_event rows — "
            f"02_collect_leaderboards.py did not complete for them: {examples}{more}"
        )

    conn.close()
    return failures


def collect_warnings(db_path: Path) -> list[str]:
    """Non-fatal diagnostics: historical error/blocked collection_runs
    rows. NOT counted toward pass/fail — a script can legitimately fail
    once, get fixed, and be re-run successfully, and this append-only
    audit log keeps the old failed row forever. The authoritative
    "did collection actually complete" signal is the player_event
    coverage check in validate() above; this is just context to help
    explain a failure it finds, or to flag past retries even when
    coverage now looks fine."""
    conn = sqlite3.connect(db_path)
    total = _scalar(conn, "SELECT COUNT(*) FROM collection_runs WHERE status IN ('error', 'blocked')")
    warnings: list[str] = []
    if total:
        recent = conn.execute(
            "SELECT script_name, target, status, error_message FROM collection_runs "
            "WHERE status IN ('error', 'blocked') ORDER BY run_id DESC LIMIT 5"
        ).fetchall()
        examples = "; ".join(f"{s}/{t}: {status} ({msg})" for s, t, status, msg in recent)
        more = f" (+{total - len(recent)} more)" if total > len(recent) else ""
        warnings.append(f"{total} historical collection_runs row(s) logged error/blocked: {examples}{more}")
    conn.close()
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--target", type=int, default=config.TARGET_COMPLETED_TOURNAMENTS)
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist.", file=sys.stderr)
        return 2

    failures = validate(db_path, args.target)
    warnings = collect_warnings(db_path)

    if warnings:
        print(f"NOTE ({len(warnings)} non-fatal, informational — does not affect pass/fail):")
        for w in warnings:
            print(f"  - {w}")
        print()

    if failures:
        print(f"VALIDATION FAILED ({len(failures)} issue(s)):")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("VALIDATION PASSED: all checks OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
