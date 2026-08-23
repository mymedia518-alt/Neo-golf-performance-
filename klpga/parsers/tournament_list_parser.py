"""Parses the KLPGA tournament schedule/list page into structured rows.

Only extracts what is actually present in the page. Missing optional
fields are left as None rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from bs4 import BeautifulSoup

from .. import selectors
from . import ParseError


@dataclass
class TournamentListItem:
    tournament_id: str
    tournament_name: str
    period_text: Optional[str]
    status: Optional[str]
    tournament_type: Optional[str]
    detail_url: Optional[str]


def _extract_id_from_href(href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    # TODO(CONFIRM): real query-param / path shape, e.g. "?tid=12345".
    if "=" in href:
        return href.rsplit("=", 1)[-1].strip() or None
    return href.strip("/").rsplit("/", 1)[-1] or None


def parse_tournament_list(html: str) -> List[TournamentListItem]:
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select(selectors.TOURNAMENT_LIST["row"])
    if not rows:
        raise ParseError(
            "no tournament rows found; page structure may have changed "
            "or the content is JS-rendered"
        )

    items: List[TournamentListItem] = []
    for row in rows:
        name_el = row.select_one(selectors.TOURNAMENT_LIST["name"])
        if name_el is None:
            continue
        name = name_el.get_text(strip=True)
        href = name_el.get(selectors.TOURNAMENT_LIST["id_attr"])
        tid = _extract_id_from_href(href)
        if tid is None or not name:
            continue

        period_el = row.select_one(selectors.TOURNAMENT_LIST["period"])
        status_el = row.select_one(selectors.TOURNAMENT_LIST["status"])
        type_el = row.select_one(selectors.TOURNAMENT_LIST["type"])

        items.append(
            TournamentListItem(
                tournament_id=tid,
                tournament_name=name,
                period_text=period_el.get_text(strip=True) if period_el else None,
                status=status_el.get_text(strip=True) if status_el else None,
                tournament_type=type_el.get_text(strip=True) if type_el else None,
                detail_url=href,
            )
        )
    return items
