"""Framed validation renders: reference-sheet views + head close-ups. python shots.py -- <blend> <outdir> [views]"""
import sys, math
import bpy
from mathutils import Vector
args = sys.argv[sys.argv.index('--') + 1:]
blend, outdir, names = args[0], args[1], args[2:]
bpy.ops.wm.open_mainfile(filepath=blend)
import os
if os.environ.get('ACTION'):
    rig = bpy.data.objects['LavaHorse_Rig']
    rig.animation_data.action = bpy.data.actions[os.environ['ACTION']]
    bpy.context.scene.frame_set(int(os.environ.get('FRAME', '1')))
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = 48
sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'Standard'
sc.render.film_transparent = False
w = sc.world or bpy.data.worlds.new('World')
sc.world = w
nt = w.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
bg = nt.nodes.new('ShaderNodeBackground')
bg.inputs['Color'].default_value = (0.21, 0.21, 0.22, 1)
bg.inputs['Strength'].default_value = 1.0
o = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(bg.outputs[0], o.inputs[0])
for nm, e, rot in (('key', 3.2, (50, 0, -35)), ('fill', 1.0, (60, 0, 150)), ('rim', 1.2, (70, 0, 60))):
    L = bpy.data.lights.new(nm, 'SUN')
    L.energy = e
    L.angle = math.radians(12)
    ob = bpy.data.objects.new(nm, L)
    ob.rotation_euler = [math.radians(a) for a in rot]
    sc.collection.objects.link(ob)
# ground plane (shadow catcher look)
me = bpy.data.meshes.new('ground')
me.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
g = bpy.data.objects.new('ground', me)
sc.collection.objects.link(g)
gm = bpy.data.materials.new('ground')
gm.diffuse_color = (0.5, 0.5, 0.52, 1)
gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.42, 0.42, 0.44, 1)
g.data.materials.append(gm)
S = 7.0 / 444.0
T = Vector((0, 0, 225 * S))
H = Vector((0, -205 * S, 360 * S))
VIEWS = {  # dir from target to camera, ortho scale or lens, target
    'front': ((0, -1, 0.08), 8.6, T), 'left': ((1, 0, 0.05), 9.8, T), 'right': ((-1, 0, 0.05), 9.8, T),
    'back': ((0, 1, 0.08), 8.6, T), 'q_fl': ((0.78, -0.62, 0.3), 9.6, T), 'q_bl': ((0.72, 0.68, 0.3), 9.6, T),
    'top': ((0.0, 0.35, 1.0), 9.8, T),
    'head_side': ((1, -0.05, 0.05), 3.2, H), 'head_q': ((0.75, -0.75, 0.35), 3.4, H), 'head_front': ((0, -1, 0.12), 3.2, H),
}
for n in (names or list(VIEWS)):
    d, scale, tgt = VIEWS[n]
    d = Vector(d).normalized()
    cd = bpy.data.cameras.new(n)
    c = bpy.data.objects.new(n, cd)
    sc.collection.objects.link(c)
    cd.type = 'ORTHO'
    cd.ortho_scale = scale
    cd.clip_end = 200
    c.location = tgt + d * 40
    c.rotation_euler = (tgt - c.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = c
    sc.render.resolution_x = sc.render.resolution_y = 720
    sc.render.filepath = f'{outdir}/{n}.png'
    bpy.ops.render.render(write_still=True)
    print('rendered', n)
