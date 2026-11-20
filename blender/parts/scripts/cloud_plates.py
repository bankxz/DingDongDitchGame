import numpy as np, cv2, pickle, sys
sys.path.insert(0,'/tmp/w/s3')
from tripre import tri_safe
im=cv2.imread('/tmp/w/ref.png'); H,W=im.shape[:2]; K=3
b,g,r=[cv2.resize(im,(W*K,H*K),interpolation=cv2.INTER_CUBIC)[...,i].astype(int) for i in range(3)]
lum=(r+g+b)/3; lav=(b>g+31)&(r>g+14)&(lum>120)&(lum<225)
CUR=pickle.load(open('/tmp/w/parts/cloud_curves.pkl','rb'))
Fm=cv2.resize(np.load('/tmp/w/masks.npz')['fg'].astype(np.uint8),(W*K,H*K),interpolation=cv2.INTER_NEAREST)
wall=np.zeros((H*K,W*K),np.uint8)
for vw,a in CUR: cv2.polylines(wall,[(a*K).round().astype(np.int32).reshape(-1,1,2)],False,1,int(5.0*K))
# hem band line & coat outline as walls
lumS=im.mean(2); F0=np.load('/tmp/w/masks.npz')['fg']
for x in range(W):
    ys=np.nonzero(F0[640:900,x]&(lumS[640:900,x]>105))[0]
    if len(ys): wall[(640+ys.max()-15)*K:,x*K:(x+1)*K]=1
zone=np.zeros_like(wall); zone[700*K:860*K]=1
lavS=cv2.morphologyEx(lav.astype(np.uint8),cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(15,15)))
lavS=cv2.morphologyEx(lavS,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(21,21)))
yy,xx=np.mgrid[0:H*K,0:W*K]; yS=yy/K; xS=xx/K
itp=lambda tab,y: np.interp(y,[a for a,b in tab],[b for a,b in tab])
OPL=[(700,185),(756,171),(804,158),(852,147),(880,145)]; OPR=[(700,388),(756,399),(804,411),(852,413),(880,415)]
panel=~((xS<560)&(xS>itp(OPL,yS)-8)&(xS<itp(OPR,yS)+8))
plates=(lavS>0)&(wall==0)&(zone>0)&(Fm>0)&panel&~((xS<560)&(yS<748))&~((xS>=560)&(xS<905)&(xS<678))
n,lab,st,_=cv2.connectedComponentsWithStats(plates.astype(np.uint8),connectivity=4)
keep=np.zeros(n,bool); keep[1:]=(st[1:,4]>1800)&((st[1:,1]+st[1:,3])/K>770); plates=keep[lab]
inv=(~plates).astype(np.uint8); n,lab,st,_=cv2.connectedComponentsWithStats(inv,connectivity=4)
small=np.zeros(n,bool); small[1:]=st[1:,4]<1500; plates|=small[lab]
plates=(cv2.GaussianBlur(plates.astype(np.float32),(0,0),3.0)>0.5)&(wall==0)
res=[]
for vw,(x0,x1) in (('F',(0,560)),('S',(560,905)),('B',(905,1448))):
    sub=np.zeros_like(plates); sub[:,x0*K:x1*K]=plates[:,x0*K:x1*K]
    cs,hier=cv2.findContours(sub.astype(np.uint8),cv2.RETR_CCOMP,cv2.CHAIN_APPROX_NONE)
    if hier is None: continue
    for i,c in enumerate(cs):
        if hier[0][i][3]!=-1 or cv2.contourArea(c)<60: continue
        a=cv2.approxPolyDP(c,1.5,True)[:,0,:].astype(float)/K
        if len(a)<3: continue
        vs=list(map(tuple,a)); segs=[(k,(k+1)%len(a)) for k in range(len(a))]
        t=tri_safe(vs,segs,[],4.0)
        if t is not None and len(t[1]): res.append((vw,t[0],t[1]))
D=pickle.load(open('/tmp/w/parts/trim_polys.pkl','rb')); D['cloud']=res
pickle.dump(D,open('/tmp/w/parts/trim_polys.pkl','wb'))
dbg=(im*0.45).astype(np.uint8); pm=cv2.resize(plates.astype(np.uint8),(W,H),interpolation=cv2.INTER_NEAREST)>0
dbg[pm]=(210,150,215)
for vw,a in CUR: cv2.polylines(dbg,[a.round().astype(np.int32).reshape(-1,1,2)],False,(0,215,255),2)
cv2.imwrite('/tmp/w/parts/dbg_plates.png',dbg[690:870]); print('plates',len(res))
