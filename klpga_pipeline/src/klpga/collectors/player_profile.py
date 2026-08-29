"""Player profile page collector — reported (not yet independently
confirmed) `/web/profile/mainRecord` adapter (fetch only, no parsing
yet).

REPORTED via chat, not confirmed by a live fetch in this project (this
sandbox has no network access to klpga.co.kr):
    GET https://klpga.co.kr/web/profile/mainRecord?playerCode=<code>

NOT yet confirmed: the page's real DOM structure — in particular how
"소속" (team/sponsor) and the other profile fields (등급, 출생년도,
회원번호, 입회년도) are represented (a table, a definition list, or
something else). This project never guesses DOM relationships, so this
module intentionally does nothing but fetch and return the raw page
text — no field is extracted here. A real parser
(`klpga.parsers.player_profile_parser`, matching the
`klpga.parsers.entry_list_parser` precedent) can only be written once a
real HTML sample of this page has been captured and reviewed, e.g.
saved as `tests/fixtures/player_profile_sample.html` — see
scripts/53_fetch_player_profile_sample.py.
"""
from __future__ import annotations

from klpga import config
from klpga.http_client import PoliteHttpClient


def fetch_player_profile_html(client: PoliteHttpClient, player_code: str) -> tuple[int, str]:
    """Real, always-live GET against the reported player-profile
    endpoint — never served from the disk cache, so every call proves
    a real network round-trip happened. Returns
    `(status_code, raw_html_text)` unparsed — see module docstring for
    why nothing is extracted from it. Raises (never swallows) on a
    real fetch failure — a non-2xx response, timeout, or connection
    error — so a caller that needs to fail loudly on a broken fetch
    gets a real exception to catch, rather than a silently
    empty/cached result."""
    return client.get_text_with_status(
        config.PLAYER_PROFILE_ENDPOINT, params={"playerCode": player_code}
    )
