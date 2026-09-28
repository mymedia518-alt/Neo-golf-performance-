"""PlayerProvider -- the single generic entry point for loading a
player's real PLAYER_HISTORY.json by player code.

MISSION "PLAYER COMPARISON, ARCHITECTURE FIRST" (2026-09-28): "Everything
must work from PlayerProvider(player_code). No component may reference
playerCode=10097 directly." Before this module, the report engine
(player_history_report.py, then named player_history_10097_report.py)
hardcoded its own REPORT_PATH to player 10097's file -- the only real
coupling to one player left anywhere in the render engine, once you
exclude docstrings/comments. This module replaces that hardcoded path
with one real, tested, player-code-driven loader: every caller (a
single-player page, or a future Compare Mode rendering two players'
docs through the same components) goes through the same function.

This module owns loading ONLY. It never renders anything and it never
computes anything -- reconciliation, season replay, career DNA, etc.
are the builder scripts' job (e.g. scripts/build_10097_player_history.py
for playerCode=10097), and remain player-specific for now; generalizing
that data-build pipeline is explicitly out of scope for this pass
("Architecture first. Data second. Players last.")."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from klpga.tournament_context import CONTENT_DIR


def player_history_path(player_code: str) -> Path:
    """The one real, generic path shape every player's built
    PLAYER_HISTORY.json lives at -- never assembled ad hoc by a caller."""
    return CONTENT_DIR / "knowledge_engine" / "player_intelligence" / str(player_code) / "PLAYER_HISTORY.json"


def load_player_history(player_code: str) -> Optional[dict]:
    """Real doc in, or None if this player has no built PLAYER_HISTORY.json
    yet -- never a fabricated empty doc standing in for missing data."""
    path = player_history_path(player_code)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


class PlayerProvider:
    """Thin, explicit wrapper around load_player_history for call sites
    that want a named object rather than a bare function -- e.g. Compare
    Mode, which holds one provider per player being compared
    (PlayerProvider('10097'), PlayerProvider('9431')) and calls
    .history() on each to get the two real docs it renders side by
    side through the same components."""

    def __init__(self, player_code: str):
        self.player_code = str(player_code)

    def history(self) -> Optional[dict]:
        return load_player_history(self.player_code)
