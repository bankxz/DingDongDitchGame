"""Render multiview previews of a kitsune .blend.
python render_blend.py -- <file.blend> <outdir> [views,comma,sep] [action] [frame]
"""
import os, sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_views as rv

argv = sys.argv[sys.argv.index('--') + 1:]
blend, out = argv[0], argv[1]
views = argv[2].split(',') if len(argv) > 2 else ['front', 'back', 'side_right', 'top', 'q34_front_right', 'q34_back_left']
action = argv[3] if len(argv) > 3 else None
frame = int(argv[4]) if len(argv) > 4 else 1
bpy.ops.wm.open_mainfile(filepath=blend)
os.makedirs(out, exist_ok=True)
arm = bpy.data.objects.get('Kitsune_Rig')
if arm and action:
    arm.animation_data.action = bpy.data.actions[action]
bpy.context.scene.frame_set(frame)
rv.setup_scene(res=(1000, 750), samples=64)
S = 4.0
tgt = Vector((0, 0.45, 0.85)) * S
for v in views:
    ext = 3.9 * S
    if v in ('head_close', 'head_side'):
        rv.render_view(v, os.path.join(out, f'shape_{v}.png'), Vector((0, -0.78, 1.30)) * S, 1.05 * S)
    elif v == 'leg_close':
        rv.render_view(v, os.path.join(out, f'shape_{v}.png'), Vector((0.28, -0.34, 0.34)) * S, 0.85 * S)
    else:
        rv.render_view(v, os.path.join(out, f'shape_{v}.png'), tgt, ext)
