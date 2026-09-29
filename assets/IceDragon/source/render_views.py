"""Render validation views of IceDragon.blend (front/left/back/top/3-4)."""
import bpy, sys, os, math
from mathutils import Vector
ROOT = os.path.abspath(sys.argv[-2]); OUT = os.path.abspath(sys.argv[-1])
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'IceDragon.blend'))
sc = bpy.context.scene
FRAME = int(os.environ.get('FRAME', '0'))
ACTION = os.environ.get('ACTION')
arm = bpy.data.objects['IceDragon']
if ACTION:
    arm.animation_data.action = bpy.data.actions[ACTION]
elif arm.animation_data:
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
sc.frame_set(FRAME)
sc.render.engine = 'CYCLES'; sc.cycles.samples = int(os.environ.get('SAMPLES', '24')); sc.cycles.device = 'CPU'
sc.cycles.use_denoising = False
sc.render.resolution_x = int(os.environ.get('RES', '700')); sc.render.resolution_y = sc.render.resolution_x
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs[0].default_value = (0.035, 0.04, 0.055, 1)
w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
def light(name, rot, energy):
    l = bpy.data.lights.new(name, 'SUN'); l.energy = energy; l.angle = 0.3
    o = bpy.data.objects.new(name, l); sc.collection.objects.link(o); o.rotation_euler = [math.radians(a) for a in rot]
light('key', (50, 0, -35), 3.2); light('fill', (60, 0, 150), 1.4); light('rim', (-60, 0, 180), 1.2); light('top', (0, 0, 0), 1.0)
# ground
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
g = bpy.context.object; m = bpy.data.materials.new('G'); m.use_nodes = True
m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.05, 0.055, 0.07, 1)
g.data.materials.append(m)
cam_d = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
C = Vector((0, 2.5, 5.2))
views = {
 'front': ((0, -40, 5.2), 'ORTHO', 14.5), 'left': ((40, 2.5, 5.2), 'ORTHO', 19.0),
 'back': ((0, 45, 5.2), 'ORTHO', 14.5), 'top': ((0, 2.5, 45), 'ORTHO', 19.0),
 'persp34': ((22, -22, 12), 'PERSP', 35),
 'closeup': ((9, -14, 9.5), 'PERSP', 45), 'ref34': ((24, -14, 9), 'PERSP', 42),
}
only = os.environ.get('VIEWS')
for name, (loc, typ, s) in views.items():
    if only and name not in only.split(','): continue
    cam.location = loc; cam_d.type = typ
    if typ == 'ORTHO': cam_d.ortho_scale = s
    else: cam_d.lens = s
    tgt = Vector((0, 2.5 if name != 'front' and name != 'back' else 0, 5.2))
    if name == 'persp34': tgt = Vector((0, 1.5, 4.5))
    if name == 'closeup': tgt = Vector((0.5, -3, 6.2))
    if name == 'ref34': tgt = Vector((0, 1.5, 5.0))
    d = tgt - Vector(loc)
    cam.rotation_euler = d.to_track_quat('-Z', 'Y' if name != 'top' else 'Y').to_euler()
    if name == 'top': cam.rotation_euler = (0, 0, 0)
    g.hide_render = name == 'top'
    sc.render.filepath = os.path.join(OUT, f'{name}.png')
    bpy.ops.render.render(write_still=True)
print('rendered')
