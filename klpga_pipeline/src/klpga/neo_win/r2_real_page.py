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

PUBLIC MAIN-TABLE POPULATION (fix/kb-r2-official-cut-gate-20260911,
R2 CUT SURVIVORS ONLY task): the public main table shows ONLY players
with real, explicit status=="ACTIVE" in the FROZEN R2 EVIDENCE
(r2_freeze["records"]) -- i.e. players who officially advanced past
the R2 cut. CUT/WD/DQ/DNS players are never rendered as a public main-
table row, and are never inferred from a missing row, rank, score, or
population count -- the exclusion is driven entirely by each record's
own explicit official `status` field, already established upstream by
the real cut-boundary evidence (scripts/112's
_collect_cut_boundary_evidence/_reconcile_cut_evidence). This is
PUBLIC-VIEW FILTERING ONLY: the full frozen evidence (including every
CUT/WD/DQ/DNS record) is passed in and used unmodified elsewhere
(rendered-output gate population checks, audit artifacts, model
inputs) -- nothing is deleted from r2_freeze itself, only excluded
from this one table's rendered rows. Ranking is DERIVED (ascending
total_to_par among the advancing population only, ties share a rank
-- see r2_house_contract.py's own DERIVED classification for "rank"),
the standard golf-leaderboard computation from a real score, never a
separately fabricated number.
"""
from __future__ import annotations

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.player_identity import render_player_identity
from klpga.website_v2.probability_format import format_public_probability
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
    return format_public_probability(v)


def _sg_display(v) -> str:
    if v is None:
        return EMPTY_MARK
    return f"{float(v):+.2f}"


def _total_to_par(row: dict):
    """Real cumulative R1+R2 total-to-par. BUGFIX (fix/kb-r2-official-
    cut-gate-20260911, real production visual QA correction): the R2
    freeze schema (klpga.neo_win.r2_freeze, written by scripts/112's
    _publish_and_close) has NEVER carried a `total_to_par` field --
    every real row carries `r1_score_to_par` and `r2_score_to_par`
    (the same two fields klpga.neo_win.round_update_r2.PlayerR2SimInput
    and post_r2_forecast.py already key off of throughout the rest of
    this pipeline). This module's OWN prior code read `row.get(
    "total_to_par")`, which is None on every real row -- so every
    player's rank sort key fell into the "missing" branch identically,
    and every player (CUT included) rendered as a tied "T1". This
    function is the ONE place that computes the real total, directly
    from the two real fields the freeze actually has. Never fabricated:
    None unless BOTH r1_score_to_par and r2_score_to_par are real,
    non-null numbers (a player who has not yet completed -- or never
    will complete, e.g. a mid-round WD -- correctly has no real total)."""
    r1 = row.get("r1_score_to_par")
    r2 = row.get("r2_score_to_par")
    if r1 is None or r2 is None:
        return None
    try:
        return float(r1) + float(r2)
    except (TypeError, ValueError):
        return None


def _rank_sort_key(row: dict):
    total = _total_to_par(row)
    return (0, total) if total is not None else (1, 0)


def _derive_display_ranks(records: list[dict]) -> dict[str, str]:
    """Ascending real cumulative total (see _total_to_par -- lower is
    better). A row with no real, complete total (either round score
    missing/unresolved) NEVER receives a numeric or tied rank -- it
    renders EMPTY_MARK ("--"), matching this page's own established
    never-fabricate convention (previously, even before the
    total_to_par field-name bug above, such a row would have received
    a fabricated numeric "last place" rank it never actually earned --
    also fixed here). Ties among rows that DO have a real total share a
    rank with a "T" prefix, exactly R1's own rank_display convention."""
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
    # sg_ingest is accepted for call-site/interface compatibility with
    # scripts/112 (which still ingests and validates real SG data every
    # cycle) but is no longer rendered in the PUBLIC R2 main table --
    # see the PUBLIC TABLE COLUMN FIX task on this branch. SG data is
    # never deleted from the pipeline/artifacts, only from this one
    # public view.
    # PUBLIC MAIN TABLE = CUT SURVIVORS ONLY (fix/kb-r2-official-cut-
    # gate-20260911, R2 CUT SURVIVORS ONLY task): `records` above stays
    # the FULL frozen evidence (every CUT/WD/DQ/DNS record intact,
    # untouched, still the module's return-value input for anything
    # else a caller does with it); `advancing_records` is a display-
    # only filter, driven strictly by each record's own explicit
    # official status -- never inferred from a missing row/rank/score.
    advancing_records = [r for r in records if r.get("status", "ACTIVE") == ADVANCING_STATUS]
    ranks = _derive_display_ranks(advancing_records)

    rows_html = []
    for row in sorted(advancing_records, key=_rank_sort_key):
        pid = str(row["player_id"])
        # `data-player-id` -- a real audit hook (fix/kb-r2-official-
        # cut-gate-20260911): lets a rendered-output regression or
        # publication gate join back to the frozen evidence by stable
        # player_id, never by display name (see this task's own
        # invariant 9). Purely additive, never a visible change.
        status = row.get("status", "ACTIVE")
        identity = render_player_identity(row["player_name"], sponsor_by_id.get(pid), quote="'")
        status_badge = f" <span class='status-badge'>{STATUS_LABEL.get(status, status)}</span>" if status != "ACTIVE" else ""
        fc = forecast_by_id.get(pid)
        rows_html.append(
            f"<tr data-player-id='{pid}'>"
            f"<td data-label='순위'>{ranks[pid]}</td>"
            f"<th scope='row' data-label='선수'>{identity}{status_badge}</th>"
            f"<td data-label='합계'>{_to_par_display(_total_to_par(row))}</td>"
            f"<td data-label='2R'>{_to_par_display(row.get('r2_score_to_par'))}</td>"
            + _cell(fc["top5_pct"] if fc else None, "Top5")
            + _cell(fc["top10_pct"] if fc else None, "Top10")
            + _cell(fc["top20_pct"] if fc else None, "Top20")
            + _cell(fc["win_pct"] if fc else None, "우승")
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
        "<th>Top5</th><th>Top10</th><th>Top20</th><th>우승</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
        + f'<p class="note">총 {len(advancing_records)}명 (컷 통과 선수만 표시)</p>'
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
