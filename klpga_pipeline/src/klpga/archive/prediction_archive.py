"""Immutable prediction snapshot: schema, atomic writer, reader, and
the reconstruction cross-check used only for a rerun-reconstructed
prediction (see module docstring of `klpga.models.inference` for why a
reconstruction can ever be necessary, and `docs/PREDICTION_ARCHIVE.md`
for the full policy).

======================================================================
WHAT THIS MODULE DOES NOT DO
======================================================================
No feature, shrinkage, fitting, or softmax logic lives here. Every
number in a `PredictionSnapshot` is copied unchanged from an
already-computed `klpga.models.inference.InferenceResult` — this
module only reshapes/serializes it. `klpga.models.inference` is
imported for exactly one already-existing, unmodified helper
(`_build_training_rows`, reused — not duplicated — to report the
latest historical tournament date actually used, a read-only
diagnostic `InferenceResult` doesn't itself carry).

======================================================================
IMMUTABILITY
======================================================================
`write_prediction_snapshot_atomic` NEVER overwrites an existing
archive file. It claims the final filename with `os.link` (an
atomic, exists-fails create — not a check-then-write race), only
after the full, validated content has already been written to a
temp file in the same directory and fsynced. A duplicate
`(prediction_id, game_code)` pair raises `PredictionAlreadyArchivedError`
before anything at the final path is touched. There is no UPDATE path
anywhere in this module.

======================================================================
PROVENANCE
======================================================================
Every snapshot's `provenance.source` is exactly one of:
  - "live_atomic_inference" — `run_inference()` was called once, in
    the same process, immediately before archiving. This is the ONLY
    source that may ever be called the authoritative record of what
    NEO predicted.
  - "rerun_reconstruction" — the archived run is a deterministic
    RE-EXECUTION of inference standing in for an earlier real run
    whose complete output was never captured to a machine-readable
    file. This is never labeled "original." `verify_against_observed_facts`
    exists specifically to give this path a hard, code-enforced abort
    if the reconstruction disagrees with independently-recorded facts
    from the real first run.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from klpga.models.inference import EntrantPrediction, InferenceResult, _build_training_rows

RECORD_KIND = "neo_prediction_archive_v1"
MODEL_VERSION = "v1"

KNOWN_LIMITATIONS: tuple[str, ...] = (
    "Coarse calibration diagnostics suggest possible over-confidence in some "
    "higher probability bins, especially approximately 10-20%. Not corrected "
    "in this prediction — see docs/SITE_STRUCTURE_TODO.md section 10.",
)

CSV_FIELDNAMES: tuple[str, ...] = (
    "rank",
    "player_code",
    "player_name_display",
    "win_probability",
    "prior_events_n",
    "prior_avg_round_score_to_par",
    "prior_recent_form_10",
    "prior_recent_form_10_n",
    "history_slice",
    "player_master_matched",
)


class PredictionAlreadyArchivedError(RuntimeError):
    """Raised when a (prediction_id, game_code) archive already exists.
    The archive is append-only — this is the only way a duplicate is
    ever handled: loudly, before any write, never by overwriting."""


# ----------------------------------------------------------------
# Schema
# ----------------------------------------------------------------


@dataclass(frozen=True)
class EntrantSnapshot:
    rank: int
    player_code: str
    player_name_display: str
    win_probability: float
    prior_events_n: int
    prior_avg_round_score_to_par: Optional[float]
    prior_recent_form_10: Optional[float]
    prior_recent_form_10_n: int
    history_slice: str
    player_master_matched: bool


@dataclass(frozen=True)
class PredictionSnapshot:
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
    required_final_checks: dict
    known_limitations: tuple[str, ...]
    provenance: dict
    predictions: tuple[EntrantSnapshot, ...] = field(default_factory=tuple)


def build_required_final_checks(result: InferenceResult) -> dict:
    """The same 5 checks `scripts/23`/`scripts/24` print, re-derived
    (not recomputed by any new logic) purely from `InferenceResult`
    fields so they're preserved in the archive too."""
    return {
        "entrants_parsed_eq_field_size": result.entrants_parsed == result.field_size,
        "entrants_predicted_eq_field_size": result.predicted_count == result.field_size,
        "dropped_entrants_eq_zero": result.dropped_entrants == 0,
        "duplicate_player_codes_eq_zero": result.duplicate_player_codes == 0,
        "probability_sum_within_tolerance": abs(result.sum_probability - 1.0) <= 1e-6,
    }


def snapshot_from_inference_result(
    result: InferenceResult,
    *,
    prediction_id: str,
    created_at_utc: str,
    provenance: dict,
) -> PredictionSnapshot:
    """Pure mapper: every field is copied unchanged from `result`. No
    probability, feature, or count is computed, rounded, or altered
    here — see module docstring."""
    codes = [p.player_code for p in result.predictions]
    if len(set(codes)) != len(codes):
        raise ValueError(
            "duplicate player_code(s) inside InferenceResult.predictions — refusing to "
            "archive a corrupted result (this should never happen given "
            "klpga.models.inference's own invariants)."
        )

    entrants = tuple(_entrant_snapshot(p) for p in result.predictions)
    return PredictionSnapshot(
        prediction_id=prediction_id,
        created_at_utc=created_at_utc,
        record_kind=RECORD_KIND,
        game_code=result.game_code,
        tournament_name=result.tournament_name,
        cutoff_date=result.cutoff_date,
        cutoff_source=result.cutoff_date_source,
        model_id=result.model_id,
        model_version=MODEL_VERSION,
        model_features=tuple(result.model_features),
        training_tournament_count=result.training_tournament_count,
        field_size=result.field_size,
        entrants_predicted=result.predicted_count,
        dropped_entrants=result.dropped_entrants,
        probability_sum=result.sum_probability,
        minimum_probability=result.min_probability,
        maximum_probability=result.max_probability,
        zero_history_count=result.zero_history_count,
        unmatched_count=result.unmatched_count,
        required_final_checks=build_required_final_checks(result),
        known_limitations=KNOWN_LIMITATIONS,
        provenance=dict(provenance),
        predictions=entrants,
    )


def _entrant_snapshot(p: EntrantPrediction) -> EntrantSnapshot:
    return EntrantSnapshot(
        rank=p.rank,
        player_code=p.player_code,
        player_name_display=p.player_name,
        win_probability=p.win_probability,
        prior_events_n=p.prior_events_n,
        prior_avg_round_score_to_par=p.prior_avg_round_score_to_par,
        prior_recent_form_10=p.prior_recent_form_10,
        prior_recent_form_10_n=p.prior_recent_form_10_n,
        history_slice=p.history_slice,
        player_master_matched=not p.is_unmatched,
    )


# ----------------------------------------------------------------
# Provenance builders
# ----------------------------------------------------------------


def build_live_atomic_provenance() -> dict:
    return {"source": "live_atomic_inference"}


def build_rerun_reconstruction_provenance(
    *,
    original_run_status: str,
    original_machine_readable_snapshot_available: bool,
    reconstruction_reason: str,
    verification: dict,
) -> dict:
    return {
        "source": "rerun_reconstruction",
        "original_run_status": original_run_status,
        "original_machine_readable_snapshot_available": original_machine_readable_snapshot_available,
        "reconstruction_reason": reconstruction_reason,
        "verification": dict(verification),
    }


# ----------------------------------------------------------------
# Reconstruction cross-check (rerun_reconstruction only)
# ----------------------------------------------------------------


@dataclass(frozen=True)
class ExpectedFacts:
    """Facts independently observed/recorded from the real first run,
    to verify a reconstruction against. Every field is optional —
    only what is actually known is checked ("where known"); an unset
    field is silently skipped, never treated as a pass."""

    game_code: Optional[str] = None
    field_size: Optional[int] = None
    cutoff_date: Optional[str] = None
    model_id: Optional[str] = None
    training_tournament_count: Optional[int] = None
    entrants_predicted: Optional[int] = None
    dropped_entrants: Optional[int] = None
    probability_sum: Optional[float] = None
    zero_history_count: Optional[int] = None
    unmatched_count: Optional[int] = None
    top_player_code: Optional[str] = None
    top_player_name: Optional[str] = None
    top_player_display_probability_pct: Optional[float] = None


def verify_against_observed_facts(result: InferenceResult, expected: ExpectedFacts) -> list[str]:
    """Returns a list of human-readable mismatch descriptions (empty =
    every known fact matches). Never rounds/mutates `result` — this
    only compares. The display-probability check compares the SAME
    3-decimal-place rounding `scripts/23`/`scripts/24` print
    (`round(pct, 3)`), never the stored full-precision value, so the
    archive keeps the reconstruction's own highest-precision
    probability regardless of outcome."""
    mismatches: list[str] = []

    def _check(label: str, actual, exp) -> None:
        if exp is not None and actual != exp:
            mismatches.append(f"{label}: expected {exp!r}, reconstruction produced {actual!r}")

    _check("game_code", result.game_code, expected.game_code)
    _check("field_size", result.field_size, expected.field_size)
    _check("cutoff_date", result.cutoff_date, expected.cutoff_date)
    _check("model_id", result.model_id, expected.model_id)
    _check("training_tournament_count", result.training_tournament_count, expected.training_tournament_count)
    _check("entrants_predicted", result.predicted_count, expected.entrants_predicted)
    _check("dropped_entrants", result.dropped_entrants, expected.dropped_entrants)
    _check("zero_history_count", result.zero_history_count, expected.zero_history_count)
    _check("unmatched_count", result.unmatched_count, expected.unmatched_count)

    if expected.probability_sum is not None and abs(result.sum_probability - expected.probability_sum) > 1e-6:
        mismatches.append(
            f"probability_sum: expected {expected.probability_sum!r} +/- 1e-6, "
            f"reconstruction produced {result.sum_probability!r}"
        )

    if expected.top_player_code is not None:
        actual_top = result.predictions[0] if result.predictions else None
        if actual_top is None or actual_top.player_code != expected.top_player_code:
            mismatches.append(
                f"top_player_code: expected {expected.top_player_code!r} at rank 1, "
                f"reconstruction produced {(actual_top.player_code if actual_top else None)!r}"
            )
        else:
            if expected.top_player_name is not None and actual_top.player_name != expected.top_player_name:
                mismatches.append(
                    f"top_player_name: expected {expected.top_player_name!r} at rank 1 "
                    f"(player_code matched), reconstruction produced {actual_top.player_name!r}"
                )
            if expected.top_player_display_probability_pct is not None:
                actual_pct = round(actual_top.win_probability * 100, 3)
                expected_pct = round(expected.top_player_display_probability_pct, 3)
                if actual_pct != expected_pct:
                    mismatches.append(
                        f"top_player display probability: expected {expected_pct}% (3dp), "
                        f"reconstruction rounds to {actual_pct}%"
                    )

    return mismatches


def latest_training_tournament_date(
    conn: sqlite3.Connection, game_code: str, cutoff_date_obj: date
) -> Optional[str]:
    """Read-only diagnostic: the most recent `target_start_date` among
    the exact training rows `run_inference()` itself would fit M4 on
    for this game_code/cutoff — reuses
    `klpga.models.inference._build_training_rows` unchanged rather
    than re-deriving the training-population rule a second time."""
    training_rows, _ = _build_training_rows(conn, game_code, cutoff_date_obj)
    dates = [row["target_start_date"] for row in training_rows if row.get("target_start_date")]
    return max(dates) if dates else None


# ----------------------------------------------------------------
# Serialization
# ----------------------------------------------------------------


def snapshot_to_dict(snapshot: PredictionSnapshot) -> dict:
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
        "required_final_checks": dict(snapshot.required_final_checks),
        "known_limitations": list(snapshot.known_limitations),
        "provenance": dict(snapshot.provenance),
        "predictions": [
            {
                "rank": e.rank,
                "player_code": e.player_code,
                "player_name_display": e.player_name_display,
                "win_probability": e.win_probability,
                "prior_events_n": e.prior_events_n,
                "prior_avg_round_score_to_par": e.prior_avg_round_score_to_par,
                "prior_recent_form_10": e.prior_recent_form_10,
                "prior_recent_form_10_n": e.prior_recent_form_10_n,
                "history_slice": e.history_slice,
                "player_master_matched": e.player_master_matched,
            }
            for e in snapshot.predictions
        ],
    }


def snapshot_to_json_text(snapshot: PredictionSnapshot) -> str:
    """Deterministic: fixed key order (dict literal insertion order,
    not hash-dependent), fixed float repr, fixed indent — two calls on
    equal snapshots always produce byte-identical text."""
    return json.dumps(snapshot_to_dict(snapshot), indent=2, ensure_ascii=False) + "\n"


def read_prediction_snapshot(path: Path) -> PredictionSnapshot:
    """Read-only: opens `path` for reading only, never writes back to
    it. Safe to call against a read-only-permission file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    entrants = tuple(
        EntrantSnapshot(
            rank=row["rank"],
            player_code=row["player_code"],
            player_name_display=row["player_name_display"],
            win_probability=row["win_probability"],
            prior_events_n=row["prior_events_n"],
            prior_avg_round_score_to_par=row["prior_avg_round_score_to_par"],
            prior_recent_form_10=row["prior_recent_form_10"],
            prior_recent_form_10_n=row["prior_recent_form_10_n"],
            history_slice=row["history_slice"],
            player_master_matched=row["player_master_matched"],
        )
        for row in data["predictions"]
    )
    return PredictionSnapshot(
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
        required_final_checks=data["required_final_checks"],
        known_limitations=tuple(data["known_limitations"]),
        provenance=data["provenance"],
        predictions=entrants,
    )


def _entrants_csv_bytes(snapshot: PredictionSnapshot) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDNAMES)
    writer.writeheader()
    for e in snapshot.predictions:
        writer.writerow(
            {
                "rank": e.rank,
                "player_code": e.player_code,
                "player_name_display": e.player_name_display,
                "win_probability": e.win_probability,
                "prior_events_n": e.prior_events_n,
                "prior_avg_round_score_to_par": "" if e.prior_avg_round_score_to_par is None else e.prior_avg_round_score_to_par,
                "prior_recent_form_10": "" if e.prior_recent_form_10 is None else e.prior_recent_form_10,
                "prior_recent_form_10_n": e.prior_recent_form_10_n,
                "history_slice": e.history_slice,
                "player_master_matched": e.player_master_matched,
            }
        )
    # utf-8-sig (BOM) so Excel on Windows renders Korean player names
    # correctly without a manual import-encoding step; the JSON stays
    # plain UTF-8 since it is only ever parsed programmatically.
    return buf.getvalue().encode("utf-8-sig")


# ----------------------------------------------------------------
# Atomic, append-only write
# ----------------------------------------------------------------


def archive_filename_stem(prediction_id: str, game_code: str) -> str:
    return f"prediction_{prediction_id}_{game_code}"


def archive_paths(predictions_root: Path, prediction_id: str, game_code: str, cutoff_date: str) -> tuple[Path, Path]:
    year = cutoff_date[:4]
    target_dir = Path(predictions_root) / year
    stem = archive_filename_stem(prediction_id, game_code)
    return target_dir / f"{stem}.json", target_dir / f"{stem}.csv"


def _atomic_claim(content_bytes: bytes, final_path: Path) -> None:
    """Writes `content_bytes` to a temp file in `final_path`'s own
    directory, fsyncs it, then claims `final_path` via `os.link` — an
    atomic, exists-fails create. Raises `PredictionAlreadyArchivedError`
    if `final_path` already exists; the temp file is always cleaned up,
    on every exit path, and the original content is never visible at
    `final_path` until it is already complete and durable."""
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
            raise PredictionAlreadyArchivedError(
                f"{final_path} already exists — the archive is append-only and is never overwritten."
            ) from exc
        except (OSError, NotImplementedError) as exc:
            # Hard links unsupported on this filesystem (rare). Fall back to a
            # check-then-replace, which reopens a narrow TOCTOU window —
            # disclosed here and in docs/PREDICTION_ARCHIVE.md, not hidden.
            if final_path.exists():
                raise PredictionAlreadyArchivedError(
                    f"{final_path} already exists — the archive is append-only and is never overwritten."
                ) from exc
            os.replace(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def write_prediction_snapshot_atomic(
    snapshot: PredictionSnapshot, predictions_root: Path
) -> tuple[Path, Path]:
    """Writes `snapshot` as `<predictions_root>/<year>/prediction_<id>_<game_code>.json`
    and `.csv`. Raises `PredictionAlreadyArchivedError` and writes
    NOTHING if either file already exists. JSON is written first and is
    authoritative; if the JSON claim succeeds but the CSV claim then
    fails for any reason other than already-existing, the JSON remains
    (it is already valid and immutable) and a `RuntimeError` is raised
    naming the CSV problem explicitly — the CSV is always regenerable
    from the JSON, so this is a disclosed, recoverable, non-silent
    failure, never a corrupted-looking archive."""
    json_path, csv_path = archive_paths(
        predictions_root, snapshot.prediction_id, snapshot.game_code, snapshot.cutoff_date
    )
    json_bytes = snapshot_to_json_text(snapshot).encode("utf-8")
    csv_bytes = _entrants_csv_bytes(snapshot)

    _atomic_claim(json_bytes, json_path)
    try:
        _atomic_claim(csv_bytes, csv_path)
    except PredictionAlreadyArchivedError:
        raise
    except Exception as exc:  # noqa: BLE001 - deliberately broad, re-raised with context
        raise RuntimeError(
            f"JSON archived successfully at {json_path}, but the CSV write failed at "
            f"{csv_path}: {exc}. The JSON is authoritative and already immutable; "
            "regenerate the CSV separately rather than retrying this command."
        ) from exc

    return json_path, csv_path
