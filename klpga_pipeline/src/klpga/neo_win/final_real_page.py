"""R3 FINAL WEB DRY-RUN / PRE-MORTEM -- the real-data FINAL renderer.

Consumes ONLY klpga.neo_win.r3_result_input.build_final_validation_dataset's
already-validated candidate payload (the dict written to
`<game_code>_FINAL_VALIDATION_CANDIDATE.json`, or an equivalent synthetic
fixture of the exact same shape) plus a sponsor map -- this module reads
no live data itself and computes no rank/score: every number it renders
was already derived upstream (r3_result_input._derive_final_ranks) or is
the frozen R2 forecast's own raw prediction value, carried through
unchanged. This is deliberately the SAME never-fabricate contract
r2_real_page.py already established for R2's public table.

FINAL IS NOT A NEW PREDICTION SCREEN (R3 FINAL WEB DRY-RUN task, section
5): KB 2026090003's final_round_number is 3, so there is nothing left to
forecast. This page shows two clearly separated groups of columns:
  - FINAL 결과 (공식): 순위/선수/합계/R3 -- the real official outcome,
    from `final_rank`/`final_total`/`r3_score` in the candidate.
  - R2 종료 후 예측: TOP20/TOP10/TOP5/우승 -- R2's OWN frozen prediction
    (`r2_top20`/`r2_top10`/`r2_top5`/`r2_win`), carried through verbatim
    and explicitly labeled as a historical, pre-result prediction. This
    module NEVER computes a new probability from the real R3/FINAL
    outcome -- outcome and prediction are never mixed into one number.

CSS: reuses `leaderboard-table--r2-full` verbatim (zero new CSS). FINAL's
column shape is identical to R2's: a 2-row rank/name/total/round-score
identity block (순위, 선수, 합계 big, round-score small subtext) followed
by one full-width row of exactly 4 probability-shaped cells -- so the
already-shipped, already mobile-QA'd `--r2-full` grid rule (docs/assets/
neo.css) applies unchanged. This module's own output is never written
under docs/ (only under klpga_pipeline/candidate/... or a test's own tmp
dir), so reusing the class touches zero live production file.
"""
from __future__ import annotations

import re

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.player_identity import render_player_identity
from klpga.website_v2.probability_format import format_public_probability
from klpga.website_v2.shell import breadcrumb_html

EMPTY_MARK = "—"
STAGE_READY_META = '<meta name="neo-stage-final-candidate" content="true">'
"""Deliberately a DIFFERENT literal than r2_real_page.STAGE_READY_META --
a FINAL candidate page is never mistaken for a real, promoted R2 page,
and (per this task's explicit "no auto deploy" requirement) this marker
alone is NEVER treated as production publication evidence anywhere --
see klpga.neo_win.final_publication_gate, which requires a separate,
explicit, human-produced artifact instead."""

STATUS_LABEL = {"ACTIVE": "", "WD": "WD", "DQ": "DQ"}

HISTORICAL_PREDICTION_LABEL = "R2 종료 후 예측"
"""R3 FINAL WEB DRY-RUN task, section 5: any R2 probability shown on the
FINAL page must carry this exact historical-prediction label -- it is
never presented as a live/current forecast, and is never recomputed from
the real outcome."""


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


def _pct_cell(v, label: str) -> str:
    display = _pct_display(v)
    cls = " class='metric-empty'" if v is None else " class='win'"
    return f"<td{cls} data-label='{label}'>{display}</td>"


def render_final_candidate_page(
    *,
    tournament_name: str,
    game_code: str,
    date_range: str,
    candidate: dict,
    sponsor_by_id: dict,
) -> str:
    """The complete FINAL-candidate HTML for one tournament, built ONLY
    from an already-validated `candidate` dict (the exact shape
    klpga.neo_win.r3_result_input.build_final_validation_dataset's
    caller writes as `records`, plus `schema_version`/`game_code`/
    `final_round_number`/`post_r3_win_forecast_generated`). Raises
    KeyError/TypeError on a structurally malformed input rather than
    silently rendering a partial/guessed page."""
    records = candidate["records"]
    if candidate.get("post_r3_win_forecast_generated"):
        raise ValueError("a FINAL candidate must never carry a POST-R3 win forecast")

    rows_html = []
    for row in records:
        pid = str(row["player_id"])
        status = row.get("final_status", "ACTIVE")
        identity = render_player_identity(row["player_name"], sponsor_by_id.get(pid), quote="'")
        status_badge = f" <span class='status-badge'>{STATUS_LABEL.get(status, status)}</span>" if status != "ACTIVE" else ""
        final_rank = row.get("final_rank") or EMPTY_MARK
        rows_html.append(
            f"<tr data-player-id='{pid}'>"
            f"<td data-label='순위'>{final_rank}</td>"
            f"<th scope='row' data-label='선수'>{identity}{status_badge}</th>"
            f"<td data-label='합계'>{_to_par_display(row.get('final_total'))}</td>"
            f"<td data-label='R3'>{_to_par_display(row.get('r3_score'))}</td>"
            + _pct_cell(row.get("r2_top20"), "Top20")
            + _pct_cell(row.get("r2_top10"), "Top10")
            + _pct_cell(row.get("r2_top5"), "Top5")
            + _pct_cell(row.get("r2_win"), "우승")
            + "</tr>"
        )

    breadcrumb = breadcrumb_html(tournament_name, None, "FINAL")
    body = (
        f"{breadcrumb}"
        '<section class="hero" id="tournament"><div><p class="eyebrow">FINAL 결과</p>'
        f"<h1>{tournament_name}</h1><p class=\"meta\">{date_range}</p></div>"
        '<strong class="status">FINAL</strong></section>'
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/pre/">사전 분석 PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r2/">R2</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/final/" aria-current="page">FINAL</a></li>'
        '</ol></nav>'
        '<section class="panel leaderboard-panel" id="final">'
        '<div class="leaderboard-head"><h2>FINAL 결과</h2></div>'
        '<div class="table-wrap"><table class="data leaderboard-table leaderboard-table--r2-full"><thead>'
        f'<tr><th colspan="4">FINAL 결과 (공식)</th><th colspan="4">{HISTORICAL_PREDICTION_LABEL}</th></tr>'
        "<tr><th>순위</th><th>선수</th><th>합계</th><th>R3</th>"
        "<th>Top20</th><th>Top10</th><th>Top5</th><th>우승</th></tr>"
        "</thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
        + f'<p class="note">총 {len(records)}명 (공식 FINAL 결과)</p>'
        + f'<p class="note">TOP20/TOP10/TOP5/우승 열은 {HISTORICAL_PREDICTION_LABEL}값이며, 결과를 알고 다시 계산한 값이 아닙니다.</p>'
        + "</section>"
    )

    shell = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} FINAL</title>"
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


def is_final_candidate_page(html: str) -> bool:
    return STAGE_READY_META in html and "leaderboard-table--r2-full" in html and 'id="final"' in html


_ROW_RE = re.compile(
    # Non-greedy `.*?` (never `[^<]*`) for every value cell: a real
    # rendered probability can legitimately be the literal string
    # "<0.1%" (klpga.website_v2.probability_format.format_public_
    # probability's own "<0.1%" case) -- a class excluding "<" would
    # fail to match that real, valid content, silently reporting zero
    # parsed rows instead of a real value.
    r"<tr data-player-id='(?P<pid>[^']+)'>"
    r"<td data-label='순위'>(?P<rank>.*?)</td>"
    r"<th scope='row' data-label='선수'>(?P<identity>.*?)</th>"
    r"<td data-label='합계'>(?P<total>.*?)</td>"
    r"<td data-label='R3'>(?P<r3>.*?)</td>"
    r"<td[^>]*data-label='Top20'>(?P<top20>.*?)</td>"
    r"<td[^>]*data-label='Top10'>(?P<top10>.*?)</td>"
    r"<td[^>]*data-label='Top5'>(?P<top5>.*?)</td>"
    r"<td[^>]*data-label='우승'>(?P<win>.*?)</td>"
    r"</tr>",
    re.DOTALL,
)
_SPONSOR_RE = re.compile(r"<span class='player-sponsor'>(?P<sponsor>.*?)</span>")


def parse_final_candidate_page(html: str) -> list[dict]:
    """Reads a rendered FINAL candidate page back into per-player dicts
    -- the ONE mechanism used both by scripts/117's own post-render QA
    and by this task's regression tests to prove the rendered HTML and
    the source candidate JSON agree player-by-player (R3 FINAL WEB
    DRY-RUN task, section 6). Never guesses a field it cannot find --
    a row that fails to match the exact rendered shape is simply absent
    from the result, so a caller comparing lengths catches a real
    rendering defect instead of silently passing."""
    rows = []
    for m in _ROW_RE.finditer(html):
        sponsor_m = _SPONSOR_RE.search(m.group("identity"))
        rows.append({
            "player_id": m.group("pid"),
            "final_rank": m.group("rank"),
            "final_total_display": m.group("total"),
            "r3_score_display": m.group("r3"),
            "r2_top20_display": m.group("top20"),
            "r2_top10_display": m.group("top10"),
            "r2_top5_display": m.group("top5"),
            "r2_win_display": m.group("win"),
            "sponsor": (sponsor_m.group("sponsor") if sponsor_m else ""),
            "has_status_badge": "status-badge" in m.group("identity"),
        })
    return rows
