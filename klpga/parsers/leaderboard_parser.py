"""Parses a KLPGA tournament leaderboard/scorecard page.

Round scores are collected in the order the source page presents them; a
player who has only played 2 rounds (e.g. missed the cut) simply yields a
round_strokes list of length 2, never padded or backfilled.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from bs4 import BeautifulSoup

from .. import selectors
from . import ParseError

_INT_RE = re.compile(r"-?\d+")


def _first_int(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = _INT_RE.search(text.replace(",", "").replace("+", ""))
    return int(m.group()) if m else None


@dataclass
class LeaderboardRow:
    raw_rank: Optional[str]
    player_name: str
    player_id: Optional[str]
    final_score_text: Optional[str]
    total_strokes: Optional[int]
    round_strokes: List[Optional[int]] = field(default_factory=list)


def _extract_player_id(href: Optional[str]) -> Optional[str]:
    if not href:
        return None
    # TODO(CONFIRM): real query-param / path shape, e.g. "?pid=9001".
    if "=" in href:
        return href.rsplit("=", 1)[-1].strip() or None
    return href.strip("/").rsplit("/", 1)[-1] or None


def parse_leaderboard(html: str) -> List[LeaderboardRow]:
    soup = BeautifulSoup(html, "lxml")
    sel = selectors.LEADERBOARD
    rows = soup.select(sel["row"])
    if not rows:
        raise ParseError(
            "no leaderboard rows found; page structure may have changed "
            "or the content is JS-rendered"
        )

    results: List[LeaderboardRow] = []
    for row in rows:
        name_el = row.select_one(sel["player_name"])
        if name_el is None:
            continue
        name = name_el.get_text(strip=True)
        if not name:
            continue
        href = name_el.get(sel["player_id_attr"])
        rank_el = row.select_one(sel["rank"])
        total_score_el = row.select_one(sel["total_score"])
        total_strokes_el = row.select_one(sel["total_strokes"])
        round_cells = row.select(sel["round_cell"])

        results.append(
            LeaderboardRow(
                raw_rank=rank_el.get_text(strip=True) if rank_el else None,
                player_name=name,
                player_id=_extract_player_id(href),
                final_score_text=total_score_el.get_text(strip=True) if total_score_el else None,
                total_strokes=_first_int(
                    total_strokes_el.get_text(strip=True) if total_strokes_el else None
                ),
                round_strokes=[_first_int(c.get_text(strip=True)) for c in round_cells],
            )
        )
    return results
