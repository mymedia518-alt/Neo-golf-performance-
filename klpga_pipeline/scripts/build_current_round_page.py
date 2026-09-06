"""Add a verified current leaderboard to an existing round forecast page."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
import re


def build(snapshot, template):
    players = snapshot["player_table"]
    assert len(players) == snapshot["row_count"] == len({r["player_code"] for r in players})
    stamp = datetime.fromisoformat(snapshot["collected_at"]).astimezone(
        timezone(timedelta(hours=9))
    ).strftime("%Y-%m-%d %H:%M:%S KST")
    sg_stamp = datetime.fromisoformat(snapshot["sg_retrieved_at"]).astimezone(
        timezone(timedelta(hours=9))
    ).strftime("%H:%M:%S KST")
    rows = []
    for r in players:
        assert 0 <= r["holes_completed"] <= 18
        cells = [r["rank_display"], r["player_name"], r["total_under_par_display"],
                 r["today_under_par_display"], str(r["holes_completed"]),
                 "종료" if r["progress_display"] == "F" else f'{r["raw_inghole"]}번 홀',
                 "OUT (1번)" if r["starting_tee"] == 1 else "IN (10번)"]
        rows.append(f'<tr data-current-player="{escape(r["player_code"])}">' +
                    "".join(f"<td>{escape(str(x))}</td>" for x in cells) + "</tr>")
    sg_rows = []
    for r in snapshot["sg"]:
        assert all(r["validation"][k] for k in ("total_within_tolerance", "t2g_within_tolerance"))
        sg_rows.append(f'<tr data-sg-player="{escape(r["player_id"])}"><td>{escape(r["player"])}</td>' +
                       "".join(f'<td>{r[k]:+.2f}</td>' for k in ("total", "tee_to_green", "off_the_tee", "approach", "around_green", "putting")) + "</tr>")
    finished = sum(r["holes_completed"] == 18 for r in players)
    leader = players[0]
    current = f'''<!-- NEO CURRENT ROUND START -->
<section class="panel neo-current-round" id="current-round" data-current-round="{snapshot['round']}" data-collected-at="{escape(snapshot['collected_at'])}">
<p class="eyebrow">OK저축은행 읏맨 오픈 · 공식 R3 현재 상황</p>
<h1>R3 (FINAL) 현재 리더보드</h1>
<p class="note">공식 데이터 확인: <time>{stamp}</time> · {len(players)}명 · 라운드 완료 {finished}명</p>
<p><strong>현재 선두 {escape(leader['player_name'])} · 합계 {escape(leader['total_under_par_display'])}</strong></p>
<p class="note">완료 홀은 공식 홀별 스코어가 기록된 개수입니다. 진행 홀은 코스의 홀 번호이며, IN 출발은 10번 홀부터 시작합니다.</p>
<div class="table-wrap"><table class="data"><caption>R3 공식 성적</caption><thead><tr><th>순위</th><th>선수</th><th>합계</th><th>오늘</th><th>완료 홀</th><th>진행 홀</th><th>출발</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="note"><a href="https://klpga.co.kr/web/leaderboard/leaderboard?gameCode={snapshot['game_code']}">KLPGA 공식 리더보드</a> · 원본에 별도 갱신 시각이 없어 NEO가 확인한 시각을 표시합니다.</p>
<details><summary>공식 R3 SG 경기력 보기</summary>
<p class="note">R3 단일 라운드 공식 SG · 확인 {sg_stamp}. 진행 중인 라운드의 잠정 기록입니다. 성적과 SG는 공식 제공 시차가 있을 수 있습니다.</p>
<div class="table-wrap"><table class="data"><thead><tr><th>선수</th><th>SG 전체</th><th>티→그린</th><th>티샷</th><th>어프로치</th><th>그린주변</th><th>퍼팅</th></tr></thead><tbody>{''.join(sg_rows)}</tbody></table></div></details>
<p class="note">아래 NEO 확률은 R2 종료 기준 사전예측입니다. 현재 R3 성적을 반영한 실시간 확률은 제공하지 않습니다.</p>
</section>
<!-- NEO CURRENT ROUND END -->
'''
    template = re.sub(r'<!-- NEO CURRENT ROUND START -->.*?<!-- NEO CURRENT ROUND END -->\s*', '', template, flags=re.S)
    template = template.replace('<h1>R3 (FINAL) NEO 예측</h1>', '<h2>R2 종료 기준 · R3 (FINAL) NEO 사전예측</h2>')
    template = template.replace('NEO GOLF DATA · R3 (FINAL) 예측</title>', 'NEO GOLF DATA · R3 (FINAL) 현재 상황</title>')
    template = re.sub(r'(<meta name="neo-build-id" content=")[^"]+', r'\g<1>' + snapshot['collected_at'], template)
    assert '<section class="panel">' in template
    return template.replace('<section class="panel">', current + '\n<section class="panel">', 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--snapshot', type=Path, required=True)
    ap.add_argument('--template', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    template_bytes = args.template.read_bytes()
    result = build(json.loads(args.snapshot.read_text(encoding='utf-8')), template_bytes.decode('utf-8').replace('\r\n', '\n'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    newline = '\r\n' if b'\r\n' in template_bytes else '\n'
    args.output.write_bytes(result.replace('\n', newline).encode('utf-8'))
    print(args.output)


if __name__ == '__main__':
    main()
