# Contact sheets for the Idle / Walk actions (animation quality gate).
import sys, os, bpy
sys.path.insert(0, os.path.dirname(__file__))
import render_views
out = sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=os.path.join(os.path.dirname(__file__), '..', 'LavaHorse.blend'))
render_views.setup_world(samples=8, res=(480, 360))
rig = bpy.data.objects['LavaHorseRig']
for act_name, frames, view in (('Walk', [0, 4, 8, 12, 16, 20, 24, 28], 'left'),
                               ('Idle', [0, 20, 40, 60, 72, 90, 105, 120], 'three_quarter')):
    rig.animation_data.action = bpy.data.actions[act_name]
    for f in frames:
        bpy.context.scene.frame_set(f)
        render_views.render_view(view, os.path.join(out, f'anim_{act_name}_{f:03d}.png'))
