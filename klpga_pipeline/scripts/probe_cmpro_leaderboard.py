"""Probe cmpro leaderboard player discovery before full collection."""
from __future__ import annotations
import argparse,sys
from pathlib import Path
SRC_ROOT=Path(__file__).resolve().parents[1]/"src"
if str(SRC_ROOT) not in sys.path: sys.path.insert(0,str(SRC_ROOT))
from klpga.collectors.cmpro_shots import fetch_cmpro_leaderboard_html,parse_cmpro_players
from klpga.http_client import PoliteHttpClient

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--game",required=True)
    ap.add_argument("--cache",type=Path,default=Path("cache/cmpro"))
    a=ap.parse_args()
    html=fetch_cmpro_leaderboard_html(PoliteHttpClient(a.cache),a.game)
    players=parse_cmpro_players(html)
    print("LEADERBOARD bytes=",len(html.encode("utf-8")))
    print("PLAYER_COUNT=",len(players))
    print("PLAYER_SAMPLE=",list(players.items())[:10])
    if not players:
        raise SystemExit("FAIL: no player codes discovered")
if __name__=="__main__":
    main()
