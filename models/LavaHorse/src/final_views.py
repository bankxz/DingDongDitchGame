import sys, os, bpy
sys.path.insert(0, os.path.dirname(__file__))
import render_views
out = sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=os.path.join(os.path.dirname(__file__), '..', 'LavaHorse.blend'))
bpy.data.objects['LavaHorseRig'].animation_data.action = None
for pb in bpy.data.objects['LavaHorseRig'].pose.bones:
    pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
render_views.setup_world(samples=32, res=(1280, 960)); render_views.add_glow()
for v in sys.argv[-2].split(','):
    render_views.render_view(v, os.path.join(out, f'final_{v}.png'))
