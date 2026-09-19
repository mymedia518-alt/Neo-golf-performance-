"""NEO STANDARD ARTIFACT (POST_TOURNAMENT_REPORT) -- generic "biggest
movers" computation: given any two stage snapshots of a per-player win
probability (e.g. PRE vs FINAL, or any two adjacent rounds), rank
players by the signed change and split into the top-N risers and
top-N fallers.

Tour/tournament-agnostic: takes plain dict[player_id, float] inputs
and a name lookup, no game_code/date/player-name literals. A player
present in only one of the two snapshots is skipped (never fabricates
a 0.0 for a missing side -- that would misrepresent "not in the
field" as "predicted at 0%").
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProbabilityMover:
    player_id: str
    player_name: str
    before_pct: float
    after_pct: float
    delta_pct: float


@dataclass(frozen=True)
class MoversReport:
    before_label: str
    after_label: str
    risers: tuple[ProbabilityMover, ...]
    fallers: tuple[ProbabilityMover, ...]


def compute_probability_movers(
    before: dict[str, float],
    after: dict[str, float],
    names: dict[str, str],
    *,
    before_label: str,
    after_label: str,
    top_n: int = 10,
) -> MoversReport:
    """Ranks by (after - before); ties broken by player_id for a
    stable, reproducible order. `before`/`after` are percentage points
    (0-100) on the same scale -- callers pass whatever probability
    metric they are comparing (win_pct, top5_pct, ...)."""
    shared_ids = sorted(set(before) & set(after))
    movers = [
        ProbabilityMover(
            player_id=pid,
            player_name=names.get(pid, pid),
            before_pct=before[pid],
            after_pct=after[pid],
            delta_pct=after[pid] - before[pid],
        )
        for pid in shared_ids
    ]
    risers = tuple(sorted(movers, key=lambda m: (-m.delta_pct, m.player_id))[:top_n])
    fallers = tuple(sorted(movers, key=lambda m: (m.delta_pct, m.player_id))[:top_n])
    return MoversReport(before_label=before_label, after_label=after_label, risers=risers, fallers=fallers)
