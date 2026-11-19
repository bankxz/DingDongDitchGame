import math, numpy as np, cv2, triangle
from mathutils import Vector as V
from mathutils.bvhtree import BVHTree
from kit import *
H_IMG=1086
def trees_from(P):
    T={}
    for k,p in P.items():
        T[k]=BVHTree.FromPolygons([V(v) for v in p.v],[ids for ids,_ in p.f])
    return T
def ray_setup(view,px,py):
    z=Zmap(py)
    if view=='F': return V((XF(px),20,z)),V((0,-1,0))
    if view=='B': return V(((px-CXB)/S,-20,z)),V((0,1,0))
    if view=='SL': return V((-20,(CXS-px)/S,z)),V((1,0,0))
    if view=='SR': return V((20,(CXS-px)/S,z)),V((-1,0,0))
def dominant(n):
    c={'F':n.y,'B':-n.y,'SL':-n.x,'SR':n.x}; return max(c,key=c.get),c
def components(mask,eps=0.7):
    m8=mask.astype(np.uint8)
    cs,hier=cv2.findContours(m8,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_NONE)
    if hier is None: return []
    hier=hier[0]; out=[]
    for i,c in enumerate(cs):
        if hier[i][3]!=-1: continue
        if cv2.contourArea(c)<6: continue
        holes=[]; j=hier[i][2]
        while j!=-1:
            if cv2.contourArea(cs[j])>=6: holes.append(cs[j])
            j=hier[j][0]
        out.append((c,holes))
    return out
def tri_component(c,holes,area):
    vs=[];segs=[];hp=[]
    for cc in [c]+holes:
        a=cv2.approxPolyDP(cc,0.7,True)[:,0,:].astype(float)
        if len(a)<3: continue
        b=len(vs); vs+=list(map(tuple,a)); segs+=[(b+i,b+(i+1)%len(a)) for i in range(len(a))]
    for h in holes:
        hm=np.zeros((H_IMG,1448),np.uint8); cv2.drawContours(hm,[h],-1,1,-1)
        hm2=cv2.erode(hm,np.ones((3,3),np.uint8)); ys,xs=np.nonzero(hm2 if hm2.any() else hm)
        if len(xs): k=len(xs)//2; hp.append((xs[k]+0.5,ys[k]+0.5))
    d=dict(vertices=np.array(vs),segments=np.array(segs))
    if hp: d['holes']=np.array(hp)
    try: t=triangle.triangulate(d,'pq20a%g'%area)
    except Exception: return None,None
    return t['vertices'],t['triangles']
import pickle
TRIS=pickle.load(open('/tmp/w/tris.pkl','rb'))
def project(P,TR,name,views,mat,off,depth=0.006,target=None):
    cnt=0
    for (vw,vs,tr) in TRIS[name]:
        vlist=[vw] if vw!='S' else ['SL','SR']
        vlist=[v for v in vlist if v in views]
        for view in vlist:
            hits=[]
            for (px,py) in vs:
                o,d=ray_setup(view,px,py); best=None
                for k,t in TR.items():
                    if target and k not in target: continue
                    r=t.ray_cast(o,d,60)
                    if r[0] is not None and (best is None or r[3]<best[3]): best=(r[0],r[1],k,r[3])
                if best is None: hits.append(None); continue
                n=best[1].copy()
                if n.dot(d)>0: n=-n
                dv,c_=dominant(n)
                if dv!=view and c_[view]<c_[dv]-0.08: hits.append(None); continue
                hits.append((best[0],n,best[2]))
            kept=[t3 for t3 in tr if all(hits[i] is not None for i in t3)]
            if not kept: continue
            ec={}
            for t3 in kept:
                for a,b in ((t3[0],t3[1]),(t3[1],t3[2]),(t3[2],t3[0])):
                    k=(min(a,b),max(a,b)); ec[k]=ec.get(k,0)+1
            for t3 in kept:
                gs=[hits[i][2] for i in t3]; g=max(set(gs),key=gs.count)
                top=[tuple(hits[i][0]+hits[i][1]*off) for i in t3]; bot=[tuple(hits[i][0]-hits[i][1]*depth) for i in t3]
                P[g].face(top,mat); P[g].face(bot[::-1],mat)
                for a,b in ((t3[0],t3[1]),(t3[1],t3[2]),(t3[2],t3[0])):
                    if ec[(min(a,b),max(a,b))]==1:
                        P[g].face([tuple(hits[a][0]+hits[a][1]*off),tuple(hits[b][0]+hits[b][1]*off),tuple(hits[b][0]-hits[b][1]*depth),tuple(hits[a][0]-hits[a][1]*depth)],mat)
                cnt+=1
    return cnt

LINES=pickle.load(open('/tmp/w/lines.pkl','rb'))
def strip_poly(part_of,pts3,nrms,hw,h,mat,prof='bevel'):
    """pts3/nrms: lists of Vectors along the path on a surface"""
    L=len(pts3)
    if L<2: return
    rings=[]
    for i in range(L):
        t=(pts3[min(i+1,L-1)]-pts3[max(i-1,0)])
        if t.length<1e-9: t=V((1,0,0))
        t.normalize(); n=nrms[i]; sd=t.cross(n)
        if sd.length<1e-9: continue
        sd.normalize(); p=pts3[i]
        if prof=='bevel':
            ring=[p-sd*hw-n*0.006,p+sd*hw-n*0.006,p+sd*hw+n*h*0.65,p+sd*hw*0.62+n*h,p-sd*hw*0.62+n*h,p-sd*hw+n*h*0.65]
        else:
            ring=[p-sd*hw-n*0.006,p+sd*hw-n*0.006,p+sd*hw+n*h,p-sd*hw+n*h]
        rings.append([tuple(q) for q in ring])
    if len(rings)>=2: part_of.loft(rings,mat,cap0=mat,cap1=mat)
def strip_lines(P,TR,name,views,mat,h,step=2.5,wscale=1.0,filt=None,minw=None):
    cnt=0
    for (vw,poly,wpx) in LINES[name]:
        if filt and not filt(vw,poly): continue
        vlist=[vw] if vw!='S' else ['SL','SR']
        vlist=[v for v in vlist if v in views]
        # resample polyline
        pts=[poly[0]]
        for a,b in zip(poly[:-1],poly[1:]):
            d=np.linalg.norm(b-a); k=max(1,int(d/step))
            for s in range(1,k+1): pts.append(a+(b-a)*s/k)
        hw=max(wpx if minw is None else max(wpx,minw),2.5)/2/S*wscale
        for view in vlist:
            run=[];rn=[];rg=None
            def flush():
                nonlocal run,rn,rg,cnt
                if len(run)>=2: strip_poly(P[rg],run,rn,hw,h,mat); cnt+=1
                run=[];rn=[]
            for (px,py) in pts:
                o,d=ray_setup(view,px,py); best=None
                for k,t in TR.items():
                    r=t.ray_cast(o,d,60)
                    if r[0] is not None and (best is None or r[3]<best[3]): best=(r[0],r[1],k,r[3])
                if best is None: flush(); rg=None; continue
                n=best[1].copy()
                if n.dot(d)>0: n=-n
                dv,c_=dominant(n)
                if dv!=view and c_[view]<c_[dv]-0.08: flush(); rg=None; continue
                if rg is not None and best[2]!=rg: flush()
                rg=best[2]; run.append(best[0]); rn.append(n)
            flush()
    return cnt
