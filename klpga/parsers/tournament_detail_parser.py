"""Parses a single KLPGA tournament detail page (course, par, yardage, ...)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from .. import selectors

_INT_RE = re.compile(r"-?\d+")


def _first_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = _INT_RE.search(text.replace(",", ""))
    return int(m.group()) if m else None


@dataclass
class TournamentDetail:
    course_name: Optional[str]
    par: Optional[int]
    yardage: Optional[int]
    rounds_scheduled: Optional[int]


def parse_tournament_detail(html: str) -> TournamentDetail:
    soup = BeautifulSoup(html, "lxml")
    sel = selectors.TOURNAMENT_DETAIL

    def text_of(key: str) -> Optional[str]:
        el = soup.select_one(sel[key])
        return el.get_text(strip=True) if el else None

    return TournamentDetail(
        course_name=text_of("course_name"),
        par=_first_int(text_of("par")),
        yardage=_first_int(text_of("yardage")),
        rounds_scheduled=_first_int(text_of("rounds_scheduled")),
    )
