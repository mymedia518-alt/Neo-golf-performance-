"""R2 HOUSE -- P0-1: the real-data R2 renderer.

Replaces r2_wait_page.render_r2_wait_page() at the same route
(docs/tournaments/2026/<game_code>/r2/index.html) ONLY once
r2_publication_gate.evaluate_r2_publication_gate() reports
publication_allowed=True -- this module itself enforces nothing about
WHEN it may be called (that is the publication gate's and the
operator's job, see scripts/112); it is a pure renderer that trusts
its caller to have already gated. What it refuses on its own: it never
invents a player row, SG value, or probability -- every displayed
number comes from one of exactly three already-validated canonical
inputs, and a missing value renders as the site's own established
"--" / metric-empty convention (neo-site.css's .home-table
td.metric-empty, extended to .leaderboard-table by neo.css's own new
rule -- see the CSS block added alongside .leaderboard-table--r2-full
in scripts/84_build_ok_open_pre_website_candidate.py's CSS string),
never a fabricated placeholder number.

Inputs (all already-validated canonical artifacts -- this module reads
no live data itself):
  - r2_freeze: the dict loaded by klpga.neo_win.r2_freeze.load_r2_freeze
    (or an equivalent synthetic fixture of the exact same shape) --
    supplies identity/status/round_to_par/total_to_par per player.
  - forecast: the payload written by
    klpga.neo_win.post_r2_forecast.run_post_r2_forecast (or an
    equivalent fixture) -- supplies win_pct/top5_pct/top10_pct/
    top20_pct (already on a 0-100 scale, see round_update_r2.py) keyed
    by player_id via its own `records` list.
  - sg_ingest: the dict returned by
    klpga.neo_win.r2_sg_pipeline.ingest_r2_sg -- supplies
    sg_by_player_id (SG_KEYS-keyed) when status == "AVAILABLE"; when
    status == "NOT_AVAILABLE" every SG cell renders the empty mark,
    never a guess.

Row population and order: every ACTIVE-or-otherwise-real row in the
FROZEN R2 EVIDENCE (r2_freeze["records"]) is shown -- never the
forecast's or SG's own player set, which may legitimately be a subset
(a player missing a PRE profile is excluded from simulation;
see post_r2_forecast's own missing_players list) or absent entirely
(SG NOT_AVAILABLE). A non-ACTIVE player (CUT/WD/DQ/DNS) is still shown
with their real status and whatever real round_to_par/total_to_par
they have -- never dropped, matching R1's own "never silently drop a
real entrant" invariant. Ranking is DERIVED (ascending total_to_par,
ties share a rank -- see r2_house_contract.py's own DERIVED
classification for "rank"), the standard golf-leaderboard computation
from a real score, never a separately fabricated number.
"""
from __future__ import annotations

from klpga.neo_win.r2_sg_pipeline import SG_KEYS, STATUS_AVAILABLE
from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.player_identity import render_player_identity
from klpga.website_v2.shell import breadcrumb_html

EMPTY_MARK = "—"
STAGE_READY_META = '<meta name="neo-stage-publication-ready" content="true">'
"""Deliberately the OPPOSITE literal of r2_wait_page.STAGE_NOT_READY_META
(and of scripts/88's STAGE_READINESS_MARKER, which only tests for the
"false" content) -- a real, gate-passed page must NEVER carry the
not-ready marker, or the HOME STATE ROUTER would refuse to ever
promote it to root HOME. This tag is not required by the router (mere
absence of the not-ready marker is sufficient, see scripts/88's
_stage_is_publication_ready docstring) but is emitted anyway as a
positive, machine-checkable assertion for this page's own tests."""

STATUS_LABEL = {"ACTIVE": "", "CUT": "CUT", "WD": "WD", "DQ": "DQ", "DNS": "DNS"}


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


def _sg_display(v) -> str:
    if v is None:
        return EMPTY_MARK
    return f"{float(v):+.2f}"


def _derive_display_ranks(records: list[dict]) -> dict[str, str]:
    """Ascending total_to_par (lower = better), missing/non-numeric
    total_to_par sorts last (never assumed 0/best) -- ties (identical
    total_to_par) share a rank with a "T" prefix, exactly R1's own
    rank_display convention."""
    def sort_key(r):
        raw = r.get("total_to_par")
        try:
            return (0, int(raw))
        except (TypeError, ValueError):
            return (1, 0)

    ordered = sorted(records, key=sort_key)
    ranks: dict[str, str] = {}
    current_rank = 0
    current_key = None
    tie_counts: dict[int, int] = {}
    key_at_rank: dict[int, object] = {}
    for i, r in enumerate(ordered, start=1):
        key = sort_key(r)
        if key != current_key:
            current_rank = i
            current_key = key
        ranks[str(r["player_id"])] = str(current_rank)
        tie_counts[current_rank] = tie_counts.get(current_rank, 0) + 1
    return {pid: (f"T{r}" if tie_counts[int(r)] > 1 else r) for pid, r in ranks.items()}


def _cell(v, label: str) -> str:
    display = _pct_display(v)
    cls = " class='metric-empty'" if v is None else " class='win'"
    return f"<td{cls} data-label='{label}'>{display}</td>"


def _sg_cell(v, label: str) -> str:
    display = _sg_display(v)
    cls = " class='metric-empty'" if v is None else ""
    return f"<td{cls} data-label='{label}'>{display}</td>"


def render_r2_real_page(
    *,
    tournament_name: str,
    game_code: str,
    date_range: str,
    r2_freeze: dict,
    forecast: dict,
    sg_ingest: dict,
    sponsor_by_id: dict,
) -> str:
    """The complete, real HTML for R2's public route once the
    publication gate has passed. Consumes ONLY the three validated
    canonical inputs described in this module's own docstring --
    raises KeyError/TypeError on a structurally malformed input rather
    than silently rendering a partial/guessed page (fail loud, never a
    quiet fabrication)."""
    records = r2_freeze["records"]
    forecast_by_id = {str(r["player_id"]): r for r in forecast.get("records", [])}
    sg_available = sg_ingest.get("status") == STATUS_AVAILABLE
    sg_by_id = sg_ingest.get("sg_by_player_id", {}) if sg_available else {}
    ranks = _derive_display_ranks(records)

    rows_html = []
    for row in sorted(records, key=lambda r: (ranks[str(r["player_id"])].lstrip("T").zfill(4), str(r["player_id"]))):
        pid = str(row["player_id"])
        status = row.get("status", "ACTIVE")
        identity = render_player_identity(row["player_name"], sponsor_by_id.get(pid), quote="'")
        status_badge = f" <span class='status-badge'>{STATUS_LABEL.get(status, status)}</span>" if status != "ACTIVE" else ""
        sg = sg_by_id.get(pid, {})
        fc = forecast_by_id.get(pid)
        rows_html.append(
            "<tr>"
            f"<td data-label='순위'>{ranks[pid]}</td>"
            f"<th scope='row' data-label='선수'>{identity}{status_badge}</th>"
            f"<td data-label='합계'>{_to_par_display(row.get('total_to_par'))}</td>"
            f"<td data-label='2R'>{_to_par_display(row.get('round_to_par'))}</td>"
            + _sg_cell(sg.get("total"), "SG TOTAL")
            + _sg_cell(sg.get("off_the_tee"), "SG OTT")
            + _sg_cell(sg.get("approach"), "SG APP")
            + _sg_cell(sg.get("around_green"), "SG ARG")
            + _sg_cell(sg.get("putting"), "SG PUTT")
            + _cell(fc["win_pct"] if fc else None, "우승")
            + _cell(fc["top5_pct"] if fc else None, "Top5")
            + _cell(fc["top10_pct"] if fc else None, "Top10")
            + _cell(fc["top20_pct"] if fc else None, "Top20")
            + "</tr>"
        )

    breadcrumb = breadcrumb_html(tournament_name, None, "R2")
    body = (
        f"{breadcrumb}"
        '<section class="hero" id="tournament"><div><p class="eyebrow">R2 업데이트</p>'
        f"<h1>{tournament_name}</h1><p class=\"meta\">{date_range}</p></div>"
        '<strong class="status">R2</strong></section>'
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/pre/">사전 분석 PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r2/" aria-current="page">R2</a></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FINAL</span></li>'
        '</ol></nav>'
        '<section class="panel leaderboard-panel" id="r2">'
        '<div class="leaderboard-head"><h2>2R 결과</h2></div>'
        '<div class="table-wrap"><table class="data leaderboard-table leaderboard-table--r2-full"><thead><tr>'
        "<th>순위</th><th>선수</th><th>합계</th><th>2R</th>"
        "<th>SG TOTAL</th><th>SG OTT</th><th>SG APP</th><th>SG ARG</th><th>SG PUTT</th>"
        "<th>우승</th><th>Top5</th><th>Top10</th><th>Top20</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
        + (
            '<p class="note">※ 공식 스트로크 게인드 데이터가 아직 발표되지 않아 SG 항목은 이 페이지에 표시되지 않습니다.</p>'
            if not sg_available else ""
        )
        + "</section>"
    )

    shell = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} R2</title>"
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
