"""Render a contact sheet per action from a rigged .blend (side ortho + 3/4 persp).
python anim_contact_sheet.py -- file.blend outdir [Action1,Action2] [frames=5] [armature=Rig]
Needs a render helper with setup_scene()/render_view(); this file is self-contained."""
import sys, os, math
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
blend, out = argv[0], argv[1]
bpy.ops.wm.open_mainfile(filepath=blend)
acts = argv[2].split(',') if len(argv) > 2 else [a.name for a in bpy.data.actions]
nf = int(argv[3]) if len(argv) > 3 else 5
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE' and (len(argv) < 5 or o.name == argv[4]))
mesh = next(o for o in bpy.data.objects if o.type == 'MESH' and o.parent == arm)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.samples = 10; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y = 520, 390
sc.view_settings.view_transform = 'Standard'
if not sc.world:
    sc.world = bpy.data.worlds.new('W')
sc.world.use_nodes = True
sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 1.0
if 'KEY' not in bpy.data.objects:
    ld = bpy.data.lights.new('KEY', 'SUN'); ld.energy = 3
    lo = bpy.data.objects.new('KEY', ld); lo.rotation_euler = (math.radians(50), 0, math.radians(-35))
    sc.collection.objects.link(lo)
cd = bpy.data.cameras.new('CS'); cam = bpy.data.objects.new('CS', cd); sc.collection.objects.link(cam); sc.camera = cam
bb = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
ctr = sum(bb, Vector()) / 8
ext = max((max(v[i] for v in bb) - min(v[i] for v in bb)) for i in range(3)) * 1.25
os.makedirs(out, exist_ok=True)
from PIL import Image
for a in acts:
    act = bpy.data.actions[a]
    arm.animation_data_create(); arm.animation_data.action = act
    N = int(act.frame_range[1])
    tiles = {'side': [], 'q34': []}
    for i in range(nf):
        sc.frame_set(round(act.frame_range[0] + i * (N - act.frame_range[0]) / nf))
        for v, d, ortho in (('side', Vector((-1, 0, 0.12)), True), ('q34', Vector((-1, -0.8, 0.35)), False)):
            d.normalize()
            cd.type = 'ORTHO' if ortho else 'PERSP'
            cd.ortho_scale = ext
            cam.location = ctr + d * ext * (4 if ortho else 1.6)
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
            p = os.path.join(out, f'{a}_{v}_{i:02d}.png')
            sc.render.filepath = p
            bpy.ops.render.render(write_still=True)
            tiles[v].append(Image.open(p).convert('RGB'))
    w, h = tiles['side'][0].size
    S = Image.new('RGB', (w * nf, h * 2))
    for r, v in enumerate(('side', 'q34')):
        for c, im in enumerate(tiles[v]):
            S.paste(im, (c * w, r * h))
    S.save(os.path.join(out, f'{a}_sheet.png'))
    print('sheet', a)
