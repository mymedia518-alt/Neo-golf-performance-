"""Generic tournament discovery and validated config construction.

Discovery chooses tournament identity from persisted tournament data.
It does NOT infer lifecycle state from calendar dates.

Lifecycle fields remain validation-owned until an official-state
validator supplies a newer validated state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import sqlite3
from typing import Any


class TournamentDiscoveryBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class DiscoveredTournament:
    game_code: str
    tournament_name: str
    season: int
    start_date: str
    end_date: str
    rounds_scheduled: int | None


def _parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise TournamentDiscoveryBlocked(
            f"invalid tournament date: {value!r}"
        ) from exc


def discover_tournament(
    db_path: Path,
    *,
    as_of: date,
) -> DiscoveredTournament:
    if not db_path.exists():
        raise TournamentDiscoveryBlocked(
            f"database missing: {db_path}"
        )

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    try:
        rows = con.execute(
            """
            SELECT
                game_code,
                event_name,
                season,
                start_date,
                end_date,
                rounds_scheduled
            FROM tournament_master
            WHERE game_code IS NOT NULL
              AND event_name IS NOT NULL
              AND start_date IS NOT NULL
              AND end_date IS NOT NULL
            """
        ).fetchall()
    finally:
        con.close()

    candidates = []

    for row in rows:
        start = _parse_iso_date(row["start_date"])
        end = _parse_iso_date(row["end_date"])

        if start <= as_of <= end:
            candidates.append(row)

    if not candidates:
        raise TournamentDiscoveryBlocked(
            f"no active tournament for {as_of.isoformat()}"
        )

    if len(candidates) != 1:
        codes = sorted(str(r["game_code"]) for r in candidates)
        raise TournamentDiscoveryBlocked(
            "ambiguous active tournaments: " + ",".join(codes)
        )

    row = candidates[0]

    rounds = row["rounds_scheduled"]
    if rounds is not None:
        rounds = int(rounds)
        if rounds < 2:
            raise TournamentDiscoveryBlocked(
                "invalid rounds_scheduled"
            )

    return DiscoveredTournament(
        game_code=str(row["game_code"]),
        tournament_name=str(row["event_name"]),
        season=int(row["season"]),
        start_date=str(row["start_date"]),
        end_date=str(row["end_date"]),
        rounds_scheduled=rounds,
    )


def build_validated_config(
    tournament: DiscoveredTournament,
    *,
    previous_config: dict[str, Any],
) -> dict[str, Any]:
    """Bind discovered identity to validation-owned lifecycle state.

    This function intentionally refuses to invent final round,
    current round, cut round, stage, or model readiness.
    """

    previous_game = str(
        previous_config.get("game_code", "")
    )

    if previous_game != tournament.game_code:
        raise TournamentDiscoveryBlocked(
            "new tournament discovered but no validated lifecycle "
            "state exists for that game_code"
        )

    required = (
        "final_round_number",
        "current_round_number",
        "validated_stage",
        "cut_after_round",
        "model_ready",
    )

    missing = [
        key for key in required
        if key not in previous_config
    ]

    if missing:
        raise TournamentDiscoveryBlocked(
            "validated lifecycle fields missing: "
            + ",".join(missing)
        )

    final_round = int(
        previous_config["final_round_number"]
    )

    current_round = int(
        previous_config["current_round_number"]
    )

    if final_round < 2:
        raise TournamentDiscoveryBlocked(
            "invalid validated final_round_number"
        )

    if not 1 <= current_round <= final_round:
        raise TournamentDiscoveryBlocked(
            "invalid validated current_round_number"
        )

    cut_after = previous_config["cut_after_round"]
    if cut_after is not None:
        cut_after = int(cut_after)
        if not 1 <= cut_after < final_round:
            raise TournamentDiscoveryBlocked(
                "invalid validated cut_after_round"
            )

    if (
        tournament.rounds_scheduled is not None
        and tournament.rounds_scheduled != final_round
    ):
        raise TournamentDiscoveryBlocked(
            "round-count conflict between discovery and validation"
        )

    return {
        "schema_version": 2,
        "game_code": tournament.game_code,
        "tournament_name": tournament.tournament_name,
        "season": tournament.season,
        "start_date": tournament.start_date,
        "end_date": tournament.end_date,
        "final_round_number": final_round,
        "current_round_number": current_round,
        "validated_stage": str(
            previous_config["validated_stage"]
        ),
        "cut_after_round": cut_after,
        "model_ready": bool(
            previous_config["model_ready"]
        ),
        "identity_source": "tournament_master",
        "lifecycle_source": "validated_state",
    }


def refresh_active_config(
    *,
    db_path: Path,
    config_path: Path,
    as_of: date,
) -> dict[str, Any]:
    previous = json.loads(
        config_path.read_text(encoding="utf-8-sig")
    )

    tournament = discover_tournament(
        db_path,
        as_of=as_of,
    )

    payload = build_validated_config(
        tournament,
        previous_config=previous,
    )

    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    tmp = config_path.with_suffix(
        config_path.suffix + ".tmp"
    )

    tmp.write_text(
        encoded,
        encoding="utf-8",
    )

    tmp.replace(config_path)

    return payload
