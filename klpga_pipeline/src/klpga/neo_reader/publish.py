"""Stage 6: GitHub upload. Stages the exact, explicit set of paths NEO
Sync itself just wrote (raw/<game_code>, normalized/<game_code>,
reports/<game_code>, content/website_v2/<game_code>_*.json) -- never
`git add -A`/`git add .` -- commits them, and pushes to a dedicated
`reader/<game_code>` branch. Never touches the production branch
(neo-website-v2) directly: this branch is left for explicit review/
merge, the same "never auto-merge into production" discipline this
whole project already follows for its automation pipeline.

Refuses to run (returns a PublishResult with ok=False) if validation
did not PASS -- publishing an artifact set the review report itself
says not to trust would defeat the entire point of stage 5."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PublishResult:
    ok: bool
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    message: str = ""
    staged_paths: list = field(default_factory=list)


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True, text=True,
    )


def publish_sync_artifacts(
    repo_root: Path,
    game_code: str,
    event_name: str,
    *,
    raw_root: Path,
    normalized_root: Path,
    reports_root: Path,
    content_root: Path,
    validation_ok: bool,
    branch_prefix: str = "reader",
) -> PublishResult:
    if not validation_ok:
        return PublishResult(ok=False, message="Refusing to publish: validation did not PASS. See the review report.")

    branch = f"{branch_prefix}/{game_code}"

    def _rel(p: Path) -> str:
        return str(p.relative_to(repo_root))

    paths = []
    for root in (raw_root / game_code, normalized_root / game_code, reports_root / game_code):
        if root.exists():
            paths.append(_rel(root))
    content_hits = sorted(content_root.glob(f"{game_code}_*.json"))
    paths.extend(_rel(p) for p in content_hits)

    if not paths:
        return PublishResult(ok=False, message=f"Nothing to publish -- no sync artifacts found on disk for gameCode={game_code}.")

    current_branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()

    checkout = _run_git(repo_root, ["checkout", "-B", branch])
    if checkout.returncode != 0:
        return PublishResult(ok=False, message=f"git checkout -B {branch} failed: {checkout.stderr.strip()}")

    add = _run_git(repo_root, ["add", "--", *paths])
    if add.returncode != 0:
        _run_git(repo_root, ["checkout", current_branch])
        return PublishResult(ok=False, message=f"git add failed: {add.stderr.strip()}")

    diff_check = _run_git(repo_root, ["diff", "--cached", "--quiet"])
    if diff_check.returncode == 0:
        _run_git(repo_root, ["checkout", current_branch])
        return PublishResult(ok=True, branch=branch, message="Nothing changed -- these artifacts are already committed on this branch.", staged_paths=paths)

    commit_message = f"NEO Sync: collect {game_code} ({event_name})"
    commit = _run_git(repo_root, ["commit", "-m", commit_message])
    if commit.returncode != 0:
        _run_git(repo_root, ["checkout", current_branch])
        return PublishResult(ok=False, message=f"git commit failed: {commit.stderr.strip()}")

    commit_sha = _run_git(repo_root, ["rev-parse", "HEAD"]).stdout.strip()

    push = _run_git(repo_root, ["push", "-u", "origin", branch])
    _run_git(repo_root, ["checkout", current_branch])

    if push.returncode != 0:
        return PublishResult(
            ok=False, branch=branch, commit_sha=commit_sha, staged_paths=paths,
            message=f"Committed locally ({commit_sha[:12]}) but push failed: {push.stderr.strip()}",
        )

    return PublishResult(
        ok=True, branch=branch, commit_sha=commit_sha, staged_paths=paths,
        message=f"Pushed {branch} ({commit_sha[:12]}) — review and merge into the production branch when ready.",
    )
