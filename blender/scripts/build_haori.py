import bpy, bmesh, math, sys, cv2, numpy as np, triangle
from mathutils import Vector as V
SRC=sys.argv[-2]; OUT=sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=SRC)
pi=math.pi
atlas=cv2.imread('/tmp/w/atlas.png'); AH,AW=atlas.shape[:2]; TH=1086
MK=np.load('/tmp/w/masks.npz')
S=121.0; CXF=280.0; CXB=1179.5; CXS=722.0; CXH=694.0; KH=1.11; CXA=727.5
def Ymap(z): return 372+(4-z)*130 if z>=2 else 958-z*163
def Zmap(y): return 4+(372-y)/130 if y<=632 else (958-y)/163
def XF(px): return (CXF-px)/S
def pxF(p): return (CXF-p[0]*S, Ymap(p[2]))
def pxB(p): return (CXB+p[0]*S, Ymap(p[2]))
def pxS(p,cx=CXS,k=1.0): return (cx-p[1]*S/k, Ymap(p[2]))
def uv(px,tile): return (px[0]/AW, 1-(px[1]+tile*TH)/AH)
def samp(px,tile):
    x=int(min(max(px[0],0),AW-1)); y=int(min(max(px[1],0),TH-1))+tile*TH
    b,g,r=atlas[y,x].astype(int); return r,g,b
def dark(c): return (c[0]+c[1]+c[2])/3<105
# ---------------- materials
img=bpy.data.images.load('/tmp/w/atlas.png'); img.pack()
def texmat(name):
    m=bpy.data.materials.new(name); m.use_nodes=True; nt=m.node_tree; b=nt.nodes['Principled BSDF']
    t=nt.nodes.new('ShaderNodeTexImage'); t.image=img; nt.links.new(t.outputs['Color'],b.inputs['Base Color'])
    b.inputs['Roughness'].default_value=0.7; return m
MAT=texmat('RefAtlas')
GL=bpy.data.materials.new('GlowPurple'); GL.use_nodes=True; GL.diffuse_color=(0.75,0.3,1,1)
b=GL.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value=(0.75,0.3,1,1); b.inputs['Emission Color'].default_value=(0.75,0.3,1,1); b.inputs['Emission Strength'].default_value=3
# ---------------- part container
class Part:
    def __init__(s,name,bone,mat=MAT): s.name=name; s.bone=bone; s.v=[]; s.key={}; s.f=[]; s.mat=mat
    def vid(s,p):
        k=(round(p[0],4),round(p[1],4),round(p[2],4))
        if k not in s.key: s.key[k]=len(s.v); s.v.append(k)
        return s.key[k]
    def face(s,pts,uvs):
        ids=[s.vid(p) for p in pts]
        if len(set(ids))<3: return
        keep=[i for i in range(len(ids)) if ids[i]!=ids[i-1]]
        s.f.append(([ids[i] for i in keep],[uvs[i] for i in keep]))
    def build(s):
        bm=bmesh.new(); vs=[bm.verts.new(p) for p in s.v]; uvl=bm.loops.layers.uv.new('UVMap')
        for ids,uvs in s.f:
            try: f=bm.faces.new([vs[i] for i in ids])
            except ValueError: continue
            for l,u in zip(f.loops,uvs): l[uvl].uv=u
        bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
        bm.faces.ensure_lookup_table(); unv=set(range(len(bm.faces)))
        while unv:
            st=[unv.pop()]; grp=[st[0]]
            while st:
                f=bm.faces[st.pop()]
                for e in f.edges:
                    for g in e.link_faces:
                        if g.index in unv: unv.discard(g.index); st.append(g.index); grp.append(g.index)
            vol=0
            for i in grp:
                c=[v.co for v in bm.faces[i].verts]
                for k in range(1,len(c)-1): vol+=c[0].dot(c[k].cross(c[k+1]))
            if vol<0: bmesh.ops.reverse_faces(bm,faces=[bm.faces[i] for i in grp])
        me=bpy.data.meshes.new(s.name); bm.to_mesh(me); bm.free(); me.materials.append(s.mat)
        ob=bpy.data.objects.new(s.name,me); bpy.context.scene.collection.objects.link(ob)
        c=bpy.data.objects[s.bone].constraints[0]
        cc=ob.constraints.new('CHILD_OF'); cc.target=c.target; cc.subtarget=c.subtarget; cc.inverse_matrix=c.inverse_matrix.copy()
        return ob
def nrm(pts):
    n=V((0,0,0))
    for i in range(len(pts)):
        a=V(pts[i]); b=V(pts[(i+1)%len(pts)]); n+=V(((a.y-b.y)*(a.z+b.z),(a.z-b.z)*(a.x+b.x),(a.x-b.x)*(a.y+b.y)))
    return n.normalized() if n.length>1e-9 else V((0,0,1))
def view_of(n):
    if abs(n.z)>0.8: return 'C'
    if abs(n.y)>=abs(n.x): return 'F' if n.y>0 else 'B'
    return 'S'
def proj_uv(view,refpts,tile,side=(CXS,1.0)):
    if view=='F': px=[pxF(p) for p in refpts]
    elif view=='B': px=[pxB(p) for p in refpts]
    else: px=[pxS(p,*side) for p in refpts]
    return px
def sering(cx,hx,cy,hy,z,n,N,t0=0,t1=2*pi,open_=False):
    pts=[]
    for i in range(N):
        t=t0+(t1-t0)*(i/(N-1 if open_ else N)); s_,c_=math.sin(t),math.cos(t)
        pts.append((cx+hx*math.copysign(abs(s_)**(2/n),s_),cy+hy*math.copysign(abs(c_)**(2/n),c_),z))
    return pts
def rowloft(part,rows,n,N,tile,side=(CXS,1.0),gate=None,sw=None,captop=None,capbot=None,views=None,outward=1):
    """rows: (ypx,(X0,X1,Y0,Y1) final,(..) ref or None). """
    Rf=[];Rr=[]
    for r in rows:
        y,fe=r[0],r[1]; re=r[2] if len(r)>2 and r[2] else fe; z=Zmap(y)
        nn=r[3] if len(r)>3 else n
        Rf.append(sering((fe[0]+fe[1])/2,abs(fe[1]-fe[0])/2,(fe[2]+fe[3])/2,abs(fe[3]-fe[2])/2,z,nn,N))
        Rr.append(sering((re[0]+re[1])/2,abs(re[1]-re[0])/2,(re[2]+re[3])/2,abs(re[3]-re[2])/2,z,nn,N))
    for i in range(len(rows)-1):
        for j in range(N):
            k=(j+1)%N
            fp=[Rf[i][j],Rf[i][k],Rf[i+1][k],Rf[i+1][j]]; rp=[Rr[i][j],Rr[i][k],Rr[i+1][k],Rr[i+1][j]]
            nv=nrm(fp)*-1  # ring order gives inward normals for z decreasing; fix sign by radial check
            c=sum((V(p) for p in fp),V())/4; cen=V(((rows[i][1][0]+rows[i][1][1])/2,(rows[i][1][2]+rows[i][1][3])/2,c.z))
            nv=nrm(fp)
            if nv.dot(c-cen)<0: nv=-nv
            vw=view_of(V((nv.x,nv.y,0)).normalized() if abs(nv.z)<0.95 else nv)
            if views: vw=views(vw,nv)
            px=proj_uv(vw,rp,tile,side)
            if gate and not all(gate(samp(p,tile)) for p in px+[tuple(np.mean(px,0))]):
                part.face(fp,[uv(sw,tile)]*4)
            else: part.face(fp,[uv(p,tile) for p in px])
    if captop: part.face(Rf[0],[uv(captop,tile)]*N)
    if capbot: part.face(Rf[-1][::-1],[uv(capbot,tile)]*N)
parts=[]
# swatches (front px)
SW_NAVY=(240,770); SW_PURPLE=(221,480); SW_GOLD=(207,480); SW_MARBLE=(100,450); SW_BLACK=(200,925); SW_DARK=(221,470)
for nme,p in dict(navy=SW_NAVY,purple=SW_PURPLE,gold=SW_GOLD,marble=SW_MARBLE,black=SW_BLACK,dark=SW_DARK).items(): print('swatch',nme,samp(p,0))
# ======================= SLEEVES
def sleeve(name,bone,sx):
    P=Part(name,bone)
    if sx>0: xr=(XF(152),XF(39))
    else: xr=(XF(521),XF(408))
    xf=(sx*1.02,sx*2.03)
    yr=(-0.49,0.49); yf=(-0.535,0.535)
    def sh(e,d): return (e[0]+math.copysign(d,e[1]-e[0]),e[1]-math.copysign(d,e[1]-e[0]))
    rows=[(367,sh(xf,0.05)+sh(yf,0.05),sh(xr,0.05)+sh(yr,0.05)),(375,xf+yf,xr+yr),(603,xf+yf,xr+yr)]
    rowloft(P,rows,8,12,0,side=(CXA,1.0),captop=SW_MARBLE,capbot=SW_DARK)
    return P
parts+=[sleeve('Gear_RightArm','Right Arm',1),sleeve('Gear_LeftArm','Left Arm',-1)]
# ======================= COAT (open shell)
fgm=MK['fg']
def frow(y):
    xs=np.nonzero(fgm[y,0:560])[0]; return XF(xs.max()),XF(xs.min())   # (-x side, +x side)
def interp(tab,y):
    ys=[t[0] for t in tab]; return float(np.interp(y,ys,[t[1] for t in tab]))
OPL=[(352,225),(373,222),(400,216),(450,220),(500,222),(560,224),(632,213),(650,200),(700,187),(750,175),(800,163),(858,150)]
OPR=[(352,345),(373,347),(400,352),(440,350),(500,348),(560,350),(632,362),(650,366),(700,376),(750,386),(800,396),(858,407)]
YB=[(352,-0.66),(380,-0.66),(420,-0.58),(600,-0.57),(632,-0.66),(650,-0.79),(700,-0.87),(750,-0.97),(800,-1.11),(852,-1.23),(858,-1.2)]
YFt=[(352,0.61),(632,0.61),(858,0.67)]
NN=[(352,8),(632,8),(645,6),(700,5),(750,4.5),(800,4),(858,3.5)]
C=Part('Gear_Torso','Torso')
crow=[]
for y in (352,371,373,400,450,500,560,632,645,700,750,800,840,854,859):
    if y<372: x0,x1=-0.95,0.95
    elif y<=632: x0,x1=XF(408),XF(152)
    else:
        yy=min(y,852); x0,x1=frow(yy)
        if y>=859: x0+=0.03; x1-=0.03
    crow.append((y,x0,x1,interp(YB,y),interp(YFt,y),XF(interp(OPL,y)),XF(interp(OPR,y)),interp(NN,y)))
def coat_ring(r,th,N):
    y,x0,x1,yb,yf,ol,orr,n=r; cx=(x0+x1)/2; hx=(x1-x0)/2-th; cy=(yb+yf)/2; hy=(yf-yb)/2-th
    tl=math.asin(min(0.999,max(0.0,(ol-cx)/hx))**(n/2)); tr=math.asin(min(0.999,max(0.0,(cx-orr)/hx))**(n/2))
    return sering(cx,hx,cy,hy,Zmap(y),n,N,tl,2*pi-tr,True)
NC=21; THK=0.05
O=[coat_ring(r,0,NC) for r in crow]; I=[coat_ring(r,THK,NC) for r in crow]
for i in range(len(crow)-1):
    for j in range(NC-1):
        fp=[O[i][j],O[i][j+1],O[i+1][j+1],O[i+1][j]]
        nv=nrm(fp); c=sum((V(p) for p in fp),V())/4
        if nv.dot(V((c.x,c.y+0.1,0)))<0: nv=-nv
        vw=view_of(V((nv.x,nv.y,0)).normalized())
        C.face(fp,[uv(p,1) for p in proj_uv(vw,fp,1)])
        C.face([I[i][j+1],I[i][j],I[i+1][j],I[i+1][j+1]],[uv(SW_PURPLE,0)]*4)
    for e in (0,NC-1):
        C.face([O[i][e],I[i][e],I[i+1][e],O[i+1][e]],[uv(SW_GOLD,0)]*4)
for j in range(NC-1):
    C.face([O[-1][j],I[-1][j],I[-1][j+1],O[-1][j+1]],[uv(SW_GOLD,0)]*4)
    C.face([O[0][j+1],I[0][j+1],I[0][j],O[0][j]],[uv(SW_GOLD,0)]*4)
# inner body (kimono / obi) – closed loft, front projected
xb=(-0.93,0.93); yb_=(-0.45,0.545)
rowloft(C,[(366,xb+yb_),(500,xb+yb_),(632,xb+yb_)],8,8,1,gate=None,captop=SW_NAVY,capbot=SW_NAVY,
        views=lambda vw,nv: vw)
# fix: non-front faces of the inner body -> navy swatch (they are hidden by the coat)
parts.append(C)
# tassel
TP=Part('Gear_Tassel','Torso'); tas=MK['tas']; trow=[]
ys=np.nonzero(tas.any(1))[0]
for y in list(range(ys.min(),ys.max(),7))+[ys.max()]:
    xs=np.nonzero(tas[y])[0]; x0,x1=XF(xs.max()),XF(xs.min()); w=max(0.03,(x1-x0)); 
    trow.append((y,(x0,x1,0.58,0.58+min(w,0.30))))
rowloft(TP,trow,2,8,0,views=lambda vw,nv:'F',captop=(332,600),capbot=(332,700))
parts.append(TP)
# ======================= LEGS (hakama + boots)
def leg(name,bone,sx):
    P=Part(name,bone); rows=[]
    for y,xo,yf in((632,1.03,0.54),(700,1.09,0.63),(800,1.20,0.80),(870,1.31,0.92),(905,1.31,0.95)):
        rows.append((y,(0.0,sx*xo,-0.55,yf)))
    g=lambda c: dark(c) or (c[2]>c[1]+25 and c[0]<190)
    rowloft(P,rows,6,10,1,gate=g,sw=SW_NAVY,captop=SW_NAVY,capbot=SW_BLACK)
    rf=(0.0,sx*1.16,-0.535,0.87); rr=(sx*0.05,sx*1.16,-0.46,0.87)
    rowloft(P,[(907,rf,rr),(958,rf,rr)],10,8,0,captop=SW_BLACK,capbot=SW_BLACK)
    return P
parts+=[leg('Gear_RightLeg','Right Leg',1),leg('Gear_LeftLeg','Left Leg',-1)]
# ======================= HAIR (inflated from masks)
def tri_mask(mask,extra=None,area=90,eps=1.2):
    m8=mask.astype(np.uint8)
    cs,_=cv2.findContours(m8,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE); c=max(cs,key=cv2.contourArea)
    c=cv2.approxPolyDP(c,eps,True)[:,0,:].astype(float)
    vs=list(map(tuple,c)); segs=[(i,(i+1)%len(c)) for i in range(len(c))]
    if extra is not None:
        cs,_=cv2.findContours(extra.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
        for e in cs:
            if cv2.contourArea(e)<200: continue
            e=cv2.approxPolyDP(e,1.5,True)[:,0,:].astype(float); b=len(vs)
            vs+=list(map(tuple,e)); segs+=[(b+i,b+(i+1)%len(e)) for i in range(len(e))]
    t=triangle.triangulate(dict(vertices=np.array(vs),segments=np.array(segs)),'pq20a%d'%area)
    return t['vertices'],t['triangles'],t['vertex_markers'][:,0]
def smooth(a,k=9):
    return np.convolve(np.pad(a,(k,k),mode='edge'),np.ones(2*k+1)/(2*k+1),mode='valid')
def bil(arr,x,y):
    return arr[int(min(max(round(y),0),arr.shape[0]-1)),int(min(max(round(x),0),arr.shape[1]-1))]
HP=Part('Gear_Head','Head')
cap=MK['cap']; face=MK['face']; capside=MK['capside']
faceE=cv2.erode((face&cv2.erode(cap.astype(np.uint8),np.ones((9,9),np.uint8)).astype(bool)).astype(np.uint8),np.ones((3,3),np.uint8)).astype(bool)
Fz=np.zeros(TH); Bz=np.zeros(TH); Mz=np.zeros(TH)
HT=Ymap(5.1)
for y in range(TH):
    xs=np.nonzero(capside[y,560:905])[0]
    if y<=352 and len(xs):
        f=(CXH-(xs.min()+560))/S*KH; b=(CXH-(xs.max()+560))/S*KH
        if y>=HT: f=min(max(f,0.68),0.76); b=min(b,-0.70)
        Fz[y],Bz[y],Mz[y]=f,b,(0.0 if y>=HT-20 else (f+b)/2)
    elif y>352: Fz[y],Bz[y],Mz[y]=0.80,0.50,0.65
    else: Fz[y],Bz[y],Mz[y]=0.05,-0.05,0
y0=np.nonzero(capside.any(1))[0].min(); Fz[:y0]=Fz[y0]; Bz[:y0]=Bz[y0]; Mz[:y0]=Mz[y0]
Fz[353:372]=np.linspace(Fz[352],0.80,19); Bz[353:372]=np.linspace(-0.3,0.50,19); Mz[353:372]=np.linspace(0.0,0.65,19)
Fz,Bz,Mz=smooth(Fz,5),smooth(Bz,5),smooth(Mz,5)
vs,tr,mk=tri_mask(cap,faceE,area=110)
dt=cv2.distanceTransform(cap.astype(np.uint8),cv2.DIST_L2,5); R=0.16*S
fr=[];bk=[];infc=[]
for (px,py),m in zip(vs,mk):
    d=0 if m==1 else bil(dt,px,py); h=min(1.0,d/R); s=math.sqrt(max(0,1-(1-h)**2))
    yi=int(min(max(py,0),TH-1)); x=XF(px); z=Zmap(py)
    f=Mz[yi]+s*(Fz[yi]-Mz[yi]); b=Mz[yi]+s*(Bz[yi]-Mz[yi])
    inf=bool(bil(faceE,px,py)) and bil(cv2.erode(faceE.astype(np.uint8),np.ones((5,5),np.uint8)),px,py)>0
    if inf: f=0.22
    fr.append((x,f,z)); bk.append((x,b,z)); infc.append(inf)
def tri_uv(P_,pts,tile=0,side=(CXH,KH),force=None):
    n=nrm(pts); return n
for a,b_,c in tr:
    for pts,sgn in(([fr[a],fr[b_],fr[c]],1),([bk[c],bk[b_],bk[a]],-1)):
        n=nrm(pts)
        if n.y*sgn<0: n=-n; pts=pts[::-1]
        tl=0
        if abs(n.x)>abs(n.y)*1.1 and abs(n.x)>abs(n.z): px=[pxS(p,CXH,KH) for p in pts]; tl=1
        elif sgn>0: px=[pxF(p) for p in pts]
        else: px=[pxB(p) for p in pts]
        HP.face(pts,[uv(p,tl) for p in px])
# ponytail (inflated in the side plane)
pony=MK['pony']
vs,tr,mk=tri_mask(pony,None,area=160,eps=1.5)
dt=cv2.distanceTransform(pony.astype(np.uint8),cv2.DIST_L2,5); R=0.14*S
WT=[(130,0.22),(250,0.30),(330,0.45),(400,0.58),(470,0.45),(540,0.22),(610,0.12)]
L=[];Rr=[]
for (px,py),m in zip(vs,mk):
    d=0 if m==1 else bil(dt,px,py); h=min(1.0,d/R); s=math.sqrt(max(0,1-(1-h)**2))
    w=interp(WT,py)*s; y=(CXH-px)/S*KH; z=Zmap(py)
    L.append((w,y,z)); Rr.append((-w,y,z))
for a,b_,c in tr:
    for pts,sgn in(([L[a],L[b_],L[c]],1),([Rr[c],Rr[b_],Rr[a]],-1)):
        n=nrm(pts)
        if n.x*sgn<0: n=-n; pts=pts[::-1]
        if abs(n.y)>abs(n.x)*1.4 and n.y<0: px=[pxB(p) for p in pts]
        else: px=[pxS(p,CXH,KH) for p in pts]
        HP.face(pts,[uv(p,0) for p in px])
parts.append(HP)
# ======================= GLOW (separate plain meshes)
def boxpart(P,c,sz):
    cx,cy,cz=c; hx,hy,hz=[v/2 for v in sz]
    p=[(cx+a*hx,cy+b*hy,cz+d*hz) for d in(-1,1) for (a,b) in((-1,-1),(1,-1),(1,1),(-1,1))]
    for q in((0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)): P.face([p[i] for i in q],[(0.5,0.5)]*4)
GH=Part('Glow_Head','Head',GL)
def onhead(x,z,o=0.012): return (x,math.sqrt(max(0.01,0.36-x*x))+o,z)
x0,z0=XF(316),Zmap(262); x1,z1=XF(320),Zmap(345); w=0.022
a=[onhead(x0+w,z0),onhead(x0-w,z0),onhead(x1-w*0.3,z1),onhead(x1+w*0.3,z1)]; b=[(p[0],p[1]+0.015,p[2]) for p in a]
for q in((0,1,2,3),):
    GH.face(a[::-1],[(0.5,0.5)]*4); GH.face(b,[(0.5,0.5)]*4)
    for i in range(4): GH.face([a[i],a[(i+1)%4],b[(i+1)%4],b[i]],[(0.5,0.5)]*4)
parts.append(GH)
for nm,bone,sx in(('Glow_RightArm','Right Arm',1),('Glow_LeftArm','Left Arm',-1)):
    G=Part(nm,bone,GL)
    r0=sering(sx*1.525,0.52,0,0.55,Zmap(591),8,12); r1=sering(sx*1.525,0.52,0,0.55,Zmap(600),8,12)
    for j in range(12):
        k=(j+1)%12; G.face([r0[j],r0[k],r1[k],r1[j]],[(0.5,0.5)]*4)
    G.face(r0,[(0.5,0.5)]*12); G.face(r1[::-1],[(0.5,0.5)]*12)
    parts.append(G)
GT=Part('Glow_Torso','Torso',GL)
ybk=interp(YB,575)-0.012
d=0.16; zc=Zmap(575)
pts=[(0,ybk,zc+d),(d,ybk,zc),(0,ybk,zc-d),(-d,ybk,zc)]; pb=[(p[0],p[1]-0.02,p[2]) for p in pts]
GT.face(pts,[(0.5,0.5)]*4); GT.face(pb[::-1],[(0.5,0.5)]*4)
for i in range(4): GT.face([pts[i],pts[(i+1)%4],pb[(i+1)%4],pb[i]],[(0.5,0.5)]*4)
parts.append(GT)
objs=[p.build() for p in parts if p.f]
# ======================= head face texture (new material, mesh + UVs untouched)
hd=bpy.data.objects['Head']; me=hd.data; mw=hd.matrix_world
FW,FH=2048,1024
skinpx=atlas[:TH][MK['face']&~MK['locks']]; b_,g_,r_=skinpx[:,0].astype(int),skinpx[:,1].astype(int),skinpx[:,2].astype(int)
sel=(r_>200)&(r_-b_>40); skc=np.median(skinpx[sel],0)
fimg=np.zeros((FH,FW,3),np.float32); fimg[:]=skc
facem=cv2.dilate(MK['face'].astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
uvd=me.uv_layers[0].data
for p in me.polygons:
    nw=(mw.to_3x3()@p.normal).normalized()
    if nw.y<0.25: continue
    li=list(p.loop_indices)
    for k in range(1,len(li)-1):
        tri=[li[0],li[k],li[k+1]]
        U=np.array([[uvd[i].uv[0]*FW,uvd[i].uv[1]*FH] for i in tri]); Wd=np.array([list(mw@me.vertices[me.loops[i].vertex_index].co) for i in tri])
        x0,y0=np.floor(U.min(0)).astype(int); x1,y1=np.ceil(U.max(0)).astype(int)
        gx,gy=np.meshgrid(np.arange(x0,x1+1)+0.5,np.arange(y0,y1+1)+0.5)
        d=(U[1,1]-U[2,1])*(U[0,0]-U[2,0])+(U[2,0]-U[1,0])*(U[0,1]-U[2,1])
        if abs(d)<1e-9: continue
        w0=((U[1,1]-U[2,1])*(gx-U[2,0])+(U[2,0]-U[1,0])*(gy-U[2,1]))/d
        w1=((U[2,1]-U[0,1])*(gx-U[2,0])+(U[0,0]-U[2,0])*(gy-U[2,1]))/d; w2=1-w0-w1
        ins=(w0>=-0.02)&(w1>=-0.02)&(w2>=-0.02)
        wx=w0*Wd[0,0]+w1*Wd[1,0]+w2*Wd[2,0]; wz=w0*Wd[0,2]+w1*Wd[1,2]+w2*Wd[2,2]
        px=np.clip((CXF-wx*S).round().astype(int),0,AW-1); py=np.clip((372+(4-wz)*130).round().astype(int),0,TH-1)
        ok=ins&facem[py,px]
        yy=np.clip(gy.astype(int),0,FH-1); xx=np.clip(gx.astype(int),0,FW-1)
        fimg[yy[ok],xx[ok]]=atlas[py[ok],px[ok]]
rgba=np.concatenate([fimg[...,::-1]/255.0,np.ones((FH,FW,1),np.float32)],2)
fi=bpy.data.images.new('HeadFace',FW,FH); fi.pixels.foreach_set(rgba.ravel()); fi.filepath_raw='/tmp/w/HeadFace.png'; fi.file_format='PNG'; fi.save(); fi.pack()
hm=bpy.data.materials.new('HeadFace'); hm.use_nodes=True; t=hm.node_tree.nodes.new('ShaderNodeTexImage'); t.image=fi
hm.node_tree.links.new(t.outputs['Color'],hm.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
me.materials.clear(); me.materials.append(hm)
# ======================= rig materials (material only; meshes/UVs untouched)
skin=skc[::-1]/255.0
def flat(name,c):
    m=bpy.data.materials.new(name); m.use_nodes=True; m.diffuse_color=(*c,1)
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*[x**2.2 for x in c],1); return m
SK=flat('Skin',tuple(skin)); NV=flat('BodyNavy',(0.1,0.09,0.2))
for n,m in(('Left Arm',SK),('Right Arm',SK),('Torso',NV),('Left Leg',NV),('Right Leg',NV)):
    o=bpy.data.objects[n]; o.data.materials.clear(); o.data.materials.append(m)
bpy.ops.wm.save_as_mainfile(filepath=OUT)
tot=0
for ob in objs:
    t=sum(len(p.vertices)-2 for p in ob.data.polygons); tot+=t; print(f'{ob.name:16s} verts {len(ob.data.vertices):5d} tris {t}')
print('TOTAL',tot)
