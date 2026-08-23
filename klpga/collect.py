"""python -m klpga.collect --events 100

Orchestrates: list recent tournaments -> for each, fetch detail + full
leaderboard (with per-round strokes) -> UPSERT everything into SQLite.
Every write is a real KLPGA-sourced value or NULL; nothing is estimated.
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Set

from . import db
from .adapters.klpga_adapter import KLPGAWebAdapter
from .http_client import FetchError
from .logging_conf import setup_logging
from .models import Player, PlayerEvent, RoundResult, Tournament
from .parsers import ParseError
from .playwright_fallback import RenderError
from .rank_utils import classify_model_scope, parse_rank, placement_flags

logger = logging.getLogger("klpga.collect")


def collect(events: int, *, use_cache: bool = True) -> int:
    """Runs one collection pass. Returns 0 on success, 1 on hard failure."""
    conn = db.get_connection()
    db.init_db(conn)
    run_id = db.start_collection_run(conn, events)

    adapter = KLPGAWebAdapter(use_cache=use_cache)
    tournaments_collected = 0
    players_seen: Set[str] = set()
    failures = 0

    try:
        try:
            listing = adapter.list_recent_tournaments(events)
        except (FetchError, RenderError, ParseError) as exc:
            db.finish_collection_run(
                conn, run_id, tournaments_collected=0, players_collected=0,
                status="failed", error_message=str(exc),
            )
            logger.error("could not obtain tournament list: %s", exc)
            return 1

        for item in listing:
            if tournaments_collected >= events:
                break
            try:
                detail = adapter.fetch_tournament_detail(item)
            except (FetchError, RenderError) as exc:
                logger.warning(
                    "skipping %s (%s): detail fetch failed: %s",
                    item.tournament_id, item.tournament_name, exc,
                )
                failures += 1
                continue

            in_scope = classify_model_scope(item.tournament_type, item.status)
            season = None
            if item.period_text and len(item.period_text) >= 4 and item.period_text[:4].isdigit():
                season = int(item.period_text[:4])

            tournament = Tournament(
                tournament_id=item.tournament_id,
                tournament_name=item.tournament_name,
                season=season,
                start_date=item.period_text,
                end_date=None,
                course_name=detail.course_name,
                par=detail.par,
                yardage=detail.yardage,
                rounds_scheduled=detail.rounds_scheduled,
                tournament_type=item.tournament_type,
                status=item.status,
                in_model_scope=in_scope,
                source_url=item.detail_url,
            )
            db.upsert_tournament(conn, tournament)

            try:
                leaderboard = adapter.fetch_leaderboard(item)
            except (FetchError, RenderError, ParseError) as exc:
                logger.warning("skipping leaderboard for %s: %s", item.tournament_id, exc)
                failures += 1
                tournaments_collected += 1
                continue

            for row in leaderboard:
                if not row.player_id:
                    logger.warning(
                        "leaderboard row without a resolvable player id in %s (%s); skipping",
                        item.tournament_id, row.player_name,
                    )
                    continue

                db.upsert_player(conn, Player(player_id=row.player_id, player_name=row.player_name))
                players_seen.add(row.player_id)

                rank_numeric, made_cut = parse_rank(row.raw_rank)
                win, top5, top10, top20 = placement_flags(rank_numeric)

                final_score = None
                if row.final_score_text:
                    stripped = row.final_score_text.replace("E", "0").strip()
                    try:
                        final_score = int(stripped)
                    except ValueError:
                        final_score = None

                rounds_played = sum(1 for s in row.round_strokes if s is not None)
                pe = PlayerEvent(
                    tournament_id=item.tournament_id,
                    player_id=row.player_id,
                    final_rank=row.raw_rank,
                    final_rank_numeric=rank_numeric,
                    final_score=final_score,
                    total_strokes=row.total_strokes,
                    rounds_played=rounds_played or None,
                    made_cut=made_cut,
                    win=win,
                    top5=top5,
                    top10=top10,
                    top20=top20,
                )
                db.upsert_player_event(conn, pe)

                for round_number, strokes in enumerate(row.round_strokes, start=1):
                    if strokes is None:
                        continue
                    db.upsert_round(
                        conn,
                        RoundResult(
                            tournament_id=item.tournament_id,
                            player_id=row.player_id,
                            round_number=round_number,
                            round_score=None,
                            strokes=strokes,
                            round_rank=None,
                        ),
                    )

            tournaments_collected += 1
            logger.info(
                "collected %s (%d/%d)", item.tournament_name, tournaments_collected, events
            )

        status = "success" if failures == 0 else "partial"
        db.finish_collection_run(
            conn, run_id,
            tournaments_collected=tournaments_collected,
            players_collected=len(players_seen),
            status=status,
            notes=f"{failures} tournament(s) skipped due to fetch/parse failures" if failures else None,
        )
        return 0
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m klpga.collect",
        description="Collect KLPGA regular-tour historical data into SQLite.",
    )
    parser.add_argument("--events", type=int, default=100, help="number of tournaments to collect (default: 100)")
    parser.add_argument("--no-cache", action="store_true", help="bypass the local HTTP cache")
    args = parser.parse_args(argv)

    setup_logging()
    return collect(args.events, use_cache=not args.no_cache)


if __name__ == "__main__":
    sys.exit(main())
