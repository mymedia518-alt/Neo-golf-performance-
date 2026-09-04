"""Immutable 30-minute OK Open R1 snapshot store.

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
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

SNAPSHOT_DIR = Path(__file__).resolve().parents[3] / "content" / "website_v2" / "r1_snapshots"
SNAPSHOT_SCHEMA_VERSION = "neo_ok_open_r1_snapshot_v1"


def snapshot_path(game_code: str, kind: str) -> Path:
    return SNAPSHOT_DIR / f"OK_OPEN_{game_code}_SNAPSHOT_{kind}.json"


def save_snapshot_immutable(game_code: str, kind: str, payload: dict) -> Path:
    """Writes content/website_v2/r1_snapshots/OK_OPEN_<game_code>_SNAPSHOT_<kind>.json.
    Raises FileExistsError if that exact (game_code, kind) snapshot
    already exists -- immutability is enforced here, not left to the
    caller's discipline."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = snapshot_path(game_code, kind)
    if path.exists():
        raise FileExistsError(f"snapshot already exists and is immutable: {path}")
    full = {"schema_version": SNAPSHOT_SCHEMA_VERSION, "kind": kind, "game_code": game_code, **payload}
    path.write_text(json.dumps(full, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def list_snapshots(game_code: str, *, kind_prefix: Optional[str] = None) -> list[Path]:
    if not SNAPSHOT_DIR.is_dir():
        return []
    prefix = f"OK_OPEN_{game_code}_SNAPSHOT_{kind_prefix or ''}"
    return sorted(p for p in SNAPSHOT_DIR.glob(f"OK_OPEN_{game_code}_SNAPSHOT_*.json") if p.name.startswith(prefix))


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
