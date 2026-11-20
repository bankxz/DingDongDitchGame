import bpy,bmesh,math,numpy as np
from mathutils import Vector as V, Matrix
pi=math.pi
S=121.0
def Zmap(y): return 4+(372-y)/130 if y<=632 else (958-y)/163
def XF(px): return (280-px)/S
MAT={}
def mat(name,col,metal=0.0,rough=0.6,emit=0.0):
    if name in MAT: return MAT[name]
    if name in bpy.data.materials: MAT[name]=bpy.data.materials[name]; return MAT[name]
    m=bpy.data.materials.new(name); m.use_nodes=True; b=m.node_tree.nodes['Principled BSDF']
    lin=tuple(c**2.2 for c in col)
    b.inputs['Base Color'].default_value=(*lin,1); b.inputs['Metallic'].default_value=metal; b.inputs['Roughness'].default_value=rough
    if emit: b.inputs['Emission Color'].default_value=(*lin,1); b.inputs['Emission Strength'].default_value=emit
    m.diffuse_color=(*lin,1); m.metallic=metal; m.roughness=rough; MAT[name]=m; return m
def mats():
    return dict(Marble=mat('Marble',(0.93,0.90,0.97),0,0.35),Gold=mat('Gold',(0.90,0.68,0.30),0.55,0.35),
        Lining=mat('Lining',(0.40,0.20,0.60)),Glow=mat('GlowPurple',(0.80,0.42,1.0),0,0.4,3.0),
        Purple=mat('Purple',(0.36,0.18,0.52)),Navy=mat('Navy',(0.17,0.15,0.30),0,0.8),Black=mat('Black',(0.06,0.055,0.07),0,0.7),
        White=mat('WhiteCloth',(0.95,0.94,0.97)),Hair=mat('Hair',(0.94,0.92,0.98),0,0.5),Skin=mat('Skin',(0.96,0.80,0.68),0,0.8))
class Part:
    def __init__(s,name,bone): s.name=name; s.bone=bone; s.v=[]; s.key={}; s.f=[]; s.mats=[]
    def vid(s,p):
        k=(round(p[0],5),round(p[1],5),round(p[2],5))
        if k not in s.key: s.key[k]=len(s.v); s.v.append(k)
        return s.key[k]
    def face(s,pts,m):
        ids=[s.vid(p) for p in pts]; keep=[ids[i] for i in range(len(ids)) if ids[i]!=ids[i-1]]
        if len(set(keep))<3: return
        if m not in s.mats: s.mats.append(m)
        s.f.append((keep,s.mats.index(m)))
    def loft(s,rings,m,cap0=None,cap1=None,closed=True):
        n=len(rings[0]); rng=n if closed else n-1
        for i in range(len(rings)-1):
            for j in range(rng):
                k=(j+1)%n; s.face([rings[i][j],rings[i][k],rings[i+1][k],rings[i+1][j]],m)
        if cap0: s.face(rings[0][::-1],cap0)
        if cap1: s.face(rings[-1],cap1)
    def build(s):
        bm=bmesh.new(); vs=[bm.verts.new(p) for p in s.v]
        for ids,mi in s.f:
            try: f=bm.faces.new([vs[i] for i in ids]); f.material_index=mi
            except ValueError: pass
        bmesh.ops.remove_doubles(bm,verts=bm.verts,dist=1e-5)
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
        old=bpy.data.objects.get(s.name)
        if old: bpy.data.objects.remove(old)
        me=bpy.data.meshes.new(s.name); bm.to_mesh(me); bm.free()
        for m in s.mats: me.materials.append(m)
        ob=bpy.data.objects.new(s.name,me); bpy.context.scene.collection.objects.link(ob)
        c=bpy.data.objects[s.bone].constraints[0]
        cc=ob.constraints.new('CHILD_OF'); cc.target=c.target; cc.subtarget=c.subtarget; cc.inverse_matrix=c.inverse_matrix.copy()
        return ob
def rrect(cx,cy,hx,hy,r,z,seg=3):
    """rounded rectangle ring, CCW from +x side"""
    pts=[]
    for (sx,sy,a0) in ((1,1,0),(-1,1,90),(-1,-1,180),(1,-1,270)):
        ccx=cx+sx*(hx-r); ccy=cy+sy*(hy-r)
        for k in range(seg+1):
            a=math.radians(a0+90*k/seg); pts.append((ccx+r*math.cos(a),ccy+r*math.sin(a),z))
    return pts
def strip(part,pts3,nrm,hw,h,m,depth=0.006):
    """bevelled raised strip along a polyline lying on a planar-ish surface with normal nrm (per point list or single)"""
    if not isinstance(nrm,list): nrm=[nrm]*len(pts3)
    q=[(pts3[0],nrm[0])]
    for p_,n_ in zip(pts3[1:],nrm[1:]):
        if (V(p_)-V(q[-1][0])).length>0.004: q.append((p_,n_))
    pts3=[a for a,b in q]; nrm=[b for a,b in q]
    if len(pts3)<2: return
    L=len(pts3); rings=[]
    for i in range(L):
        n=nrm[i] if isinstance(nrm,list) else nrm
        t=(V(pts3[min(i+1,L-1)])-V(pts3[max(i-1,0)])).normalized(); sd=t.cross(n).normalized(); p=V(pts3[i])
        # miter at interior corners
        if 0<i<L-1:
            t1=(V(pts3[i])-V(pts3[i-1])).normalized(); t2=(V(pts3[i+1])-V(pts3[i])).normalized()
            s1=t1.cross(n).normalized(); s2=t2.cross(n).normalized(); sd=(s1+s2)
            sd=sd/max(0.5,sd.dot(s1)) if sd.length>1e-6 else s1
        ring=[p-sd*hw-n*depth,p+sd*hw-n*depth,p+sd*hw+n*h*0.6,p+sd*hw*0.6+n*h,p-sd*hw*0.6+n*h,p-sd*hw+n*h*0.6]
        rings.append([tuple(q) for q in ring])
    part.loft(rings,m,cap0=m,cap1=m)
