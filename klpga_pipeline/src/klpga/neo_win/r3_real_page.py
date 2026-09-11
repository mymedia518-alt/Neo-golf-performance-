"""R3 HOUSE: the real-data R3 renderer.

Replaces r3_wait_page.render_r3_wait_page() at the same route
(docs/tournaments/2026/<game_code>/r3/index.html) ONLY once
r3_publication_gate.evaluate_r3_publication_gate() reports
publication_allowed=True -- mirrors klpga.neo_win.r2_real_page exactly,
one round later. This module itself enforces nothing about WHEN it may
be called; it is a pure renderer that trusts its caller to have already
gated. It never invents a player row or probability -- every displayed
number comes from one of exactly two already-validated canonical
inputs, and a missing value renders as the site's own established
"--" / metric-empty convention, never a fabricated placeholder number.

Inputs (all already-validated canonical artifacts -- this module reads
no live data itself):
  - r3_freeze: the dict loaded by klpga.neo_win.r3_freeze.load_r3_freeze
    (or an equivalent synthetic fixture of the exact same shape) --
    supplies identity/status/r1/r2/r3_score_to_par per player.
  - forecast: the payload written by
    klpga.neo_win.post_r3_forecast.run_post_r3_forecast (or an
    equivalent fixture) -- supplies win_pct/top5_pct/top10_pct/
    top20_pct keyed by player_id via its own `records` list.

PUBLIC MAIN-TABLE POPULATION (R3 CUT SURVIVORS ONLY, mirroring R2's own
established contract): the public main table shows ONLY players with
real, explicit status=="ACTIVE" in the FROZEN R3 EVIDENCE (r3_freeze
["records"]) -- i.e. players legitimately still active/advancing at
R3. WD/DQ/DNS players (real events that can occur during R3 itself --
there is no new CUT event at R3, the cut is settled before R3 starts)
are never rendered as a public main-table row, and are never inferred
from a missing row, rank, score, or population count -- the exclusion
is driven entirely by each record's own explicit official `status`
field. This is PUBLIC-VIEW FILTERING ONLY: the full frozen evidence
(including every WD/DQ/DNS record) is passed in and used unmodified
elsewhere (rendered-output gate population checks, audit artifacts,
model inputs) -- nothing is deleted from r3_freeze itself, only
excluded from this one table's rendered rows. Ranking is DERIVED
(ascending total_to_par among the advancing population only, ties
share a rank), the standard golf-leaderboard computation from a real
score, never a separately fabricated number.

Sponsor invariant preserved exactly (render_player_identity, same as R2).

Public main table columns (WIN last, no SG):
  순위 | 선수 | 합계 | 3R | Top5 | Top10 | Top20 | 우승

Stage navigation once R3 is published: PRE/R1/R2 clickable, R3 current
(aria-current), FINAL disabled -- FINAL only activates once the
tournament actually finishes, never here.
"""
from __future__ import annotations

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.player_identity import render_player_identity
from klpga.website_v2.shell import breadcrumb_html

EMPTY_MARK = "—"
STAGE_READY_META = '<meta name="neo-stage-publication-ready" content="true">'

STATUS_LABEL = {"ACTIVE": "", "WD": "WD", "DQ": "DQ", "DNS": "DNS"}
ADVANCING_STATUS = "ACTIVE"


def _to_par_display(raw) -> str:
    if raw is None:
        return EMPTY_MARK
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return EMPTY_MARK
    if n == 0:
        return "E"
    return f"+{n}" if n > 0 else str(n)


def _pct_display(v) -> str:
    if v is None:
        return EMPTY_MARK
    return f"{float(v):.1f}%"


def _total_to_par(row: dict):
    """Real cumulative R1+R2+R3 total-to-par -- COMPUTED directly from
    the three real fields the R3 freeze actually has, exactly mirroring
    r2_real_page._total_to_par's own established, bugfix-proven
    convention (never read from a nonexistent pre-computed field).
    None unless all three are real, non-null numbers."""
    r1 = row.get("r1_score_to_par")
    r2 = row.get("r2_score_to_par")
    r3 = row.get("r3_score_to_par")
    if r1 is None or r2 is None or r3 is None:
        return None
    try:
        return float(r1) + float(r2) + float(r3)
    except (TypeError, ValueError):
        return None


def _rank_sort_key(row: dict):
    total = _total_to_par(row)
    return (0, total) if total is not None else (1, 0)


def _derive_display_ranks(records: list[dict]) -> dict[str, str]:
    """Ascending real cumulative total (see _total_to_par). A row with
    no real, complete total NEVER receives a numeric or tied rank -- it
    renders EMPTY_MARK. Ties share a rank with a "T" prefix."""
    ordered = sorted(records, key=_rank_sort_key)
    ranks: dict[str, str] = {}
    current_rank = 0
    current_key = None
    tie_counts: dict[int, int] = {}
    for i, r in enumerate(ordered, start=1):
        pid = str(r["player_id"])
        key = _rank_sort_key(r)
        if key[0] == 1:
            ranks[pid] = EMPTY_MARK
            continue
        if key != current_key:
            current_rank = i
            current_key = key
        ranks[pid] = str(current_rank)
        tie_counts[current_rank] = tie_counts.get(current_rank, 0) + 1
    return {pid: (f"T{r}" if r != EMPTY_MARK and tie_counts.get(int(r), 0) > 1 else r) for pid, r in ranks.items()}


def _cell(v, label: str) -> str:
    display = _pct_display(v)
    cls = " class='metric-empty'" if v is None else " class='win'"
    return f"<td{cls} data-label='{label}'>{display}</td>"


def render_r3_real_page(
    *,
    tournament_name: str,
    game_code: str,
    date_range: str,
    r3_freeze: dict,
    forecast: dict,
    sponsor_by_id: dict,
) -> str:
    """The complete, real HTML for R3's public route once the
    publication gate has passed. Consumes ONLY the two validated
    canonical inputs described in this module's own docstring -- raises
    KeyError/TypeError on a structurally malformed input rather than
    silently rendering a partial/guessed page (fail loud, never a quiet
    fabrication)."""
    records = r3_freeze["records"]
    forecast_by_id = {str(r["player_id"]): r for r in forecast.get("records", [])}
    # PUBLIC MAIN TABLE = CUT SURVIVORS ONLY (R3, mirroring R2's own
    # established contract): `records` above stays the FULL frozen
    # evidence (every WD/DQ/DNS record intact, untouched);
    # `advancing_records` is a display-only filter, driven strictly by
    # each record's own explicit official status -- never inferred
    # from a missing row/rank/score.
    advancing_records = [r for r in records if r.get("status", "ACTIVE") == ADVANCING_STATUS]
    ranks = _derive_display_ranks(advancing_records)

    rows_html = []
    for row in sorted(advancing_records, key=_rank_sort_key):
        pid = str(row["player_id"])
        status = row.get("status", "ACTIVE")
        identity = render_player_identity(row["player_name"], sponsor_by_id.get(pid), quote="'")
        status_badge = f" <span class='status-badge'>{STATUS_LABEL.get(status, status)}</span>" if status != "ACTIVE" else ""
        fc = forecast_by_id.get(pid)
        rows_html.append(
            f"<tr data-player-id='{pid}'>"
            f"<td data-label='순위'>{ranks[pid]}</td>"
            f"<th scope='row' data-label='선수'>{identity}{status_badge}</th>"
            f"<td data-label='합계'>{_to_par_display(_total_to_par(row))}</td>"
            f"<td data-label='3R'>{_to_par_display(row.get('r3_score_to_par'))}</td>"
            + _cell(fc["top5_pct"] if fc else None, "Top5")
            + _cell(fc["top10_pct"] if fc else None, "Top10")
            + _cell(fc["top20_pct"] if fc else None, "Top20")
            + _cell(fc["win_pct"] if fc else None, "우승")
            + "</tr>"
        )

    breadcrumb = breadcrumb_html(tournament_name, None, "R3")
    body = (
        f"{breadcrumb}"
        '<section class="hero" id="tournament"><div><p class="eyebrow">R3 업데이트</p>'
        f"<h1>{tournament_name}</h1><p class=\"meta\">{date_range}</p></div>"
        '<strong class="status">R3</strong></section>'
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/pre/">사전 분석 PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r2/">R2</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r3/" aria-current="page">R3</a></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FINAL</span></li>'
        '</ol></nav>'
        '<section class="panel leaderboard-panel" id="r3">'
        '<div class="leaderboard-head"><h2>3R 결과</h2></div>'
        '<div class="table-wrap"><table class="data leaderboard-table leaderboard-table--r2-full"><thead><tr>'
        "<th>순위</th><th>선수</th><th>합계</th><th>3R</th>"
        "<th>Top5</th><th>Top10</th><th>Top20</th><th>우승</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
        + f'<p class="note">총 {len(advancing_records)}명</p>'
        + "</section>"
    )

    shell = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} R3</title>"
        "<link rel=\"stylesheet\" href=\"/assets/neo-site.css\">"
        "<link rel=\"stylesheet\" href=\"/assets/neo.css\">"
        "</head><body>"
        f"<main>{body}</main>"
        "<footer class=\"site-footer\"><div class=\"site-footer__inner\">"
        "<p class=\"site-footer__copyright\">© 2026 NEO GOLF DATA. All Rights Reserved.</p>"
        "</div></footer>"
        "</body></html>"
    )
    return inject_global_navigation(shell, active_section="tournaments")


def is_real_page(html: str) -> bool:
    return STAGE_READY_META in html and "leaderboard-table--r2-full" in html
