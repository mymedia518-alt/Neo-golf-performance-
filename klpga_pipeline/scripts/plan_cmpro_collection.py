"""Build a no-shot-request cmpro collection manifest from leaderboard + playerScore."""
from __future__ import annotations
import argparse,csv,sys
from pathlib import Path
SRC_ROOT=Path(__file__).resolve().parents[1]/"src"
if str(SRC_ROOT) not in sys.path: sys.path.insert(0,str(SRC_ROOT))
from klpga.collectors.cmpro_shots import (
    fetch_cmpro_leaderboard_html,fetch_player_score_html,
    parse_cmpro_players,parse_cmpro_played_holes,
)
from klpga.http_client import PoliteHttpClient

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--game",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--cache",type=Path,default=Path("cache/cmpro"))
    a=ap.parse_args()
    client=PoliteHttpClient(a.cache)
    players=parse_cmpro_players(fetch_cmpro_leaderboard_html(client,a.game))
    rows=[]
    round_counts={}
    for code,name in players.items():
        scope=parse_cmpro_played_holes(fetch_player_score_html(client,a.game,code))
        rounds=sorted(scope)
        holes=sum(len(v) for v in scope.values())
        rows.append((code,name,",".join(map(str,rounds)),holes))
        key=len(rounds)
        round_counts[key]=round_counts.get(key,0)+1
        print(f"{code} {name} rounds={rounds} holes={holes}",flush=True)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["player_code","player_name","rounds","planned_holes"]);w.writerows(rows)
    print("PLAYERS",len(players))
    print("ROUND_COUNTS",dict(sorted(round_counts.items())))
    print("PLANNED_HOLES",sum(r[3] for r in rows))
    print("MANIFEST",a.out)

if __name__=="__main__":
    main()
