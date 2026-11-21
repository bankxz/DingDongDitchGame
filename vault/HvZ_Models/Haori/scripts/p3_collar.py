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
def ring(lv,off,xf=0.60):
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
for k in range(N-1):
    C.face([O[-1][k+1],O[-1][k],I[-1][k],I[-1][k+1]],M['Gold'])
    C.face([O[0][k],O[0][k+1],I[0][k+1],I[0][k]],M['Purple'])
# gold rim: bevelled strip capping the top edge (wraps both faces), and down the two front edges
top=[V(((a[0]+b[0])/2,(a[1]+b[1])/2,(a[2]+b[2])/2)) for a,b in zip(O[-1],I[-1])]
strip(C,[tuple(p) for p in top],[V((0,0,1))]*len(top),TH*0.5+0.022,0.022,M['Gold'])
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
    rows=sorted(set([374,375.5]+list(range(377,400,4))+list(range(400,452,2))+list(range(452,500,4))+list(range(500,549,3))+[549]))
    K=14; R=[]
    for y in rows:
        notch=max(0.0,1-abs(y-425)/21.0)                 # jutting lapel point (sheet chevron, tip at y425)
        if sx>0: xin=I_(OPL,y)-1; xout0=204-21*notch
        else:    xin=I_(OPR,y)+1; xout0=366+21*notch
        f=max(0.0,(y-500)/(549-500)); f=f*f*(3-2*f); xout=xout0+(xin-xout0)*min(1,f*1.02)
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
    # the flap rises and BECOMES the collar's front: same height/slant/flare as the collar (collar wall stops behind it)
    def ss(u): u=min(1,max(0,u)); return u*u*(3-2*u)
    def ztop(x): return 4.185-0.055*ss((abs(x)-0.35)/0.6)
    def cfy(z): return float(np.interp(z,[3.985,4.05,4.12,4.185],[0.545,0.56,0.588,0.615]))
    base=S[0]; y0=min(p.y for p in base); ext=[]
    for t in (1.0,0.8,0.6,0.4,0.2):
        sec=[]
        for p in base:
            z=p.z+t*(ztop(p.x)-p.z); dy=max(0.0,cfy(z)+0.004-y0)*t
            sec.append(V((p.x,p.y+dy,z)))
        ext.append(sec)
    S=ext+S
    R=[R[0]]*len(ext)+R
    TOPSEC=ext[0]
    OUTCOL[sx]=[(V(sec[-2]),V(sec[-1])) for sec in S[:len(ext)+4]]
    for i in range(len(S)-1):
        for j in range(n-1):
            m=M['Gold'] if j<6 else (M['Purple'] if j<n-2 else M['Gold'])
            q=[tuple(S[i][j]),tuple(S[i][j+1]),tuple(S[i+1][j+1]),tuple(S[i+1][j])]
            C.face(q if sx>0 else q[::-1],m)
    # caps
    for i in (0,len(S)-1):
        ring=[tuple(p) for p in S[i]]; C.face(ring if i==0 else ring[::-1],M['Gold'] if i==0 else M['Purple'])
    tp=[V(p) for p in TOPSEC[1:-1]]
    strip(C,[tuple(p) for p in tp],[V((0,0,1))]*len(tp),0.03,0.02,M['Gold'])
    # gold trim on the flap's outer edge (bevelled strip on the top surface edge)
    pts=[];nr=[]
    for i in range(len(S)):
        p=S[i][-2]; q=S[i][-3]; D=(p-q).normalized(); nn=R[i][0][-1][1]
        pts.append(tuple(p-D*0.03)); nr.append(nn)
    strip(C,pts,nr,0.032,0.016,M['Gold'])
OUTCOL={}
for sx in (1,-1): flap(sx)
# ---- bridge: collar wall ends weld into the flap's outer edge (one continuous piece)
for sx,e in ((1,0),(-1,N-1)):
    col=sorted(OUTCOL[sx],key=lambda q:q[0].z)
    zs=[q[0].z for q in col]
    def at(z,which):
        z=min(max(z,zs[0]),zs[-1]); k=max(0,min(len(zs)-2,int(np.searchsorted(zs,z))-1))
        t=(z-zs[k])/max(1e-6,zs[k+1]-zs[k]); return col[k][which].lerp(col[k+1][which],t)
    for i in range(len(LV)):
        pass
    L=len(LV)
    FT=[at(O[i][e][2],0) for i in range(L)]; FB=[at(O[i][e][2],1) for i in range(L)]
    for i in range(L-1):
        q=[O[i][e],O[i+1][e],tuple(FT[i+1]),tuple(FT[i])]; C.face(q if sx<0 else q[::-1],M['Purple'])
        q=[I[i][e],tuple(FB[i]),tuple(FB[i+1]),I[i+1][e]]; C.face(q if sx<0 else q[::-1],M['Lining'])
    q=[O[-1][e],I[-1][e],tuple(FB[-1]),tuple(FT[-1])]; C.face(q if sx<0 else q[::-1],M['Gold'])
    a_=V(((O[-1][e][0]+I[-1][e][0])/2,(O[-1][e][1]+I[-1][e][1])/2,O[-1][e][2])); b_=(FT[-1]+FB[-1])/2
    strip(C,[tuple(a_.lerp(b_,t)) for t in np.linspace(0,1,5)],[V((0,0,1))]*5,TH*0.5+0.022,0.022,M['Gold'])
# remove the old flat traced lapel line/chevron from the coat trim (the folded flap replaces it)
tr=bpy.data.objects['Trim_Torso']; bmt=bmesh.new(); bmt.from_mesh(tr.data)
mw=tr.matrix_world; kill=[]
for f in bmt.faces:
    c=mw@f.calc_center_median()
    if c.y<0.3: continue
    yy=372+(4-c.z)*130; ax=abs(c.x)
    if 372<=yy<=549:
        ex=abs(XF(I_(OPL,yy))) if c.x>0 else abs(XF(I_(OPR,yy)))
        notch=max(0.0,1-abs(yy-425)/21.0)
        xo=abs(XF(204-21*notch)) if c.x>0 else abs(XF(366+21*notch))
        if ex+0.13<ax<xo+0.06: kill.append(f)
    elif 549<yy<=580 and 0.56<ax<0.74: kill.append(f)
bmesh.ops.delete(bmt,geom=kill,context='FACES')
# drop leftover fragments (small islands) on the upper front
bmt.faces.ensure_lookup_table(); unv=set(range(len(bmt.faces))); frag=[]
while unv:
    st=[unv.pop()]; g=[st[0]]
    while st:
        f=bmt.faces[st.pop()]
        for e in f.edges:
            for h in e.link_faces:
                if h.index in unv: unv.discard(h.index); st.append(h.index); g.append(h.index)
    cs=[mw@bmt.faces[i].calc_center_median() for i in g]
    lo=V((min(c.x for c in cs),min(c.y for c in cs),min(c.z for c in cs))); hi=V((max(c.x for c in cs),max(c.y for c in cs),max(c.z for c in cs)))
    cen=(lo+hi)/2
    if (hi-lo).length<0.15 and cen.y>0.3 and cen.z>Zmap(600): frag+=[bmt.faces[i] for i in g]
bmesh.ops.delete(bmt,geom=frag,context='FACES'); print('fragments removed',len(frag))
bmt.to_mesh(tr.data); bmt.free(); print('removed old lapel trim faces',len(kill))
ob=C.build(); print('collar tris',sum(len(p.vertices)-2 for p in ob.data.polygons))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
