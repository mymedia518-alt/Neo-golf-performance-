"""Build the official FINAL result page for 제20회 S-OIL 챔피언십
(game_code 2026100001) -- docs/tournaments/2026/2026100001/fr/index.html.

Source of truth:
  - SOIL_2026100001_FR_OFFICIAL_V1.json (scripts/289): real final rank
    (KLPGA's own finish_position, including real scorecard ties) and
    R1-R4 scores for the 68 real finishers.
  - The FROZEN, sha256-verified archive copy of
    SOIL_2026100001_POST_R3_FORECAST_V1.json (never the live file, and
    never recomputed/adjusted to match the real outcome) for the
    TOP20/TOP10/TOP5/win-probability columns -- the same pre-FR
    forecast already shown on the R3 page, now displayed alongside the
    real result it was forecasting. This follows the same "frozen
    pre-result forecast shown next to the real outcome" convention
    already established for a prior tournament's own FR page
    (scripts/258), adapted to read from the sha256-verified archive
    rather than the live file for extra certainty that nothing was
    altered after freezing.

SCOPE: only the 68 real finishers appear, same as the R3 page --
"no cut-probability column, no CUT marker, no divider row: every
player on this page is already a confirmed part of the field, so there
is nothing left to flag" (scripts/281's own docstring). The FR page is
a direct continuation of that same field, now with final results.

No raw SG figures appear anywhere on this page -- the FR SG file
(scripts/290) is never read here.

Rank display: the official final_rank is used verbatim (never
recomputed); real ties (final_tie=True, confirmed by scripts/289's own
rank/score-group consistency check) are shown with the standard golf
leaderboard "T" prefix (e.g. "T3"), which is more accurate than R3's
own provisional "TT" grouping label (R3 had no official tie data yet,
only matching total_score; FR has the real, confirmed tie from KLPGA
itself).
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
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "fr" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}

ENTRY_JOIN_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
TOURNAMENT_INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"
FR_OFFICIAL_PATH = CONTENT / f"SOIL_{GAME_CODE}_FR_OFFICIAL_V1.json"
ARCHIVE_MANIFEST_PATH = CONTENT / "archive" / GAME_CODE / "r3" / "R3_ARCHIVE_MANIFEST_V1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_frozen_forecast() -> dict:
    manifest = _load(ARCHIVE_MANIFEST_PATH)
    rec = next(r for r in manifest["records"] if r["original_path"].endswith("SOIL_2026100001_POST_R3_FORECAST_V1.json"))
    archive_path = REPO_ROOT / rec["archive_path"]
    data = archive_path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == rec["sha256"], "frozen forecast sha256 mismatch -- refusing to publish"
    return json.loads(data), archive_path


def main() -> None:
    tourney = _load(TOURNAMENT_INFO_PATH)
    entry_join = _load(ENTRY_JOIN_PATH)
    fr_official = _load(FR_OFFICIAL_PATH)
    assert tourney["game_code"] == GAME_CODE
    assert fr_official["verification_pass"], "FR official data failed its own verification -- refusing to build the page"

    forecast, forecast_archive_path = _load_frozen_forecast()

    entry_by_id = {str(r["player_code"]): r for r in entry_join["records"]}
    official_by_id = {r["player_id"]: r for r in fr_official["records"]}
    assert len(official_by_id) == 68

    forecast_by_id = {r["player_id"]: r for r in forecast["field_records"]}
    assert set(forecast_by_id) == set(official_by_id), "frozen forecast field != FR official field"

    sponsor_cache = cross_tournament_verified_sponsor_cache()

    rows_sorted = sorted(official_by_id.values(), key=lambda r: r["final_rank_numeric"])

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

        rank_cell = f"T{r['final_rank']}" if r["final_tie"] else r["final_rank"]
        to_par = r["score_to_par"]
        to_par_cell = f"{to_par:+d}" if to_par else "0"

        rows_html.append(
            "<tr>"
            f"<td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}"
            f"{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span></th>"
            f"<td data-label='합계'><strong>{to_par_cell}</strong></td>"
            f"<td data-label='R1'>{r['r1_score']}</td>"
            f"<td data-label='R2'>{r['r2_score']}</td>"
            f"<td data-label='R3'>{r['r3_score']}</td>"
            f"<td data-label='FR'>{r['r4_score']}</td>"
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

    winner_name = fr_official["winner_player_name"]
    winner_to_par = fr_official["winner_score_to_par"]
    winner_to_par_str = f"{winner_to_par:+d}" if winner_to_par else "0"

    seo_description = f"{event_name} 공식 최종 결과 · 우승 {winner_name} {winner_to_par_str} · NEO GOLF DATA"
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/fr/"

    factual_sha256 = _sha256(FR_OFFICIAL_PATH)
    forecast_sha256 = hashlib.sha256(forecast_archive_path.read_bytes()).hexdigest()

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1280">'
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
        '<meta name="neo-publication-mode" content="factual-plus-estimate">'
        f'<meta name="neo-game-code" content="{GAME_CODE}">'
        '<meta name="neo-round-number" content="4">'
        f'<meta name="neo-factual-sha256" content="{factual_sha256}">'
        f'<meta name="neo-forecast-sha256" content="{forecast_sha256}">'
        '</head><body><header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/"><img class="neo-brand-logo" src="/assets/neo-logo.png" alt="NEO GOLF DATA" width="362" height="160">'
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
        f"<p class='meta'>{_esc(course_line)}</p>"
        f"<p class='meta'><strong>{_esc(winner_name)}</strong> 우승 · 최종 {winner_to_par_str}</p>"
        "<p class='meta'>이전 대회 <a href='/tournaments/2026/2026100003/fr/'>아이스버그골프 · 서울신문 오픈</a></p></div></section>"
    )

    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/">PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r2/">R2</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r3/">R3</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/fr/" aria-current="page">FR</a></li>'
        "</ol></nav>"
    )

    video_section = (
        "<section class='panel' id='fr-video'><p class='note'>NEO GOLF DATA</p>"
        "<video controls playsinline style='display:block;width:100%;max-width:100%;height:auto' "
        f"src='/assets/tournaments/{GAME_CODE}/neo-golf-data-fr.mp4'></video></section>"
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="fr">'
        f"<div class=\"leaderboard-head\"><h2>최종 결과 <small>{len(rows_sorted)}명</small></h2></div>"
        '<div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1">'
        "<thead><tr><th>순위</th><th>선수</th><th>합계</th><th>R1</th><th>R2</th><th>R3</th><th>FR</th>"
        "<th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th></tr></thead>"
        "<tbody>" + "".join(rows_html) + "</tbody></table></div>"
        f'<p><a href="https://klpga.co.kr/web/tourRecord/scoreRecord?gameCode={GAME_CODE}" rel="noopener">KLPGA 공식 기록 원문 ↗</a></p>'
        '</section>'
    )

    footer = (
        "</main>"
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        '<a href="/tournaments/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        "</div></footer></body></html>"
    )

    html = header + stage_nav + video_section + table_section + footer
    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")

    print(json.dumps({
        "written": str(OUT_PAGE),
        "field": len(rows_sorted),
        "winner": winner_name,
        "winner_to_par": winner_to_par_str,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
