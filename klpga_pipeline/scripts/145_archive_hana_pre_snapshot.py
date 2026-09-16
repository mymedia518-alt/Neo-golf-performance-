"""HANA PRE -- version-locked archive of the exact raw/input/output/
verification materials that produced the live Hana PRE page at a fixed
base commit (fix/hana-2026090002-pre-20260915, c7a2857).

Purely additive: every archived file is read via `git show
<commit>:<path>` (never the working tree, so the archive is pinned to
that exact commit regardless of later edits) and written ONLY under
content/website_v2/archive/2026090002/pre/<original repo-relative
path> -- a hard assertion refuses to run if any target path already
exists, so re-running this script (or running it after later commits)
can never silently overwrite a prior archive. No existing file
anywhere else in the repo is ever touched.

Categories archived (the exact set actually used by
139_build_hana_pre_kb_structure.py at the base commit, traced from its
own _load()/sources calls -- never a broader "everything Hana-named"
sweep, and never a superseded V1/V2 predecessor that the final build
no longer reads):

  RAW      -- official capture HTML the derivation scripts parsed
  INPUT    -- the derived JSON files 139 actually loads (entry list,
              flag match, player analysis input, SG sorted, M4
              candidate, amateur KGA analysis, the 4 sponsor evidence
              sources)
  OUTPUT   -- the built public pages (Hana PRE + HOME, byte-identical
              <main> per the build's own invariant)
  VERIFY   -- the executable scripts that reproduce OUTPUT from
              RAW/INPUT (139 itself, plus 130/141/142/143/144)

Writes PRE_ARCHIVE_MANIFEST_V1.json alongside the archived files,
recording each file's category, original path, archive path, sha256
(computed independently before and after write, both checked against
the sha256 `git show` itself would produce for that blob), and the
base commit this whole snapshot is pinned to.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KLPGA_ROOT = Path(__file__).resolve().parents[1]
BASE_COMMIT = "c7a28578fa3652a3295e1377f8411753a393a1d9"
ARCHIVE_BASE = KLPGA_ROOT / "content" / "website_v2" / "archive" / "2026090002" / "pre"

FILES: list[tuple[str, str]] = [
    # RAW
    ("RAW", "klpga_pipeline/content/website_v2/incoming_evidence/2026090002/HANA_2026090002_ENTRY_LIST_RAW_V2.html"),
    ("RAW", "klpga_pipeline/content/website_v2/incoming_evidence/2026090002/KLPGA_KRANKING_2026_LATEST_V2_RAW.html"),
    ("RAW", "klpga_pipeline/content/website_v2/incoming_evidence/2026090003/KLPGA_KRANKING_2026_W36_RAW.html"),
    # INPUT (exactly what 139 loads, per its own _load()/sponsor-sources calls)
    ("INPUT", "klpga_pipeline/content/website_v2/HANA_2026090002_ENTRY_FLAG_MATCH_V2.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/HANA_2026090002_OFFICIAL_ENTRY_LIST_V2.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/HANA_2026090002_PLAYER_ANALYSIS_INPUT_V4.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/HANA_2026090002_SEASON_SG_SORTED_V3.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/HANA_2026090002_PRE_M4_60000_CANDIDATE_V2.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/HANA_2026090002_AMATEUR_KGA_ANALYSIS_V1.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V3.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2.json"),
    ("INPUT", "klpga_pipeline/content/website_v2/OPERATOR_REPORTED_SPONSOR_EVIDENCE_V3.json"),
    # OUTPUT
    ("OUTPUT", "docs/tournaments/2026/2026090002/pre/index.html"),
    ("OUTPUT", "docs/index.html"),
    # VERIFY (executable chain that reproduces OUTPUT from RAW/INPUT)
    ("VERIFY", "klpga_pipeline/scripts/130_build_hana_pre_m4.py"),
    ("VERIFY", "klpga_pipeline/scripts/139_build_hana_pre_kb_structure.py"),
    ("VERIFY", "klpga_pipeline/scripts/141_regenerate_hana_entry_list_v2.py"),
    ("VERIFY", "klpga_pipeline/scripts/142_rebuild_hana_player_input_for_roster_swap.py"),
    ("VERIFY", "klpga_pipeline/scripts/143_refresh_hana_kranking_from_latest_capture.py"),
    ("VERIFY", "klpga_pipeline/scripts/144_recover_hana_sponsor_evidence.py"),
]


def git_show_bytes(path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{BASE_COMMIT}:{path}"],
        cwd=REPO_ROOT, capture_output=True, check=True,
    )
    return result.stdout


def git_blob_sha256(path: str) -> str:
    """Independent cross-check: hash of the exact bytes `git show` returns
    for this path at BASE_COMMIT, computed the same way the archived
    copy's own sha256 is computed -- catches any transcription error."""
    return hashlib.sha256(git_show_bytes(path)).hexdigest()


def main() -> None:
    # Confirm the worktree's current HEAD really is BASE_COMMIT before
    # trusting `git show` at all -- refuses to proceed on a detached or
    # different checkout.
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert head == BASE_COMMIT, f"HEAD is {head}, expected base commit {BASE_COMMIT} -- refusing to archive"

    manifest_records = []
    for category, rel_path in FILES:
        archive_path = ARCHIVE_BASE / rel_path
        assert not archive_path.exists(), f"refusing to overwrite existing archive file: {archive_path}"

        content = git_show_bytes(rel_path)
        sha_before = hashlib.sha256(content).hexdigest()

        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(content)

        # re-read from disk and re-hash -- proves the write was faithful
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
            "base_commit": BASE_COMMIT,
        })
        print(f"[{category}] {rel_path} -> sha256={sha_after[:12]}... ({len(content)} bytes)")

    manifest = {
        "schema_version": "pre_archive_manifest_v1",
        "purpose": (
            "Version-locked snapshot of the exact raw/input/output/verification "
            "materials that produced the Hana PRE (game_code 2026090002) public "
            "page at base_commit -- purely additive, never overwrites any file "
            "outside this archive directory, and this script refuses to "
            "overwrite an already-archived file even on re-run."
        ),
        "base_commit": BASE_COMMIT,
        "base_branch": "fix/hana-2026090002-pre-20260915",
        "archived_at_utc": "2026-09-16T19:45:00Z",
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
    manifest_path = ARCHIVE_BASE / "PRE_ARCHIVE_MANIFEST_V1.json"
    assert not manifest_path.exists(), f"refusing to overwrite existing manifest: {manifest_path}"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print()
    print(f"wrote manifest: {manifest_path} ({len(manifest_records)} files)")


if __name__ == "__main__":
    main()
