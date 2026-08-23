"""python -m klpga.validate

Runs data-quality checks against data/klpga_history.db and writes
reports/data_quality_report.md.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone

from . import config, db


def _count(conn: sqlite3.Connection, sql: str, params=()) -> int:
    return conn.execute(sql, params).fetchone()[0]


def run_validation(conn: sqlite3.Connection) -> str:
    lines: list = []
    lines.append("# KLPGA Historical DB — Data Quality Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append("")

    n_tournaments = _count(conn, "SELECT COUNT(*) FROM tournaments")
    n_in_scope = _count(conn, "SELECT COUNT(*) FROM tournaments WHERE in_model_scope = 1")
    n_players = _count(conn, "SELECT COUNT(*) FROM players")
    n_events = _count(conn, "SELECT COUNT(*) FROM player_events")
    n_rounds = _count(conn, "SELECT COUNT(*) FROM rounds")

    lines.append("## Row counts")
    lines.append("")
    lines.append(f"- Tournaments collected: {n_tournaments}")
    lines.append(f"- Tournaments in model scope (regular tour, completed): {n_in_scope}")
    lines.append(f"- Players: {n_players}")
    lines.append(f"- Player-event rows: {n_events}")
    lines.append(f"- Round rows: {n_rounds}")
    lines.append("")

    dup_events = _count(
        conn,
        """
        SELECT COUNT(*) FROM (
            SELECT tournament_id, player_id, COUNT(*) c FROM player_events
            GROUP BY tournament_id, player_id HAVING c > 1
        )
        """,
    )
    dup_rounds = _count(
        conn,
        """
        SELECT COUNT(*) FROM (
            SELECT tournament_id, player_id, round_number, COUNT(*) c FROM rounds
            GROUP BY tournament_id, player_id, round_number HAVING c > 1
        )
        """,
    )
    lines.append("## Duplicate primary keys")
    lines.append("")
    lines.append(f"- Duplicate player_events keys: {dup_events}")
    lines.append(f"- Duplicate rounds keys: {dup_rounds}")
    lines.append("")

    lines.append("## NULL ratios (player_events)")
    lines.append("")
    for col in ("final_rank", "final_score", "total_strokes", "rounds_played", "made_cut"):
        n_null = _count(conn, f"SELECT COUNT(*) FROM player_events WHERE {col} IS NULL")
        pct = (n_null / n_events * 100) if n_events else 0.0
        lines.append(f"- {col}: {n_null} / {n_events} NULL ({pct:.1f}%)")
    lines.append("")

    abnormal_rounds = _count(
        conn,
        "SELECT COUNT(*) FROM rounds WHERE strokes IS NOT NULL AND (strokes < 50 OR strokes > 100)",
    )
    lines.append("## Abnormal scores")
    lines.append("")
    lines.append(f"- Round rows with strokes outside a plausible [50, 100] range: {abnormal_rounds}")
    lines.append("")

    lines.append("## Field size per tournament (top/bottom 5 by player count)")
    lines.append("")
    field_sizes = conn.execute(
        """
        SELECT t.tournament_id, t.tournament_name, COUNT(pe.player_id) AS n_players
        FROM tournaments t LEFT JOIN player_events pe ON pe.tournament_id = t.tournament_id
        GROUP BY t.tournament_id ORDER BY n_players DESC
        """
    ).fetchall()
    if field_sizes:
        lines.append("| Tournament | Players |")
        lines.append("|---|---|")
        for row in field_sizes[:5]:
            lines.append(f"| {row['tournament_name']} | {row['n_players']} |")
        lines.append("| ... | ... |")
        for row in field_sizes[-5:]:
            lines.append(f"| {row['tournament_name']} | {row['n_players']} |")
    else:
        lines.append("(no data)")
    lines.append("")

    inconsistent = conn.execute(
        """
        SELECT pe.tournament_id, pe.player_id, pe.total_strokes, SUM(r.strokes) AS round_sum
        FROM player_events pe JOIN rounds r
          ON r.tournament_id = pe.tournament_id AND r.player_id = pe.player_id
        WHERE pe.total_strokes IS NOT NULL
        GROUP BY pe.tournament_id, pe.player_id
        HAVING round_sum IS NOT NULL AND round_sum != pe.total_strokes
        """
    ).fetchall()
    lines.append("## Round-sum vs. total_strokes consistency")
    lines.append("")
    lines.append(f"- Player-events where SUM(round strokes) != total_strokes: {len(inconsistent)}")
    lines.append("")

    lines.append("## Placement flag sanity")
    lines.append("")
    n_win = _count(conn, "SELECT COUNT(*) FROM player_events WHERE win = 1")
    n_top5 = _count(conn, "SELECT COUNT(*) FROM player_events WHERE top5 = 1")
    n_top10 = _count(conn, "SELECT COUNT(*) FROM player_events WHERE top10 = 1")
    n_top20 = _count(conn, "SELECT COUNT(*) FROM player_events WHERE top20 = 1")
    lines.append(f"- WIN rows: {n_win} (expect ~= number of in-scope tournaments: {n_in_scope})")
    lines.append(f"- TOP5 rows: {n_top5}")
    lines.append(f"- TOP10 rows: {n_top10}")
    lines.append(f"- TOP20 rows: {n_top20}")
    win_not_top5 = _count(conn, "SELECT COUNT(*) FROM player_events WHERE win = 1 AND top5 = 0")
    top5_not_top10 = _count(conn, "SELECT COUNT(*) FROM player_events WHERE top5 = 1 AND top10 = 0")
    top10_not_top20 = _count(conn, "SELECT COUNT(*) FROM player_events WHERE top10 = 1 AND top20 = 0")
    lines.append(f"- WIN rows not flagged TOP5 (should be 0): {win_not_top5}")
    lines.append(f"- TOP5 rows not flagged TOP10 (should be 0): {top5_not_top10}")
    lines.append(f"- TOP10 rows not flagged TOP20 (should be 0): {top10_not_top20}")
    lines.append("")

    lines.append("## Collection run history")
    lines.append("")
    runs = conn.execute(
        "SELECT run_id, started_at, finished_at, requested_events, tournaments_collected, "
        "players_collected, status, error_message FROM collection_runs ORDER BY run_id DESC LIMIT 20"
    ).fetchall()
    if runs:
        lines.append("| run_id | started_at | status | requested | tournaments | players | error |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in runs:
            lines.append(
                f"| {r['run_id']} | {r['started_at']} | {r['status']} | {r['requested_events']} | "
                f"{r['tournaments_collected']} | {r['players_collected']} | {r['error_message'] or ''} |"
            )
    else:
        lines.append("(no collection runs recorded)")
    lines.append("")

    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m klpga.validate",
        description="Validate the collected KLPGA historical DB and write a data quality report.",
    )
    parser.parse_args(argv)

    conn = db.get_connection()
    db.init_db(conn)
    try:
        report = run_validation(conn)
    finally:
        conn.close()

    out_path = config.REPORT_DIR / "data_quality_report.md"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nReport written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
