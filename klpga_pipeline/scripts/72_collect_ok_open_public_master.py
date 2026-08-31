"""Collect official current identity/ranking data and export PRE evidence artifacts."""
from __future__ import annotations
import hashlib, json, sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content" / "website_v2"
ENTRY_PATH = CONTENT / "OK_OPEN_2026_ENTRY_SNAPSHOT.json"
PROFILE_URL = "https://klpga.co.kr/web/profile/mainRecord"
RANK_URL = "https://k-rankings.klpga.co.kr/allplayer.jsp"
DB = Path(r"C:/Users/user/Desktop/Neo-golf-performance-/klpga_pipeline/data/klpga.sqlite")

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
def label_value(soup, label_text):
    lab = soup.find("label", string=lambda x: x and x.strip() == label_text)
    if lab is None: return None
    parent = lab.parent
    tags = parent.find_all("h5")
    return tags[-1].get_text(" ", strip=True) if tags else ""

def collect_profiles(entries):
    session = requests.Session(); session.headers.update({"User-Agent":"Mozilla/5.0", "Accept-Language":"ko-KR,ko;q=0.9"})
    out=[]
    for i,e in enumerate(entries,1):
        pid=str(e["player_id"]); r=session.get(PROFILE_URL,params={"playerCode":pid},timeout=30); r.raise_for_status()
        soup=BeautifulSoup(r.content.decode("utf-8","replace"),"html.parser")
        search=soup.select_one("input.playerSearch")
        current_name=(search.get("placeholder") if search else None) or (soup.select_one(".ph-player h3").get_text(" ",strip=True) if soup.select_one(".ph-player h3") else None)
        status=label_value(soup,"등급"); sponsor=label_value(soup,"소속")
        out.append({"player_id":pid,"historical_source_names":list(dict.fromkeys([x for x in (e.get("player_name"),e.get("canonical_name")) if x])),"current_official_player_name":current_name,"current_player_status":status,"current_official_sponsor":sponsor or None,"official_source":PROFILE_URL+"?playerCode="+pid,"retrieved_at":now(),"identity_validation":"PASS" if current_name else "FAIL"})
        if i % 20 == 0: print(f"profiles {i}/{len(entries)}",flush=True)
        time.sleep(0.15)
    return out

def collect_rankings(target_ids):
    s=requests.Session(); s.headers.update({"User-Agent":"Mozilla/5.0","Referer":RANK_URL})
    s.get(RANK_URL,timeout=30).raise_for_status()
    # Official K-Rankings requires the public weekly form POST to populate
    # table rows; this is the same endpoint used by the site's UI.
    r=s.post(RANK_URL,data={"Rank_week":"202635","top_player":"김민솔","last_week":"null"},timeout=30); r.raise_for_status()
    soup=BeautifulSoup(r.content.decode("utf-8","replace"),"html.parser"); table=soup.select_one("table#example"); found={}
    if table:
        for tr in table.select("tbody tr"):
            cells=tr.find_all("td"); link=tr.find("a",href=lambda x: x and "player_code=" in x)
            if not cells or not link: continue
            pid=link.get("href").split("player_code=")[-1].split("&")[0]; rank=cells[0].get_text(" ",strip=True)
            try: rank=int(rank)
            except ValueError: continue
            if pid in target_ids: found[pid]=rank
    return {"schema_version":"neo_ok_open_official_klpga_ranking_v1","ranking_category":"K-RANKING (official weekly KLPGA ranking)","ranking_date":"2026-W35","official_source":RANK_URL,"retrieved_at":now(),"records":[{"player_id":pid,"official_rank":found.get(pid),"validation_state":"PASS" if pid in found else "UNAVAILABLE"} for pid in sorted(target_ids)]}

def main():
    entry=json.loads(ENTRY_PATH.read_text(encoding="utf-8")); entries=entry["entries"]; ids={str(e["player_id"]) for e in entries}; retrieved=now()
    profiles=collect_profiles(entries); ranking=collect_rankings(ids); rank_by={x["player_id"]:x["official_rank"] for x in ranking["records"]}
    perf=json.loads((CONTENT/"OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json").read_text(encoding="utf-8")); pby={str(p["player_id"]):p for p in perf["profiles"]}
    sgvals={pid: (((pby.get(pid,{}).get("windows") or {}).get("recent5") or {}).get("components") or {}).get("total",{}).get("mean") for pid in ids}
    sg_order=sorted(ids,key=lambda pid:(-(sgvals[pid] if sgvals[pid] is not None else float("-inf")),pid)); sg_rank={pid:(i+1 if sgvals[pid] is not None else None) for i,pid in enumerate(sg_order)}
    # Existing model, in-memory copy only: canonical DB is never modified.
    prob={}
    with sqlite3.connect(f"file:{DB}?mode=ro",uri=True) as sc:
        with sqlite3.connect(":memory:") as c:
            sc.backup(c); c.executemany("INSERT OR REPLACE INTO tournament_entry (game_code,player_code,player_name_display,nationality,qualification_category,qualification_reason,source,collected_at) VALUES (?,?,?,?,?,?,?,?)",[("2026120001",str(e["player_id"]),str(e.get("player_name") or ""),e.get("nationality"),e.get("qualification_category"),e.get("qualification_reason"),"frozen_entry_snapshot",entry["retrieved_at"]) for e in entries])
            sys.path.insert(0,str(DB.parent.parent/"src")); from klpga.models.inference import run_inference
            result=run_inference(c,"2026120001",cutoff_date_arg="2026-09-04",tournament_name_arg="OK저축은행 읏맨 오픈"); prob={str(x.player_code):x.win_probability for x in result.predictions}
    forecast={"schema_version":"neo_ok_open_pre_win_forecast_v1","game_code":"2026120001","cutoff":"2026-09-04T00:00:00+09:00","model_version":"M4","model_features":["prior_avg_round_score_to_par","prior_recent_form_10"],"future_data_excluded":True,"normalization":{"sum":sum(prob.values()),"entrant_count":len(prob)},"source":"existing validated NEO inference; in-memory join to frozen entry snapshot","records":[{"player_id":pid,"win_probability":prob.get(pid),"provenance":{"source_artifact":"existing M4 inference","cutoff":"2026-09-04T00:00:00+09:00"}} for pid in sorted(ids)]}
    master=[]
    for prof in profiles:
        pid=prof["player_id"]
        provenance={"entry":"OK_OPEN_2026_ENTRY_SNAPSHOT.json","profile":prof["official_source"],"ranking":RANK_URL,"performance":"OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json","forecast":"OK_OPEN_2026_PRE_WIN_FORECAST.json"}
        field_provenance={k:{"source_artifact":v,"official_source_reference":prof["official_source"] if k.startswith("current_") else (RANK_URL if k=="official_klpga_rank" else None),"retrieved_at":prof["retrieved_at"],"cutoff":"2026-09-04T00:00:00+09:00","validation_state":"PASS" if v is not None else "UNAVAILABLE"} for k,v in {"current_official_player_name":prof["current_official_player_name"],"current_player_status":prof["current_player_status"],"current_official_sponsor":prof["current_official_sponsor"],"official_klpga_rank":rank_by.get(pid),"sg_total_rank":sg_rank.get(pid),"win_probability":prob.get(pid)}.items()}
        master.append({**prof,"official_klpga_rank":rank_by.get(pid),"neo_pre_rank":None,"sg_total_rank":sg_rank.get(pid),"top20_probability":None,"top10_probability":None,"top5_probability":None,"win_probability":prob.get(pid),"validation_status":"PARTIAL_UPSTREAM" if prof["current_official_player_name"] and prob.get(pid) is not None else "UPSTREAM_GAP","provenance":provenance,"field_provenance":field_provenance})
    (CONTENT/"OK_OPEN_2026_CURRENT_PLAYER_MASTER.json").write_text(json.dumps({"schema_version":"neo_ok_open_current_player_master_v1","game_code":"2026120001","entry_count":len(master),"records":master},ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    (CONTENT/"OK_OPEN_2026_OFFICIAL_KLPGA_RANKING.json").write_text(json.dumps(ranking,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    (CONTENT/"OK_OPEN_2026_PRE_WIN_FORECAST.json").write_text(json.dumps(forecast,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    evidence={"schema_version":"neo_ok_open_neo_pre_ranking_evidence_v1","game_code":"2026120001","cutoff":perf["cutoff"],"neo_pre_rank":None,"ranking_status":"PENDING_INDEPENDENT_METHOD_APPROVAL","records":[{"player_id":p["player_id"],"performance":p.get("windows"),"dimensions":p.get("dimensions"),"direction":p.get("direction"),"consistency":p.get("consistency"),"composition":p.get("composition"),"coverage":p.get("coverage"),"win_probability":prob.get(p["player_id"])} for p in perf["profiles"]]}
    (CONTENT/"OK_OPEN_2026_NEO_PRE_RANKING_EVIDENCE.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    sgdoc={"schema_version":"neo_ok_open_pre_sg_total_rank_v1","game_code":"2026120001","cutoff":perf["cutoff"],"window":"recent5 cumulative SG","scope":"tournament_cumulative arithmetic mean of completed single-round SG","minimum_sample":1,"tie_rule":"ascending player_id after equal mean","missing_rule":"NULL when no validated recent5 total mean","records":[{"player_id":pid,"sg_total_mean":sgvals[pid],"sg_total_rank":sg_rank[pid],"provenance":"OK_OPEN_2026_PRE_PERFORMANCE_SNAPSHOT.json"} for pid in sorted(ids)]}
    (CONTENT/"OK_OPEN_2026_PRE_SG_TOTAL_RANK.json").write_text(json.dumps(sgdoc,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    report={"entrant_count":len(master),"identity_count":sum(bool(x["current_official_player_name"]) for x in master),"current_name_coverage":sum(bool(x["current_official_player_name"]) for x in master),"current_status_coverage":sum(bool(x["current_player_status"]) for x in master),"sponsor_coverage":sum(bool(x["current_official_sponsor"]) for x in master),"klpga_rank_coverage":sum(x["official_klpga_rank"] is not None for x in master),"neo_rank_coverage":0,"sg_total_rank_coverage":sum(x["sg_total_rank"] is not None for x in master),"top20_coverage":0,"top10_coverage":0,"top5_coverage":0,"win_coverage":sum(x["win_probability"] is not None for x in master),"neo_pre_rank_status":"PENDING_INDEPENDENT_METHOD_APPROVAL","website_generation":"NOT RUN"}
    (CONTENT/"OK_OPEN_2026_PRE_PUBLIC_MASTER_VALIDATION.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    print(json.dumps(report,ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
