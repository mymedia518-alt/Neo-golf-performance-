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
    silently overwriting)."""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = _ROOT / "data" / "raw_cache" / "r1_final"
SNAPSHOT_DIR = _ROOT / "content" / "website_v2" / "r1_final_snapshots"
SNAPSHOT_SCHEMA_VERSION = "neo_ok_open_r1_final_snapshot_v1"


def raw_response_path(game_code: str, kind: str) -> Path:
    return RAW_DIR / f"OK_OPEN_{game_code}_SCORE_RECORD_RAW_{kind}.html"


def save_raw_response_immutable(game_code: str, kind: str, raw_html: str) -> Path:
    """Writes data/raw_cache/r1_final/OK_OPEN_<game_code>_SCORE_RECORD_RAW_<kind>.html.
    Raises FileExistsError if that exact (game_code, kind) raw response
    already exists -- the exact bytes klpga.co.kr returned for a given
    fetch are never silently replaced by a later one."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = raw_response_path(game_code, kind)
    if path.exists():
        raise FileExistsError(f"raw scoreRecord response already exists and is immutable: {path}")
    path.write_text(raw_html, encoding="utf-8")
    return path


def snapshot_path(game_code: str, kind: str) -> Path:
    return SNAPSHOT_DIR / f"OK_OPEN_{game_code}_FINAL_{kind}.json"


def save_snapshot_immutable(game_code: str, kind: str, payload: dict) -> Path:
    """Writes content/website_v2/r1_final_snapshots/OK_OPEN_<game_code>_FINAL_<kind>.json.
    Raises FileExistsError if that exact (game_code, kind) snapshot
    already exists."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(game_code, kind)
    if path.exists():
        raise FileExistsError(f"R1 FINAL snapshot already exists and is immutable: {path}")
    full = {"schema_version": SNAPSHOT_SCHEMA_VERSION, "kind": kind, "game_code": game_code, **payload}
    path.write_text(json.dumps(full, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def list_snapshots(game_code: str) -> list[Path]:
    if not SNAPSHOT_DIR.is_dir():
        return []
    return sorted(SNAPSHOT_DIR.glob(f"OK_OPEN_{game_code}_FINAL_*.json"))
