"""NEO Performance Dataset — the read-only join layer combining:
  - tournament_master (the 100-tournament historical corpus)
  - player_event (results — one row per player per tournament)
  - official_metric_value (2023-2026+ official KLPGA season metrics)
  - player_master (identity)

via the player_id <-> official_metric_value.player_code join CONFIRMED
safe by real evidence — `klpga.discovery.season_metric_collector.
verify_player_code_identity_space` reported a 98.65% match rate against
a real production DB. A `player_code` with NO `player_master.player_id`
match is never guessed into a row: it is excluded from official-metric
enrichment and reported separately in `unmatched_official_metric_
player_codes` — the event/player_event rows themselves are unaffected
(this dataset never drops a historical result over a metrics-join
miss).

This is a general-purpose reporting/analysis join — NOT itself
leakage-sensitive (unlike klpga.neo_win's model features, which
deliberately use only the PRIOR season's official metrics). This
dataset joins each player-season pair to that SAME season's official
metrics, since it exists for inspection/export/backfill, not for
predicting that season's own outcomes.
"""
from __future__ import annotations

import sqlite3


def build_neo_performance_dataset(conn: sqlite3.Connection) -> dict:
    """Returns a dict: `rows` (one per player_event row, enriched with
    that player+season's official metrics as a nested dict),
    `row_count`, `official_metric_seasons_available`,
    `unmatched_official_metric_player_codes`,
    `unmatched_official_metric_player_code_count`."""
    player_master_ids = {row[0] for row in conn.execute("SELECT player_id FROM player_master")}

    official_by_player_season: dict[tuple[str, int], dict[str, float]] = {}
    unmatched_codes: set[str] = set()
    seasons_available: set[int] = set()
    for player_code, season, official_label, value_raw in conn.execute(
        "SELECT player_code, season, official_label, value_raw FROM official_metric_value WHERE value_raw IS NOT NULL"
    ):
        seasons_available.add(season)
        if player_code not in player_master_ids:
            unmatched_codes.add(player_code)
            continue
        cleaned = str(value_raw).replace(",", "").strip()
        try:
            value = float(cleaned)
        except ValueError:
            continue
        official_by_player_season.setdefault((player_code, season), {})[official_label] = value

    rows: list[dict] = []
    for (
        event_id,
        game_code,
        event_name,
        season,
        start_date,
        end_date,
        course_name,
        player_id,
        player_name,
        finish_position,
        finish_position_numeric,
        made_cut,
        withdrawn,
        disqualified,
        rounds_played,
        total_score,
        score_to_par,
    ) in conn.execute(
        "SELECT tm.event_id, tm.game_code, tm.event_name, tm.season, tm.start_date, tm.end_date, tm.course_name, "
        "pe.player_id, pe.player_name, pe.finish_position, pe.finish_position_numeric, pe.made_cut, "
        "pe.withdrawn, pe.disqualified, pe.rounds_played, pe.total_score, pe.score_to_par "
        "FROM player_event pe JOIN tournament_master tm ON tm.event_id = pe.event_id"
    ):
        official_metrics = official_by_player_season.get((player_id, season), {})
        rows.append(
            {
                "event_id": event_id,
                "game_code": game_code,
                "event_name": event_name,
                "season": season,
                "start_date": start_date,
                "end_date": end_date,
                "course_name": course_name,
                "player_id": player_id,
                "player_name": player_name,
                "finish_position": finish_position,
                "finish_position_numeric": finish_position_numeric,
                "made_cut": bool(made_cut),
                "withdrawn": bool(withdrawn),
                "disqualified": bool(disqualified),
                "rounds_played": rounds_played,
                "total_score": total_score,
                "score_to_par": score_to_par,
                "official_metrics": official_metrics,
                "official_metrics_available": bool(official_metrics),
            }
        )

    return {
        "rows": rows,
        "row_count": len(rows),
        "official_metric_seasons_available": sorted(seasons_available),
        "unmatched_official_metric_player_codes": sorted(unmatched_codes),
        "unmatched_official_metric_player_code_count": len(unmatched_codes),
    }
