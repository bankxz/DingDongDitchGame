import bpy,sys,math
sys.path.insert(0,'/tmp/w'); import rend
bpy.ops.wm.open_mainfile(filepath=sys.argv[-2]); tag=sys.argv[-1]
sc=bpy.context.scene; rend.setup((700,800))
for n,c in (('Head',(0.9,0.62,0.45)),('Left Arm',(0.9,0.62,0.45)),('Right Arm',(0.9,0.62,0.45)),('Torso',(0.03,0.025,0.07)),('Left Leg',(0.03,0.025,0.07)),('Right Leg',(0.03,0.025,0.07))):
    m=bpy.data.materials.new('pv'+n); m.use_nodes=True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*c,1); o=bpy.data.objects[n]; o.data.materials.clear(); o.data.materials.append(m)
sc.render.engine='BLENDER_EEVEE' if 'BLENDER_EEVEE' in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items] else 'BLENDER_EEVEE_NEXT'
w=bpy.data.worlds.new('W'); sc.world=w; w.use_nodes=True; w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.35
for nm,loc,en in (('K',(-4,6,7),900),('R',(5,-6,5),500)):
    ld=bpy.data.lights.new(nm,'AREA'); ld.energy=en; ld.size=4; o=bpy.data.objects.new(nm,ld); sc.collection.objects.link(o); o.location=loc
    o.rotation_euler=(-V(loc)).to_track_quat('-Z','Y').to_euler() if False else (0,0,0)
    from mathutils import Vector
    o.rotation_euler=(Vector((0,0,2))-Vector(loc)).to_track_quat('-Z','Y').to_euler()
sc.view_settings.view_transform='Standard'
for n,az,el in (('s1',210,10),('s2',30,10),('s3',120,10)):
    rend.shot(f'/tmp/w/{tag}_{n}.png',az,el=el,scale=5.0,center=(0,-0.2,1.8))
from PIL import Image
m=Image.new('RGB',(2100,800))
for i,n in enumerate(('s1','s2','s3')): m.paste(Image.open(f'/tmp/w/{tag}_{n}.png'),(700*i,0))
m.resize((1600,610)).save(f'/tmp/w/{tag}_shade.png')
