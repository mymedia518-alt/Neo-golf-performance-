"""Strict validation for NEO forecast-evidence manifests.

This module is deliberately read-only. It hashes existing artifacts and fails
closed; it has no API that writes, updates, repairs, or regenerates evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "neo_forecast_evidence_manifest_v1"
REQUIRED_STAGES = ("PRE", "R1", "R2", "R3")
ALLOWED_PROVENANCE = {"published_original", "reconstructed"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_RECORD_FIELDS = {
    "stage", "stable_intended_url", "source_artifact", "artifact_type",
    "publication_provenance", "prediction_id", "model_version", "data_cutoff",
    "sha256", "immutability_status", "notes",
}
REQUIRED_PROVENANCE_FIELDS = {
    "classification", "git_commit", "commit_timestamp", "publication_timestamp",
    "build_timestamp", "evidence_basis",
}
FORBIDDEN_RESULT_FIELDS = {
    "final", "result", "results", "winner", "final_result", "official_result",
    "actual_finish_position", "actual_winner", "result_data",
}


class EvidenceManifestError(ValueError):
    """Raised when evidence is ambiguous, incomplete, missing, or mutated."""


def _fail(message: str) -> None:
    raise EvidenceManifestError(message)


def _forbidden_keys(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in FORBIDDEN_RESULT_FIELDS:
                _fail(f"{location}: forecast record contains forbidden result field {key!r}")
            _forbidden_keys(nested, f"{location}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _forbidden_keys(nested, f"{location}[{index}]")


def _resolve_artifact(repo_root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        _fail(f"source_artifact must be a non-empty repository-relative path: {relative_path!r}")
    root = repo_root.resolve()
    artifact = (root / relative_path).resolve()
    try:
        artifact.relative_to(root)
    except ValueError:
        _fail(f"source_artifact escapes repository root: {relative_path!r}")
    return artifact


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(data: dict[str, Any], repo_root: Path) -> dict[str, str]:
    if data.get("schema_version") != SCHEMA_VERSION:
        _fail(f"unsupported schema_version: {data.get('schema_version')!r}")
    if data.get("forecast_only") is not True:
        _fail("forecast_only must be true")
    if data.get("final_result_record", "missing") is not None:
        _fail("FINAL/result records must remain separate from forecast evidence")

    stages = data.get("stages")
    if not isinstance(stages, list):
        _fail("stages must be a list")
    names = [record.get("stage") for record in stages if isinstance(record, dict)]
    if len(names) != len(stages):
        _fail("every stage entry must be an object")
    if len(set(names)) != len(names):
        _fail("duplicate stage detected")
    if set(names) != set(REQUIRED_STAGES):
        _fail(f"required forecast stages are exactly {REQUIRED_STAGES}; got {tuple(names)}")

    artifact_names: set[str] = set()
    verified: dict[str, str] = {}
    for record in stages:
        stage = record["stage"]
        missing = REQUIRED_RECORD_FIELDS - set(record)
        if missing:
            _fail(f"{stage}: missing required fields: {sorted(missing)}")
        provenance = record["publication_provenance"]
        if not isinstance(provenance, dict):
            _fail(f"{stage}: publication_provenance must be an object")
        missing_provenance = REQUIRED_PROVENANCE_FIELDS - set(provenance)
        if missing_provenance:
            _fail(f"{stage}: missing provenance fields: {sorted(missing_provenance)}")
        classification = provenance.get("classification")
        if classification not in ALLOWED_PROVENANCE:
            _fail(f"{stage}: invalid provenance classification {classification!r}")
        if classification == "reconstructed" and "reconstruct" not in record["notes"].lower():
            _fail(f"{stage}: reconstructed evidence must be disclosed explicitly in notes")
        notes_lower = record["notes"].lower()
        if classification == "published_original" and (
            "rerun reconstruction" in notes_lower or "is a reconstruction" in notes_lower
        ):
            _fail(f"{stage}: original evidence has contradictory reconstruction wording")

        relative = record["source_artifact"]
        normalized = Path(relative).as_posix().lower()
        if normalized in artifact_names:
            _fail(f"{stage}: two stages point to the same artifact: {relative}")
        artifact_names.add(normalized)
        artifact = _resolve_artifact(repo_root, relative)
        if not artifact.is_file():
            _fail(f"{stage}: evidence artifact missing: {relative}")
        expected = record["sha256"]
        if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
            _fail(f"{stage}: sha256 must be 64 lowercase hexadecimal characters")
        actual = sha256_file(artifact)
        if actual != expected:
            _fail(f"{stage}: evidence mutation detected for {relative}: expected {expected}, got {actual}")
        _forbidden_keys(record, f"stage[{stage}]")
        verified[stage] = actual

    return verified


def load_and_verify_manifest(manifest_path: Path, repo_root: Path | None = None) -> dict[str, str]:
    manifest_path = Path(manifest_path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceManifestError(f"cannot read evidence manifest {manifest_path}: {exc}") from exc
    if repo_root is None:
        repo_root = manifest_path.resolve().parents[3]
    return verify_manifest(data, Path(repo_root))
