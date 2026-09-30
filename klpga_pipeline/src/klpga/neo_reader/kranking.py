"""Live K-Ranking fetch -- the one narrow addition to an already-
confirmed source this package makes.

scripts/87_collect_kranking_top120.py already establishes, and cites as
confirmed, the two real K-Ranking pages:

    CANONICAL_URL    = "https://k-rankings.klpga.co.kr/allplayer.jsp"
    ACQUISITION_URL  = "https://k-rankings.klpga.co.kr/index.jsp"

but that script only ever accepted already-captured local HTML files
(--period-html / --full-table-html) -- this repo has never attempted a
live GET against either URL. This module adds exactly that: a plain
GET through the same PoliteHttpClient every other confirmed collector
in this project uses, against the SAME two URLs 87 already cites --
no new endpoint is invented.

Parsing stays out of this module deliberately. 87's own parser
(clean_name / _week_from_html / _player_id and the surrounding table
walk) is the only tested K-Ranking parser in this project; duplicating
it here would create a second, unverified implementation of the same
logic. The sync pipeline instead feeds this module's fetched HTML
straight into 87 via its existing --period-html/--full-table-html
flags (see neo_reader.sync), so 87 remains the single source of truth
for how a K-Ranking page is actually read."""
from __future__ import annotations

from klpga.http_client import PoliteHttpClient

CANONICAL_URL = "https://k-rankings.klpga.co.kr/allplayer.jsp"
ACQUISITION_URL = "https://k-rankings.klpga.co.kr/index.jsp"


def fetch_full_table_html(client: PoliteHttpClient) -> str:
    """GET the full-population K-Ranking table page. No gameCode or
    other parameter is sent -- 87's own docstring and CANONICAL_URL
    confirm this page carries the complete, current ranking with no
    query parameters."""
    return client.get_text(CANONICAL_URL)


def fetch_period_html(client: PoliteHttpClient) -> str:
    """GET the K-Ranking landing/period page -- confirms the literal
    official ranking period and supplies the visible TOP 10, per 87's
    own module docstring ("the period page proves the literal official
    ranking period")."""
    return client.get_text(ACQUISITION_URL)
