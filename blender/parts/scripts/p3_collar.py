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
# ---- turned-back lapel flaps: coat edge rolls over (gold roll) and the flap lies on the chest (purple lining), gold outer edge
I_=lambda tab,y: float(np.interp(y,[q[0] for q in tab],[q[1] for q in tab]))
OPL=[(372,250),(500,250),(540,240),(566,226)]; OPR=[(372,323),(500,326),(540,338),(566,352)]
def flap(sx):
    rows=[374,375.5]+list(range(377,500,4))+list(range(500,549,3))+[549]
    K=14; R=[]
    for y in rows:
        if sx>0: xin=I_(OPL,y)-1; xout0=204
        else:    xin=I_(OPR,y)+1; xout0=366
        f=max(0.0,(y-500)/(549-500)); xout=xout0+(xin-xout0)*min(1,f*1.02)
        if abs(xout-xin)<1.2: xout=xin+(-1.2 if sx>0 else 1.2)
        H=0.065-0.035*f
        row=[]
        for k in range(K):
            px=xin+(xout-xin)*k/(K-1); h=hit(px,y)
            if h is None: break
            row.append((V(h[0]),V(h[1])))
        if len(row)==K: R.append((row,H))
    def sect(row,H):
        B=[p for p,n in row]; N=[n for p,n in row]
        D=(B[1]-B[0]).normalized()
        cc=B[0]+N[0]*H*0.5; ring=[]
        for j in range(7):                                  # roll: from coat surface over to the flap top
            a=math.pi*j/6; ring.append(cc-N[0]*(H*0.5*math.cos(a))-D*(H*0.5*math.sin(a))+D*0.0)
        for k in range(1,K): ring.append(B[k]+N[k]*H)        # flap top
        ring.append(B[-1]-N[-1]*0.004)                       # outer edge wall down to the coat
        return ring
    S=[sect(r,H) for r,H in R]; n=len(S[0])
    for i in range(len(S)-1):
        for j in range(n-1):
            m=M['Gold'] if j<6 else (M['Purple'] if j<n-2 else M['Gold'])
            q=[tuple(S[i][j]),tuple(S[i][j+1]),tuple(S[i+1][j+1]),tuple(S[i+1][j])]
            C.face(q if sx>0 else q[::-1],m)
    # caps
    for i in (0,len(S)-1):
        ring=[tuple(p) for p in S[i]]; C.face(ring if i==0 else ring[::-1],M['Purple'])
    # gold trim on the flap's outer edge (bevelled strip on the top surface edge)
    pts=[];nr=[]
    for r,H in R:
        p,nn=r[-1]; q,_=r[-2]; D=(p-q).normalized(); pts.append(tuple(p+nn*H-D*0.03)); nr.append(nn)
    strip(C,pts,nr,0.032,0.016,M['Gold'])
for sx in (1,-1): flap(sx)
ob=C.build(); print('collar tris',sum(len(p.vertices)-2 for p in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
