"""Immutable 30-minute tournament R1 snapshot store.

Every successful collection cycle is written as its OWN file, named by
`kind` (e.g. "PRE", "R1_1000", "R1_1030") -- never overwritten. This is
the literal "각 성공 cycle을 절대 overwrite하지 않는다" requirement:
`save_snapshot_immutable` raises if the target file already exists.

Each snapshot records everything needed to reconstruct exactly what
was known and shown at that moment: collected_at (when this cycle
ran), official_data_timestamp (the source's own data timestamp, when
one is resolvable -- KLPGA's leaderboard response carries no per-row
timestamp field, so this is honestly `None` rather than faked equal to
collected_at), the real leaderboard rows, every Cut/Top20/Top10/Top5/
Win probability, the cutline distribution (never a single point
estimate), model/build version, input provenance, and the cycle's own
validation result.

GENERIC NAMING (Phase 7): new snapshots are written under a
tournament-neutral filename, TOURNAMENT_<game_code>_SNAPSHOT_<kind>.json
-- the historical OK_OPEN_<game_code>_SNAPSHOT_<kind>.json convention
that every already-collected OK Open R1 snapshot uses is a legacy
naming scheme, never renamed or duplicated here, only still resolvable.
Read paths (`list_snapshots`) merge both namings; a write
(`save_snapshot_immutable`) always uses the generic name for a NEW
snapshot and refuses to create one if EITHER naming already holds a
file for that exact (game_code, kind) -- one collection cycle must
never be representable as two competing on-disk truths."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "content" / "website_v2" / "r1_snapshots"
SNAPSHOT_SCHEMA_VERSION = "neo_ok_open_r1_snapshot_v1"
_LEGACY_PREFIX = "OK_OPEN_"
_GENERIC_PREFIX = "TOURNAMENT_"


def snapshot_path(game_code: str, kind: str) -> Path:
    """The canonical path a NEW snapshot is written to. Never the
    legacy OK_OPEN_ naming -- see `_legacy_snapshot_path` for that."""
    return SNAPSHOT_DIR / f"{_GENERIC_PREFIX}{game_code}_SNAPSHOT_{kind}.json"


def _legacy_snapshot_path(game_code: str, kind: str) -> Path:
    return SNAPSHOT_DIR / f"{_LEGACY_PREFIX}{game_code}_SNAPSHOT_{kind}.json"


def save_snapshot_immutable(game_code: str, kind: str, payload: dict) -> Path:
    """Writes content/website_v2/r1_snapshots/TOURNAMENT_<game_code>_SNAPSHOT_<kind>.json.
    Raises FileExistsError if that exact (game_code, kind) snapshot
    already exists under EITHER the generic or the legacy OK_OPEN_
    naming -- immutability is enforced here, not left to the caller's
    discipline, and a cycle already recorded under the legacy name must
    never be duplicated under the generic one."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(game_code, kind)
    legacy_path = _legacy_snapshot_path(game_code, kind)
    if path.exists():
        raise FileExistsError(f"snapshot already exists and is immutable: {path}")
    if legacy_path.exists():
        raise FileExistsError(f"snapshot already exists and is immutable (legacy naming): {legacy_path}")
    full = {"schema_version": SNAPSHOT_SCHEMA_VERSION, "kind": kind, "game_code": game_code, **payload}
    path.write_text(json.dumps(full, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def list_snapshots(game_code: str, *, kind_prefix: Optional[str] = None) -> list[Path]:
    """Merges both namings -- a game_code collected before Phase 7 has
    only legacy OK_OPEN_ files, one collected after has only generic
    TOURNAMENT_ files, and either is found here identically. If the
    same (game_code, kind) somehow existed under both names, the
    generic one takes precedence (see `resolve_snapshot_path`) but both
    still appear here since list_snapshots enumerates real files on
    disk, not a resolved/deduplicated view."""
    if not SNAPSHOT_DIR.is_dir():
        return []
    generic_prefix = f"{_GENERIC_PREFIX}{game_code}_SNAPSHOT_{kind_prefix or ''}"
    legacy_prefix = f"{_LEGACY_PREFIX}{game_code}_SNAPSHOT_{kind_prefix or ''}"
    matches = [p for p in SNAPSHOT_DIR.glob(f"{_GENERIC_PREFIX}{game_code}_SNAPSHOT_*.json") if p.name.startswith(generic_prefix)]
    matches += [p for p in SNAPSHOT_DIR.glob(f"{_LEGACY_PREFIX}{game_code}_SNAPSHOT_*.json") if p.name.startswith(legacy_prefix)]
    return sorted(matches)


def resolve_snapshot_path(game_code: str, kind: str) -> Optional[Path]:
    """Read-path resolution for one exact (game_code, kind): generic
    naming first, legacy OK_OPEN_ naming as a fallback, None if neither
    exists. Never invents a path that isn't actually on disk."""
    path = snapshot_path(game_code, kind)
    if path.is_file():
        return path
    legacy_path = _legacy_snapshot_path(game_code, kind)
    if legacy_path.is_file():
        return legacy_path
    return None


def load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_snapshot(game_code: str, *, kind_prefix: str = "R1_") -> Optional[dict]:
    """The most recent snapshot by its own recorded `collected_at`
    (never by filename string order, which would break across a day
    boundary) among snapshots whose kind starts with `kind_prefix`."""
    candidates = [load_snapshot(p) for p in list_snapshots(game_code, kind_prefix=kind_prefix)]
    if not candidates:
        return None
    return max(candidates, key=lambda s: s.get("collected_at") or "")


def leaderboard_state_signature(leaderboard: list) -> tuple:
    """A hashable, order-independent signature of the parts of the
    leaderboard that matter for a "did anything real change" freshness
    check -- (player_id, total_under_par, holes_completed, status) per
    row. Two collections with an identical signature carry no new
    validated information, regardless of how many times they are
    polled."""
    return tuple(
        sorted(
            (
                str(row.get("player_id") or row.get("player_code") or ""),
                row.get("total_under_par"),
                str(row.get("holes_completed") or ""),
                str(row.get("status") or ""),
            )
            for row in leaderboard
        )
    )
