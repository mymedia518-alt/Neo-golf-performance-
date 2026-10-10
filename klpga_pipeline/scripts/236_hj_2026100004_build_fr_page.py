"""Build the 4R (final round) forecast page for HJ 2026100004 (the 61
official R3 active players).

Reads the public-safe fields from content/website_v2/
HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_RESULTS.json: TOP20,
TOP10, TOP5, and win probability (operator instruction, 2026-10-10:
TOP5 is public on this page and its HOME mirror only; TOP20 added the
same day, same scope -- R1/R2/R3 still never show either, see
test_no_sg_or_top5_data_on_either_public_page /
test_no_top20_data_on_r2_or_r3_page). No SG field is read, on any page.

TOPN here means "probability of finishing in the top N after R4", NOT
"the N players with the highest win probability" -- each is read
per-player directly from the Monte Carlo output's own topN_pct
(_topN_pct(N) in 235_hj_2026100004_post_r3_stableford_monte_carlo.py),
which counts a simulated trial as a top-N finish whenever that
player's final score is >= the N-th-highest score in that trial (ties
at the boundary all count -- the same inclusion rule already used for
make_cut). Under that rule win_pct <= top5_pct <= top10_pct <= top20_pct
is a mathematical invariant per player (top-1 implies top-5 implies
top-10 implies top-20 within the same simulated trial); verified for
all 61 current players with zero violations.

Row order/rank is based on each player's REAL official R1+R2+R3 score
(not on forecast win probability), matching how the R1/R2/R3 pages rank
by actual current score rather than by model output.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klpga.website_v2.hj_2026100004_round_pages import (
    GAME_CODE,
    TOURNAMENT_DOCS_ROOT,
    name_cell,
    page_shell,
    rank_labels,
    stage_nav_html,
)

CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
FORECAST_PATH = CONTENT / "HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_RESULTS.json"
R3_OFFICIAL_PATH = CONTENT / "HJ_2026100004_R3_OFFICIAL_RESULTS_V1.json"

ALLOWED_PUBLIC_FIELDS = {"player_code", "player_name", "official_sponsor", "nationality", "real_cum54_points", "top20_pct", "top10_pct", "top5_pct", "win_pct"}


def main():
    forecast = json.loads(FORECAST_PATH.read_text(encoding="utf-8"))
    r3 = json.loads(R3_OFFICIAL_PATH.read_text(encoding="utf-8"))
    assert forecast["active_for_fr_count"] == r3["active_count"] == len(forecast["players"]) == 61

    players = sorted(forecast["players"], key=lambda p: -p["real_cum54_points"])
    ranks = rank_labels([p["real_cum54_points"] for p in players])

    rows_html = []
    for rank, p in zip(ranks, players):
        public = {k: v for k, v in p.items() if k in ALLOWED_PUBLIC_FIELDS}
        assert public["win_pct"] <= public["top5_pct"] + 1e-9, f"{public['player_name']}: win_pct > top5_pct"
        assert public["top5_pct"] <= public["top10_pct"] + 1e-9, f"{public['player_name']}: top5_pct > top10_pct"
        assert public["top10_pct"] <= public["top20_pct"] + 1e-9, f"{public['player_name']}: top10_pct > top20_pct"
        rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=public["nationality"], name=public["player_name"], sponsor=public["official_sponsor"])
            + f"<td data-label=\"R1+R2+R3 포인트\">+{public['real_cum54_points']}</td>"
            f"<td class=\"win\" data-label=\"TOP20\">{public['top20_pct'] * 100:.2f}%</td>"
            f"<td class=\"win\" data-label=\"TOP10\">{public['top10_pct'] * 100:.2f}%</td>"
            f"<td class=\"win\" data-label=\"TOP5\">{public['top5_pct'] * 100:.2f}%</td>"
            f"<td class=\"win\" data-label=\"우승확률\"><strong>{public['win_pct'] * 100:.2f}%</strong></td>"
            "</tr>"
        )

    table_html = (
        "<div class=\"table-wrap\"><table class=\"data leaderboard-table\"><thead><tr>"
        '<th>순위</th><th>선수</th><th>R1+R2+R3 포인트</th><th>TOP20</th><th>TOP10</th><th>TOP5</th><th>우승확률</th>'
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
    )

    leader = players[0]
    leader_win = next(p for p in forecast["players"] if p["player_name"] == leader["player_name"])["win_pct"]
    intro = (
        "<section class=\"page-intro\"><p class=\"eyebrow\">공식 결과 기반 예측 · 4R</p>"
        "<h1>HJ중공업·동부건설 챔피언십</h1>"
        "<p>변형 스테이블포드 · 2026.10.08–11 · 에이원CC · Par 72</p>"
        f"<p class=\"meta\">3R 공식 결과 {len(players)}명 대상 4R 예측</p>"
        "</section>"
    )

    body = (
        "<section class=\"panel\"><h2>4R 예측 · 3R 종료 {}명</h2>".format(len(players))
        + f"<p>{leader['player_name']} 단독 선두 <strong>+{leader['real_cum54_points']}</strong> "
        f"· 우승확률 {leader_win * 100:.2f}%</p>"
        + table_html
        + f"<p><a href=\"/tournaments/2026/{GAME_CODE}/r3/\">3R 최종 결과 보기</a></p>"
        + "<p><a href=\"https://klpga.co.kr/web/tourRecord/stablefordScoreRecord?gameCode=2026100004\" rel=\"noopener\">KLPGA 공식 기록 원문 ↗</a></p>"
        + "</section>"
    )

    html = page_shell(
        title="HJ중공업·동부건설 챔피언십 4R 예측 · NEO GOLF DATA",
        description=f"3R 공식 결과 {len(players)}명 대상 NEO 4R 예측 (TOP20/TOP10/TOP5/우승확률)",
        canonical_suffix="fr",
        breadcrumb_label="4R",
        intro_html=intro,
        stage_nav=stage_nav_html("fr", live_stages={"pre", "r1", "r2", "r3", "fr"}),
        body_html=body,
    )

    out_dir = TOURNAMENT_DOCS_ROOT / "fr"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(json.dumps({"written": str(out_path), "players": len(players)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
