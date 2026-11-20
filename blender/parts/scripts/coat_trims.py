import numpy as np, cv2, pickle
from skimage.morphology import skeletonize
im=cv2.imread('/tmp/w/ref.png'); H,W=im.shape[:2]
b,g,r=[im[...,i].astype(int) for i in range(3)]; lum=im.mean(2); sat=im.max(2).astype(int)-im.min(2).astype(int)
hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV).astype(int)
hh,ss,vv=hsv[...,0],hsv[...,1],hsv[...,2]
gold=(hh>=8)&(hh<=32)&(ss>=48)&(vv>=95)
F=np.load('/tmp/w/masks.npz')['fg']
def box(x0,x1,y0,y1): m=np.zeros((H,W),bool); m[y0:y1,x0:x1]=True; return m
# coat-only regions (exclude sleeves 25-160/405-530 above 610, tassel, collar zone, front edge bindings & hem band already modelled)
reg=np.zeros((H,W),bool)
reg|=box(0,560,616,850)&~box(296,372,560,720)
reg|=box(600,905,616,846)
reg|=box(1060,1300,380,606)|box(905,1448,616,846)
reg&=~(box(0,160,360,634)|box(400,560,360,634)|box(640,815,360,634)|box(915,1065,360,634)|box(1295,1448,360,634))
reg&=~box(0,1448,841,1086)
OPL=[(372,250),(500,250),(540,240),(566,226),(612,201),(660,193),(708,183),(756,171),(804,158),(852,145)]
OPR=[(372,323),(500,326),(540,338),(566,352),(612,373),(660,380),(708,389),(756,399),(804,411),(852,415)]
yy,xx=np.mgrid[0:H,0:W]
def itp(t,y): return np.interp(y,[a for a,b in t],[b for a,b in t])
excl=(xx<560)&(yy>370)&((np.abs(xx-itp(OPL,yy)+3)<12)|(np.abs(xx-itp(OPR,yy)-3)<12))
excl|=(xx>=560)&(xx<905)&(xx<668)&(yy>600)                       # side-view front edge binding
# silhouette bottom (hem band) exclusion: within 14px above the coat bottom per column
cb=np.zeros(W,int)
for x in range(W):
    col=F[640:900,x]&(lum[640:900,x]>105); ys=np.nonzero(col)[0]; cb[x]=640+ys.max() if len(ys) else 0
for x in range(W):
    if cb[x]: excl[cb[x]-15:cb[x]+3,x]=True
m=(gold&reg&~excl).astype(np.uint8)
m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
n,lab,st,_=cv2.connectedComponentsWithStats(m); keep=np.zeros(n,bool); keep[1:]=st[1:,4]>=40; m=keep[lab].astype(np.uint8)
dt=cv2.distanceTransform(m,cv2.DIST_L2,5); sk=skeletonize(m>0)
P=set(zip(*np.nonzero(sk)))
def nb(p): y,x=p; return [(y+a,x+c) for a in(-1,0,1) for c in(-1,0,1) if (a or c) and (y+a,x+c) in P]
deg={p:len(nb(p)) for p in P}; nodes={p for p in P if deg[p]!=2}; used=set(); lines=[]
for s0 in nodes:
    for q in nb(s0):
        e=(min(s0,q),max(s0,q))
        if e in used: continue
        path=[s0,q]; used.add(e); prev,cur=s0,q
        while cur not in nodes:
            nx=[t for t in nb(cur) if t!=prev and (min(cur,t),max(cur,t)) not in used]
            if not nx: break
            t=nx[0]; used.add((min(cur,t),max(cur,t))); path.append(t); prev,cur=cur,t
        lines.append(path)
# loops
rem=[p for p in P if deg[p]==2 and not any((min(p,t),max(p,t)) in used for t in nb(p))]
seen=set()
for p in rem:
    if p in seen: continue
    path=[p]; seen.add(p); prev=None; cur=p
    while True:
        nx=[t for t in nb(cur) if t!=prev and t not in seen]
        if not nx: break
        prev,cur=cur,nx[0]; seen.add(cur); path.append(cur)
    path.append(p); lines.append(path)
out=[]
for pth in lines:
    a=np.array([(x,y) for y,x in pth],float)
    L=np.sum(np.linalg.norm(np.diff(a,axis=0),axis=1)) if len(a)>1 else 0
    if L<8 and (deg.get(pth[0],0)==1 or deg.get(pth[-1],0)==1): continue
    if L<3: continue
    w=float(np.clip(np.median([dt[y,x] for y,x in pth])*2,3.5,12))
    ap=cv2.approxPolyDP(a.astype(np.float32).reshape(-1,1,2),1.0,False)[:,0,:].astype(float)
    for _ in range(2):
        if len(ap)<3: break
        q=[ap[0]]
        for u,v in zip(ap[:-1],ap[1:]): q+=[0.75*u+0.25*v,0.25*u+0.75*v]
        q.append(ap[-1]); ap=np.array(q)
    x=ap[:,0].mean(); vw='F' if x<560 else ('S' if x<905 else 'B')
    out.append((vw,ap,w))
# bridge small gaps between line ends
ends=[]
for i,(vw,a,w) in enumerate(out):
    if np.linalg.norm(a[0]-a[-1])<1.5: continue
    for p,q in ((a[0],a[min(1,len(a)-1)]),(a[-1],a[max(-2,-len(a))])):
        d=p-q; nn=np.linalg.norm(d); ends.append((vw,p,d/nn if nn>0 else d,w,i))
used=set()
for i in range(len(ends)):
    for j in range(i+1,len(ends)):
        A,B=ends[i],ends[j]
        if A[0]!=B[0] or A[4]==B[4] or i in used or j in used: continue
        gap=B[1]-A[1]; dist=np.linalg.norm(gap)
        if 0<dist<13 and np.dot(A[2],gap/dist)>0.2 and np.dot(B[2],-gap/dist)>0.2:
            out.append((A[0],np.array([A[1],B[1]]),(A[3]+B[3])/2)); used|={i,j}
# cloud fills (purple plates inside the scrolls)
cl=np.load('/tmp/w/masks3.npz')['cloud'].astype(np.float32)
cl=(cv2.GaussianBlur(cl,(0,0),2.0)>0.5).astype(np.uint8)
pickle.dump(dict(lines=out,cloud=cl),open('/tmp/w/parts/coat_trims.pkl','wb'))
dbg=(im*0.45).astype(np.uint8)
dbg[cl>0]=(200,150,200)
for vw,a,w in out: cv2.polylines(dbg,[a.round().astype(np.int32).reshape(-1,1,2)],False,(0,215,255),max(1,int(round(w*0.7))))
cv2.imwrite('/tmp/w/parts/dbg_coat_trims.png',dbg[340:880])
print('lines',len(out))
