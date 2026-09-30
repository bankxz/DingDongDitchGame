"""Quick shape preview: build mesh with flat per-part colours and render views.
Usage: python preview_shape.py <outdir>
"""
import sys, os, math
import numpy as np
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitsune_geo as kg
import render_views as rv

out = sys.argv[-1]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

md, _ = kg.build_kitsune()
me = bpy.data.meshes.new('shape')
me.from_pydata([tuple(v) for v in md.verts], [], md.faces)
me.update()
ob = bpy.data.objects.new('GEO-shape', me)
bpy.context.scene.collection.objects.link(ob)
for p in me.polygons:
    p.use_smooth = True

COL = {'torso': (0.08, 0.05, 0.35), 'neck': (0.08, 0.05, 0.35), 'head': (0.1, 0.06, 0.4), 'ear': (0.1, 0.06, 0.4),
       'leg_f': (0.08, 0.05, 0.35), 'leg_h': (0.08, 0.05, 0.35), 'paw': (0.1, 0.8, 1.0), 'claw': (0.8, 1, 1),
       'tail': (0.2, 0.6, 1.0), 'tuft': (0.06, 0.04, 0.3), 'tuft_cyan': (0.1, 0.8, 1), 'spike': (0.06, 0.04, 0.3),
       'tail_tuft': (0.06, 0.04, 0.3), 'rope': (0.6, 0.02, 0.05), 'knot': (0.6, 0.02, 0.05), 'gem': (1, 0.02, 0.05),
       'frame': (0.5, 0.02, 0.04), 'bead': (0.7, 0.02, 0.04), 'tassel': (0.7, 0.02, 0.04), 'eye': (1, 0, 0)}
inv = {v: k for k, v in kg.PART_IDS.items()}
mats = {}
for pid, name in inv.items():
    m = bpy.data.materials.new('P-' + name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*COL[name], 1)
    b.inputs['Roughness'].default_value = 0.7
    me.materials.append(m)
    mats[pid] = len(me.materials) - 1
for poly, pid in zip(me.polygons, md.face_part):
    poly.material_index = mats[pid]

rv.setup_scene(res=(640, 480), samples=16)
tgt = Vector((0, 0.30, 0.85))
for v in ('front', 'back', 'side_left', 'top', 'q34_front_right', 'q34_back_left'):
    rv.render_view(v, os.path.join(out, f'shape_{v}.png'), tgt, 3.6)
print('tris', md.tri_count())
