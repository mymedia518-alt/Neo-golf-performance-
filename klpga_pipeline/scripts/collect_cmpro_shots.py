"""Collect cmpro shot-level data into an isolated SQLite warehouse."""
from __future__ import annotations
import argparse,csv,hashlib,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
SRC_ROOT=Path(__file__).resolve().parents[1]/"src"
if str(SRC_ROOT) not in sys.path: sys.path.insert(0,str(SRC_ROOT))
from klpga.collectors.cmpro_shots import fetch_cmpro_leaderboard_html,fetch_player_info_html,fetch_player_score_html,parse_cmpro_players,parse_cmpro_played_holes,parse_cmpro_shots,validate_cmpro_hole
from klpga.http_client import PoliteHttpClient
SCHEMA="""CREATE TABLE IF NOT EXISTS shot_event(game_code TEXT NOT NULL,player_code TEXT NOT NULL,player_name TEXT,round_number INTEGER NOT NULL,hole INTEGER NOT NULL,shot_no INTEGER NOT NULL,start_distance_yd REAL,start_lie TEXT,shot_distance_yd REAL NOT NULL,end_distance_yd REAL NOT NULL,end_lie TEXT NOT NULL,source_hash TEXT NOT NULL,collected_at TEXT NOT NULL,qa_status TEXT NOT NULL,PRIMARY KEY(game_code,player_code,round_number,hole,shot_no));
CREATE TABLE IF NOT EXISTS hole_audit(game_code TEXT NOT NULL,player_code TEXT NOT NULL,player_name TEXT,round_number INTEGER NOT NULL,hole INTEGER NOT NULL,shot_count INTEGER NOT NULL,qa_status TEXT NOT NULL,source_hash TEXT NOT NULL,collected_at TEXT NOT NULL,PRIMARY KEY(game_code,player_code,round_number,hole));"""
def utcnow(): return datetime.now(timezone.utc).isoformat()
def collect_hole(client,conn,game,code,name,rnd,hole,force=False):
 old=conn.execute("SELECT qa_status FROM hole_audit WHERE game_code=? AND player_code=? AND round_number=? AND hole=?",(game,code,rnd,hole)).fetchone()
 if old and old[0]=="PASS" and not force:return "SKIP_PASS",0
 html=fetch_player_info_html(client,game,code,rnd,hole,use_cache=not force); digest=hashlib.sha256(html.encode()).hexdigest()
 shots=parse_cmpro_shots(html);qa=validate_cmpro_hole(shots);ts=utcnow()
 conn.execute("DELETE FROM shot_event WHERE game_code=? AND player_code=? AND round_number=? AND hole=?",(game,code,rnd,hole))
 for s in shots: conn.execute("INSERT INTO shot_event VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(game,code,name,rnd,hole,s.shot_no,s.start_distance_yd,s.start_lie,s.shot_distance_yd,s.end_distance_yd,s.end_lie,digest,ts,qa))
 conn.execute("""INSERT INTO hole_audit VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(game_code,player_code,round_number,hole) DO UPDATE SET player_name=excluded.player_name,shot_count=excluded.shot_count,qa_status=excluded.qa_status,source_hash=excluded.source_hash,collected_at=excluded.collected_at""",(game,code,name,rnd,hole,len(shots),qa,digest,ts));conn.commit();return qa,len(shots)
def export_csv(conn,path):
 cur=conn.execute("SELECT * FROM shot_event ORDER BY player_code,round_number,hole,shot_no")
 with path.open("w",newline="",encoding="utf-8-sig") as f:
  w=csv.writer(f);w.writerow([x[0] for x in cur.description]);w.writerows(cur)
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--game",required=True);ap.add_argument("--out",type=Path,required=True);ap.add_argument("--cache",type=Path,default=Path("cache/cmpro"));ap.add_argument("--player");ap.add_argument("--round",type=int);ap.add_argument("--hole",type=int);ap.add_argument("--max-round",type=int,default=4);ap.add_argument("--force",action="store_true");a=ap.parse_args()
 client=PoliteHttpClient(a.cache);conn=sqlite3.connect(a.out);conn.executescript(SCHEMA)
 try:
  players={a.player:a.player} if a.player else parse_cmpro_players(fetch_cmpro_leaderboard_html(client,a.game))
  if not players:raise RuntimeError("No cmpro player codes found; stop rather than guessing.")
  counts={}
  for code,name in players.items():
   if a.round is not None:
    scope={a.round:[a.hole] if a.hole is not None else list(range(1,19))}
   else:
    score_html=fetch_player_score_html(client,a.game,code,use_cache=not a.force)
    scope=parse_cmpro_played_holes(score_html)
    if not scope:
     print(f"{code} NO_PLAYED_HOLES",flush=True)
     counts["NO_PLAYED_HOLES"]=counts.get("NO_PLAYED_HOLES",0)+1
     continue
   for rnd,holes in scope.items():
    if rnd > a.max_round: continue
    for hole in holes:
     qa,n=collect_hole(client,conn,a.game,code,name,rnd,hole,a.force);counts[qa]=counts.get(qa,0)+1;print(f"{code} R{rnd} H{hole:02d} {qa} shots={n}",flush=True)
  export_csv(conn,a.out.with_suffix(".csv"));print("SUMMARY",counts,flush=True)
  bad={k:v for k,v in counts.items() if k not in ("PASS","SKIP_PASS")}
  if bad:
   print("QA_FAIL",bad,flush=True)
   raise SystemExit(2)
 finally:conn.close()
if __name__=="__main__":main()
