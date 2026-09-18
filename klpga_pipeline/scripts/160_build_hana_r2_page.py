"""HANA R2 -- build the public Round 2 results page at
docs/tournaments/2026/2026090002/r2/index.html.

Sourced from the real, immutable 2026090002_R2_FROZEN_EVIDENCE.json
(scripts/158) and 2026090002_POST_R2_FINAL_FORECAST.json (scripts/159,
built via klpga.neo_win.post_r2_forecast.run_post_r2_forecast -- the
same generic production Monte Carlo engine KB uses, n_simulations=
60000, remaining_rounds=2, real R1+R2 scores).

POPULATION (operator's explicit R2 requirement -- deliberately
DIFFERENT from KB's own r2_real_page.py convention, which excludes
CUT rows from its table entirely): every real-score R2 leaderboard row
(102 -- both cut-survivors AND cut-missed) is shown in the score table.
WD (3, real: 최예본/리 슈잉/박혜준) are excluded entirely. Only the 64
official cut-survivors (status=="ACTIVE" in the freeze, the same
population run_post_r2_forecast itself simulated) get real TOP20/TOP10/
TOP5/우승확률 numbers; the 38 cut-missed rows show "—" in those four
cells -- never a fabricated 0%.

Markup/CSS classes/shared helpers are the same ones scripts/151 (Hana
R1) already established and klpga.website_v2.round_page_contract /
probability_format already validate elsewhere -- no new template
system, no new CSS.
"""
from __future__ import annotations

import json
import sys
from html import escape as _esc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
REPO_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))

from klpga.website_v2.round_score_format import format_to_par  # noqa: E402
from klpga.website_v2.round_page_contract import assert_cumulative_score_is_relative_to_par  # noqa: E402
from klpga.website_v2.home_ownership_guard import assert_not_root_home  # noqa: E402
from klpga.website_v2.probability_format import format_public_probability  # noqa: E402

R2_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r2" / "index.html"
assert_not_root_home(R2_PAGE, repo_root=REPO_ROOT)

TOURNAMENT_NAME = "하나금융그룹 챔피언십"
TOURNAMENT_DATE_META = "2026.09.17 — 09.20"
TOURNAMENT_WINNER_META = "2025 우승 이다연 · 279타(-9)"
TOURNAMENT_VENUE_META = "더헤븐 · West, South · Par 72"
EMPTY_MARK = "—"


def _load(name: str) -> dict:
    return json.loads((CONTENT / name).read_text(encoding="utf-8"))


def _load_country_by_id() -> dict[str, str]:
    match = _load("HANA_2026090002_ENTRY_FLAG_MATCH_V2.json")
    country_by_id = {r["player_id"]: r["country_code"] for r in match["records"]}
    for r in _load("HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json")["records"]:
        pid = r["player_id"]
        if pid not in country_by_id:
            country_by_id[pid] = r["country_code"]
    return country_by_id


def _load_sponsor_by_id() -> dict[str, str]:
    """Same sources/merge logic as scripts/151's own _load_sponsor_by_id
    -- duplicated here (not imported), per this project's established
    self-contained-builder convention (each tournament-page builder
    stays independent, see docs/OPERATING_RULES.md rule 4)."""
    sources: list[tuple[str, str, str, set[str]]] = [
        ("KB_2026090003_SPONSOR_INTEGRITY_AUDIT_V3.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("HOME_TOP120_SPONSOR_INTEGRITY_AUDIT_V2.json", "newly_recovered_sponsors", "status", {"VERIFIED_OFFICIAL"}),
        ("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V2.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_OPERATOR_REPORTED"}),
        ("OPERATOR_REPORTED_SPONSOR_EVIDENCE_V3.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_OPERATOR_REPORTED"}),
        ("HANA_2026090002_R1_NEW_ENTRANT_IDENTITY_EVIDENCE_V1.json", "records", "evidence_status", {"VERIFIED_OFFICIAL_R1_LEADERBOARD"}),
    ]
    sponsor_by_id: dict[str, str] = {}
    for filename, list_key, status_key, allowed in sources:
        path = CONTENT / filename
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for r in data[list_key]:
            if r.get(status_key) not in allowed:
                continue
            sponsor = r.get("sponsor")
            if not sponsor:
                continue
            pid = str(r["player_id"])
            existing = sponsor_by_id.get(pid)
            if existing is not None and existing != sponsor:
                continue
            sponsor_by_id[pid] = sponsor
    return sponsor_by_id


def _player_cell(pid: str, name: str, country_by_id: dict[str, str], sponsor_by_id: dict[str, str]) -> str:
    flag_cell = ""
    country_code = country_by_id.get(pid)
    if country_code:
        flag_cell = (
            f"<img src='/assets/flags/{country_code}.svg' alt='' width='16' height='12' "
            f"style='display:inline-block;vertical-align:middle;margin-right:4px'>"
        )
    sponsor = sponsor_by_id.get(pid)
    sponsor_text = _esc(sponsor) if sponsor else ""
    sponsor_cell = f"<span class='player-sponsor' style='display:inline;vertical-align:middle;margin-left:6px'>{sponsor_text}</span>"
    return (
        f"{flag_cell}<span class='player-name' style='display:inline;vertical-align:middle'>{_esc(name)}</span>"
        f"{sponsor_cell}"
    )


def main() -> None:
    freeze = _load("2026090002_R2_FROZEN_EVIDENCE.json")
    forecast = _load("2026090002_POST_R2_FINAL_FORECAST.json")
    forecast_by_id = {r["player_id"]: r for r in forecast["records"]}

    all_records = freeze["records"]
    score_rows = [r for r in all_records if r["status"] != "WD"]
    assert len(score_rows) == 102, f"expected 102 non-WD R2 score rows, got {len(score_rows)}"
    active_rows = [r for r in score_rows if r["status"] == "ACTIVE"]
    assert len(active_rows) == 64, f"expected 64 cut-survivor rows, got {len(active_rows)}"
    assert len(forecast_by_id) == 64, f"expected 64 forecast records, got {len(forecast_by_id)}"

    country_by_id = _load_country_by_id()
    sponsor_by_id = _load_sponsor_by_id()

    def _sort_key(r):
        return (r["r2_total_under_par"] is None, r["r2_total_under_par"], int(r["player_id"]))

    rank_counts: dict[int, int] = {}
    for r in score_rows:
        if r["r2_total_under_par"] is not None:
            rank_counts[r["r2_total_under_par"]] = rank_counts.get(r["r2_total_under_par"], 0) + 1

    sorted_rows = sorted(score_rows, key=_sort_key)
    ranks: dict[str, str] = {}
    current_rank = 0
    prev_total = object()
    for i, r in enumerate(sorted_rows):
        total_key = r["r2_total_under_par"]
        if total_key is None:
            ranks[r["player_id"]] = "—"
            continue
        if total_key != prev_total:
            current_rank = i + 1
            prev_total = total_key
        ranks[r["player_id"]] = f"T{current_rank}" if rank_counts.get(total_key, 0) > 1 else str(current_rank)

    rows_html = []
    for r in sorted_rows:
        pid = r["player_id"]
        is_active = r["status"] == "ACTIVE"
        total_key = r["r2_total_under_par"]
        rank_cell = ranks[pid]
        player_cell = _player_cell(pid, r["player_name"], country_by_id, sponsor_by_id)

        r1_display = format_to_par(r["r1_score_to_par"]) if r["r1_score_to_par"] is not None else EMPTY_MARK
        r2_display = format_to_par(r["r2_score_to_par"]) if r["r2_score_to_par"] is not None else EMPTY_MARK
        total_display = format_to_par(total_key) if total_key is not None else EMPTY_MARK
        if total_display != EMPTY_MARK:
            assert_cumulative_score_is_relative_to_par(total_display, label="합계", player=r["player_name"])

        status_badge = "" if is_active else "<span class='r2-cut-badge' style='margin-left:6px;font-size:.75em;color:#8a8f98'>CUT</span>"

        frow = forecast_by_id.get(pid)
        if is_active and frow is not None:
            top20 = format_public_probability(frow["top20_pct"])
            top10 = format_public_probability(frow["top10_pct"])
            top5 = format_public_probability(frow["top5_pct"])
            win = format_public_probability(frow["win_pct"])
        else:
            top20 = top10 = top5 = win = EMPTY_MARK

        rows_html.append(
            f"<tr><td data-label='순위'>{_esc(rank_cell)}</td>"
            f"<th scope='row' data-label='선수' style='white-space:nowrap;text-align:left'>{player_cell}{status_badge}</th>"
            f"<td data-label='1R'>{_esc(r1_display)}</td>"
            f"<td data-label='2R'>{_esc(r2_display)}</td>"
            f"<td data-label='합계'>{_esc(total_display)}</td>"
            f"<td class='{'win' if top20 != EMPTY_MARK else 'metric-empty'}' data-label='TOP20'>{_esc(top20)}</td>"
            f"<td class='{'win' if top10 != EMPTY_MARK else 'metric-empty'}' data-label='TOP10'>{_esc(top10)}</td>"
            f"<td class='{'win' if top5 != EMPTY_MARK else 'metric-empty'}' data-label='TOP5'>{_esc(top5)}</td>"
            f"<td class='{'win' if win != EMPTY_MARK else 'metric-empty'}' data-label='우승확률'>{_esc(win)}</td>"
            f"</tr>"
        )

    final_rows = rows_html

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEO GOLF DATA · {TOURNAMENT_NAME}</title><link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="../../../../assets/neo.css"></head><body><header class="neo-global-header" data-neo-global-navigation><div class="neo-global-header__inner"><a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span><span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span><span class="neo-brand-legend__item">EVIDENCE</span><span class="neo-brand-legend__item">ORACLE</span></span></a><nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a><a href="/tournaments/2026/2026090002/r2/" class="is-active" aria-current="page">대회</a><a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a><a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header><main><style>@media(max-width:760px){{.hana-tourinfo-sep{{display:none}}.hana-tourinfo-holes{{display:block}}}}</style><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><a href="/tournaments/">대회</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span>{TOURNAMENT_NAME}</span><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span aria-current="page">R2</span></nav><section class="hero" id="tournament"><div><p class="eyebrow">R2 결과</p><h1>{TOURNAMENT_NAME}</h1><p class="meta">{TOURNAMENT_DATE_META}</p><p class="meta">{TOURNAMENT_WINNER_META}</p><p class="meta">{TOURNAMENT_VENUE_META}<span class="hana-tourinfo-sep"> · </span><span class="hana-tourinfo-holes">72홀 스트로크 플레이</span></p><p class="meta">공식 컷: +6 (150타) · 컷 통과 64명</p></div><p class="round-update-note">R3 종료 후 업데이트</p></section><nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list"><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/pre/">사전 분석 PRE</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r1/">R1</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r2/" aria-current="page">R2</a></li><li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">R3</span></li><li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FR</span></li></ol></nav><section class="panel leaderboard-panel" id="r2"><div class="leaderboard-head"><h2>R2 결과 <small>102명</small></h2><p class="leaderboard-note">TOP20/TOP10/TOP5/우승확률은 공식 컷(+6/150타) 통과자 64명에게만 표시됩니다. 컷 탈락자는 스코어만 표시되며 확률란은 —로 표시합니다.</p></div><div class="table-wrap table-wrap--flat-scroll"><table class="data leaderboard-table leaderboard-table--flat-scroll leaderboard-table--r2-full"><thead><tr><th>순위</th><th>선수</th><th>1R</th><th>2R</th><th>합계</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th></tr></thead><tbody>{''.join(final_rows)}</tbody></table></div></section></main><nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> <a href="/tournaments/2026/2026090002/r2/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav><footer class="site-footer"><div class="site-footer__inner"><p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body></html>"""

    assert_not_root_home(R2_PAGE, repo_root=REPO_ROOT)
    R2_PAGE.parent.mkdir(parents=True, exist_ok=True)
    R2_PAGE.write_text(html, encoding="utf-8")
    print("wrote", R2_PAGE)
    print("rows:", len(final_rows), "active(with probability):", len(active_rows), "cut(no probability):", len(score_rows) - len(active_rows))


if __name__ == "__main__":
    main()
