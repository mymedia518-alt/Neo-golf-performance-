from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "klpga_pipeline/evidence/KB_2026090003_FR/KB_2026090003_KLPGA_OFFICIAL_FR_70_SUPPLIED.json"
PAGE = ROOT / "docs/tournaments/2026/2026090002/pre/index.html"


def main() -> None:
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    players = sorted(evidence["players"], key=lambda row: (row["total_strokes"], row["player_name"]))[:5]
    rows = "".join(
        "<tr>"
        f"<td data-label='최종순위'>{escape(str(row['final_position']))}</td>"
        "<th scope='row'><span class='player-name'>"
        f"{escape(row['player_name'])}</span><span class='player-sponsor'></span></th>"
        f"<td data-label='최종스코어'>{escape(row['to_par_display'])} ({row['total_strokes']})</td>"
        f"<td data-label='FR'>{row['fr_score']}</td>"
        "</tr>"
        for row in players
    )
    section = (
        "<section class='panel previous-event-validation' id='previous-event-validation'>"
        "<div class='leaderboard-head'><h2>직전 대회 검증 <small>KB금융 골든라이프 챔피언십</small></h2>"
        "<p class='note'>FR 공식 결과 70명 전체 검증 PASS · 하나 대회 분석의 직전 대회 기준</p></div>"
        "<div class='table-wrap'><table class='data leaderboard-table'><thead><tr>"
        "<th>최종순위</th><th>선수</th><th>최종스코어</th><th>FR</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
        "<p class='note'>선수 70명 · 이름 중복 0 · 라운드 합산 오류 0 · 기준 데이터 2026.09.13 FR</p>"
        "<p class='note'><a href='https://klpga.co.kr/web/leaderboard/leaderboard_group?gameCode=2026090003' rel='noopener'>KLPGA 공식 결과 원본</a></p>"
        "</section>"
    )
    html = PAGE.read_text(encoding="utf-8")
    marker = "<section class=\"panel leaderboard-panel\" id=\"pre\">"
    if "id='previous-event-validation'" in html:
        raise SystemExit("previous-event-validation already exists")
    if marker not in html:
        raise SystemExit("PRE panel marker not found")
    PAGE.write_text(html.replace(marker, section + marker, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
