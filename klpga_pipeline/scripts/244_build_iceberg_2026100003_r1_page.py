"""Build docs/tournaments/2026/2026100003/r1/index.html -- real official
R1 leaderboard + the same NEO 경기력 bands PRE already shows + the
SG-adjusted, R1-conditioned win/TOP20/TOP10/TOP5 probabilities
(ICEBERG_2026100003_POST_R1_FORECAST_SG_V1.json, built by scripts/249:
same Monte Carlo mechanics scripts/247 already shipped -- real R1 score
+ remaining rounds drawn from Normal(expected, spread) -- but the
expectation now comes from scripts/246's walk-forward-fit R1SG model
(prior_avg_round_to_par AND real official R1 Strokes Gained together),
not plain BASE alone. scripts/246's own walk-forward found R1SG does
NOT beat BASE on held-out accuracy (event wins tied 4-4 across 8
evaluated historical events, 0.0035-stroke pooled MAE difference) --
the SG-adjusted numbers are published anyway, as the operator-directed
follow-through on having collected real official R1 SG (see scripts/
249's own docstring for the full disclosure), not withheld for a weak
validation result. 컷 통과확률 stays the original frozen PRE logistic
model's own value, untouched by SG (official cut rule for this 3-round
tournament unconfirmed -- same convention hitejinro_round_page.py's own
comment documents for round-scoped models kept separate from round-
conditioning).

Structure copied verbatim from scripts/238_build_iceberg_2026100003_pre_page.py
(this project's own "self-contained per-tournament builder" convention)
-- only the leaderboard table body changes: a 순위/R1/R2/FR score
section replaces PRE's entry list, matching this tournament's own real
3-round (54-hole) shape (scripts/238's own 2026-10-16 operator-confirmed
note), not hitejinro's 4-round layout.

NEO 경기력 COLUMN DROPPED FROM R1 (operator instruction, 2026-10-16): the
column overflowed the on-screen table once the wrap fix below widened
every other cell to one line. PRE (scripts/238) is unaffected and keeps
showing NEO 경기력 -- only this tournament's R1/R2/FR stage pages drop
it (R2/FR builders don't exist yet; when they're written, copy the
table without the NEO 경기력 <th>/<td> and without the info_js block,
same as here). Other tournaments' already-published pages are untouched.

PROVENANCE PARAGRAPH REMOVED FROM R1 (operator instruction, 2026-10-16):
the hero's own internal-methodology line (워크포워드 검증/SG 보정/
시뮬레이션 횟수 등) read as developer jargon on the public page -- not
shown at all now, same scope as the NEO 경기력 removal above (R1/R2/FR
for this tournament only; PRE and other tournaments' pages untouched).

MOBILE KEPT AS A REAL TABLE, NOT CARDS (operator instruction, 2026-10-16):
table-wrap--iceberg-r1 on the wrapper div, combined with the table's own
leaderboard-table--iceberg-r1 class, opts into the same real table/row/
cell mobile display + horizontal-scroll mechanics already shipped for
HANA's pages (leaderboard-table--flat-scroll in neo.css) -- but under
its own, separately-named CSS rules so a future change to HANA's class
can never reach this page and vice versa. Same column order as desktop,
no wrapped cells, no shrunk columns; HOME mirrors this verbatim via
scripts/245. No other tournament's markup carries this class.

Source of truth:
 - 2026100003_ENTRY_KRANKING_JOIN.json (same roster/sponsor/K-ranking PRE uses)
 - the real R1 roundLeaderboard, collected via the one-off GitHub Actions
   workflow sg-recovery-oneoff.yml (same official klpga.co.kr endpoint
   scripts/63's collector uses), run_id 38894425383, raw HTML committed
   under klpga_pipeline/content/website_v2/raw_capture/2026100003_r1/.
 - klpga.neo_win.hitejinro_player_metrics.load_current_form_by_id/
   neo_band_by_id (the same generic, no-gameCode-coupling helpers 238 uses)
 - ICEBERG_2026100003_POST_R1_FORECAST_V2.json for win/TOP20/TOP10/TOP5
   (scripts/247); ICEBERG_2026100003_PRE_M4_CANDIDATE_V1.json for 컷 통과확률
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
from klpga.website_v2.previous_tournament_link import (  # noqa: E402
    previous_tournament_meta_html,
    resolve_previous_tournament_link,
)
from klpga.website_v2.official_data import parse_leaderboard_html  # noqa: E402
from klpga.neo_win.hitejinro_player_metrics import (  # noqa: E402
    load_current_form_by_id as _load_current_form_by_id,
    neo_band_by_id as _neo_band_by_id,
    pct as _pct,
)

GAME_CODE = "2026100003"
ROUND_NUMBER = 1
RAW_R1_LEADERBOARD = CONTENT / "raw_capture" / "2026100003_r1" / "roundLeaderboard_r1.html"
FORECAST_SG_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_POST_R1_FORECAST_SG_V1.json"
M4_CANDIDATE_PATH = CONTENT / f"ICEBERG_{GAME_CODE}_PRE_M4_CANDIDATE_V1.json"
JOIN_PATH = CONTENT / f"{GAME_CODE}_ENTRY_KRANKING_JOIN.json"
OUT_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / "r1" / "index.html"
FLAG_ASSETS = {p.stem for p in (REPO_ROOT / "docs" / "assets" / "flags").glob("*.svg")}
_NOWRAP = "<span style='white-space:nowrap'>데이터 부족</span>"

PUBLICATION_STATUS = "REFERENCE_ESTIMATE"  # same policy script 238 already applies to this tournament


def _load(name: str) -> dict:
    return json.loads((CONTENT / f"{GAME_CODE}_{name}").read_text(encoding="utf-8"))


def main() -> None:
    join = json.loads(JOIN_PATH.read_text(encoding="utf-8"))
    tourney = _load("TOURNAMENT_INFO.json")
    join_records = {r["player_code"]: r for r in join["records"]}

    r1_html = RAW_R1_LEADERBOARD.read_text(encoding="utf-8")
    r1_rows = parse_leaderboard_html(r1_html)
    assert len(r1_rows) == 108, f"expected 108 R1 leaderboard rows, found {len(r1_rows)}"
    r1_by_id = {r["player_id"]: r for r in r1_rows}
    assert set(r1_by_id) == set(join_records), "R1 leaderboard player_id set does not match the 108-entrant roster"

    forecast = json.loads(FORECAST_SG_PATH.read_text(encoding="utf-8"))
    assert forecast["game_code"] == GAME_CODE
    forecast_by_id = {r["player_id"]: r for r in forecast["records"]}

    m4_candidate = json.loads(M4_CANDIDATE_PATH.read_text(encoding="utf-8"))
    cut_by_id = {
        str(r["playerCode"]): r["cut_probability"]
        for r in m4_candidate.get("records", [])
        if r.get("analysis_status") == "PASS" and r.get("cut_probability") is not None
    }
    # Merged view _render uses: win/top5/top10/top20 from the SG-adjusted
    # R1-conditioned forecast (scripts/249); cut_probability from the
    # unrelated, unchanged frozen PRE model (official cut rule for this
    # 3-round tournament unconfirmed -- see scripts/249's own docstring).
    m4_by_id = {}
    for pid, rec in forecast_by_id.items():
        if pid in cut_by_id:
            m4_by_id[pid] = {
                "cut_probability": cut_by_id[pid],
                "top20_probability": rec["sg_adjusted_top20_probability"],
                "top10_probability": rec["sg_adjusted_top10_probability"],
                "top5_probability": rec["sg_adjusted_top5_probability"],
                "win_probability": rec["sg_adjusted_win_probability"],
            }

    sponsor_cache = cross_tournament_verified_sponsor_cache()
    all_ids = list(join_records.keys())
    current_form_by_id = _load_current_form_by_id(all_ids)
    neo_band_by_id = _neo_band_by_id(current_form_by_id)

    def _sort_key(pid):
        r1 = r1_by_id[pid]
        rn = r1.get("rank_numeric")
        return (0, rn, pid) if rn is not None else (1, 0, pid)

    rows_data = sorted(all_ids, key=_sort_key)

    rank_counts: dict[int, int] = {}
    for pid in all_ids:
        rn = r1_by_id[pid].get("rank_numeric")
        if rn is not None:
            rank_counts[rn] = rank_counts.get(rn, 0) + 1

    rows_html = []
    for pid in rows_data:
        jr = join_records[pid]
        r1 = r1_by_id[pid]
        is_wd = r1.get("status") == "WD"

        if is_wd:
            rank_cell = "WD"
            total_cell = "WD"
            r1_cell = "WD"
        else:
            rn = r1.get("rank_numeric")
            rank_cell = (f"T{r1['rank']}" if rank_counts.get(rn, 0) > 1 else str(r1["rank"])) if rn is not None else "-"
            to_par = r1.get("to_par") or "-"
            total_cell = _esc(to_par if to_par not in ("", None) else "-")
            r1_score = (r1.get("rounds") or [None])[0]
            r1_cell = str(r1_score) if r1_score is not None else "-"

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

        if is_wd:
            cut_cell = top20_cell = top10_cell = top5_cell = win_cell = "—"
            metric_class = "win metric-empty"
        elif pid in m4_by_id:
            m4 = m4_by_id[pid]
            cut_cell = _pct(m4["cut_probability"])
            top20_cell = _pct(m4["top20_probability"])
            top10_cell = _pct(m4["top10_probability"])
            top5_cell = _pct(m4["top5_probability"])
            win_cell = _pct(m4["win_probability"])
            metric_class = "win"
        else:
            cut_cell = top20_cell = top10_cell = top5_cell = win_cell = _NOWRAP
            metric_class = "win"

        rows_html.append(
            f"<tr><td data-label='순위'>{rank_cell}</td>"
            f"<th scope='row' style='white-space:nowrap;text-align:left'>{flag_cell}{name_cell}"
            f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span></th>"
            f"<td data-label='합계'>{total_cell}</td>"
            f"<td data-label='R1'>{r1_cell}</td>"
            f"<td data-label='R2'>-</td>"
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
    leader_r1 = r1_by_id[leader_pid]
    leader_name = join_records[leader_pid]["player_name"]
    leader_to_par = leader_r1.get("to_par") or "-"
    seo_description = f"{event_name} 1R 공식 결과 · 선두 {leader_name} {leader_to_par} · NEO GOLF DATA 실시간 분석"
    canonical_url = f"{_SITE_ORIGIN}/tournaments/2026/{GAME_CODE}/r1/"

    previous_meta_html = previous_tournament_meta_html()

    header = (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>NEO GOLF DATA · {_esc(event_name)} 1R 공식 결과</title>'
        f'<meta name="description" content="{_esc(seo_description)}">'
        f'<link rel="canonical" href="{canonical_url}">'
        f'<meta property="og:title" content="NEO GOLF DATA · {_esc(event_name)} 1R 공식 결과">'
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
        '<span aria-current="page">R1</span></nav>'
        '<section class="hero" id="tournament"><div><p class="eyebrow">1R 공식 결과</p>'
        f'<h1>{_esc(event_name)}</h1><p class="meta">{date_range}</p>'
        f'<p class="meta">{_esc(course_line)}</p>'
        f'{previous_meta_html}</div></section>'
    )

    _round_items = []
    for key, label in (("r2", "R2"), ("fr", "FR")):
        if (REPO_ROOT / "docs" / "tournaments" / "2026" / GAME_CODE / key / "index.html").is_file():
            _round_items.append(f"<li class='stage-nav__item'><a class='stage-nav__link' href='/tournaments/2026/{GAME_CODE}/{key}/'>{label}</a></li>")
        else:
            _round_items.append(f"<li class='stage-nav__item'><span class='stage-nav__disabled' aria-disabled='true'>{label}</span></li>")

    stage_nav = (
        '<nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list">'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/pre/">PRE</a></li>'
        f'<li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/{GAME_CODE}/r1/" aria-current="page">R1</a></li>'
        + "".join(_round_items) +
        '</ol></nav>'
    )

    table_section = (
        '<section class="panel leaderboard-panel" id="r1">'
        '<div class="leaderboard-head"><h2>1R 공식 결과 <small>108명</small></h2></div>'
        '<div class="table-wrap table-wrap--iceberg-r1"><table class="data leaderboard-table leaderboard-table--iceberg-r1"><thead><tr>'
        "<th>순위</th><th>선수</th><th>합계</th><th>R1</th><th>R2</th><th>FR</th>"
        "<th>컷 통과확률</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div></section>"
    )

    footer = (
        '</main>' +
        '<nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> '
        f'<a href="/tournaments/2026/{GAME_CODE}/r1/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav>'
        '<footer class="site-footer"><div class="site-footer__inner">'
        '<p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p>'
        '</div></footer></body></html>'
    )

    html = header + stage_nav + table_section + footer

    assert_no_blocked_probability_output(
        html,
        model_validated=(PUBLICATION_STATUS == "VALIDATED"),
        reference_estimate=(PUBLICATION_STATUS == "REFERENCE_ESTIMATE"),
        label=f"{GAME_CODE} R1",
    )

    OUT_PAGE.parent.mkdir(parents=True, exist_ok=True)
    OUT_PAGE.write_text(html, encoding="utf-8", newline="\n")

    wins = [m["win_probability"] for m in m4_by_id.values()]
    top5s = [m["top5_probability"] for m in m4_by_id.values()]
    top10s = [m["top10_probability"] for m in m4_by_id.values()]
    top20s = [m["top20_probability"] for m in m4_by_id.values()]
    monotonic_problems = []
    for pid, m in m4_by_id.items():
        if not (m["win_probability"] <= m["top5_probability"] <= m["top10_probability"] <= m["top20_probability"] <= 1.0 + 1e-9):
            monotonic_problems.append(pid)

    print(json.dumps({
        "written": str(OUT_PAGE),
        "rows": len(rows_data),
        "r1_leaderboard_rows": len(r1_rows),
        "wd_count": sum(1 for pid in rows_data if r1_by_id[pid].get("status") == "WD"),
        "neo_band_connected": len(neo_band_by_id),
        "m4_connected": len(m4_by_id),
        "m4_missing": len(rows_data) - len(m4_by_id),
        "monotonicity_problems": monotonic_problems,
        "monotonicity_pass": len(monotonic_problems) == 0,
        "forecast_n_simulations": forecast.get("n_simulations"),
        "forecast_random_seed": forecast.get("random_seed"),
        "forecast_walk_forward_r1sg_beats_base": forecast.get("walk_forward_r1sg_beats_base"),
        "forecast_excluded": forecast.get("excluded"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
