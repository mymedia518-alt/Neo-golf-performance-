from __future__ import annotations
import json,hashlib
from pathlib import Path
WT=Path(__file__).resolve().parents[1]; C=WT/'content/website_v2'; E=WT/'evidence/KB_2026090003_R3'; OUT=E
def main():
 f=C/'2026090003_POST_R2_FINAL_FORECAST.json'; b=f.read_bytes(); forecast=json.loads(b); r3=json.loads((E/'KB_2026090003_R3_OFFICIAL_FINAL.json').read_text(encoding='utf-8'))
 actual={x['playerCode']:x for x in r3['rows']}; joined=[]
 for x in forecast['records']:
  a=actual.get(str(x['player_id'])); rank=None if not a or a['raw_status']=='WD' else (int(a['rank']) if str(a['rank']).isdigit() else None)
  joined.append({'playerCode':str(x['player_id']),'playerName':x['player_name'],'neo_final_rank':x['neo_final_rank'],'win_pct':x['win_pct'],'top5_pct':x['top5_pct'],'top10_pct':x['top10_pct'],'top20_pct':x['top20_pct'],'actual_rank':rank,'actual_status':a['raw_status'] if a else 'MISSING'})
 top=sorted([x for x in joined if x['actual_rank'] is not None],key=lambda x:(x['actual_rank'],x['playerCode']))[:25]
 audit={'forecast_provenance':{'path':str(f),'sha256':hashlib.sha256(b).hexdigest(),'build_id':forecast['build_id'],'collection_timestamp':forecast['build_id'],'n_simulations':forecast['n_simulations'],'source_round':forecast['source_round'],'feature_cutoff':forecast['feature_cutoff'],'code_commit':forecast['code_commit']},'join':{'forecast_rows':len(joined),'matched':sum(1 for x in joined if x['actual_rank'] is not None or x['actual_status']=='WD'),'wd_preserved':sum(1 for x in joined if x['actual_status']=='WD')},'outcome_definitions':{'WIN':'actual final rank == 1; WD excluded','TOP5':'actual final rank <= 5; WD excluded','TOP10':'actual final rank <= 10; WD excluded','TOP20':'actual final rank <= 20; WD excluded'},'validation':{},'r3_top20_plus_boundary':top}
 for key,thr in [('win',1),('top5',5),('top10',10),('top20',20)]:
  eligible=[x for x in joined if x['actual_rank'] is not None]; hits=sum(1 for x in eligible if x['actual_rank']<=thr); pred=sorted(eligible,key=lambda x:-x[key+'_pct'])[:thr]; audit['validation'][key]={'eligible_n':len(eligible),'actual_hits':hits,'top_probability_selection_hits':sum(1 for x in pred if x['actual_rank']<=thr)}
 (OUT/'KB_2026090003_R2_FORECAST_R3_VALIDATION.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': main()
