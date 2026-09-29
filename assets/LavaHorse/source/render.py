"""Render the reference-sheet views.  python3 render.py <blend> [views...]  -> out/validation/<view>.png (RGBA)"""
import os
import sys, math
import bpy
from mathutils import Vector

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build') + '/'
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
blend = args[0] if args else OUT + 'LavaHorse_stage1.blend'
names = args[1:]
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 24
sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'Standard'
sc.render.film_transparent = True
w = sc.world or bpy.data.worlds.new('World')
sc.world = w
w.use_nodes = True
nt = w.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
bg = nt.nodes.new('ShaderNodeBackground')
bg.inputs['Color'].default_value = (0.5, 0.5, 0.53, 1)
bg.inputs['Strength'].default_value = 0.9
o = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(bg.outputs[0], o.inputs[0])
for nm, e, rot in (('key', 2.6, (50, 0, -35)), ('fill', 0.8, (60, 0, 150))):
    L = bpy.data.lights.new(nm, 'SUN')
    L.energy = e
    L.angle = math.radians(10)
    ob = bpy.data.objects.new(nm, L)
    ob.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(ob)

S = 7.0 / 444.0
T = Vector((0, 0, 220 * S))
VIEWS = {  # direction from target to camera, ortho?
    'front': ((0, -1, 0), True), 'left': ((1, 0, 0), True), 'right': ((-1, 0, 0), True), 'back': ((0, 1, 0), True),
    'q_fl': ((0.78, -0.62, 0.22), False), 'top': ((0, 0.5, 1.0), False), 'q_bl': ((0.72, 0.68, 0.22), False),
}
for n in (names or list(VIEWS)):
    d, ortho = VIEWS[n]
    d = Vector(d).normalized()
    cd = bpy.data.cameras.new(n)
    c = bpy.data.objects.new(n, cd)
    sc.collection.objects.link(c)
    if ortho:
        cd.type = 'ORTHO'
        cd.ortho_scale = 560 * S
        c.location = T + d * 40
    else:
        cd.lens = 50
        c.location = T + d * 28
    c.rotation_euler = (T - c.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = c
    sc.render.resolution_x = sc.render.resolution_y = 640
    sc.render.filepath = OUT + f'validation/{n}.png'
    bpy.ops.render.render(write_still=True)
    print('rendered', n)
