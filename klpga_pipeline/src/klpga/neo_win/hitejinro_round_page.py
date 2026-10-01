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
real rank/player identity/round scores, plus the SAME real NEO 경기력
band and M4 probabilities (컷 통과율/TOP20/TOP10/TOP5/우승확률) PRE
already shows for the identical player -- both now read through
klpga.neo_win.hitejinro_player_metrics, the one shared source for
both (2026-10-01 fix: this module used to hardcode 데이터 부족 for
every row here unconditionally, even once the warehouse and M4 model
were both real and PRE was already displaying them for the same 107
players -- there was never a reason a round page should know less
than PRE about a player who has already played). A player absent from
either source (current_form incomplete, or M4 marks them
DATA_INSUFFICIENT/missing) still renders 데이터 부족 for that one
column, per-player, never a whole-field fallback.

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

from klpga.neo_win.hitejinro_player_metrics import (
    load_current_form_by_id,
    load_m4_by_id,
    neo_band_by_id,
    pct,
)
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


def render_round_page(
    round_number: int, *, tournament_name: str, date_range: str, content_root: Path,
    in_progress: dict[str, dict] | None = None, show_hole_progress: bool = True,
) -> str:
    """in_progress (optional): {player_id: {"excluded", "status_text",
    "score", "hole"}} from klpga.neo_win.hitejinro_round_pipeline.
    parse_in_progress_state() -- an "R2 START"-type render for a round
    that has not yet produced a single real completed score. When
    given, the roster/ranking/total this renders is round_number-1's
    already-completed field (its own real finish_position, "R1 종료
    기준 그대로 사용" -- round_number itself has no real standings of
    its own yet to re-sort by), and round_number's own column shows
    ONLY in_progress's real per-player state: excluded players' real
    status text (WD/CUT/...), a real completed score once a player
    finishes, a real in-progress hole number ("{hole}H") once
    show_hole_progress is True AND that player has genuinely started,
    or "-" for anyone not yet confirmed started -- never a fabricated
    score or a guessed "진행 중"/"대기" label.

    show_hole_progress (operator call, 2026-10-01): the hole-number
    display is correct and ready whenever a capture genuinely shows
    per-player in-course progress, but the operator judged the FIRST
    such capture too close to this round's own start to treat as the
    real signal to switch on -- so this build keeps every still-active
    player's cell at "-" regardless of a real `hole` value, while a
    real completed `score` (rule 6's other, later case) still renders
    immediately, automatically, the moment one appears in any future
    capture -- no code change needed for that. Passing True (the
    default, used by every other round/caller) switches hole-number
    display back on."""
    if round_number not in STAGE_LABELS:
        raise ValueError(f"round_number must be 1-4, got {round_number}")
    stage_key, stage_label = STAGE_LABELS[round_number]
    # R1's own page keeps its already-shipped "R1" column label
    # unchanged (out of scope here); from R2 on, the column sits
    # alongside "1R"/"2R"/... prior-round columns and uses that same
    # "{N}R" suffix style for visual consistency, per explicit
    # operator instruction -- stage_label itself (used in the hero/
    # title/breadcrumb/stage-nav) is untouched.
    round_col_label = stage_label if round_number == 1 else f"{round_number}R"

    board = load_leaderboard(content_root)
    records = board["records"]
    if in_progress is not None:
        score_field = f"r{round_number - 1}_score"
    else:
        score_field = f"r{round_number}_score"
    played = [r for r in records if r.get(score_field) is not None or r.get("withdrawn") or r.get("disqualified")]
    if not played:
        raise FileNotFoundError(
            f"LEADERBOARD.json exists but no row has a real {score_field} yet -- round {round_number} "
            "has not actually been played/collected. Never renders a round page with zero real scores."
        )
    played.sort(key=lambda r: (r.get("finish_position_numeric") is None, r.get("finish_position_numeric", 10**9)))

    rank_counts: dict[int, int] = {}
    for r in played:
        n = r.get("finish_position_numeric")
        if n is not None:
            rank_counts[n] = rank_counts.get(n, 0) + 1

    if in_progress is not None:
        # Operator rule (2026-10-01): a player already excluded before
        # this round starts (real WD/CUT/... per in_progress) is not
        # part of this round's field -- drop the row entirely instead
        # of listing it with a status cell. Applied only AFTER
        # rank_counts so every remaining player's previous-round rank
        # (incl. a "T" tie shared with an excluded player) is unchanged.
        played = [r for r in played if not (in_progress.get(str(r["player_id"])) or {}).get("excluded")]

    nationality_by_id = _load_nationality_by_id(content_root)
    sponsor_cache = cross_tournament_verified_sponsor_cache()

    all_ids = [str(r["player_id"]) for r in played]
    current_form_by_id = load_current_form_by_id(all_ids)
    band_by_id = neo_band_by_id(current_form_by_id)
    m4_by_id = load_m4_by_id()

    rows_html = []
    for r in played:
        pid = str(r["player_id"])
        status = "WD" if r.get("withdrawn") else "DQ" if r.get("disqualified") else None
        finish_position_numeric = r.get("finish_position_numeric")
        if r.get("finish_position") is None:
            rank_cell = "-"
        elif rank_counts.get(finish_position_numeric, 0) > 1:
            # 2+ players share this rank -- "T{rank}" (tied), matching
            # klpga.co.kr's own real convention (confirmed against
            # Hana's already-published PRE/R1/R2 pages, which all use
            # this same "T" prefix, never a bare number for a shared rank).
            rank_cell = _esc(f"T{r['finish_position']}")
        else:
            rank_cell = _esc(str(r["finish_position"]))
        if in_progress is not None:
            # round_number has no real score of its own yet -- show
            # ONLY what in_progress's real per-player state carries,
            # never fall back to score_field (that's the PREVIOUS
            # round's own completed score, not this one's).
            live = in_progress.get(pid)
            if live is None:
                score_cell = "-"
            elif live["excluded"]:
                score_cell = _esc(live["status_text"] or "제외")
            elif live["score"] is not None:
                score_cell = str(live["score"])
            elif live["hole"] is not None and show_hole_progress:
                score_cell = f"{live['hole']}H"
            else:
                score_cell = "-"
        else:
            # r{N}_score is the raw stroke count for that round (e.g. 68),
            # never a to-par differential -- format_to_par is only for an
            # already-relative-to-par value (score_to_par below). Running a
            # raw score through format_to_par would print "+68", which is
            # not what that field means.
            score_cell = status or (str(r[score_field]) if r.get(score_field) is not None else "-")
        total_cell = status or (format_to_par(r["score_to_par"]) if r.get("score_to_par") is not None else "-")
        prior_round_cells = [
            f"<td data-label='{k}R'>{status or (str(r[f'r{k}_score']) if r.get(f'r{k}_score') is not None else '-')}</td>"
            for k in range(1, round_number)
        ]
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

        if round_number == 1 and pid in band_by_id:
            label, score = band_by_id[pid]
            band_cell = (
                f"<span class='band' role='img' aria-label='NEO 경기력 {label}' "
                f"data-neo-score='{score:.2f}'>{label}</span>"
            )
        else:
            band_cell = _NOWRAP

        if pid in m4_by_id:
            m4 = m4_by_id[pid]
            cut_cell = pct(m4["cut_probability"])
            top20_cell = pct(m4["top20_probability"])
            top10_cell = pct(m4["top10_probability"])
            top5_cell = pct(m4["top5_probability"])
            win_cell = pct(m4["win_probability"])
        else:
            cut_cell = top20_cell = top10_cell = top5_cell = win_cell = _NOWRAP

        band_td = f"<td data-label='NEO 경기력'>{band_cell}</td>" if round_number == 1 else ""
        rows_html.append(
            f"<tr><td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{name_cell}</th>"
            f"<td data-label='합계'>{total_cell}</td>"
            + "".join(prior_round_cells) +
            f"<td data-label='{round_col_label}'>{score_cell}</td>"
            f"{band_td}"
            f"<td class='win' data-label='컷 통과확률'>{cut_cell}</td>"
            f"<td class='win' data-label='TOP20'>{top20_cell}</td>"
            f"<td class='win' data-label='TOP10'>{top10_cell}</td>"
            f"<td class='win' data-label='TOP5'>{top5_cell}</td>"
            f"<td class='win' data-label='우승확률'>{win_cell}</td></tr>"
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
        f"<th>순위</th><th>선수</th><th>합계</th>"
        + "".join(f"<th>{k}R</th>" for k in range(1, round_number))
        + f"<th>{round_col_label}</th>"
        + ("<th>NEO 경기력</th>" if round_number == 1 else "")
        + "<th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>"
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
