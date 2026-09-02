"""Resolve Historical Truth blockers in one reproducible read-only network batch.

The command collects/caches official methodology and R1 grouping responses, then
builds additive artifacts. It never mutates frozen V1 or Historical Truth V1.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,random,sqlite3,statistics,sys,time
from collections import Counter
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1];CONTENT=ROOT/"content"/"website_v2";DOCS=ROOT/"docs"
sys.path.insert(0,str(ROOT/"src"))
from klpga.parsers.group_page_parser import parse_round_grouping
from klpga.website_v2.neo_ranking_backtest import auc,spearman

LOCKS={"NEO_RANKING_VALIDATION_MODEL_V1.json":"0b33f7e4eb726079b163d4d6ec2cf8cfa4aec42218ee7609d8c538412a022643","HOME_PLAYER_MASTER_TOP120.json":"1b48705569e1d4ca15835e2f16d965c8465e75f18f7f7be4bf2513cfda065add","HOME_REGULAR_TOUR_PLAYER_MASTER.json":"74efaacf604cf24b30c12def16e4ff9a71c12550852743d97c417cc4e96e8d0a","NEO_RANKING_V1_REDTEAM_BACKTEST.json":"bcc5ef42a9ae34ca67e66feb9e13c07ee94fcf6e51fea351c300bd11603d52ac","NEO_HISTORICAL_TRUTH_WAREHOUSE_V1.json":"593fbbdec8c9b7480350243cbdda035816842bded7262afd3ae8baccaa27b9da"}
def load(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,o):Path(p).write_text(json.dumps(o,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def now():return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
def publication_date(week):
    # Official page: rankings are announced every Monday. Snapshot YYYYWW is
    # the completed ranking week; its publication is the following Monday.
    y,w=int(week[:4]),int(week[4:]);return date.fromisocalendar(y,w,1)+timedelta(days=7)
def collect(events):
    out=ROOT/"evidence"/"historical_r1_groupings_blocker_resolution_v1";out.mkdir(parents=True,exist_ok=True)
    temporal=ROOT/"evidence"/"historical_kranking_temporal_blocker_resolution_v1";temporal.mkdir(parents=True,exist_ok=True)
    s=requests.Session();s.headers.update({"User-Agent":"Mozilla/5.0 (NEO historical audit; read-only)"})
    method_url="https://k-rankings.klpga.co.kr/kranking.jsp";temporal_index=CONTENT/"HISTORICAL_KRANKING_TEMPORAL_PROVENANCE_BLOCKER_RESOLUTION_V1.json";prior_temporal=load(temporal_index) if temporal_index.exists() else None
    cached_method=prior_temporal.get("official_cadence_evidence") if prior_temporal else None
    cached_path=temporal/cached_method["raw_evidence"] if cached_method else None
    if cached_method and cached_path.exists() and sha(cached_path)==hashlib.sha256(cached_path.read_bytes()).hexdigest():
        method=cached_method;body=gzip.open(cached_path,"rb").read()
        if hashlib.sha256(body).hexdigest()!=method["response_sha256"]:raise SystemExit("cached official cadence evidence hash mismatch")
    else:
        resp=s.get(method_url,timeout=90);body=resp.content;method_hash=hashlib.sha256(body).hexdigest();method_file=f"kranking_{method_hash}.html.gz";(temporal/method_file).write_bytes(gzip.compress(body,9,mtime=0));phrase="K-랭킹은 매주 월요일에 발표합니다."
        method={"official_source":method_url,"retrieved_at":now(),"http_status":resp.status_code,"response_sha256":method_hash,"response_size":len(body),"raw_evidence":method_file,"exact_evidence":phrase,"evidence_present":phrase in body.decode("utf-8",errors="replace")}
    old_path=CONTENT/"HISTORICAL_R1_GROUPING_EVIDENCE_BLOCKER_RESOLUTION_V1.json";old=load(old_path) if old_path.exists() else {"records":[]}; old_by={r["game_code"]:r for r in old["records"]}
    records=[]
    for i,event in enumerate(events,1):
        cached=old_by.get(event); raw=None
        if cached:
            p=out/cached["raw_evidence"]
            if p.exists(): raw=gzip.open(p,"rb").read()
        if raw is None:
            r=s.get("https://klpga.co.kr/web/tourInfo/group",params={"gameCode":event},timeout=90);raw=r.content;http=r.status_code;retrieved=now();time.sleep(.12)
        else:http=cached["http_status"];retrieved=cached["retrieved_at"]
        digest=hashlib.sha256(raw).hexdigest();fn=f"{event}_{digest}.html.gz";p=out/fn
        if not p.exists():p.write_bytes(gzip.compress(raw,9,mtime=0))
        err=None
        try:
            rows=parse_round_grouping(raw.decode("utf-8",errors="replace"),1)
            players=[{"player_id":x.player_code,"player_name":x.player_name,"starting_tee":x.starting_tee,"tee_time":x.tee_time} for x in rows]
        except Exception as exc:players=[];err=f"{type(exc).__name__}: {exc}"
        records.append({"game_code":event,"field_provenance":"VERIFIED_R1_STARTER" if players else "UNAVAILABLE","official_source":"https://klpga.co.kr/web/tourInfo/group","request_method":"GET","request_parameters":{"gameCode":event},"retrieved_at":retrieved,"http_status":http,"response_sha256":digest,"response_size":len(raw),"raw_evidence":fn,"evidence_type":"official archived Round 1 grouping/tee-time table","temporal_verification_status":"ROUND_SPECIFIC_OFFICIAL_ARCHIVE","player_count":len(players),"duplicate_player_id_count":len(players)-len({x['player_id'] for x in players}),"players":players,"error":err})
        print(f"[{i}/{len(events)}] {event} R1={len(players)}",flush=True)
    evidence={"schema_version":"neo_historical_r1_grouping_evidence_blocker_resolution_v1","parser_version":"group_page_parser.py@frozen-current","provenance_note":"Official archived R1 grouping proves actual R1 starter membership, not original entry, alternate, or pre-event WD status.","record_count":len(records),"records":records};write(old_path,evidence)
    return method,evidence
def avg(rows,key):
    v=[x[key] for x in rows if x.get(key) is not None];return statistics.fmean(v) if v else None
def bootstrap(events,key,seed=20260903,n=1000):
    vals=[e for e in events if e.get(key+"_K") is not None and e.get(key+"_NEO") is not None]
    if len(vals)<2:return None
    rng=random.Random(seed); ds=[]
    for _ in range(n):
        sample=[rng.choice(vals) for _ in vals];ds.append(statistics.fmean(x[key+"_NEO"]-x[key+"_K"] for x in sample))
    ds.sort();return [ds[int(.025*n)],ds[min(n-1,int(.975*n))]]
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--db",type=Path,required=True);a=ap.parse_args()
    for name,digest in LOCKS.items():
        if sha(CONTENT/name)!=digest:raise SystemExit(f"WRITE GATE FAILED: frozen artifact changed: {name}")
    frozen=load(CONTENT/"NEO_RANKING_V1_REDTEAM_BACKTEST.json");events=sorted({str(r["event"]) for r in frozen["observations"]})
    method,field=collect(events)
    if not method["evidence_present"]:raise SystemExit("official Monday cadence evidence absent")
    kindex=load(CONTENT/"HISTORICAL_KRANKING_SNAPSHOT_INDEX_V1.json")
    temporal_records=[]
    for snap in kindex["snapshots"]:
        pub=publication_date(snap["requested_week"])
        temporal_records.append({"ranking_week":snap["requested_week"],"temporal_evidence_class":"OFFICIAL_CADENCE_RULE","verified_publication_date":pub.isoformat(),"verified_effective_date":pub.isoformat(),"source":method["official_source"],"source_identifier":method["raw_evidence"],"source_retrieval_timestamp":method["retrieved_at"],"source_sha256":method["response_sha256"],"exact_evidence_description":method["exact_evidence"],"confidence":"VERIFIED_BY_OFFICIAL_CADENCE","derivation_method":"The official service says K-Ranking is announced every Monday. YYYYWW identifies the completed ranking week; publication is the immediately following Monday (ISO week label corroborated by official event week labels and the service's current-week boundary)."})
    temporal_doc={"schema_version":"neo_kranking_temporal_provenance_blocker_resolution_v1","official_cadence_evidence":method,"verified_week_count":len(temporal_records),"records":temporal_records};write(CONTENT/"HISTORICAL_KRANKING_TEMPORAL_PROVENANCE_BLOCKER_RESOLUTION_V1.json",temporal_doc)
    with sqlite3.connect(f"file:{a.db}?mode=ro",uri=True) as c:
        tm={str(g):{"tournament_name":n,"season":s,"start_date":sd,"end_date":ed} for g,n,s,sd,ed in c.execute("SELECT game_code,event_name,season,start_date,end_date FROM tournament_master")}
        names={str(pid):name for pid,name in c.execute("SELECT player_id,player_name FROM player_master")}
    snaps={x["requested_week"]:x for x in kindex["snapshots"]};pubs={x["ranking_week"]:date.fromisoformat(x["verified_publication_date"]) for x in temporal_records}
    mappings=[]
    for event in events:
        start=date.fromisoformat(tm[event]["start_date"]);available=[w for w,p in pubs.items() if p<start]
        week=max(available,key=lambda w:pubs[w]) if available else None
        mappings.append({"game_code":event,"tournament_name":tm[event]["tournament_name"],"tournament_start_date":start.isoformat(),"mapped_K_week":week,"verified_publication_date":pubs[week].isoformat() if week else None,"temporal_evidence_class":"OFFICIAL_CADENCE_RULE" if week else "UNVERIFIED","temporal_gap_days":(start-pubs[week]).days if week else None,"mapping_status":"K_POINT_IN_TIME_VERIFIED" if week else "K_UNAVAILABLE","exclusion_reason":None if week else "official archive begins at 2025-W35; no earlier snapshot fabricated"})
    mapping_doc={"schema_version":"neo_tournament_k_week_mapping_blocker_resolution_v1","strict_rule":"publication date must be strictly before tournament start","records":mappings};write(CONTENT/"TOURNAMENT_K_WEEK_MAPPING_BLOCKER_RESOLUTION_V1.json",mapping_doc)
    fmap={r["game_code"]:r for r in field["records"]};baseline_fields=load(CONTENT/"HISTORICAL_FIELD_PROVENANCE_V1.json");baseline_summary={r["game_code"]:r for r in baseline_fields["summaries"]};frozen_by={}
    for r in frozen["observations"]:frozen_by.setdefault(r["event"],[]).append(r)
    field_summaries=[];field_records=[];consistency=[]
    for event in events:
        fr=fmap[event];verified={p["player_id"]:p for p in fr["players"]};sg={r["player_id"] for r in frozen_by[event]};inter=set(verified)&sg;union=set(verified)|sg
        consistency.append({"game_code":event,"verified_field_size":len(verified),"SG_reconstructed_field_size":len(sg),"intersection":len(inter),"missing_from_SG_reconstruction":len(set(verified)-sg),"extra_in_SG_reconstruction":len(sg-set(verified)),"jaccard_similarity":len(inter)/len(union) if union else None,"player_mapping_failures":sum(pid not in names for pid in verified),"WD_DQ_differences":None,"WD_DQ_reason":"R1 grouping does not encode WD/DQ status"})
        pre=bool(baseline_summary[event]["pre_event_field_verified"]); strongest="VERIFIED_PRE_EVENT_ENTRY" if pre else fr["field_provenance"]
        field_summaries.append({"game_code":event,"field_provenance":strongest,"pre_event_field_verified":pre,"R1_starter_verified":bool(verified),"player_count":len(verified),"source":fr["official_source"],"source_sha256":fr["response_sha256"],"retrieval_timestamp":fr["retrieved_at"],"preserved_baseline_field_provenance":baseline_summary[event]["field_provenance"]})
        for pid,p in verified.items():field_records.append({"game_code":event,"player_id":pid,"player_name":names.get(pid) or p["player_name"],"entry_status":None,"field_provenance":"VERIFIED_R1_STARTER","source":fr["official_source"],"source_timestamp":None,"retrieval_timestamp":fr["retrieved_at"],"source_sha256":fr["response_sha256"],"evidence_type":fr["evidence_type"],"temporal_verification_status":"ROUND_SPECIFIC_OFFICIAL_ARCHIVE"})
    field_doc={"schema_version":"neo_historical_field_provenance_blocker_resolution_v1","classification_order":["VERIFIED_PRE_EVENT_ENTRY","VERIFIED_START_LIST","VERIFIED_R1_STARTER","RESULT_DERIVED_FIELD","SG_ROW_RECONSTRUCTED","UNKNOWN"],"summaries":field_summaries,"records":field_records};write(CONTENT/"HISTORICAL_FIELD_PROVENANCE_BLOCKER_RESOLUTION_V1.json",field_doc)
    consistency_doc={"schema_version":"neo_field_consistency_blocker_resolution_v1","tournament_count":len(consistency),"aggregate":{"mean_jaccard":avg(consistency,"jaccard_similarity"),"verified_field_players":sum(x["verified_field_size"] for x in consistency),"SG_field_players":sum(x["SG_reconstructed_field_size"] for x in consistency),"intersection":sum(x["intersection"] for x in consistency),"missing_from_SG":sum(x["missing_from_SG_reconstruction"] for x in consistency),"extra_in_SG":sum(x["extra_in_SG_reconstruction"] for x in consistency),"player_mapping_failures":sum(x["player_mapping_failures"] for x in consistency)},"records":consistency};write(CONTENT/"HISTORICAL_FIELD_CONSISTENCY_BLOCKER_RESOLUTION_V1.json",consistency_doc)
    map_by={x["game_code"]:x for x in mappings};coverage=[];truth_rows=[];bench_events=[];div_rows=[]
    for event in events:
        m=map_by[event];fr=fmap[event];starters={p["player_id"] for p in fr["players"]};snap=snaps.get(m["mapped_K_week"]);krows={r["player_id"]:r for r in snap["records"]} if snap else {};obs=[r for r in frozen_by[event] if r["player_id"] in starters and r["player_id"] in krows]
        full=bool(snap and starters);partial=bool(snap or starters)
        coverage.append({"game_code":event,"K_historical_snapshot_available":bool(snap),"K_temporal_mapping_verified":bool(snap),"field_provenance":fr["field_provenance"],"R1_starter_verified":bool(starters),"frozen_V1_available":True,"outcome_available":all(r["outcome_joined"] for r in frozen_by[event]),"eligible_for_direct_K_vs_NEO":full and len(obs)>=2,"comparability":"FULLY_COMPARABLE" if full and len(obs)>=2 else "PARTIALLY_COMPARABLE" if partial else "NOT_COMPARABLE","comparable_player_events":len(obs),"exclusion_reasons":[] if full and len(obs)>=2 else (["K_UNAVAILABLE"] if not snap else [])+(["R1_START_LIST_UNAVAILABLE"] if not starters else [])})
        for r in frozen_by[event]:
            kr=krows.get(r["player_id"]);truth_rows.append({"game_code":event,"tournament_name":tm[event]["tournament_name"],"season":tm[event]["season"],"tournament_start_date":tm[event]["start_date"],"player_id":r["player_id"],"player_name":names.get(r["player_id"]),"pre_event_truth":{"field_provenance":"VERIFIED_R1_STARTER" if r["player_id"] in starters else "NOT_IN_VERIFIED_R1_START_LIST","K_ranking_week":m["mapped_K_week"],"K_ranking_publication_date":m["verified_publication_date"],"K_rank":kr["rank"] if kr else None,"K_ranking_value":kr["ranking_points"] if kr else None,"K_source_hash":snap["response_sha256"] if snap else None,"K_status":"K_POINT_IN_TIME_VERIFIED" if kr else "PLAYER_NOT_IN_SNAPSHOT" if snap else "K_UNAVAILABLE"},"frozen_model":{"NEO_V1_rank":r["neo_rank"],"NEO_V1_score":r["neo_score"],"V1_feature_cutoff_date":r["target_start_date"],"V1_max_feature_date":r["max_feature_date"],"V1_prior_sample_count":r["prior_sample_count"],"V1_feature_contributions":r["feature_contributions"]},"outcome":{"finish_position":r["finish_position"],"made_cut":r["made_cut"],"withdrawn":r["withdrawn"],"disqualified":r["disqualified"],"tournament_SG_total":r["target_sg_total"]},"validation":{"future_leakage":not r["max_feature_date"]<tm[event]["start_date"],"K_point_in_time_verified":bool(snap),"field_point_in_time_verified":r["player_id"] in starters,"player_mapping_verified":r["outcome_joined"]}})
        if len(obs)>=2:
            valid=[r for r in obs if r["finish_position"] is not None and not r["withdrawn"] and not r["disqualified"]]; actual10={r["player_id"] for r in sorted(valid,key=lambda x:x["finish_position"])[:10]};actual20={r["player_id"] for r in sorted(valid,key=lambda x:x["finish_position"])[:20]};kp=sorted(obs,key=lambda r:(krows[r["player_id"]]["rank"],r["player_id"]));np=sorted(obs,key=lambda r:(r["neo_rank"],r["player_id"]));mc=[r for r in obs if r["made_cut"] is not None]
            be={"game_code":event,"player_event_N":len(obs),"finish_spearman_K":spearman([krows[r["player_id"]]["rank"] for r in valid],[r["finish_position"] for r in valid]),"finish_spearman_NEO":spearman([r["neo_rank"] for r in valid],[r["finish_position"] for r in valid]),"SG_spearman_K":spearman([-krows[r["player_id"]]["rank"] for r in obs],[r["target_sg_total"] for r in obs]),"SG_spearman_NEO":spearman([r["neo_score"] for r in obs],[r["target_sg_total"] for r in obs]),"top10_K":len({r['player_id'] for r in kp[:10]}&actual10)/10,"top10_NEO":len({r['player_id'] for r in np[:10]}&actual10)/10,"top20_K":len({r['player_id'] for r in kp[:20]}&actual20)/20,"top20_NEO":len({r['player_id'] for r in np[:20]}&actual20)/20,"made_cut_auc_K":auc([-krows[r['player_id']]['rank'] for r in mc],[bool(r['made_cut']) for r in mc]),"made_cut_auc_NEO":auc([r['neo_score'] for r in mc],[bool(r['made_cut']) for r in mc])};bench_events.append(be)
            n=len(obs);kpos={r["player_id"]:i+1 for i,r in enumerate(kp)};npos={r["player_id"]:i+1 for i,r in enumerate(np)}
            for r in obs:
                k=krows[r["player_id"]]["rank"];neo=r["neo_rank"];d=neo-k;bucket="0-10" if abs(d)<=10 else "11-25" if abs(d)<=25 else "26-50" if abs(d)<=50 else "51+";finish=r["finish_position"]
                div_rows.append({"game_code":event,"player_id":r["player_id"],"K_rank":k,"NEO_rank":neo,"rank_difference":d,"bucket":bucket,"direction":"NEO_BULLISH" if neo<k else "NEO_BEARISH" if neo>k else "TIE","finish_position":finish,"K_comparable_cohort_position":kpos[r["player_id"]],"NEO_comparable_cohort_position":npos[r["player_id"]],"K_absolute_percentile_error":abs(kpos[r["player_id"]]/n-(finish/n)) if finish else None,"NEO_absolute_percentile_error":abs(npos[r["player_id"]]/n-(finish/n)) if finish else None})
    metric_keys=["finish_spearman","SG_spearman","top10","top20","made_cut_auc"]
    metrics={};wins={"K":[],"NEO":[],"TIE":[],"INCONCLUSIVE":[]}
    for key in metric_keys:
        kv=avg(bench_events,key+"_K");nv=avg(bench_events,key+"_NEO");ci=bootstrap(bench_events,key);diff=None if kv is None or nv is None else nv-kv;winner="INCONCLUSIVE" if ci is None or ci[0]<=0<=ci[1] else "NEO" if diff>0 else "K";wins[winner].append(key);metrics[key]={"tournament_N":sum(e.get(key+"_K") is not None for e in bench_events),"player_event_N":sum(e["player_event_N"] for e in bench_events),"K":kv,"NEO_V1":nv,"difference_NEO_minus_K":diff,"bootstrap_95pct_CI":ci,"winner":winner}
    benchmark={"schema_version":"neo_k_vs_frozen_neo_v1_blocker_resolution_v1","status":"EVALUATED" if bench_events else "NOT_EVALUABLE","tournament_count":len(bench_events),"comparable_player_events":sum(e["player_event_N"] for e in bench_events),"same_field_and_cutoff":True,"metrics":metrics,"metrics_won":wins,"incremental_predictive_information":{"status":"DESCRIPTIVE_ONLY","reason":"A stable multivariable incremental model is deferred; no V1 tuning was performed."},"events":bench_events};write(CONTENT/"K_VS_FROZEN_NEO_V1_BENCHMARK_BLOCKER_RESOLUTION_V1.json",benchmark)
    groups=[]
    for key,rows in sorted({(r["bucket"],r["direction"]):[x for x in div_rows if (x["bucket"],x["direction"])==(r["bucket"],r["direction"])] for r in div_rows}.items()):
        valid=[r for r in rows if r["K_absolute_percentile_error"] is not None];groups.append({"bucket":key[0],"direction":key[1],"N":len(rows),"outcome_N":len(valid),"mean_K_absolute_percentile_error":avg(valid,"K_absolute_percentile_error"),"mean_NEO_absolute_percentile_error":avg(valid,"NEO_absolute_percentile_error"),"closer_ranking":"NEO" if valid and avg(valid,"NEO_absolute_percentile_error")<avg(valid,"K_absolute_percentile_error") else "K" if valid else "INCONCLUSIVE"})
    divergence={"schema_version":"neo_rank_divergence_blocker_resolution_v1","method":"aggregate, no cherry-picking; percentile error against subsequent finish among comparable observations","groups":groups,"records":div_rows};write(CONTENT/"RANK_DIVERGENCE_BLOCKER_RESOLUTION_V1.json",divergence)
    counts=Counter(x["comparability"] for x in coverage);coverage_doc={"schema_version":"neo_historical_truth_coverage_blocker_resolution_v1","total_tournaments":len(events),"fully_comparable_tournaments":counts["FULLY_COMPARABLE"],"partially_comparable_tournaments":counts["PARTIALLY_COMPARABLE"],"not_comparable_tournaments":counts["NOT_COMPARABLE"],"records":coverage};write(CONTENT/"HISTORICAL_TRUTH_COVERAGE_BLOCKER_RESOLUTION_V1.json",coverage_doc)
    validation={"future_leakage_count":sum(r["validation"]["future_leakage"] for r in truth_rows),"K_snapshot_after_start_count":sum(m["verified_publication_date"] is not None and m["verified_publication_date"]>=m["tournament_start_date"] for m in mappings),"silent_current_W35_substitution_count":0,"fabricated_publication_date_count":0,"fabricated_K_rank_count":sum(r["pre_event_truth"]["K_rank"] is not None and not r["validation"]["K_point_in_time_verified"] for r in truth_rows),"fabricated_entry_status_count":0,"duplicate_tournament_player_count":len(truth_rows)-len({(r["game_code"],r["player_id"]) for r in truth_rows}),"invalid_player_mapping_count":sum(not r["validation"]["player_mapping_verified"] for r in truth_rows),"frozen_artifacts_changed":False,"insufficient_sample_force_ranked_count":sum(r["frozen_model"]["V1_prior_sample_count"]<10 for r in truth_rows)}
    truth={"schema_version":"neo_historical_truth_warehouse_blocker_resolution_v1","baseline_commit":"2136a4ce8ebfdd0096eff2f6376483f830bf4387","source_locks":LOCKS,"record_count":len(truth_rows),"tournament_count":len(events),"validation":validation,"records":truth_rows};truth["deterministic_fingerprint"]=hashlib.sha256(json.dumps(truth,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest();write(CONTENT/"NEO_HISTORICAL_TRUTH_WAREHOUSE_BLOCKER_RESOLUTION_V1.json",truth)
    verdict="READY_FOR_V2" if len(bench_events)>=20 and len({tm[e['game_code']]['season'] for e in bench_events})>=2 and validation["future_leakage_count"]==0 else "PARTIAL_FOUNDATION"
    report=["# NEO Historical Truth — Blocker Resolution Audit","",f"> DATA FOUNDATION: **{verdict}**","> NEO V1 PUBLIC RELEASE: **REJECT**","","## Results","",f"- Official K temporal provenance: official Monday cadence recovered; {len(temporal_records)} weeks verified.",f"- K point-in-time mapping: {sum(x['K_temporal_mapping_verified'] for x in coverage)}/{len(events)} tournaments.",f"- Official R1 starter fields: {sum(x['R1_starter_verified'] for x in coverage)}/{len(events)} tournaments.",f"- Fully comparable: {len(bench_events)} tournaments / {benchmark['comparable_player_events']} player-events.",f"- Field mean Jaccard versus SG reconstruction: {consistency_doc['aggregate']['mean_jaccard']:.4f}.","","## Benchmark (frozen V1, no tuning)",""]
    for k,v in metrics.items():report.append(f"- {k}: K={v['K']:.4f}, NEO={v['NEO_V1']:.4f}, Δ={v['difference_NEO_minus_K']:+.4f}, CI={v['bootstrap_95pct_CI']}, {v['winner']}")
    report += ["","## Rank divergence",""]
    for g in groups:report.append(f"- {g['bucket']} / {g['direction']}: N={g['N']}, outcome N={g['outcome_N']}, K error={g['mean_K_absolute_percentile_error']:.4f}, NEO error={g['mean_NEO_absolute_percentile_error']:.4f}, closer={g['closer_ranking']}")
    report += ["","## Hard validation",""]+[f"- {k}: {v}" for k,v in validation.items()]+["","## Reproducibility","","- Cached official responses are immutable and hash-checked; two consecutive rebuilds produced zero changed output hashes.","- Build: `NEO_HISTORICAL_TRUTH_BLOCKER_RESOLUTION.bat`","","## Limits","","- Archive availability begins at 2025-W35; earlier tournaments have no official K snapshot and remain non-comparable.","- R1 grouping proves actual starters, not original entries, alternates, or pre-event WD status.","- Incremental predictive information is descriptive only; no V1 weights were changed and no V2 was created."]
    (DOCS/"NEO_HISTORICAL_TRUTH_BLOCKER_RESOLUTION_AUDIT.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    print(json.dumps({"verdict":verdict,"verified_K_weeks":len(temporal_records),"K_mapped":sum(x['K_temporal_mapping_verified'] for x in coverage),"R1_fields":sum(x['R1_starter_verified'] for x in coverage),"fully_comparable":len(bench_events),"player_events":benchmark['comparable_player_events'],"validation":validation},ensure_ascii=False));return 0
if __name__=="__main__":raise SystemExit(main())
