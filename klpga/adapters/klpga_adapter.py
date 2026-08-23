"""Adapter against the live klpga.co.kr / data.klpga.co.kr sites.

Static HTML is tried first (fast, cache-friendly, cheap on the server);
if the static page doesn't contain the expected rows, the page is assumed
to be JS-rendered and Playwright is used as a fallback. If the endpoints
or selectors in klpga/config.py and klpga/selectors.py are wrong (they are
unverified placeholders — see docs/SITE_STRUCTURE_TODO.md), both paths
will fail and raise; that failure should be fixed by correcting those two
files, not by loosening this adapter's error handling.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from .. import config, http_client
from ..parsers import ParseError
from ..parsers.leaderboard_parser import LeaderboardRow, parse_leaderboard
from ..parsers.tournament_detail_parser import TournamentDetail, parse_tournament_detail
from ..parsers.tournament_list_parser import TournamentListItem, parse_tournament_list
from ..playwright_fallback import fetch_rendered_html
from .base import TournamentDataSource

logger = logging.getLogger("klpga.adapter")


class KLPGAWebAdapter(TournamentDataSource):
    def __init__(self, *, use_cache: bool = True):
        self.use_cache = use_cache

    def _get_html(self, url: str, params: Optional[dict], wait_selector: str) -> str:
        try:
            return http_client.get(url, params=params, use_cache=self.use_cache)
        except http_client.FetchError:
            logger.warning("static fetch failed for %s, trying Playwright fallback", url)
            return fetch_rendered_html(url, wait_selector=wait_selector)

    def _get_parsed_with_fallback(self, url: str, params: Optional[dict], wait_selector: str, parse_fn):
        html = self._get_html(url, params, wait_selector)
        try:
            return parse_fn(html)
        except ParseError:
            logger.info("static parse yielded no rows for %s, retrying via Playwright", url)
            rendered = fetch_rendered_html(url, wait_selector=wait_selector)
            return parse_fn(rendered)

    def list_recent_tournaments(self, limit: int) -> List[TournamentListItem]:
        items = self._get_parsed_with_fallback(
            config.ENDPOINTS["tournament_list"],
            {"limit": limit},
            wait_selector="table.tourSchedule",
            parse_fn=parse_tournament_list,
        )
        return items[:limit]

    def fetch_tournament_detail(self, item: TournamentListItem) -> TournamentDetail:
        html = self._get_html(
            config.ENDPOINTS["tournament_detail"],
            {"tid": item.tournament_id},
            wait_selector=".tournament-info",
        )
        return parse_tournament_detail(html)

    def fetch_leaderboard(self, item: TournamentListItem) -> List[LeaderboardRow]:
        return self._get_parsed_with_fallback(
            config.ENDPOINTS["leaderboard"],
            {"tid": item.tournament_id},
            wait_selector="table.leaderboard",
            parse_fn=parse_leaderboard,
        )
