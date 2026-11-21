# original cloud-scroll design, built in surface coordinates (arc length around the coat, height) so it wraps over folds
import bpy, bmesh, math, numpy as np, cv2, sys
sys.path.insert(0,'/tmp/w/parts'); sys.path.insert(0,'/tmp/w/s3')
from common import *
from mathutils.bvhtree import BVHTree
from tripre import tri_safe
def tree_of(ob):
    dg=bpy.context.evaluated_depsgraph_get(); bm=bmesh.new(); bm.from_object(ob,dg); bm.transform(ob.matrix_world)
    t=BVHTree.FromBMesh(bm); bm.free(); return t
AX=V((0,-0.05,0))
def radial_hit(tree,theta,z):
    d=V((math.sin(theta),math.cos(theta),0)); c=V((AX.x,AX.y,z))
    h=tree.ray_cast(c+d*4.0,-d,8.0)
    if h[0] is None: return None
    n=h[1].copy()
    if n.dot(d)<0: n=-n
    return h[0],n
class SurfMap:
    def __init__(s,ptree,rtree,sx):
        s.pt=ptree; s.rt=rtree; s.sx=sx; s.cache={}
    def table(s,z):
        k=round(z,2)
        if k in s.cache: return s.cache[k]
        th=np.radians(np.arange(0,180.01,0.5)); pts=[]
        for t in th:
            h=radial_hit(s.pt,s.sx*t,k); pts.append(np.array(h[0]) if h else None)
        sarr=[0.0]; last=None
        for p in pts[1:]:
            st=0.0
            if p is not None and last is not None:
                st=np.linalg.norm(p-last)
                if st>0.12: st=0.0      # jump to another surface (opening / lining): ignore
            sarr.append(sarr[-1]+st)
            if p is not None: last=p
        s.cache[k]=(th,np.array(sarr)); return s.cache[k]
    def s_of_theta(s,theta,z):
        th,sa=s.table(z); return float(np.interp(theta,th,sa))
    def point(s,sv,z,lift=0.0):
        th,sa=s.table(z); t=float(np.interp(sv,sa,th))
        h=radial_hit(s.rt,s.sx*t,z)
        if h is None: return None
        return h[0]+h[1]*lift,h[1]
import motif2d as MD
def build_on(T,M,CL,smap,s0,hemz,scale,flip):
    def P(u,w,lift=0.0):
        uu=(-u if flip else u)*scale; ww=w*scale; sv=s0+uu
        th,sa=smap.table(0.75); t=float(np.interp(sv,sa,th))
        h=radial_hit(smap.rt,smap.sx*t,hemz(t)+0.115+ww)
        if h is None: return None
        return h[0]+h[1]*lift,h[1]
    def strip_uw(a,hw,h):
        pts=[];nr=[]
        for u,w in a:
            r=P(u,w)
            if r is not None and pts and (V(pts[-1])-r[0]).length>0.09: r=None
            if r is None:
                if len(pts)>1: strip(T,pts,nr,hw*scale,h,M['Gold'])
                pts=[];nr=[]; continue
            pts.append(tuple(r[0])); nr.append(r[1])
        if len(pts)>1: strip(T,pts,nr,hw*scale,h,M['Gold'])
    # densify helper
    def dens(a,step=0.012):
        out=[a[0]]
        for p,q in zip(a[:-1],a[1:]):
            k=max(1,int(np.linalg.norm(q-p)/step))
            for j in range(1,k+1): out.append(p+(q-p)*j/k)
        return np.array(out)
    for pp in MD.plates():
        segs=[(i,(i+1)%len(pp)) for i in range(len(pp))]
        t=tri_safe([tuple(p) for p in pp],segs,[],0.0005)
        if t is None: continue
        vs,tr=t; hs=[P(u,w,0.0) for u,w in vs]
        for t3 in tr:
            if any(hs[i] is None for i in t3): continue
            if max((hs[t3[k]][0]-hs[t3[(k+1)%3]][0]).length for k in range(3))>0.12: continue
            top=[tuple(hs[i][0]+hs[i][1]*0.010) for i in t3]
            T.face(top,CL)
    for a_,hw in MD.strokes(): strip_uw(a_,hw,0.024)
