"""Immutable PRE-tournament snapshot for NEO WIN v0.1 — same atomic,
append-only, never-overwrite discipline as `klpga.archive.
prediction_archive` (see that module's docstring for the full
rationale), reimplemented self-contained here rather than imported so
this new BETA archive has ZERO code coupling to the existing `Prediction
#001` archive: writing here can never affect, and reading here never
depends on, anything under `predictions/`.

Writes to `neo_win_predictions/<year>/neo_win_<prediction_id>_<game_code>.json`
+ `.csv` — a directory sibling to, and completely separate from,
`predictions/`.
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

RECORD_KIND = "neo_win_beta_prediction_v1"
MODEL_VERSION = "v0.1"


class NeoWinAlreadyArchivedError(RuntimeError):
    """A (prediction_id, game_code) NEO WIN snapshot already exists —
    the archive is append-only; this is the only way a duplicate is
    ever handled."""


@dataclass(frozen=True)
class NeoWinEntrantSnapshot:
    rank: int
    player_code: str
    player_name: str
    win_probability: float
    prior_events_n: int
    prior_avg_round_score_to_par: Optional[float]
    prior_recent_form_10: Optional[float]
    prior_recent_form_10_n: int
    neo_consistency_stddev: Optional[float]
    neo_consistency_stddev_n: int
    official_metrics: dict = field(default_factory=dict)
    """{slot_name: value or None} — see klpga.neo_win.official_metrics.
    OFFICIAL_METRIC_SLOTS for the slot names this run could use."""
    player_master_matched: bool = True


@dataclass(frozen=True)
class NeoWinPredictionSnapshot:
    prediction_id: str
    created_at_utc: str
    record_kind: str
    game_code: str
    tournament_name: Optional[str]
    cutoff_date: str
    cutoff_source: str
    model_id: str
    model_version: str
    model_features: tuple[str, ...]
    training_tournament_count: int
    field_size: int
    entrants_predicted: int
    dropped_entrants: int
    probability_sum: float
    minimum_probability: float
    maximum_probability: float
    zero_history_count: int
    unmatched_count: int
    official_metric_context: dict
    leakage_validation: dict
    missing_data_report: dict
    known_limitations: tuple[str, ...]
    predictions: tuple[NeoWinEntrantSnapshot, ...] = field(default_factory=tuple)


def snapshot_to_dict(snapshot: NeoWinPredictionSnapshot) -> dict:
    return {
        "prediction_id": snapshot.prediction_id,
        "created_at_utc": snapshot.created_at_utc,
        "record_kind": snapshot.record_kind,
        "game_code": snapshot.game_code,
        "tournament_name": snapshot.tournament_name,
        "cutoff_date": snapshot.cutoff_date,
        "cutoff_source": snapshot.cutoff_source,
        "model_id": snapshot.model_id,
        "model_version": snapshot.model_version,
        "model_features": list(snapshot.model_features),
        "training_tournament_count": snapshot.training_tournament_count,
        "field_size": snapshot.field_size,
        "entrants_predicted": snapshot.entrants_predicted,
        "dropped_entrants": snapshot.dropped_entrants,
        "probability_sum": snapshot.probability_sum,
        "minimum_probability": snapshot.minimum_probability,
        "maximum_probability": snapshot.maximum_probability,
        "zero_history_count": snapshot.zero_history_count,
        "unmatched_count": snapshot.unmatched_count,
        "official_metric_context": dict(snapshot.official_metric_context),
        "leakage_validation": dict(snapshot.leakage_validation),
        "missing_data_report": dict(snapshot.missing_data_report),
        "known_limitations": list(snapshot.known_limitations),
        "predictions": [
            {
                "rank": e.rank,
                "player_code": e.player_code,
                "player_name": e.player_name,
                "win_probability": e.win_probability,
                "prior_events_n": e.prior_events_n,
                "prior_avg_round_score_to_par": e.prior_avg_round_score_to_par,
                "prior_recent_form_10": e.prior_recent_form_10,
                "prior_recent_form_10_n": e.prior_recent_form_10_n,
                "neo_consistency_stddev": e.neo_consistency_stddev,
                "neo_consistency_stddev_n": e.neo_consistency_stddev_n,
                "official_metrics": dict(e.official_metrics),
                "player_master_matched": e.player_master_matched,
            }
            for e in snapshot.predictions
        ],
    }


def snapshot_to_json_text(snapshot: NeoWinPredictionSnapshot) -> str:
    return json.dumps(snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n"


def read_neo_win_snapshot(path: Path) -> NeoWinPredictionSnapshot:
    """Read-only: opens `path` for reading only, never writes back to
    it — used by klpga.neo_win.audit to load an already-frozen
    prediction without ever re-deriving it."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entrants = tuple(
        NeoWinEntrantSnapshot(
            rank=row["rank"],
            player_code=row["player_code"],
            player_name=row["player_name"],
            win_probability=row["win_probability"],
            prior_events_n=row["prior_events_n"],
            prior_avg_round_score_to_par=row["prior_avg_round_score_to_par"],
            prior_recent_form_10=row["prior_recent_form_10"],
            prior_recent_form_10_n=row["prior_recent_form_10_n"],
            neo_consistency_stddev=row["neo_consistency_stddev"],
            neo_consistency_stddev_n=row["neo_consistency_stddev_n"],
            official_metrics=row.get("official_metrics", {}),
            player_master_matched=row["player_master_matched"],
        )
        for row in data["predictions"]
    )
    return NeoWinPredictionSnapshot(
        prediction_id=data["prediction_id"],
        created_at_utc=data["created_at_utc"],
        record_kind=data["record_kind"],
        game_code=data["game_code"],
        tournament_name=data["tournament_name"],
        cutoff_date=data["cutoff_date"],
        cutoff_source=data["cutoff_source"],
        model_id=data["model_id"],
        model_version=data["model_version"],
        model_features=tuple(data["model_features"]),
        training_tournament_count=data["training_tournament_count"],
        field_size=data["field_size"],
        entrants_predicted=data["entrants_predicted"],
        dropped_entrants=data["dropped_entrants"],
        probability_sum=data["probability_sum"],
        minimum_probability=data["minimum_probability"],
        maximum_probability=data["maximum_probability"],
        zero_history_count=data["zero_history_count"],
        unmatched_count=data["unmatched_count"],
        official_metric_context=data["official_metric_context"],
        leakage_validation=data["leakage_validation"],
        missing_data_report=data["missing_data_report"],
        known_limitations=tuple(data["known_limitations"]),
        predictions=entrants,
    )


_OFFICIAL_METRIC_SLOT_NAMES: tuple[str, ...] = ("overall_skill", "driving", "short_game", "putting")

_CSV_FIELDNAMES: tuple[str, ...] = (
    "rank",
    "player_code",
    "player_name",
    "win_probability",
    "prior_events_n",
    "prior_avg_round_score_to_par",
    "prior_recent_form_10",
    "neo_consistency_stddev",
) + tuple(f"official_{slot}" for slot in _OFFICIAL_METRIC_SLOT_NAMES) + ("player_master_matched",)


def _entrants_csv_bytes(snapshot: NeoWinPredictionSnapshot) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDNAMES)
    writer.writeheader()
    for e in snapshot.predictions:
        row = {
            "rank": e.rank,
            "player_code": e.player_code,
            "player_name": e.player_name,
            "win_probability": e.win_probability,
            "prior_events_n": e.prior_events_n,
            "prior_avg_round_score_to_par": "" if e.prior_avg_round_score_to_par is None else e.prior_avg_round_score_to_par,
            "prior_recent_form_10": "" if e.prior_recent_form_10 is None else e.prior_recent_form_10,
            "neo_consistency_stddev": "" if e.neo_consistency_stddev is None else e.neo_consistency_stddev,
            "player_master_matched": e.player_master_matched,
        }
        for slot in _OFFICIAL_METRIC_SLOT_NAMES:
            value = e.official_metrics.get(slot)
            row[f"official_{slot}"] = "" if value is None else value
        writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")


def archive_filename_stem(prediction_id: str, game_code: str) -> str:
    return f"neo_win_{prediction_id}_{game_code}"


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


def write_neo_win_snapshot_atomic(snapshot: NeoWinPredictionSnapshot, predictions_root: Path) -> tuple[Path, Path]:
    """Same durability/atomicity guarantee as klpga.archive.
    prediction_archive.write_prediction_snapshot_atomic — writes NOTHING
    if either target file already exists."""
    json_path, csv_path = archive_paths(predictions_root, snapshot.prediction_id, snapshot.game_code, snapshot.cutoff_date)
    json_bytes = snapshot_to_json_text(snapshot).encode("utf-8")
    csv_bytes = _entrants_csv_bytes(snapshot)

    _atomic_claim(json_bytes, json_path)
    try:
        _atomic_claim(csv_bytes, csv_path)
    except NeoWinAlreadyArchivedError:
        raise
    except Exception as exc:  # noqa: BLE001 - deliberately broad, re-raised with context
        raise RuntimeError(
            f"JSON archived successfully at {json_path}, but the CSV write failed at {csv_path}: {exc}. "
            "The JSON is authoritative and already immutable; regenerate the CSV separately."
        ) from exc

    return json_path, csv_path
