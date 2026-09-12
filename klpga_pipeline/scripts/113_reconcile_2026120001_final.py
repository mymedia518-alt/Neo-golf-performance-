from __future__ import annotations
import json, zipfile, hashlib, re
from pathlib import Path
from bs4 import BeautifulSoup
WT=Path(__file__).resolve().parents[1]; ZIP=WT/'evidence/current_round_2026120001_r3_20260906/official_sources.zip'; OUT=WT/'evidence/official_tournament_warehouse_v1'
def rows(html,round_no):
 s=BeautifulSoup(html,'html.parser'); out=[]
 for tr in s.select('[data-rank]'):
  a={str(k).lower():v for k,v in tr.attrs.items()}; code=a.get('_playercode') or a.get('data-playercode') or a.get('playercode')
  if not code:
   d=tr.select_one('[_playercode]'); code=d.get('_playercode') if d else None
  if not code: continue
  status=(a.get('data-status') or a.get('status') or '').upper() or None
  out.append({'gameCode':'2026120001','playerCode':str(code),'round':round_no,'rank':a.get('data-rank'),'status':status,'round_score':a.get(f'data-round{round_no}score'),'total_score':a.get('data-score'),'ingHole':a.get('data-inghole'),'finishHole':a.get('data-finishhole')})
 return out
def main():
 z=zipfile.ZipFile(ZIP); allrows=[]; manifest=[]
 for n in range(3):
  fn=f'leaderboard-{n}.html'; b=z.read(fn); manifest.append({'file':fn,'round':n+1,'sha256':hashlib.sha256(b).hexdigest(),'source_type':'official_scoreRecord_archived'})
  seen={(r['playerCode'],r['round']) for r in allrows}; allrows += [r for r in rows(b,n+1) if (r['playerCode'],r['round']) not in seen]
 r1=json.loads((WT/'content/website_v2/OK_OPEN_2026_R1_LIVE_SNAPSHOT.json').read_text(encoding='utf-8'))
 codes=sorted({str(p.get('player_id')) for p in r1.get('leaderboard',[]) if p.get('player_id')} | {r['playerCode'] for r in allrows}); final={c:{'playerCode':c,'rounds':[r['round'] for r in allrows if r['playerCode']==c],'status':next((r['status'] for r in reversed(allrows) if r['playerCode']==c and r['status']), 'OTHER_OFFICIAL_STATUS')} for c in codes}
 counts={}
 for v in final.values(): counts[v['status']]=counts.get(v['status'],0)+1
 OUT.mkdir(parents=True,exist_ok=True); (OUT/'2026120001_FINAL_STATUS_TRUTH.json').write_text(json.dumps({'gameCode':'2026120001','source_manifest':manifest,'players':list(final.values()),'status_counts':counts},ensure_ascii=False,indent=2),encoding='utf-8'); (OUT/'2026120001_RECONCILED_PLAYER_ROUNDS.json').write_text(json.dumps({'gameCode':'2026120001','rows':allrows,'row_count':len(allrows)},ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__': main()
