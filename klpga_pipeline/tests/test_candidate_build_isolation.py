"""OWNER QA HARD STOP regression coverage: calling a real build() must
never mutate git-tracked files under the real candidate/ directory.

Root cause (see tests/conftest.py and klpga.tournament_context.candidate_dir
for the fix): scripts/84, 86, and 88 used to hardcode their OUTPUT/OUT
constant as `ROOT / "candidate" / <name>` -- the real, git-tracked
directory -- evaluated once at module import time. Every test that calls
the module's real build() (deliberate, to verify actual generated HTML
rather than a mock) therefore wrote real files into the tracked
repository tree: a fresh neo-build-id/neo-build-source-commit provenance
stamp on every generated page (see
klpga.website_v2.global_navigation.inject_build_provenance), never real
content, but `git status` was left dirty after every test run regardless.

The fix routes OUTPUT/OUT through candidate_dir(), which resolves under
KLPGA_CANDIDATE_ROOT_OVERRIDE -- a disposable temp directory that
tests/conftest.py's pytest_configure hook sets before test collection
begins -- instead of the real candidate/ tree. This test proves that
property by hashing the real, tracked candidate/ directory before and
after invoking every affected script's build() and asserting zero
difference, rather than merely trusting the plumbing.
"""
from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BUILD_SCRIPTS = (
    "84_build_ok_open_pre_website_candidate.py",
    "86_build_neo_data_home_candidate.py",
    "88_build_neo_top120_candidate.py",
)


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / name)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _tracked_candidate_status() -> str:
    """Working-tree status of every git-tracked path under candidate/,
    relative to whatever it was before this test ran -- not asserting a
    pristine starting point (a real environment may have unrelated,
    already-committed-pending changes from a manual script run), only
    that build() adds nothing on top of it."""
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "candidate"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout


def test_build_functions_never_mutate_tracked_candidate_directory():
    before = _tracked_candidate_status()

    for name in BUILD_SCRIPTS:
        mod = _load_script(name)
        mod.build()

    after = _tracked_candidate_status()
    assert after == before, (
        "a build() call mutated git-tracked candidate/ files -- "
        "OUTPUT/OUT must resolve through klpga.tournament_context.candidate_dir(), "
        "never a hardcoded `ROOT / \"candidate\" / ...` literal\n"
        f"--- before ---\n{before}\n--- after ---\n{after}"
    )


def test_candidate_dir_honors_the_pytest_override():
    """Direct check on the mechanism itself, independent of any one
    script: under pytest, candidate_dir() must never resolve inside the
    real repository tree."""
    from klpga.tournament_context import CANDIDATE_ROOT, candidate_dir

    real_candidate = ROOT / "candidate"
    assert CANDIDATE_ROOT != real_candidate
    resolved = candidate_dir("anything")
    assert real_candidate not in (resolved, *resolved.parents)
