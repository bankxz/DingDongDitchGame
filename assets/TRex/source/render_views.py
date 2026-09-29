"""Render the reference-sheet views (hero, front, back, sides, top, bottom, head
close-ups) of TRex.blend for side-by-side comparison with the concept sheet.

python3 render_views.py <TRex.blend> <out_dir> [action] [frame]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

blend, out = sys.argv[1], sys.argv[2]
action = sys.argv[3] if len(sys.argv) > 3 else ''
frame = int(sys.argv[4]) if len(sys.argv) > 4 else 1
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
rig = bpy.data.objects['TRexRig']
if action:
    rig.animation_data.action = bpy.data.actions[action]
else:
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
scene.frame_set(frame)

S = 0.28  # stud -> metre
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.view_settings.view_transform = 'Standard'
scene.render.film_transparent = False

world = bpy.data.worlds.new('Sky')
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes['Background']
bg.inputs['Color'].default_value = (0.45, 0.66, 0.95, 1)
bg.inputs['Strength'].default_value = 0.9

sun_data = bpy.data.lights.new('Sun', 'SUN')
sun_data.energy = 3.2
sun_data.angle = math.radians(8)
sun = bpy.data.objects.new('Sun', sun_data)
scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(50), math.radians(-15), math.radians(-35))

bpy.ops.mesh.primitive_plane_add(size=200 * S, location=(0, 0, 0))
ground = bpy.context.active_object
gm = bpy.data.materials.new('Ground')
gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.16, 0.17, 0.22, 1)
ground.data.materials.append(gm)

cam_data = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

VIEWS = {
    # name: (camera position in studs, look-at in studs, lens, resolution)
    'hero': ((50, -34, 13), (0, 0, 8), 30, (1180, 590)),
    'front': ((0, -66, 22), (0, 0, 8.5), 55, (560, 700)),
    'back': ((0, 66, 22), (0, 0, 8.5), 55, (560, 700)),
    'left': ((70, -1, 12), (0, 1.5, 8.0), 45, (1036, 470)),
    'right': ((-70, -1, 12), (0, 1.5, 8.0), 45, (1036, 470)),
    'top': ((0, 1.5, 75), (0, 1.5, 0), 45, (456, 780)),
    'bottom': ((0, 1.5, -75), (0, 1.5, 0), 45, (456, 780)),
    'head_front': ((0, -42, 12), (0, -18, 11.5), 50, (512, 640)),
    'head_side': ((22, -22, 12), (0, -18.5, 11.5), 50, (640, 512)),
}
only = os.environ.get('VIEWS')
for name, (pos, look, lens, res) in VIEWS.items():
    if only and name not in only.split(','):
        continue
    ground.hide_render = name == 'bottom'
    cam.location = Vector(pos) * S
    d = Vector(look) * S - cam.location
    cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if name == 'top':
        cam.rotation_euler = (0, 0, math.radians(180))
    if name == 'bottom':
        cam.rotation_euler = (math.radians(180), 0, 0)
    cam_data.lens = lens
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = os.path.join(out, f'{name}.png')
    bpy.ops.render.render(write_still=True)
    print('rendered', name)
