from __future__ import annotations
import json, hashlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from klpga.official_tournament_warehouse import freeze_tournament_snapshot, build_round_exposure

ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/'content/website_v2/NEO_HISTORICAL_R1_FULL_FIELD_V1.json'; OUT=ROOT/'evidence/official_tournament_warehouse_v1'
def main():
 d=json.loads(SRC.read_text(encoding='utf-8')); selected=d['records'][:3]; rows=[]; manifests=[]; exposure=[]
 for rec in selected:
  game=rec['game_code']; players=rec.get('players',[])
  raw_path=ROOT/'evidence'/'historical_r1_groupings_blocker_resolution_v1'/rec.get('raw_evidence','')
  manifests.append({'gameCode':game,'source_type':'scoreRecord','source_url':rec['official_source'],'capture_timestamp':rec['retrieved_at'],'sha256':rec['source_sha256'],'parser_version':'leaderboard_parser','retrieval_status':'ARCHIVED_OK','raw_evidence':rec.get('raw_evidence')})
  for p in players:
   rows.append({'gameCode':game,'playerCode':p['player_code'],'player_name':p.get('player_name'),'round':1,'round_score':p.get('r1_score'),'finish':None,'status':p.get('r1_status'),'raw_source_values':p})
   exposure.append({'playerCode':p['player_code'],'gameCode':game,'round':1,'round_played':p.get('r1_status')!='INCOMPLETE','round_score':p.get('r1_score'),'completion_status':p.get('r1_status') or 'ACTIVE'})
 doc={'schema':'OFFICIAL_TOURNAMENT_WAREHOUSE_V1','status':'REAL_ARCHIVED_OFFICIAL_OBSERVATIONS','tournaments':selected,'round_rows':rows,'source_manifest':manifests,'counts':{'tournaments':len(selected),'unique_players':len({x['playerCode'] for x in rows}),'player_tournament_rows':len(rows),'player_round_rows':len(rows),'course_hole_rows':0,'performance_rows':0}}
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'OFFICIAL_TOURNAMENT_WAREHOUSE_V1.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
 ex={'schema':'NEO_OFFICIAL_ROUND_EXPOSURE_V1','status':'REAL_ARCHIVED_OFFICIAL_OBSERVATIONS','rows':build_round_exposure(exposure,game_code='MULTI') if False else exposure,'counts':{'rows':len(exposure),'players_1_round':len({x['playerCode'] for x in exposure})}}
 (OUT/'NEO_OFFICIAL_ROUND_EXPOSURE_V1_REAL.json').write_text(json.dumps(ex,ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'coverage_audit.json').write_text(json.dumps({'population_completeness':'UNVERIFIED','sampled_gameCodes':[r['game_code'] for r in selected],'source_family_counts':{'scoreRecord':3,'tourInfo':0,'entry':0,'group':0,'mainRecord':0,'liveMap':0},'real_rows':len(rows)},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': main()
