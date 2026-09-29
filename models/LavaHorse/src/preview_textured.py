# Render the baked, textured model from the reference sheet's views.
import sys, os, bpy
sys.path.insert(0, os.path.dirname(__file__))
import render_views
blend, out, pre = sys.argv[-3:]
bpy.ops.wm.open_mainfile(filepath=blend)
render_views.setup_world(samples=24); render_views.add_glow()
for v in ('left', 'front', 'three_quarter', 'top', 'back'):
    render_views.render_view(v, os.path.join(out, f'{pre}_{v}.png'))
