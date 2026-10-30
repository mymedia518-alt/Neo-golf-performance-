import csv,collections,json,statistics as st
N='/home/claude/neo-shot/klpga_pipeline/data/players/kim_saeromi/2026/normalized/'
ev={r['game_code']:r for r in csv.DictReader(open(N+'events.csv',encoding='utf-8'))}
holes={(r['game_code'],int(r['round']),int(r['hole'])):r for r in csv.DictReader(open(N+'holes.csv',encoding='utf-8'))}
shots=collections.defaultdict(list)
for r in csv.DictReader(open(N+'shots.csv',encoding='utf-8')):
    shots[(r['game_code'],int(r['round']),int(r['hole']))].append(r)
PEN={'4','5','7','8'}; BUNK={'6','9'}
rows=[]
for k,h in holes.items():
    g=k[0]
    if ev[g]['game_type']!='0': continue
    L=sorted(shots[k],key=lambda s:int(s['shot'])); P=int(h['par']); n=len(L); sts=[s['pp_state'] for s in L]
    reach=next((i+1 for i,x in enumerate(sts) if x in('3','10')),None)
    gir= reach is not None and reach<=P-2
    putts=sum(1 for i in range(1,n) if sts[i-1]=='3')
    t=sts[0]
    if P==3: tee='green' if t in('3','10') else ('penalty' if t in PEN else ('bunker' if t in BUNK else ('fringe' if t=='12' else 'miss_other')))
    else: tee='fairway' if t=='1' else 'rough' if t=='2' else 'bunker' if t in BUNK else 'penalty' if t in PEN else 'other:'+t
    pen=sum(1 for x in sts if x in PEN)
    # approach: the shot that first reaches green-or-not: remaining distance before the approach = rem after previous shot
    app_from=None
    if P>=4 and n>=2: app_from=float(L[P-3]['pp_distance']) if len(L)>P-3 else None  # remaining before shot (P-2): after shot P-3 (0-index)
    rows.append(dict(game=g,title=ev[g]['game_title'],course=ev[g]['course_text'],rnd=k[1],hole=k[2],par=P,strokes=n,avg=float(h['field_avg_score']),
        diff=n-float(h['field_avg_score']),gir=gir,putts=putts,tee=tee,pen=pen,drive=float(L[0]['pp_distanceLen']) if P>=4 else None,
        app_from=app_from, chip_lie=(sts[reach-2] if (reach and not gir and reach>=2) else None),score=n-P,yds=int(h['yds'])))
json.dump(rows,open('rows.json','w'),ensure_ascii=False)
