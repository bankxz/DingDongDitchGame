# clean cloud-scroll curves: gold mask -> skeleton graph -> smoothing splines -> bridged, uniform-width paths
import numpy as np, cv2, pickle
from skimage.morphology import skeletonize
from scipy.interpolate import splprep, splev
im=cv2.imread('/tmp/w/ref.png'); H,W=im.shape[:2]; K=3
up=cv2.resize(im,(W*K,H*K),interpolation=cv2.INTER_CUBIC)
hsv=cv2.cvtColor(up,cv2.COLOR_BGR2HSV).astype(int); h,s,v=hsv[...,0],hsv[...,1],hsv[...,2]
gold=((h>=7)&(h<=33)&(s>=40)&(v>=80)) | ((h>=7)&(h<=33)&(s>=22)&(v>=190))
yy,xx=np.mgrid[0:H*K,0:W*K]; yS=yy/K; xS=xx/K
itp=lambda tab,y: np.interp(y,[a for a,b in tab],[b for a,b in tab])
OPL=[(372,250),(500,250),(540,240),(566,226),(612,201),(660,193),(708,183),(756,171),(804,158),(852,147),(880,145)]
OPR=[(372,323),(500,326),(540,338),(566,352),(612,373),(660,380),(708,389),(756,399),(804,411),(852,413),(880,415)]
zone=(yS>698)&(yS<858)
zone&=~((xS<560)&((np.abs(xS-itp(OPL,yS)+4)<12)|(np.abs(xS-itp(OPR,yS)-4)<12)))
zone&=~((xS>=560)&(xS<905)&(xS<674))
zone&=~((xS>1085)&(xS<1275))                         # back motif
Fm=np.load('/tmp/w/masks.npz')['fg']; lum=im.mean(2)
hem=np.zeros((H,W),bool)
for x in range(W):
    ys=np.nonzero(Fm[640:900,x]&(lum[640:900,x]>105))[0]
    if len(ys): hem[640+ys.max()-15:,x]=True
zone&=~cv2.resize(hem.astype(np.uint8),(W*K,H*K),interpolation=cv2.INTER_NEAREST).astype(bool)
zone&=~((xS<170)&(yS<660))&~((xS>390)&(xS<560)&(yS<660))
m=(gold&zone).astype(np.uint8)
m=cv2.morphologyEx(m,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9)))
m=(cv2.GaussianBlur(m.astype(np.float32),(0,0),2.5)>0.45).astype(np.uint8)
n,lab,st,_=cv2.connectedComponentsWithStats(m); keep=np.zeros(n,bool); keep[1:]=st[1:,4]>=300; m=keep[lab].astype(np.uint8)
dt=cv2.distanceTransform(m,cv2.DIST_L2,5)
m1=cv2.resize(m,(W*2,H*2),interpolation=cv2.INTER_AREA)>0      # skeleton at 2x for smoother graph
sk=skeletonize(m1)
P=set(zip(*np.nonzero(sk)))
def nb(p): y,x=p; return [(y+a,x+c) for a in(-1,0,1) for c in(-1,0,1) if (a or c) and (y+a,x+c) in P]
deg={p:len(nb(p)) for p in P}; nodes={p for p in P if deg[p]!=2}; used=set(); paths=[]
for s0 in nodes:
    for q in nb(s0):
        e=(min(s0,q),max(s0,q))
        if e in used: continue
        pth=[s0,q]; used.add(e); prev,cur=s0,q
        while cur not in nodes:
            nx=[t for t in nb(cur) if t!=prev and (min(cur,t),max(cur,t)) not in used]
            if not nx: break
            t=nx[0]; used.add((min(cur,t),max(cur,t))); pth.append(t); prev,cur=cur,t
        paths.append(pth)
rem=[p for p in P if deg[p]==2 and not any((min(p,t),max(p,t)) in used for t in nb(p))]
seen=set()
for p in rem:
    if p in seen: continue
    pth=[p]; seen.add(p); prev=None; cur=p
    while True:
        nx=[t for t in nb(cur) if t!=prev and t not in seen]
        if not nx: break
        prev,cur=cur,nx[0]; seen.add(cur); pth.append(cur)
    paths.append(pth)
curves=[]
for pth in paths:
    a=np.array([(x/2,y/2) for y,x in pth],float)
    L=np.sum(np.linalg.norm(np.diff(a,axis=0),axis=1)) if len(a)>1 else 0
    spur=(deg.get(pth[0],0)==1) or (deg.get(pth[-1],0)==1)
    if L<9 and spur: continue
    if L<3: continue
    # dedupe & spline smooth
    keep_=[0]+[i for i in range(1,len(a)) if np.linalg.norm(a[i]-a[i-1])>0.3]
    a=a[keep_]
    if len(a)>=5:
        try:
            tck,u=splprep([a[:,0],a[:,1]],s=len(a)*0.35,k=3)
            uu=np.linspace(0,1,max(6,int(L/1.5))); a=np.array(splev(uu,tck)).T
        except Exception: pass
    x=a[:,0].mean(); vw='F' if x<560 else ('S' if x<905 else 'B')
    curves.append([vw,a])
# bridge gaps between endpoints (direction-aware), also snap ends onto nearby curves (T-junctions)
ends=[]
for i,(vw,a) in enumerate(curves):
    if len(a)<2 or np.linalg.norm(a[0]-a[-1])<1.0: continue
    for p,q in ((a[0],a[min(3,len(a)-1)]),(a[-1],a[max(-4,-len(a))])):
        d=p-q; n_=np.linalg.norm(d); ends.append((vw,p,d/n_ if n_>0 else d,i))
used=set(); added=[]
for i in range(len(ends)):
    best=None
    for j in range(len(ends)):
        if j==i or ends[i][0]!=ends[j][0] or ends[i][3]==ends[j][3] or j in used or i in used: continue
        g=ends[j][1]-ends[i][1]; d=np.linalg.norm(g)
        if 0<d<14 and np.dot(ends[i][2],g/d)>0.35 and np.dot(ends[j][2],-g/d)>0.35:
            if best is None or d<best[0]: best=(d,j)
    if best:
        j=best[1]; p0,d0=ends[i][1],ends[i][2]; p1,d1=ends[j][1],ends[j][2]; L=best[0]
        t=np.linspace(0,1,8)[:,None]
        c=(1-t)**3*p0+3*(1-t)**2*t*(p0+d0*L/3)+3*(1-t)*t**2*(p1+d1*L/3)+t**3*p1
        added.append([ends[i][0],c]); used|={i,j}
curves+=added
curves=[c for c in curves if not (c[1][:,1].mean()>829 and np.ptp(c[1][:,1])<9)]
pickle.dump(curves,open('/tmp/w/parts/cloud_curves.pkl','wb'))
dbg=(im*0.45).astype(np.uint8)
for vw,a in curves: cv2.polylines(dbg,[(a*4).round().astype(np.int32).reshape(-1,1,2)],False,(0,215,255),2,cv2.LINE_AA,shift=2)
cv2.imwrite('/tmp/w/parts/dbg_curves.png',cv2.resize(dbg[690:870],(W,180)))
big=cv2.resize(dbg[690:870,0:560],(1120,360),interpolation=cv2.INTER_NEAREST); cv2.imwrite('/tmp/w/parts/dbg_curves_front.png',big)
print('curves',len(curves),'bridges',len(added))
