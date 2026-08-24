"""Collect player_master / player_event / player_round rows for every
tournament already in tournament_master, via the confirmed
roundLeaderboard API adapter.

Usage:
    python scripts/02_collect_leaderboards.py --db data/klpga.sqlite

Flow (per project spec sections 4-5):
    for each tournament_master row (by game_code)
        -> discover the final round, fetch it
        -> targeted extra fetch of any earlier round missing scores
        -> merge per-player rows across whatever rounds were fetched
        -> UPSERT player_master / player_event / player_round

Fields with no confirmed source (prize_money, round_to_par for rounds
that weren't directly queried, front9/back9/birdie/eagle/etc. counts,
player birth_year/nationality/team_or_sponsor) are left NULL — see
docs/SITE_STRUCTURE_TODO.md.

ASSUMPTION (not confirmed against a live response, flagged so it can be
corrected once verified): made_cut is derived as status not in {'CUT'};
withdrawn/disqualified are derived from status == 'WD'/'DQ'. This is a
reasonable reading of the confirmed CUT/WD/DQ status strings, not a
verified site rule.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from klpga.collectors.leaderboard import collect_all_rounds_for_game  # noqa: E402
from klpga.db.upsert import (  # noqa: E402
    finish_collection_run,
    start_collection_run,
    upsert_player,
    upsert_player_event,
    upsert_player_round,
)
from klpga.http_client import PoliteHttpClient, RateLimitBlockedError  # noqa: E402
from klpga.parsers.leaderboard_parser import PlayerRoundRow  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def merge_player_rows(rounds_data: dict[int, list[PlayerRoundRow]]) -> dict[str, dict]:
    """Merge every fetched round response into one record per
    player_code. See module docstring for the precision rules this
    follows (round_to_par / finish_position_after_round are only kept
    for the round that was actually queried directly)."""
    merged: dict[str, dict] = {}
    for round_num in sorted(rounds_data.keys()):
        for row in rounds_data[round_num]:
            if row.player_code is None:
                continue
            entry = merged.setdefault(
                row.player_code,
                {
                    "player_code": row.player_code,
                    "player_name": None,
                    "player_eng_name": None,
                    "rank_display": None,
                    "rank": None,
                    "tie_flag": False,
                    "status": None,
                    "total_strokes": None,
                    "total_under_par": None,
                    "round_scores": {},        # round_num -> score
                    "round_to_par": {},         # round_num -> to-par (only when directly queried)
                    "round_rank": {},           # round_num -> rank_display (only when directly queried)
                    "_seen_at_round": None,
                },
            )
            for r_idx, score in (
                (1, row.round1_score), (2, row.round2_score),
                (3, row.round3_score), (4, row.round4_score),
            ):
                if score is not None and r_idx not in entry["round_scores"]:
                    entry["round_scores"][r_idx] = score

            if row.round_number is not None:
                if row.today_under_par is not None:
                    entry["round_to_par"].setdefault(row.round_number, row.today_under_par)
                if row.rank_display is not None:
                    entry["round_rank"].setdefault(row.round_number, row.rank_display)

            # Summary fields (identity, final rank/status/totals): take
            # them from the highest round-number response the player
            # appears in, since that reflects their latest known state.
            if entry["_seen_at_round"] is None or round_num >= entry["_seen_at_round"]:
                entry["_seen_at_round"] = round_num
                entry["player_name"] = row.player_name or entry["player_name"]
                entry["player_eng_name"] = row.player_eng_name or entry["player_eng_name"]
                entry["rank_display"] = row.rank_display
                entry["rank"] = row.rank
                entry["tie_flag"] = row.tie_flag
                entry["status"] = row.status
                entry["total_strokes"] = row.total_strokes
                entry["total_under_par"] = row.total_under_par
    return merged


def build_rows(game_code: str, season: int, event_id: str, merged: dict[str, dict]):
    player_rows, player_event_rows, player_round_rows = [], [], []

    for player_code, entry in merged.items():
        player_rows.append(
            {
                "player_id": player_code,
                "player_name": entry["player_name"],
                "birth_year": None,
                "nationality": None,
                "team_or_sponsor": None,
                "official_player_url": None,
            }
        )

        round_scores: dict[int, int] = entry["round_scores"]
        rounds_played = len(round_scores)
        total_score = entry["total_strokes"]
        avg_score_event: Optional[float] = (
            total_score / rounds_played if total_score is not None and rounds_played > 0 else None
        )
        status = entry["status"]

        player_event_rows.append(
            {
                "event_id": event_id,
                "game_code": game_code,
                "season": season,
                "player_id": player_code,
                "player_name": entry["player_name"],
                "finish_position": entry["rank_display"],
                "finish_position_numeric": entry["rank"],
                "tie_flag": 1 if entry["tie_flag"] else 0,
                "made_cut": 0 if status == "CUT" else 1,
                "withdrawn": 1 if status == "WD" else 0,
                "disqualified": 1 if status == "DQ" else 0,
                "rounds_played": rounds_played or None,
                "r1_score": round_scores.get(1),
                "r2_score": round_scores.get(2),
                "r3_score": round_scores.get(3),
                "r4_score": round_scores.get(4),
                "total_score": total_score,
                "score_to_par": entry["total_under_par"],
                "prize_money": None,
                "avg_score_event": avg_score_event,
                "official_url": None,
            }
        )

        for r_idx, score in round_scores.items():
            player_round_rows.append(
                {
                    "event_id": event_id,
                    "game_code": game_code,
                    "season": season,
                    "round_number": r_idx,
                    "player_id": player_code,
                    "player_name": entry["player_name"],
                    "round_score": score,
                    "round_to_par": entry["round_to_par"].get(r_idx),
                    "finish_position_after_round": entry["round_rank"].get(r_idx),
                    "course_name": None,
                    "course_par": None,
                    "front9_score": None,
                    "back9_score": None,
                    "birdies": None,
                    "eagles": None,
                    "pars": None,
                    "bogeys": None,
                    "double_bogey_plus": None,
                    "official_url": None,
                }
            )

    return player_rows, player_event_rows, player_round_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "klpga.sqlite"))
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "raw_cache" / "http"))
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist — run db/init_db.py and "
              f"01_collect_tournaments.py first.", file=sys.stderr)
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tournaments = conn.execute(
        "SELECT event_id, game_code, season FROM tournament_master ORDER BY end_date DESC"
    ).fetchall()

    if not tournaments:
        print("No rows in tournament_master — run 01_collect_tournaments.py first.", file=sys.stderr)
        return 2

    client = PoliteHttpClient(cache_dir=Path(args.cache_dir))
    total_players_written = 0
    blocked = False

    for t in tournaments:
        run_id = start_collection_run(conn, "02_collect_leaderboards", target=t["game_code"], started_at=_now_iso())
        conn.commit()
        try:
            rounds_data = collect_all_rounds_for_game(client, t["game_code"])
        except RateLimitBlockedError as exc:
            finish_collection_run(conn, run_id, status="blocked", finished_at=_now_iso(), error_message=str(exc))
            conn.commit()
            print(f"BLOCKED collecting gameCode={t['game_code']}: {exc}", file=sys.stderr)
            blocked = True
            break
        except Exception as exc:  # noqa: BLE001
            finish_collection_run(conn, run_id, status="error", finished_at=_now_iso(), error_message=str(exc))
            conn.commit()
            print(f"ERROR collecting gameCode={t['game_code']}: {exc}", file=sys.stderr)
            continue

        merged = merge_player_rows(rounds_data)
        player_rows, player_event_rows, player_round_rows = build_rows(
            t["game_code"], t["season"], t["event_id"], merged
        )

        for row in player_rows:
            upsert_player(conn, row)
        for row in player_event_rows:
            upsert_player_event(conn, row)
        for row in player_round_rows:
            upsert_player_round(conn, row)
        conn.commit()

        total_players_written += len(player_rows)
        finish_collection_run(
            conn, run_id, status="success", finished_at=_now_iso(), rows_written=len(player_rows)
        )
        conn.commit()
        print(f"gameCode={t['game_code']}: {len(player_rows)} players, "
              f"{len(player_round_rows)} round rows.")

    conn.close()
    print(f"Total players written across tournaments processed: {total_players_written}")
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
