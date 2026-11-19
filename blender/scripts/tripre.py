# precompute triangulations of all mask components (isolated per component via fork: triangle can segfault)
import numpy as np, cv2, os, pickle, sys
import triangle
MK=np.load('/tmp/w/masks3.npz'); H,W=1086,1448
def components(mask):
    cs,hier=cv2.findContours(mask.astype(np.uint8),cv2.RETR_CCOMP,cv2.CHAIN_APPROX_NONE)
    if hier is None: return []
    hier=hier[0]; out=[]
    for i,c in enumerate(cs):
        if hier[i][3]!=-1 or cv2.contourArea(c)<6: continue
        holes=[]; j=hier[i][2]
        while j!=-1:
            if cv2.contourArea(cs[j])>=6: holes.append(cs[j])
            j=hier[j][0]
        out.append((c,holes))
    return out
def prep(c,holes):
    vs=[];segs=[];key={}
    def vid(p):
        k=(round(p[0],3),round(p[1],3))
        if k not in key: key[k]=len(vs); vs.append(k)
        return key[k]
    for cc in [c]+holes:
        a=cv2.approxPolyDP(cc,0.8,True)[:,0,:].astype(float)
        if len(a)<3: continue
        ids=[vid(tuple(p)) for p in a]
        for i in range(len(ids)):
            s=(ids[i],ids[(i+1)%len(ids)])
            if s[0]!=s[1]: segs.append(s)
    hp=[]
    for h in holes:
        hm=np.zeros((H,W),np.uint8); cv2.drawContours(hm,[h],-1,1,-1)
        dt=cv2.distanceTransform(hm,cv2.DIST_L2,3); y,x=np.unravel_index(np.argmax(dt),dt.shape)
        if dt[y,x]>=1: hp.append((x+0.5,y+0.5))
    return vs,segs,hp
def grid_fallback(c,holes):
    m=np.zeros((H,W),np.uint8); cv2.drawContours(m,[c],-1,1,-1); cv2.drawContours(m,holes,-1,0,-1)
    ys,xs=np.nonzero(m); vs={};V=[];T=[]
    def vid(x,y):
        if (x,y) not in vs: vs[(x,y)]=len(V); V.append((x,y))
        return vs[(x,y)]
    st=2
    for y in range(ys.min()-ys.min()%st,ys.max()+1,st):
        for x in range(xs.min()-xs.min()%st,xs.max()+1,st):
            if m[min(y+1,H-1),min(x+1,W-1)]:
                a,b,c2,d=vid(x,y),vid(x+st,y),vid(x+st,y+st),vid(x,y+st); T+= [(a,b,c2),(a,c2,d)]
    return np.array(V,float),np.array(T)
def tri_safe(vs,segs,hp,area):
    r,w=os.pipe(); pid=os.fork()
    if pid==0:
        os.close(r)
        try:
            d=dict(vertices=np.array(vs),segments=np.array(segs))
            if hp: d['holes']=np.array(hp)
            t=triangle.triangulate(d,'pq20a%g'%area)
            data=pickle.dumps((t['vertices'],t['triangles']))
        except Exception: data=pickle.dumps(None)
        os.write(w,len(data).to_bytes(8,'little')); 
        mv=memoryview(data)
        while mv: n=os.write(w,mv); mv=mv[n:]
        os._exit(0)
    os.close(w); buf=b''
    while True:
        ch=os.read(r,1<<20)
        if not ch: break
        buf+=ch
    os.close(r); os.waitpid(pid,0)
    if len(buf)<8: return None
    return pickle.loads(buf[8:])
AREA=dict(cloud=20,purple=20,white=10,gold=12,glow=10)
out={}; fails=0
for name in AREA:
    m=MK[name].copy()
    if name=='cloud': m=cv2.GaussianBlur(m.astype(np.float32),(0,0),2.5)>0.5
    if name=='purple': m[:381]=False
    res=[]
    for view,sl in (('F',(0,560)),('S',(560,905)),('B',(905,1448))):
        sub=np.zeros_like(m); sub[:,sl[0]:sl[1]]=m[:,sl[0]:sl[1]]
        for c,holes in components(sub):
            vs,segs,hp=prep(c,holes)
            t=tri_safe(vs,segs,hp,AREA[name]) if len(vs)>=3 else None
            if t is None or len(t[1])==0:
                fails+=1; t=grid_fallback(c,holes)
            res.append((view,t[0],t[1]))
    out[name]=res
pickle.dump(out,open('/tmp/w/tris.pkl','wb'))
print('done; fallback comps',fails,{k:len(v) for k,v in out.items()})
