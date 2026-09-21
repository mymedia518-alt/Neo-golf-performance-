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
# Hole-by-hole extraction (NEO CMPRO FULL COLLECTION score cross-check,
# 2026-09-21). CONFIRMED real structure: a captured scoreRecord page's
# per-round tab-pane (id="round-one"/"round-two"/etc., same id scheme
# already used by GROUP_PAGE_ENDPOINT's own round tab-panes) contains
# ONE table whose <thead> repeats hole numbers 1-9 then "OUT" then
# 10-18 then "IN", and whose <tbody><tr> rows carry, in the SAME
# column order, one <td> per hole holding the player's real stroke
# count as its own text (the td's CSS class -- "par"/"birdies"/
# "bogeys"/etc. -- is only a to-par color hint, never itself the
# value). Directly inspected from a real captured page (game_code
# 2026120001, round-one) -- see
# tests/fixtures/score_record_2026120001_round_one_trimmed_real_excerpt.html,
# a byte-faithful trimmed slice of that real capture (kept: <thead> +
# the first 6 real <tbody> rows). NOT confirmed for game 2026090002
# specifically -- this game code was never captured -- so this
# function is generic: round_tab_id/game code are never hardcoded, and
# it raises rather than guesses if a round's tab-pane/table is absent
# or its cell layout differs from what was confirmed here.
# ---------------------------------------------------------------------

def _clean_cell_text(text: str) -> str:
    """Collapses whitespace AND the real captured page's own literal
    two-character "\\n" escape sequences (confirmed present as actual
    text content inside td.rank on the real fixture -- not real
    newline characters, which get_text(strip=True) already handles;
    an artifact of the page's own markup, not a parsing bug here)."""
    return " ".join(text.replace("\\n", " ").split())


def _hole_cell_int_or_none(text: str) -> "int | None":
    text = _clean_cell_text(text)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_score_record_hole_by_hole(html: str, *, round_tab_id: str) -> list[dict]:
    """Parse one round's own tab-pane (round_tab_id="round-one" for R1,
    "round-two" for R2, etc. -- caller-supplied, never hardcoded here)
    from a real captured scoreRecord page, extracting each player's
    real per-hole stroke count. Raises ValueError -- never returns a
    fabricated/empty result -- if that round's tab-pane, its table, or
    a row's expected 9-cell front/back-nine cell counts are missing:
    this function refuses to guess which cells are holes rather than
    silently mis-mapping scores to the wrong hole.

    Returns a list of {"player_name": str, "rank_display": str,
    "official_status": str | None ("WD"/"DQ"/"DNS"/"CUT" or None),
    "holes": {1: int | None, ..., 18: int | None}} -- one entry per
    real player row (a divider/non-player row, e.g. a cut-boundary
    row, has no td.rank/td.name/td.out/td.in and is skipped). A hole
    value of None means the real cell's own text was blank (e.g. a
    round not yet completed for that player) -- never coerced to 0 or
    any other guessed number."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(f"#{round_tab_id}")
    if container is None:
        raise ValueError(
            f"scoreRecord round tab-pane #{round_tab_id} not found in this page -- "
            "that round was not captured/published in it."
        )
    table = container.find("table")
    if table is None:
        raise ValueError(f"scoreRecord table missing inside #{round_tab_id}")
    tbody = table.find("tbody")
    if tbody is None:
        raise ValueError(f"scoreRecord tbody missing inside #{round_tab_id}")

    rows: list[dict] = []
    for tr in tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        rank_cell = tr.select_one("td.rank")
        name_cell = tr.select_one("td.name")
        out_cell = tr.select_one("td.out")
        in_cell = tr.select_one("td.in")
        if not (rank_cell and name_cell and out_cell and in_cell):
            continue  # a divider/non-player row -- never guessed as a player

        rank_display = _clean_cell_text(rank_cell.get_text(" ", strip=True))
        player_name = _clean_cell_text(name_cell.get_text(" ", strip=True))

        out_idx = tds.index(out_cell)
        in_idx = tds.index(in_cell)
        front_nine_cells = tds[out_idx - 9:out_idx]
        back_nine_cells = tds[in_idx - 9:in_idx]
        if len(front_nine_cells) != 9 or len(back_nine_cells) != 9:
            raise ValueError(
                f"expected 9 hole cells before OUT and 9 before IN for player {player_name!r}, "
                f"found {len(front_nine_cells)} and {len(back_nine_cells)} -- this page's real "
                "cell layout differs from what was confirmed; refusing to guess which cells are holes."
            )

        holes: dict[int, "int | None"] = {}
        for h, cell in enumerate(front_nine_cells, start=1):
            holes[h] = _hole_cell_int_or_none(cell.get_text(strip=True))
        for h, cell in enumerate(back_nine_cells, start=10):
            holes[h] = _hole_cell_int_or_none(cell.get_text(strip=True))

        status = rank_display.upper() if rank_display.upper() in {"WD", "DQ", "DNS", "CUT"} else None
        rows.append({
            "player_name": player_name,
            "rank_display": rank_display,
            "official_status": status,
            "holes": holes,
        })
    return rows


# ---------------------------------------------------------------------
# Per-hole PAR extraction (NEO Expected Strokes Phase 1, 2026-09-21).
# CONFIRMED real structure: the same table's <thead> has a SECOND <tr>
# (after the header-label row) whose own first cell is th.today
# reading the round label (e.g. "1R") and whose remaining cells are
# laid out in the IDENTICAL 9-cells/OUT/9-cells/IN column pattern as
# every real player row -- but holding that hole's PAR instead of a
# stroke count (confirmed against the real captured page: front-nine
# par cells 4,4,3,4,5,4,4,3,5 sum to the real th.out text "36",
# matching the course's own overall par=72 when combined with an
# identical real back-nine). Reuses the exact same cell-position logic
# as parse_score_record_hole_by_hole -- see that function's docstring
# for the shared confirmed-vs-guessed provenance notes.
# ---------------------------------------------------------------------

def parse_score_record_hole_par(html: str, *, round_tab_id: str) -> dict[int, int]:
    """Returns {1: par, ..., 18: par} for one round's tab-pane. Raises
    ValueError -- never guesses -- if the tab-pane/table/thead's second
    row is missing, or its cell layout doesn't match what was
    confirmed (9 cells before OUT, 9 before IN)."""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(f"#{round_tab_id}")
    if container is None:
        raise ValueError(
            f"scoreRecord round tab-pane #{round_tab_id} not found in this page -- "
            "that round was not captured/published in it."
        )
    table = container.find("table")
    if table is None:
        raise ValueError(f"scoreRecord table missing inside #{round_tab_id}")
    thead = table.find("thead")
    if thead is None:
        raise ValueError(f"scoreRecord thead missing inside #{round_tab_id}")
    thead_rows = thead.find_all("tr", recursive=False)
    if len(thead_rows) < 2:
        raise ValueError(
            f"expected a second thead row (the per-hole par row) inside #{round_tab_id}, "
            f"found {len(thead_rows)} thead row(s) -- cannot extract par without it."
        )
    par_row = thead_rows[1]
    cells = par_row.find_all(["th", "td"], recursive=False)
    out_cell = par_row.select_one(".out")
    in_cell = par_row.select_one(".in")
    if out_cell is None or in_cell is None:
        raise ValueError(f"par row inside #{round_tab_id} is missing its OUT/IN cells -- refusing to guess layout")
    out_idx = cells.index(out_cell)
    in_idx = cells.index(in_cell)
    front_nine_cells = cells[out_idx - 9:out_idx]
    back_nine_cells = cells[in_idx - 9:in_idx]
    if len(front_nine_cells) != 9 or len(back_nine_cells) != 9:
        raise ValueError(
            f"expected 9 par cells before OUT and 9 before IN inside #{round_tab_id}, found "
            f"{len(front_nine_cells)} and {len(back_nine_cells)} -- refusing to guess which cells are holes."
        )
    par: dict[int, int] = {}
    for h, cell in enumerate(front_nine_cells, start=1):
        val = _hole_cell_int_or_none(cell.get_text(strip=True))
        if val is None:
            raise ValueError(f"par cell for hole {h} inside #{round_tab_id} is not a real integer")
        par[h] = val
    for h, cell in enumerate(back_nine_cells, start=10):
        val = _hole_cell_int_or_none(cell.get_text(strip=True))
        if val is None:
            raise ValueError(f"par cell for hole {h} inside #{round_tab_id} is not a real integer")
        par[h] = val
    return par
