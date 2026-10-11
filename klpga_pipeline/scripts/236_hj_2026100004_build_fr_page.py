"""Build the FR (final round / official final results) page for HJ
2026100004.

4R is now officially over (confirmed via HJ_2026100004_FR_OFFICIAL_
RESULTS_V1.json -- see that file's fr_official_final_evidence array
for the full evidence chain: the official stablefordScoreRecord page
now shows all 4 rounds populated with an assigned prize amount for
every one of the 61 players, cross-checked against the operator-
specified scoreRecord URL and against the already-verified R3 JSON).
This page now shows the OFFICIAL FINAL RESULTS as its primary table:
rank, player, R1/R2/R3/4R points, final total.

The pre-4R forecast (TOP20/TOP10/TOP5/win probability, computed from
HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_RESULTS.json, the
real 60,000-run Monte Carlo output generated 2026-10-10 from verified
3R input) is preserved exactly as published -- never recomputed or
adjusted to match the real outcome -- as clearly-dated "4R 종료 전
TOP20"-style columns plus a dedicated, explicitly-dated section below
the final results, so a reader can never mistake it for the real
outcome or suspect it was edited after the fact. No SG field is read,
on any page.

Primary table row order is by REAL official final points (not by
forecast win probability), matching how every other round page on
this tournament ranks by actual score.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klpga.website_v2.hj_2026100004_round_pages import (
    GAME_CODE,
    TOURNAMENT_DOCS_ROOT,
    image_section_html,
    name_cell,
    page_shell,
    rank_labels,
    stage_nav_html,
)

CONTENT = Path(__file__).resolve().parents[1] / "content" / "website_v2"
FR_OFFICIAL_PATH = CONTENT / "HJ_2026100004_FR_OFFICIAL_RESULTS_V1.json"
FORECAST_PATH = CONTENT / "HJ_2026100004_POST_R3_STABLEFORD_MONTE_CARLO_V1_RESULTS.json"
FR_SUMMARY_IMAGE_FILENAME = "neo-golf-data-fr-summary.png"

FORECAST_PUBLIC_FIELDS = {"top20_pct", "top10_pct", "top5_pct", "win_pct"}


def main():
    final = json.loads(FR_OFFICIAL_PATH.read_text(encoding="utf-8"))
    forecast = json.loads(FORECAST_PATH.read_text(encoding="utf-8"))
    forecast_by_name = {p["player_name"]: p for p in forecast["players"]}

    assert final["field_size"] == len(final["final_players"]) == 61
    assert set(forecast_by_name) == {p["player_name"] for p in final["final_players"]}, (
        "forecast roster and official final roster must be the exact same 61 players"
    )

    players = sorted(final["final_players"], key=lambda p: -p["final_points"])
    ranks = rank_labels([p["final_points"] for p in players])

    rows_html = []
    forecast_rows_html = []
    for rank, p in zip(ranks, players):
        fc = forecast_by_name[p["player_name"]]
        fpub = {k: v for k, v in fc.items() if k in FORECAST_PUBLIC_FIELDS}
        assert fpub["win_pct"] <= fpub["top5_pct"] + 1e-9, f"{p['player_name']}: win_pct > top5_pct"
        assert fpub["top5_pct"] <= fpub["top10_pct"] + 1e-9, f"{p['player_name']}: top5_pct > top10_pct"
        assert fpub["top10_pct"] <= fpub["top20_pct"] + 1e-9, f"{p['player_name']}: top10_pct > top20_pct"

        rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=fc["nationality"], name=p["player_name"], sponsor=fc["official_sponsor"])
            + f"<td data-label=\"R1\">+{p['r1_points']}</td>"
            f"<td data-label=\"R2\">+{p['r2_points']}</td>"
            f"<td data-label=\"R3\">+{p['r3_points']}</td>"
            f"<td data-label=\"4R\">{'+' if p['r4_points'] >= 0 else ''}{p['r4_points']}</td>"
            f"<td data-label=\"최종 포인트\"><strong>{'+' if p['final_points'] >= 0 else ''}{p['final_points']}</strong></td>"
            "</tr>"
        )
        forecast_rows_html.append(
            "<tr>"
            f"<td data-label=\"순위\">{rank}</td>"
            + name_cell(nationality=fc["nationality"], name=p["player_name"], sponsor=fc["official_sponsor"])
            + f"<td class=\"win\" data-label=\"4R 종료 전 TOP20\">{fpub['top20_pct'] * 100:.2f}%</td>"
            f"<td class=\"win\" data-label=\"4R 종료 전 TOP10\">{fpub['top10_pct'] * 100:.2f}%</td>"
            f"<td class=\"win\" data-label=\"4R 종료 전 TOP5\">{fpub['top5_pct'] * 100:.2f}%</td>"
            f"<td class=\"win\" data-label=\"4R 종료 전 우승확률\">{fpub['win_pct'] * 100:.2f}%</td>"
            "</tr>"
        )

    table_html = (
        "<div class=\"table-wrap\"><table class=\"data leaderboard-table\"><thead><tr>"
        "<th>순위</th><th>선수</th><th>R1</th><th>R2</th><th>R3</th><th>4R</th><th>최종 포인트</th>"
        "</tr></thead><tbody>" + "".join(rows_html) + "</tbody></table></div>"
    )
    forecast_table_html = (
        "<div class=\"table-wrap\"><table class=\"data leaderboard-table\"><thead><tr>"
        "<th>순위</th><th>선수</th><th>4R 종료 전 TOP20</th><th>4R 종료 전 TOP10</th>"
        "<th>4R 종료 전 TOP5</th><th>4R 종료 전 우승확률</th>"
        "</tr></thead><tbody>" + "".join(forecast_rows_html) + "</tbody></table></div>"
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

    forecast_label = "4R 종료 전 공개 예측 · 3R 종료 시점(2026-10-10 공개)"
    summary_alt = (
        f"{forecast_label} 요약: {winner['player_name']} 4R 우승확률 "
        f"{forecast_by_name[winner['player_name']]['win_pct'] * 100:.1f}% 1위"
    )

    body = (
        "<section class=\"panel\"><h2>공식 최종 순위 · {}명</h2>".format(len(players))
        + f"<p><strong>{winner['player_name']}</strong> 우승 "
        f"<strong>{'+' if winner['final_points'] >= 0 else ''}{winner['final_points']}</strong>"
        f" · 2위와 {margin}점 차</p>"
        + table_html
        + "<p><a href=\"https://klpga.co.kr/web/tourRecord/stablefordScoreRecord?gameCode=2026100004\" rel=\"noopener\">KLPGA 공식 기록 원문 ↗</a></p>"
        + "</section>"
        + f"<section class=\"panel\" id=\"pre-fr-forecast\"><h2>{forecast_label}</h2>"
        + "<p>4R이 끝나기 전, 검증된 3R 입력으로 실행한 NEO 예측입니다. "
        "실제 최종 결과가 나온 뒤에도 이 수치는 공개 당시 값 그대로 보존되며, 사후에 다시 계산하거나 결과에 맞춰 바꾸지 않습니다. "
        "위 공식 최종 순위와 혼동하지 않도록 구분해 표시합니다.</p>"
        + image_section_html(FR_SUMMARY_IMAGE_FILENAME, summary_alt, section_id="fr-summary")
        + forecast_table_html
        + f"<p><a href=\"/tournaments/2026/{GAME_CODE}/r3/\">3R 최종 결과 보기</a></p>"
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
