"""Export the SQLite tables to the exact CSV column layout the project
spec requires (booleans as TRUE/FALSE, one file per table)."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pandas as pd

BOOL_COLUMNS = {
    "player_event": ["tie_flag", "made_cut", "withdrawn", "disqualified"],
}

TABLE_TO_COLUMNS = {
    "tournament_master": [
        "event_id", "game_code", "event_name", "season", "start_date", "end_date",
        "course_name", "course_location", "par", "course_yards",
        "rounds_scheduled", "rounds_completed", "field_size",
        "winner", "winner_score", "official_url",
    ],
    "player_master": [
        "player_id", "player_name", "birth_year", "nationality",
        "team_or_sponsor", "official_player_url",
    ],
    "player_event": [
        "event_id", "game_code", "season", "player_id", "player_name",
        "finish_position", "finish_position_numeric", "tie_flag",
        "made_cut", "withdrawn", "disqualified", "rounds_played",
        "r1_score", "r2_score", "r3_score", "r4_score",
        "total_score", "score_to_par", "prize_money", "avg_score_event",
        "official_url",
    ],
    "player_round": [
        "event_id", "game_code", "season", "round_number",
        "player_id", "player_name",
        "round_score", "round_to_par", "finish_position_after_round",
        "course_name", "course_par",
        "front9_score", "back9_score", "birdies", "eagles", "pars",
        "bogeys", "double_bogey_plus", "official_url",
    ],
    "player_stats_snapshot": [
        "snapshot_id", "player_id", "season", "as_of_date", "snapshot_type",
        "related_event_id",
        "scoring_average", "scoring_average_rank",
        "sg_total", "sg_total_rank",
        "sg_off_the_tee", "sg_off_the_tee_rank",
        "sg_approach", "sg_approach_rank",
        "sg_around_green", "sg_around_green_rank",
        "sg_putting", "sg_putting_rank",
        "gir", "gir_rank",
        "driving_distance", "driving_distance_rank",
        "driving_accuracy", "driving_accuracy_rank",
        "putting_average", "putting_average_rank",
        "sixties_rate", "sixties_rate_rank",
        "top10_rate", "top10_rate_rank",
        "birdie_average", "birdie_average_rank",
        "par_breakers", "par_breakers_rank",
        "sand_save", "sand_save_rank",
        "scrambling", "scrambling_rank",
        "official_url", "collected_at",
    ],
}


def export_all(db_path: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        for table, columns in TABLE_TO_COLUMNS.items():
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            df = df.reindex(columns=columns)
            for bool_col in BOOL_COLUMNS.get(table, []):
                if bool_col in df.columns:
                    df[bool_col] = df[bool_col].map({1: "TRUE", 0: "FALSE"}).fillna("")
            out_path = out_dir / f"{table}.csv"
            df.to_csv(out_path, index=False)
            print(f"{table}: {len(df)} rows -> {out_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/klpga.sqlite")
    parser.add_argument("--out", default="data/csv")
    args = parser.parse_args()
    export_all(Path(args.db), Path(args.out))
