"""Per action: Root drift, lowest deformed point, loop seam.  python3 check_clips.py model.blend [Armature] [Root]
Ground clips should sit at ~0 (claws/feet on the floor, not under it); flying clips should be
clearly above 0; root drift and loop seam should be 0."""
import bpy, sys
args = [a for a in sys.argv[sys.argv.index('--') + 1:]] if '--' in sys.argv else sys.argv[1:]
bpy.ops.wm.open_mainfile(filepath=args[0])
arm = bpy.data.objects[args[1]] if len(args) > 1 else next(o for o in bpy.data.objects if o.type == 'ARMATURE')
root = args[2] if len(args) > 2 else arm.data.bones[0].name
sc = bpy.context.scene; meshes = [o for o in bpy.data.objects if o.type == 'MESH']
for a in bpy.data.actions:
    arm.animation_data.action = a; n = int(a.frame_range[1]); lows = []; drift = 0.0
    for f in range(0, n + 1, max(1, n // 10)):
        sc.frame_set(f); dg = bpy.context.evaluated_depsgraph_get()
        lows.append(min(min((o.matrix_world @ v.co).z for v in o.evaluated_get(dg).to_mesh().vertices) for o in meshes))
        drift = max(drift, arm.pose.bones[root].matrix.translation.length - arm.data.bones[root].head_local.length)
    sc.frame_set(0); m0 = {b.name: b.matrix.copy() for b in arm.pose.bones}
    sc.frame_set(n)
    seam = max((m0[b.name].to_translation() - b.matrix.to_translation()).length +
               sum(abs(x) for r in (m0[b.name].to_3x3() - b.matrix.to_3x3()) for x in r) for b in arm.pose.bones)
    print(f'{a.name:10s} 0-{n:3d}  root_drift={abs(drift):.3f}  lowest={min(lows):.2f}..{max(lows):.2f}  loop_seam={seam:.4f}')
