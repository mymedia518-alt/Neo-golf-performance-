"""Build the HITE JINRO Championship (game_code 2026100005) PRE page,
replicating docs/tournaments/2026/2026090002/pre/index.html's (Hana's
own build, itself replicating the 2026090003/pre reference verbatim
per 139_build_hana_pre_kb_structure.py's own docstring) exact HTML
structure and CSS byte-for-byte -- only tournament-specific text, the
108-row entry table's content, and the stage-nav link states differ.
No new sections, no new CSS classes are introduced, matching this
project's existing "self-contained per-tournament builder, structure
copied verbatim" convention (see 139/151/160/174/181's own headers).

Source of truth: ONLY klpga_pipeline/content/website_v2/2026100005_*.json
(TOURNAMENT_INFO, ENTRY_SNAPSHOT, ENTRY_KRANKING_JOIN), all mirrored
directly from the validated `reader/2026100005` branch (NEO Sync run
#6, all 7 validation checks PASS -- see reports/2026100005/REVIEW_REPORT_V1.md
on that branch). No other source is read.

WHAT IS DELIBERATELY OMITTED, AND WHY (no-fabrication rule):

- NEO 경기력 band + 컷 통과확률/TOP20/TOP10/TOP5/우승확률 (all 5 M4
  probability columns): forced to "데이터 부족" for ALL 108 entrants,
  never just some. The M4 win-probability model
  (scripts/130_build_hana_pre_m4.py) requires a populated historical
  warehouse (player_event/player_round tables in data/klpga.sqlite) to
  compute point-in-time features per player. That file is
  .gitignore'd and does not exist anywhere in this sandbox or on the
  GitHub Actions runner that ran NEO Sync (confirmed via `git log
  --all` -- no history -- and a filesystem-wide search -- no copy).
  This is the exact same fallback value this codebase's own 139
  script already uses for players it cannot analyze (amateurs with an
  improper KGA basis) -- "데이터 부족" is this project's own
  established convention for "no legitimate value exists", not a
  placeholder invented for this build.
- data-neo-score attribute on the band span: omitted entirely (not
  set to 0.00 or any other value) for the same reason -- no M4 record
  exists to source it from, and it is invisible metadata, not
  rendered text, so omitting it changes no UX/layout.
- Sponsor: left blank for all 108 entrants. 139's own
  _load_sponsor_by_id() docstring states the established rule
  explicitly: "A player_id with no verified sponsor anywhere is
  simply absent from the returned dict -- the caller renders an empty
  sponsor slot, never a guess." No VERIFIED_OFFICIAL sponsor evidence
  file exists for any 2026100005 entrant, so every sponsor slot is
  empty, matching that exact rule.
- "2025 우승 ..." hero fact line: omitted entirely (not left with a
  placeholder). No prior-year 하이트진로 챔피언십 winner fact exists
  anywhere in this repository or in reader/2026100005 to report.
  Hana's own hero line for this fact is real historical data specific
  to that tournament; inventing an equivalent line here would be
  fabrication. This is a self-contained <p class="meta"> the
  reference markup does not require to be present.
- Par / hole-count ("72홀 스트로크 플레이"): omitted. TOURNAMENT_INFO
  confirms is_stroke_play=true (rendered) and course_name/out-in
  labels (rendered), but no par value or explicit hole count for
  Blue Heron is present in the official getGameList response this
  repo collected -- inventing "Par 72"/"72홀" the way Hana's hero
  states them would be a guess this project's rules forbid.
- Country flag <img> for player_code 13386 (에리카 윤 스미스(I),
  nationality=USA): omitted (no <img> tag emitted for this one row's
  flag cell) rather than either fabricating an SVG or pointing at a
  path that does not exist -- docs/assets/flags/ has no USA.svg
  (confirmed: 8 files, KOR/CHN/THA/JPN/PHI/TPE/AUS/NZL only). All 107
  other entrants' flags render normally (KOR/CHN/THA all have real
  assets).
- Stage nav: R1/R2/R3/FR all render as the same disabled placeholder
  the reference page itself starts from -- none of those pages exist
  yet for this game_code.

K-RANKING: sourced from 2026100005_ENTRY_KRANKING_JOIN.json, itself a
direct join of the 108 official entrants against the full 747-player
official K-Ranking table (k-rankings.klpga.co.kr/allplayer.jsp,
2026-W39) by official player_code -- no player_master/warehouse
dependency, matching this repo's own established "K-RANKING
BEYOND-TOP-120 RESTORATION" precedent (scripts/140). 105 of 108
entrants have a real official_k_rank; 3 are genuinely absent from the
747-player table (render "-"), consistent with 140's own "no number
is ever guessed for those" rule.

Row order: mirrors 139's own convention exactly -- k_rank ascending
first, then the no-k_rank remainder in a stable, ranking-free order
(by name), since without a win-probability model there is no
neo_score to break ties with the way 139 does for its own no-k_rank
group.
"""
from __future__ import annotations

import json
import sys
from html import escape as _esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.player_link import linked_player_name_cell  # noqa: E402

GAME_CODE = "2026100005"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "pre" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}


def _load(name: str) -> dict:
    return json.loads((CONTENT / f"{GAME_CODE}_{name}").read_text(encoding="utf-8"))


_NOWRAP = "<span style='white-space:nowrap'>데이터 부족</span>"


def main() -> None:
    tourney = _load("TOURNAMENT_INFO.json")
    kranking_join = _load("ENTRY_KRANKING_JOIN.json")
    records = kranking_join["records"]
    assert len(records) == 108, f"expected exactly 108 official entries, found {len(records)}"
    assert tourney["game_code"] == GAME_CODE

    def _sort_key(r):
        if r["official_k_rank"] is not None:
            return (0, r["official_k_rank"], "")
        return (1, 0, r["player_name"])

    rows_data = sorted(records, key=_sort_key)

    rows_html = []
    for r in rows_data:
        pid = r["player_code"]
        k_rank_cell = str(r["official_k_rank"]) if r["official_k_rank"] is not None else "—"
        band_cell = f"<span class='band' role='img' aria-label='NEO 경기력 데이터 부족'>{_NOWRAP}</span>"
        cut_cell = top20_cell = top10_cell = top5_cell = win_cell = _NOWRAP

        country_code = r["nationality"]
        if country_code in FLAG_ASSETS:
            flag_cell = (
                f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
                f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
            )
        else:
            flag_cell = ""

        name_cell = f"<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(r['player_name'])}</span>"
        name_cell = linked_player_name_cell(pid, name_cell)
        rows_html.append(
            f"<tr><th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}"
            f"{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'></span></th>"
            f"<td data-label='KLPGA K-RANKING'>{k_rank_cell}</td>"
            f"<td data-label='NEO 경기력'>{band_cell}</td>"
            f"<td class='win' data-label='컷 통과확률'>{cut_cell}</td>"
            f"<td class='win' data-label='TOP20'>{top20_cell}</td>"
            f"<td class='win' data-label='TOP10'>{top10_cell}</td>"
            f"<td class='win' data-label='TOP5'>{top5_cell}</td>"
            f"<td class='win' data-label='우승확률'>{win_cell}</td></tr>"
        )

    event_name = tourney["event_name"]
    start = tourney["start_date"]  # YYYYMMDD
    end = tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    course_line = f"{tourney['course_name']} · {tourney['out_course_text']}, {tourney['in_course_text']}"
    if tourney.get("is_stroke_play"):
        course_line += " · 스트로크 플레이"

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {_esc(event_name)}</title>'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../assets/neo.css"></head><body>'
        '<header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span>'
        '<span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span>'
        '<span class="neo-brand-legend__item">EVIDENCE</span>'
        '<span class="neo-brand-legend__item">ORACLE</span></span></a>'
        '<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a>'
        f'<a href="/tournaments/2026/{GAME_CODE}/pre/" class="is-active" aria-current="page">대회</a>'
        '<a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a>'
        '<a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header>'
        '<main><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<a href="/tournaments/">대회</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<span>{_esc(event_name)}</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<span aria-current="page">PRE</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">PRE 분석</p>'
        f'<h1>{_esc(event_name)}</h1><p class="meta">{date_range}</p>'
        f'<p class="meta">{_esc(course_line)}</p></div>'
        '<p class="round-update-note">1R 종료 후 업데이트</p></section>'
    )

    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/" aria-current="page">사전 분석 PRE</a></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R1</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R2</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li>'
        '<li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FR</span></li>'
        '</ol></nav>'
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="pre">'
        '<div class="leaderboard-head"><h2>PRE 참가 선수 <small>108명</small></h2></div>'
        '<div class="table-wrap"><table class="data leaderboard-table"><thead><tr>'
        "<th>선수</th><th>KLPGA K-RANKING</th>"
        "<th class='band-head'>NEO 경기력 "
        "<button type='button' class='info-control' aria-label='NEO 경기력 설명' aria-expanded='false' aria-controls='neo-info'>ⓘ</button>"
        "<span id='neo-info' class='info-popover' role='tooltip' tabindex='-1'>최근 공식 경기 데이터를 출전 선수들과 비교한 상대적 경기력 위치입니다.</span></th>"
        "<th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div></section>"
    )

    info_js = (
        "<script>(function(){const b=document.querySelector('.info-control'),p=document.getElementById('neo-info');"
        "if(!b||!p)return;function close(){p.classList.remove('is-open');b.setAttribute('aria-expanded','false')}"
        "function place(){if(window.innerWidth<=760)return;const r=b.getBoundingClientRect();"
        "let left=Math.min(r.left,window.innerWidth-p.offsetWidth-16);left=Math.max(16,left);"
        "p.style.left=left+'px';p.style.top=(r.bottom+6)+'px'}"
        "b.addEventListener('click',function(){const open=p.classList.toggle('is-open');"
        "b.setAttribute('aria-expanded',String(open));if(open){place();p.focus()}});"
        "document.addEventListener('keydown',function(e){if(e.key==='Escape'&&p.classList.contains('is-open'))close()});"
        "document.addEventListener('click',function(e){if(!b.contains(e.target)&&!p.contains(e.target))close()});"
        "window.addEventListener('scroll',close,true);window.addEventListener('resize',close)})();</script>"
    )

    footer = (
        '</main>' + info_js +
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="/tournaments/2026/{GAME_CODE}/pre/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
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
        "k_rank_matched": sum(1 for r in rows_data if r["official_k_rank"] is not None),
        "k_rank_unmatched": sum(1 for r in rows_data if r["official_k_rank"] is None),
        "data_insufficient_all_rows": True,
        "reason": "no historical warehouse (data/klpga.sqlite) available to run the M4 win-probability model",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
