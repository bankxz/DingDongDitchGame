import bpy, bmesh, os, colorsys
import numpy as np
SCR='/tmp/claude-0/-home-user-DingDongDitchGame/e957eb1f-e9e2-5681-b3cd-7c3b0d0c8588/scratchpad'
OUT='/home/user/DingDongDitchGame/assets/models/Octopus'
bpy.ops.wm.open_mainfile(filepath=f'{SCR}/edited.blend')
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.samples=4; sc.cycles.device='CPU'
o=bpy.data.objects['Octopus']
col=bpy.data.images['Octopus_Color.png']; nrm=bpy.data.images['Octopus_Normal.png']
W,H=col.size
orig_c=np.array(col.pixels[:],dtype=np.float32).reshape(H,W,4)
orig_n=np.array(nrm.pixels[:],dtype=np.float32).reshape(H,W,4)

# ---- brows: stronger, clearly-purple patch (was reading as navy)
BROW=(0.353,0.047,0.549)  # sRGB #5A0C8C
orig_c[8:20,8:20,:3]=BROW

# ---- stud tile (one period): flat top, square recess with bevelled walls
T=128; u=(np.arange(T)+0.5)/T; X,Y=np.meshgrid(u,u)
d=np.maximum(abs(X-0.5),abs(Y-0.5))          # square distance from tile centre
R_OUT,R_IN=0.22,0.16                          # recess outer edge / floor edge
h=np.clip((d-R_IN)/(R_OUT-R_IN),0,1)          # 0 floor .. 1 surface
BASE=np.array([0.30,0.24,0.93]); FLOOR=np.array([0.26,0.20,0.84])
LIT=np.array([0.47,0.42,1.00]); SHADE=np.array([0.17,0.12,0.60])
tile=np.tile(BASE,(T,T,1)).astype(np.float32)
floor=d<=R_IN; wall=(d>R_IN)&(d<R_OUT)
tile[floor]=FLOOR
# walls facing "up" in tile space catch light, walls facing down are in shadow (matches refs)
up=(Y-0.5)<=-abs(X-0.5)+1e-6; down=(Y-0.5)>=abs(X-0.5)-1e-6
tile[wall&down]=SHADE; tile[wall&up]=LIT
tile[wall&~up&~down&(X<0.5)]=BASE*0.78; tile[wall&~up&~down&(X>=0.5)]=np.minimum(BASE*1.12,1)
def mkimg(name,arr,noncolor=False):
    im=bpy.data.images.new(name,T,T,alpha=True)
    if noncolor: im.colorspace_settings.name='Non-Color'
    a=np.ones((T,T,4),np.float32); a[...,:arr.shape[2]]=arr; im.pixels[:]=a.ravel(); return im
tile_img=mkimg('stud_col',tile); h_img=mkimg('stud_h',np.repeat(h[...,None],3,2),True)

# ---- bake copy: drop eyes + brows (their UVs overlap the atlas; keep them untouched)
bake=o.copy(); bake.data=o.data.copy(); sc.collection.objects.link(bake); bake.modifiers.clear()
o.hide_render=True
bm=bmesh.new(); bm.from_mesh(bake.data)
def island(f):
    s={f};st=[f]
    while st:
        c=st.pop()
        for e in c.edges:
            for n in e.link_faces:
                if n not in s: s.add(n); st.append(n)
    return s
seen=set(); kill=set()
for f in bm.faces:
    if f in seen: continue
    isl=island(f); seen|=isl; vs={v for x in isl for v in x.verts}
    if len(vs)==18 and min(v.co.y for v in vs)<-1.8: kill|=isl  # beak/mouth keeps its dark shade
    if len(vs)==8:
        ys=[v.co.y for v in vs]; zs=[v.co.z for v in vs]
        if (min(ys)<-1.7 and 4.2<max(zs)<4.4) or (min(ys)<-1.55 and max(zs)<3.8 and min(zs)>2.4 and max(abs(v.co.x) for v in vs)<1.8): kill|=isl
print('removed faces',len(kill))
bmesh.ops.delete(bm,geom=list(kill),context='FACES'); bm.to_mesh(bake.data)

PERIOD=0.8   # mesh units per stud (head ≈ 4–5 studs across, tentacles 1–2)
mat=bpy.data.materials.new('MAT-stud_bake'); mat.use_nodes=True
nt=mat.node_tree; N=nt.nodes; L=nt.links
for n in list(N): N.remove(n)
tc=N.new('ShaderNodeTexCoord'); mp=N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value=(1/PERIOD,)*3
L.new(tc.outputs['Object'],mp.inputs['Vector'])
def boxtex(img):
    t=N.new('ShaderNodeTexImage'); t.image=img; t.projection='BOX'; t.projection_blend=0.15; t.interpolation='Linear'
    L.new(mp.outputs['Vector'],t.inputs['Vector']); return t
tc_col=boxtex(tile_img); tc_h=boxtex(h_img)
em=N.new('ShaderNodeEmission'); L.new(tc_col.outputs['Color'],em.inputs['Color'])
bump=N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=1.0; bump.inputs['Distance'].default_value=0.08
L.new(tc_h.outputs['Color'],bump.inputs['Height'])
bsdf=N.new('ShaderNodeBsdfPrincipled'); L.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
out=N.new('ShaderNodeOutputMaterial')
tgt=N.new('ShaderNodeTexImage'); nt.nodes.active=tgt
bake.data.materials.clear(); bake.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT'); bake.select_set(True); bpy.context.view_layer.objects.active=bake

def do_bake(kind,noncolor):
    im=bpy.data.images.new('bake_'+kind,W,H,alpha=True)
    if noncolor: im.colorspace_settings.name='Non-Color'
    im.pixels[:]=np.zeros(W*H*4,np.float32)
    tgt.image=im
    if kind=='EMIT': L.new(em.outputs['Emission'],out.inputs['Surface'])
    else: L.new(bsdf.outputs['BSDF'],out.inputs['Surface'])
    bpy.ops.object.bake(type=kind,margin=4,use_clear=False,normal_space='TANGENT')
    return np.array(im.pixels[:],dtype=np.float32).reshape(H,W,4)
bc=do_bake('EMIT',False); bn=do_bake('NORMAL',True)

# ---- composite: replace only the blue scale areas of the original atlas
rgb=orig_c[...,:3]; mx=rgb.max(-1); mn=rgb.min(-1)
sat=np.where(mx>0,(mx-mn)/np.maximum(mx,1e-6),0)
r,g,b=rgb[...,0],rgb[...,1],rgb[...,2]
blue=(b==mx)&(b>0.25)&(sat>0.45)&(r<b*0.8)          # saturated blue (not lavender/white/purple brow)
blue[8:20,8:20]=False
covered=bc[...,3]>0.5
m=blue&covered
print('replaced px',int(m.sum()),'of blue',int(blue.sum()))
new_c=orig_c.copy(); new_c[m,:3]=bc[m,:3]
new_n=orig_n.copy(); new_n[m,:3]=bn[m,:3]
col.pixels[:]=new_c.ravel(); nrm.pixels[:]=new_n.ravel()
col.filepath_raw=f'{OUT}/Octopus_Color.png'; col.save()
nrm.filepath_raw=f'{OUT}/Octopus_Normal.png'; nrm.save()
col.pack(); nrm.pack()

bpy.data.objects.remove(bake); o.hide_render=False
bpy.ops.wm.save_as_mainfile(filepath=f'{SCR}/studs.blend')
bpy.ops.export_scene.fbx(filepath=f'{OUT}/Octopus_Rig.fbx', use_selection=False,
    object_types={'MESH','ARMATURE'}, use_mesh_modifiers=False, mesh_smooth_type='FACE',
    add_leaf_bones=False, bake_anim=False, embed_textures=True, path_mode='COPY',
    axis_forward='-Z', axis_up='Y')
print('export:fbx',os.path.getsize(f'{OUT}/Octopus_Rig.fbx'))
