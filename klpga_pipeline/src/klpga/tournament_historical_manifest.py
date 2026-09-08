"""NEO TOURNAMENT PIPELINE Phase 5 (FINAL -> POSTMORTEM resume /
historical handoff): a generic, append-only terminal manifest written
once per tournament right after a genuinely valid POSTMORTEM.

Downstream historical-truth consumers should read ONE validated
manifest (real hashes/identity for every source artifact) rather than
reaching into mutable loose files directly -- a source file edited or
regenerated after the manifest was written is detectable, not silently
trusted.

Never overwrites an existing manifest: once written for a game_code,
it is immutable historical record, append-only across tournaments
(each game_code gets its own manifest artifact via the generic
artifact_path contract), never versioned-in-place.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from klpga.tournament_context import TournamentContext


class HistoricalManifestBlocked(RuntimeError):
    """A recorded manifest hash no longer matches the current source
    file -- the source was altered/regenerated after the manifest was
    written. Ingestion must fail closed, never trust a stale record."""


def _hash_if_exists(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _artifact_record(path: Path) -> dict:
    return {"path": path.name, "sha256": _hash_if_exists(path), "present": path.is_file()}


def build_historical_manifest(context: TournamentContext) -> dict:
    """Real hashes only -- never a fabricated or estimated identity for
    a missing artifact (present=False, sha256=None instead)."""
    round_snapshots = {
        str(n): _artifact_record(context.artifact_path(f"r{n}_live_snapshot"))
        for n in range(1, context.final_round_number + 1)
    }
    return {
        "schema_version": 1,
        "artifact": "historical_terminal_manifest",
        "game_code": context.game_code,
        "tournament_name": context.tournament_name,
        "final_round_number": context.final_round_number,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "entry_snapshot": _artifact_record(context.artifact_path("entry_snapshot")),
        "pre_features_frozen_source": _artifact_record(context.artifact_path("pre_performance_snapshot")),
        "k_ranking_provenance": _artifact_record(context.artifact_path("official_klpga_ranking")),
        "round_snapshots": round_snapshots,
        "final_snapshot": round_snapshots.get(str(context.final_round_number)),
        "postmortem_report": _artifact_record(context.artifact_path("postmortem_report")),
    }


def write_historical_manifest_if_absent(context: TournamentContext) -> tuple[Path, bool]:
    """-> (manifest_path, written_this_call). Append-only: if a manifest
    already exists for this game_code, it is returned unchanged --
    never overwritten, even if the underlying source artifacts have
    since changed (that staleness is what validate_historical_manifest
    below is for, at read time)."""
    out_path = context.artifact_path("historical_terminal_manifest")
    if out_path.is_file():
        return out_path, False
    manifest = build_historical_manifest(context)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path, True


def ingest_terminal_manifest(context: TournamentContext) -> dict:
    """The one generic read path a historical-truth consumer should
    use instead of reaching into mutable loose files directly. Re-
    hashes every artifact the manifest recorded and raises
    HistoricalManifestBlocked the moment any recorded hash no longer
    matches the artifact currently on disk -- a source altered after
    the manifest was written must never be silently ingested as if it
    still matched the validated terminal record."""
    path = context.artifact_path("historical_terminal_manifest")
    if not path.is_file():
        raise HistoricalManifestBlocked(f"no historical terminal manifest at {path} -- nothing to ingest")
    manifest = json.loads(path.read_text(encoding="utf-8"))

    def _check(record: dict | None, artifact_type: str) -> None:
        if not record or not record.get("present"):
            return
        current = context.artifact_path(artifact_type)
        actual_hash = _hash_if_exists(current)
        if actual_hash != record.get("sha256"):
            raise HistoricalManifestBlocked(
                f"{artifact_type} has changed since the terminal manifest was written "
                f"(recorded sha256={record.get('sha256')!r}, current={actual_hash!r})"
            )

    _check(manifest.get("entry_snapshot"), "entry_snapshot")
    _check(manifest.get("pre_features_frozen_source"), "pre_performance_snapshot")
    _check(manifest.get("k_ranking_provenance"), "official_klpga_ranking")
    _check(manifest.get("postmortem_report"), "postmortem_report")
    for n_str, record in (manifest.get("round_snapshots") or {}).items():
        _check(record, f"r{n_str}_live_snapshot")

    return manifest
