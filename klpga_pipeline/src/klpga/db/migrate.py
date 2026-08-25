"""Safe, additive migration for player_stats_snapshot's `derived_*`
columns (see src/klpga/analytics/player_stats.py for what they are).

Never touches tournament_master / player_master / player_event /
player_round — the validated raw dataset — under any circumstance.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

# Every derived_* column compute_player_stats() writes. Used only to
# detect "this DB predates the derived-metrics schema change" — not
# compared against column types, just presence.
EXPECTED_DERIVED_COLUMNS = {
    "derived_tournaments_played",
    "derived_rounds_played",
    "derived_made_cuts",
    "derived_cut_rate",
    "derived_wins",
    "derived_top5",
    "derived_top10",
    "derived_best_finish",
    "derived_avg_round_score",
    "derived_round_scoring_stddev",
    "derived_avg_event_score_to_par",
    "derived_avg_event_score_to_par_n",
    "derived_avg_round_score_to_par",
    "derived_avg_round_score_to_par_n",
    "derived_recent_event_form_5",
    "derived_recent_event_form_5_n",
    "derived_recent_event_form_10",
    "derived_recent_event_form_10_n",
    "derived_recent_event_form_20",
    "derived_recent_event_form_20_n",
    "derived_weighted_recent_event_form",
    "derived_weighted_recent_event_form_n",
}


def ensure_player_stats_snapshot_schema(conn: sqlite3.Connection, schema_path: Path) -> None:
    """If player_stats_snapshot already has every derived_* column, do
    nothing. Otherwise, if the table has no rows under a snapshot_type
    OTHER than 'derived_trailing100', drop and recreate it (plus its
    indexes) from schema.sql.

    This is safe even when the table already holds many
    'derived_trailing100' rows (e.g. a populated production DB) — that
    snapshot type is BY DESIGN always fully, mechanically regenerated
    from the validated raw tables by scripts/09_build_player_stats_
    snapshot.py (see that script's docstring), so dropping and rebuilding
    them loses nothing that isn't immediately reproducible. It is NOT
    safe for any other snapshot_type (the OFFICIAL Data Center rows,
    group (a) in schema.sql, which would represent real external data
    with no regeneration path) — if any such row exists under an
    outdated schema, this refuses to touch the table and raises instead
    of silently dropping it.
    """
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(player_stats_snapshot)")}
    if not existing_cols:
        # Table doesn't exist yet at all (a brand-new DB) — schema.sql's
        # own CREATE TABLE IF NOT EXISTS will create it correctly below.
        pass
    elif EXPECTED_DERIVED_COLUMNS.issubset(existing_cols):
        return
    else:
        non_derived_count = conn.execute(
            "SELECT COUNT(*) FROM player_stats_snapshot WHERE snapshot_type != 'derived_trailing100'"
        ).fetchone()[0]
        if non_derived_count > 0:
            raise RuntimeError(
                f"player_stats_snapshot has {non_derived_count} row(s) under an outdated "
                "schema with a snapshot_type OTHER than 'derived_trailing100' (i.e. real, "
                "non-reproducible official-stat data) — refusing to drop it automatically. "
                "Back up its contents, then either migrate them by hand or "
                "DROP TABLE player_stats_snapshot yourself and re-run this script."
            )
        conn.execute("DROP TABLE IF EXISTS player_stats_snapshot")
        conn.execute("DROP INDEX IF EXISTS idx_stats_snapshot_player")
        conn.execute("DROP INDEX IF EXISTS idx_stats_snapshot_event")

    conn.executescript(schema_path.read_text(encoding="utf-8"))
