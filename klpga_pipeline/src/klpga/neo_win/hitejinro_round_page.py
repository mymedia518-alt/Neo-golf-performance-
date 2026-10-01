"""Shared round-page (R1/R2/R3/FR) renderer for the HITE JINRO
Championship (game_code 2026100005) -- imported only by this
tournament's own scripts/196-199_build_hitejinro_r*.py wrappers, never
by another tournament's builder (this repo's own established
self-contained-per-tournament convention is about never sharing a
builder ACROSS tournaments; sharing logic across one tournament's own
four near-identical round stages is exactly what
klpga.website_v2.player_link/home_ownership_guard/round_score_format
already do site-wide).

Reads real leaderboard rows from normalized/2026100005/LEADERBOARD.json
(NEO Sync stage="results" output -- see klpga.neo_reader.sync). Renders
real rank/player identity/round scores only. NEO 경기력 and every
probability column (컷 통과율/TOP20/TOP10/TOP5/우승확률) render 데이터
부족 for every row, same as the PRE page and for the identical reason:
no historical warehouse exists to run the M4 model, whether or not real
round data now exists (see scripts/193_build_hitejinro_pre_m4.py's own
module docstring for the full, exhaustive account of what was checked).
Real round scores are never blocked by that -- they come from NEO
Sync's official leaderboard collection directly, no model involved.

FAILS CLOSED: raises FileNotFoundError with a precise message if
LEADERBOARD.json does not exist yet (true right now -- no round has
been played; NEO Sync's stage="results" collection itself raises for
exactly this reason, "an expected state pre-tournament", per that
module's own docstring) -- never renders an empty or fabricated table.
"""
from __future__ import annotations

import json
from html import escape as _esc
from pathlib import Path

from klpga.website_v2.player_identity import cross_tournament_verified_sponsor_cache
from klpga.website_v2.player_link import linked_player_name_cell
from klpga.website_v2.previous_tournament_link import previous_tournament_meta_html
from klpga.website_v2.round_score_format import format_to_par

GAME_CODE = "2026100005"
_NOWRAP = "<span style='white-space:nowrap'>데이터 부족</span>"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_FLAG_ASSETS = {p.stem for p in (_REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}

STAGE_LABELS = {1: ("r1", "R1"), 2: ("r2", "R2"), 3: ("r3", "R3"), 4: ("fr", "FR")}


def _load_nationality_by_id(content_root: Path) -> dict[str, str]:
    """{player_id: nationality} from the real official entry/K-ranking
    join (same source scripts/190's PRE page already uses for the
    identical flag feature) -- empty dict (no flags rendered) if the
    file doesn't exist yet, never a guessed nationality."""
    path = content_root / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
    if not path.is_file():
        return {}
    records = json.loads(path.read_text(encoding="utf-8")).get("records", [])
    return {r["player_code"]: r["nationality"] for r in records if r.get("nationality")}


def load_leaderboard(content_root: Path) -> dict:
    path = content_root / f"{GAME_CODE}_LEADERBOARD.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"no {path} yet -- run NEO Sync with --stage results after the relevant round has real "
            "official data (see klpga.neo_reader.sync's own 'stage=\"results\"... never attempted "
            "implicitly' rule). This page cannot be built before that."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def render_round_page(round_number: int, *, tournament_name: str, date_range: str, content_root: Path) -> str:
    if round_number not in STAGE_LABELS:
        raise ValueError(f"round_number must be 1-4, got {round_number}")
    stage_key, stage_label = STAGE_LABELS[round_number]

    board = load_leaderboard(content_root)
    records = board["records"]
    score_field = f"r{round_number}_score"
    played = [r for r in records if r.get(score_field) is not None or r.get("withdrawn") or r.get("disqualified")]
    if not played:
        raise FileNotFoundError(
            f"LEADERBOARD.json exists but no row has a real {score_field} yet -- round {round_number} "
            "has not actually been played/collected. Never renders a round page with zero real scores."
        )

    played.sort(key=lambda r: (r.get("finish_position_numeric") is None, r.get("finish_position_numeric", 10**9)))

    nationality_by_id = _load_nationality_by_id(content_root)
    sponsor_cache = cross_tournament_verified_sponsor_cache()

    rows_html = []
    for r in played:
        pid = str(r["player_id"])
        status = "WD" if r.get("withdrawn") else "DQ" if r.get("disqualified") else None
        rank_cell = _esc(str(r.get("finish_position") or "-"))
        # r{N}_score is the raw stroke count for that round (e.g. 68),
        # never a to-par differential -- format_to_par is only for an
        # already-relative-to-par value (score_to_par below). Running a
        # raw score through format_to_par would print "+68", which is
        # not what that field means.
        score_cell = status or (str(r[score_field]) if r.get(score_field) is not None else "-")
        total_cell = status or (format_to_par(r["score_to_par"]) if r.get("score_to_par") is not None else "-")
        country_code = nationality_by_id.get(pid)
        flag_cell = (
            f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
            f"style='display:inline;vertical-align:middle;margin-right:4px'>"
            if country_code in _FLAG_ASSETS else ""
        )
        sponsor_text = _esc(sponsor_cache.get(pid, ""))
        name_cell = (
            f"{flag_cell}<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(r['player_name'])}</span>"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span>"
        )
        name_cell = linked_player_name_cell(pid, name_cell)
        rows_html.append(
            f"<tr><td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{name_cell}</th>"
            f"<td data-label='합계'>{total_cell}</td>"
            f"<td data-label='{stage_label}'>{score_cell}</td>"
            f"<td data-label='NEO 경기력'>{_NOWRAP}</td>"
            f"<td class='win' data-label='컷 통과확률'>{_NOWRAP}</td>"
            f"<td class='win' data-label='TOP20'>{_NOWRAP}</td>"
            f"<td class='win' data-label='TOP10'>{_NOWRAP}</td>"
            f"<td class='win' data-label='TOP5'>{_NOWRAP}</td>"
            f"<td class='win' data-label='우승확률'>{_NOWRAP}</td></tr>"
        )

    stage_nav_items = []
    for n, (key, label) in [(0, ("pre", "사전 분석 PRE"))] + [(n, STAGE_LABELS[n]) for n in (1, 2, 3, 4)]:
        display_label = "사전 분석 PRE" if key == "pre" else label
        if key == "pre" or n < round_number:
            href = f"/tournaments/2026/{GAME_CODE}/{key}/"
            cur = " aria-current='page'" if key == stage_key else ""
            stage_nav_items.append(f"<li class='stage-nav__item'><a class='stage-nav__link' href='{href}'{cur}>{display_label}</a></li>")
        elif key == stage_key:
            stage_nav_items.append(f"<li class='stage-nav__item'><a class='stage-nav__link' href='/tournaments/2026/{GAME_CODE}/{key}/' aria-current='page'>{display_label}</a></li>")
        else:
            stage_nav_items.append(f"<li class='stage-nav__item'><span class='stage-nav__disabled' aria-disabled='true'>{display_label}</span></li>")

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {_esc(tournament_name)} {stage_label}</title>'
        '<link rel="stylesheet" href="/assets/neo-site.css">'
        '<link rel="stylesheet" href="../../../../assets/neo.css"></head><body>'
        '<header class="neo-global-header" data-neo-global-navigation>'
        '<div class="neo-global-header__inner">'
        '<a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span>'
        '<span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span>'
        '<span class="neo-brand-legend__item">EVIDENCE</span>'
        '<span class="neo-brand-legend__item">ORACLE</span></span></a>'
        '<nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a>'
        f'<a href="/tournaments/2026/{GAME_CODE}/{stage_key}/" class="is-active" aria-current="page">대회</a>'
        '<a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a>'
        '<a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header>'
        '<main><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        '<a href="/tournaments/">대회</a>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<span>{_esc(tournament_name)}</span>'
        '<span class="breadcrumb__sep" aria-hidden="true"> &gt; </span>'
        f'<span aria-current="page">{stage_label}</span></nav>'
        f'<section class="hero" id="tournament"><div><p class="eyebrow">{stage_label} 업데이트</p>'
        f'<h1>{_esc(tournament_name)}</h1><p class="meta">{_esc(date_range)}</p>'
        f'{previous_tournament_meta_html()}</div></section>'
    )
    stage_nav = f"<nav class='stage-nav' aria-label='대회 단계' data-stage-nav><ol class='stage-nav__list'>{''.join(stage_nav_items)}</ol></nav>"
    table_section = (
        f"<section class='panel leaderboard-panel' id='{stage_key}'>"
        f"<div class='leaderboard-head'><h2>{stage_label} 결과 <small>{len(played)}명</small></h2></div>"
        "<div class='table-wrap'><table class='data leaderboard-table'><thead><tr>"
        f"<th>순위</th><th>선수</th><th>합계</th><th>{stage_label}</th>"
        "<th>NEO 경기력</th><th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div></section>"
    )
    footer = (
        '</main>'
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="/tournaments/2026/{GAME_CODE}/{stage_key}/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        '</div></footer></body></html>'
    )
    return header + stage_nav + table_section + footer
