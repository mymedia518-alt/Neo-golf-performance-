"""Abstraction over "wherever KLPGA tournament data comes from".

klpga.collect depends only on this interface, not on requests/BeautifulSoup/
Playwright directly, so the fetching/parsing layer can be repaired or
swapped without touching orchestration logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from ..parsers.leaderboard_parser import LeaderboardRow
from ..parsers.tournament_detail_parser import TournamentDetail
from ..parsers.tournament_list_parser import TournamentListItem


class TournamentDataSource(ABC):
    @abstractmethod
    def list_recent_tournaments(self, limit: int) -> List[TournamentListItem]:
        """Most-recent-first list of up to `limit` tournaments."""

    @abstractmethod
    def fetch_tournament_detail(self, item: TournamentListItem) -> TournamentDetail:
        """Course/par/yardage/rounds-scheduled for one tournament."""

    @abstractmethod
    def fetch_leaderboard(self, item: TournamentListItem) -> List[LeaderboardRow]:
        """Full final leaderboard (with per-round strokes) for one tournament."""
