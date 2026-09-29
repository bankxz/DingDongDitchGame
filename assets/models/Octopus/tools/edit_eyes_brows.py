import bpy, bmesh, os
from mathutils import Vector
OUT='/home/user/DingDongDitchGame/assets/models/Octopus'
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath='/root/.claude/uploads/e957eb1f-e9e2-5681-b3cd-7c3b0d0c8588/da22e7d1-Octopus_Rig.fbx')
o=bpy.data.objects['Octopus']
for ob in bpy.data.objects: print('XFORM',ob.name,tuple(ob.scale),tuple(ob.rotation_euler))
bm=bmesh.new(); bm.from_mesh(o.data); uvl=bm.loops.layers.uv.active
def island(f):
    s={f};st=[f]
    while st:
        c=st.pop()
        for e in c.edges:
            for n in e.link_faces:
                if n not in s: s.add(n); st.append(n)
    return s
seen=set(); brows=[]; eyes=[]
for f in bm.faces:
    if f in seen: continue
    isl=island(f); seen|=isl; vs={v for x in isl for v in x.verts}
    if len(vs)!=8: continue
    ys=[v.co.y for v in vs]; zs=[v.co.z for v in vs]
    if min(ys)<-1.7 and 4.2<max(zs)<4.4: brows.append(isl)
    if -1.6<min(ys)<-1.55 and max(zs)<3.6: eyes.append(isl)
assert len(brows)==2 and len(eyes)==2

# --- Eyes: 1.5x bigger, nudged outward so the two eyes don't collide at the midline
EYE_SCALE=1.5; EYE_OUT=0.25
for isl in eyes:
    vs={v for x in isl for v in x.verts}
    c=sum((v.co for v in vs),Vector())/len(vs)
    side=1 if c.x>0 else -1
    for v in vs:
        v.co=c+(v.co-c)*EYE_SCALE+Vector((side*EYE_OUT,0,0))

# --- Brows: find an empty texel block in the atlas, paint it deep purple, remap brow UVs there
img=bpy.data.images['Octopus_Color.png']; nrm=bpy.data.images['Octopus_Normal.png']
W,H=img.size
used=bytearray(W*H)
def mark_tri(a,b,c):
    xs=[p[0]*W for p in (a,b,c)]; ys=[p[1]*H for p in (a,b,c)]
    x0,x1=max(0,int(min(xs))-2),min(W-1,int(max(xs))+2); y0,y1=max(0,int(min(ys))-2),min(H-1,int(max(ys))+2)
    for y in range(y0,y1+1):
        for x in range(x0,x1+1): used[y*W+x]=1   # conservative: mark bbox
for f in bm.faces:
    if any(f in b for b in brows): continue
    uv=[l[uvl].uv.copy() for l in f.loops]
    for i in range(1,len(uv)-1): mark_tri(uv[0],uv[i],uv[i+1])
S=12; spot=None
for y in range(8,H-S-8,4):
    for x in range(8,W-S-8,4):
        if not any(used[(y+j)*W+x+i] for j in range(-4,S+4,2) for i in range(-4,S+4,2)): spot=(x,y); break
    if spot: break
assert spot, 'no free texel block'
print('SPOT',spot)
DEEP_PURPLE=(0.235,0.035,0.37)   # sRGB #3C095E — much darker/redder than the blue-violet body
px=list(img.pixels); npx=list(nrm.pixels)
sx,sy=spot
for j in range(S):
    for i in range(S):
        k=((sy+j)*W+sx+i)*4
        px[k:k+4]=[*DEEP_PURPLE,1.0]
        npx[k:k+4]=[0.5,0.5,1.0,1.0]  # flat normal
img.pixels[:]=px; nrm.pixels[:]=npx
cu,cv=(sx+S/2)/W,(sy+S/2)/H
for isl in brows:
    for f in isl:
        for l in f.loops: l[uvl].uv=(cu,cv)
bm.to_mesh(o.data); o.data.update()

img.filepath_raw=f'{OUT}/Octopus_Color.png'; img.file_format='PNG'; img.save()
nrm.filepath_raw=f'{OUT}/Octopus_Normal.png'; nrm.file_format='PNG'; nrm.save()
img.pack(); nrm.pack()
bpy.ops.wm.save_as_mainfile(filepath='/tmp/claude-0/-home-user-DingDongDitchGame/e957eb1f-e9e2-5681-b3cd-7c3b0d0c8588/scratchpad/edited.blend')
# FBX export (blender-export Recipe 3, keeping the source's transforms/scale for a faithful round-trip)
bpy.ops.export_scene.fbx(filepath=f'{OUT}/Octopus_Rig.fbx', use_selection=False,
    object_types={'MESH','ARMATURE'}, use_mesh_modifiers=False, mesh_smooth_type='FACE',
    add_leaf_bones=False, bake_anim=False, embed_textures=True, path_mode='COPY',
    axis_forward='-Z', axis_up='Y')
print('export:fbx', os.path.getsize(f'{OUT}/Octopus_Rig.fbx'))
