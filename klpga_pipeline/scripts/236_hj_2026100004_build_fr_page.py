"""Build the FR (final round / official final results) page for HJ
2026100004.

4R is officially over (HJ_2026100004_FR_OFFICIAL_RESULTS_V1.json --
see its fr_official_final_evidence array for the evidence chain). The
page shows ONLY the official final results: rank, player, R1/R2/R3/4R
points, final total -- the real outcome, nothing else (operator
instruction, 2026-10-11: remove everything related to the pre-4R
forecast, and keep no internal/pipeline terminology visible). No
forecast field (TOP20/TOP10/TOP5/win probability), no forecast
image/section, and no SG field, on this or any public page.

Reuses the already-established leaderboard-table--fr-full modifier
(klpga.neo_win's KB FR page) for the mobile card layout -- same
7-column shape (순위/선수/R1/R2/R3/4R/최종 포인트), so no new CSS is
needed.

Row order is by REAL official final points, matching how every other
round page on this tournament ranks by actual score.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klpga.website_v2.hj_2026100004_round_pages import (
    TOURNAMENT_DOCS_ROOT,
    name_cell,
    page_shell,
    rank_labels,
    stage_nav_html,
)

CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
FR_OFFICIAL_PATH = CONTENT / "HJ_2026100004_FR_OFFICIAL_RESULTS_V1.json"


def main():
    final = json.loads(FR_OFFICIAL_PATH.read_text(encoding="utf-8"))
    assert final["field_size"] == len(final["final_players"]) == 61
    final_names = {p["player_name"] for p in final["final_players"]}
    assert len(final_names) == len(final["final_players"]) == 61, "duplicate player name in official final results"

    players = sorted(final["final_players"], key=lambda p: -p["final_points"])
    ranks = rank_labels([p["final_points"] for p in players])

    rows_html = []
    for rank, p in zip(ranks, players):
        rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=p["nationality"], name=p["player_name"], sponsor=p["official_sponsor"])
            + f"<td data-label=\"R1\">+{p['r1_points']}</td>"
            f"<td data-label=\"R2\">+{p['r2_points']}</td>"
            f"<td data-label=\"R3\">+{p['r3_points']}</td>"
            f"<td data-label=\"4R\">{'+' if p['r4_points'] >= 0 else ''}{p['r4_points']}</td>"
            f"<td data-label=\"최종 포인트\"><strong>{'+' if p['final_points'] >= 0 else ''}{p['final_points']}</strong></td>"
            "</tr>"
        )

    table_html = (
        "<div class=\"table-wrap\"><table class=\"data leaderboard-table leaderboard-table--fr-full\"><thead><tr>"
        "<th>순위</th><th>선수</th><th>R1</th><th>R2</th><th>R3</th><th>4R</th><th>최종 포인트</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
    )

    winner = players[0]
    runner_up_points = players[1]["final_points"]
    margin = winner["final_points"] - runner_up_points

    intro = (
        "<section class=\"page-intro\"><p class=\"eyebrow\">공식 최종 결과 · FR</p>"
        "<h1>HJ중공업·동부건설 챔피언십</h1>"
        "<p>변형 스테이블포드 · 2026.10.08–11 · 에이원CC · Par 72</p>"
        f"<p class=\"meta\">KLPGA 공식 기록 기준 최종 결과 · 전체 {len(players)}명</p>"
        "</section>"
    )

    body = (
        "<section class=\"panel\"><h2>공식 최종 순위 · {}명</h2>".format(len(players))
        + f"<p><strong>{winner['player_name']}</strong> 우승 "
        f"<strong>{'+' if winner['final_points'] >= 0 else ''}{winner['final_points']}</strong>"
        f" · 2위와 {margin}점 차</p>"
        + table_html
        + "<p><a href=\"https://klpga.co.kr/web/tourRecord/stablefordScoreRecord?gameCode=2026100004\" rel=\"noopener\">KLPGA 공식 기록 원문 ↗</a></p>"
        + "</section>"
    )

    html = page_shell(
        title="HJ중공업·동부건설 챔피언십 공식 최종 결과 · NEO GOLF DATA",
        description=f"HJ중공업·동부건설 챔피언십 KLPGA 공식 최종 결과 전체 {len(players)}명 (우승 {winner['player_name']} {winner['final_points']})",
        canonical_suffix="fr",
        breadcrumb_label="FR",
        intro_html=intro,
        stage_nav=stage_nav_html("fr", live_stages={"pre", "r1", "r2", "r3", "fr"}),
        body_html=body,
    )

    out_dir = TOURNAMENT_DOCS_ROOT / "fr"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(json.dumps({"written": str(out_path), "players": len(players), "winner": winner["player_name"], "winner_points": winner["final_points"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
