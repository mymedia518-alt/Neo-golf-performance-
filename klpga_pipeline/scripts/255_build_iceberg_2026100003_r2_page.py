"""Build docs/tournaments/2026/2026100003/r2/index.html -- real official
R1+R2 results + the SG-adjusted, R2-conditioned FR forecast
(ICEBERG_2026100003_POST_R2_FORECAST_V1.json, scripts/254), continuing
the exact structure scripts/244 established for R1 one stage later.

CUT STATUS (operator correction, 2026-10-17): the real cut outcome
(scripts/251, from the official R3 tee sheet) and the 컷 통과확률
COLUMN are two different things, kept deliberately separate --
컷 통과확률 is the R1-end prediction (same ICEBERG_2026100003_
PRE_M4_CANDIDATE_V1.json cut_probability value scripts/244's own R1
page already shows, keyed by player_id, never recomputed here), and it
is NOT overwritten by the real outcome once the cut is known -- an
earlier version of this script did overwrite it with 100.0%/0.0% (the
real fact), which silently destroyed the preserved prediction; fixed
here. A player with no R1-end prediction available shows 데이터 부족
in that column even if they really did make the cut -- never
backfilled with 100%.

The real outcome is shown separately (operator instruction, 2026-10-17,
revised from an earlier '컷 통과' badge): a real missed-cut player
still gets the 'CUT' status badge next to their name (existing
.status-badge class, no new CSS) and a real withdrawal still gets 'WD'
-- a real cutmaker gets NO badge. Instead, a single divider row reading
"Missed cut" (existing .leaderboard-table tbody tr.cut-divider CSS,
already shipped and used by hitejinro_round_page.py -- reused as-is,
no change to that shared class so hitejinro's own pages are unaffected;
the operator asked for THIS divider's text centered, so a one-off
inline style='text-align:center' is set on this <td> only, instead of
touching the shared left-aligned class default) separates the made-cut
rows from the missed-cut rows, inserted exactly once at the real
transition point (rows_data is sorted by real score, and scripts/251's
own made_cut boundary is a
verified zero-exception split, so made-cut and missed-cut rows are
already contiguous blocks). The other four forward-looking columns
(TOP20/TOP10/TOP5/우승확률) are untouched by either correction: a real
missed-cut player still shows a real, known 0.0% there (not "—" --
they are mathematically out, same convention klpga.neo_win.
round_update_r2 already established site-wide), WD still shows "—",
and a real cutmaker still shows scripts/254's SG-adjusted forecast.

No NEO 경기력 column and no provenance paragraph, same operator
instruction scripts/244 already applies to this tournament's R1/R2/FR
pages (PRE unaffected). Mobile real-table (not cards), same
leaderboard-table--iceberg-r1 / table-wrap--iceberg-r1 classes R1
already uses -- reused here (same tournament, same CSS scope), not
redefined.
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
R2_OFFICIAL_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_R2_OFFICIAL_V1.json"
FORECAST_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_POST_R2_FORECAST_V1.json"
M4_CANDIDATE_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_PRE_M4_CANDIDATE_V1.json"
JOIN_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r2" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}
_NOWRAP = "<span style='white-space:nowrap'>데이터 부족</span>"

PUBLICATION_STATUS = "REFERENCE_ESTIMATE"


def _load(name: str) -> dict:
    return json.loads((CONTENT / f"{GAME_CODE}_{name}").read_text(encoding="utf-8"))


def _pct(x) -> str:
    return f"{x * 100:.1f}%" if isinstance(x, float) and x <= 1.0 else f"{x:.1f}%"


def main() -> None:
    join = json.loads(JOIN_PATH.read_text(encoding="utf-8"))
    tourney = _load("TOURNAMENT_INFO.json")
    join_records = {r["player_code"]: r for r in join["records"]}

    r2_official = json.loads(R2_OFFICIAL_PATH.read_text(encoding="utf-8"))
    assert r2_official["game_code"] == GAME_CODE
    r2_by_id = {r["player_id"]: r for r in r2_official["records"]}
    assert set(r2_by_id) | {"8243"} == set(join_records), "R2 + known R1-WD player_id set does not match the 108-entrant roster"

    forecast = json.loads(FORECAST_PATH.read_text(encoding="utf-8"))
    assert forecast["game_code"] == GAME_CODE
    forecast_by_id = {r["player_id"]: r for r in forecast["cutmaker_records"]}

    # R1-end 컷 통과확률 prediction -- same source/filter scripts/244's own
    # R1 page already uses for this exact column. Independent of the real
    # cut outcome: never recomputed, never overwritten by it.
    m4_candidate = json.loads(M4_CANDIDATE_PATH.read_text(encoding="utf-8"))
    cut_prob_by_id = {
        str(r["playerCode"]): r["cut_probability"]
        for r in m4_candidate.get("records", [])
        if r.get("analysis_status") == "PASS" and r.get("cut_probability") is not None
    }

    sponsor_cache = cross_tournament_verified_sponsor_cache()

    def to_par_num(tp):
        if tp in ("E", "", None):
            return 0
        try:
            return int(tp)
        except (TypeError, ValueError):
            return None

    def _sort_key(pid):
        if pid == "8243":  # known R1 WD, no R2 row at all
            return (2, 0, pid)
        r = r2_by_id[pid]
        if r["r2_status"] == "WD":
            return (1, 0, pid)
        tp = to_par_num(r["r2_to_par"])
        return (0, tp if tp is not None else 999, pid)

    rows_data = sorted(join_records.keys(), key=_sort_key)

    rank_counts: dict[int, int] = {}
    for pid, r in r2_by_id.items():
        if r["r2_status"] != "WD":
            tp = to_par_num(r["r2_to_par"])
            if tp is not None:
                rank_counts[tp] = rank_counts.get(tp, 0) + 1

    TOTAL_COLS = 11  # 순위/선수/합계/R1/R2/FR/컷통과확률/TOP20/TOP10/TOP5/우승확률
    cut_divider_inserted = False

    rows_html = []
    for pid in rows_data:
        jr = join_records[pid]
        r = r2_by_id.get(pid)
        is_known_r1_wd = r is None  # 8243, never appears past R1
        is_wd = is_known_r1_wd or r["r2_status"] == "WD"
        is_cut = (not is_wd) and (not r["made_cut"])

        # One-line divider between real cutmakers and real missed-cut
        # players -- operator instruction, 2026-10-17. rows_data is
        # sorted by real 2-round score ascending within the non-WD
        # group (scripts/251's own made_cut<=+4/>=+5 boundary, verified
        # zero exceptions), so made-cut and missed-cut rows are already
        # contiguous blocks; this fires exactly once, at the real
        # transition, never guessed or recomputed from score alone.
        if is_cut and not cut_divider_inserted:
            rows_html.append(f"<tr class='cut-divider'><td colspan='{TOTAL_COLS}' style='text-align:center'>Missed cut</td></tr>")
            cut_divider_inserted = True

        if is_wd:
            rank_cell = "WD"
            total_cell = "WD"
            r1_cell = str(r["r1_score"]) if (r and r.get("r1_score") is not None) else "-"
            r2_cell = "-"
        else:
            tp = to_par_num(r["r2_to_par"])
            rank_cell = (f"T{r['r2_rank']}" if rank_counts.get(tp, 0) > 1 else str(r["r2_rank"])) if r["r2_rank"] else "-"
            total_cell = _esc(r["r2_to_par"] or "-")
            r1_cell = str(r["r1_score"]) if r.get("r1_score") is not None else "-"
            r2_cell = str(r["r2_score"]) if r.get("r2_score") is not None else "-"

        country_code = jr["nationality"]
        flag_cell = (
            f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
            f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
            if country_code in FLAG_ASSETS else ""
        )
        sponsor_text = _esc(sponsor_cache.get(pid, ""))
        name_cell = f"<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(jr['player_name'])}</span>"
        name_cell = linked_player_name_cell(pid, name_cell)
        if is_wd:
            name_cell += "<span class='status-badge'>WD</span>"
        elif is_cut:
            name_cell += "<span class='status-badge'>CUT</span>"

        # 컷 통과확률 column: ALWAYS the R1-end prediction, independent of
        # the real outcome above -- never recomputed, never replaced by
        # 100.0%/0.0% even for a confirmed real cutmaker/missed-cut player.
        if is_wd:
            cut_cell = "—"
        elif pid in cut_prob_by_id:
            cut_cell = _pct(cut_prob_by_id[pid])
        else:
            cut_cell = _NOWRAP

        # Forward-looking columns (TOP20/TOP10/TOP5/우승확률): unchanged
        # from before -- real, known 0.0% for a real missed-cut player,
        # the SG-adjusted forecast for a real cutmaker, 데이터 부족 only
        # when that forecast genuinely could not be computed.
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
            # made_cut=True (real fact) but excluded from the forward
            # simulation (e.g. no BASE feature) -- only these four
            # genuinely-uncomputable columns show 데이터 부족.
            top20_cell = top10_cell = top5_cell = win_cell = _NOWRAP
            metric_class = "win"

        rows_html.append(
            f"<tr><td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span></th>"
            f"<td data-label='합계'>{total_cell}</td>"
            f"<td data-label='R1'>{r1_cell}</td>"
            f"<td data-label='R2'>{r2_cell}</td>"
            f"<td data-label='FR'>-</td>"
            f"<td class='{metric_class}' data-label='컷 통과확률'>{cut_cell}</td>"
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

    leader_pid = rows_data[0]
    leader_name = join_records[leader_pid]["player_name"]
    leader_to_par = r2_by_id[leader_pid]["r2_to_par"] or "-"
    seo_description = f"{event_name} 2R 공식 결과 · 선두 {leader_name} {leader_to_par} · NEO GOLF DATA 실시간 분석"
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/r2/"

    previous_meta_html = previous_tournament_meta_html()

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
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
        '<span aria-current="page">R2</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">2R 공식 결과</p>'
        f'<h1>{_esc(event_name)}</h1><p class="meta">{date_range}</p>'
        f'<p class="meta">{_esc(course_line)}</p>'
        f'{previous_meta_html}</div></section>'
    )

    fr_exists = (REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "fr" / "index.html").is_file()
    fr_item = (
        f"<li class='stage-nav__item'><a class='stage-nav__link' href='/tournaments/2026/{GAME_CODE}/fr/'>FR</a></li>"
        if fr_exists else
        "<li class='stage-nav__item'><span class='stage-nav__disabled' aria-disabled='true'>FR</span></li>"
    )

    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/">PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/">R1</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r2/" aria-current="page">R2</a></li>'
        + fr_item +
        '</ol></nav>'
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="r2">'
        '<div class="leaderboard-head"><h2>2R 공식 결과 <small>108명</small></h2></div>'
        '<div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1"><thead><tr>'
        "<th>순위</th><th>선수</th><th>합계</th><th>R1</th><th>R2</th><th>FR</th>"
        "<th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div></section>"
    )

    footer = (
        '</main>' +
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="/tournaments/2026/{GAME_CODE}/r2/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        '</div></footer></body></html>'
    )

    html = header + stage_nav + table_section + footer

    assert_no_blocked_probability_output(
        html,
        model_validated=(PUBLICATION_STATUS == "VALIDATED"),
        reference_estimate=(PUBLICATION_STATUS == "REFERENCE_ESTIMATE"),
        label=f"{GAME_CODE} R2",
    )

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")

    cutmaker_wins = [r["sg_adjusted_win_probability"] for r in forecast["cutmaker_records"]]
    monotonic_problems = []
    for r in forecast["cutmaker_records"]:
        if not (r["sg_adjusted_win_probability"] <= r["sg_adjusted_top5_probability"] <= r["sg_adjusted_top10_probability"] <= r["sg_adjusted_top20_probability"] <= 1.0 + 1e-9):
            monotonic_problems.append(r["player_id"])

    print(json.dumps({
        "written": str(OUT_PAGE),
        "rows": len(rows_data),
        "r2_leaderboard_rows": r2_official["r2_leaderboard_rows"],
        "made_cut_counts": r2_official["made_cut_counts"],
        "cut_probability_prediction_connected": len(cut_prob_by_id),
        "forecast_connected": len(forecast_by_id),
        "forecast_excluded": forecast.get("excluded_cutmakers"),
        "monotonicity_problems": monotonic_problems,
        "monotonicity_pass": len(monotonic_problems) == 0,
        "win_probability_sum": round(sum(cutmaker_wins), 4),
        "forecast_n_simulations": forecast.get("n_simulations"),
        "forecast_random_seed": forecast.get("random_seed"),
        "forecast_walk_forward_r2sg_beats_base": forecast.get("walk_forward_r2sg_beats_base"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
