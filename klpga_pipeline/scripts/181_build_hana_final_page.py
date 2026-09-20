"""HANA FINAL -- build the public FINAL results page at
docs/tournaments/2026/2026090002/final/index.html.

MAINTAINS THE IDENTICAL LEADERBOARD LAYOUT already established for R3
(scripts/174): same shell/hero/stage-nav/table structure, same
12-column set (순위 | 선수 | 합계 | 1R | 2R | 3R | 4R | 합계 | TOP20 |
TOP10 | TOP5 | 우승), same probability display contract -- TOP20/TOP10/
TOP5/우승 show the frozen PRE-FINAL (post-R3) forecast, exactly as it
stood before Round 4 was played, now that the real 4R strokes are
available for comparison. Per round_page_contract.py's own
PUBLIC_ROUND_PAGE_001 ("raw cumulative totals belong on FINAL"), the
FINAL page shows BOTH the to-par 합계 (via format_to_par) and the raw
stroke-total 합계, exactly like R3 already does.

Below the leaderboard, a single plain-language public summary is
rendered via klpga.neo_win.final_real_page.render_final_public_summary
(2026-09-20 operator principle: "검증은 깊게, 화면은 쉽게" -- deep
internal validation, an easy public screen). No Brier/Log Loss/Rank
MAE/Reciprocal Rank, no proxy/methodology language, no Precision/
Recall terms, no Top20 (this FINAL has an official 8-way tie at rank
20 that makes any simple public phrasing either misleading or as
convoluted as the internal report -- dropped from the public page per
the operator's own instruction), no biggest-movers (an internal,
rank_delta-based diagnostic with no honest plain-language public
form). ALL of that validation detail remains fully computed and
recorded, unchanged, in final_validator.run_final_validation /
final_report.build_final_report -- this script only decides what the
public page displays, never deletes or waters down what gets computed.

Sourced from:
  - 2026090002_FINAL_TRUTH.json (scripts/178, write-once official
    FINAL result, 64 players, parsed from the real official 4R
    leaderboard capture)
  - 2026090002_POST_R4_FINAL_PREVIEW.json (the frozen, untouched
    PRE-FINAL forecast -- read-only, same file R3's page already
    displays)
  - klpga.neo_win.final_validator.run_final_validation (generic
    forecast-vs-truth scorer, joins strictly by player_id) for Brier/
    log loss/rank MAE/reciprocal rank/biggest surprises
  - a tie-aware Top5/Top10/Top20 precision-recall computation against
    NEO's own probability-ranked candidates vs FinalTruth's topN_actual
    flags (Top20's ACTUAL population is 27, not 20, due to an official
    tie at rank 20 -- reported explicitly, never silently truncated)
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
from klpga.tournament_context import load_tournament_context  # noqa: E402
from klpga.neo_win import final_validator  # noqa: E402
from klpga.neo_win.final_truth import load_final_truth  # noqa: E402
from klpga.neo_win.final_real_page import render_final_hero_forecast_line, render_final_public_summary  # noqa: E402

FINAL_PAGE = REPO_ROOT / "docs" / "tournaments" / "2026" / "2026090002" / "final" / "index.html"
assert_not_root_home(FINAL_PAGE, repo_root=REPO_ROOT)

RAW_HTML_PATH = CONTENT / "incoming_evidence" / "2026090002" / "HANA_2026090002_R4_LEADERBOARD_RAW_V1.html"

TOURNAMENT_NAME = "하나금융그룹 챔피언십"
TOURNAMENT_DATE_META = "2026.09.17 — 09.20"
TOURNAMENT_VENUE_META = "더헤븐 · West, South · Par 72"
EMPTY_MARK = "—"
SCOPE_LABEL = "FINAL 공식 결과 전체 64명 기준"


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
    """Same sources/merge logic as scripts/151/160/174's own
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


def _load_raw_scores_by_id() -> dict:
    html = RAW_HTML_PATH.read_text(encoding="utf-8")
    rows = parse_round_leaderboard_html(html, game_code="2026090002", round_number=4)
    return {r.player_code: r for r in rows}


def _probability_rank_key(item) -> tuple:
    """Same deterministic ordering as scripts/180's neo_final_rank
    derivation (win_pct desc, then top10_pct/top5_pct/top20_pct desc,
    then player_id asc) -- kept identical so this page's Top-k stats
    never disagree with final_validator's own rank_mae/surprise
    computation over the same probability-ranked candidate order."""
    pid, r = item
    return (-r["win_pct"], -r["top10_pct"], -r["top5_pct"], -r["top20_pct"], int(pid))


def _topk_stats(forecast_by_id: dict, truth_by_id: dict) -> dict:
    ordered = sorted(forecast_by_id.items(), key=_probability_rank_key)
    stats = {}
    for k, field in ((5, "top5_actual"), (10, "top10_actual"), (20, "top20_actual")):
        predicted_ids = {pid for pid, _ in ordered[:k]}
        actual_ids = {pid for pid, r in truth_by_id.items() if r.get(field) is True}
        hits = predicted_ids & actual_ids
        precision = len(hits) / len(predicted_ids) if predicted_ids else 0.0
        recall = len(hits) / len(actual_ids) if actual_ids else 0.0
        stats[k] = {
            "precision": precision, "recall": recall, "hit_count": len(hits),
            "predicted_population": len(predicted_ids), "actual_population": len(actual_ids),
        }
    return stats


def main() -> None:
    context = load_tournament_context("2026090002")
    truth = load_final_truth(context)
    forecast = _load("2026090002_POST_R4_FINAL_PREVIEW.json")
    forecast_by_id = {r["player_id"]: r for r in forecast["records"]}
    truth_by_id = {r["player_id"]: r for r in truth["records"]}

    assert len(truth["records"]) == 64, f"expected 64 FINAL truth records, got {len(truth['records'])}"
    assert set(forecast_by_id) == set(truth_by_id), "forecast / FINAL truth population mismatch"

    raw_by_id = _load_raw_scores_by_id()
    country_by_id = _load_country_by_id()
    sponsor_by_id = _load_sponsor_by_id()

    # ---------------- Leaderboard rows: 63 ACTIVE by rank, then WD ----------------
    active = [r for r in truth["records"] if r["status"] == "ACTIVE"]
    wd = [r for r in truth["records"] if r["status"] != "ACTIVE"]
    active_sorted = sorted(active, key=lambda r: (r["final_rank"], int(r["player_id"])))

    rank_counts: dict[int, int] = {}
    for r in active:
        rank_counts[r["final_rank"]] = rank_counts.get(r["final_rank"], 0) + 1

    rows_html = []
    for r in active_sorted:
        pid = r["player_id"]
        raw = raw_by_id[pid]
        rank_display = f"T{r['final_rank']}" if rank_counts.get(r["final_rank"], 0) > 1 else str(r["final_rank"])
        player_cell = _player_cell(pid, r["player_name"], country_by_id, sponsor_by_id)

        total_display = format_to_par(raw.total_under_par)
        assert_cumulative_score_is_relative_to_par(total_display, label="합계", player=r["player_name"])

        frow = forecast_by_id[pid]
        top20 = format_public_probability(frow["top20_pct"]).rstrip("%")
        top10 = format_public_probability(frow["top10_pct"]).rstrip("%")
        top5 = format_public_probability(frow["top5_pct"]).rstrip("%")
        win = format_public_probability(frow["win_pct"]).rstrip("%")

        rows_html.append(
            f"<tr><td data-label='순위'>{_esc(rank_display)}</td>"
            f"<th scope='row' data-label='선수' style='white-space:nowrap;text-align:left'>{player_cell}</th>"
            f"<td data-label='합계'>{_esc(total_display)}</td>"
            f"<td data-label='1R'>{raw.round1_score}</td>"
            f"<td data-label='2R'>{raw.round2_score}</td>"
            f"<td data-label='3R'>{raw.round3_score}</td>"
            f"<td data-label='4R'>{raw.round4_score}</td>"
            f"<td data-label='합계'>{raw.total_strokes}</td>"
            f"<td class='win' data-label='TOP20'>{_esc(top20)}</td>"
            f"<td class='win' data-label='TOP10'>{_esc(top10)}</td>"
            f"<td class='win' data-label='TOP5'>{_esc(top5)}</td>"
            f"<td class='win' data-label='우승'>{_esc(win)}</td>"
            f"</tr>"
        )

    for r in wd:
        pid = r["player_id"]
        raw = raw_by_id[pid]
        player_cell = _player_cell(pid, r["player_name"], country_by_id, sponsor_by_id)
        rows_html.append(
            f"<tr><td data-label='순위'>WD</td>"
            f"<th scope='row' data-label='선수' style='white-space:nowrap;text-align:left'>{player_cell}</th>"
            f"<td data-label='합계'>{EMPTY_MARK}</td>"
            f"<td data-label='1R'>{raw.round1_score if raw.round1_score is not None else EMPTY_MARK}</td>"
            f"<td data-label='2R'>{raw.round2_score if raw.round2_score is not None else EMPTY_MARK}</td>"
            f"<td data-label='3R'>{raw.round3_score if raw.round3_score is not None else EMPTY_MARK}</td>"
            f"<td data-label='4R'>{EMPTY_MARK}</td>"
            f"<td data-label='합계'>{EMPTY_MARK}</td>"
            f"<td class='win' data-label='TOP20'>{EMPTY_MARK}</td>"
            f"<td class='win' data-label='TOP10'>{EMPTY_MARK}</td>"
            f"<td class='win' data-label='TOP5'>{EMPTY_MARK}</td>"
            f"<td class='win' data-label='우승'>{EMPTY_MARK}</td>"
            f"</tr>"
        )

    winner_truth = truth_by_id[truth["winner_player_id"]]
    runner_up = next(r for r in truth["records"] if r.get("final_rank") == 2)
    winner_to_par = winner_truth["final_score"]  # already a to-par display string, e.g. "-12"

    # ---------------- Internal validation (unchanged, fully computed) --------
    # final_validator.run_final_validation still runs in full -- every
    # metric (Brier/log loss/rank MAE/reciprocal rank/tie-aware Top20/
    # surprises) remains available via final_report.build_final_report
    # for the internal evidence artifact. Only the PUBLIC page's own
    # content (below) was simplified per the 2026-09-20 operator
    # principle -- nothing was removed from what gets computed.
    final_validator.run_final_validation(context)  # build-time gate: raises FinalValidationBlocked on bad data
    topk_stats = _topk_stats(forecast_by_id, truth_by_id)

    # ---------------- Public summary (plain language, no jargon) -------------
    winner_win_pct = forecast_by_id[winner_truth["player_id"]]["win_pct"]
    winner_is_top_pick = winner_win_pct == max(r["win_pct"] for r in forecast_by_id.values())
    top5, top10 = topk_stats[5], topk_stats[10]
    hero_forecast_line = render_final_hero_forecast_line(
        winner_win_probability_pct=winner_win_pct,
        winner_is_top_pick=winner_is_top_pick,
    )
    public_summary_html = render_final_public_summary(
        top5_predicted=top5["predicted_population"],
        top5_hit=top5["hit_count"],
        top10_predicted=top10["predicted_population"],
        top10_hit=top10["hit_count"],
    )

    winner_identity = _player_cell(winner_truth["player_id"], winner_truth["player_name"], country_by_id, sponsor_by_id)
    del runner_up  # kept for potential future use; not rendered separately (already appears in the leaderboard)

    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NEO GOLF DATA · {TOURNAMENT_NAME} FINAL</title><link rel="stylesheet" href="/assets/neo-site.css"><link rel="stylesheet" href="../../../../assets/neo.css"><meta name="neo-stage-publication-ready" content="true"></head><body><header class="neo-global-header" data-neo-global-navigation><div class="neo-global-header__inner"><a class="neo-global-brand" href="/"><span class="neo-brand-mark">NEO GOLF DATA</span><span class="neo-brand-legend"><span class="neo-brand-legend__item">NUMBER</span><span class="neo-brand-legend__item">EVIDENCE</span><span class="neo-brand-legend__item">ORACLE</span></span></a><nav class="neo-global-nav" aria-label="주요 메뉴"><a href="/">홈</a><a href="/tournaments/2026/2026090002/final/" class="is-active" aria-current="page">대회</a><a href="/ranking/">랭킹</a><a href="/deep-dive/">딥다이브</a><a href="/neo-lab/">NEO LAB</a><a href="/about/">소개</a></nav></div></header><main><style>@media(max-width:760px){{.hana-tourinfo-sep{{display:none}}.hana-tourinfo-holes{{display:block}}}}
.leaderboard-table.leaderboard-table--flat-scroll tbody td:nth-child(n+3):nth-child(-n+8){{text-align:center}}
@media(max-width:760px){{
.leaderboard-table.leaderboard-table--flat-scroll thead th:nth-child(n+3):nth-child(-n+8),
.leaderboard-table.leaderboard-table--flat-scroll tbody td:nth-child(n+3):nth-child(-n+8){{padding-left:6px;padding-right:6px;text-align:center}}
}}
</style><nav class="breadcrumb" aria-label="현재 위치"><a href="/">홈</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><a href="/tournaments/">대회</a><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span>{TOURNAMENT_NAME}</span><span class="breadcrumb__sep" aria-hidden="true"> &gt; </span><span aria-current="page">FINAL</span></nav><section class="hero" id="tournament"><div><p class="eyebrow">FINAL</p><h1>{TOURNAMENT_NAME}</h1><p class="meta">{TOURNAMENT_DATE_META}</p><p class="meta">우승 {winner_identity} {winner_to_par} ({winner_truth['rounds_completed']}라운드 합계 {raw_by_id[winner_truth['player_id']].total_strokes}타)</p>{hero_forecast_line}<p class="meta">{TOURNAMENT_VENUE_META}</p></div></section><nav class="stage-nav" aria-label="대회 단계" data-stage-nav><ol class="stage-nav__list"><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/pre/">사전 분석 PRE</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r1/">R1</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r2/">R2</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/r3/">R3</a></li><li class="stage-nav__item"><a class="stage-nav__link" href="/tournaments/2026/2026090002/final/" aria-current="page">FINAL</a></li></ol></nav><section class="panel leaderboard-panel" id="final-leaderboard"><div class="leaderboard-head"><h2>FINAL 결과 <small>{len(truth['records'])}명</small></h2><p class="note">{SCOPE_LABEL}</p></div><div class="table-wrap table-wrap--flat-scroll"><table class="data leaderboard-table leaderboard-table--flat-scroll"><thead><tr><th>순위</th><th>선수</th><th>합계</th><th>1R</th><th>2R</th><th>3R</th><th>4R</th><th>합계</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table></div></section>{public_summary_html}</main><nav class="sr-data" aria-label="추가 탐색 링크"><a href="/">NEO GOLF DATA</a> <a href="/">홈</a> <a href="/tournaments/2026/2026090002/final/">대회</a> <a href="/deep-dive/">딥다이브</a> <a href="/about/">소개</a></nav><footer class="site-footer"><div class="site-footer__inner"><p class="site-footer__copyright">© 2026 NEO GOLF DATA. All Rights Reserved.</p></div></footer></body></html>"""

    assert_not_root_home(FINAL_PAGE, repo_root=REPO_ROOT)
    FINAL_PAGE.parent.mkdir(parents=True, exist_ok=True)
    FINAL_PAGE.write_text(html, encoding="utf-8")
    print("wrote", FINAL_PAGE)
    print("rows:", len(rows_html), "(63 ACTIVE + 1 WD)")
    print("topk_stats:", json.dumps(topk_stats, ensure_ascii=False))


if __name__ == "__main__":
    main()
