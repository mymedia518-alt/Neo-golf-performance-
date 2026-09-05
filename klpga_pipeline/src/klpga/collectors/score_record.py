"""Official tournament record page collector -- real, confirmed
`/web/tourRecord/scoreRecord` adapter (fetch only, no parsing yet).

This is meant to become the canonical FINAL source for R1 (and later
R2/R3/FINAL) results: unlike the live roundLeaderboard-based active
cycle (klpga.neo_win.r1_active_cycle), which only ever sees KLPGA's
own "999 rank sentinel -> status=INCOMPLETE" and can never distinguish
a withdrawal from any other did-not-complete reason, this page's own
title ("대회기록" -- tournament record) suggests it may carry KLPGA's
own official WD/DQ/DNS determination directly. That has NOT been
confirmed against a real response yet.

CONFIRMED (URL only): the literal nav link
    <a class="nav-link " href="/web/tourRecord/scoreRecord?gameCode=2026080001">대회기록</a>
appears in tests/fixtures/entry_list_sample.html -- the same real,
user-pasted HTML entry_list_parser.py is built and tested against. See
klpga.config.SCORE_RECORD_ENDPOINT for the full provenance note.

NOT yet confirmed: the page's own DOM structure -- in particular
whether/how it represents a withdrawn or disqualified player, whether
"final score" appears as a single field or must be derived, and
whether the page is a single static response or (like GROUP_PAGE_
ENDPOINT) has tab/round parameters not yet discovered. This project
never guesses DOM structure, so this module intentionally does
nothing but fetch and return the raw page text -- no query parameter
beyond `gameCode` is added, and no parsing function exists here yet. A
real parser (klpga.parsers.score_record_parser, matching the
klpga.parsers.entry_list_parser precedent) can only be written once a
real HTML sample of this page has been captured and reviewed, e.g.
saved as tests/fixtures/score_record_sample.html -- see
scripts/97_fetch_score_record_sample.py.
"""
from __future__ import annotations

import re
from bs4 import BeautifulSoup

from klpga import config
from klpga.http_client import PoliteHttpClient


def fetch_score_record_html(client: PoliteHttpClient, game_code: str) -> tuple[int, str]:
    """Real, always-live GET against the confirmed scoreRecord endpoint
    -- never served from the disk cache, so every call proves a real
    network round-trip happened. Returns `(status_code, raw_html_text)`
    unparsed -- see module docstring for why nothing is extracted from
    it. Raises (never swallows) on a real fetch failure -- a non-2xx
    response, timeout, or connection error -- so a caller that needs to
    fail loudly on a broken fetch gets a real exception to catch,
    rather than a silently empty/cached result."""
    return client.get_text_with_status(config.SCORE_RECORD_ENDPOINT, params={"gameCode": game_code})


def parse_score_record_html(html: str) -> list[dict]:
    """NOT YET IMPLEMENTED, deliberately.

    This project never writes a parser against DOM structure it has
    not actually seen -- that would be exactly the kind of fabrication
    the WD/DQ/INCOMPLETE rendering rules elsewhere in this codebase
    exist to prevent, just applied to code correctness instead of a
    displayed value. No real fixture of this page's markup exists yet
    (see the module docstring). Run scripts/97_fetch_score_record_sample.py
    with real network access to klpga.co.kr to capture one, save it as
    tests/fixtures/score_record_sample.html, and this function can then
    be written and tested against real markup -- matching every other
    parser in this project (entry_list_parser.py, leaderboard_parser.py).

    The intended return contract, once implemented, is a list of dicts
    shaped like: {"player_id": str, "official_status": str | None
    ("WD"/"DQ"/"DNS"/None-meaning-ACTIVE -- whatever the real page
    actually uses, never guessed in advance), "final_score": <value> |
    None, "rank_display": str | None}. klpga.neo_win.
    r1_final_reconciliation.reconcile_r1_final() is already written and
    tested against exactly this contract, so completing this function
    is the ONLY remaining step to wire up the real FINAL source."""
    raise NotImplementedError(
        "scoreRecord HTML structure has not been captured from a real page yet -- "
        "run scripts/97_fetch_score_record_sample.py with real network access to "
        "klpga.co.kr, save the result as tests/fixtures/score_record_sample.html, "
        "then implement this function against the real markup. See this module's "
        "docstring for the intended return contract."
    )


# Observed production DOM implementation. Defined after the historical
# placeholder above so older source context remains auditable while this
# canonical function is now the active definition.
def parse_score_record_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for table in soup.select("table"):
        header_texts = {" ".join(x.get_text(" ", strip=True).split()) for x in table.select("thead .today")}
        if "1R" not in header_texts:
            continue
        for tr in table.select("tbody tr"):
            rank_cell = tr.select_one("td.rank")
            name_cell = tr.select_one("td.name")
            total_cell = tr.select_one("td.total")
            if not (rank_cell and name_cell and total_cell):
                continue
            name = " ".join(name_cell.get_text(" ", strip=True).split())
            rank_display = " ".join(rank_cell.get_text(" ", strip=True).split()) or None
            total_text = " ".join(total_cell.get_text(" ", strip=True).split())
            status = rank_display.upper() if rank_display and rank_display.upper() in {"WD", "DQ", "DNS", "CUT"} else None
            final_score = None
            if status is None and re.fullmatch(r"[+-]?\d+|E", total_text or ""):
                final_score = 0 if total_text == "E" else int(total_text)
            candidates.append({"player_name": name, "official_status": status, "final_score": final_score, "rank_display": rank_display})
    if not candidates:
        raise ValueError("scoreRecord R1 table not found in official HTML")
    by_name = {}
    for row in candidates:
        prior = by_name.get(row["player_name"])
        if prior is not None and prior != row:
            raise ValueError(f"conflicting scoreRecord rows for player_name={row['player_name']!r}")
        by_name[row["player_name"]] = row
    return list(by_name.values())
