"""Phase B2 checkpoint/state artifact — an explicit, on-disk resume
state for the full canonical-metric sweep, kept independent of
`PoliteHttpClient`'s own HTTP-level disk cache (`data/raw_cache/http/`).
That cache is a second, lower-level safety net: it stops an
already-fetched URL from being re-requested even if this checkpoint
were lost, but it is keyed by an opaque content hash and knows nothing
about parse outcome, completion status, or which of the canonical
identities have been fully processed. This module is the authoritative
"is this identity_key done" answer for
`scripts/29_execute_phase_b2_full_sweep.py`.

Format: one JSON object keyed by identity_key -> record. Writes are
ATOMIC — serialize to a temp file in the same directory, then
`os.replace` it onto the real path (atomic on both POSIX and Windows).
A crash or kill at any point before that final replace leaves the
previous checkpoint file completely intact; there is no window where a
reader could observe a half-written file.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

COMPLETION_SUCCESS = "SUCCESS"
COMPLETION_HTTP_FAILURE = "HTTP_FAILURE"
"""The two `completion_status` values. SUCCESS means an HTTP response
was obtained and parsed (regardless of parse_status — an AMBIGUOUS or
FAILED parse is still a completed REQUEST, matching Phase B1's
existing "record it, never silently drop it" behavior) and this
identity_key must be SKIPPED on resume. HTTP_FAILURE means no response
was ever obtained (the request itself failed after retries) and this
identity_key remains explicitly visible and rerunnable."""


@dataclass
class CheckpointEntry:
    identity_key: str
    request_params: dict
    season: str
    http_result: str
    """"SUCCESS" | "HTTP_FAILURE" — mirrors completion_status; kept as
    its own field since a future completion_status value (e.g. an
    explicit BLOCKED state) need not always imply the same http_result
    wording."""
    parse_status: Optional[str]
    schema_fingerprint: Optional[str]
    player_row_count: Optional[int]
    completion_status: str
    timestamp: str
    sample_record: Optional[dict] = None
    """The full `build_sample_record(...)` dict (same shape Phase B1
    writes to KLPGA_RESPONSE_SCHEMA_SAMPLES.json), stored here so the
    B2 runner's periodic/final output artifacts can be REGENERATED
    from the checkpoint alone — reflecting every identity completed
    across ALL runs, not just the current invocation. None for
    HTTP_FAILURE entries."""
    log_entry: Optional[dict] = None
    """`asdict(RequestLogEntry)` — same reason as `sample_record`,
    for regenerating the B2 request log across all runs. None for
    HTTP_FAILURE entries."""

    @property
    def is_complete(self) -> bool:
        return self.completion_status == COMPLETION_SUCCESS


def load_checkpoint(path: Path) -> dict[str, CheckpointEntry]:
    """Returns {} if the file doesn't exist yet (first run) — a
    missing checkpoint is the normal, expected first-run state, not an
    error. A genuinely corrupt (unparseable) checkpoint DOES raise —
    silently discarding partial B2 progress because of a malformed
    file would be exactly the kind of silent data loss this project's
    evidence discipline exists to prevent."""
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {key: CheckpointEntry(**entry) for key, entry in payload.items()}


def write_checkpoint_atomic(path: Path, entries: dict[str, CheckpointEntry]) -> None:
    """Writes the FULL checkpoint dict atomically. `tempfile.mkstemp`
    is created in `path`'s own directory specifically so the final
    `os.replace` is a same-filesystem rename — the only way POSIX/
    Windows both guarantee atomicity; a cross-filesystem temp dir
    (e.g. the OS default /tmp) would not give that guarantee."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: asdict(entry) for key, entry in entries.items()}
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def mark_success(
    entries: dict[str, CheckpointEntry],
    *,
    identity_key: str,
    request_params: dict,
    season: str,
    parse_status: str,
    schema_fingerprint: Optional[str],
    player_row_count: int,
    timestamp: str,
    sample_record: Optional[dict] = None,
    log_entry: Optional[dict] = None,
) -> None:
    entries[identity_key] = CheckpointEntry(
        identity_key=identity_key,
        request_params=request_params,
        season=season,
        http_result="SUCCESS",
        parse_status=parse_status,
        schema_fingerprint=schema_fingerprint,
        player_row_count=player_row_count,
        completion_status=COMPLETION_SUCCESS,
        timestamp=timestamp,
        sample_record=sample_record,
        log_entry=log_entry,
    )


def mark_http_failure(
    entries: dict[str, CheckpointEntry],
    *,
    identity_key: str,
    request_params: dict,
    season: str,
    timestamp: str,
) -> None:
    entries[identity_key] = CheckpointEntry(
        identity_key=identity_key,
        request_params=request_params,
        season=season,
        http_result="HTTP_FAILURE",
        parse_status=None,
        schema_fingerprint=None,
        player_row_count=None,
        completion_status=COMPLETION_HTTP_FAILURE,
        timestamp=timestamp,
    )
