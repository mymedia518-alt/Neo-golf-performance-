"""KB금융 골든라이프 챔피언십 FR BUILD: the real-data public FR page.

FR is the actual fourth competitive round's own RESULT page -- never
publicly labeled "R4", never confused with FINAL (the distinct post-
tournament validation/result-vs-forecast stage that follows it). FR's
one job: "공식 최종 리더보드를 NEO 디자인으로 보여주는 실제 4라운드
결과 페이지." It carries ZERO model analysis -- no win/Top5/Top10/
Top20 probability, no NEO ranking, no forecast-vs-actual comparison,
no Brier/log-loss/Monte-Carlo language, no "왜 우승했는가" narrative.
Those all belong to FINAL, a separate page this module never touches
or reads.

Mirrors klpga.neo_win.final_real_page's own conventions exactly -- same
design system (docs/assets/neo.css / neo-site.css, no new CSS classes
beyond one new additive leaderboard-table modifier), same sponsor-
invariant helper (render_player_identity), same shell/breadcrumb/
global-nav machinery. A pure renderer: it invents nothing and computes
nothing itself -- every number comes from the same V3 operator-supplied
-official-screenshot evidence FINAL already uses (r1_strokes/r2_strokes
/r3_strokes/r4_strokes/final_total_strokes/final_to_par per confirmed
record); the caller (scripts/132_build_kb_fr_page.py) is responsible
for the completeness/arithmetic hard-stop before ever calling this.

SCOPE: identical to FINAL's own Top-39 scope -- this is NOT the
complete 70-player field. The public copy says "FR 상위 N명 공식
결과 기준" using the evidence's own positions_confirmed_gapless_through,
never a hardcoded 39.

Never exposes internal state in the public HTML: no SHA/hash, no
evidence-tier name, no file path, no "review_required"/QA-state word,
no build/commit id -- same enforced contract as final_real_page.py.
"""
from __future__ import annotations

from klpga.website_v2.global_navigation import inject_global_navigation
from klpga.website_v2.player_identity import render_player_identity
from klpga.website_v2.shell import breadcrumb_html

EMPTY_MARK = "—"
STAGE_READY_META = '<meta name="neo-stage-publication-ready" content="true">'


def _to_par_display(v) -> str:
    if v is None:
        return EMPTY_MARK
    n = int(v)
    if n == 0:
        return "E"
    return f"+{n}" if n > 0 else str(n)


def _strokes_display(v) -> str:
    if v is None:
        return EMPTY_MARK
    return str(int(v))


def render_fr_real_page(
    *,
    tournament_name: str,
    game_code: str,
    date_range: str,
    evidence: dict,
) -> str:
    scope_through = evidence["positions_confirmed_gapless_through"]
    scope_label = f"FR 상위 {scope_through}명 공식 결과 기준"
    records = sorted(evidence["confirmed_records"], key=lambda r: r["position_from"])

    winner_record = next(r for r in records if str(r["final_rank"]) == "1")
    winner_identity = render_player_identity(winner_record["player_name"], winner_record.get("sponsor"), quote="'")
    winner_to_par = _to_par_display(winner_record.get("final_to_par"))
    winner_fr_score = _strokes_display(winner_record.get("r4_strokes"))

    rows_html = []
    for row in records:
        identity = render_player_identity(row["player_name"], row.get("sponsor"), quote="'")
        rows_html.append(
            f"<tr data-player-id='{row['player_id']}'>"
            f"<td data-label='순위'>{row['final_rank']}</td>"
            f"<th scope='row' data-label='선수'>{identity}</th>"
            f"<td data-label='R1'>{_strokes_display(row.get('r1_strokes'))}</td>"
            f"<td data-label='R2'>{_strokes_display(row.get('r2_strokes'))}</td>"
            f"<td data-label='R3'>{_strokes_display(row.get('r3_strokes'))}</td>"
            f"<td data-label='FR'>{_strokes_display(row.get('r4_strokes'))}</td>"
            f"<td data-label='합계'>{_to_par_display(row.get('final_to_par'))}</td>"
            "</tr>"
        )

    breadcrumb = breadcrumb_html(tournament_name, None, "FR")
    body = (
        f"{breadcrumb}"
        '<section class="hero" id="tournament"><div><p class="eyebrow">FR · 종료</p>'
        f"<h1>{tournament_name}</h1><p class=\"meta\">{date_range}</p>"
        '<p class="meta">'
        f"우승 {winner_identity} "
        f"<span class='metric'>{winner_to_par}</span> "
        f"<span class='win'>우승</span> · FR {winner_fr_score}"
        "</p></div>"
        '<strong class="status">FR</strong></section>'
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/pre/">사전 분석 PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r2/">R2</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/r3/">R3</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{game_code}/fr/" aria-current="page">FR</a></li>'
        '</ol></nav>'
        '<section class="panel leaderboard-panel" id="fr-leaderboard">'
        f'<div class="leaderboard-head"><h2>FR 최종 리더보드</h2><p class="note">{scope_label}</p></div>'
        '<div class="table-wrap"><table class="data leaderboard-table leaderboard-table--fr-full"><thead><tr>'
        "<th>순위</th><th>선수</th><th>R1</th><th>R2</th><th>R3</th><th>FR</th><th>합계</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
        "</section>"
    )

    shell = (
        "<!doctype html><html lang=\"ko\"><head>"
        f"{STAGE_READY_META}"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>NEO GOLF DATA · {tournament_name} FR</title>"
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


def is_fr_real_page(html: str) -> bool:
    return STAGE_READY_META in html and 'id="fr-leaderboard"' in html
