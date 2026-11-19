import bpy, bmesh, math, numpy as np
from mathutils import Vector as V, Matrix
pi=math.pi
S=121.0; CXF=280.0; CXB=1179.5; CXS=722.0; CXH=694.0; KH=1.11
def Zmap(y): return 4+(372-y)/130 if y<=632 else (958-y)/163
def Ymap(z): return 372+(4-z)*130 if z>=2 else 958-z*163
def XF(px): return (CXF-px)/S
def interp(tab,y):
    return float(np.interp(y,[t[0] for t in tab],[t[1] for t in tab]))
MATS={}
def mat(name,col,metal=0.0,rough=0.6,emit=0.0):
    m=bpy.data.materials.new(name); m.use_nodes=True
    b=m.node_tree.nodes['Principled BSDF']
    lin=tuple(c**2.2 for c in col)
    b.inputs['Base Color'].default_value=(*lin,1); b.inputs['Metallic'].default_value=metal; b.inputs['Roughness'].default_value=rough
    if emit: b.inputs['Emission Color'].default_value=(*lin,1); b.inputs['Emission Strength'].default_value=emit
    m.diffuse_color=(*lin,1); m.metallic=metal; m.roughness=rough
    MATS[name]=m; return m
class Part:
    def __init__(s,name,bone):
        s.name=name; s.bone=bone; s.v=[]; s.key={}; s.f=[]; s.mats=[]
    def vid(s,p):
        k=(round(p[0],5),round(p[1],5),round(p[2],5))
        if k not in s.key: s.key[k]=len(s.v); s.v.append(k)
        return s.key[k]
    def face(s,pts,m):
        ids=[s.vid(p) for p in pts]
        keep=[ids[i] for i in range(len(ids)) if ids[i]!=ids[i-1]]
        if len(set(keep))<3: return
        if m not in s.mats: s.mats.append(m)
        s.f.append((keep,s.mats.index(m)))
    def loft(s,rings,m,cap0=None,cap1=None,closed=True,mats=None):
        n=len(rings[0]); rng=n if closed else n-1
        for i in range(len(rings)-1):
            mm=mats[i] if mats else m
            for j in range(rng):
                k=(j+1)%n; s.face([rings[i][j],rings[i][k],rings[i+1][k],rings[i+1][j]],mm)
        if cap0: s.face(rings[0][::-1],cap0)
        if cap1: s.face(rings[-1],cap1)
    def box(s,c,sz,m,R=None):
        hx,hy,hz=[v/2 for v in sz]
        p=[V((a*hx,b*hy,d*hz)) for d in(-1,1) for (a,b) in((-1,-1),(1,-1),(1,1),(-1,1))]
        if R: p=[R@q for q in p]
        p=[tuple(q+V(c)) for q in p]
        for q in((0,1,2,3),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)): s.face([p[i] for i in q],m)
    def build(s,fix=True,smooth_angle=None):
        bm=bmesh.new(); vs=[bm.verts.new(p) for p in s.v]
        for ids,mi in s.f:
            try: f=bm.faces.new([vs[i] for i in ids]); f.material_index=mi
            except ValueError: pass
        bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-5)
        if fix:
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
        me=bpy.data.meshes.new(s.name); bm.to_mesh(me); bm.free()
        for m in s.mats: me.materials.append(m)
        if smooth_angle:
            for p in me.polygons: p.use_smooth=True
            try: me.set_sharp_from_angle(angle=math.radians(smooth_angle))
            except Exception: pass
        ob=bpy.data.objects.new(s.name,me); bpy.context.scene.collection.objects.link(ob)
        c=bpy.data.objects[s.bone].constraints[0]
        cc=ob.constraints.new('CHILD_OF'); cc.target=c.target; cc.subtarget=c.subtarget; cc.inverse_matrix=c.inverse_matrix.copy()
        return ob
def se(cx,hx,cy,hy,z,n,N,t0=0.0,t1=2*pi,open_=False,mod=None):
    pts=[]
    for i in range(N):
        t=t0+(t1-t0)*(i/(N-1 if open_ else N)); s_,c_=math.sin(t),math.cos(t)
        x=hx*math.copysign(abs(s_)**(2/n),s_); y=hy*math.copysign(abs(c_)**(2/n),c_)
        if mod:
            k=mod(i,t); x*=k; y*=k
        pts.append((cx+x,cy+y,z))
    return pts
def nrm(pts):
    n=V((0,0,0))
    for i in range(len(pts)):
        a=V(pts[i]); b=V(pts[(i+1)%len(pts)]); n+=V(((a.y-b.y)*(a.z+b.z),(a.z-b.z)*(a.x+b.x),(a.x-b.x)*(a.y+b.y)))
    return n.normalized() if n.length>1e-12 else V((0,0,1))
def catmull(pts,n=12):
    P=[V(p) for p in pts]; P=[P[0]*2-P[1]]+P+[P[-1]*2-P[-2]]; out=[]
    for i in range(1,len(P)-2):
        for k in range(n):
            t=k/n; p0,p1,p2,p3=P[i-1],P[i],P[i+1],P[i+2]
            out.append(0.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t**3))
    out.append(P[-2]); return out
def ribbon(part,pts,widths,thick,m,outward=None,sides=6,n=10,tipcap=True):
    """flat strand: width along side vector, thickness along outward normal"""
    P=catmull(pts,n); L=len(P); rings=[]
    for i,p in enumerate(P):
        t=(P[min(i+1,L-1)]-P[max(i-1,0)]).normalized()
        o=outward(p) if outward else V((0,0,1))
        o=(o-t*o.dot(t));
        if o.length<1e-6: o=V((0,0,1))-t*t.z
        o.normalize(); sd=t.cross(o).normalized()
        f=i/(L-1); w=float(np.interp(f,np.linspace(0,1,len(widths)),widths)); th=thick*(0.35+0.65*min(1,w/max(widths)))
        ring=[]
        for j in range(sides):
            a=2*pi*j/sides; ring.append(tuple(p+sd*(w*math.cos(a))+o*(th*math.sin(a)*(1.0 if math.sin(a)>0 else 0.6))))
        rings.append(ring)
    part.loft(rings,m,cap0=m,cap1=m)
