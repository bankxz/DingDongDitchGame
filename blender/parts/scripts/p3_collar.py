import sys; sys.path.insert(0,'/tmp/w/parts'); sys.path.insert(0,'/tmp/w/s3')
import bpy, bmesh, pickle
from common import *
from mathutils.bvhtree import BVHTree
from tripre import tri_safe
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats()
for n in ('Gear_Collar',):
    o=bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o)
C=Part('Gear_Collar','Torso')
# ---- collar wall (measured: front tips at |x|0.31, wings to |x|0.95, top z~4.17-4.20, base on the coat top)
def se_pt(hx,hy,cy,n,t):
    s,c=math.sin(t),math.cos(t); return (hx*math.copysign(abs(s)**(2/n),s), cy+hy*math.copysign(abs(c)**(2/n),c))
def t_front(hx,hy,cy,n,xv):
    best=None
    for k in range(1,1000):
        t=pi*k/1000; x,y=se_pt(hx,hy,cy,n,t)
        if y>cy and (best is None or abs(x-xv)<best[0]): best=(abs(x-xv),t)
    return best[1]
N=72; TH=0.04
LV=[  # (z, hx, hy, cy, n)  base -> top, slight outward flare
    (3.985,0.88,0.555,-0.01,6),(4.05,0.90,0.57,-0.01,6),(4.12,0.95,0.605,-0.015,6),(4.185,1.0,0.635,-0.02,6)]
def ring(lv,off,xf=0.31):
    z,hx,hy,cy,n=lv; hx-=off; hy-=off
    t0=t_front(hx,hy,cy,n,xf); ts=np.linspace(t0,2*pi-t0,N)
    pts=[]
    for k,t in enumerate(ts):
        x,y=se_pt(hx,hy,cy,n,t)
        zz=z
        if lv is LV[-1] and y>0.15:            # front wings: top slants down toward the outer corner (sheet: 4.17 inner -> 4.12 outer)
            u=min(1,max(0,(abs(x)-0.35)/0.6)); zz=z-0.055*u*u*(3-2*u)
        pts.append((x,y,zz))
    return pts
O=[ring(l,0) for l in LV]; I=[ring(l,TH) for l in LV]
for i in range(len(LV)-1):
    for k in range(N-1):
        C.face([O[i][k],O[i][k+1],O[i+1][k+1],O[i+1][k]],M['Purple'])
        C.face([I[i][k+1],I[i][k],I[i+1][k],I[i+1][k+1]],M['Lining'])
    for e in (0,N-1): C.face([O[i][e],I[i][e],I[i+1][e],O[i+1][e]],M['Gold'])
for k in range(N-1):
    C.face([O[-1][k+1],O[-1][k],I[-1][k],I[-1][k+1]],M['Gold'])
    C.face([O[0][k],O[0][k+1],I[0][k+1],I[0][k]],M['Purple'])
# gold rim: bevelled strip capping the top edge (wraps both faces), and down the two front edges
top=[V(((a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2)) for a,b in zip(O[-1],I[-1])]
strip(C,[tuple(p) for p in top],[V((0,0,1))]*len(top),TH*0.5+0.022,0.022,M['Gold'])
for e in (0,N-1):
    pts=[V(((O[i][e][0]+I[i][e][0])/2,(O[i][e][1]+I[i][e][1])/2,O[i][e][2])) for i in range(len(LV))]
    tang=(V(O[0][e+(1 if e==0 else -1)])-V(O[0][e])); tang.z=0; tang.normalize()
    strip(C,[tuple(p) for p in pts],[-tang]*len(pts),TH*0.5+0.02,0.02,M['Gold'])
# ---- purple lapel facings on the coat front (projected from the front view, same as the gold trim)
coat=bpy.data.objects['Gear_Torso']
dg=bpy.context.evaluated_depsgraph_get(); bm=bmesh.new(); bm.from_object(coat,dg); bm.transform(coat.matrix_world)
tree=BVHTree.FromBMesh(bm); bm.free()
def hit(px,py):
    o=V((XF(px),20,Zmap(py))); d=V((0,-1,0)); h=tree.ray_cast(o,d,60)
    if h[0] is None: return None
    n=h[1].copy()
    if n.dot(d)>0: n=-n
    if n.y<0.3: return None
    return h[0],n
FAC=[[(245,377),(245,500),(238,530),(220,551),(208,542),(208,377)],
     [(328,377),(330,500),(336,530),(352,551),(364,542),(364,377)]]
for poly in FAC:
    vs=[tuple(map(float,p)) for p in poly]; segs=[(i,(i+1)%len(vs)) for i in range(len(vs))]
    t=tri_safe(vs,segs,[],3.0)
    vv,tr=t; hs=[hit(px,py) for px,py in vv]
    ec={}
    for t3 in tr:
        for a,b in ((t3[0],t3[1]),(t3[1],t3[2]),(t3[2],t3[0])): k=(min(a,b),max(a,b)); ec[k]=ec.get(k,0)+1
    for t3 in tr:
        if any(hs[i] is None for i in t3): continue
        tp=[tuple(hs[i][0]+hs[i][1]*0.012) for i in t3]; bt=[tuple(hs[i][0]-hs[i][1]*0.004) for i in t3]
        C.face(tp,M['Purple']); C.face(bt[::-1],M['Purple'])
        for a,b in ((t3[0],t3[1]),(t3[1],t3[2]),(t3[2],t3[0])):
            if ec[(min(a,b),max(a,b))]==1: C.face([tp[t3.index(a)] if False else tuple(hs[a][0]+hs[a][1]*0.012),tuple(hs[b][0]+hs[b][1]*0.012),tuple(hs[b][0]-hs[b][1]*0.004),tuple(hs[a][0]-hs[a][1]*0.004)],M['Purple'])
ob=C.build(); print('collar tris',sum(len(p.vertices)-2 for p in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
