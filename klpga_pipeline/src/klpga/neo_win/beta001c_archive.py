"""Immutable PRE-tournament snapshot for BETA #001-C — same atomic,
append-only, never-overwrite discipline as `klpga.neo_win.archive`
(BETA #001's own archive) and `klpga.archive.prediction_archive`
(Prediction #001's), reimplemented self-contained here so #001-C
writing can NEVER affect, and reading here never depends on, either of
those — a hard requirement of this release ("DO NOT: modify BETA #001,
overwrite prediction_id=001").

Writes to `neo_win_c_predictions/<year>/neo_win_c_<prediction_id>_<game_code>.json`
+ `.csv` — a directory of its own, sibling to (never inside) both
`predictions/` and `neo_win_predictions/`.

`NeoWinCEntrantSnapshot.feature_values` is a plain {feature_name: value
or None} dict rather than a fixed set of dataclass fields — the actual
selected model (MODEL_A, MODEL_B, or MODEL_C, see klpga.neo_win.
backtest_eval.select_best_beta001c_model) determines which feature
names are meaningful for a given run, decided by real backtest
evidence, never hardcoded here."""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

RECORD_KIND = "neo_win_beta001c_prediction_v1"


class NeoWinCAlreadyArchivedError(RuntimeError):
    """A (prediction_id, game_code) BETA #001-C snapshot already
    exists — the archive is append-only; this is the only way a
    duplicate is ever handled."""


@dataclass(frozen=True)
class NeoWinCEntrantSnapshot:
    rank: int
    player_code: str
    player_name: str
    win_probability: float
    prior_events_n: int
    feature_values: dict = field(default_factory=dict)
    player_master_matched: bool = True


@dataclass(frozen=True)
class NeoWinCPredictionSnapshot:
    prediction_id: str
    created_at_utc: str
    record_kind: str
    game_code: str
    tournament_name: Optional[str]
    cutoff_date: str
    cutoff_source: str
    selected_model_id: str
    model_features: tuple[str, ...]
    selection_decision: dict
    training_tournament_count: int
    field_size: int
    entrants_predicted: int
    probability_sum: float
    minimum_probability: float
    maximum_probability: float
    duplicate_count: int
    null_count: int
    non_field_count: int
    known_limitations: tuple[str, ...]
    predictions: tuple[NeoWinCEntrantSnapshot, ...] = field(default_factory=tuple)


def snapshot_to_dict(snapshot: NeoWinCPredictionSnapshot) -> dict:
    return {
        "prediction_id": snapshot.prediction_id,
        "created_at_utc": snapshot.created_at_utc,
        "record_kind": snapshot.record_kind,
        "game_code": snapshot.game_code,
        "tournament_name": snapshot.tournament_name,
        "cutoff_date": snapshot.cutoff_date,
        "cutoff_source": snapshot.cutoff_source,
        "selected_model_id": snapshot.selected_model_id,
        "model_features": list(snapshot.model_features),
        "selection_decision": snapshot.selection_decision,
        "training_tournament_count": snapshot.training_tournament_count,
        "field_size": snapshot.field_size,
        "entrants_predicted": snapshot.entrants_predicted,
        "probability_sum": snapshot.probability_sum,
        "minimum_probability": snapshot.minimum_probability,
        "maximum_probability": snapshot.maximum_probability,
        "duplicate_count": snapshot.duplicate_count,
        "null_count": snapshot.null_count,
        "non_field_count": snapshot.non_field_count,
        "known_limitations": list(snapshot.known_limitations),
        "predictions": [
            {
                "rank": e.rank,
                "player_code": e.player_code,
                "player_name": e.player_name,
                "win_probability": e.win_probability,
                "prior_events_n": e.prior_events_n,
                "feature_values": dict(e.feature_values),
                "player_master_matched": e.player_master_matched,
            }
            for e in snapshot.predictions
        ],
    }


def snapshot_to_json_text(snapshot: NeoWinCPredictionSnapshot) -> str:
    return json.dumps(snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n"


def read_neo_win_c_snapshot(path: Path) -> NeoWinCPredictionSnapshot:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entrants = tuple(
        NeoWinCEntrantSnapshot(
            rank=row["rank"],
            player_code=row["player_code"],
            player_name=row["player_name"],
            win_probability=row["win_probability"],
            prior_events_n=row["prior_events_n"],
            feature_values=row.get("feature_values", {}),
            player_master_matched=row["player_master_matched"],
        )
        for row in data["predictions"]
    )
    return NeoWinCPredictionSnapshot(
        prediction_id=data["prediction_id"],
        created_at_utc=data["created_at_utc"],
        record_kind=data["record_kind"],
        game_code=data["game_code"],
        tournament_name=data["tournament_name"],
        cutoff_date=data["cutoff_date"],
        cutoff_source=data["cutoff_source"],
        selected_model_id=data["selected_model_id"],
        model_features=tuple(data["model_features"]),
        selection_decision=data["selection_decision"],
        training_tournament_count=data["training_tournament_count"],
        field_size=data["field_size"],
        entrants_predicted=data["entrants_predicted"],
        probability_sum=data["probability_sum"],
        minimum_probability=data["minimum_probability"],
        maximum_probability=data["maximum_probability"],
        duplicate_count=data["duplicate_count"],
        null_count=data["null_count"],
        non_field_count=data["non_field_count"],
        known_limitations=tuple(data["known_limitations"]),
        predictions=entrants,
    )


def _entrants_csv_bytes(snapshot: NeoWinCPredictionSnapshot) -> bytes:
    feature_names = list(snapshot.model_features)
    fieldnames = ["rank", "player_code", "player_name", "win_probability", "prior_events_n"] + feature_names + [
        "player_master_matched"
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for e in snapshot.predictions:
        row = {
            "rank": e.rank,
            "player_code": e.player_code,
            "player_name": e.player_name,
            "win_probability": e.win_probability,
            "prior_events_n": e.prior_events_n,
            "player_master_matched": e.player_master_matched,
        }
        for name in feature_names:
            value = e.feature_values.get(name)
            row[name] = "" if value is None else value
        writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")


def archive_filename_stem(prediction_id: str, game_code: str) -> str:
    return f"neo_win_c_{prediction_id}_{game_code}"


def archive_paths(predictions_root: Path, prediction_id: str, game_code: str, cutoff_date: str) -> tuple[Path, Path]:
    year = cutoff_date[:4]
    target_dir = Path(predictions_root) / year
    stem = archive_filename_stem(prediction_id, game_code)
    return target_dir / f"{stem}.json", target_dir / f"{stem}.csv"


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
            raise NeoWinCAlreadyArchivedError(
                f"{final_path} already exists — the archive is append-only and is never overwritten."
            ) from exc
        except (OSError, NotImplementedError) as exc:
            if final_path.exists():
                raise NeoWinCAlreadyArchivedError(
                    f"{final_path} already exists — the archive is append-only and is never overwritten."
                ) from exc
            os.replace(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def write_neo_win_c_snapshot_atomic(snapshot: NeoWinCPredictionSnapshot, predictions_root: Path) -> tuple[Path, Path]:
    json_path, csv_path = archive_paths(predictions_root, snapshot.prediction_id, snapshot.game_code, snapshot.cutoff_date)
    json_bytes = snapshot_to_json_text(snapshot).encode("utf-8")
    csv_bytes = _entrants_csv_bytes(snapshot)

    _atomic_claim(json_bytes, json_path)
    try:
        _atomic_claim(csv_bytes, csv_path)
    except NeoWinCAlreadyArchivedError:
        raise
    except Exception as exc:  # noqa: BLE001 - deliberately broad, re-raised with context
        raise RuntimeError(
            f"JSON archived successfully at {json_path}, but the CSV write failed at {csv_path}: {exc}. "
            "The JSON is authoritative and already immutable; regenerate the CSV separately."
        ) from exc

    return json_path, csv_path
