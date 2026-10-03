"""Player profile page collector — reported (not yet independently
confirmed) `/web/profile/mainRecord` adapter (fetch only, no parsing
yet), plus a real, confirmed, parsed collector for the player's season
detail record.

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

CONFIRMED separately, live, 2026-10-03 (GitHub Actions runner — see
klpga.config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT for the full real
discovery trail): mainRecord's own GIR/드라이브 비거리/페어웨이/평균퍼팅
table cells ship empty from the server (client-JS-filled), but a
SEPARATE confirmed endpoint — POST .../load/profile/
publicRecordSeasonDetail — returns the real values as a plain HTML
fragment, label/value table rows grouped under three real section
headings (스코어/기술/기타종합). `fetch_public_record_season_detail_html`
+ `parse_public_record_season_detail_html` below are the real,
confirmed fetch+parse pair for that endpoint — PLAYER_PROFILE_ENDPOINT
above stays fetch-only/unparsed, unchanged.
"""
from __future__ import annotations

from bs4 import BeautifulSoup

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


def fetch_public_record_season_detail_html(
    client: PoliteHttpClient,
    player_code: str,
    season: str,
    *,
    tour_type: str = "RE",
    game_code: str = "",
    use_cache: bool = True,
) -> str:
    """Real POST against the confirmed publicRecordSeasonDetail
    endpoint (see klpga.config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT for
    the full discovery trail — this is the real source
    PLAYER_PROFILE_ENDPOINT's own mainRecord page itself loads client-
    side via `$("#detail").load(...)`, not a guessed URL). `tour_type`
    defaults to "RE" (정규투어), the publicRecordSeason page's own
    default selection; `game_code` defaults to "" (전체 — every
    tournament that season), matching the page's own default too.
    Returns the raw HTML fragment unparsed-of-caching-concerns; pass to
    `parse_public_record_season_detail_html` for the real label/value
    extraction."""
    return client.post_text(
        config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT,
        data={
            "playerCode": str(player_code),
            "season": str(season),
            "tourType": tour_type,
            "gameCode": game_code,
        },
        use_cache=use_cache,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )


# Real section headings confirmed in the live 2026-10-03 capture (see
# klpga.config.PUBLIC_RECORD_SEASON_DETAIL_ENDPOINT) -- never guessed;
# a fragment missing all three is treated as a real parse failure, not
# silently returned as an empty/partial result.
_EXPECTED_SECTION_HEADINGS = ("스코어", "기술", "기타종합")


def _parse_number(raw: str) -> float | None:
    """A confirmed-real empty cell (no value published for this
    player/season/tour/game combination, e.g. 유현주's 이글 row) stays
    None -- never coerced to 0, which would fabricate a real-looking
    "zero eagles" claim this project has no actual evidence for."""
    text = raw.strip()
    if not text or text == "-":
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def parse_public_record_season_detail_html(html: str) -> dict:
    """Parse the real, confirmed publicRecordSeasonDetail HTML
    fragment into
        {section_heading: {row_label: {"value": v, "detail": {label: v}}}}
    keyed by each ROW's own real Korean primary label (기록명 — the
    row's first cell), never flattened into one label->value dict per
    section: a real captured response has multiple DIFFERENT rows that
    reuse the SAME detail-column label text with a DIFFERENT meaning
    (e.g. both the 페어웨이 안착률 row and the 드라이브 거리 row carry
    their own, unrelated "전체 측정 홀" detail column — 110 vs 15 in
    the real 2026-10-03 capture) — a flat dict would silently let the
    second row's value overwrite the first's, exactly the kind of
    silent data loss this project's conventions exist to prevent.
    Detail-column labels stay nested under their own row, never
    renamed/guessed into an English field name here — that mapping is
    the caller's own, explicit responsibility, so a label this project
    has not yet looked at is never silently dropped. Raises ValueError
    if none of the three confirmed section headings are found at all —
    this project never returns an empty dict and lets a caller mistake
    "the page structure changed" for "this player/season genuinely has
    zero recorded stats"."""
    soup = BeautifulSoup(html, "html.parser")
    sections: dict[str, dict[str, dict]] = {}
    for heading in soup.select("h2.content-title"):
        section_name = heading.get_text(strip=True)
        table = heading.find_parent("div").find_next_sibling("div")
        table = table.find("table") if table else None
        if table is None:
            continue
        rows: dict[str, dict] = {}
        for tr in table.select("tbody tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            primary_label = cells[0].get_text(strip=True)
            if not primary_label or primary_label == "-":
                continue
            row_entry: dict = {
                "value": _parse_number(cells[1].get_text(strip=True)),
                "detail": {},
            }
            # Confirmed real layout: up to two further label/value
            # pairs at cells[3:5] and cells[5:7] (세부기록 columns) — a
            # row with fewer cells (malformed/unexpected) contributes
            # whatever complete pairs it has, never a guessed value.
            for label_idx, value_idx in ((3, 4), (5, 6)):
                if value_idx >= len(cells):
                    continue
                detail_label = cells[label_idx].get_text(strip=True)
                if not detail_label or detail_label == "-":
                    continue
                row_entry["detail"][detail_label] = _parse_number(cells[value_idx].get_text(strip=True))
            rows[primary_label] = row_entry
        sections[section_name] = rows
    if not any(name in sections for name in _EXPECTED_SECTION_HEADINGS):
        raise ValueError(
            f"publicRecordSeasonDetail: none of the expected section headings "
            f"{_EXPECTED_SECTION_HEADINGS} found — real page structure may have "
            f"changed (found headings: {list(sections)})"
        )
    return sections


def fetch_score_detail_html(
    client: PoliteHttpClient,
    player_code: str,
    game_code: str,
    *,
    player_name: str,
    use_cache: bool = True,
) -> str:
    """Real POST against the confirmed scoreDetail endpoint (see
    klpga.config.SCORE_DETAIL_ENDPOINT for the full discovery trail).
    `game_code` must be a real tournament this player actually played
    — this project never guesses one; the caller is expected to source
    it from already-reconciled evidence (e.g. PLAYER_HISTORY.json's own
    `tournament_history[*].game_code`)."""
    return client.post_text(
        config.SCORE_DETAIL_ENDPOINT,
        data={
            "playerCode": str(player_code),
            "gameCode": str(game_code),
            "playerName": player_name,
        },
        use_cache=use_cache,
        headers={"X-Requested-With": "XMLHttpRequest"},
    )


# Real per-hole classification classes confirmed in the live
# 2026-10-03 capture ("par"/"birdies"/"bogeys"/"Dbogeys") plus the two
# not yet observed in that specific capture but read defensively,
# never assumed absent (see klpga.config.SCORE_DETAIL_ENDPOINT).
_SCORE_CLASS_LABELS = {
    "eagles": "Eagle",
    "birdies": "Birdie",
    "par": "Par",
    "bogeys": "Bogey",
    "Dbogeys": "Double Bogey",
    "Tbogeys": "Triple Bogey+",
}


def parse_score_detail_html(html: str) -> dict:
    """Parse the real, confirmed scoreDetail HTML fragment into
        {round_number: {
            "holes": [{"hole": 1, "par": 5, "strokes": 5,
                       "class": "Par", "status_to_par": "E"}, ...],
            "out_strokes": int, "in_strokes": int, "total_strokes": int,
        }}
    keyed by the real `_round` attribute on each round's own <tbody
    id="tbodyShotTrackerScore">. Only rounds with a real PAR/Score/
    Status triple are included — a round tab that exists in the DOM
    but carries no tbody (not yet played) contributes nothing, never a
    guessed/empty round entry. Raises ValueError if no round at all
    could be parsed, so a caller never mistakes "this page's structure
    changed" for "this player has zero recorded holes"."""
    soup = BeautifulSoup(html, "html.parser")
    rounds: dict[int, dict] = {}
    for tbody in soup.select("tbody#tbodyShotTrackerScore"):
        round_attr = tbody.get("_round")
        if round_attr is None or not str(round_attr).isdigit():
            continue
        round_number = int(round_attr)
        trs = tbody.find_all("tr", recursive=False)
        row_by_title = {}
        for tr in trs:
            title_cell = tr.find("td", class_="title")
            if title_cell is None:
                continue
            row_by_title[title_cell.get_text(strip=True)] = tr.find_all("td")
        par_cells, score_cells, status_cells = (
            row_by_title.get("PAR"), row_by_title.get("Score"), row_by_title.get("Status"),
        )
        if par_cells is None or score_cells is None:
            continue
        holes = []
        hole_number = 0
        out_strokes = in_strokes = total_strokes = None
        for idx in range(1, len(par_cells)):
            cell_classes = set(score_cells[idx].get("class") or []) if idx < len(score_cells) else set()
            cell_text = score_cells[idx].get_text(strip=True) if idx < len(score_cells) else ""
            if "out" in (par_cells[idx].get("class") or []):
                out_strokes = _parse_number(cell_text)
                continue
            if "in" in (par_cells[idx].get("class") or []):
                in_strokes = _parse_number(cell_text)
                continue
            if "total" in (par_cells[idx].get("class") or []):
                total_strokes = _parse_number(cell_text)
                continue
            hole_number += 1
            par_value = _parse_number(par_cells[idx].get_text(strip=True))
            strokes_value = _parse_number(cell_text)
            score_class = next((_SCORE_CLASS_LABELS[c] for c in cell_classes if c in _SCORE_CLASS_LABELS), None)
            status_text = (
                status_cells[idx].get_text(strip=True)
                if status_cells is not None and idx < len(status_cells)
                else None
            )
            holes.append({
                "hole": hole_number, "par": par_value, "strokes": strokes_value,
                "class": score_class, "status_to_par": status_text,
            })
        rounds[round_number] = {
            "holes": holes, "out_strokes": out_strokes, "in_strokes": in_strokes,
            "total_strokes": total_strokes,
        }
    if not rounds:
        raise ValueError(
            "scoreDetail: no round with a real PAR/Score tbody found — "
            "real page structure may have changed, or this gameCode has no "
            "published scorecard for this player yet"
        )
    return rounds
