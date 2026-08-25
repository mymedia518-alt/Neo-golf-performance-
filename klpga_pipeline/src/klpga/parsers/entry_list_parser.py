"""Parser for the KLPGA upcoming-tournament entry-list HTML page.

Confirmed via a manual browser capture (user-reported, then cross-checked
against the full raw HTML the user pasted verbatim — see
tests/fixtures/entry_list_sample.html and docs/SITE_STRUCTURE_TODO.md):

  GET https://klpga.co.kr/web/tourInfo/entry?gameCode=<code>
  response: text/html; charset=UTF-8 — a full rendered page, NOT JSON
  and NOT an AJAX fragment.

Confirmed structure of that page (gameCode=2026080001, 제15회 KG
레이디스 오픈, captured 2026-08-25):

  - A summary box (`div.bg-light.boxshadow div.row.text-center`) with
    repeating `div.col > h4 (label) + h1 (value)` pairs, e.g.
    총 참가자=120, 자격자=115, 추천자=5, 초청자=0.

  - TWO tables on the page. `<h2>즐겨찾기 선수</h2>` ("favorites") is
    wrapped in `<div class="section-favorit" style="display:none">` and,
    confirmed from the real capture, actually lists ALL entrants again
    (each individual `<tr>` also carries `style="display:none;"`) — this
    is a client-side favorite-toggle list, NOT a distinct roster, and
    must be excluded entirely. `<h2>전체 선수</h2>` ("all players") is the
    real, confirmed entry list; its row count reconciles exactly with
    the summary box's "총 참가자" figure (verified: 120 == 120).

  - Inside 전체 선수's `<tbody>`, real player rows carry a name link
    `a.col-7[href*='playerCode=']` (a second, duplicate-code anchor
    wraps the avatar image — only `a.col-7` carries the display name
    text). Interleaved in the SAME tbody are section-divider rows with
    no player link, e.g. `<td colspan="3">| 자격자 : 115명</td>` — these
    carry no entrant data and only update the running category context
    for rows that follow (a category with 0 entrants, e.g. 초청자 above,
    has no divider row at all, confirmed from the real capture).

  - The last `<td>` in a real player row is a free-text "참가 자격"
    (qualification/eligibility REASON) column, e.g. "시드순위자", "2025
    정규투어 상금순위 60위 이내", "2024 일반대회 우승자", or empty.

CONFIRMED live cross-check (문정민 → playerCode 10296): her row sits
under the 자격자 category divider, with qualification_reason "2024
일반대회 우승자" — see tests/test_entry_list_parser.py.

NOT confirmed: no withdrawal/DNS/cancellation marker of any kind was
found anywhere on this page (no WD/DNS text, class, or attribute). This
mirrors the earlier, already-documented finding that the roundLeaderboard
endpoint has no confirmed WD/DQ text either (see
klpga.parsers.leaderboard_parser). This parser therefore does NOT expose
an `entry_status` field — only the genuinely confirmed
qualification_category / qualification_reason fields below.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag

_PLAYER_CODE_RE = re.compile(r"playerCode=(\d+)")
_COUNTRY_RE = re.compile(r"country/([A-Za-z]+)\.png")
_CATEGORY_HEADER_RE = re.compile(r"^\|\s*(.+?)\s*:\s*(\d+)\s*명\s*$")

_FAVORITES_HEADING = "즐겨찾기 선수"
_ALL_PLAYERS_HEADING = "전체 선수"


@dataclass
class EntryRow:
    player_code: str
    player_name: str
    nationality: Optional[str]
    # Confirmed from the section-divider rows preceding this entrant in
    # the same tbody, e.g. "자격자" / "추천자" / "초청자". None only if
    # no divider row was ever seen before this entrant (shouldn't happen
    # on a well-formed page, but never guessed).
    qualification_category: Optional[str]
    # Confirmed free-text "참가 자격" column, e.g. "시드순위자". None if
    # the column was present but empty.
    qualification_reason: Optional[str]


@dataclass
class EntryListSummary:
    # Raw label -> value from the summary box, e.g.
    # {"총 참가자": 120, "자격자": 115, "추천자": 5, "초청자": 0}.
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class EntryListParseResult:
    rows: list[EntryRow]
    # Rows found inside the 전체 선수 tbody that had no divider text AND
    # no extractable playerCode — per the project's "never silently
    # discard" requirement, these are surfaced explicitly rather than
    # dropped.
    unparsed_row_count: int
    unparsed_samples: list[str]


def parse_entry_summary(html: str) -> EntryListSummary:
    soup = BeautifulSoup(html, "lxml")
    counts: dict[str, int] = {}
    for col in soup.select("div.bg-light.boxshadow div.row.text-center > div.col"):
        h4 = col.find("h4")
        h1 = col.find("h1")
        if h4 is None or h1 is None:
            continue
        label = h4.get_text(strip=True)
        value_text = h1.get_text(strip=True)
        if value_text.isdigit():
            counts[label] = int(value_text)
    return EntryListSummary(counts=counts)


def _find_all_players_table(soup: BeautifulSoup) -> Tag:
    heading = soup.find("h2", string=lambda s: s is not None and s.strip() == _ALL_PLAYERS_HEADING)
    if heading is None:
        raise ValueError(
            f"Could not find the '{_ALL_PLAYERS_HEADING}' section heading — "
            "entry-list page structure may have changed"
        )
    table = heading.find_next("table")
    if table is None:
        raise ValueError(f"Could not find a table following the '{_ALL_PLAYERS_HEADING}' heading")
    return table


def parse_entry_list_html(html: str) -> EntryListParseResult:
    """Parse the confirmed '전체 선수' table only — the '즐겨찾기 선수'
    table is a hidden, client-side favorites duplicate of the same
    entrants and is never consulted here."""
    soup = BeautifulSoup(html, "lxml")
    table = _find_all_players_table(soup)

    rows: list[EntryRow] = []
    unparsed_samples: list[str] = []
    unparsed_row_count = 0
    current_category: Optional[str] = None

    for tr in table.select("tbody tr"):
        header_td = tr.find("td", attrs={"colspan": True})
        name_link = tr.select_one("a.col-7[href*='playerCode=']")

        if name_link is None:
            if header_td is not None:
                m = _CATEGORY_HEADER_RE.match(header_td.get_text(strip=True))
                if m:
                    current_category = m.group(1)
                    continue
            # Not a recognized divider row and no player link either —
            # explicitly track rather than silently skip.
            text = tr.get_text(" ", strip=True)
            if text:
                unparsed_row_count += 1
                if len(unparsed_samples) < 10:
                    unparsed_samples.append(text)
            continue

        code_match = _PLAYER_CODE_RE.search(name_link.get("href", ""))
        if code_match is None:
            unparsed_row_count += 1
            if len(unparsed_samples) < 10:
                unparsed_samples.append(tr.get_text(" ", strip=True))
            continue

        player_code = code_match.group(1)
        player_name = name_link.get_text(strip=True)

        flag = tr.select_one("span.tb-flag")
        nationality = None
        if flag is not None:
            cm = _COUNTRY_RE.search(flag.get("style", ""))
            if cm:
                nationality = cm.group(1)

        tds = tr.find_all("td", recursive=False)
        qualification_reason = tds[-1].get_text(strip=True) if tds else None
        qualification_reason = qualification_reason or None

        rows.append(
            EntryRow(
                player_code=player_code,
                player_name=player_name,
                nationality=nationality,
                qualification_category=current_category,
                qualification_reason=qualification_reason,
            )
        )

    return EntryListParseResult(
        rows=rows,
        unparsed_row_count=unparsed_row_count,
        unparsed_samples=unparsed_samples,
    )
