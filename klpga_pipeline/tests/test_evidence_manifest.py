from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from klpga.evidence.manifest import EvidenceManifestError, load_and_verify_manifest, verify_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "klpga_pipeline" / "evidence" / "beta001" / "manifest.json"


def _fixture(tmp_path: Path) -> tuple[dict, Path]:
    stages = []
    for stage in ("PRE", "R1", "R2", "R3"):
        artifact = tmp_path / f"{stage.lower()}.txt"
        artifact.write_bytes(f"frozen-{stage}".encode())
        stages.append({
            "stage": stage,
            "stable_intended_url": f"/tournaments/x/{stage.lower()}/",
            "source_artifact": artifact.name,
            "artifact_type": "test",
            "publication_provenance": {
                "classification": "reconstructed" if stage == "PRE" else "published_original",
                "git_commit": "a" * 40,
                "commit_timestamp": "2026-01-01T00:00:00Z",
                "publication_timestamp": None,
                "build_timestamp": None,
                "evidence_basis": "test evidence",
            },
            "prediction_id": stage,
            "model_version": "test-v1",
            "data_cutoff": "before round",
            "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "immutability_status": "protected",
            "notes": "rerun reconstruction, never original" if stage == "PRE" else "published artifact",
        })
    return {
        "schema_version": "neo_forecast_evidence_manifest_v1",
        "forecast_only": True,
        "final_result_record": None,
        "stages": stages,
    }, tmp_path


def test_real_manifest_schema_required_stages_and_checksums():
    verified = load_and_verify_manifest(MANIFEST_PATH, REPO_ROOT)
    assert tuple(verified) == ("PRE", "R1", "R2", "R3")


def test_mutation_detection(tmp_path):
    data, root = _fixture(tmp_path)
    verify_manifest(data, root)
    (root / "r2.txt").write_bytes(b"changed-by-later-generator")
    with pytest.raises(EvidenceManifestError, match="mutation detected"):
        verify_manifest(data, root)


def test_missing_artifact_detection(tmp_path):
    data, root = _fixture(tmp_path)
    (root / "r1.txt").unlink()
    with pytest.raises(EvidenceManifestError, match="artifact missing"):
        verify_manifest(data, root)


def test_duplicate_stage_detection(tmp_path):
    data, root = _fixture(tmp_path)
    data["stages"][1]["stage"] = "PRE"
    with pytest.raises(EvidenceManifestError, match="duplicate stage"):
        verify_manifest(data, root)


def test_two_stages_cannot_share_artifact(tmp_path):
    data, root = _fixture(tmp_path)
    data["stages"][1]["source_artifact"] = data["stages"][0]["source_artifact"]
    with pytest.raises(EvidenceManifestError, match="same artifact"):
        verify_manifest(data, root)


def test_provenance_fields_required(tmp_path):
    data, root = _fixture(tmp_path)
    del data["stages"][0]["publication_provenance"]["git_commit"]
    with pytest.raises(EvidenceManifestError, match="missing provenance"):
        verify_manifest(data, root)


def test_reconstructed_evidence_cannot_be_called_original(tmp_path):
    data, root = _fixture(tmp_path)
    data["stages"][0]["publication_provenance"]["classification"] = "published_original"
    with pytest.raises(EvidenceManifestError, match="contradictory reconstruction"):
        verify_manifest(data, root)


def test_reconstruction_must_be_disclosed(tmp_path):
    data, root = _fixture(tmp_path)
    data["stages"][0]["notes"] = "original publication"
    with pytest.raises(EvidenceManifestError, match="disclosed explicitly"):
        verify_manifest(data, root)


def test_final_is_excluded_from_forecast_evidence(tmp_path):
    data, root = _fixture(tmp_path)
    data["stages"][3]["stage"] = "FINAL"
    with pytest.raises(EvidenceManifestError, match="required forecast stages"):
        verify_manifest(data, root)


@pytest.mark.parametrize("field", ["winner", "official_result", "actual_finish_position"])
def test_result_fields_rejected_from_forecast_records(tmp_path, field):
    data, root = _fixture(tmp_path)
    data["stages"][0][field] = "forbidden"
    with pytest.raises(EvidenceManifestError, match="forbidden result field"):
        verify_manifest(data, root)


def test_manifest_artifact_must_stay_inside_repository(tmp_path):
    data, root = _fixture(tmp_path)
    data["stages"][0]["source_artifact"] = "../escape.txt"
    with pytest.raises(EvidenceManifestError, match="escapes repository root"):
        verify_manifest(data, root)


def test_manifest_json_has_no_duplicate_stage_names():
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    stages = [record["stage"] for record in data["stages"]]
    assert len(stages) == len(set(stages))
