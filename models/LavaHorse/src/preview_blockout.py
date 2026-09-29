# Quick flat-colour blockout renders to compare silhouette/proportions with the reference sheet.
import sys, os, bpy
sys.path.insert(0, os.path.dirname(__file__))
import build_geo, render_views

OUT = sys.argv[-1]
parts = build_geo.build_all()
COL = {'lava': (0.55, 0.06, 0.02), 'rock': (0.06, 0.03, 0.025), 'hoof': (0.05, 0.035, 0.035),
       'muzzle': (0.2, 0.04, 0.03), 'eye_white': (1, 1, 1), 'eye_black': (0, 0, 0), 'flame': (1, 0.45, 0.02)}
mats = {}
for k, c in COL.items():
    m = bpy.data.materials.new('P_' + k)
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*c, 1)
    if k == 'flame':
        b.inputs['Emission Color'].default_value = (1, 0.5, 0.05, 1)
        b.inputs['Emission Strength'].default_value = 0.6
    mats[k] = m
tris = 0
for ob, cat, bone in parts:
    ob.data.materials.append(mats[cat])
    tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
print('TRIS', tris, 'PARTS', len(parts))
render_views.setup_world(samples=16)
for v in ('left', 'front', 'three_quarter', 'top', 'back'):
    render_views.render_view(v, os.path.join(OUT, f'block_{v}.png'))
