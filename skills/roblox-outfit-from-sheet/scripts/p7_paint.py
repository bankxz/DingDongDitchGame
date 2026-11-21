import bpy, math, sys
SRC,OUT,RES=sys.argv[-3],sys.argv[-2],int(sys.argv[-1])
bpy.ops.wm.open_mainfile(filepath=SRC)
for n in ('Gear_Hair',):
    o=bpy.data.objects.get(n)
    if o: bpy.data.objects.remove(o)
sc=bpy.context.scene; sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=24
# palette: (shadow, mid, light) sampled-by-eye from the sheet style
PAL={
 'Marble':((0.70,0.64,0.84),(0.90,0.87,0.96),(0.98,0.97,1.0)),
 'Gold':((0.55,0.33,0.12),(0.92,0.68,0.28),(1.0,0.93,0.66)),
 'Lining':((0.26,0.10,0.45),(0.44,0.20,0.68),(0.60,0.36,0.84)),
 'Purple':((0.24,0.09,0.42),(0.42,0.18,0.66),(0.60,0.34,0.84)),
 'Cloud':((0.50,0.38,0.74),(0.66,0.54,0.86),(0.78,0.68,0.93)),
 'Navy':((0.08,0.07,0.18),(0.17,0.15,0.33),(0.28,0.26,0.48)),
 'NavyDark':((0.05,0.05,0.12),(0.10,0.09,0.20),(0.17,0.15,0.30)),
 'Hakama':((0.09,0.08,0.20),(0.19,0.17,0.38),(0.31,0.29,0.55)),
 'HakamaDark':((0.05,0.05,0.13),(0.11,0.10,0.24),(0.17,0.16,0.33)),
 'Black':((0.04,0.04,0.05),(0.10,0.09,0.11),(0.22,0.21,0.25)),
 'ObiBlack':((0.04,0.04,0.05),(0.10,0.09,0.11),(0.24,0.23,0.27)),
 'ObiBlack2':((0.06,0.06,0.07),(0.14,0.13,0.16),(0.30,0.29,0.33)),
 'Boot':((0.06,0.06,0.10),(0.15,0.14,0.22),(0.30,0.29,0.40)),
 'BootEdge':((0.10,0.10,0.15),(0.24,0.23,0.32),(0.40,0.39,0.50)),
 'WhiteCloth':((0.72,0.70,0.80),(0.92,0.91,0.95),(1.0,1.0,1.0)),
 'Skin':((0.80,0.58,0.47),(0.96,0.79,0.67),(1.0,0.90,0.80)),
 'GlowPurple':((0.36,0.16,0.58),(0.58,0.34,0.84),(0.76,0.56,0.95)),
}
PAL={k:tuple(tuple(c**2.2 for c in t) for t in v) for k,v in PAL.items()}
def fam(name):
    for k in sorted(PAL,key=len,reverse=True):
        if name==k or name.startswith(k+'.') : return k
    return None
LIGHT=(-0.30,0.25,0.92)
def painted(m,key):
    sh,mid,li=PAL[key]
    m.use_nodes=True; nt=m.node_tree; N=nt.nodes; L=nt.links
    for n in list(N): N.remove(n)
    out=N.new('ShaderNodeOutputMaterial'); em=N.new('ShaderNodeEmission'); L.new(em.outputs[0],out.inputs['Surface'])
    geo=N.new('ShaderNodeNewGeometry')
    dp=N.new('ShaderNodeVectorMath'); dp.operation='DOT_PRODUCT'; dp.inputs[1].default_value=LIGHT
    L.new(geo.outputs['Normal'],dp.inputs[0])
    ao=N.new('ShaderNodeAmbientOcclusion'); ao.inputs['Distance'].default_value=0.25; ao.samples=16
    # cel ramp: shadow | mid | light (soft painted transitions)
    mx=N.new('ShaderNodeMath'); mx.operation='MULTIPLY_ADD'; mx.inputs[1].default_value=0.5; mx.inputs[2].default_value=0.5
    L.new(dp.outputs['Value'],mx.inputs[0])
    m2=N.new('ShaderNodeMath'); m2.operation='MULTIPLY'; L.new(mx.outputs[0],m2.inputs[0]); L.new(ao.outputs['AO'],m2.inputs[1])
    cr=N.new('ShaderNodeValToRGB'); e=cr.color_ramp.elements; cr.color_ramp.interpolation='EASE'
    e[0].position=0.12; e[0].color=(*sh,1); e[1].position=0.40; e[1].color=(*mid,1)
    hi=0.78 if key=='Gold' else 0.86
    x=e.new(hi-0.04); x.color=(*mid,1); y=e.new(hi); y.color=(*li,1)
    L.new(m2.outputs[0],cr.inputs['Fac'])
    col=cr.outputs['Color']
    if key=='Marble':
        tc=N.new('ShaderNodeTexCoord'); mp=N.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value=(0.3,0.0,0.6)
        L.new(tc.outputs['Object'],mp.inputs['Vector'])
        dn=N.new('ShaderNodeTexNoise'); dn.inputs['Scale'].default_value=1.2; dn.inputs['Detail'].default_value=3
        L.new(mp.outputs['Vector'],dn.inputs['Vector'])
        dv=N.new('ShaderNodeMix'); dv.data_type='VECTOR'; dv.inputs[0].default_value=0.35
        L.new(mp.outputs['Vector'],dv.inputs[4]); L.new(dn.outputs['Color'],dv.inputs[5])
        def cracks(scale,width):
            vo=N.new('ShaderNodeTexVoronoi'); vo.feature='DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value=scale
            L.new(dv.outputs[1],vo.inputs['Vector'])
            r=N.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].position=0.0; r.color_ramp.elements[0].color=(1,1,1,1)
            r.color_ramp.elements[1].position=width; r.color_ramp.elements[1].color=(0,0,0,1)
            L.new(vo.outputs['Distance'],r.inputs['Fac']); return r
        c1=cracks(0.75,0.06); c2=cracks(1.8,0.028)
        mxv=N.new('ShaderNodeMath'); mxv.operation='MAXIMUM'; L.new(c1.outputs['Color'],mxv.inputs[0])
        c2s=N.new('ShaderNodeMath'); c2s.operation='MULTIPLY'; c2s.inputs[1].default_value=0.6; L.new(c2.outputs['Color'],c2s.inputs[0]); L.new(c2s.outputs[0],mxv.inputs[1])
        cl=N.new('ShaderNodeTexNoise'); cl.inputs['Scale'].default_value=0.8; L.new(mp.outputs['Vector'],cl.inputs['Vector'])
        clr=N.new('ShaderNodeValToRGB'); clr.color_ramp.elements[0].position=0.5; clr.color_ramp.elements[0].color=(0,0,0,1); clr.color_ramp.elements[1].position=0.75; clr.color_ramp.elements[1].color=(0.35,0.35,0.35,1)
        L.new(cl.outputs['Fac'],clr.inputs['Fac'])
        a1=N.new('ShaderNodeMix'); a1.data_type='RGBA'; a1.inputs[7].default_value=(0.80**2.2,0.72**2.2,0.94**2.2,1)
        L.new(clr.outputs['Color'],a1.inputs[0]); L.new(col,a1.inputs[6])
        a2=N.new('ShaderNodeMix'); a2.data_type='RGBA'; a2.inputs[7].default_value=(0.66**2.2,0.55**2.2,0.88**2.2,1)
        f=N.new('ShaderNodeMath'); f.operation='MULTIPLY'; f.inputs[1].default_value=0.75; L.new(mxv.outputs[0],f.inputs[0])
        L.new(f.outputs[0],a2.inputs[0]); L.new(a1.outputs[2],a2.inputs[6]); col=a2.outputs[2]
    if key=='Gold':   # bright specular-like band on edges facing the light
        lw=N.new('ShaderNodeLayerWeight'); lw.inputs['Blend'].default_value=0.25
        r=N.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].position=0.55; r.color_ramp.elements[0].color=(0,0,0,1); r.color_ramp.elements[1].position=0.75; r.color_ramp.elements[1].color=(0.55,0.55,0.55,1)
        L.new(lw.outputs['Facing'],r.inputs['Fac'])
        g=N.new('ShaderNodeMix'); g.data_type='RGBA'; g.inputs[7].default_value=(0.45**2.2,0.25**2.2,0.08**2.2,1)
        L.new(r.outputs['Color'],g.inputs[0]); L.new(col,g.inputs[6]); col=g.outputs[2]
    L.new(col,em.inputs['Color'])
done=set()
for m in bpy.data.materials:
    k=fam(m.name)
    if k and m.users: painted(m,k); done.add(m.name)
print('painted',sorted(done))
# ---- bake each gear object to its own texture (glow meshes stay plain for Neon)
for o in bpy.data.objects:
    if o.name.startswith('Glow_'): o.name='Gear_Band'+o.name[5:]
objs=[o for o in bpy.data.objects if o.type=='MESH' and (o.name.startswith(('Gear_','Trim_'))) ]
for ob in objs:
    for o in bpy.context.selected_objects: o.select_set(False)
    bpy.context.view_layer.objects.active=ob; ob.select_set(True)
    for u in list(ob.data.uv_layers): ob.data.uv_layers.remove(u)
    ob.data.uv_layers.new(name='UVMap')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=0.002); bpy.ops.object.mode_set(mode='OBJECT')
    img=bpy.data.images.new(ob.name+'_Paint',RES,RES)
    tmp=[]
    for m in ob.data.materials:
        tn=m.node_tree.nodes.new('ShaderNodeTexImage'); tn.image=img; m.node_tree.nodes.active=tn; tmp.append((m,tn))
    sc.render.bake.margin=8
    bpy.ops.object.bake(type='EMIT')
    for m,tn in tmp: m.node_tree.nodes.remove(tn)
    img.filepath_raw=f'/tmp/w/parts/tex/{ob.name}_Paint.png'; img.file_format='PNG'; img.save(); img.pack()
    fm=bpy.data.materials.new(ob.name+'_Painted'); fm.use_nodes=True
    t=fm.node_tree.nodes.new('ShaderNodeTexImage'); t.image=img; b=fm.node_tree.nodes['Principled BSDF']
    fm.node_tree.links.new(t.outputs['Color'],b.inputs['Base Color']); b.inputs['Roughness'].default_value=0.9
    fm.node_tree.links.new(t.outputs['Color'],b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value=0.35
    ob.data.materials.clear(); ob.data.materials.append(fm)
    print('baked',ob.name)
nv=bpy.data.materials.new('R6Under'); nv.use_nodes=True; nv.diffuse_color=(0.02,0.02,0.05,1)
nv.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(0.02,0.02,0.05,1)
for n in ('Torso','Left Leg','Right Leg'):
    o=bpy.data.objects[n]; o.data.materials.clear(); o.data.materials.append(nv)
sc.render.engine='BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
bpy.ops.wm.save_as_mainfile(filepath=OUT)
