"""Build the 제20회 S-OIL 챔피언십 (game_code 2026100001) R3 page --
real R1+R2+R3 scores for the 68 real players still in the field, plus a
forecast for the one round that remains (FR).

R3 has now actually been played (re-confirmed on 2026-10-31 by
re-dispatching neo-sync.yml stage=results and finding real, non-zero
round3score values -- not assumed; see scripts/282's own docstring for
the three-way cross-check against the raw R3 and R4 pages, and that no
second cut occurred between R3 and R4).

This supersedes the first version of this script (which pre-dated real
R3 data and showed a PRE-R3 forecast reusing scripts/279's post-R2
numbers under the R3 tab). Per operator direction, that reuse is wrong
now that R3 has real results -- this version reads only real R3 data
and a freshly computed post-R3 forecast (scripts/283), never the old
post-R2 numbers.

Source of truth:
  - SOIL_2026100001_R3_OFFICIAL_V1.json (scripts/282): real R1+R2+R3
    scores for the 68 players still in the field (no cut-missed player
    appears here at all -- there is nothing to exclude a second time).
  - SOIL_2026100001_POST_R3_FORECAST_V1.json (scripts/283): TOP20/
    TOP10/TOP5/win probabilities for those same 68, simulated from
    their real R1+R2+R3 totals plus this tournament's own R1+R2+R3 SG
    and the 2026-season prior-event SG history.

No cut-probability column, no CUT marker, no divider row: every player
on this page is already a confirmed part of the field, so there is
nothing left to flag. No SG raw figures appear anywhere on this page.
"""
from __future__ import annotations

import hashlib
import json
import sys
from html import escape as _esc
from pathlib import Path

_SITE_ORIGIN = "https://neogolfdata.com"

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CONTENT = ROOT / "content" / "website_v2"
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.player_link import linked_player_name_cell  # noqa: E402
from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache  # noqa: E402

GAME_CODE = "2026100001"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r3" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}

ENTRY_JOIN_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
TOURNAMENT_INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"
R3_OFFICIAL_PATH = CONTENT / f"SOIL_{GAME_CODE}_R3_OFFICIAL_V1.json"
POST_R3_PATH = CONTENT / f"SOIL_{GAME_CODE}_POST_R3_FORECAST_V1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    tourney = _load(TOURNAMENT_INFO_PATH)
    entry_join = _load(ENTRY_JOIN_PATH)
    r3_official = _load(R3_OFFICIAL_PATH)
    post_r3 = _load(POST_R3_PATH)
    assert tourney["game_code"] == GAME_CODE

    entry_by_id = {str(r["player_code"]): r for r in entry_join["records"]}
    official_by_id = {r["player_id"]: r for r in r3_official["records"]}
    assert len(official_by_id) == 68

    validation = post_r3["validation"]
    assert validation["field_count_matches_official"] is True
    assert validation["nesting_monotonicity_pass"] is True
    assert validation["win_probability_sum_within_tolerance"] is True
    assert validation["data_insufficient_players"] == []

    forecast_by_id = {r["player_id"]: r for r in post_r3["field_records"]}
    assert set(forecast_by_id) == set(official_by_id)

    sponsor_cache = cross_tournament_verified_sponsor_cache()

    rows_sorted = sorted(official_by_id.values(), key=lambda r: r["total_score"])
    rank_labels: dict[str, str] = {}
    i = 0
    while i < len(rows_sorted):
        j = i
        while j < len(rows_sorted) and rows_sorted[j]["total_score"] == rows_sorted[i]["total_score"]:
            j += 1
        label = str(i + 1) if j - i == 1 else f"TT{i + 1}"
        for k in range(i, j):
            rank_labels[rows_sorted[k]["player_id"]] = label
        i = j

    rows_html = []
    for r in rows_sorted:
        pid = r["player_id"]
        entry = entry_by_id.get(pid, {})
        country_code = entry.get("nationality", "KOR")
        if country_code in FLAG_ASSETS:
            flag_cell = (
                f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
                f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
            )
        else:
            flag_cell = ""
        sponsor_text = _esc(sponsor_cache.get(pid, ""))
        name_cell = f"<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(r['player_name'])}</span>"
        name_cell = linked_player_name_cell(pid, name_cell)

        f = forecast_by_id[pid]
        top20_cell = f"{f['top20_probability'] * 100:.1f}%"
        top10_cell = f"{f['top10_probability'] * 100:.1f}%"
        top5_cell = f"{f['top5_probability'] * 100:.1f}%"
        win_cell = f"{f['win_probability'] * 100:.1f}%"

        to_par = r["score_to_par"]
        to_par_cell = f"{to_par:+d}" if to_par else "0"

        rows_html.append(
            "<tr>"
            f"<td data-label='순위'>{rank_labels[pid]}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}"
            f"{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span></th>"
            f"<td data-label='합계'>{to_par_cell}</td>"
            f"<td data-label='R1'>{r['r1_score']}</td>"
            f"<td data-label='R2'>{r['r2_score']}</td>"
            f"<td data-label='R3'>{r['r3_score']}</td>"
            "<td data-label='FR'>-</td>"
            f"<td class='win' data-label='TOP20'>{top20_cell}</td>"
            f"<td class='win' data-label='TOP10'>{top10_cell}</td>"
            f"<td class='win' data-label='TOP5'>{top5_cell}</td>"
            f"<td class='win' data-label='우승확률'>{win_cell}</td>"
            "</tr>"
        )

    event_name = tourney["event_name"]
    start = tourney["start_date"]
    end = tourney["end_date"]
    date_range = f"{start[:4]}.{start[4:6]}.{start[6:8]} — {end[4:6]}.{end[6:8]}"
    course_line = f"{tourney['course_name']} · {tourney['out_course_text']}, {tourney['in_course_text']}"
    if tourney.get("is_stroke_play"):
        course_line += " · 스트로크 플레이"

    leader = rows_sorted[0]
    leader_to_par = leader["score_to_par"]
    leader_to_par_str = f"{leader_to_par:+d}" if leader_to_par else "0"
    seo_description = f"{event_name} 3R 공식 결과 · 선두 {leader['player_name']} {leader_to_par_str} · NEO GOLF DATA 실시간 분석"
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/r3/"

    factual_sha256 = _sha256(R3_OFFICIAL_PATH)
    forecast_sha256 = _sha256(POST_R3_PATH)

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1280">'
        f'<title>NEO GOLF DATA · {_esc(event_name)} 3R 공식 결과</title>'
        f'<meta name="description" content="{_esc(seo_description)}">'
        f'<link rel="canonical" href="{canonical_url}">'
        f'<meta property="og:title" content="NEO GOLF DATA · {_esc(event_name)} 3R 공식 결과">'
        f'<meta property="og:description" content="{_esc(seo_description)}">'
        f'<meta property="og:url" content="{canonical_url}">'
        '<meta property="og:type" content="website">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../assets/neo.css">'
        "<style>.neo-global-header__inner{padding-inline:clamp(1rem,2.5vw,2.5rem)}</style>"
        '<meta name="neo-publication-mode" content="factual-plus-estimate">'
        f'<meta name="neo-game-code" content="{GAME_CODE}">'
        '<meta name="neo-round-number" content="3">'
        f'<meta name="neo-factual-sha256" content="{factual_sha256}">'
        f'<meta name="neo-forecast-sha256" content="{forecast_sha256}">'
        '</head><body><header class="neo-global-header" data-neo-global-navigation>'
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
        '<span aria-current="page">R3</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">3R 공식 결과</p>'
        f'<h1>{_esc(event_name)}</h1><p class="meta">{date_range}</p>'
        f"<p class='meta'>{_esc(course_line)}</p>"
        "<p class='meta'>이전 대회 <a href='/tournaments/2026/2026100003/fr/'>아이스버그골프 · 서울신문 오픈</a></p></div></section>"
    )

    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/">PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r2/">R2</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r3/" aria-current="page">R3</a></li>'
        "<li class='stage-nav__item'><span class='stage-nav__disabled' aria-disabled='true'>FR</span></li>"
        "</ol></nav>"
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="r3">'
        f"<div class=\"leaderboard-head\"><h2>3R 공식 결과 <small>{len(rows_sorted)}명</small></h2></div>"
        '<div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1">'
        "<thead><tr><th>순위</th><th>선수</th><th>합계</th><th>R1</th><th>R2</th><th>R3</th><th>FR</th>"
        "<th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th></tr></thead>"
        "<tbody>" + "".join(rows_html) + "</tbody></table></div></section>"
    )

    footer = (
        "</main>"
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        '<a href="/tournaments/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        "</div></footer></body></html>"
    )

    html = header + stage_nav + table_section + footer
    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")

    print(json.dumps({
        "written": str(OUT_PAGE),
        "field": len(rows_sorted),
        "win_probability_sum": round(sum(forecast_by_id[r["player_id"]]["win_probability"] for r in rows_sorted), 6),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
