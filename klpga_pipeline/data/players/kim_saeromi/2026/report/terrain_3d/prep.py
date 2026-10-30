import json,math,csv,collections,sqlite3,numpy as np,statistics as st
CM='/mnt/user-data/attachments/5df4e607-34ac-5142-b238-67ec4ea61ec4/f3ef3e87-kim_saeromi_cmpro_2026100005.json'
dem=np.load('../terrain/dem_z15.npy')
LAT0,LON0=37.3834,127.6466
R=6378137.0
def enu(lat,lon): return ((lon-LON0)*math.pi/180*R*math.cos(math.radians(LAT0)), (lat-LAT0)*math.pi/180*R)
def merc_px(lat,lon):
    n=2**15*256; x=(lon+180)/360*n; y=(1-math.log(math.tan(math.radians(lat))+1/math.cos(math.radians(lat)))/math.pi)/2*n
    return x-28001*256, y-12709*256
def px_latlon(x,y):
    n=2**15*256; X=x+28001*256; Y=y+12709*256
    lon=X/n*360-180; lat=math.degrees(math.atan(math.sinh(math.pi*(1-2*Y/n)))); return lat,lon
BIAS=3.75
def samp(lat,lon):
    x,y=merc_px(lat,lon); x0,y0=int(x),int(y); fx,fy=x-x0,y-y0
    a=dem[y0,x0];b=dem[y0,x0+1];c=dem[y0+1,x0];d=dem[y0+1,x0+1]
    return a*(1-fx)*(1-fy)+b*fx*(1-fy)+c*(1-fx)*fy+d*fx*fy - BIAS
cm=json.load(open(CM,encoding='utf-8'))
rows=[r for v in cm.values() for r in json.loads(v['body']) if r['PlayerCode']=='00008380']
two={(int(r['round']),int(r['hole']),int(r['shot'])):r for r in csv.DictReader(open('/home/claude/neo-shot/klpga_pipeline/data/players/kim_saeromi/2026/normalized/shots.csv',encoding='utf-8')) if r['game_code']=='2026100005'}
A_,B_,C_=-3.3326271186440724,649.8622881355936,3.337133757961783
img=lambda x,y:(A_*y+B_, C_*x)
# per-hole affine image(u,v)->(e,n)
aff={}; fit={}
for h in range(1,19):
    P=[];Q=[]
    for r in rows:
        if r['HoleNum']!=h or r['ShotNum']==0: continue
        t=two[(r['GameRound'],h,r['ShotNum'])]; u,v=img(float(t['pp_x']),float(t['pp_y']))
        P.append([u,v,1]); Q.append(enu(r['Latitude'],r['Logitude']))
    P=np.array(P);Q=np.array(Q); M=np.linalg.lstsq(P,Q,rcond=None)[0]; err=np.linalg.norm(P@M-Q,axis=1)
    aff[h]=M.T.round(6).tolist(); fit[h]=dict(n=len(P),median_m=round(float(np.median(err)),2),max_m=round(float(err.max()),2))
# DEM crop: course extent = union of hole image corners
E_=[];N_=[]
for h,M in aff.items():
    M=np.array(M)
    for u,v in [(0,0),(650,0),(0,433),(650,433)]:
        e,n=M@[u,v,1]; E_.append(e); N_.append(n)
pad=150
emin,emax,nmin,nmax=min(E_)-pad,max(E_)+pad,min(N_)-pad,max(N_)+pad
# convert bbox to pixel range
def en2ll(e,n): return LAT0+n/(math.pi/180*R), LON0+e/(math.pi/180*R*math.cos(math.radians(LAT0)))
x1,y1=merc_px(*en2ll(emin,nmax)); x2,y2=merc_px(*en2ll(emax,nmin))
x1,y1=max(0,int(x1)),max(0,int(y1)); x2,y2=min(767,int(x2)+1),min(767,int(y2)+1)
grid=[]; 
for y in range(y1,y2+1):
    for x in range(x1,x2+1):
        grid.append(int(round((dem[y,x]-BIAS)*10)))
e00,n00=enu(*px_latlon(x1,y1)); e10,_=enu(*px_latlon(x1+1,y1)); _,n01=enu(*px_latlon(x1,y1+1))
terrain=dict(nx=x2-x1+1,ny=y2-y1+1,e0=round(e00,2),n0=round(n00,2),dx=round(e10-e00,4),dy=round(n01-n00,4),h_dm=grid)
# shots
S=collections.defaultdict(list)
for r in sorted(rows,key=lambda r:(r['GameRound'],r['HoleNum'],r['ShotNum'])):
    if r['PlayerCode']!='00008380': continue
    e,n=enu(r['Latitude'],r['Logitude'])
    item=dict(n=r['ShotNum'],e=round(e,2),nn=round(n,2),alt=None if r['Altitude']<-1000 else round(r['Altitude']-0,2),
              ground=round(samp(r['Latitude'],r['Logitude']),2))
    if r['ShotNum']>0:
        t=two[(r['GameRound'],r['HoleNum'],r['ShotNum'])]
        item.update(st=t['pp_state'],ko=t['state_name_ko'],len=float(t['pp_distanceLen']),rem=float(t['pp_distance']),gx=round(A_*float(t['pp_greeny'])+B_,1),gy=round(C_*float(t['pp_greenx']),1))
    S[f"{r['GameRound']}-{r['HoleNum']}"].append(item)
# field from 2D full-field sqlite, converted with hole affine
c=sqlite3.connect('../ff/ff.sqlite')
fr=c.execute("select player_code,round,hole,shot,state_code,distance,x,y from klpga_player_shot order by player_code,round,hole,shot").fetchall()
H=collections.defaultdict(list)
for p,r,h,s,stt,d,x,y in fr: H[(p,r,h)].append((s,stt,d,x,y))
def toEN(h,x,y):
    u,v=img(x,y); M=np.array(aff[h]); e,n=M@[u,v,1]; return round(float(e),1),round(float(n),1)
ftee=collections.defaultdict(list); fapp=collections.defaultdict(list)
for (p,r,h),L in H.items():
    if p=='8380': continue
    s1=L[0]; ftee[f'{r}-{h}'].append(list(toEN(h,s1[3],s1[4]))+[s1[1]])
    for i in range(1,len(L)):
        pv=L[i-1]
        if pv[1]=='2' and 125<pv[2]<=150:
            a=toEN(h,pv[3],pv[4]); b=toEN(h,L[i][3],L[i][4]); fapp[f'{r}-{h}'].append([a[0],a[1],b[0],b[1],1 if L[i][1] in('3','10') else 0])
old=json.load(open('../3d/data.json'))
out=dict(origin=[LAT0,LON0],dem_bias_m=BIAS,terrain=terrain,affine=aff,affine_fit=fit,holes=old['holes'],shots=S,field_tee=ftee,field_rough_app=fapp)
json.dump(out,open('data.json','w'),ensure_ascii=False,separators=(',',':'))
print('terrain',terrain['nx'],terrain['ny'],terrain['dx'],terrain['dy'],'size',len(json.dumps(out))//1024,'KB')
print('fit',fit)
