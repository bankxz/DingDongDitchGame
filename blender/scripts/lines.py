import numpy as np, cv2, pickle
from skimage.morphology import skeletonize
im=cv2.imread('/tmp/w/ref.png'); H,W=im.shape[:2]
lum=im.mean(2)
MK=np.load('/tmp/w/masks3.npz'); F=np.load('/tmp/w/masks.npz')['fg']
OPL=[(373,250),(500,250),(560,232),(632,213),(650,200),(700,187),(750,175),(800,163),(858,150)]
OPR=[(373,323),(500,326),(560,345),(632,362),(650,366),(700,376),(750,386),(800,396),(858,407)]
def itp(t,y): return np.interp(y,[a for a,b in t],[b for a,b in t])
# coat bottom per column
cb=np.zeros(W,int)
for x in range(W):
    col=F[640:900,x]&(lum[640:900,x]>105)
    ys=np.nonzero(col)[0]
    cb[x]=640+ys.max() if len(ys) else 0
excl=np.zeros((H,W),bool)
yy,xx=np.mgrid[0:H,0:W]
for x in range(W):
    if cb[x]: excl[cb[x]-9:cb[x]+3,x]=True
fr=(yy>=370)&(yy<=860)&(xx<560)
excl|=fr&(np.abs(xx-itp(OPL,yy))<10)
excl|=fr&(np.abs(xx-itp(OPR,yy))<10)
excl|=(yy>=370)&(xx>=560)&(xx<=669)&(yy<=860)
fac=(yy>=370)&(yy<=566)&(xx<560)
excl|=fac&(np.abs(xx-(itp(OPL,yy)-30))<9)
excl|=fac&(np.abs(xx-(itp(OPR,yy)+30))<9)
def polylines(mask,minlen=6):
    m=cv2.morphologyEx(mask.astype(np.uint8),cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7)))
    n,lab,st,_=cv2.connectedComponentsWithStats(m)
    keep=np.zeros(n,bool); keep[1:]=st[1:,4]>=25; m=keep[lab].astype(np.uint8)
    dt=cv2.distanceTransform(m,cv2.DIST_L2,5)
    sk=skeletonize(m>0)
    ys,xs=np.nonzero(sk); P=set(zip(ys,xs))
    def nb(p):
        y,x=p; return [(y+dy,x+dx) for dy in(-1,0,1) for dx in(-1,0,1) if (dy or dx) and (y+dy,x+dx) in P]
    deg={p:len(nb(p)) for p in P}
    nodes={p for p in P if deg[p]!=2}
    used=set(); lines=[]
    for s in nodes:
        for q in nb(s):
            e=(s,q) if s<q else (q,s)
            if e in used: continue
            path=[s,q]; used.add(e); prev,cur=s,q
            while cur not in nodes:
                nxt=[r for r in nb(cur) if r!=prev and ((cur,r) if cur<r else (r,cur)) not in used]
                if not nxt: break
                r=nxt[0]; used.add((cur,r) if cur<r else (r,cur)); path.append(r); prev,cur=cur,r
            lines.append(path)
    # pure loops
    rem=[p for p in P if deg[p]==2 and not any(((p,r) if p<r else (r,p)) in used for r in nb(p))]
    seen=set()
    for p in rem:
        if p in seen: continue
        path=[p]; seen.add(p); prev=None; cur=p
        while True:
            nxt=[r for r in nb(cur) if r!=prev and r not in seen]
            if not nxt: break
            prev,cur=cur,nxt[0]; seen.add(cur); path.append(cur)
        path.append(p); lines.append(path)
    out=[]
    for pth in lines:
        a=np.array([(x,y) for y,x in pth],float)
        L=np.sum(np.linalg.norm(np.diff(a,axis=0),axis=1)) if len(a)>1 else 0
        endsdeg=[deg.get(pth[0],0),deg.get(pth[-1],0)]
        if L<minlen and 1 in endsdeg: continue
        if L<2: continue
        w=np.median([dt[y,x] for y,x in pth])*2
        ap=cv2.approxPolyDP(a.astype(np.float32).reshape(-1,1,2),1.4,False)[:,0,:].astype(float)
        closed=np.linalg.norm(a[0]-a[-1])<1.5
        for _ in range(2):
            if len(ap)<3: break
            q=[ap[0]]
            for u,v in zip(ap[:-1],ap[1:]): q+= [0.75*u+0.25*v,0.25*u+0.75*v]
            q.append(ap[-1]); ap=np.array(q)
        out.append((ap,float(np.clip(w,3,12))))
    return out
res={}
g=MK['gold']&~excl
hz=np.zeros_like(g); hz[700:880]=True
g=g|(cv2.morphologyEx(g.astype(np.uint8),cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(9,9))).astype(bool)&hz&~excl)
res['gold']=[]
for vw,(x0,x1) in (('F',(0,560)),('S',(560,905)),('B',(905,W))):
    sub=np.zeros_like(g); sub[:,x0:x1]=g[:,x0:x1]
    res['gold']+= [(vw,a,w) for a,w in polylines(sub)]
w=MK['white']; res['white']=[('F',a,ww) for a,ww in polylines(w,8)]
gl=MK['glow']; res['glow']=[]
for vw,(x0,x1) in (('F',(0,560)),('S',(560,905)),('B',(905,W))):
    sub=np.zeros_like(gl); sub[:,x0:x1]=gl[:,x0:x1]
    res['glow']+=[(vw,a,ww) for a,ww in polylines(sub,4)]
# bridge small gaps between line ends
def bridge(lst):
    ends=[]
    for i,(vw,a,w) in enumerate(lst):
        if np.linalg.norm(a[0]-a[-1])<1.5: continue
        for k,(p,q) in enumerate(((a[0],a[1] if len(a)>1 else a[0]),(a[-1],a[-2] if len(a)>1 else a[-1]))):
            d=p-q; n=np.linalg.norm(d); ends.append((vw,p,d/n if n>0 else d,w,i))
    add=[];used=set()
    for i in range(len(ends)):
        for j in range(i+1,len(ends)):
            a,b=ends[i],ends[j]
            if a[0]!=b[0] or a[4]==b[4] or i in used or j in used: continue
            gap=b[1]-a[1]; dist=np.linalg.norm(gap)
            if 0<dist<11 and np.dot(a[2],gap/dist)>0.3 and np.dot(b[2],-gap/dist)>0.3:
                add.append((a[0],np.array([a[1],b[1]]),(a[3]+b[3])/2)); used|={i,j}
    return lst+add
res['gold']=bridge(res['gold'])
# hem zone: keep only long skeleton lines, add smoothed outlines of the cloud fills as continuous gold scrolls
def plen(a): return float(np.sum(np.linalg.norm(np.diff(a,axis=0),axis=1))) if len(a)>1 else 0.0
res['gold']=[(vw,a,w) for vw,a,w in res['gold'] if not (a[:,1].mean()>730 and plen(a)<22)]
cl=MK['cloud'].astype(np.uint8)
cl=(cv2.GaussianBlur(cl.astype(np.float32),(0,0),2.5)>0.5).astype(np.uint8)
cs,_=cv2.findContours(cl,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
for c in cs:
    if cv2.contourArea(c)<120: continue
    a=cv2.approxPolyDP(c,1.2,True)[:,0,:].astype(float); a=np.vstack([a,a[:1]])
    for _ in range(2):
        q=[a[0]]
        for u,v in zip(a[:-1],a[1:]): q+=[0.75*u+0.25*v,0.25*u+0.75*v]
        q.append(a[-1]); a=np.array(q)
    x=a[:,0].mean(); vw='F' if x<560 else ('S' if x<905 else 'B')
    res['gold'].append((vw,a,6.0))
pickle.dump(res,open('/tmp/w/lines.pkl','wb'))
dbg=(im*0.4).astype(np.uint8)
for k,c in (('gold',(0,200,255)),('white',(255,255,255)),('glow',(255,0,255))):
    for vw,a,ww in res[k]:
        cv2.polylines(dbg,[a.astype(np.int32).reshape(-1,1,2)],False,c,max(1,int(round(ww*0.6))))
dbg[excl&MK['gold']]=(0,0,255)
cv2.imwrite('/tmp/w/dbg_lines.png',dbg)
print({k:len(v) for k,v in res.items()})
