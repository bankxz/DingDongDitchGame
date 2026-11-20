import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy, pickle, bmesh
from common import *
from mathutils.bvhtree import BVHTree
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats(); CL=mat('Cloud',(0.78,0.66,0.90),0,0.4)
def tree_of(ob):
    dg=bpy.context.evaluated_depsgraph_get(); bm=bmesh.new(); bm.from_object(ob,dg); bm.transform(ob.matrix_world)
    t=BVHTree.FromBMesh(bm); bm.free(); return t
tree=tree_of(bpy.data.objects['Gear_Torso'])
with bpy.data.libraries.load('/tmp/w/parts/P2proxy.blend') as (src,dst): dst.objects=['Gear_Torso']
px_ob=dst.objects[0]; px_ob.name='ProxyCoat'; bpy.context.scene.collection.objects.link(px_ob)
ptree=tree_of(px_ob); bpy.data.objects.remove(px_ob)
D=pickle.load(open('/tmp/w/parts/trim_polys.pkl','rb'))
def ray(view,px,py):
    z=Zmap(py)
    if view=='F': return V((XF(px),20,z)),V((0,-1,0))
    if view=='B': return V(((px-1179.5)/121,-20,z)),V((0,1,0))
    if view=='SL': return V((-20,(722-px)/121,z)),V((1,0,0))
    return V((20,(722-px)/121,z)),V((-1,0,0))
def hit(view,px,py):
    o,d=ray(view,px,py); h=ptree.ray_cast(o,d,60)          # 1) land on the smooth (fold-free) proxy: continuous, no occlusion
    if h[0] is None: return None
    n=h[1].copy()
    if n.dot(d)>0: n=-n
    dots={'F':n.y,'B':-n.y,'SL':-n.x,'SR':n.x}
    if dots[view]<max(dots.values())-0.03 or dots[view]<0.05: return None
    p0=h[0]; c=V((0,-0.05,p0.z)); r=V((p0.x,p0.y+0.05,0))
    if r.length<1e-6: return None
    r.normalize()
    h2=tree.ray_cast(c+r*4.0,-r,8.0)                          # 2) drop radially onto the real folded coat
    if h2[0] is None: return None
    n2=h2[1].copy()
    if n2.dot(r)<0: n2=-n2
    return h2[0],n2
T=Part('Trim_Torso','Torso'); G=Part('Glow_Torso','Torso')
def prism(part,vs,tr,view,lift,mat_,sink=0.006):
    hs=[hit(view,px,py) for px,py in vs]
    kept=[t3 for t3 in tr if all(hs[i] is not None for i in t3)]
    ec={}
    for t3 in kept:
        for a,b in ((t3[0],t3[1]),(t3[1],t3[2]),(t3[2],t3[0])): k=(min(a,b),max(a,b)); ec[k]=ec.get(k,0)+1
    def top(i): return tuple(hs[i][0]+hs[i][1]*lift)
    def bot(i): return tuple(hs[i][0]-hs[i][1]*sink)
    for t3 in kept:
        part.face([top(i) for i in t3],mat_); part.face([bot(i) for i in t3][::-1],mat_)
        for a,b in ((t3[0],t3[1]),(t3[1],t3[2]),(t3[2],t3[0])):
            if ec[(min(a,b),max(a,b))]==1: part.face([top(a),top(b),bot(b),bot(a)],mat_)
    return len(kept)
cnt={'gold':0,'cloud':0}
for name,lift,mt in (('gold',0.024,M['Gold']),):
    for vw,vs,tr in D[name]:
        if name=='gold' and vs[:,1].mean()>690: continue
        for view in (['SL','SR'] if vw=='S' else [vw]):
            cnt[name]+=prism(T,vs,tr,view,lift,mt)
print('projected tris',cnt)

# ---- hem band from the hem geometry (continuous, follows every fold)
HEMS=pickle.load(open('/tmp/w/parts/hem.pkl','rb'))
for ro,ri,last4 in HEMS:
    pts=[];nr=[]
    for k in range(len(ro)):
        p=V(ro[k]); up=(V(last4[-2][k])-p); up=up.normalized() if up.length>1e-9 else V((0,0,1))
        n=V(ro[k])-V(ri[k]); n=n.normalized() if n.length>1e-9 else V((0,1,0))
        pts.append(tuple(p+up*0.055)); nr.append(n)
    strip(T,pts,nr,0.05,0.022,M['Gold'])
# ---- front edge binding: hem -> up the opening -> round the neck line -> down the other opening
E=pickle.load(open('/tmp/w/parts/edges.pkl','rb'))
def edge_strip(sx):
    rows=E['open'][sx]; inn=E['openi'][sx]; pts=[];nr=[]
    for i in range(len(rows)-1,-1,-1):
        p=V(rows[i][0]); q=V(rows[i][2]); dvec=(q-p).normalized(); n=(V(rows[i][0])-V(inn[i])).normalized()
        pts.append(p+dvec*0.035); nr.append(n)
    return pts,nr
PATH=[];NR=[]
p1,n1=edge_strip(1); PATH+=p1; NR+=n1
for sx,rev in ((1,False),(-1,True)):
    nk=[V(q) for q in E['edges'][sx]['neck']]
    if rev: nk=nk[::-1]
    for q in nk: PATH.append(q+V((0,0,0.004))); NR.append(V((0,0,1)))
p2,n2=edge_strip(-1); PATH+=p2[::-1]; NR+=n2[::-1]
# densify corners: insert blended normals
strip(T,[tuple(q) for q in PATH],NR,0.05,0.024,M['Gold'])
# ---- original cloud-scroll design, wrapped on the coat
import clouds_design as CD
def hemz_fn(sx):
    pts=[]
    for ro,ri,l4 in HEMS:
        for q in ro:
            if q[0]*sx>=-1e-6: pts.append((math.atan2(abs(q[0]),q[1]+0.05),q[2]))
    pts.sort(); a=np.array(pts)
    # smooth the scallops so the clouds sit level
    zs=np.convolve(np.pad(a[:,1],(6,6),mode='edge'),np.ones(13)/13,mode='valid')
    return lambda t: float(np.interp(t,a[:,0],zs))
for sx in (1,-1):
    sm=CD.SurfMap(ptree,tree,sx); hz=hemz_fn(sx)
    for theta_c,scale,flip in ((66,0.95,False),(97,1.12,True),(134,1.28,False)):
        s0=sm.s_of_theta(math.radians(theta_c),0.75)
        CD.build_on(T,M,CL,sm,s0,hz,scale,flip if sx>0 else not flip)
# ---- back centre motif (measured, symmetric about x=1180)
def mir(pl): return [(2*1180-x,y) for x,y in pl]
MOT=[([(1140,388),(1140,705),(1095,736),(1090,766)],5.5),
     ([(1172,392),(1172,532)],5.0),([(1172,605),(1172,731),(1160,746),(1160,800),(1170,815),(1170,842)],5.5),
     ([(1131,571),(1180,522),(1229,571)],6.0),([(1131,571),(1172,609)],6.0),
     ([(1151,573),(1180,546),(1209,573)],5.0),([(1151,573),(1172,594)],5.0)]
def lay(pl,hw,part,mat_,h=0.024):
    pts=[np.array(pl[0],float)]
    for a,b in zip(pl[:-1],pl[1:]):
        a=np.array(a,float); b=np.array(b,float); k=max(1,int(np.linalg.norm(b-a)/1.5))
        for q in range(1,k+1): pts.append(a+(b-a)*q/k)
    run=[];rn=[]
    for px,py in pts:
        hh=hit('B',px,py)
        if hh is None: continue
        run.append(tuple(hh[0])); rn.append(hh[1])
    if len(run)>1: strip(part,run,rn,hw,h,mat_)
for i,(pl,w) in enumerate(MOT):
    lay(pl,w/2/121,T,M['Gold'])
    if i not in (3,5): lay(mir(pl),w/2/121,T,M['Gold'])
lay([(1180,490),(1180,786)],2.4/121,G,M['Glow'],0.03)
def plate(poly_px,part,mat_,lift):
    ring=[hit('B',px,py) for px,py in poly_px]; hc=hit('B',*np.mean(poly_px,0))
    if any(r is None for r in ring) or hc is None: return
    top=[tuple(h_[0]+h_[1]*lift) for h_ in ring]; ct=tuple(hc[0]+hc[1]*lift); bot=[tuple(h_[0]-h_[1]*0.004) for h_ in ring]
    for i in range(len(ring)):
        j=(i+1)%len(ring); part.face([top[i],top[j],ct],mat_); part.face([top[j],top[i],bot[i],bot[j]],mat_)
    part.face(bot[::-1],mat_)
plate([(1180,552),(1203,573),(1180,592),(1157,573)],G,M['Glow'],0.014)
plate([(1180,742),(1196,750),(1196,800),(1180,812),(1164,800),(1164,750)],G,M['Glow'],0.010)
for p in (T,G):
    ob=p.build(); print(ob.name,'tris',sum(len(q.vertices)-2 for q in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
