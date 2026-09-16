import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'klpga_pipeline/src'))

from klpga.website_v2.neo_ranking_v2a import evaluate_v2a, estimate_shrinkage_prior

INPUT = ROOT / 'klpga_pipeline/content/website_v2/HANA_2026090002_PLAYER_ANALYSIS_INPUT_V1.json'
WAREHOUSE = ROOT / 'klpga_pipeline/content/website_v2/historical_sg_warehouse_corrected_v2.json'
OUTPUT = ROOT / 'klpga_pipeline/content/website_v2/HANA_2026090002_NEO_SCORE_CANDIDATE_V1.json'

hana = json.loads(INPUT.read_text(encoding='utf-8'))
warehouse = json.loads(WAREHOUSE.read_text(encoding='utf-8'))
cohort = {
    'records': [
        {
            'player_id': r['player_id'],
            'player_name': r['official_display_name'],
            'official_k_rank': r.get('k_rank') if r.get('k_rank') is not None else 999,
        }
        for r in hana['records']
    ]
}
prior = estimate_shrinkage_prior(warehouse)
scores, summary = evaluate_v2a(cohort, warehouse, prior, minimum_rounds=20)
by_id = {r['player_id']: r for r in hana['records']}
for row in scores:
    source = by_id[row['player_id']]
    row['season_sg'] = source.get('current_official_sg')
    row['season_sg_status'] = '확인' if source.get('current_official_sg') else '데이터 부족'
    row['neo_score_display'] = round(row['validation_score'], 2) if row.get('validation_score') is not None else None
    row['analysis_label'] = 'NEO 분석 가능' if row.get('validation_score') is not None else '데이터 부족'
scores.sort(key=lambda r: (r['validation_score'] is None, -(r['validation_score'] or 0), r['player_name']))
for i, row in enumerate(scores, 1):
    row['display_order'] = i

out = {
    'schema_version': 'HANA_2026090002_NEO_SCORE_CANDIDATE_V1',
    'game_code': hana['game_code'],
    'tournament_name': hana['tournament_name'],
    'model_id': 'neo-ranking-v2a-exposure-neutral',
    'publication_class': 'VALIDATION_MODEL_NOT_PRODUCTION',
    'score_display_precision': 2,
    'season_sg_source': 'KLPGA_2026_SEASON_SG_FULL_CAPTURE_V1.json',
    'historical_warehouse_source': 'historical_sg_warehouse_corrected_v2.json',
    'note': 'Evaluation-only NEO V2A score. Season SG is attached as an audited input; V2A score uses the frozen historical SG windows and consistency features. No production publication.',
    'summary': {**summary, 'season_sg_confirmed': sum(r['season_sg_status'] == '확인' for r in scores), 'season_sg_data_insufficient': sum(r['season_sg_status'] == '데이터 부족' for r in scores)},
    'records': scores,
}
OUTPUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out['summary'], ensure_ascii=False))
for r in scores[:20]:
    print(r['display_order'], r['player_name'], r['neo_score_display'], r['season_sg_status'], r['neo_ranking_state'])
print('DATA_INSUFFICIENT', [r['player_name'] for r in scores if r['analysis_label'] == '데이터 부족'])
