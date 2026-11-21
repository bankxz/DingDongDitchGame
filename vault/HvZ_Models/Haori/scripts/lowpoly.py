import bpy,bmesh,sys,math
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=1
# groups: low target <- high sources (sources are joined copies), target tris
G=[('Low_Coat',['Gear_Torso'],['Trim_Torso','Gear_BandTorso'],3300,'Torso'),
   ('Low_Kimono',['Gear_Kimono','Gear_HakamaWaist'],[],950,'Torso'),
   ('Low_Collar',['Gear_Collar'],[],800,'Torso'),
   ('Low_RightArm',['Gear_RightArm'],['Gear_BandRightArm'],520,'Right Arm'),
   ('Low_LeftArm',['Gear_LeftArm'],['Gear_BandLeftArm'],520,'Left Arm'),
   ('Low_RightLeg',['Gear_RightLeg'],[],720,'Right Leg'),
   ('Low_LeftLeg',['Gear_LeftLeg'],[],720,'Left Leg'),
   ('Low_Tassel',['Gear_Tassel'],[],300,'Torso')]
def sel(objs,active=None):
    for o in bpy.context.selected_objects: o.select_set(False)
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active=active or objs[0]
def tris(o): return sum(len(p.vertices)-2 for p in o.data.polygons)
dg=bpy.context.evaluated_depsgraph_get()
def bake_copy(name):   # world-space static copy of a gear object (constraint evaluated)
    o=bpy.data.objects[name]; me=bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world)
    c=bpy.data.objects.new(name+'_HI',me); sc.collection.objects.link(c); return c
report=[]
for low_name,shape_src,extra_src,target,bone in G:
    his=[bake_copy(n) for n in shape_src+extra_src]
    # low: decimate a joined copy of the shape sources only
    shp=[bake_copy(n) for n in shape_src]
    sel(shp); 
    if len(shp)>1: bpy.ops.object.join()
    low=bpy.context.view_layer.objects.active; low.name=low_name; low.data.name=low_name
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.remove_doubles(threshold=0.0005); bpy.ops.object.mode_set(mode='OBJECT')
    n0=tris(low)
    md=low.modifiers.new('d','DECIMATE'); md.decimate_type='COLLAPSE'; md.ratio=min(1.0,target/max(1,n0)); md.use_collapse_triangulate=True
    bpy.ops.object.modifier_apply(modifier='d')
    for p in low.data.polygons: p.use_smooth=True
    # UVs
    for u in list(low.data.uv_layers): low.data.uv_layers.remove(u)
    low.data.uv_layers.new(name='UVMap')
    sel([low]); bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60),island_margin=0.004); bpy.ops.object.mode_set(mode='OBJECT')
    # target images + material
    col=bpy.data.images.new(low_name+'_Color',2048,2048); nrm=bpy.data.images.new(low_name+'_Normal',2048,2048); nrm.colorspace_settings.name='Non-Color'
    m=bpy.data.materials.new(low_name+'_Mat'); m.use_nodes=True; N=m.node_tree.nodes; L=m.node_tree.links
    tc=N.new('ShaderNodeTexImage'); tc.image=col; tn=N.new('ShaderNodeTexImage'); tn.image=nrm
    nm=N.new('ShaderNodeNormalMap'); b=N['Principled BSDF']; b.inputs['Roughness'].default_value=0.85
    L.new(tc.outputs['Color'],b.inputs['Base Color'])
    low.data.materials.clear(); low.data.materials.append(m)
    # bake selected -> active
    sc.render.bake.use_selected_to_active=True; sc.render.bake.use_cage=False
    sc.render.bake.cage_extrusion=0.05; sc.render.bake.max_ray_distance=0.12; sc.render.bake.margin=8
    sel(his+[low],low)
    N.active=tc; sc.render.bake.use_pass_direct=False; sc.render.bake.use_pass_indirect=False
    bpy.ops.object.bake(type='DIFFUSE',pass_filter={'COLOR'})
    N.active=tn; bpy.ops.object.bake(type='NORMAL',normal_space='TANGENT')
    L.new(tn.outputs['Color'],nm.inputs['Color']); L.new(nm.outputs['Normal'],b.inputs['Normal'])
    for im,suf in ((col,'Color'),(nrm,'Normal')):
        im.filepath_raw=f'/tmp/w/parts/low/{low_name}_{suf}.png'; im.file_format='PNG'; im.save(); im.pack()
    for h in his: bpy.data.objects.remove(h)
    # rig it like the originals
    c=bpy.data.objects[bone].constraints[0]
    cc=low.constraints.new('CHILD_OF'); cc.target=c.target; cc.subtarget=c.subtarget; cc.inverse_matrix=c.inverse_matrix.copy()
    report.append((low_name,n0,tris(low))); print('done',low_name,n0,'->',tris(low),flush=True)
# remove the high-poly gear
for o in list(bpy.data.objects):
    if o.name.startswith(('Gear_','Trim_')): bpy.data.objects.remove(o)
sc.render.bake.use_selected_to_active=False
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('TOTAL gear tris',sum(r[2] for r in report))
