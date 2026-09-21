"""Plan cmpro collection for one player only; makes no playerInfo shot requests."""
from __future__ import annotations
import argparse,sys
from pathlib import Path
SRC_ROOT=Path(__file__).resolve().parents[1]/"src"
if str(SRC_ROOT) not in sys.path: sys.path.insert(0,str(SRC_ROOT))
from klpga.collectors.cmpro_shots import fetch_cmpro_leaderboard_html,fetch_player_score_html,parse_cmpro_players,parse_cmpro_played_holes
from klpga.http_client import PoliteHttpClient

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--game",required=True)
    ap.add_argument("--player-code",required=True)
    ap.add_argument("--player-name",required=True)
    ap.add_argument("--cache",type=Path,default=Path("cache/cmpro"))
    a=ap.parse_args()
    client=PoliteHttpClient(a.cache)
    players=parse_cmpro_players(fetch_cmpro_leaderboard_html(client,a.game))
    official_name=players.get(a.player_code)
    if official_name is None:
        print(f"PLAYER_NOT_FOUND game={a.game} code={a.player_code} name={a.player_name}",flush=True)
        raise SystemExit(3)
    if a.player_name not in official_name and official_name not in a.player_name:
        print(f"PLAYER_IDENTITY_MISMATCH game={a.game} code={a.player_code} expected={a.player_name} official={official_name}",flush=True)
        raise SystemExit(4)
    scope=parse_cmpro_played_holes(fetch_player_score_html(client,a.game,a.player_code))
    if not scope:
        print(f"NO_PLAYED_HOLES game={a.game} code={a.player_code} official={official_name}",flush=True)
        raise SystemExit(5)
    rounds=sorted(scope)
    holes=sum(len(v) for v in scope.values())
    print(f"PLAYER {a.player_code} {official_name}",flush=True)
    print(f"ROUNDS {rounds}",flush=True)
    print(f"HOLES_BY_ROUND {scope}",flush=True)
    print(f"PLANNED_HOLES {holes}",flush=True)
    print(f"[PLAYER PLAN PASS] {a.game}",flush=True)

if __name__=="__main__": main()
