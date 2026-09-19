"""HANA R3 -> FINAL PIPELINE, STEP 8 (operator instruction, 2026-09-19):
build the public Round 3 results page at
docs/tournaments/2026/2026090002/r3/index.html.

MAINTAINS THE IDENTICAL LAYOUT already established for R2 (scripts/160):
same shell/hero/stage-nav/table structure, same 12-column set (순위 |
선수 | 합계 | 1R | 2R | 3R | 4R | 합계 | TOP20 | TOP10 | TOP5 | 우승),
same probability display contract (no "%", header "우승" not "우승확률").

Sourced from the real, immutable 2026090002_R3_FROZEN_EVIDENCE.json
(scripts/168, built from operator-supplied official R3 evidence) and
2026090002_POST_R4_FINAL_PREVIEW.json (scripts/170, the ALREADY-
VALIDATED/PROMOTED R1SG_R2SG model reused exactly as promoted -- no
retraining, no new coefficients, no R3 SG as a predictive feature).

POPULATION: all 64 real R3 finishers (no new cut event at R3 -- see
r3_freeze.py's own docstring) get real TOP20/TOP10/TOP5/우승 numbers
for the FINAL (post-R3, remaining_rounds=1) forecast. 3R shows the
real official raw stroke count; 4R still shows EMPTY_MARK ("—") since
Round 4 has not been played yet -- this page is a PREVIEW of the
FINAL round, not the FINAL result itself.

Raw strokes (1R/2R/3R/누적합계) are read-only, re-parsed from the same
already-ingested official raw R3 evidence scripts/168 used to build
the (untouched) R3 freeze, via the same trusted
klpga.parsers.leaderboard_parser -- never derived by PAR arithmetic,
never a second source of truth for status/rank.
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
from klpga.parsers.leaderboard_parser import parse_round_leaderboard_html  # noqa: E402

R3_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "r3" / "index.html"
assert_not_root_home(R3_PAGE, repo_root=REPO_ROOT)

RAW_HTML_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R3_LEADERBOARD_RAW_V1.html"

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
    """Same sources/merge logic as scripts/151/160's own
    _load_sponsor_by_id -- duplicated here (not imported), per this
    project's established self-contained-builder convention."""
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


def _load_raw_scores_by_id() -> dict[str, tuple[int, int, int, int]]:
    """(round1_score, round2_score, round3_score, total_strokes) per
    player_id, read-only by re-parsing the SAME already-ingested
    official raw R3 evidence scripts/168 used -- never mutates or
    rewrites 2026090002_R3_FROZEN_EVIDENCE.json."""
    html = RAW_HTML_PATH.read_text(encoding="utf-8")
    rows = parse_round_leaderboard_html(html, game_code="2026090002", round_number=3)
    return {
        r.player_code: (r.round1_score, r.round2_score, r.round3_score, r.total_strokes)
        for r in rows
        if r.round1_score is not None and r.round2_score is not None and r.round3_score is not None and r.total_strokes is not None
    }


def main() -> None:
    freeze = _load("2026090002_R3_FROZEN_EVIDENCE.json")
    forecast = _load("2026090002_POST_R4_FINAL_PREVIEW.json")
    forecast_by_id = {r["player_id"]: r for r in forecast["records"]}

    active_rows = [r for r in freeze["records"] if r["status"] == "ACTIVE"]
    assert len(active_rows) == 64, f"expected 64 R3 finisher rows, got {len(active_rows)}"
    assert len(forecast_by_id) == 64, f"expected 64 forecast records, got {len(forecast_by_id)}"
    assert set(r["player_id"] for r in active_rows) == set(forecast_by_id), "R3 freeze / FINAL preview population mismatch"

    raw_scores_by_id = _load_raw_scores_by_id()
    missing_raw = [r["player_id"] for r in active_rows if r["player_id"] not in raw_scores_by_id]
    if missing_raw:
        raise RuntimeError(f"REFUSING: {len(missing_raw)} player(s) have no real raw R1/R2/R3 stroke evidence: {missing_raw}")
    for r in active_rows:
        r1_raw, r2_raw, r3_raw, total_raw = raw_scores_by_id[r["player_id"]]
        if r1_raw + r2_raw + r3_raw != total_raw:
            raise RuntimeError(f"REFUSING: raw score arithmetic mismatch for {r['player_name']}: {r1_raw}+{r2_raw}+{r3_raw}!={total_raw}")
        if r["r3_total_under_par"] is not None and (total_raw - 216) != r["r3_total_under_par"]:
            raise RuntimeError(
                f"REFUSING: raw total {total_raw} (par 216) disagrees with frozen r3_total_under_par "
                f"{r['r3_total_under_par']} for {r['player_name']}"
            )

    country_by_id = _load_country_by_id()
    sponsor_by_id = _load_sponsor_by_id()

    def _sort_key(r):
        return (r["r3_total_under_par"] is None, r["r3_total_under_par"], int(r["player_id"]))

    rank_counts: dict[int, int] = {}
    for r in active_rows:
        if r["r3_total_under_par"] is not None:
            rank_counts[r["r3_total_under_par"]] = rank_counts.get(r["r3_total_under_par"], 0) + 1

    sorted_rows = sorted(active_rows, key=_sort_key)
    ranks: dict[str, str] = {}
    current_rank = 0
    prev_total = object()
    for i, r in enumerate(sorted_rows):
        total_key = r["r3_total_under_par"]
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
        total_key = r["r3_total_under_par"]
        rank_cell = ranks[pid]
        player_cell = _player_cell(pid, r["player_name"], country_by_id, sponsor_by_id)

        total_display = format_to_par(total_key) if total_key is not None else EMPTY_MARK
        if total_display != EMPTY_MARK:
            assert_cumulative_score_is_relative_to_par(total_display, label="합계", player=r["player_name"])

        r1_raw, r2_raw, r3_raw, total_raw = raw_scores_by_id[pid]
        r1_display = str(r1_raw)
        r2_display = str(r2_raw)
        r3_display = str(r3_raw)
        total_raw_display = str(total_raw)

        frow = forecast_by_id.get(pid)
        top20 = format_public_probability(frow["top20_pct"]).rstrip("%")
        top10 = format_public_probability(frow["top10_pct"]).rstrip("%")
        top5 = format_public_probability(frow["top5_pct"]).rstrip("%")
        win = format_public_probability(frow["win_pct"]).rstrip("%")

        rows_html.append(
            f"<tr><td data-label='순위'>{_esc(rank_cell)}</td>"
            f"<th scope='row' data-label='선수' style='white-space:nowrap;text-align:left'>{player_cell}</th>"
            f"<td data-label='합계'>{_esc(total_display)}</td>"
            f"<td data-label='1R'>{_esc(r1_display)}</td>"
            f"<td data-label='2R'>{_esc(r2_display)}</td>"
            f"<td data-label='3R'>{_esc(r3_display)}</td>"
            f"<td data-label='4R'>{EMPTY_MARK}</td>"
            f"<td data-label='합계'>{_esc(total_raw_display)}</td>"
            f"<td class='win' data-label='TOP20'>{_esc(top20)}</td>"
            f"<td class='win' data-label='TOP10'>{_esc(top10)}</td>"
            f"<td class='win' data-label='TOP5'>{_esc(top5)}</td>"
            f"<td class='win' data-label='우승'>{_esc(win)}</td>"
            f"</tr>"
        )

    final_rows = rows_html

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEO GOLF DATA · {TOURNAMENT_NAME}</title><link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="../../../../assets/neo.css"></head><body><header class="neo-global-header" data-neo-global-navigation><div class="neo-global-header__inner"><a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span><span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span><span class="neo-brand-legend__item">EVIDENCE</span><span class="neo-brand-legend__item">ORACLE</span></span></a><nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a><a href="/tournaments/2026/2026090002/r3/" class="is-active" aria-current="page">대회</a><a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a><a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header><main><style>@media(max-width:760px){{.hana-tourinfo-sep{{display:none}}.hana-tourinfo-holes{{display:block}}}}
.leaderboard-table.leaderboard-table--flat-scroll tbody td:nth-child(n+3):nth-child(-n+8){{text-align:center}}
@media(max-width:760px){{
.leaderboard-table.leaderboard-table--flat-scroll thead th:nth-child(n+3):nth-child(-n+8),
.leaderboard-table.leaderboard-table--flat-scroll tbody td:nth-child(n+3):nth-child(-n+8){{padding-left:6px;padding-right:6px;text-align:center}}
}}
</style><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><a href="/tournaments/">대회</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span>{TOURNAMENT_NAME}</span><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span aria-current="page">R3</span></nav><section class="hero" id="tournament"><div><p class="eyebrow">R3 결과</p><h1>{TOURNAMENT_NAME}</h1><p class="meta">{TOURNAMENT_DATE_META}</p><p class="meta">{TOURNAMENT_WINNER_META}</p><p class="meta">{TOURNAMENT_VENUE_META}<span class="hana-tourinfo-sep"> · </span><span class="hana-tourinfo-holes">72홀 스트로크 플레이</span></p></div><p class="round-update-note">FINAL 종료 후 업데이트</p></section><nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list"><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/pre/">사전 분석 PRE</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r1/">R1</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r2/">R2</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r3/" aria-current="page">R3</a></li><li class="stage-nav__item"><span class="stage-nav__disabled" aria-disabled="true">FR</span></li></ol></nav><section class="panel leaderboard-panel" id="r3"><div class="leaderboard-head"><h2>R3 결과 <small>{len(active_rows)}명</small></h2></div><div class="table-wrap table-wrap--flat-scroll"><table class="data leaderboard-table leaderboard-table--flat-scroll"><thead><tr><th>순위</th><th>선수</th><th>합계</th><th>1R</th><th>2R</th><th>3R</th><th>4R</th><th>합계</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승</th></tr></thead><tbody>{''.join(final_rows)}</tbody></table></div></section></main><nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> <a href="/tournaments/2026/2026090002/r3/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav><footer class="site-footer"><div class="site-footer__inner"><p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body></html>"""

    assert_not_root_home(R3_PAGE, repo_root=REPO_ROOT)
    R3_PAGE.parent.mkdir(parents=True, exist_ok=True)
    R3_PAGE.write_text(html, encoding="utf-8")
    print("wrote", R3_PAGE)
    print("rows:", len(final_rows), "all with probability (no cut event at R3)")


if __name__ == "__main__":
    main()
