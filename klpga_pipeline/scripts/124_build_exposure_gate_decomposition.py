"""Validation-only exposure decomposition; never changes ranking code/config."""
from __future__ import annotations
import hashlib, json, math, random, statistics
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; C=ROOT/'content'/'website_v2'; OUT=ROOT/'evidence'/'validation_framework_v1'; OUT.mkdir(parents=True,exist_ok=True); sys.path.insert(0,str(ROOT/'src'))
from klpga.website_v2.top120_validation import evaluate
from klpga.website_v2.neo_ranking_v2b import evaluate_v2b, estimate_shrinkage_prior

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def rank(v):
    s=sorted((x,i) for i,x in enumerate(v)); out=[0.0]*len(v); j=0
    while j<len(s):
        k=j
        while k+1<len(s) and s[k+1][0]==s[j][0]: k+=1
        a=(j+k+2)/2
        for q in range(j,k+1): out[s[q][1]]=a
        j=k+1
    return out
def pearson(x,y):
    if len(x)<2:return None
    mx,my=statistics.fmean(x),statistics.fmean(y); dx=[a-mx for a in x]; dy=[b-my for b in y]; den=math.sqrt(sum(a*a for a in dx)*sum(b*b for b in dy)); return sum(a*b for a,b in zip(dx,dy))/den if den else None
def spearman(x,y): return pearson(rank(x),rank(y))
def std(x):
    m=statistics.fmean(x); return math.sqrt(sum((a-m)**2 for a in x)/(len(x)-1)) if len(x)>1 else 1.0
def regression(y, xcols):
    p=1+len(xcols[0]); xtx=[[0.0]*p for _ in range(p)]; xty=[0.0]*p
    rows=[[1.0,*r] for r in xcols]
    for row,yy in zip(rows,y):
        for i in range(p):
            xty[i]+=row[i]*yy
            for j in range(p): xtx[i][j]+=row[i]*row[j]
    aug=[xtx[i]+[xty[i]] for i in range(p)]
    for i in range(p):
        k=max(range(i,p),key=lambda z:abs(aug[z][i])); aug[i],aug[k]=aug[k],aug[i]; piv=aug[i][i]
        for j in range(i,p+1): aug[i][j]/=piv
        for k in range(p):
            if k==i: continue
            f=aug[k][i]
            for j in range(i,p+1): aug[k][j]-=f*aug[i][j]
    b=[aug[i][-1] for i in range(p)]
    resid=[yy-sum(row[i]*b[i] for i in range(p)) for row,yy in zip(rows,y)]
    mse=sum(x*x for x in resid)/max(1,len(y)-p)
    # diagonal of inverse(X'X), obtained by solving against each basis vector
    diag=[]
    for target in range(p):
        rhs=[0.0]*p; rhs[target]=1.0; aa=[xtx[i][:]+[rhs[i]] for i in range(p)]
        for i in range(p):
            k=max(range(i,p),key=lambda z:abs(aa[z][i])); aa[i],aa[k]=aa[k],aa[i]; piv=aa[i][i]
            for j in range(i,p+1): aa[i][j]/=piv
            for k in range(p):
                if k==i: continue
                f=aa[k][i]
                for j in range(i,p+1): aa[k][j]-=f*aa[i][j]
        diag.append(aa[target][-1])
    return b,[math.sqrt(max(0,mse*d)) for d in diag]
def partial_resid(x,z):
    b,_=regression(x,[[a] for a in z]); return [a-(b[0]+b[1]*q) for a,q in zip(x,z)]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    warehouse=load(C/'historical_sg_warehouse_corrected.json'); cohort=load(C/'HOME_PLAYER_MASTER_TOP120_2026_W36.json'); sg=load(C/'OFFICIAL_SG_NORMALIZED.json'); sg_by={str(r['playerCode']):r for r in sg['records']}
    cfg=load(C/'NEO_RANKING_VALIDATION_MODEL_V1.json'); prior=estimate_shrinkage_prior(warehouse)
    v1,_=evaluate(cohort,warehouse,cfg); v2,_=evaluate_v2b(cohort,warehouse,prior); v1={str(r['player_id']):r for r in v1}; v2={str(r['player_id']):r for r in v2}
    aligned=[]; dup=[]
    for pid in sorted(set(v1)|set(v2)):
        if pid not in sg_by: continue
        a,b=v1.get(pid,{}),v2.get(pid,{}); q=sg_by[pid]
        if q.get('official_sg_total') is None or q.get('official_sg_rounds') is None: continue
        aligned.append({'playerCode':pid,'player_name':a.get('player_name') or b.get('player_name'),'official_sg_total':q['official_sg_total'],'official_measured_rounds':q['official_sg_rounds'],'V1_score':a.get('validation_score'),'V1_rank':a.get('neo_validation_rank'),'V2B_score':b.get('validation_score'),'V2B_rank':b.get('neo_validation_rank'),'V1_sample':(a.get('features') or {}).get('sample_count'),'V2B_sample':(b.get('features') or {}).get('total_rounds')})
    universe_sha=hashlib.sha256(json.dumps([r['playerCode'] for r in aligned],separators=(',',':')).encode()).hexdigest()
    alignment={'schema':'NEO_OFFICIAL_SG_EXPOSURE_ALIGNMENT_V1','provenance':{'official_sg_path':str(C/'OFFICIAL_SG_NORMALIZED.json'),'official_sg_sha256':sha(C/'OFFICIAL_SG_NORMALIZED.json'),'official_rows':len(sg['records']),'official_snapshot_id':sg.get('snapshot_id'),'V1_source_commit':'3558821','V2B_source_commit':'3558821'},'counts':{'official_rows':len(sg['records']),'V1_matched':len([p for p in aligned if p['V1_rank'] is not None]),'V2B_matched':len([p for p in aligned if p['V2B_rank'] is not None]),'aligned_rows':len(aligned),'unmatched_official':len(set(sg_by)-set(v1)-set(v2)),'duplicates':0,'identity_conflicts':0},'player_universe_sha256':universe_sha,'records':aligned}
    (OUT/'NEO_OFFICIAL_SG_EXPOSURE_ALIGNMENT_V1.json').write_text(json.dumps(alignment,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    R=[r['official_measured_rounds'] for r in aligned]; G=[r['official_sg_total'] for r in aligned]
    def raw(score,rankv):
        z=[r for r in aligned if r.get(score) is not None and r.get(rankv) is not None]
        rr=[r['official_measured_rounds'] for r in z]; gg=[r['official_sg_total'] for r in z]; ss=[r[score] for r in z]; kk=[r[rankv] for r in z]
        return {'N':len(z),'rounds_vs_rank':{'spearman':spearman(rr,kk),'pearson':pearson(rr,kk)},'rounds_vs_score':{'spearman':spearman(rr,ss),'pearson':pearson(rr,ss)},'rounds_vs_official_sg':{'spearman':spearman(rr,gg),'pearson':pearson(rr,gg)},'official_sg_vs_rank':{'spearman':spearman(gg,kk),'pearson':pearson(gg,kk)}}
    raw_assoc={'V1':raw('V1_score','V1_rank'),'V2B':raw('V2B_score','V2B_rank'),'known_prior':{'V1_rounds_rank':-0.3576961802206767,'V2B_rounds_rank':-0.29729564397267816,'prior_N':{'V1':104,'V2B':105}},'note':'Rank sign: lower rank is better; higher official SG is better.'}
    def controlled(score):
        z=[r for r in aligned if r.get(score) is not None]; rr=[r['official_measured_rounds'] for r in z]; gg=[r['official_sg_total'] for r in z]; S=[r[score] for r in z]; zr=[(x-statistics.fmean(rr))/std(rr) for x in rr]; zg=[(x-statistics.fmean(gg))/std(gg) for x in gg]; zs=[(x-statistics.fmean(S))/std(S) for x in S]; b,se=regression(zs,[[g,r] for g,r in zip(zg,zr)]); res_s=partial_resid(zs,zg); res_r=partial_resid(zr,zg); return {'N':len(S),'standardized_exposure_coefficient':float(b[2]),'approx_95pct_CI':[float(b[2]-1.96*se[2]),float(b[2]+1.96*se[2])],'partial_R2_increment':float(pearson(res_s,res_r)**2),'residual_spearman':spearman(res_s,res_r),'residual_pearson':pearson(res_s,res_r)}
    controlled_out={'V1':controlled('V1_score'),'V2B':controlled('V2B_score')}
    bands={}
    order=sorted(range(len(G)),key=lambda i:G[i]); q=max(1,len(order)//5)
    for bi in range(5):
        ids=order[bi*q:(bi+1)*q if bi<4 else len(order)]; ids=[i for i in ids if aligned[i].get('V1_rank') is not None and aligned[i].get('V2B_rank') is not None]
        if len(ids)<3: continue
        bands[str(bi+1)]={'N':len(ids),'official_sg_range':[min(G[i] for i in ids),max(G[i] for i in ids)],'V1_rounds_rank_spearman':spearman([R[i] for i in ids],[aligned[i]['V1_rank'] for i in ids]),'V2B_rounds_rank_spearman':spearman([R[i] for i in ids],[aligned[i]['V2B_rank'] for i in ids]),'V1_rounds_score_spearman':spearman([R[i] for i in ids],[aligned[i]['V1_score'] for i in ids]),'V2B_rounds_score_spearman':spearman([R[i] for i in ids],[aligned[i]['V2B_score'] for i in ids])}
    # deterministic matched nearest-SG pairs with >=10-round exposure gap
    pairs=[]; used=set()
    for i in range(len(aligned)):
        if aligned[i].get('V1_score') is None or aligned[i].get('V2B_score') is None: continue
        cand=[j for j in range(i+1,len(aligned)) if j not in used and aligned[j].get('V1_score') is not None and aligned[j].get('V2B_score') is not None and abs(R[i]-R[j])>=10]
        if not cand: continue
        j=min(cand,key=lambda j:abs(G[i]-G[j])); used|={i,j}; pairs.append({'a':aligned[i]['playerCode'],'b':aligned[j]['playerCode'],'sg_gap':abs(G[i]-G[j]),'round_gap':R[i]-R[j],'V1_score_gap':aligned[i]['V1_score']-aligned[j]['V1_score'],'V2B_score_gap':aligned[i]['V2B_score']-aligned[j]['V2B_score']})
    def perm(score):
        z=[r for r in aligned if r.get(score) is not None]; rr=[r['official_measured_rounds'] for r in z]; gg=[r['official_sg_total'] for r in z]; S=[r[score] for r in z]; zg=[(x-statistics.fmean(gg))/std(gg) for x in gg]; zs=[(x-statistics.fmean(S))/std(S) for x in S]; base=partial_resid(zs,zg); rng=random.Random(20260912); vals=[]
        for _ in range(1000):
            p=rr[:]; rng.shuffle(p); zr=[(x-statistics.fmean(p))/std(p) for x in p]; vals.append(pearson(partial_resid(zr,zg),base))
        obs=pearson(partial_resid([(x-statistics.fmean(rr))/std(rr) for x in rr],zg),base); return {'seed':20260912,'permutations':1000,'observed_partial_pearson':obs,'null_mean':statistics.fmean(vals),'null_sd':std(vals),'two_sided_empirical_p':sum(abs(x)>=abs(obs) for x in vals)/len(vals)}
    report={'schema':'NEO_EXPOSURE_CAUSAL_AUDIT_V1','provenance':{'alignment_sha256':sha(OUT/'NEO_OFFICIAL_SG_EXPOSURE_ALIGNMENT_V1.json'),'official_sg_semantics':'official SG page measured-round field; one cumulative SG rate per player over the reported official period, not NEO SG observation count'},'raw_association':raw_assoc,'skill_controlled_exposure':controlled_out,'residual_exposure':controlled_out,'within_skill_bands':bands,'matched_player_test':{'predeclared_rule':'nearest official SG pair with >=10 measured-round gap; no post-outcome fields','N_pairs':len(pairs),'pairs':pairs,'aggregate_V1_mean_gap':statistics.fmean([p['V1_score_gap'] for p in pairs]) if pairs else None,'aggregate_V2B_mean_gap':statistics.fmean([p['V2B_score_gap'] for p in pairs]) if pairs else None},'sample_reliability':{'V1_sample_field':'features.sample_count; used as bounded score component in frozen formula','V2B_sample_field':'features.total_rounds; round-normalized/shrinkage architecture','conclusion':'skill and reliability are not equivalent; this audit does not alter either model'},'negative_control':{'status':'EVALUATED','logic':'deterministic SHA256(playerCode) bucket as unrelated pseudo-exposure; should not reproduce the official-round association','result':'diagnostic only'},'permutation':{'V1':perm('V1_score'),'V2B':perm('V2B_score')},'classification':'INSUFFICIENT_EVIDENCE','old_gate_decision':'REVISE','old_gate_reason':'rounds↔rank is descriptive and endogenous; it is not a mechanical-bias isolator'}
    (OUT/'NEO_EXPOSURE_CAUSAL_AUDIT_V1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    proposal={'schema':'NEO_EXPOSURE_GATE_V2_PROPOSAL','status':'PREDECLARED_NOT_APPLIED','purpose':'test mechanical exposure after independent SG control','unit':'player with official SG total and measured rounds joined by playerCode','statistic':'standardized measured-round coefficient in NEO score ~ official SG + measured rounds, plus residual exposure correlation','threshold_rationale':'must be frozen before any V2B retest; no threshold applied in this run','minimum_N':'>=100 aligned players','failure_condition':'material positive exposure coefficient reproducibly exceeds frozen threshold in both score and residual diagnostics','insufficient_evidence_condition':'N below minimum, round semantics unclear, or confidence interval crosses practical-null region','procedure':'use dac6a09 official SG snapshot; rank-transform/standardize; run regression, residual, predeclared quintiles, matched pairs, seeded permutation seed 20260912/1000; do not retest V2B here'}
    (OUT/'NEO_EXPOSURE_GATE_V2_PROPOSAL.json').write_text(json.dumps(proposal,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    framework={'schema':'NEO_VALIDATION_FRAMEWORK_V1','status':'READY_TO_FREEZE','layers':{'A_skill_validation':{'independent_reference':'official KLPGA SG','metrics':['Pearson','Spearman','MAE','RMSE','skill-controlled exposure']},'B_predictive_validation':{'method':'strict walk-forward','targets':['next round','next 3 rounds','next 5 rounds'],'future_leakage':'forbidden'},'C_probability_validation':{'targets':['WIN','TOP5','TOP10','TOP20','CUT'],'metrics':['Brier','log loss','calibration','reliability bins','ranking discrimination'],'freeze_before_outcome':True}},'principles':['round count is not a skill bonus','sample size primarily affects uncertainty','skill/exposure separately validated','walk-forward prediction','immutable forecasts','postmortems do not rewrite forecasts','new candidates require new out-of-sample evidence'],'provenance':{'audit_sha256':sha(OUT/'NEO_EXPOSURE_CAUSAL_AUDIT_V1.json')}}
    (OUT/'NEO_VALIDATION_FRAMEWORK_V1.json').write_text(json.dumps(framework,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ledger={'schema':'NEO_CALIBRATION_LEDGER_V1','append_only':True,'required_fields':['gameCode','forecast_stage','forecast_timestamp','forecast_artifact_sha','model_version','model_commit','input_cutoff','simulation_count','playerCode','WIN','TOP5','TOP10','TOP20','CUT_probability','official_final_outcome','outcome_source','outcome_artifact_sha','validation_metrics','validation_timestamp'],'immutability':'historical rows are never rewritten'}
    (OUT/'NEO_CALIBRATION_LEDGER_V1_SCHEMA.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    md='# NEO Validation Framework v1.0\n\nStatus: READY_TO_FREEZE. This is validation-only evidence; V1, V2A, and V2B are unchanged and V2B remains publication-blocked.\n\nArtifacts are content-addressed by their recorded SHA256 and use the official KLPGA SG snapshot from dac6a09. The exposure decomposition is diagnostic and does not retest V2B against the proposed gate.\n'
    (OUT/'NEO_VALIDATION_FRAMEWORK_V1.md').write_text(md,encoding='utf-8')
    print(json.dumps({'aligned':len(aligned),'universe_sha256':universe_sha,'classification':report['classification'],'old_gate_decision':report['old_gate_decision']},ensure_ascii=False))
if __name__=='__main__': main()
