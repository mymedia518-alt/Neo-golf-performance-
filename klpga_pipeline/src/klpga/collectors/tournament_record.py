"""Generic per-tournament technical record collector -- UNCONFIRMED
endpoint, fetch only, no parsing.

RED TEAM mission (2026-09-25) asked NEO to investigate
`/web/tourRecord/mainRecord?gameCode=<gameCode>` for all 96 completed
tournaments of playerCode=10097, looking for average score, driving
distance, fairway accuracy, GIR, average putting, birdies, and prize
money, and explicitly required a GENERIC `gameCode` + `playerCode`
collector rather than a one-off patch for player 10097.

CONFIRMED: nothing. An exhaustive local search (this repo only -- no
live network access in this sandbox, see docs/KLPGA_OFFICIAL_DATA_MAP.md
for 13+ prior rounds confirming the same block) found no trace of this
exact path anywhere in the project. See klpga.config.
TOURNAMENT_RECORD_ENDPOINT_UNCONFIRMED's own comment for why this
appears to conflate two already-confirmed, DIFFERENT real endpoints
(SCORE_RECORD_ENDPOINT is gameCode-scoped but has only ever shown
rank/round-score/WD-DQ-CUT status in what this project has captured of
it; PLAYER_PROFILE_ENDPOINT carries technical-sounding data but is
playerCode-scoped, not gameCode-scoped, and per the user's own report
only ever carried 소속/출생년도/회원번호/입회년도).

Matching the GROUP_PAGE_ENDPOINT / PLAYER_PROFILE_ENDPOINT / SCORE_
RECORD_ENDPOINT precedent exactly: this module fetches the raw page
and returns it unparsed. No parser is written here, because no real
sample of this page's markup has ever been captured and reviewed by
this project. Do not write a parser against guessed DOM structure --
that is exactly the fabrication discipline every other collector in
this package already follows.

Once a real HTML sample is captured (see the workflow below) and saved
to tests/fixtures/tournament_record_sample.html, a real parser
(klpga.parsers.tournament_record_parser) can be written and reviewed
against it, and this collector's contract can be finalized. The
intended row shape, sketched only (never guessed into code) from the
RED TEAM mission's own list of expected fields, is:
{"player_id": str, "average_score": float | None,
 "driving_distance": float | None, "fairway_accuracy_pct": float | None,
 "gir_pct": float | None, "average_putts": float | None,
 "birdies": int | None, "prize_money": int | None,
 "final_rank": str | None} -- every field optional because this
project has never seen the real page and must not assume every field
survives contact with it.
"""
from __future__ import annotations

from klpga import config
from klpga.http_client import PoliteHttpClient


def fetch_tournament_record_html(client: PoliteHttpClient, game_code: str) -> tuple[int, str]:
    """Real, always-live GET against the UNCONFIRMED tourRecord/
    mainRecord endpoint -- never served from a disk cache, so a real
    network round-trip is the only way this ever returns data. Raises
    (never swallows) on a non-2xx response, timeout, or connection
    error. This function's only job is proving whether the endpoint
    exists at all and, if so, capturing one real sample per gameCode --
    it is deliberately NOT looped over all 96 tournaments here; a
    caller (a one-off discovery script, matching scripts/97_fetch_
    score_record_sample.py's precedent) decides how many gameCodes to
    try and where to save what comes back."""
    return client.get_text_with_status(
        config.TOURNAMENT_RECORD_ENDPOINT_UNCONFIRMED,
        params={"gameCode": game_code},
    )


def parse_tournament_record_html(html: str, *, player_code: str) -> dict | None:
    """NOT YET IMPLEMENTED, deliberately -- see module docstring.

    Generic by design once written: takes any (html, player_code) pair
    -- this is the "gameCode + playerCode" generic collector the
    mission required, never a player-10097-specific patch. Returns None
    when the given player_code has no row on the page (never raises for
    a merely-absent player -- that is a real, valid outcome, not an
    error); raises only on a genuinely malformed/unexpected page."""
    raise NotImplementedError(
        "tourRecord/mainRecord HTML structure has never been captured from a real "
        "page in this project -- run a discovery script with real network access to "
        "klpga.co.kr (fetch_tournament_record_html), save the result as "
        "tests/fixtures/tournament_record_sample.html, confirm the endpoint actually "
        "returns per-tournament technical stats (average score / driving distance / "
        "fairway accuracy / GIR / putting / birdies / prize money) rather than a 404 "
        "or a redirect to PLAYER_PROFILE_ENDPOINT, and only then implement this "
        "function against the real markup."
    )
