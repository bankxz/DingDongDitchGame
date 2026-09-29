"""For every clip: Root bone motion, lowest mesh point per frame, and loop seam error."""
import bpy, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
arm = bpy.data.objects['IceDragon']; sc = bpy.context.scene
meshes = [o for o in bpy.data.objects if o.type == 'MESH']
for act in ('Idle', 'Walk', 'FlyIdle', 'FlyWalk'):
    a = bpy.data.actions[act]; arm.animation_data.action = a
    n = int(a.frame_range[1])
    lows, root_moves = [], 0.0
    for f in range(0, n + 1, max(1, n // 10)):
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
        low = min(min((o.matrix_world @ v.co).z for v in o.evaluated_get(dg).to_mesh().vertices) for o in meshes)
        lows.append(low)
        root_moves = max(root_moves, (arm.pose.bones['Root'].matrix.translation).length)
    sc.frame_set(0); m0 = {b.name: b.matrix.copy() for b in arm.pose.bones}
    sc.frame_set(n); seam = max((m0[b.name] - b.matrix).to_translation().length + sum(abs(x) for r in (m0[b.name].to_3x3() - b.matrix.to_3x3()) for x in r) for b in arm.pose.bones)
    print(f'{act:8s} frames 0-{n}  root_offset_max={root_moves:.3f}  lowest_point min/max={min(lows):.2f}/{max(lows):.2f}  loop_seam={seam:.4f}')
