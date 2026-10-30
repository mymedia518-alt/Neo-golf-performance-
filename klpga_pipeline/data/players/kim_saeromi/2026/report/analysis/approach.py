import csv,collections,json
N='/home/claude/neo-shot/klpga_pipeline/data/players/kim_saeromi/2026/normalized/'
ev={r['game_code']:r for r in csv.DictReader(open(N+'events.csv',encoding='utf-8'))}
holes={(r['game_code'],int(r['round']),int(r['hole'])):r for r in csv.DictReader(open(N+'holes.csv',encoding='utf-8'))}
shots=collections.defaultdict(list)
for r in csv.DictReader(open(N+'shots.csv',encoding='utf-8')): shots[(r['game_code'],int(r['round']),int(r['hole']))].append(r)
LIE={'1':'페어웨이','2':'러프','6':'벙커','9':'그린주변벙커','12':'프린지','3':'그린'}
out=[]
for k,h in holes.items():
    g,rnd,hole=k
    if ev[g]['game_type']!='0': continue
    P=int(h['par']); L=sorted(shots[k],key=lambda s:int(s['shot'])); n=len(L)
    for i,s in enumerate(L):
        if i==0:
            if P!=3: continue
            start=float(h['yds']); lie='티'
        else:
            prev=L[i-1]
            if prev['pp_state'] in ('4','5','7','8'): continue  # after penalty rows, position semantics differ
            start=float(prev['pp_distance']); lie=LIE.get(prev['pp_state'],'기타'+prev['pp_state'])
        if start<=30 or lie in ('그린',): continue
        end=s['pp_state']; on= end in ('3','10')
        prox=float(s['pp_distance']) if on else None
        out.append(dict(g=g,rnd=rnd,hole=hole,par=P,shot=i+1,start=start,lie=lie,end=end,on=on,prox=prox,
                        holed_strokes_after=n-(i+1),cut=ev[g]['rank_text']=='CUT',score=n-P))
json.dump(out,open('app.json','w'),ensure_ascii=False)
