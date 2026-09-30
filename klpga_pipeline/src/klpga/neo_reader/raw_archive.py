"""Stage 1 support: archive every raw response NEO Sync fetches under
raw/<game_code>/, human-readably named (not PoliteHttpClient's own
hash-keyed disk cache, which exists for a different purpose -- avoiding
re-hitting the network during development). This is the literal "raw/"
artifact the operator's Required Workflow names.

Write-once, same discipline as OPERATING_RULES.md's stage-snapshot
rule: a raw capture already on disk for this (game_code, label) is
never silently overwritten by a later sync run -- re-syncing the same
gameCode raises rather than clobbering evidence a downstream stage may
already have consumed. A caller that genuinely wants to re-fetch must
delete the old capture first, an explicit, visible action."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class RawCapture:
    label: str
    path: Path
    sha256: str
    byte_count: int
    source_url: str
    fetched_at: str


class RawCaptureAlreadyExists(RuntimeError):
    pass


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def archive_raw(
    raw_root: Path,
    game_code: str,
    label: str,
    content: str,
    source_url: str,
    extension: str = "html",
) -> RawCapture:
    """Write one raw capture to raw/<game_code>/<label>.<extension>.
    `label` should be a short, stable name for what was fetched (e.g.
    "game_list", "entry_list", "round_leaderboard_r1", "kranking_all",
    "kranking_period") -- one file per distinct real fetch, never a
    merged/edited blob."""
    game_dir = raw_root / str(game_code)
    game_dir.mkdir(parents=True, exist_ok=True)
    out_path = game_dir / f"{label}.{extension}"
    if out_path.exists():
        raise RawCaptureAlreadyExists(
            f"{out_path} already exists -- raw captures are write-once. "
            "Delete it explicitly first if a genuine re-fetch is intended."
        )
    out_path.write_text(content, encoding="utf-8")
    fetched_at = datetime.now(timezone.utc).isoformat()
    capture = RawCapture(
        label=label,
        path=out_path,
        sha256=_sha256(content),
        byte_count=len(content.encode("utf-8")),
        source_url=source_url,
        fetched_at=fetched_at,
    )
    _update_manifest(game_dir, capture)
    return capture


def _update_manifest(game_dir: Path, capture: RawCapture) -> None:
    manifest_path = game_dir / "RAW_MANIFEST_V1.json"
    manifest = {"game_code": game_dir.name, "captures": {}}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["captures"][capture.label] = {
        "path": capture.path.name,
        "sha256": capture.sha256,
        "byte_count": capture.byte_count,
        "source_url": capture.source_url,
        "fetched_at": capture.fetched_at,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def existing_capture(raw_root: Path, game_code: str, label: str) -> Optional[Path]:
    """The already-archived raw file for (game_code, label), if any --
    lets a later stage (normalize) read back what stage 1 actually
    fetched rather than re-fetching or trusting an in-memory value that
    may not match what was archived."""
    game_dir = raw_root / str(game_code)
    for ext in ("html", "json"):
        candidate = game_dir / f"{label}.{ext}"
        if candidate.exists():
            return candidate
    return None
