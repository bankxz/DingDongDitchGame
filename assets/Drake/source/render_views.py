"""Render validation views of Drake.blend (textured).  usage: python3 render_views.py OUTDIR [samples]"""
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy
from mathutils import Vector, Quaternion
import preview as P

OUT = sys.argv[1]
SAMPLES = int(sys.argv[2]) if len(sys.argv) > 2 else 32
os.makedirs(OUT, exist_ok=True)
P.OUT = OUT

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, '..', 'Drake.blend'))
sc = bpy.context.scene
for o in list(sc.objects):
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o)
co = P.setup_scene()
sc.cycles.samples = SAMPLES
rig = bpy.data.objects['DrakeRig']
rig.hide_render = True


def rest():
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_quaternion = Quaternion(); pb.location = Vector()


ortho = {k: v for k, v in P.VIEWS.items() if k not in ('q34',)}
rest()
P.render_views(co, 'tex', ortho)
rig.animation_data.action = bpy.data.actions['Drake_Idle']
sc.frame_set(0)
P.render_views(co, 'tex', {'q34': P.VIEWS['q34'], 'q34pose': ((9.5, -6.0, 2.4), (0, -0.2, 1.0), None, (1200, 700))})
