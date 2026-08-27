"""Immutable BETA #001-R1 snapshot — same append-only, never-overwrite
discipline as klpga.neo_win.archive (PRE), written to the SAME
neo_win_predictions/ directory (reusing its generic, dataclass-agnostic
`archive_paths`/`archive_filename_stem` path helpers directly — a
different `prediction_id` string, e.g. "001-R1", naturally produces a
different filename, so PRE (`neo_win_001_<game_code>.json`) and this
round update (`neo_win_001-R1_<game_code>.json`) can never collide or
overwrite each other) but with its OWN dataclass shape (R1 score/
position, strokes behind leader, and 5 outcome probabilities per
player instead of PRE's single win_probability) and its OWN atomic
writer, so writing an R1 snapshot can never touch PRE's code path.
"""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from klpga.neo_win.archive import NeoWinAlreadyArchivedError, archive_paths

RECORD_KIND = "neo_win_beta_round_update_v1"
MODEL_VERSION = "v0.1"


@dataclass(frozen=True)
class RoundUpdateEntrantSnapshot:
    player_code: str
    player_name: str
    pre_win_probability: Optional[float]
    r1_score_to_par: Optional[float]
    r1_position: Optional[int]
    strokes_behind_leader: Optional[float]
    post_r1_win_pct: Optional[float]
    post_r1_top5_pct: Optional[float]
    post_r1_top10_pct: Optional[float]
    post_r1_top20_pct: Optional[float]
    post_r1_make_cut_pct: Optional[float]
    probability_change_from_pre: Optional[float]
    missing_r1_data: bool = False


@dataclass(frozen=True)
class RoundUpdateSnapshot:
    prediction_id: str
    created_at_utc: str
    record_kind: str
    game_code: str
    tournament_name: Optional[str]
    pre_prediction_id: str
    pre_cutoff_date: str
    round_number: int
    cut_fraction_used: float
    cut_format: str
    n_simulations: int
    field_size: int
    entrants_scored: int
    missing_r1_players: tuple[str, ...]
    win_probability_sum_pct: float
    leakage_check: dict
    known_limitations: tuple[str, ...]
    predictions: tuple[RoundUpdateEntrantSnapshot, ...] = field(default_factory=tuple)


def snapshot_to_dict(snapshot: RoundUpdateSnapshot) -> dict:
    return {
        "prediction_id": snapshot.prediction_id,
        "created_at_utc": snapshot.created_at_utc,
        "record_kind": snapshot.record_kind,
        "game_code": snapshot.game_code,
        "tournament_name": snapshot.tournament_name,
        "pre_prediction_id": snapshot.pre_prediction_id,
        "pre_cutoff_date": snapshot.pre_cutoff_date,
        "round_number": snapshot.round_number,
        "cut_fraction_used": snapshot.cut_fraction_used,
        "cut_format": snapshot.cut_format,
        "n_simulations": snapshot.n_simulations,
        "field_size": snapshot.field_size,
        "entrants_scored": snapshot.entrants_scored,
        "missing_r1_players": list(snapshot.missing_r1_players),
        "win_probability_sum_pct": snapshot.win_probability_sum_pct,
        "leakage_check": dict(snapshot.leakage_check),
        "known_limitations": list(snapshot.known_limitations),
        "predictions": [
            {
                "player_code": e.player_code,
                "player_name": e.player_name,
                "pre_win_probability": e.pre_win_probability,
                "r1_score_to_par": e.r1_score_to_par,
                "r1_position": e.r1_position,
                "strokes_behind_leader": e.strokes_behind_leader,
                "post_r1_win_pct": e.post_r1_win_pct,
                "post_r1_top5_pct": e.post_r1_top5_pct,
                "post_r1_top10_pct": e.post_r1_top10_pct,
                "post_r1_top20_pct": e.post_r1_top20_pct,
                "post_r1_make_cut_pct": e.post_r1_make_cut_pct,
                "probability_change_from_pre": e.probability_change_from_pre,
                "missing_r1_data": e.missing_r1_data,
            }
            for e in snapshot.predictions
        ],
    }


def snapshot_to_json_text(snapshot: RoundUpdateSnapshot) -> str:
    return json.dumps(snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n"


_CSV_FIELDNAMES: tuple[str, ...] = (
    "player_code", "player_name", "pre_win_probability", "r1_score_to_par", "r1_position",
    "strokes_behind_leader", "post_r1_win_pct", "post_r1_top5_pct", "post_r1_top10_pct",
    "post_r1_top20_pct", "post_r1_make_cut_pct", "probability_change_from_pre", "missing_r1_data",
)


def _entrants_csv_bytes(snapshot: RoundUpdateSnapshot) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDNAMES)
    writer.writeheader()
    for e in snapshot.predictions:
        writer.writerow(
            {name: ("" if getattr(e, name) is None else getattr(e, name)) for name in _CSV_FIELDNAMES}
        )
    return buf.getvalue().encode("utf-8-sig")


def _atomic_claim(content_bytes: bytes, final_path: Path) -> None:
    final_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(final_path.parent), suffix=final_path.suffix + ".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content_bytes)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(tmp_path, final_path)
        except FileExistsError as exc:
            raise NeoWinAlreadyArchivedError(
                f"{final_path} already exists — the archive is append-only and is never overwritten."
            ) from exc
        except (OSError, NotImplementedError) as exc:
            if final_path.exists():
                raise NeoWinAlreadyArchivedError(
                    f"{final_path} already exists — the archive is append-only and is never overwritten."
                ) from exc
            os.replace(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def write_round_update_snapshot_atomic(snapshot: RoundUpdateSnapshot, predictions_root: Path) -> tuple[Path, Path]:
    """Same immutability guarantee as klpga.neo_win.archive.write_neo_
    win_snapshot_atomic — writes NOTHING if either target already
    exists. Never touches, opens, or depends on the PRE snapshot's own
    files at all."""
    json_path, csv_path = archive_paths(predictions_root, snapshot.prediction_id, snapshot.game_code, snapshot.pre_cutoff_date)
    json_bytes = snapshot_to_json_text(snapshot).encode("utf-8")
    csv_bytes = _entrants_csv_bytes(snapshot)

    _atomic_claim(json_bytes, json_path)
    try:
        _atomic_claim(csv_bytes, csv_path)
    except NeoWinAlreadyArchivedError:
        raise
    except Exception as exc:  # noqa: BLE001 - deliberately broad, re-raised with context
        raise RuntimeError(
            f"JSON archived successfully at {json_path}, but the CSV write failed at {csv_path}: {exc}."
        ) from exc

    return json_path, csv_path
