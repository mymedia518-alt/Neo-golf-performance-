"""Merge raw per-round roundLeaderboard rows into one record per player,
and build the DB row dicts for player_master / player_event /
player_round.

Shared by scripts/02_collect_leaderboards.py (full season walk) and
scripts/04_collect_single_tournament.py (one known gameCode, used as
the real-data validation checkpoint before scaling up).

Fields with no confirmed source (prize_money, round_to_par for rounds
that weren't directly queried, front9/back9/birdie/eagle/etc. counts,
player birth_year/nationality/team_or_sponsor) are left NULL — see
docs/SITE_STRUCTURE_TODO.md.

made_cut/withdrawn/disqualified, CONFIRMED live 2026-08-24
(gameCode=2026080002 real HTML — see docs/SITE_STRUCTURE_TODO.md):
  - made_cut is derived from whether the player has a real (non-
    sentinel) score for the tournament's actual final round — a
    structural fact from real collected data, NOT from data-rank text.
    The site does not appear to use literal "CUT" text at all; a
    missed-cut player simply gets a real numeric rank on their last
    completed round and no row on later rounds.
  - withdrawn/disqualified are left 0 UNLESS status is literally "WD"
    or "DQ" (kept for forward-compatibility in case some response
    somewhere does use that text — never actually observed so far).
    A player who didn't complete their last-appeared round shows the
    confirmed data-rank="999" sentinel (parsed as status="INCOMPLETE")
    instead — this clearly means "something abnormal happened," but no
    marker distinguishing WD from DQ was found anywhere in this
    endpoint's HTML. Rather than guess, withdrawn/disqualified stay 0
    for these rows too; the raw finish_position="999" is preserved
    so this group remains identifiable to downstream consumers without
    fabricating which specific status applies.
"""
from __future__ import annotations

from typing import Optional

from klpga.parsers.leaderboard_parser import PlayerRoundRow


def merge_player_rows(rounds_data: dict[int, list[PlayerRoundRow]]) -> dict[str, dict]:
    """Merge every fetched round response into one record per
    player_code. round_to_par / finish_position_after_round are only
    kept for the round that was actually queried directly, since
    today_under_par/rank on a given response only describe the round
    that response was requested for."""
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


def build_rows(game_code: str, season: int, event_id: str, merged: dict[str, dict], final_round: int):
    """Returns (player_rows, player_event_rows, player_round_rows) — dicts
    shaped exactly for klpga.db.upsert.upsert_player /
    upsert_player_event / upsert_player_round.

    `final_round` is the tournament's actual final round (e.g. the
    round number collect_all_rounds_for_game discovered/was given —
    typically `max(rounds_data.keys())` at the call site). made_cut is
    computed from whether each player has a real score for exactly
    that round, not from any status text."""
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
        made_cut = 1 if final_round in round_scores else 0

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
                "made_cut": made_cut,
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


def resolve_winner_score(player_event_rows: list[dict], winner_player_id: Optional[str]) -> Optional[int]:
    """Look up the winner's total_score from already-collected real
    player_event rows — never fabricated, only returned when unambiguous.

    Prefers matching by winner_player_id (from getGameList's confirmed
    winnerCode field, the site's own authoritative winner designation).
    Falls back to a unique finish_position_numeric == 1 row only when no
    winner_player_id is available (e.g. an older/unconfirmed response
    shape). Returns None — never a guess — if the match isn't exactly
    one row (missing data, or a tie not resolved by a single winnerCode).
    """
    if winner_player_id is not None:
        matches = [r for r in player_event_rows if r["player_id"] == winner_player_id]
        return matches[0]["total_score"] if len(matches) == 1 else None

    rank1 = [r for r in player_event_rows if r["finish_position_numeric"] == 1]
    return rank1[0]["total_score"] if len(rank1) == 1 else None
