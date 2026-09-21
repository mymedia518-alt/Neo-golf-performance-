"""Probe the official cmpro playerScore fragment without guessing its schema."""
from __future__ import annotations
import argparse,sys
from pathlib import Path
SRC_ROOT=Path(__file__).resolve().parents[1]/"src"
if str(SRC_ROOT) not in sys.path: sys.path.insert(0,str(SRC_ROOT))
from bs4 import BeautifulSoup
from klpga.collectors.cmpro_shots import fetch_player_score_html
from klpga.http_client import PoliteHttpClient

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--game",required=True)
    ap.add_argument("--player",required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--cache",type=Path,default=Path("cache/cmpro"))
    a=ap.parse_args()
    html=fetch_player_score_html(PoliteHttpClient(a.cache),a.game,a.player,use_cache=False)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(html,encoding="utf-8")
    soup=BeautifulSoup(html,"html.parser")
    print("PLAYER_SCORE bytes=",len(html.encode("utf-8")))
    print("tags=",len(soup.find_all(True)))
    attrs=sorted({str(k) for tag in soup.find_all(True) for k in tag.attrs})
    print("attrs=",attrs)
    text=" ".join(soup.stripped_strings)
    print("text_preview=",text[:1000])
    print("saved=",a.out)

if __name__=="__main__":
    main()
