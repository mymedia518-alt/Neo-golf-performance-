"""Export the existing official KLPGA SG collection into canonical time-series rows."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from klpga.analytics.sg_performance import normalize_sg_records, validate_sg_records

def main() -> int:
    source=ROOT/"content/website_v2/kg_2026080001_official.json"; data=json.loads(source.read_text(encoding="utf-8"))
    ids={str(r.get("player")):str(r.get("player_id")) for r in data["leaderboard"] if r.get("player_id")}
    rows=[]
    for key, values in data["sg"].items():
        scope="tournament_cumulative" if key=="tournament" else "single_round"
        rnd=None if key=="tournament" else int(key[1:])
        for row in values:
            item=dict(row); item.update({"player_id":ids.get(str(row.get("player")),""),"season":2026,"game_code":data["game_code"],"tournament":"2026 KG Ladies Open","date":"2026-06-14","round":rnd,"scope":scope,"source":data["sources"]["sg"],"retrieved_at":data["retrieved_at"]}); rows.append(item)
    canonical=normalize_sg_records(rows); validation=validate_sg_records(canonical)
    out={"schema_version":"1.0","generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),"source_artifact":str(source.name),"source":data["sources"]["sg"],"validation":validation,"records":canonical}
    dest=ROOT/"content/website_v2/historical_sg_series.json"; dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n"); print(f"WROTE {dest} rows={len(canonical)} valid={validation['valid']}"); return 0
if __name__=="__main__": raise SystemExit(main())
