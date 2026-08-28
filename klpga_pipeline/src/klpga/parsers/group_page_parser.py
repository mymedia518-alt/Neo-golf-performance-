"""Parser for the KLPGA Round grouping / tee-time page.

Confirmed via a real Windows browser fetch of the confirmed endpoint
(klpga.config.GROUP_PAGE_ENDPOINT), then cross-checked against the
full raw HTML the user provided (game_code=2026080001, HTTP 200,
1,357,468 bytes, captured 2026-08-28 — see
docs/SITE_STRUCTURE_TODO.md section 13 and
tests/fixtures/group_page_sample.html, a trimmed but byte-faithful
slice of that real capture):

    GET https://klpga.co.kr/web/tourInfo/group?gameCode=<code>
    response: text/html; charset=UTF-8 — a full rendered page, NOT
    JSON and NOT an AJAX fragment.

CONFIRMED structure (resolves the "how are the 1R/2R/3R tabs
represented" open question from klpga.collectors.group_page's
docstring): ALL rounds' groupings — 공식연습일 (official practice
day), 1R, 2R, 3R, and (once published) FR — are already embedded in
ONE HTML response as sibling Bootstrap tab panes
(`<div class="tab-pane" id="round-one">`, `id="round-two"`,
`id="round-three"`, `id="round-four"`), switched client-side via
`data-bs-toggle="pill"`. No `round` query parameter exists or is
needed — the real capture used only `gameCode`. A round whose
grouping has not been published yet has NO corresponding tab-pane div
at all: in the 2026080001 capture, round-four's tab BUTTON exists
(`id="round-four-tab"`) but `id="round-four"` does not — Round 4 had
not been grouped yet.

Each published round's tab-pane contains exactly TWO
`table.table-teetimes` elements:

  1. A `div.section-favorit[style="display:none"]` wrapping a
     "즐겨찾기 선수" (favorite players) table that, confirmed from the
     real capture, lists every entrant again with `style="display:none"`
     on each individual row — the SAME client-side favorite-toggle
     pattern already confirmed and excluded on the entry-list page
     (see klpga.parsers.entry_list_parser's module docstring: "a
     client-side favorite-toggle list, NOT a distinct roster, and must
     be excluded entirely"). This table is NEVER the real grouping and
     is always excluded here.
  2. The real grouping table. Its `<h2>조 편성표</h2>` heading is
     HTML-commented out in the live markup (`<!-- <h2 ...>...</h2> -->`)
     so it cannot be used as a text anchor — this parser instead
     locates it structurally: the `table.table-teetimes` that is NOT
     nested inside a `div.section-favorit`.

Real grouping table row shape (confirmed, `<tbody> <tr>`):
  - `td.fixed-start` — the starting tee (e.g. "1", "10").
  - the next `<td>` — the tee time, e.g. "09:10 " or "09:10 *". The
    trailing "*" seen on some entries is preserved verbatim; its
    meaning is NOT confirmed anywhere on the page and is never
    interpreted here.
  - a variable number of `td.text-start` cells (3 on the 2026080001
    capture's round-three table, 4 on its round-one/round-two/
    official-practice-day tables — the count is NOT assumed fixed),
    each holding one player sharing that tee time:
    `a[href*="playerCode="]` for identity, `span.name` for the
    display name.
  - a trailing "위치보기" (show location) button cell, ignored.

NOT confirmed anywhere on this page: an explicit "조" (group) number
or label. Players who share a table row share a real starting tee and
tee time — that IS their real grouping — but no separate numeric group
identifier exists in the markup, so `GroupingRow.group` is
intentionally always `None` rather than inventing one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, Tag

_PLAYER_CODE_RE = re.compile(r"playerCode=(\d+)")

_ROUND_DIV_IDS = {
    1: "round-one",
    2: "round-two",
    3: "round-three",
    4: "round-four",
}


@dataclass(frozen=True)
class GroupingRow:
    player_code: str
    player_name: str
    starting_tee: Optional[str]
    tee_time: Optional[str]
    group: Optional[str] = None  # never fabricated — see module docstring


def _is_real_grouping_table(table: Tag) -> bool:
    """Excludes the confirmed favorites/toggle-list table — see module
    docstring. Mirrors klpga.parsers.entry_list_parser's exclusion of
    the same real pattern on the entry-list page."""
    return table.find_parent("div", class_="section-favorit") is None


def parse_round_grouping(html: str, round_number: int) -> list[GroupingRow]:
    """Parses the real grouping table for one round (1-4) out of the
    group page's raw HTML. Raises ValueError — never returns a
    fabricated empty result — if that round's tab-pane, or its real
    (non-favorites) grouping table, is not present in this page."""
    if round_number not in _ROUND_DIV_IDS:
        raise ValueError(f"round_number must be 1-4, got {round_number!r}")
    div_id = _ROUND_DIV_IDS[round_number]

    soup = BeautifulSoup(html, "lxml")
    round_div = soup.find("div", id=div_id)
    if round_div is None:
        raise ValueError(
            f"No tab-pane with id={div_id!r} found in this group page — Round {round_number}'s "
            "grouping has not been published on the real site yet (confirmed absent, not guessed)."
        )

    candidate_tables = [
        t for t in round_div.find_all("table", class_="table-teetimes") if _is_real_grouping_table(t)
    ]
    if len(candidate_tables) != 1:
        raise ValueError(
            f"Expected exactly 1 real (non-favorites) grouping table inside id={div_id!r}, found "
            f"{len(candidate_tables)} — the page's structure has changed from what was confirmed; "
            "refusing to guess which table is real."
        )
    table = candidate_tables[0]

    rows: list[GroupingRow] = []
    tbody = table.find("tbody")
    if tbody is None:
        return rows
    for tr in tbody.find_all("tr", recursive=False):
        tee_cell = tr.find("td", class_="fixed-start")
        if tee_cell is None:
            continue  # not a real player row (defensive — never observed on the real capture)
        starting_tee = tee_cell.get_text(strip=True) or None

        cells = tr.find_all("td", recursive=False)
        time_cell = cells[1] if len(cells) > 1 else None
        tee_time = (time_cell.get_text(strip=True) or None) if time_cell is not None else None

        for name_cell in tr.find_all("td", class_="text-start"):
            link = name_cell.find("a", href=_PLAYER_CODE_RE)
            if link is None:
                continue  # an empty slot in an under-filled group — never fabricated
            match = _PLAYER_CODE_RE.search(link["href"])
            if match is None:
                continue
            player_code = match.group(1)
            name_span = name_cell.find("span", class_="name")
            player_name = name_span.get_text(strip=True) if name_span is not None else ""
            rows.append(
                GroupingRow(
                    player_code=player_code,
                    player_name=player_name,
                    starting_tee=starting_tee,
                    tee_time=tee_time,
                    group=None,
                )
            )
    return rows
