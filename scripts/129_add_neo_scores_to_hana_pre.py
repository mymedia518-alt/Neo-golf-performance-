"""Put Hana M4 results into the existing PRE participant panel."""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'docs/tournaments/2026/2026090002/pre/index.html'
DATA = ROOT / 'klpga_pipeline/content/website_v2/HANA_2026090002_PRE_M4_60000_CANDIDATE_V1.json'

page = PAGE.read_text(encoding='utf-8')
data = json.loads(DATA.read_text(encoding='utf-8'))

rows = []
for record in data['records']:
    code = escape(str(record['playerCode']))
    name = escape(record['playerName'])
    category = '추천자' if record.get('entry_category') == 'recommended' else '자격자'
    status = escape(record.get('data_status', '검증 가능'))
    rows.append(
        f"<tr data-player-id='{code}'>"
        f"<th scope='row'><span class='player-name'>{name}</span><span class='player-sponsor'></span></th>"
        f"<td data-label='참가 구분'>{category}</td>"
        f"<td data-label='NEO순위'>{record['neo_rank']}</td>"
        f"<td data-label='NEO점수'>{float(record['neo_score_display']):.2f}%</td>"
        f"<td data-label='검증 상태'>{status}</td></tr>"
    )

section = (
    '<section class="panel leaderboard-panel" id="pre">'
    '<div class="leaderboard-head"><h2>PRE 참가 선수 <small>108명</small></h2>'
    '<p class="note">공식 참가자 명단 기준 · M4 검증 후보 · 60,000회 시뮬레이션</p></div>'
    '<div class="table-wrap"><table class="data leaderboard-table"><thead><tr>'
    '<th>선수</th><th>참가 구분</th><th>NEO순위</th><th>NEO점수</th><th>검증 상태</th>'
    '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'
    '<p class="note">분석 가능 103명 · 데이터 부족 5명 · 점수는 소수점 둘째 자리까지 표시</p>'
    '</section>'
)

marker = '<section class="panel leaderboard-panel" id="pre">'
if marker not in page:
    raise ValueError('PRE participant panel marker not found')

for start_marker in (
    "<section class='panel previous-event-validation' id='previous-event-validation'>",
    "<section class='panel neo-player-analysis' id='neo-player-analysis'>",
):
    if start_marker in page:
        start = page.index(start_marker)
        end = page.index('</section>', start) + len('</section>')
        page = page[:start] + page[end:]

start = page.index(marker)
end = page.index('</section>', start) + len('</section>')
page = page[:start] + section + page[end:]
PAGE.write_text(page, encoding='utf-8')
print(PAGE)
print('rows', len(rows))
