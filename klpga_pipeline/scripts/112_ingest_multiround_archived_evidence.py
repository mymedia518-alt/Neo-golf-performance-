from __future__ import annotations
import json, hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT/'content/website_v2'; OUT=ROOT/'evidence/official_tournament_warehouse_v1'
def load(n): return json.loads((BASE/n).read_text(encoding='utf-8'))
def main():
 game='2026120001'; r1=load('OK_OPEN_2026_R1_LIVE_SNAPSHOT.json'); r2=load('OK_OPEN_2026_R2_LIVE_SNAPSHOT.json'); r3=load('OK_OPEN_2026_R3_LIVE_SNAPSHOT.json')
 rows=[]
 for n,d in [(1,r1),(2,r2),(3,r3)]:
  source=d.get('input_provenance') or d.get('completion_source') or 'archived official snapshot'
  for p in (d.get('leaderboard') or d.get('player_table') or []):
   code=str(p.get('player_code') or p.get('player_id')); status=p.get('status')
   score=p.get('round_score') or p.get(f'r{n}_score')
   rows.append({'gameCode':game,'playerCode':code,'player_name':p.get('player_name'),'round':n,'round_score':score,'status':status,'holes_completed':p.get('holes_completed'),'starting_tee':p.get('starting_tee') or p.get('starting_tee_assumed'),'source_file':n})
 sources=[]
 for fn,d in [('OK_OPEN_2026_R1_LIVE_SNAPSHOT.json',r1),('OK_OPEN_2026_R2_LIVE_SNAPSHOT.json',r2),('OK_OPEN_2026_R3_LIVE_SNAPSHOT.json',r3)]:
  b=(BASE/fn).read_bytes(); sources.append({'gameCode':game,'round':d.get('round'),'source_type':'official_archived_snapshot','source_url':d.get('official_source_url') or 'klpga.co.kr roundLeaderboard','capture_timestamp':d.get('collected_at'),'sha256':hashlib.sha256(b).hexdigest(),'path':fn})
 out={'schema':'OFFICIAL_TOURNAMENT_WAREHOUSE_V1','status':'REAL_MULTIROUND_ARCHIVED_OFFICIAL_OBSERVATIONS','gameCode':game,'source_manifest':sources,'round_rows':rows,'counts':{'tournaments':1,'unique_players':len({x['playerCode'] for x in rows}),'player_tournament_rows':len({(x['playerCode'],game) for x in rows}),'player_round_rows':len(rows),'course_hole_rows':0,'performance_rows':0}}
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'OFFICIAL_TOURNAMENT_WAREHOUSE_V1_MULTIROUND.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 exp=[{k:x.get(k) for k in ('playerCode','gameCode','round','round_score','holes_completed','starting_tee')}|{'round_played':x.get('status') not in ('CUT','WD','DQ'),'completion_status':x.get('status') or 'ACTIVE'} for x in rows]
 (OUT/'NEO_OFFICIAL_ROUND_EXPOSURE_V1_MULTIROUND.json').write_text(json.dumps({'schema':'NEO_OFFICIAL_ROUND_EXPOSURE_V1','gameCode':game,'rows':exp,'counts':{'rows':len(exp),'by_round':{str(n):sum(x['round']==n for x in exp) for n in (1,2,3)},'cut':sum(x['completion_status']=='CUT' for x in exp),'wd':sum(x['completion_status']=='WD' for x in exp),'dq':sum(x['completion_status']=='DQ' for x in exp)}},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': main()
