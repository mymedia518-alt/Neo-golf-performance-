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

from pathlib import Path


def player_report_exists(player_id: str, repo_root: Path) -> bool:
    """True iff docs/player/{player_id}/index.html is a real, already-
    built file -- the one fact this module ever checks. Never guesses
    from a population list or a name; a player with no built page is
    never linked, however "known" they are elsewhere in the pipeline."""
    return (repo_root / "docs" / "player" / str(player_id) / "index.html").is_file()


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
