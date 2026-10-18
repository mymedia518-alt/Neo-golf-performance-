"""Build docs/tournaments/2026/2026100003/fr/index.html -- the official
FINAL result page for 아이스버그골프·서울신문 오픈 (game_code 2026100003),
from ICEBERG_2026100003_FR_OFFICIAL_V1.json (scripts/257).

OPERATOR CORRECTION (2026-10-18, supersedes this script's own earlier
"no NEO forecast columns" instruction): the FR results table shows the
official result AND, in the same row, the already-verified pre-FR NEO
forecast (TOP20/TOP10/TOP5/우승확률) for each real finisher -- values
come straight from ICEBERG_2026100003_POST_R2_FORECAST_V1.json's own
sg_adjusted_* fields (scripts/254, the same R2-gated Monte Carlo output
already shown on the R2 page before FR started), read verbatim and
never recomputed or adjusted to match the real FR outcome.

MAIN TABLE SCOPE: the operator's reference screenshot (another, 4-round
tournament's own FR page) titles its panel "FR 결과 <N>명" where N is
the real number of players who actually played the final round -- for
THIS tournament that is 61 (the already-verified real cutmakers;
scripts/251/257). The 47 CUT/WD players are NOT mixed into that ranked
table; the already-shipped separate-status treatment (a 'Missed cut'
divider, then CUT/WD name badges, scripts/255's own established
convention) is kept exactly as before for them, below the panel, so
"컷·기권 선수는 FR 결과 대상 선수 표에 섞지 않는다" is honored while
reusing rather than reinventing the existing status display.

COLUMN SET: operator specified 순위/선수/합계/R1/R2/R3/FR/TOP20/TOP10/
TOP5/우승확률, copied from that other (4-round) tournament's own FR
page. This tournament is independently verified 3-round (scripts/257:
official round=4 returns 0 rows) -- its FR IS official round 3, so an
R3 column would be a byte-for-byte duplicate of FR for every one of
the 61 real finishers. The duplicate column is dropped; the column set
actually built is 순위/선수/합계/R1/R2/FR/TOP20/TOP10/TOP5/우승확률.

Players outside the forecast's cutmaker set for a reason unrelated to
status (the 4 real finishers scripts/254 could not simulate --
NO_BASE_FEATURE) show '데이터 부족' in the four NEO columns, never a
fabricated number.
"""
from __future__ import annotations

import json
import sys
from html import escape as _esc
from pathlib import Path

_SITE_ORIGIN = "https://neogolfdata.com"

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.model_publication_gate import assert_no_blocked_probability_output  # noqa: E402
from klpga.website_v2.player_link import linked_player_name_cell  # noqa: E402
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402
from klpga.website_v2.previous_tournament_link import previous_tournament_meta_html  # noqa: E402

GAME_CODE = "2026100003"
FR_OFFICIAL_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_FR_OFFICIAL_V1.json"
FORECAST_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_POST_R2_FORECAST_V1.json"
JOIN_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "fr" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}
_NOWRAP = "<span style='white-space:nowrap'>데이터 부족</span>"

TOTAL_COLS = 10  # 순위/선수/합계/R1/R2/FR/TOP20/TOP10/TOP5/우승확률
PUBLICATION_STATUS = "REFERENCE_ESTIMATE"


def _load(name: str) -> dict:
    return json.loads((CONTENT / f"{GAME_CODE}_{name}").read_text(encoding="utf-8"))


def _pct(x) -> str:
    return f"{x * 100:.1f}%" if isinstance(x, float) and x <= 1.0 else f"{x:.1f}%"


def main() -> None:
    join = json.loads(JOIN_PATH.read_text(encoding="utf-8"))
    tourney = _load("TOURNAMENT_INFO.json")
    join_records = {r["player_code"]: r for r in join["records"]}

    fr_official = json.loads(FR_OFFICIAL_PATH.read_text(encoding="utf-8"))
    assert fr_official["game_code"] == GAME_CODE
    assert fr_official["verification_pass"], "FR official data failed its own arithmetic/consistency verification -- refusing to build the page"
    fr_by_id = {r["player_id"]: r for r in fr_official["records"]}
    assert set(fr_by_id) == set(join_records), "FR official player_id set does not match the 108-entrant roster"

    forecast = json.loads(FORECAST_PATH.read_text(encoding="utf-8"))
    assert forecast["game_code"] == GAME_CODE
    forecast_by_id = {r["player_id"]: r for r in forecast["cutmaker_records"]}

    finisher_ids = {pid for pid, r in fr_by_id.items() if r["status"] == "FINISHED"}
    assert len(finisher_ids) == 61, f"expected 61 real FR finishers, found {len(finisher_ids)}"
    assert set(forecast_by_id) <= finisher_ids, "forecast carries a player who did not finish FR -- must never happen (forecast is cutmaker-gated)"

    sponsor_cache = cross_tournament_verified_sponsor_cache()

    def _sort_key(pid):
        r = fr_by_id[pid]
        status = r["status"]
        if status == "FINISHED":
            return (0, r["final_rank_numeric"], pid)
        if status == "CUT":
            r1 = r["r1_score"] if r["r1_score"] is not None else 999
            r2 = r["r2_score"] if r["r2_score"] is not None else 999
            return (1, r1 + r2, pid)
        if status == "WD_R2":
            return (2, 0, pid)
        return (3, 0, pid)  # WD_R1

    rows_data = sorted(join_records.keys(), key=_sort_key)

    rows_html = []
    divider_inserted = False
    for pid in rows_data:
        jr = join_records[pid]
        r = fr_by_id[pid]
        status = r["status"]
        is_finished = status == "FINISHED"
        is_wd = status in ("WD_R1", "WD_R2")
        is_cut = status == "CUT"

        if is_cut and not divider_inserted:
            rows_html.append(f"<tr class='cut-divider'><td colspan='{TOTAL_COLS}' style='text-align:center'>Missed cut</td></tr>")
            divider_inserted = True

        if is_finished:
            rank_cell = r["final_rank"]
            total_cell = r["final_to_par"]
        elif is_wd:
            rank_cell = "—"
            total_cell = "WD"
        else:
            rank_cell = "—"
            total_cell = "CUT"

        r1_cell = str(r["r1_score"]) if r["r1_score"] is not None else "-"
        r2_cell = str(r["r2_score"]) if r["r2_score"] is not None else "-"
        fr_cell = str(r["fr_score"]) if r.get("fr_score") is not None else "-"

        country_code = jr["nationality"]
        flag_cell = (
            f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
            f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
            if country_code in FLAG_ASSETS else ""
        )
        sponsor_text = _esc(sponsor_cache.get(pid, ""))
        name_cell = f"<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(jr['player_name'])}</span>"
        name_cell = linked_player_name_cell(pid, name_cell)
        if status == "WD_R1" or status == "WD_R2":
            name_cell += "<span class='status-badge'>WD</span>"
        elif is_cut:
            name_cell += "<span class='status-badge'>CUT</span>"

        # NEO forecast columns (pre-FR, R2-gated, never recomputed from
        # the real outcome): populated only for real finishers. A real
        # CUT player is mathematically out -- real, known 0.0% (same
        # site-wide convention klpga.neo_win.round_update_r2 and the R2
        # page already use). A real WD never had a forecast -- '—'.
        # A real finisher missing from the forecast's cutmaker set
        # (NO_BASE_FEATURE) shows 데이터 부족, never a fabricated value.
        if is_wd:
            top20_cell = top10_cell = top5_cell = win_cell = "—"
            metric_class = "win metric-empty"
        elif is_cut:
            top20_cell = top10_cell = top5_cell = win_cell = "0.0%"
            metric_class = "win"
        elif pid in forecast_by_id:
            f = forecast_by_id[pid]
            top20_cell = _pct(f["sg_adjusted_top20_probability"])
            top10_cell = _pct(f["sg_adjusted_top10_probability"])
            top5_cell = _pct(f["sg_adjusted_top5_probability"])
            win_cell = _pct(f["sg_adjusted_win_probability"])
            metric_class = "win"
        else:
            top20_cell = top10_cell = top5_cell = win_cell = _NOWRAP
            metric_class = "win"

        rows_html.append(
            f"<tr><td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span></th>"
            f"<td data-label='합계'><strong>{total_cell}</strong></td>"
            f"<td data-label='R1'>{r1_cell}</td>"
            f"<td data-label='R2'>{r2_cell}</td>"
            f"<td data-label='FR'>{fr_cell}</td>"
            f"<td class='{metric_class}' data-label='TOP20'>{top20_cell}</td>"
            f"<td class='{metric_class}' data-label='TOP10'>{top10_cell}</td>"
            f"<td class='{metric_class}' data-label='TOP5'>{top5_cell}</td>"
            f"<td class='{metric_class}' data-label='우승확률'>{win_cell}</td></tr>"
        )

    event_name = tourney["event_name"]
    start = tourney["start_date"]
    end = tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    course_line = f"{tourney['course_name']} · {tourney['out_course_text']}, {tourney['in_course_text']}"
    if tourney.get("is_stroke_play"):
        course_line += " · 스트로크 플레이"

    winner_name = fr_official["winner_player_name"]
    winner_to_par = fr_official["winner_to_par"]

    seo_description = f"{event_name} 공식 최종 결과 · 우승 {winner_name} {winner_to_par} · NEO GOLF DATA"
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/fr/"

    previous_meta_html = previous_tournament_meta_html()

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {_esc(event_name)} 공식 최종 결과</title>'
        f'<meta name="description" content="{_esc(seo_description)}">'
        f'<link rel="canonical" href="{canonical_url}">'
        f'<meta property="og:title" content="NEO GOLF DATA · {_esc(event_name)} 공식 최종 결과">'
        f'<meta property="og:description" content="{_esc(seo_description)}">'
        f'<meta property="og:url" content="{canonical_url}">'
        '<meta property="og:type" content="website">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../assets/neo.css">'
        "<style>.neo-global-header__inner{padding-inline:clamp(1rem,2.5vw,2.5rem)}</style>"
        '</head><body>'
        '<header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span>'
        '<span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span>'
        '<span class="neo-brand-legend__item">EVIDENCE</span>'
        '<span class="neo-brand-legend__item">ORACLE</span></span></a>'
        '<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a>'
        '<a href="/tournaments/" class="is-active" aria-current="page">대회 기록</a>'
        '<a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a>'
        '<a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header>'
        '<main><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<a href="/tournaments/">대회</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<span>{_esc(event_name)}</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<span aria-current="page">FR</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">공식 최종 결과</p>'
        f'<h1>{_esc(event_name)}</h1><p class="meta">{date_range}</p>'
        f'<p class="meta">{_esc(course_line)}</p>'
        f'<p class="meta"><strong>{_esc(winner_name)}</strong> 우승 · 최종 {_esc(winner_to_par)}</p>'
        f'{previous_meta_html}</div></section>'
    )

    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/">PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r2/">R2</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/fr/" aria-current="page">FR</a></li>'
        '</ol></nav>'
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="fr">'
        f'<div class="leaderboard-head"><h2>FR 결과 <small>{len(finisher_ids)}명</small></h2></div>'
        '<div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1"><thead><tr>'
        "<th>순위</th><th>선수</th><th>합계</th><th>R1</th><th>R2</th><th>FR</th>"
        "<th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
        f'<p><a href="https://klpga.co.kr/web/tourRecord/scoreRecord?gameCode={GAME_CODE}" rel="noopener">KLPGA 공식 기록 원문 ↗</a></p>'
        '</section>'
    )

    footer = (
        '</main>' +
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="/tournaments/2026/{GAME_CODE}/fr/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        '</div></footer></body></html>'
    )

    html = header + stage_nav + table_section + footer

    assert_no_blocked_probability_output(
        html,
        model_validated=(PUBLICATION_STATUS == "VALIDATED"),
        reference_estimate=(PUBLICATION_STATUS == "REFERENCE_ESTIMATE"),
        label=f"{GAME_CODE} FR",
    )

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")

    print(json.dumps({
        "written": str(OUT_PAGE),
        "rows": len(rows_data),
        "finisher_count": len(finisher_ids),
        "forecast_connected": len(set(forecast_by_id) & finisher_ids),
        "winner": winner_name,
        "winner_to_par": winner_to_par,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
