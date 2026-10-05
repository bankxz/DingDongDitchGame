"""Pixel-aligned left-view render matching the reference crop (365x290 px, 24.2 px/stud, ground py 277, nose px 10 -> y -9.7).
python3 render_aligned.py model.blend out.png [scale=3]"""
import bpy, sys, math
from mathutils import Vector as V
blend, out = sys.argv[-2], sys.argv[-1]
K = 3
bpy.ops.wm.open_mainfile(filepath=blend); sc = bpy.context.scene
for pb in bpy.data.objects:
    if pb.type == 'ARMATURE' and pb.animation_data: pb.animation_data.action = None
sc.render.engine = 'CYCLES'; sc.cycles.samples = 12; sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = 365 * K, 290 * K; sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (.06, .09, .13, 1)
for nm, rot, e in (('key', (50, 0, -35), 3.2), ('fill', (60, 0, 150), 1.4), ('top', (0, 0, 0), 1.0)):
    l = bpy.data.lights.new(nm, 'SUN'); l.energy = e; o = bpy.data.objects.new(nm, l); sc.collection.objects.link(o); o.rotation_euler = [math.radians(a) for a in rot]
cd = bpy.data.cameras.new('c'); cd.type = 'ORTHO'; cd.ortho_scale = 365 / 24.2
cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
cy = -9.7 + (182.5 - 10) / 24.2; cz = (277 - 145) / 24.2
cam.location = V((40, cy, cz)); cam.rotation_euler = (V((-1, 0, 0))).to_track_quat('-Z', 'Y').to_euler()
sc.render.filepath = out; bpy.ops.render.render(write_still=True)
