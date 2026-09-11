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
            status = None
            row_tokens = set(" ".join(tr.get_text(" ", strip=True).split()).upper().split())
            for marker in ("WD", "DQ", "DNS", "CUT"):
                if marker in row_tokens:
                    status = marker
                    break
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


# ---------------------------------------------------------------------
# R2+ round-tab, cut-boundary-aware parsing (KB 2026090003 R2 evidence-
# gate task, 2026-09-11). CONFIRMED live structure, direct inspection
# of a real, user-supplied captured scoreRecord response (saved-from
# comment: "saved from url=(0066)https://klpga.co.kr/web/tourRecord/
# scoreRecord?gameCode=2026090003"): the SAME confirmed endpoint above
# embeds one <div id="round-<word>"> tab-pane per round that has
# actually been played (e.g. #round-one, #round-two -- round-three/
# round-four absent when not yet played), each with its OWN <table>
# hole-by-hole scorecard, td.rank/td.name (same classes
# parse_score_record_html already reads above) -- deliberately kept as
# a SEPARATE function from parse_score_record_html rather than folded
# into it: that function is R1-specific (its own "1R" header-text scan
# only ever matches round-one's own table) and does not yet know about
# the cut boundary at all; this one is round-tab-scoped by DOM id
# (more precise than a header-text scan) and adds real cut-boundary
# support, confirmed against the real captured page for R2:
#
#   <!-- 예상 CUT -->
#   <tr class="table-cut">
#       <td colspan="31" style="padding: 0;"><div class="bartitle-green">Missed Cut</div></td>
#   </tr>
#
# CONFIRMED in the real captured page: 118 player rows + this one
# divider row; the divider sits immediately after the last T58 row and
# immediately before the first T72 row; the page's own real WD row
# (a real player, rank cell literally reading "WD") is positioned
# AFTER the divider yet keeps its own WD status -- see
# parse_score_record_round_table's own docstring for the exact
# precedence rule this exists to get right.
# ---------------------------------------------------------------------

_CUT_BOUNDARY_CLASS = "table-cut"
_CUT_BOUNDARY_TEXT = "missed cut"
_EXPLICIT_ROUND_STATUS_VALUES = {"WD", "DQ", "DNS", "CUT"}


def _is_cut_boundary_row(tag) -> bool:
    """True only for a real tr.table-cut row whose own text content
    contains "Missed Cut" (case-insensitive) -- both the confirmed
    class AND the confirmed text together, exactly matching the real
    captured official markup, so an unrelated "table-cut"-classed row
    can never false-positive on class alone."""
    classes = tag.get("class") or []
    if _CUT_BOUNDARY_CLASS not in classes:
        return False
    return _CUT_BOUNDARY_TEXT in tag.get_text(" ", strip=True).lower()


def parse_score_record_round_table(html: str, *, round_tab_id: str) -> dict:
    """Parse one round's own tab-pane (round_tab_id="round-two" for R2,
    "round-three" for R3, etc. -- never hardcoded here, the caller
    names the round) from the confirmed scoreRecord page. Raises
    ValueError if that round's own tab-pane or table is missing --
    e.g. the round hasn't been played/published yet -- rather than
    returning an empty, easily-mistaken-for-"no cut yet" result.

    Returns {"rows": [{"player_name": str, "rank_display": str,
    "official_status": str | None}, ...], "cut_boundary_published":
    bool}. Deliberately narrower than parse_score_record_html's own
    return contract (no final_score/player_id) -- this function's one
    job is CUT-gate evidence, not a general score extraction; a
    caller needing scores continues to read them from the already-
    tested primary collection path (klpga.collectors.leaderboard),
    never duplicated here.

    SECTION-DERIVED CUT precedence (requirement D, verified against
    the real captured page's own WD row, which sits AFTER the
    boundary): a row gets official_status="CUT" ONLY when (a) it is
    physically positioned after a real tr.table-cut/"Missed Cut"
    divider row, in the real document's own row order -- never guessed
    from rank/score/arithmetic -- AND (b) its own rank cell did not
    already carry an explicit WD/DQ/DNS/CUT status ("CUT" preserved
    here purely for consistency with parse_score_record_html's own
    "another explicit official signal" token scan above -- not
    observed as literal rank-cell text in the real capture this
    function was built and tested against; WD IS confirmed live). An
    explicit status found on the row itself always wins and is never
    overwritten, regardless of the row's position relative to the
    boundary -- never infers CUT from a missing player either: a
    player absent from this table contributes no row at all, in
    either direction."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(f"#{round_tab_id}")
    if container is None:
        raise ValueError(f"scoreRecord round tab-pane #{round_tab_id} not found -- round not published yet")
    table = container.find("table")
    if table is None:
        raise ValueError(f"scoreRecord table missing inside #{round_tab_id}")
    tbody = table.find("tbody")
    if tbody is None:
        raise ValueError(f"scoreRecord tbody missing inside #{round_tab_id}")

    rows: list[dict] = []
    cut_boundary_published = False
    past_boundary = False

    for tr in tbody.find_all("tr", recursive=False):
        if _is_cut_boundary_row(tr):
            cut_boundary_published = True
            past_boundary = True
            continue

        rank_cell = tr.select_one("td.rank")
        name_cell = tr.select_one("td.name")
        if rank_cell is None or name_cell is None:
            continue
        rank_display = " ".join(rank_cell.get_text(" ", strip=True).split())
        player_name = " ".join(name_cell.get_text(" ", strip=True).split())

        explicit_status = rank_display.upper() if rank_display.upper() in _EXPLICIT_ROUND_STATUS_VALUES else None
        status = explicit_status
        if status is None and past_boundary:
            status = "CUT"  # SECTION-DERIVED, only when nothing explicit already claimed this row

        rows.append({"player_name": player_name, "rank_display": rank_display, "official_status": status})

    return {"rows": rows, "cut_boundary_published": cut_boundary_published}
