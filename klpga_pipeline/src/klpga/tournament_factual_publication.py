"""Immutable factual publication layer for NEO Tournament Engine."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from klpga.tournament_official_ingest import OfficialRoundSnapshot


class FactualPublicationBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class FrozenFactualRef:
    game_code: str
    round_number: int
    sha256: str
    path: Path
    row_count: int


def _canonical(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def build_factual_payload(
    snapshot: OfficialRoundSnapshot,
    *,
    collected_at: str | None = None,
) -> dict:
    if snapshot.row_count <= 0:
        raise FactualPublicationBlocked("zero-row snapshot")

    players = []

    for row in snapshot.players:
        if not row.player_id:
            raise FactualPublicationBlocked("missing player_id")

        players.append({
            "player_id": row.player_id,
            "player_name": row.player_name,
            "rank_display": row.rank_display,
            "status": row.status,
            "raw_inghole": row.raw_inghole,
            "holes_completed": row.holes_completed,
            "holes_completed_display": row.holes_completed_display,
            "starting_tee_assumed": row.starting_tee_assumed,
            "today_under_par_display": row.today_under_par_display,
            "total_under_par_display": row.total_under_par_display,
        })

    ids = [p["player_id"] for p in players]

    if len(ids) != len(set(ids)):
        raise FactualPublicationBlocked("duplicate player_id")

    if any(
        p["starting_tee_assumed"] is True
        for p in players
    ):
        raise FactualPublicationBlocked(
            "assumed starting tee cannot be published"
        )

    if collected_at is None:
        collected_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    return {
        "schema_version": "neo_tournament_factual_v1",
        "game_code": snapshot.game_code,
        "round_number": snapshot.round_number,
        "collected_at": collected_at,
        "row_count": len(players),
        "model_data_included": False,
        "players": players,
    }


def freeze_factual_snapshot(
    snapshot: OfficialRoundSnapshot,
    *,
    output_root: Path,
    collected_at: str | None = None,
) -> FrozenFactualRef:
    payload = build_factual_payload(
        snapshot,
        collected_at=collected_at,
    )

    raw = _canonical(payload)
    digest = sha256(raw).hexdigest()

    directory = (
        Path(output_root)
        / snapshot.game_code
        / "factual"
        / f"round-{snapshot.round_number}"
    )
    directory.mkdir(parents=True, exist_ok=True)

    target = directory / f"{digest}.json"

    if target.exists():
        existing = target.read_bytes()
        if existing != raw:
            raise FactualPublicationBlocked(
                "immutable factual hash collision"
            )
    else:
        target.write_bytes(raw)

    return FrozenFactualRef(
        game_code=snapshot.game_code,
        round_number=snapshot.round_number,
        sha256=digest,
        path=target,
        row_count=snapshot.row_count,
    )


def verify_factual_snapshot(ref: FrozenFactualRef) -> dict:
    if not ref.path.exists():
        raise FactualPublicationBlocked(
            "factual snapshot missing"
        )

    raw = ref.path.read_bytes()

    if sha256(raw).hexdigest() != ref.sha256:
        raise FactualPublicationBlocked(
            "factual snapshot SHA mismatch"
        )

    payload = json.loads(raw.decode("utf-8"))

    if payload.get("game_code") != ref.game_code:
        raise FactualPublicationBlocked(
            "factual game_code mismatch"
        )

    if payload.get("round_number") != ref.round_number:
        raise FactualPublicationBlocked(
            "factual round mismatch"
        )

    if payload.get("row_count") != ref.row_count:
        raise FactualPublicationBlocked(
            "factual row_count mismatch"
        )

    if payload.get("model_data_included") is not False:
        raise FactualPublicationBlocked(
            "factual artifact contaminated by model data"
        )

    return payload


def build_publication_candidate(
    ref: FrozenFactualRef,
) -> dict:
    payload = verify_factual_snapshot(ref)

    return {
        "schema_version": "neo_publication_candidate_v1",
        "game_code": ref.game_code,
        "round_number": ref.round_number,
        "factual_snapshot_sha256": ref.sha256,
        "factual_snapshot_path": str(ref.path),
        "row_count": ref.row_count,
        "publish_factual": True,
        "publish_model": False,
        "validation": "PASS",
    }


def validate_publication_candidate(
    candidate: dict,
    ref: FrozenFactualRef,
) -> None:
    verify_factual_snapshot(ref)

    required = {
        "game_code": ref.game_code,
        "round_number": ref.round_number,
        "factual_snapshot_sha256": ref.sha256,
        "row_count": ref.row_count,
        "publish_factual": True,
        "validation": "PASS",
    }

    for key, expected in required.items():
        if candidate.get(key) != expected:
            raise FactualPublicationBlocked(
                f"candidate gate failed: {key}"
            )

    if candidate.get("publish_model") is not False:
        raise FactualPublicationBlocked(
            "model publication requires independent model gate"
        )
