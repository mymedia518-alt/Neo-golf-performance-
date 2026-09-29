"""The one generic rule for when a player's name becomes a link.

MISSION (2026-09-29): "Any player with a generated report must
automatically become clickable everywhere the player's name appears --
Entry List, Leaderboard, K-Ranking, Tournament Results, HOME sections.
No manual whitelist. No hardcoded players." Before this module, exactly
one builder (156_build_home_page.py) linked a player's name, and it did
so with `if pid == "10097":` -- a single hardcoded special case that
happened to be the only player with a built page at the time it was
written. This module replaces that special case with the real, generic
rule it was always standing in for: a player's name links to
/player/{player_id}/ if and only if that page actually exists on disk.

No component may hardcode a player_id to decide linking, the same way
player_provider.py already forbids it for loading player data."""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=4)
def _reviewed_player_ids(repo_root: Path) -> frozenset:
    """The real, authoritative set of player_ids whose report has
    actually been reviewed and committed -- as opposed to merely
    existing as a file in the working tree. This repo's own
    established convention (see every commit in this session) is that
    a player report earns production status only once a human reviews
    it and it gets committed; the automation pipeline's own dry-run
    test batches (10/50/50-player runs) leave dozens of real HTML
    files on disk under docs/player/ that were never reviewed and were
    deliberately never committed for exactly that reason. git's own
    tracked-file list is the one real, already-existing signal for
    "reviewed", so this checks that instead of inventing a second,
    parallel approval list that could drift out of sync with what is
    actually committed. Fails closed (empty set, nothing linked) if
    git is unavailable -- a missing signal is never treated as
    approval."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "docs/player/*/index.html"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return frozenset()
    ids = set()
    for line in out.splitlines():
        parts = line.split("/")
        if len(parts) == 4 and parts[0] == "docs" and parts[1] == "player" and parts[3] == "index.html":
            ids.add(parts[2])
    return frozenset(ids)


def player_report_exists(player_id: str, repo_root: Path) -> bool:
    """True iff docs/player/{player_id}/index.html is a real, already-
    built file AND that exact file is committed to git -- i.e. a
    reviewed, production-approved report, never a merely-built dry-run
    test artifact. Never guesses from a population list or a name; a
    player with no reviewed, committed page is never linked, however
    "known" they are elsewhere in the pipeline."""
    player_id = str(player_id)
    path = repo_root / "docs" / "player" / player_id / "index.html"
    return path.is_file() and player_id in _reviewed_player_ids(repo_root)


def linked_player_name_cell(player_id: str, name_cell_html: str, repo_root: Path) -> str:
    """Wraps an already-rendered name-cell HTML fragment in a link to
    /player/{player_id}/ iff that player's report exists; otherwise
    returns it unchanged. Callers build their own flag/name/sponsor
    markup exactly as before and pass the finished fragment in here --
    this module never re-implements or reaches into that markup, so a
    caller's own escaping/layout is untouched either way."""
    if player_report_exists(player_id, repo_root):
        return f'<a href="/player/{player_id}/">{name_cell_html}</a>'
    return name_cell_html
