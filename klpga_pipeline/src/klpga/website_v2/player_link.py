"""THE PERMANENT CONTRACT (2026-09-29): the one function every player-
name renderer calls to decide whether a name links to
/player/{player_id}/:

    if player_report_exists(player_id):
        render link
    else:
        render plain text

Callers pass only a player_id -- never a repo path, never a file check,
never a git call of their own. What actually counts as a "production-
ready report" is decided entirely inside this module, so that rule can
change later without touching a single renderer. No player_id is ever
hardcoded here or in any caller; the answer is always computed fresh
from real, already-existing signals.

MISSION (2026-09-29): "Any player with a generated report must
automatically become clickable everywhere the player's name appears --
Entry List, Leaderboard, K-Ranking, Tournament Results, HOME sections.
No manual whitelist. No hardcoded players."

Operator note (2026-09-29): the current internal signal (a player's
PLAYER_HISTORY.json committed to git -- see _reviewed_player_ids) is
explicitly interim, "acceptable for now" but not the long-term rule.
It is kept isolated to one private helper for exactly that reason: a
future purpose-built "production-approved report" registry replaces
only that helper's body, never this module's public contract."""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

_MODULE_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=1)
def _repo_root() -> Optional[Path]:
    """Resolved once via git itself (git rev-parse --show-toplevel),
    the same real-repo-root resolution already established elsewhere
    in this pipeline (GIT_ROOT vs ROOT) -- never guessed by counting
    parent directories, which would silently break if this file ever
    moves. None (not an exception) if git is unavailable; every caller
    treats that as "cannot confirm anything", never as approval."""
    try:
        out = subprocess.run(
            ["git", "-C", str(_MODULE_DIR), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    return Path(out) if out else None


@lru_cache(maxsize=1)
def _reviewed_player_ids() -> frozenset:
    """INTERIM SIGNAL ONLY -- see module docstring. This repo's own
    established convention (every commit in this session) is that a
    player report earns production status only once a human reviews
    it and it gets committed; the automation pipeline's own dry-run
    test batches (10/50/50-player runs) leave dozens of real HTML
    files on disk under docs/player/ that were never reviewed and were
    deliberately never committed for exactly that reason.

    Checking PLAYER_HISTORY.json specifically (rather than the
    rendered docs/player/{id}/index.html itself) also correctly
    excludes playerCode=9431: her page is real, not a placeholder, but
    renders through her own one-off legacy engine
    (player_intelligence_9431_report.py), never the generic
    PLAYER_HISTORY.json pipeline this session has been generalizing.

    Fails closed (empty set, nothing linked) if git or the repo root
    is unavailable -- a missing signal is never treated as approval."""
    repo_root = _repo_root()
    if repo_root is None:
        return frozenset()
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files",
             "klpga_pipeline/content/website_v2/knowledge_engine/player_intelligence/*/PLAYER_HISTORY.json"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return frozenset()
    ids = set()
    for line in out.splitlines():
        parts = line.split("/")
        if len(parts) == 7 and parts[-1] == "PLAYER_HISTORY.json":
            ids.add(parts[-2])
    return frozenset(ids)


def player_report_exists(player_id: str) -> bool:
    """THE one contract (see module docstring). True iff player_id has
    a real, already-built docs/player/{player_id}/index.html AND is
    currently judged production-ready by this module's own internal
    rule. Never guesses from a population list or a name; a player who
    fails either check is never linked, however "known" they are
    elsewhere in the pipeline."""
    repo_root = _repo_root()
    if repo_root is None:
        return False
    player_id = str(player_id)
    page = repo_root / "docs" / "player" / player_id / "index.html"
    return page.is_file() and player_id in _reviewed_player_ids()


def linked_player_name_cell(player_id: str, name_cell_html: str) -> str:
    """Wraps an already-rendered name-cell HTML fragment in a link to
    /player/{player_id}/ iff player_report_exists(player_id); otherwise
    returns it unchanged. Callers build their own flag/name/sponsor
    markup exactly as before and pass the finished fragment in here --
    this module never re-implements or reaches into that markup, so a
    caller's own escaping/layout is untouched either way."""
    if player_report_exists(player_id):
        return f'<a href="/player/{player_id}/">{name_cell_html}</a>'
    return name_cell_html
