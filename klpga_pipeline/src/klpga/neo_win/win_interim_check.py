"""BETA #001 R1 WIN% -> R2 interim leaderboard check.

======================================================================
INTERIM CHECK — NOT FINAL WIN PROBABILITY EVALUATION
======================================================================
This module NEVER scores WIN% as a final, resolved prediction. A
tournament is not decided at R2 — this only asks "does the frozen R1
WIN% ranking still look directionally sane against where the field
actually stands after R2." Final WIN probability scoring (Brier/log
loss against the real eventual winner) belongs to a FINAL-stage
evaluation, not this module, and must wait until the tournament is
actually over. Every summary this module returns is labeled
`"INTERIM CHECK — NOT FINAL WIN PROBABILITY EVALUATION"` so no caller
can present it as something it isn't.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

INTERIM_CHECK_LABEL = "INTERIM CHECK — NOT FINAL WIN PROBABILITY EVALUATION"


@dataclass(frozen=True)
class PlayerWinInterimRow:
    player_code: str
    player_name: str
    r1_win_rank: int
    """This player's rank when the frozen R1 field is sorted by
    post_r1_win_pct descending (1 = highest WIN%)."""
    r1_win_pct: float
    r2_leaderboard_position: Optional[int]
    """Real R2 leaderboard position (numeric rank after R2), None if
    the player has no resolvable R2 position (WD/DQ/unresolved) —
    never guessed."""


def spearman_rank_correlation(rows: list[PlayerWinInterimRow]) -> Optional[float]:
    """Standard Spearman rank correlation between r1_win_rank and
    r2_leaderboard_position, over players with a real, resolvable R2
    position only. Returns None if fewer than 2 such players (a
    correlation needs at least 2 points, and is degenerate/undefined
    below that — never a fabricated 0.0 or 1.0)."""
    pairs = [(r.r1_win_rank, r.r2_leaderboard_position) for r in rows if r.r2_leaderboard_position is not None]
    n = len(pairs)
    if n < 2:
        return None
    d_squared_sum = sum((a - b) ** 2 for a, b in pairs)
    if n == 1:
        return None
    denom = n * (n * n - 1)
    if denom == 0:
        return None
    return 1 - (6 * d_squared_sum) / denom


def top_n_still_in_contention(rows: list[PlayerWinInterimRow], n: int, contention_threshold: int) -> dict:
    """Among the R1 WIN% top-N players, how many still have a real R2
    leaderboard position at or better than `contention_threshold`
    (e.g. top 20). Players with no resolvable R2 position (WD/DQ/
    unresolved) are reported separately, never counted as "out of
    contention" by assumption."""
    top_n = sorted(rows, key=lambda r: r.r1_win_rank)[:n]
    still_in = [r for r in top_n if r.r2_leaderboard_position is not None and r.r2_leaderboard_position <= contention_threshold]
    fallen_out = [
        r for r in top_n
        if r.r2_leaderboard_position is not None and r.r2_leaderboard_position > contention_threshold
    ]
    unresolved = [r for r in top_n if r.r2_leaderboard_position is None]
    return {
        "r1_win_top_n": n,
        "contention_threshold": contention_threshold,
        "n_players": len(top_n),
        "still_in_contention": [r.player_code for r in still_in],
        "fallen_out_of_contention": [r.player_code for r in fallen_out],
        "unresolved": [r.player_code for r in unresolved],
    }


def biggest_movements(rows: list[PlayerWinInterimRow], n: int = 5) -> dict:
    """(biggest_risers, biggest_fallers) by (r1_win_rank - r2_leaderboard_
    position) — a positive value means the player moved UP the
    leaderboard relative to their R1 WIN% rank. Players with no
    resolvable R2 position are excluded (never assigned a fabricated
    movement). Ties broken deterministically by player_code."""
    resolvable = [r for r in rows if r.r2_leaderboard_position is not None]
    with_movement = [(r, r.r1_win_rank - r.r2_leaderboard_position) for r in resolvable]
    risers = sorted(with_movement, key=lambda t: (-t[1], t[0].player_code))[:n]
    fallers = sorted(with_movement, key=lambda t: (t[1], t[0].player_code))[:n]
    return {
        "biggest_risers": [{"player_code": r.player_code, "player_name": r.player_name, "movement": m} for r, m in risers],
        "biggest_fallers": [{"player_code": r.player_code, "player_name": r.player_name, "movement": m} for r, m in fallers],
    }


def win_interim_summary(rows: list[PlayerWinInterimRow]) -> dict:
    return {
        "label": INTERIM_CHECK_LABEL,
        "n_r1_players": len(rows),
        "n_with_resolved_r2_position": sum(1 for r in rows if r.r2_leaderboard_position is not None),
        "spearman_rank_correlation": spearman_rank_correlation(rows),
        "top5": top_n_still_in_contention(rows, n=5, contention_threshold=20),
        "top10": top_n_still_in_contention(rows, n=10, contention_threshold=20),
        "movements": biggest_movements(rows),
    }
