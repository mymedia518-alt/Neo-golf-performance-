"""Tournament-independent official KLPGA round ingest."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from klpga.collectors.group_page import fetch_group_page_html
from klpga.collectors.leaderboard import fetch_round_leaderboard
from klpga.http_client import PoliteHttpClient
from klpga.parsers.group_page_parser import parse_round_grouping
from klpga.parsers.round_progress import resolve_round_progress


class OfficialIngestBlocked(RuntimeError):
    """Official facts cannot be published safely."""


@dataclass(frozen=True)
class OfficialPlayerRound:
    player_id: str
    player_name: str | None
    rank_display: str | None
    status: str
    raw_inghole: object
    holes_completed: int | None
    holes_completed_display: str | None
    starting_tee_assumed: bool | None
    today_under_par_display: str | None
    total_under_par_display: str | None


@dataclass(frozen=True)
class OfficialRoundSnapshot:
    game_code: str
    round_number: int
    players: tuple[OfficialPlayerRound, ...]

    @property
    def row_count(self) -> int:
        return len(self.players)


def reconcile_official_round(
    *,
    game_code: str,
    round_number: int,
    leaderboard_rows: Iterable,
    grouping_rows: Iterable,
    progress_resolver: Callable = resolve_round_progress,
) -> OfficialRoundSnapshot:
    """Reconcile official leaderboard and grouping facts without guessing."""

    if not str(game_code).strip():
        raise ValueError("game_code required")

    if round_number < 1:
        raise ValueError("round_number must be >= 1")

    rows = tuple(leaderboard_rows)
    groups = tuple(grouping_rows)

    if not rows:
        raise OfficialIngestBlocked(
            "official leaderboard returned zero rows"
        )

    if not groups:
        raise OfficialIngestBlocked(
            "official grouping returned zero rows"
        )

    ids = [
        str(getattr(r, "player_code", "") or "")
        for r in rows
    ]

    if any(not player_id for player_id in ids):
        raise OfficialIngestBlocked(
            "official leaderboard contains missing player identity"
        )

    if len(ids) != len(set(ids)):
        raise OfficialIngestBlocked(
            "official leaderboard contains duplicate player identity"
        )

    grouping_ids = {
        str(g.player_code)
        for g in groups
        if getattr(g, "player_code", None) is not None
    }

    progress = progress_resolver(rows, groups)
    output = []

    for row in rows:
        player_id = str(row.player_code)
        status = str(
            getattr(row, "status", None) or "ACTIVE"
        ).strip().upper()

        resolved = progress.get(player_id)
        has_grouping = player_id in grouping_ids

        if not has_grouping:
            if status != "INCOMPLETE":
                raise OfficialIngestBlocked(
                    "missing official grouping for "
                    f"non-INCOMPLETE player {player_id}"
                )

            holes_completed = None
            holes_display = None
            assumed = None

        else:
            if resolved is None:
                raise OfficialIngestBlocked(
                    f"missing round progress for {player_id}"
                )

            if resolved.assumed_default_start:
                raise OfficialIngestBlocked(
                    f"unverified starting tee for {player_id}"
                )

            holes_completed = resolved.completed
            holes_display = resolved.display
            assumed = False

        incomplete = status == "INCOMPLETE"

        output.append(
            OfficialPlayerRound(
                player_id=player_id,
                player_name=getattr(
                    row,
                    "player_name",
                    None,
                ),
                rank_display=(
                    None
                    if incomplete
                    else getattr(
                        row,
                        "rank_display",
                        None,
                    )
                ),
                status=status,
                raw_inghole=getattr(
                    row,
                    "holes_completed",
                    None,
                ),
                holes_completed=holes_completed,
                holes_completed_display=holes_display,
                starting_tee_assumed=assumed,
                today_under_par_display=(
                    None
                    if incomplete
                    else getattr(
                        row,
                        "today_under_par_display",
                        None,
                    )
                ),
                total_under_par_display=(
                    None
                    if incomplete
                    else getattr(
                        row,
                        "total_under_par_display",
                        None,
                    )
                ),
            )
        )

    return OfficialRoundSnapshot(
        game_code=str(game_code),
        round_number=round_number,
        players=tuple(output),
    )


def fetch_official_round(
    *,
    game_code: str,
    round_number: int,
    cache_dir: Path,
) -> OfficialRoundSnapshot:
    """Fresh official fetch. No tournament-specific game code or round."""

    client = PoliteHttpClient(
        cache_dir=Path(cache_dir)
    )

    rows = fetch_round_leaderboard(
        client,
        game_code,
        round_number,
        use_cache=False,
    )

    status_code, group_html = fetch_group_page_html(
        client,
        game_code,
    )

    if status_code != 200:
        raise OfficialIngestBlocked(
            f"group page HTTP {status_code}"
        )

    groups = parse_round_grouping(
        group_html,
        round_number,
    )

    return reconcile_official_round(
        game_code=game_code,
        round_number=round_number,
        leaderboard_rows=rows,
        grouping_rows=groups,
    )
