import bpy, bmesh, math, sys
from mathutils import Vector, Matrix
SRC=sys.argv[-2]; OUT=sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=SRC)
V=Vector
pi=math.pi
# ---------------- materials
def mat(name,col,metal=0.0,rough=0.6,emit=None):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes=True
    b=m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value=(*col,1)
    b.inputs['Metallic'].default_value=metal
    b.inputs['Roughness'].default_value=rough
    if emit:
        b.inputs['Emission Color'].default_value=(*emit,1); b.inputs['Emission Strength'].default_value=3.0
    m.diffuse_color=(*col,1)
    return m
M={
 'Marble':mat('Marble',(0.93,0.89,0.98),0,0.35),
 'Gold':mat('Gold',(0.88,0.64,0.14),0.85,0.3),
 'Navy':mat('Navy',(0.10,0.09,0.24),0,0.8),
 'NavyDark':mat('NavyDark',(0.05,0.045,0.12),0,0.85),
 'Black':mat('Black',(0.025,0.025,0.035),0,0.7),
 'Purple':mat('PurpleLining',(0.34,0.10,0.58),0,0.6),
 'Hair':mat('Hair',(0.80,0.78,0.88),0,0.5),
 'White':mat('WhiteTrim',(0.93,0.92,0.97),0,0.6),
 'Glow':mat('GlowPurple',(0.78,0.35,1.0),0,0.4,emit=(0.78,0.35,1.0)),
}
# ---------------- kit
class Acc:
    def __init__(s,name,bone): s.name=name; s.bone=bone; s.bm=bmesh.new(); s.mats=[]
    def mi(s,m):
        if m not in s.mats: s.mats.append(m)
        return s.mats.index(m)
    def face(s,pts,m):
        vs=[s.bm.verts.new(tuple(p)) for p in pts]
        try:
            f=s.bm.faces.new(vs); f.material_index=s.mi(m)
        except ValueError: pass
    def loft(s,rings,m,cap0=True,cap1=True,mats=None):
        n=len(rings[0])
        for i in range(len(rings)-1):
            mm=mats[i] if mats else m
            for j in range(n):
                k=(j+1)%n
                s.face([rings[i][j],rings[i][k],rings[i+1][k],rings[i+1][j]],mm)
        if cap0: s.face(rings[0][::-1],m)
        if cap1: s.face(rings[-1],m)
    def box(s,c,sz,m,rot=None):
        cx,cy,cz=c; hx,hy,hz=[v/2 for v in sz]
        pts=[V((x,y,z)) for z in(-hz,hz) for (x,y) in((-hx,-hy),(hx,-hy),(hx,hy),(-hx,hy))]
        if rot: pts=[rot@p for p in pts]
        pts=[p+V(c) for p in pts]
        s.loft([pts[0:4],pts[4:8]],m)
    def build(s):
        bm=s.bm
        bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-5)
        bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
        bm.faces.ensure_lookup_table()
        unv=set(range(len(bm.faces)))
        while unv:
            st=[unv.pop()]; grp=[st[0]]
            while st:
                f=bm.faces[st.pop()]
                for e in f.edges:
                    for g in e.link_faces:
                        if g.index in unv: unv.discard(g.index); st.append(g.index); grp.append(g.index)
            vol=0
            for i in grp:
                f=bm.faces[i]; vs=[v.co for v in f.verts]
                for k in range(1,len(vs)-1): vol+=vs[0].dot(vs[k].cross(vs[k+1]))
            if vol<0: bmesh.ops.reverse_faces(bm,faces=[bm.faces[i] for i in grp])
        me=bpy.data.meshes.new(s.name); bm.to_mesh(me); bm.free()
        for m in s.mats: me.materials.append(m)
        for p in me.polygons: p.use_smooth=False
        ob=bpy.data.objects.new(s.name,me); bpy.context.scene.collection.objects.link(ob)
        src=bpy.data.objects[s.bone]; c=src.constraints[0]
        cc=ob.constraints.new('CHILD_OF'); cc.target=c.target; cc.subtarget=c.subtarget
        cc.inverse_matrix=c.inverse_matrix.copy()
        return ob
def se(a,b,n,N,cx=0,cy=0,z=0,t0=0.0,t1=2*pi,open_=False):
    pts=[]
    for i in range(N):
        t=t0+(t1-t0)*(i/(N if not open_ else N-1))
        s_,c_=math.sin(t),math.cos(t)
        x=a*math.copysign(abs(s_)**(2/n),s_); y=b*math.copysign(abs(c_)**(2/n),c_)
        pts.append(V((cx+x,cy+y,z)))
    return pts
def sweep(path,wa,wb,N=6,up=V((1,0,0))):
    rings=[]
    for i,p in enumerate(path):
        p=V(p)
        t=(V(path[min(i+1,len(path)-1)])-V(path[max(i-1,0)])).normalized()
        sd=up-t*up.dot(t); 
        if sd.length<1e-3: sd=V((0,1,0))-t*t.y
        sd.normalize(); nm=t.cross(sd).normalized()
        a=wa[i]; b=wb[i]
        rings.append([p+sd*(a*math.cos(2*pi*j/N))+nm*(b*math.sin(2*pi*j/N)) for j in range(N)])
    return rings
def tube(acc,path,wa,wb,m,N=6,up=V((1,0,0))):
    r=sweep(path,wa,wb,N,up); acc.loft(r,m)
def spike(acc,base,tip,w,m,n=4,up=V((1,0,0)),wb=None):
    tube(acc,[base,(V(base)+V(tip))/2,tip],[w,w*0.55,0.004],[wb or w,(wb or w)*0.55,0.004],m,n,up)
def shell(acc,specs,N,th,mo,mi_,medge,mhem,hem_k=1,front_open=True):
    """open double-wall coat; specs=[(z,a,b,cy,open_hw,n)]"""
    O=[];I=[]
    for (z,a,b,cy,ohw,n) in specs:
        # front edge angle where |x|=ohw on the front
        t0=math.asin(min(0.99,ohw/a)) if a>0 else 0
        O.append(se(a,b,n,N,0,cy,z,t0,2*pi-t0,True))
        I.append(se(a-th,b-th,n,N,0,cy,z,t0,2*pi-t0,True))
    R=len(specs)
    for i in range(R-1):
        mo_i=mhem if i>=R-1-hem_k else mo
        for j in range(N-1):
            acc.face([O[i][j],O[i][j+1],O[i+1][j+1],O[i+1][j]],mo_i)
            acc.face([I[i][j+1],I[i][j],I[i+1][j],I[i+1][j+1]],mi_)
        for e in (0,N-1):
            acc.face([O[i][e],I[i][e],I[i+1][e],O[i+1][e]],medge)
    for j in range(N-1):
        acc.face([O[R-1][j],I[R-1][j],I[R-1][j+1],O[R-1][j+1]],mhem)
        acc.face([O[0][j+1],I[0][j+1],I[0][j],O[0][j]],mo)
    return O,I
def disc(acc,c,nrm,r,th,m,N=10,ri=0):
    nrm=V(nrm).normalized(); q=V((0,0,1)).rotation_difference(nrm)
    top=[];bot=[]
    for j in range(N):
        t=2*pi*j/N; p=V((r*math.cos(t),r*math.sin(t),0))
        top.append(q@(p+V((0,0,th/2)))+V(c)); bot.append(q@(p-V((0,0,th/2)))+V(c))
    acc.loft([bot,top],m)
def ring_thin(acc,c,nrm,r,w,th,m,N=12):
    nrm=V(nrm).normalized(); q=V((0,0,1)).rotation_difference(nrm)
    def P(rr,z): return [q@V((rr*math.cos(2*pi*j/N),rr*math.sin(2*pi*j/N),z))+V(c) for j in range(N)]
    a=P(r+w/2,-th/2);b=P(r+w/2,th/2);c2=P(r-w/2,th/2);d=P(r-w/2,-th/2)
    acc.loft([a,b,c2,d],m,False,False,None)
    n=N
    for j in range(n):
        k=(j+1)%n
        acc.face([d[j],d[k],a[k],a[j]],m)
# ---------------- coordinate maps from the reference (front view px)
def X(px): return (280-px)/125.0
# =====================================================  HEAD
H=Acc('Gear_Head','Head'); HG=Acc('Glow_Head','Head')
hr=0.0
# upper hair cap (closed dome) – stays above the rig face (face is z<5.03)
rings=[]
for z,r,n,cy in [(4.98,0.665,8,0),(5.2,0.70,6,0),(5.45,0.66,4,0),(5.7,0.45,3,0),(5.85,0.2,2.5,0),(5.92,0.05,2,0)]:
    rings.append(se(r,r,n,12,0,cy,z))
H.loft(rings,M['Hair'])
# back hair shell (open at front, covers back + sides of head down to nape)
O,I=shell(H,[(5.0,0.67,0.67,0,0.0,4),(4.7,0.665,0.665,0,0.55,4),(4.35,0.66,0.66,-0.02,0.58,4),(4.05,0.62,0.6,-0.04,0.5,4)],12,0.05,M['Hair'],M['Hair'],M['Hair'],M['Hair'],hem_k=0)
# bangs (spiky fringe above brows)
import random; random.seed(7)
for i,x in enumerate([-0.60,-0.46,-0.31,-0.15,0.0,0.15,0.31,0.46,0.60]):
    yb=math.sqrt(max(0.05,0.675**2-x*x))
    tipz=5.02-0.03*abs(x)*1.2-random.uniform(0,0.06)
    spike(H,(x,yb-0.04,5.3),(x*1.08,yb+0.06,tipz),0.12,M['Hair'],3,up=V((1,0,0)),wb=0.05)
# side locks (flank the face, fall to chest)
for sx in(-1,1):
    for (xo,yo,zb,lw) in[(0.66,0.12,3.55,0.10),(0.60,0.34,4.15,0.075)]:
        path=[(sx*xo,yo,5.05),(sx*(xo+0.08),yo+0.17,4.7),(sx*(xo+0.12),yo+0.27,(5.05+zb)/2),(sx*(xo+0.15),yo+0.33,zb)]
        tube(H,path,[lw*1.1,lw*1.2,lw*0.9,0.01],[0.06,0.06,0.05,0.01],M['Hair'],5,up=V((0,1,0)))
    # swept side spikes (wild tufts)
    spike(H,(sx*0.5,0.15,5.3),(sx*1.15,0.1,5.15),0.1,M['Hair'],3,up=V((0,1,0)),wb=0.06)
    spike(H,(sx*0.55,-0.2,5.4),(sx*1.1,-0.3,5.4),0.09,M['Hair'],3,up=V((0,1,0)),wb=0.06)
# ponytail
pp=[(0,-0.4,5.4),(0,-0.75,5.9),(0,-1.2,6.5),(0,-1.55,6.3),(0,-1.75,5.6),(0,-1.7,4.7),(0,-1.5,3.6),(0,-1.2,2.7),(0,-1.0,2.1)]
tube(H,pp,[0.15,0.28,0.4,0.5,0.55,0.55,0.48,0.35,0.01],[0.12,0.2,0.25,0.28,0.28,0.26,0.22,0.15,0.01],M['Hair'],6,up=V((1,0,0)))
# side strands falling from the ponytail
for sx in(-1,1):
    pth=[(sx*0.3,-0.9,5.6),(sx*0.6,-1.2,5.2),(sx*0.75,-1.4,4.4),(sx*0.8,-1.35,3.6),(sx*0.75,-1.2,3.0)]
    tube(H,pth,[0.1,0.16,0.15,0.1,0.01],[0.1,0.12,0.1,0.07,0.01],M['Hair'],5,up=V((1,0,0)))
    pth=[(sx*0.1,-1.0,5.6),(sx*0.18,-1.45,5.1),(sx*0.38,-1.7,4.3),(sx*0.42,-1.6,3.5)]
    tube(H,pth,[0.08,0.14,0.12,0.01],[0.08,0.1,0.08,0.01],M['Hair'],5,up=V((1,0,0)))
# gold hair tie
q=V((0,-0.5,0.8)).normalized()
ring_thin(H,(0,-0.75,5.88),V((0,-0.5,1)),0.30,0.10,0.24,M['Gold'],8)
# scar glow (over left eye = -x) slanted slit
def onhead(x,z): return V((x,math.sqrt(0.6**2-x*x)+0.012,z))
pts=[(-0.36,5.22),(-0.31,4.50)]
w=0.03
p1=onhead(-0.37,5.18);p2=onhead(-0.32,4.45)
for dz in(0,):
    a=[onhead(-0.37-w,5.18),onhead(-0.37+w,5.18),onhead(-0.32+w,4.45),onhead(-0.32-w,4.45)]
    b=[V((p.x,p.y+0.012,p.z)) for p in a]
    HG.loft([a,b],M['Glow'])
# =====================================================  TORSO
T=Acc('Gear_Torso','Torso'); TG=Acc('Glow_Torso','Torso')
# coat body shell: z, a, b, cy, open, n
cs=[(4.02,1.19,0.69,0.0,0.50,6),(3.2,1.20,0.70,0.0,0.52,6),(2.4,1.24,0.72,-0.02,0.58,6),(1.7,1.45,0.80,-0.08,0.72,5),(1.1,1.72,0.88,-0.20,0.86,4),(0.80,1.86,0.92,-0.27,0.93,3.2),(0.64,1.93,0.94,-0.30,0.96,3.0)]
O,I=shell(T,cs,15,0.075,M['Marble'],M['Purple'],M['Gold'],M['Gold'],hem_k=1)
# outer coat-surface sampler for decals
def coat_pt(z,t):
    for i in range(len(cs)-1):
        if cs[i+1][0]<=z<=cs[i][0] or (i==len(cs)-2):
            z0,a0,b0,c0,o0,n0=cs[i];z1,a1,b1,c1,o1,n1=cs[i+1]; f=(z0-z)/(z0-z1)
            a=a0+(a1-a0)*f+0.0;b=b0+(b1-b0)*f;cy=c0+(c1-c0)*f;n=n0+(n1-n0)*f
            s_,c_=math.sin(t),math.cos(t)
            return V((a*math.copysign(abs(s_)**(2/n),s_),cy+b*math.copysign(abs(c_)**(2/n),c_),z))
# gold hem edge (extra thick band on outside, bottom 0.14 of the coat)
# collar (standing, open at front, flares out)
cl=[(4.0,1.0,0.66,0.0,0.30,6),(4.35,1.0,0.69,0.0,0.36,6),(4.88,1.02,0.74,-0.02,0.50,6)]
O2,I2=shell(T,cl,13,0.07,M['Marble'],M['Purple'],M['Gold'],M['Marble'],hem_k=0)
# chest kimono (navy) – inside the open coat, under the obi down to the hakama
T.loft([se(0.97,0.52,6,16,0,0,z) for z in(2.6,3.4,4.03)],M['Navy'])
# V neckline lapels (white trim)
T.box((0.12,0.535,3.62),(0.07,0.03,0.88),M['White'],rot=Matrix.Rotation(-0.30,3,'Y'))
T.box((-0.20,0.54,3.62),(0.07,0.03,0.88),M['White'],rot=Matrix.Rotation(0.30,3,'Y'))
# white sash above obi + obi
T.loft([se(1.09,0.61,6,18,0,0,z) for z in(3.64,3.78)],M['White'])
T.loft([se(1.10,0.63,6,18,0,0,z) for z in(2.84,3.0,3.64)],M['Black'])
# obi knot / bow bundle at left front
T.box((-0.35,0.66,3.2),(0.55,0.08,0.52),M['Black'])
# tassel
ring_thin(T,(-0.44,0.74,3.0),(0,1,0),0.08,0.03,0.05,M['Gold'],8)
tp=[(-0.44,0.76,2.95),(-0.44,0.76,2.8),(-0.44,0.76,2.6),(-0.44,0.76,2.35),(-0.44,0.76,2.14)]
tube(T,tp,[0.05,0.10,0.19,0.17,0.12],[0.05,0.10,0.19,0.17,0.12],M['Gold'],8)
# hakama top (hip) – visible through coat opening
T.loft([se(1.10,0.60,6,18,0,0,z) for z in(2.0,2.5,2.9)],M['Navy'])
# back emblem: nested gold diamonds + purple glow core + spine lines (flush on coat back)
yb=-(0.70)-0.015
rot45=Matrix.Rotation(pi/4,3,'Y')
def diamond(cz,s,th,m,G):
    for k,(sx,sz) in enumerate([(s,th)]):
        pass
def dia(acc,cz,half,w,m,y):
    # four slabs forming a diamond ring
    for (dx,dz,ang) in[(-1,-1,-pi/4),(1,-1,pi/4),(-1,1,pi/4),(1,1,-pi/4)]:
        L=half*math.sqrt(2)
        acc.box((dx*half/2,y,cz+dz*half/2),(L,0.03,w),m,rot=Matrix.Rotation(ang,3,'Y'))
dia(T,3.12,0.36,0.045,M['Gold'],yb)
dia(T,3.12,0.24,0.04,M['Gold'],yb)
dia(TG,3.12,0.14,0.07,M['Glow'],yb-0.005)
TG.box((0,yb-0.01,3.12),(0.1,0.03,0.1),M['Glow'],rot=rot45)
T.box((0,yb,2.1),(0.05,0.03,1.55),M['Gold'])
TG.box((0.055,yb-0.008,2.15),(0.03,0.025,1.35),M['Glow'])
TG.box((-0.055,yb-0.008,2.15),(0.03,0.025,1.35),M['Glow'])
# cloud scroll medallions (purple disc + gold ring) flush on coat surface
def surf(z,xt,front):
    best=None
    for k in range(0,361):
        t=(k/360)*pi if front else pi+(k/360)*pi
        for sgn in(1,-1):
            tt=t if sgn>0 else 2*pi-t
            p=coat_pt(z,tt)
            if (p.y>-0.1)==front or True:
                d=abs(p.x-xt)
                if best is None or d<best[0]: best=(d,tt,p)
    return best
def nrm_at(z,t):
    p=coat_pt(z,t); pt=coat_pt(z,t+0.02); pz=coat_pt(z-0.05,t)
    n=(pt-p).cross(pz-p).normalized()
    cy=-0.1
    if n.dot(V((p.x,p.y-cy,0)))<0: n=-n
    return p,n
def medal(x,z,r,front):
    # choose branch: front => y larger
    cands=[]
    for k in range(0,361):
        for sgn in(1,-1):
            tt=(k/360)*pi if sgn>0 else 2*pi-(k/360)*pi
            if not front: tt=pi+(k/360)*pi if sgn>0 else pi-(k/360)*pi
            p=coat_pt(z,tt)
            cands.append((abs(p.x-x)+ (0 if (p.y>cs_cy(z))==front else 9),tt))
    d,tt=min(cands)
    p,n=nrm_at(z,tt)
    disc(T,p+n*0.01,n,r,0.03,M['Purple'],8)
    ring_thin(T,p+n*0.035,n,r*0.9,0.05,0.03,M['Gold'],8)
def cs_cy(z):
    for i in range(len(cs)-1):
        if cs[i+1][0]<=z<=cs[i][0]:
            f=(cs[i][0]-z)/(cs[i][0]-cs[i+1][0]); return cs[i][3]+(cs[i+1][3]-cs[i][3])*f
    return cs[-1][3]
for sx in(-1,1):
    medal(sx*1.25,1.12,0.30,True); medal(sx*1.0,1.55,0.2,True)
    medal(sx*1.4,1.18,0.36,False); medal(sx*0.8,1.12,0.28,False)
# =====================================================  ARMS
def arm(name,bone,sx):
    A=Acc(name,bone); AG=Acc('Glow_'+name[5:],bone)
    cx=1.5*sx
    # sleeve: wide closed box-ish loft (superellipse), z 2.84..4.06
    A.loft([se(0.64,0.62,6,12,cx,0,z) for z in(2.80,2.95,3.5,4.05)],M['Marble'])
    # cuff: gold, glow, gold bands (embedded)
    for (z0,z1,m,G) in[(3.20,3.34,M['Gold'],A),(3.34,3.40,M['Glow'],AG),(3.40,3.52,M['Gold'],A),(2.86,2.99,M['Gold'],A),(2.93,2.97,M['Purple'],A)]:
        if m==M['Purple']: continue
        G.loft([se(0.655,0.635,6,12,cx,0,z) for z in(z0,z1)],m)
    AG.loft([se(0.66,0.64,6,12,cx,0,z) for z in(2.99,3.2)],M['Glow'])
    # pauldron cap
    A.loft([se(0.655,0.635,6,12,cx,0,4.03),se(0.60,0.58,6,12,cx,0,4.10),se(0.45,0.45,6,12,cx,0,4.13)],M['Gold'])
    # front gold lines (on +y face) : outer vertical, diagonal, inner short vertical
    yf=0.625
    for ym,sgn in[(yf,1),(-yf,-1)]:
        A.box((cx+sx*0.50,ym,3.60),(0.06,0.03,0.78),M['Gold'])
        A.box((cx+sx*0.18,ym,3.84),(0.55,0.03,0.06),M['Gold'],rot=Matrix.Rotation(sx*0.55,3,'Y'))
        A.box((cx-sx*0.45,ym,3.88),(0.06,0.03,0.38),M['Gold'])
        A.box((cx,ym,4.00),(1.2,0.03,0.07),M['Gold'])
    return A,AG
AL,ALG=arm('Gear_LeftArm','Left Arm',-1); AR,ARG=arm('Gear_RightArm','Right Arm',1)
# =====================================================  LEGS
def leg(name,bone,sx):
    L=Acc(name,bone); cx=0.5*sx
    # hakama tube (pleated: n=4 corners), wide at hem
    L.loft([se(0.62,0.60,6,16,cx,0,2.0),se(0.66,0.66,5,16,cx,0,1.3),se(0.76,0.76,5,16,cx,0,0.65),se(0.84,0.80,5,16,cx,0,0.30)],M['Navy'])
    # pleat lines
    # boot + gold trim
    L.loft([se(0.57,0.58,10,12,cx,0,z) for z in(0.0,0.30)],M['Black'])
    L.loft([se(0.585,0.595,10,12,cx,0,z) for z in(0.08,0.14)],M['Gold'])
    L.loft([se(0.585,0.595,10,12,cx,0,z) for z in(0.26,0.30)],M['Gold'])
    return L
LL=leg('Gear_LeftLeg','Left Leg',-1); LR=leg('Gear_RightLeg','Right Leg',1)
# ---------------- build objects
objs=[]
tab=[]
for acc in(H,HG,T,TG,AL,ALG,AR,ARG,LL,LR):
    if len(acc.bm.faces)==0: continue
    ob=acc.build(); objs.append(ob)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
# ---------------- checks
import bmesh as bm_
tot=0
for ob in objs:
    me=ob.data
    b=bm_.new(); b.from_mesh(me)
    bm_.ops.triangulate(b,faces=b.faces[:])
    vol=0; 
    # island signed volume
    seen=set(); neg=0
    for v in b.verts: pass
    isl=[]
    unv=set(f.index for f in b.faces); b.faces.ensure_lookup_table()
    while unv:
        st=[unv.pop()]; grp=[st[0]]
        while st:
            f=b.faces[st.pop()]
            for e in f.edges:
                for g in e.link_faces:
                    if g.index in unv: unv.discard(g.index); st.append(g.index); grp.append(g.index)
        vv=sum(b.faces[i].verts[0].co.dot(b.faces[i].verts[1].co.cross(b.faces[i].verts[2].co)) for i in grp)/6
        isl.append(vv)
    neg=sum(1 for v in isl if v<0)
    if neg: print('  neg island vols',[round(v,5) for v in isl if v<0])
    print(f'{ob.name:18s} verts {len(me.vertices):5d} tris {len(b.faces):5d} islands {len(isl):3d} inside-out {neg}')
    tot+=len(b.faces); b.free()
print('TOTAL gear tris',tot)
