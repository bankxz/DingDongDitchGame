import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy, pickle, bmesh
from common import *
from mathutils.bvhtree import BVHTree
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
M=mats(); CL=mat('Cloud',(0.78,0.66,0.90),0,0.4)
coat=bpy.data.objects['Gear_Torso']
dg=bpy.context.evaluated_depsgraph_get(); bm=bmesh.new(); bm.from_object(coat,dg); bm.transform(coat.matrix_world)
tree=BVHTree.FromBMesh(bm); bm.free()
D=pickle.load(open('/tmp/w/parts/trim_polys.pkl','rb'))
def ray(view,px,py):
    z=Zmap(py)
    if view=='F': return V((XF(px),20,z)),V((0,-1,0))
    if view=='B': return V(((px-1179.5)/121,-20,z)),V((0,1,0))
    if view=='SL': return V((-20,(722-px)/121,z)),V((1,0,0))
    return V((20,(722-px)/121,z)),V((-1,0,0))
def hit(view,px,py):
    o,d=ray(view,px,py); h=tree.ray_cast(o,d,60)
    if h[0] is None: return None
    n=h[1].copy()
    if n.dot(d)>0: n=-n
    if n.dot(-d)<0.05: return None
    p0=h[0]; ang=math.degrees(math.atan2(abs(p0.x),p0.y+0.25))   # 0 front .. 180 back, by position (fold normals don't fragment it)
    own='F' if ang<62 else ('B' if ang>128 else ('SR' if p0.x>0 else 'SL'))
    if own!=view: return None
    p=h[0]
    if view=='F' and p.y<0.25: return None
    if view=='B' and p.y>-0.25: return None
    if view=='SL' and p.x>-0.4: return None
    if view=='SR' and p.x<0.4: return None
    return p,n
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
for name,lift,mt in (('cloud',0.010,CL),('gold',0.024,M['Gold'])):
    for vw,vs,tr in D[name]:
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
