"""Build the 제20회 S-OIL 챔피언십 (game_code 2026100001) R2 page,
matching docs/tournaments/2026/2026100003/r2/index.html (아이스버그골프
· 서울신문 오픈, the immediately preceding tournament) byte-for-byte in
structure, CSS classes, copy style, table layout, and row markup. Only
real tournament differences are reflected: S-OIL is a 4-round event so
the stage-nav and table carry an R3 tab/column iceberg's own 3-round
R2 page does not have, and the official field is 96, not 108.

CUT COLUMN DESIGN (per explicit operator direction, this build): the
header is "컷 통과확률" and every one of the 96 players -- cutmaker and
cut-missed alike -- shows the same kind of value: the cut-pass
percentage already computed before R2 started, reused verbatim (see
"1R 후 cut-forecast" below), never recomputed and never swapped out for
result text ("통과"/"탈락") or a status word. This column carries no
real-outcome fact or extra explanation. No footnote, no parenthetical.
The "CUT" status badge next to a missed player's name and the "Missed
cut" divider row are unrelated, pre-existing design elements that still
carry the real result, kept unchanged.

1R 후 cut-forecast source: the same per-player cut-pass percentage
already published on this tournament's own R1 page
(docs/tournaments/2026/2026100001/r1/index.html, data-r1-player rows,
class='cut-probability' cells) -- that number was computed after R1
and before R2 started, i.e. exactly "2R 시작 전 산출한 컷 통과확률".
It is parsed from that committed file, never recomputed or guessed; if
any of the 68 cutmakers were missing a value there, this script raises
rather than filling one in (see _load_r1_cut_forecast).

Source of truth:
  - SOIL_2026100001_R2_OFFICIAL_V1.json (scripts/278): real R1+R2
    scores and the real, officially-determined 36-hole cut for all 96
    entrants (68 made cut, 28 missed -- see that script's own docstring
    for exactly how this was read off two real KLPGA leaderboard pages,
    never a simulated or assumed cut rule).
  - SOIL_2026100001_POST_R2_FORECAST_V1.json (scripts/279): TOP20/TOP10/
    TOP5/win probabilities for the 68 real cutmakers only, simulated
    forward from their real known R1+R2 total. Never shown for a
    cut-missed player (iceberg's own page has no real-cut case to
    precedent this against; the site's existing "—" missing-data glyph,
    already used by iceberg's own page for a withdrawn player's empty
    cells, is reused here for the same reason -- no applicable
    forecast -- rather than a new symbol).
  - 2026100001_ENTRY_KRANKING_JOIN.json: nationality/qualification
    (unchanged from the PRE build).

No SG raw figures (round-level Strokes Gained numbers or components)
appear anywhere on this page -- SG is read only as a verification input
by scripts/279, never rendered here.
"""
from __future__ import annotations

import hashlib
import json
import re
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
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r2" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}

ENTRY_JOIN_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
TOURNAMENT_INFO_PATH = CONTENT / f"{GAME_CODE}_TOURNAMENT_INFO.json"
R2_OFFICIAL_PATH = CONTENT / f"SOIL_{GAME_CODE}_R2_OFFICIAL_V1.json"
POST_R2_PATH = CONTENT / f"SOIL_{GAME_CODE}_POST_R2_FORECAST_V1.json"
R1_PAGE_PATH = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html"

_DASH = "—"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_r1_cut_forecast(path: Path) -> dict[str, str]:
    """Parse the already-published R1 page for its per-player cut-pass
    percentage, keyed by player id -- the pre-R2 forecast this build
    reuses verbatim, never recomputes. Returns only players whose cell
    actually had a percentage; a player with no parseable value is left
    out rather than filled in with a guess, and the caller must decide
    what to do about that gap.
    """
    html = path.read_text(encoding="utf-8")
    rows = re.split(r"(?=<tr data-r1-player=')", html)
    out: dict[str, str] = {}
    for row in rows:
        m_id = re.search(r"data-r1-player='(\d+)'", row)
        if not m_id:
            continue
        m_pct = re.search(r"class='cut-probability' data-label='컷 통과확률'>([^<]*)<", row)
        if m_pct:
            out[m_id.group(1)] = m_pct.group(1)
    return out


def main() -> None:
    tourney = _load(TOURNAMENT_INFO_PATH)
    entry_join = _load(ENTRY_JOIN_PATH)
    r2_official = _load(R2_OFFICIAL_PATH)
    post_r2 = _load(POST_R2_PATH)
    r1_cut_forecast = _load_r1_cut_forecast(R1_PAGE_PATH)
    assert tourney["game_code"] == GAME_CODE

    entry_by_id = {str(r["player_code"]): r for r in entry_join["records"]}
    official_by_id = {r["player_id"]: r for r in r2_official["records"]}
    forecast_by_id = {r["player_id"]: r for r in post_r2["cutmaker_records"]}
    official_field_count = len(official_by_id)
    assert official_field_count == 96

    missing_forecast = sorted(pid for pid in official_by_id if pid not in r1_cut_forecast)
    if missing_forecast:
        names = ", ".join(f"{pid}({official_by_id[pid]['player_name']})" for pid in missing_forecast)
        print(json.dumps({
            "status": "ABORTED_MISSING_PRE_R2_CUT_FORECAST",
            "reason": (
                "R1 page has no parseable cut-probability cell for these players; "
                "refusing to guess a value -- re-check/repair the R1 page first."
            ),
            "missing_player_ids": missing_forecast,
            "missing_players": names,
        }, ensure_ascii=False, indent=2))
        return

    sponsor_cache = cross_tournament_verified_sponsor_cache()

    rows_sorted = sorted(official_by_id.values(), key=lambda r: r["total_score"])
    # Competition ranking with ties -- "TT#" for a tied group, matching
    # iceberg's own R2 page exactly (verified: that page uses "TT3",
    # "TT6", "TT9" ... never "T3"; S-OIL's own earlier R1 page used a
    # different "T#" convention, an inconsistency this build does not
    # carry forward onto the page the operator asked to match here).
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

    # S-OIL's table has 12 columns (iceberg's 3-round R2 table has 11 --
    # one fewer, no R3). The divider row's colspan must match.
    TABLE_COLUMNS = 12
    CUT_DIVIDER_ROW = f"<tr class='cut-divider'><td colspan='{TABLE_COLUMNS}' style='text-align:center'>Missed cut</td></tr>"

    rows_html = []
    divider_inserted = False
    for r in rows_sorted:
        pid = r["player_id"]
        if not r["made_cut"] and not divider_inserted:
            rows_html.append(CUT_DIVIDER_ROW)
            divider_inserted = True
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

        made_cut = r["made_cut"]
        cut_cell = r1_cut_forecast[pid]
        empty_class = "" if made_cut else " metric-empty"
        # Inline status badge next to the player name for a cut-missed
        # player -- the same component (class='status-badge') iceberg's
        # own page uses for its "CUT" and "WD" markers (docs/assets/
        # neo.css:182/305), reused here with the same "CUT" text. Per
        # operator direction, ordered 국가(flag) -> 이름(name) ->
        # 스폰서(sponsor) -> CUT -- badge last, after the sponsor
        # (iceberg itself orders name -> CUT -> sponsor; this page
        # deliberately differs here per explicit instruction).
        badge_cell = "" if made_cut else "<span class='status-badge'>CUT</span>"
        if made_cut:
            f = forecast_by_id[pid]
            top20_cell = f"{f['top20_probability'] * 100:.1f}%"
            top10_cell = f"{f['top10_probability'] * 100:.1f}%"
            top5_cell = f"{f['top5_probability'] * 100:.1f}%"
            win_cell = f"{f['win_probability'] * 100:.1f}%"
        else:
            top20_cell = top10_cell = top5_cell = win_cell = _DASH

        to_par = r["score_to_par"]
        to_par_cell = f"{to_par:+d}" if to_par else "0"

        rows_html.append(
            "<tr>"
            f"<td data-label='순위'>{rank_labels[pid]}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}"
            f"{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span>"
            f"{badge_cell}</th>"
            f"<td data-label='합계'>{to_par_cell}</td>"
            f"<td data-label='R1'>{r['r1_score']}</td>"
            f"<td data-label='R2'>{r['r2_score']}</td>"
            "<td data-label='R3'>-</td><td data-label='FR'>-</td>"
            f"<td class='win' data-label='컷 통과확률'>{cut_cell}</td>"
            f"<td class='win{empty_class}' data-label='TOP20'>{top20_cell}</td>"
            f"<td class='win{empty_class}' data-label='TOP10'>{top10_cell}</td>"
            f"<td class='win{empty_class}' data-label='TOP5'>{top5_cell}</td>"
            f"<td class='win{empty_class}' data-label='우승확률'>{win_cell}</td>"
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
    seo_description = f"{event_name} 2R 공식 결과 · 선두 {leader['player_name']} {leader_to_par_str} · NEO GOLF DATA 실시간 분석"
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/r2/"

    factual_sha256 = _sha256(R2_OFFICIAL_PATH)
    forecast_sha256 = _sha256(POST_R2_PATH)

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=1280">'
        f'<title>NEO GOLF DATA · {_esc(event_name)} 2R 공식 결과</title>'
        f'<meta name="description" content="{_esc(seo_description)}">'
        f'<link rel="canonical" href="{canonical_url}">'
        f'<meta property="og:title" content="NEO GOLF DATA · {_esc(event_name)} 2R 공식 결과">'
        f'<meta property="og:description" content="{_esc(seo_description)}">'
        f'<meta property="og:url" content="{canonical_url}">'
        '<meta property="og:type" content="website">'
        '<meta name="twitter:card" content="summary_large_image">'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../assets/neo.css">'
        "<style>.neo-global-header__inner{padding-inline:clamp(1rem,2.5vw,2.5rem)}</style>"
        '<meta name="neo-publication-mode" content="factual-plus-estimate">'
        f'<meta name="neo-game-code" content="{GAME_CODE}">'
        '<meta name="neo-round-number" content="2">'
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
        '<span aria-current="page">R2</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">2R 공식 결과</p>'
        f'<h1>{_esc(event_name)}</h1><p class="meta">{date_range}</p>'
        f"<p class='meta'>{_esc(course_line)}</p>"
        "<p class='meta'>이전 대회 <a href='/tournaments/2026/2026100003/fr/'>아이스버그골프 · 서울신문 오픈</a></p></div></section>"
    )

    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/">PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r2/" aria-current="page">R2</a></li>'
        f"<li class='stage-nav__item'><span class='stage-nav__disabled' aria-disabled='true'>R3</span></li>"
        f"<li class='stage-nav__item'><span class='stage-nav__disabled' aria-disabled='true'>FR</span></li>"
        "</ol></nav>"
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="r2">'
        f"<div class=\"leaderboard-head\"><h2>2R 공식 결과 <small>{official_field_count}명</small></h2></div>"
        '<div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1">'
        "<thead><tr><th>순위</th><th>선수</th><th>합계</th><th>R1</th><th>R2</th><th>R3</th><th>FR</th>"
        "<th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th></tr></thead>"
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
        "rows": len(rows_sorted),
        "made_cut": sum(1 for r in rows_sorted if r["made_cut"]),
        "missed_cut": sum(1 for r in rows_sorted if not r["made_cut"]),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
