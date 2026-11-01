"""S-OIL CHAMPIONSHIP (game_code 2026100001) R3 ARCHIVE -- version-locked
snapshot of the R3-point-in-time forecast and the public R3/home pages
it produced, taken at base_commit a91e56a0 (the exact local state right
before FR/final-round data collection begins).

Purpose: per the tournament-end operating procedure, the R3-point-in-time
forecast (TOP20/TOP10/TOP5/win probabilities, computed from R1-R3 scores
and official SG only) must be preserved EXACTLY as it was before any FR
data is collected, so later FR-vs-forecast validation always compares
against the real, unmodified prediction -- never a value quietly
recomputed with hindsight.

Follows the exact pattern already established by
145_archive_hana_pre_snapshot.py / PRE_ARCHIVE_MANIFEST_V1.json:
every file is read via `git show <base_commit>:<path>` (never the
working tree, so the archive is pinned to that exact commit regardless
of later edits), written ONLY under
content/website_v2/archive/2026100001/r3/<original repo-relative
path>, and a hard assertion refuses to run if any target path (or the
manifest itself) already exists -- so re-running this script can never
silently overwrite a prior archive.

Categories archived:
  INPUT  -- the official per-round score/SG files and the R3-point
            forecast itself, which scripts/283 actually reads
  OUTPUT -- the built public pages (R3 page + home, whose R3 section
            and video this forecast/data produced)
  VERIFY -- the executable scripts that reproduce OUTPUT from INPUT
            (282/283/284/281/285/287)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "a91e56a0"
GAME_CODE = "2026100001"
ARCHIVE_BASE = KLPGA_ROOT / "content" / "website_v2" / "archive" / GAME_CODE / "r3"

FILES: list[tuple[str, str]] = [
    # INPUT
    ("INPUT", "klpga_pipeline/content/website_v2/SOIL_2026100001_R1_SG_OFFICIAL_V1.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/SOIL_2026100001_R2_OFFICIAL_V1.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/SOIL_2026100001_R2_SG_OFFICIAL_V1.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/SOIL_2026100001_R3_OFFICIAL_V1.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/SOIL_2026100001_R3_SG_OFFICIAL_V1.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/SOIL_2026100001_POST_R3_FORECAST_V1.json"),
    # OUTPUT
    ("OUTPUT", "docs/tournaments/2026/2026100001/r3/index.html"),
    ("OUTPUT", "docs/index.html"),
    # VERIFY (executable chain that reproduces OUTPUT from INPUT)
    ("VERIFY", "klpga_pipeline/scripts/282_build_soil_2026100001_r3_official.py"),
    ("VERIFY", "klpga_pipeline/scripts/283_build_soil_2026100001_post_r3_forecast.py"),
    ("VERIFY", "klpga_pipeline/scripts/284_build_soil_2026100001_r3_sg_official.py"),
    ("VERIFY", "klpga_pipeline/scripts/281_build_soil_2026100001_r3_page.py"),
    ("VERIFY", "klpga_pipeline/scripts/285_patch_home_soil_r3_summary.py"),
    ("VERIFY", "klpga_pipeline/scripts/287_patch_home_soil_r3_video.py"),
]


def git_show_bytes(path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{BASE_COMMIT}:{path}"],
        cwd=REPO_ROOT, capture_output=True, check=True,
    )
    return result.stdout


def git_blob_sha256(path: str) -> str:
    return hashlib.sha256(git_show_bytes(path)).hexdigest()


def main() -> None:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert head.startswith(BASE_COMMIT), f"HEAD is {head}, expected base commit {BASE_COMMIT} -- refusing to archive"

    manifest_records = []
    for category, rel_path in FILES:
        archive_path = ARCHIVE_BASE / rel_path
        assert not archive_path.exists(), f"refusing to overwrite existing archive file: {archive_path}"

        content = git_show_bytes(rel_path)
        sha_before = hashlib.sha256(content).hexdigest()

        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(content)

        sha_after = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        sha_independent = git_blob_sha256(rel_path)
        assert sha_before == sha_after == sha_independent, (
            f"sha256 mismatch for {rel_path}: before={sha_before} after={sha_after} independent={sha_independent}"
        )

        manifest_records.append({
            "category": category,
            "original_path": rel_path,
            "archive_path": str(archive_path.relative_to(KLPGA_ROOT.parent)),
            "sha256": sha_after,
            "bytes": len(content),
            "base_commit": head,
        })
        print(f"[{category}] {rel_path} -> sha256={sha_after[:12]}... ({len(content)} bytes)")

    manifest = {
        "schema_version": "r3_archive_manifest_v1",
        "purpose": (
            "Version-locked snapshot of the R3-point-in-time forecast "
            "(TOP20/TOP10/TOP5/win probabilities computed from R1-R3 "
            "official scores and SG only, before any FR/final data "
            "existed) and the public R3/home pages it produced -- "
            "purely additive, never overwrites any file outside this "
            "archive directory, and this script refuses to overwrite an "
            "already-archived file even on re-run."
        ),
        "base_commit": head,
        "base_branch": "feature/soil-fr-finalize (branched from local neo-website-v2 @ a91e56a0)",
        "archived_at_utc": None,
        "archive_root": str(ARCHIVE_BASE.relative_to(KLPGA_ROOT.parent)),
        "file_count": len(manifest_records),
        "verification": (
            "Each file's sha256 was computed three ways and cross-checked "
            "for exact agreement: (1) the bytes read from `git show "
            "<base_commit>:<path>` before writing, (2) the bytes re-read "
            "from the archived copy on disk after writing, (3) an "
            "independently re-invoked `git show` hash computed after the "
            "write completed. All three matched for every one of the "
            f"{len(manifest_records)} files."
        ),
        "records": manifest_records,
    }
    import datetime
    manifest["archived_at_utc"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    manifest_path = ARCHIVE_BASE / "R3_ARCHIVE_MANIFEST_V1.json"
    assert not manifest_path.exists(), f"refusing to overwrite existing manifest: {manifest_path}"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"wrote manifest: {manifest_path} ({len(manifest_records)} files)")


if __name__ == "__main__":
    main()
