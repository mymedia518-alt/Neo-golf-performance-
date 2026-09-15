import json
import re
from pathlib import Path
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/workspace/scratch/c16f71b4aba6/upload/sg전체(3).html')
SG_OUT = ROOT / 'klpga_pipeline/content/website_v2/KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1.json'
HANA = ROOT / 'klpga_pipeline/content/website_v2/HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1.json'

doc = html.parse(str(SOURCE))
table = doc.xpath('//table[contains(@class,"table-record")][1]')[0]
rows = []
for tr in table.xpath('.//tbody/tr'):
    cells = [node.text_content().strip() for node in tr.xpath('./td')]
    if len(cells) != 10:
        raise ValueError(f'unexpected SG row width: {len(cells)}')
    hrefs = tr.xpath('.//a[contains(@href,"playerCode")]/@href')
    player_id = None
    if hrefs:
        match = re.search(r'playerCode=(\d+)', hrefs[0])
        player_id = match.group(1) if match else None
    def num(value):
        return float(value) if value else None
    rows.append({
        'official_rank': int(float(cells[1])) if cells[1] else None,
        'player_id': player_id,
        'player_name': cells[3],
        'sg_total': num(cells[4]),
        'sg_ott': num(cells[5]),
        'sg_app': num(cells[6]),
        'sg_arg': num(cells[7]),
        'sg_putt': num(cells[8]),
        'measured_rounds': int(float(cells[9])) if cells[9] else None,
    })

hana = json.loads(HANA.read_text(encoding='utf-8'))
by_id = {row['player_id']: row for row in rows if row['player_id']}
matched = 0
missing = 0
for record in hana['records']:
    source = by_id.get(record['player_id'])
    if source is None:
        record['current_official_sg'] = None
        record['analysis_status'] = 'DATA_INSUFFICIENT'
        missing += 1
        continue
    record['current_official_sg'] = {
        'total': source['sg_total'], 'ott': source['sg_ott'], 'app': source['sg_app'],
        'arg': source['sg_arg'], 'putt': source['sg_putt'], 'rounds': source['measured_rounds'],
        'source_capture': 'KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1.json',
        'identity_match': 'player_id',
    }
    record['analysis_status'] = 'READY_FOR_REVIEW'
    matched += 1

hana['sources'] = [
    'HANA_2026090002_OFFICIAL_ENTRY_LIST_V1.json',
    'HOME_PLAYER_MASTER_TOP120_2026_W36.json',
    'KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1.json',
    'historical_sg_warehouse_corrected_v2.json',
    'HANA_2026090002_FOREIGN_LPGA_ANALYSIS_EVIDENCE_V1.json',
]
hana['coverage']['current_official_sg'] = matched
hana['coverage']['ready_for_review'] = matched
hana['coverage']['no_data'] = missing
hana['coverage']['partial_data'] = missing
hana['publication_gate'] = 'BLOCKED_UNTIL_NEO_INPUT_REVIEW'
HANA.write_text(json.dumps(hana, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

evidence = {
    'schema_version': 'KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1',
    'source_file': SOURCE.name,
    'source_page': 'https://klpga.co.kr/web/record/locationRecord',
    'season': 2026,
    'metric': 'SG : 전체',
    'components': ['SG : 티샷', 'SG : 어프로치', 'SG : 그린주변', 'SG : 퍼팅'],
    'row_count': len(rows),
    'rows_with_player_id': len(by_id),
    'source_note': 'Operator-supplied saved HTML of the KLPGA official 2026 season SG full ranking page.',
    'players': rows,
}
SG_OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'sg_rows': len(rows), 'rows_with_player_id': len(by_id), 'hana_matched': matched, 'hana_data_insufficient': missing}, ensure_ascii=False))
