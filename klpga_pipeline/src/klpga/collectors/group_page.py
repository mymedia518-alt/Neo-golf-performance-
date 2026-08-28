"""Round grouping / tee-time page collector — real, confirmed
`/web/tourInfo/group` adapter (fetch only, no parsing yet).

CONFIRMED via manual browser Network capture, 2026-08-28
(gameCode=2026080001):
    GET https://klpga.co.kr/web/tourInfo/group?gameCode=<code>
    response: HTTP 200, text/html; charset=UTF-8

NOT yet confirmed: how the page's 1R/2R/3R tabs are represented in the
raw HTML/DOM (a `round` query parameter, a client-side JS toggle with
all rounds already embedded in one response, or something else). This
project never guesses DOM relationships, so this module intentionally
does nothing but fetch and return the raw page text — no query
parameter beyond `gameCode` is added. A real parser
(`klpga.parsers.group_page_parser`, matching the
`klpga.parsers.entry_list_parser` precedent) can only be written once a
real HTML sample of this page has been captured and reviewed, e.g.
saved as `tests/fixtures/group_page_sample.html`.
"""
from __future__ import annotations

from klpga import config
from klpga.http_client import PoliteHttpClient


def fetch_group_page_html(client: PoliteHttpClient, game_code: str) -> str:
    """Real GET against the confirmed group-page endpoint. Returns the
    raw HTML text unparsed — see module docstring for why."""
    return client.get_text(config.GROUP_PAGE_ENDPOINT, params={"gameCode": game_code})
