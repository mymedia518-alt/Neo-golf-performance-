"""Tests for klpga_pipeline/scripts/145_archive_hana_pre_snapshot.py --
the PRE stage's write-once archive script. Locks down the two
invariants docs/OPERATING_RULES.md rule 2 ("archives are write-once")
depends on: (1) every file already recorded in a stage's
ARCHIVE_MANIFEST still matches its recorded sha256 right now -- a live
tripwire against any future stage's build script accidentally touching
a prior stage's archive, and (2) the archiving script's own overwrite
guard actually fires when a target archive path already exists -- the
mechanism that makes "PRE files can never be overwritten once R1 (or
any later stage) starts" true structurally, not just by convention."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = REPO_ROOT / "klpga_pipeline"

ARCHIVE_MANIFESTS = sorted(
    (KLPGA_ROOT / "content" / "website_v2" / "archive").glob("*/*/PRE_ARCHIVE_MANIFEST_V1.json")
)


def _load_archive_module():
    spec = importlib.util.spec_from_file_location(
        "_archive_hana_pre_snapshot",
        KLPGA_ROOT / "scripts" / "145_archive_hana_pre_snapshot.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "manifest_path", ARCHIVE_MANIFESTS, ids=lambda p: str(p.relative_to(KLPGA_ROOT))
)
def test_archived_files_match_recorded_sha256(manifest_path):
    """Regression tripwire: nothing may ever change bytes under an
    already-archived stage directory, whatever build script runs next
    for a later stage of this or any tournament."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["records"], f"empty manifest: {manifest_path}"
    for record in manifest["records"]:
        archive_file = REPO_ROOT / record["archive_path"]
        assert archive_file.is_file(), f"archived file missing from disk: {archive_file}"
        actual_sha256 = hashlib.sha256(archive_file.read_bytes()).hexdigest()
        assert actual_sha256 == record["sha256"], (
            f"{archive_file} sha256 drifted from its manifest record -- "
            f"an archived file was overwritten (expected {record['sha256']}, got {actual_sha256})"
        )


def test_dataset_summary_amendment_is_additive_and_present():
    """docs/OPERATING_RULES.md rule 1: a stage's manifest must record its
    key published facts. 146_amend_hana_pre_archive_manifest_summary.py
    added these without touching any pre-existing manifest field --
    this locks that contract down going forward."""
    manifest_path = (
        KLPGA_ROOT / "content" / "website_v2" / "archive" / "2026090002" / "pre" / "PRE_ARCHIVE_MANIFEST_V1.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["base_commit"] == "c7a28578fa3652a3295e1377f8411753a393a1d9"
    assert manifest["file_count"] == 21
    summary = manifest["dataset_summary"]
    assert summary["game_code"] == "2026090002"
    assert summary["total_players"] == 108
    assert summary["band_insufficient_count"] == 8
    assert summary["kim_rian_9702_k_rank"] == 135
    assert "excluded" in summary["park_hyun_kyung_9130_status"]


def test_archive_script_refuses_to_overwrite_existing_target():
    """The actual mechanism behind 'PRE files can never be overwritten
    after R1 starts': 145's own archive_path.exists() guard. Exercises
    the real module (not a re-implementation) against a throwaway
    target directory and a single small, real, already-committed file
    (Readme.md at the current HEAD) so no real archive state is
    touched."""
    module = _load_archive_module()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()

    scratch_base = KLPGA_ROOT / "_test_archive_scratch_146"
    assert not scratch_base.exists(), f"leftover scratch dir from a prior run: {scratch_base}"
    try:
        module.BASE_COMMIT = head
        module.ARCHIVE_BASE = scratch_base
        module.FILES = [("TEST", "Readme.md")]

        module.main()  # first run succeeds
        written = scratch_base / "Readme.md"
        assert written.is_file()
        assert hashlib.sha256(written.read_bytes()).hexdigest() == hashlib.sha256(
            (REPO_ROOT / "Readme.md").read_bytes()
        ).hexdigest()

        with pytest.raises(AssertionError, match="refusing to overwrite"):
            module.main()  # second run against the same target must hard-stop
    finally:
        if scratch_base.exists():
            shutil.rmtree(scratch_base)
