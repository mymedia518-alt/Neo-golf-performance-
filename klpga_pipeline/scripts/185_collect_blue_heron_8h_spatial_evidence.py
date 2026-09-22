"""Collect Blue Heron 8H official map/coordinate evidence for NEO spatial decision gate."""
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from klpga.http_client import PoliteHttpClient

OUT=ROOT/"data/player_baseline/blue_heron_8h_spatial_evidence_v1.json"
CACHE=ROOT/"data/raw_cache/http"
GAMES=("2025090004","2026100005")
HOLE=8

def main():
    c=PoliteHttpClient(cache_dir=CACHE,min_interval_sec=1.5)
    out={"hole":8,"games":{},"gate":"HOLD"}
    for game in GAMES:
        g={"rounds":{}}
        for rnd in (1,2,3,4):
            url="https://klpga.co.kr/ajax/tourInfo/getCourseHoleData"
            # endpoint is JSON but client text is sufficient; preserve exact response evidence
            txt=c.post_text(url,data={"gameCode":game,"round":str(rnd),"hole":str(HOLE)})
            try: payload=json.loads(txt)
            except Exception:
                payload={"_raw_sha256":hashlib.sha256(txt.encode()).hexdigest(),"_parse":"FAIL"}
            base=payload.get("baseHoleInfo") or {}
            shots=payload.get("shotGroupList") or []
            g["rounds"][str(rnd)]={
              "baseHoleInfo":base,
              "shot_count":len(shots),
              "shot_fields":sorted(shots[0].keys()) if shots else [],
              "response_sha256":hashlib.sha256(txt.encode()).hexdigest(),
            }
        out["games"][game]=g
    old=out["games"]["2025090004"]["rounds"]
    new=out["games"]["2026100005"]["rounds"]
    out["checks"]={
      "2025_has_coordinates":any(v["shot_count"]>0 for v in old.values()),
      "2026_has_coordinates":any(v["shot_count"]>0 for v in new.values()),
      "same_base_coordinates_all_available_rounds":None,
    }
    oldbases=[v["baseHoleInfo"] for v in old.values() if v["baseHoleInfo"]]
    newbases=[v["baseHoleInfo"] for v in new.values() if v["baseHoleInfo"]]
    if oldbases and newbases:
        keys=("bi_sx","bi_sy","bi_gx","bi_gy","bi_gpx","bi_gpy")
        out["checks"]["same_base_coordinates_all_available_rounds"]=all(
          all(a.get(k)==b.get(k) for k in keys) for a in oldbases for b in newbases
        )
    out["gate"]="PASS" if out["checks"]["2026_has_coordinates"] and out["checks"]["same_base_coordinates_all_available_rounds"] is not False else "HOLD"
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(out["checks"],ensure_ascii=False)); print("SPATIAL_GATE",out["gate"]); print(OUT)

if __name__=="__main__": main()
