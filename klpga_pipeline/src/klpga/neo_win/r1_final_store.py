"""Immutable storage for the R1 FINAL (scoreRecord) reconciliation
pathway -- deliberately SEPARATE directories from klpga.neo_win.
r1_snapshot_store, which belongs exclusively to the 30-minute live
in-progress collector (scripts/96). Nothing in this module ever reads
or writes r1_snapshots/ -- the live collector's own snapshots are
never touched by this pathway, matching "현재 live snapshot을 수정하지
말고" exactly.

Two distinct immutable stores, matching "별도 raw response와 immutable
parsed snapshot으로 저장한다":

  - RAW_DIR: the exact HTTP response text scoreRecord returned, saved
    verbatim, one file per fetch, never overwritten -- proof of what
    was actually received, independent of whether a parser could make
    sense of it yet (see klpga.collectors.score_record.
    parse_score_record_html, not yet implemented).
  - SNAPSHOT_DIR: the structured, reconciled result (once a real
    parser exists), same immutability discipline as r1_snapshot_store
    (save_snapshot_immutable raises on a duplicate kind rather than
    silently overwriting).

GENERIC NAMING (Phase 7): new raw responses and snapshots are written
under a tournament-neutral filename, TOURNAMENT_<game_code>_..., not
the historical OK_OPEN_<game_code>_... convention every already-
collected OK Open R1 FINAL artifact uses. Read paths merge both
namings (generic first, legacy fallback); a write always uses the
generic name and refuses to create one if EITHER naming already holds
a file for that exact (game_code, kind)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = _ROOT / "data" / "raw_cache" / "r1_final"
SNAPSHOT_DIR = _ROOT / "content" / "website_v2" / "r1_final_snapshots"
SNAPSHOT_SCHEMA_VERSION = "neo_ok_open_r1_final_snapshot_v1"
_LEGACY_PREFIX = "OK_OPEN_"
_GENERIC_PREFIX = "TOURNAMENT_"


def raw_response_path(game_code: str, kind: str) -> Path:
    """The canonical path a NEW raw response is written to. Never the
    legacy OK_OPEN_ naming -- see `_legacy_raw_response_path`."""
    return RAW_DIR / f"{_GENERIC_PREFIX}{game_code}_SCORE_RECORD_RAW_{kind}.html"


def _legacy_raw_response_path(game_code: str, kind: str) -> Path:
    return RAW_DIR / f"{_LEGACY_PREFIX}{game_code}_SCORE_RECORD_RAW_{kind}.html"


def save_raw_response_immutable(game_code: str, kind: str, raw_html: str) -> Path:
    """Writes data/raw_cache/r1_final/TOURNAMENT_<game_code>_SCORE_RECORD_RAW_<kind>.html.
    Raises FileExistsError if that exact (game_code, kind) raw response
    already exists under EITHER naming -- the exact bytes klpga.co.kr
    returned for a given fetch are never silently replaced by a later
    one, and never duplicated under a second name either."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = raw_response_path(game_code, kind)
    legacy_path = _legacy_raw_response_path(game_code, kind)
    if path.exists():
        raise FileExistsError(f"raw scoreRecord response already exists and is immutable: {path}")
    if legacy_path.exists():
        raise FileExistsError(f"raw scoreRecord response already exists and is immutable (legacy naming): {legacy_path}")
    path.write_text(raw_html, encoding="utf-8")
    return path


def resolve_raw_response_path(game_code: str, kind: str) -> Optional[Path]:
    path = raw_response_path(game_code, kind)
    if path.is_file():
        return path
    legacy_path = _legacy_raw_response_path(game_code, kind)
    if legacy_path.is_file():
        return legacy_path
    return None


def snapshot_path(game_code: str, kind: str) -> Path:
    """The canonical path a NEW snapshot is written to. Never the
    legacy OK_OPEN_ naming -- see `_legacy_snapshot_path`."""
    return SNAPSHOT_DIR / f"{_GENERIC_PREFIX}{game_code}_FINAL_{kind}.json"


def _legacy_snapshot_path(game_code: str, kind: str) -> Path:
    return SNAPSHOT_DIR / f"{_LEGACY_PREFIX}{game_code}_FINAL_{kind}.json"


def save_snapshot_immutable(game_code: str, kind: str, payload: dict) -> Path:
    """Writes content/website_v2/r1_final_snapshots/TOURNAMENT_<game_code>_FINAL_<kind>.json.
    Raises FileExistsError if that exact (game_code, kind) snapshot
    already exists under either the generic or legacy naming."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(game_code, kind)
    legacy_path = _legacy_snapshot_path(game_code, kind)
    if path.exists():
        raise FileExistsError(f"R1 FINAL snapshot already exists and is immutable: {path}")
    if legacy_path.exists():
        raise FileExistsError(f"R1 FINAL snapshot already exists and is immutable (legacy naming): {legacy_path}")
    full = {"schema_version": SNAPSHOT_SCHEMA_VERSION, "kind": kind, "game_code": game_code, **payload}
    path.write_text(json.dumps(full, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def resolve_snapshot_path(game_code: str, kind: str) -> Optional[Path]:
    path = snapshot_path(game_code, kind)
    if path.is_file():
        return path
    legacy_path = _legacy_snapshot_path(game_code, kind)
    if legacy_path.is_file():
        return legacy_path
    return None


def load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def list_snapshots(game_code: str) -> list[Path]:
    """Merges both namings so a game_code with legacy-only, generic-
    only, or (in principle) both kinds of files is enumerated
    completely."""
    if not SNAPSHOT_DIR.is_dir():
        return []
    matches = list(SNAPSHOT_DIR.glob(f"{_GENERIC_PREFIX}{game_code}_FINAL_*.json"))
    matches += list(SNAPSHOT_DIR.glob(f"{_LEGACY_PREFIX}{game_code}_FINAL_*.json"))
    return sorted(matches)
