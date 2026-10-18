"""Build docs/tournaments/2026/2026100003/fr/index.html -- the official
FINAL result page for 아이스버그골프·서울신문 오픈 (game_code 2026100003),
from ICEBERG_2026100003_FR_OFFICIAL_V1.json (scripts/257).

OPERATOR INSTRUCTION (2026-10-18): this page shows the official final
leaderboard ONLY -- no NEO forecast/prediction columns, no probability
metrics, continuing scripts/244/255's house style (same header/hero/
stage-nav/table-wrap/leaderboard-table classes, same CUT/WD badge
convention and 'Missed cut' divider scripts/255 already established)
but with the forecast columns (컷 통과확률/TOP20/TOP10/TOP5/우승확률)
simply dropped -- this page has none of them.

Full 108-entrant roster shown, same convention as every prior stage on
this tournament: 61 real finishers ranked by their official final
result (scripts/257's own rank text, trusted verbatim -- including the
rank-1/rank-2 strokes tie resolved by the official site's own
countback, not re-derived here), then the 41 real missed-cut players
(below a reused 'Missed cut' divider), then the 6 real WD players
(5 WD at/by R2, 1 WD at R1) with WD badges, matching scripts/255's own
group ordering and divider placement exactly.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SITE_ORIGIN = "https://neogolfdata.com"

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.player_link import linked_player_name_cell  # noqa: E402
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402
from klpga.website_v2.previous_tournament_link import previous_tournament_meta_html  # noqa: E402

GAME_CODE = "2026100003"
FR_OFFICIAL_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_FR_OFFICIAL_V1.json"
JOIN_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "fr" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}

TOTAL_COLS = 6  # 순위/선수/R1/R2/FR/합계


def _load(name: str) -> dict:
    return json.loads((CONTENT / f"{GAME_CODE}_{name}").read_text(encoding="utf-8"))


def main() -> None:
    join = json.loads(JOIN_PATH.read_text(encoding="utf-8"))
    tourney = _load("TOURNAMENT_INFO.json")
    join_records = {r["player_code"]: r for r in join["records"]}

    fr_official = json.loads(FR_OFFICIAL_PATH.read_text(encoding="utf-8"))
    assert fr_official["game_code"] == GAME_CODE
    assert fr_official["verification_pass"], "FR official data failed its own arithmetic/consistency verification -- refusing to build the page"
    fr_by_id = {r["player_id"]: r for r in fr_official["records"]}
    assert set(fr_by_id) == set(join_records), "FR official player_id set does not match the 108-entrant roster"

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
        from html import escape as _esc
        sponsor_text = _esc(sponsor_cache.get(pid, ""))
        name_cell = f"<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(jr['player_name'])}</span>"
        name_cell = linked_player_name_cell(pid, name_cell)
        if status == "WD_R1" or status == "WD_R2":
            name_cell += "<span class='status-badge'>WD</span>"
        elif is_cut:
            name_cell += "<span class='status-badge'>CUT</span>"

        rows_html.append(
            f"<tr><td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span></th>"
            f"<td data-label='R1'>{r1_cell}</td>"
            f"<td data-label='R2'>{r2_cell}</td>"
            f"<td data-label='FR'>{fr_cell}</td>"
            f"<td data-label='합계'><strong>{total_cell}</strong></td></tr>"
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
    from html import escape as _esc

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
        '<div class="leaderboard-head"><h2>공식 최종 결과 <small>108명</small></h2></div>'
        '<div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1"><thead><tr>'
        "<th>순위</th><th>선수</th><th>R1</th><th>R2</th><th>FR</th><th>합계</th>"
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

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")

    print(json.dumps({
        "written": str(OUT_PAGE),
        "rows": len(rows_data),
        "winner": winner_name,
        "winner_to_par": winner_to_par,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
