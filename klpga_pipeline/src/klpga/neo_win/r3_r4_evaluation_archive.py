"""Append-only archive for BETA #001 FINAL validation's R3->R4
evaluation records -- self-contained, ZERO code coupling to
`klpga.neo_win.tournament_history` / `klpga.neo_win.archive` /
`klpga.neo_win.beta001c_archive` (same convention those three already
established with each other: writing here can never affect, and
reading here never depends on, any of them). `klpga.neo_win.
tournament_history`'s own schema is deliberately NOT extended for this
-- it has no generic metadata field to carry this record's provenance
(source_pre_snapshot_sha256, source_r1_r2_r3_made_cut_input_sha256)
honestly, so this is a wholly separate, purpose-built archive instead.

Writes to `neo_r3_r4_evaluation/<game_code>/<prediction_id>_R3_TO_R4.json`
-- a directory of its own, sibling to (never inside) `neo_tournament_
history/`, `neo_win_predictions/`, and `neo_win_c_predictions/`.

======================================================================
#002 REUSE
======================================================================
`prediction_id` (not just `game_code`) is part of the storage path, so
a future #002 evaluation of the SAME real tournament is a SIBLING
record under the same directory/schema -- never a collision, always
directly comparable. `read_all_evaluations` is the intended baseline-
dataset loader for that future research code.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from klpga.neo_win.r3_r4_evaluation import PlayerR3R4Evaluation

RECORD_KIND = "neo_r3_r4_evaluation_v1"
STAGE_TRANSITION_R3_TO_R4 = "R3_TO_R4"


class R3R4EvaluationAlreadyRecordedError(RuntimeError):
    """A (game_code, prediction_id, stage_transition) evaluation record
    already exists -- the archive is append-only; this is the only way
    a duplicate is ever handled. Never silently overwritten."""


@dataclass(frozen=True)
class R3R4EvaluationSnapshot:
    game_code: str
    prediction_id: str
    stage_transition: str
    record_kind: str
    recorded_at_utc: str
    source_pre_snapshot_path: str
    source_pre_snapshot_sha256: str
    source_r1_r2_r3_made_cut_input_sha256: str
    aggregate: dict
    rows: tuple[PlayerR3R4Evaluation, ...] = field(default_factory=tuple)
    known_limitations: tuple[str, ...] = field(default_factory=tuple)


def _row_to_dict(r: PlayerR3R4Evaluation) -> dict:
    return {
        "player_code": r.player_code, "player_name": r.player_name,
        "r3_total_score_to_par": r.r3_total_score_to_par,
        "expected_r4_score_to_par": r.expected_r4_score_to_par, "r4_spread": r.r4_spread,
        "actual_r4_score_to_par": r.actual_r4_score_to_par,
        "prediction_error": r.prediction_error, "absolute_error": r.absolute_error, "z_score": r.z_score,
    }


def _row_from_dict(d: dict) -> PlayerR3R4Evaluation:
    return PlayerR3R4Evaluation(
        player_code=d["player_code"], player_name=d["player_name"],
        r3_total_score_to_par=d["r3_total_score_to_par"],
        expected_r4_score_to_par=d["expected_r4_score_to_par"], r4_spread=d["r4_spread"],
        actual_r4_score_to_par=d.get("actual_r4_score_to_par"),
        prediction_error=d.get("prediction_error"), absolute_error=d.get("absolute_error"),
        z_score=d.get("z_score"),
    )


def snapshot_to_dict(snapshot: R3R4EvaluationSnapshot) -> dict:
    return {
        "game_code": snapshot.game_code,
        "prediction_id": snapshot.prediction_id,
        "stage_transition": snapshot.stage_transition,
        "record_kind": snapshot.record_kind,
        "recorded_at_utc": snapshot.recorded_at_utc,
        "source_pre_snapshot_path": snapshot.source_pre_snapshot_path,
        "source_pre_snapshot_sha256": snapshot.source_pre_snapshot_sha256,
        "source_r1_r2_r3_made_cut_input_sha256": snapshot.source_r1_r2_r3_made_cut_input_sha256,
        "aggregate": dict(snapshot.aggregate),
        "rows": [_row_to_dict(r) for r in snapshot.rows],
        "known_limitations": list(snapshot.known_limitations),
    }


def snapshot_from_dict(data: dict) -> R3R4EvaluationSnapshot:
    return R3R4EvaluationSnapshot(
        game_code=data["game_code"],
        prediction_id=data["prediction_id"],
        stage_transition=data["stage_transition"],
        record_kind=data["record_kind"],
        recorded_at_utc=data["recorded_at_utc"],
        source_pre_snapshot_path=data["source_pre_snapshot_path"],
        source_pre_snapshot_sha256=data["source_pre_snapshot_sha256"],
        source_r1_r2_r3_made_cut_input_sha256=data["source_r1_r2_r3_made_cut_input_sha256"],
        aggregate=data["aggregate"],
        rows=tuple(_row_from_dict(r) for r in data.get("rows", [])),
        known_limitations=tuple(data.get("known_limitations", ())),
    )


def evaluation_path(archive_root: Path, game_code: str, prediction_id: str) -> Path:
    return Path(archive_root) / game_code / f"{prediction_id}_{STAGE_TRANSITION_R3_TO_R4}.json"


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
            raise R3R4EvaluationAlreadyRecordedError(
                f"{final_path} already exists -- this archive is append-only and is never overwritten."
            ) from exc
        except (OSError, NotImplementedError) as exc:
            if final_path.exists():
                raise R3R4EvaluationAlreadyRecordedError(
                    f"{final_path} already exists -- this archive is append-only and is never overwritten."
                ) from exc
            os.replace(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def write_evaluation_atomic(snapshot: R3R4EvaluationSnapshot, archive_root: Path) -> Path:
    path = evaluation_path(archive_root, snapshot.game_code, snapshot.prediction_id)
    content = (json.dumps(snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    _atomic_claim(content, path)
    return path


def read_evaluation(path: Path) -> R3R4EvaluationSnapshot:
    return snapshot_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def read_all_evaluations(archive_root: Path, game_code: Optional[str] = None) -> list[R3R4EvaluationSnapshot]:
    """Loader for #002 (or any future) research code -- returns every
    recorded R3->R4 evaluation under `archive_root`, optionally
    restricted to one `game_code`. Read-only; never writes."""
    archive_root = Path(archive_root)
    if not archive_root.exists():
        return []
    pattern = f"{game_code}/*_{STAGE_TRANSITION_R3_TO_R4}.json" if game_code else f"*/*_{STAGE_TRANSITION_R3_TO_R4}.json"
    return [read_evaluation(p) for p in sorted(archive_root.glob(pattern))]
