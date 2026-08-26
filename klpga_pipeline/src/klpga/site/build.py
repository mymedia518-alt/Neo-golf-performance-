"""Loads archived predictions and renders the static site. No feature,
probability, or ranking computation happens anywhere in this module —
every number and every rank comes verbatim from an already-archived
`PredictionSnapshot` (`klpga.archive.prediction_archive`, reused
unmodified). This module's only job is: read archives -> validate
they're safe to render -> produce static HTML/CSS/JS files.

======================================================================
HARD INTEGRITY CHECKS (`_validate_snapshot_for_render`)
======================================================================
Before any file is written, every snapshot is re-validated
independently of trusting the archive layer's own invariants (the
archive layer already guarantees these at write time, via
`klpga.models.inference._validate_invariants`, but a JSON file on disk
could in principle be hand-edited after the fact — this module never
assumes that couldn't happen):
  - rendered player count == `field_size`
  - the rank sequence is a dense, gap-free 1..N permutation (a gap
    would mean an entrant silently disappeared; a duplicate would mean
    two entrants collapsed into one rank)
  - `maximum_probability` is strictly positive (the denominator used
    for the relative probability-bar width)
Any violation raises `SiteBuildIntegrityError` and stops the build —
no partial/best-effort page is ever produced.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from klpga.archive.prediction_archive import EntrantSnapshot, PredictionSnapshot, read_prediction_snapshot

STATIC_SOURCE_DIR = Path(__file__).resolve().parent / "static"


class SiteBuildIntegrityError(RuntimeError):
    """Raised when an archived prediction fails a hard integrity check
    at render time — the build stops rather than publishing a
    corrupted-looking page. See module docstring."""


@dataclass(frozen=True)
class BuildResult:
    predictions_rendered: int
    latest_prediction_id: str
    output_root: Path
    written_files: tuple[Path, ...]


def _sort_key(snapshot: PredictionSnapshot) -> tuple[str, str]:
    return (snapshot.cutoff_date, snapshot.prediction_id)


def load_predictions(predictions_root: Path) -> list[PredictionSnapshot]:
    """Reads every `predictions/<year>/*.json` archive, oldest cutoff
    first. Read-only: `read_prediction_snapshot` only ever opens a
    file for reading (see that function's docstring)."""
    paths = sorted(Path(predictions_root).glob("*/*.json"))
    snapshots = [read_prediction_snapshot(p) for p in paths]
    snapshots.sort(key=_sort_key)
    return snapshots


def ordered_entrants(snapshot: PredictionSnapshot) -> list[EntrantSnapshot]:
    """Entrants sorted by the archive's own `rank` field (display
    order only — never re-derives rank from probability)."""
    return sorted(snapshot.predictions, key=lambda e: e.rank)


def _validate_snapshot_for_render(snapshot: PredictionSnapshot) -> None:
    entrants = ordered_entrants(snapshot)

    if len(entrants) != snapshot.field_size:
        raise SiteBuildIntegrityError(
            f"prediction {snapshot.prediction_id}: rendered player count "
            f"({len(entrants)}) != archived field_size ({snapshot.field_size}) — refusing to render."
        )

    ranks = [e.rank for e in entrants]
    if ranks != list(range(1, len(ranks) + 1)):
        raise SiteBuildIntegrityError(
            f"prediction {snapshot.prediction_id}: rank sequence is not a gap-free 1..{len(ranks)} "
            f"permutation ({ranks}) — an entrant may be missing or duplicated. Refusing to render."
        )

    if snapshot.maximum_probability <= 0:
        raise SiteBuildIntegrityError(
            f"prediction {snapshot.prediction_id}: maximum_probability={snapshot.maximum_probability!r} "
            "is not strictly positive — refusing to render (this should be impossible given the frozen "
            "model's own invariants; treating it as archive corruption)."
        )


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def build_site(predictions_root: Path, output_root: Path) -> BuildResult:
    """The single entry point. Reads every archive under
    `predictions_root`, hard-validates each one, then writes the full
    static site under `output_root`. Never writes anywhere else, and
    never opens the SQLite database."""
    from klpga.site import templates  # local import: keeps template copy changes from forcing a build.py edit

    snapshots = load_predictions(predictions_root)
    if not snapshots:
        raise SiteBuildIntegrityError(f"no prediction archives found under {predictions_root} — nothing to build.")

    for snapshot in snapshots:
        _validate_snapshot_for_render(snapshot)

    latest = snapshots[-1]
    output_root = Path(output_root)
    written: list[Path] = []

    written.append(_write(output_root / "index.html", templates.render_prediction_page(latest, is_home=True)))
    written.append(_write(output_root / "predictions" / "index.html", templates.render_predictions_index(snapshots)))
    for snapshot in snapshots:
        written.append(
            _write(
                output_root / "predictions" / snapshot.prediction_id / "index.html",
                templates.render_prediction_page(snapshot, is_home=False),
            )
        )
    written.append(_write(output_root / "predictions" / "history" / "index.html", templates.render_history_page(snapshots)))
    written.append(_write(output_root / "methodology" / "index.html", templates.render_methodology_page(latest)))

    static_out = output_root / "static"
    static_out.mkdir(parents=True, exist_ok=True)
    for asset in ("app.js", "styles.css"):
        dest = static_out / asset
        shutil.copyfile(STATIC_SOURCE_DIR / asset, dest)
        written.append(dest)

    return BuildResult(
        predictions_rendered=len(snapshots),
        latest_prediction_id=latest.prediction_id,
        output_root=output_root,
        written_files=tuple(written),
    )
