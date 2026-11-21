import sys; sys.path.insert(0,'/tmp/w/parts')
import bpy, math
SRC,OUT=sys.argv[-2:]
bpy.ops.wm.open_mainfile(filepath=SRC)
for n in ('Gear_Hair',):
    o=bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o)
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=4
mar=bpy.data.materials['Marble']; nt=mar.node_tree; N=nt.nodes; Lk=nt.links
bsdf=N['Principled BSDF']
for n in list(N):
    if n.type not in ('BSDF_PRINCIPLED','OUTPUT_MATERIAL'): N.remove(n)
tc=N.new('ShaderNodeTexCoord'); mp=N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value=(1.6,1.6,1.6)
Lk.new(tc.outputs['Object'],mp.inputs['Vector'])
def veins(scale,dist,width,seed):
    nz=N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value=scale; nz.inputs['Detail'].default_value=6; nz.inputs['Distortion'].default_value=dist
    nz.noise_dimensions='4D'; nz.inputs['W'].default_value=seed; Lk.new(mp.outputs['Vector'],nz.inputs['Vector'])
    cr=N.new('ShaderNodeValToRGB'); e=cr.color_ramp.elements
    e[0].position=0.5-width; e[0].color=(0,0,0,1); e[1].position=0.5; e[1].color=(1,1,1,1)
    e.new(0.5+width).color=(0,0,0,1)
    Lk.new(nz.outputs['Fac'],cr.inputs['Fac']); return cr
v1=veins(1.4,2.2,0.012,1.3); v2=veins(3.2,3.0,0.008,7.1)
mx=N.new('ShaderNodeMath'); mx.operation='MAXIMUM'; Lk.new(v1.outputs['Color'],mx.inputs[0]); Lk.new(v2.outputs['Color'],mx.inputs[1])
cl=N.new('ShaderNodeTexNoise'); cl.inputs['Scale'].default_value=2.5; Lk.new(mp.outputs['Vector'],cl.inputs['Vector'])
base=N.new('ShaderNodeMix'); base.data_type='RGBA'
base.inputs[6].default_value=(0.88,0.84,0.95,1); base.inputs[7].default_value=(0.97,0.95,0.99,1)
Lk.new(cl.outputs['Fac'],base.inputs[0])
vm=N.new('ShaderNodeMix'); vm.data_type='RGBA'; vm.inputs[7].default_value=(0.55,0.42,0.78,1)
Lk.new(mx.outputs[0],vm.inputs[0]); Lk.new(base.outputs[2],vm.inputs[6])
Lk.new(vm.outputs[2],bsdf.inputs['Base Color'])
# ---- bake per object
targets=[o for o in bpy.data.objects if o.type=='MESH' and any(m and m.name=='Marble' for m in o.data.materials)]
print('targets',[o.name for o in targets])
for ob in targets:
    for o in bpy.context.selected_objects: o.select_set(False)
    bpy.context.view_layer.objects.active=ob; ob.select_set(True)
    if not ob.data.uv_layers: ob.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=0.003); bpy.ops.object.mode_set(mode='OBJECT')
    img=bpy.data.images.new(ob.name+'_Marble',2048,2048)
    nodes=[]
    for m in ob.data.materials:
        tn=m.node_tree.nodes.new('ShaderNodeTexImage'); tn.image=img; m.node_tree.nodes.active=tn; nodes.append((m,tn))
    sc.render.bake.use_pass_direct=False; sc.render.bake.use_pass_indirect=False; sc.render.bake.margin=6
    bpy.ops.object.bake(type='DIFFUSE',pass_filter={'COLOR'})
    img.filepath_raw=f'/tmp/w/parts/{ob.name}_Marble.png'; img.file_format='PNG'; img.save(); img.pack()
    for m,tn in nodes:
        if m.name!='Marble': m.node_tree.nodes.remove(tn)
    # per-object marble material using the baked image
    mm=bpy.data.materials.new(ob.name+'_MarbleMat'); mm.use_nodes=True
    t=mm.node_tree.nodes.new('ShaderNodeTexImage'); t.image=img
    b=mm.node_tree.nodes['Principled BSDF']; mm.node_tree.links.new(t.outputs['Color'],b.inputs['Base Color']); b.inputs['Roughness'].default_value=0.35
    for i,m in enumerate(ob.data.materials):
        if m.name=='Marble': ob.data.materials[i]=mm
    print('baked',ob.name)
for m,tn in []: pass
mar_nodes=[n for n in mar.node_tree.nodes if n.type=='TEX_IMAGE']
for n in mar_nodes: mar.node_tree.nodes.remove(n)
sc.render.engine='BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
bpy.ops.wm.save_as_mainfile(filepath=OUT)
