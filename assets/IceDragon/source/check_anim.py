import bpy, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
arm = bpy.data.objects['IceDragon']; sc = bpy.context.scene
for act, frames in (('Walk', range(0, 41, 5)), ('Idle', range(0, 91, 15))):
    arm.animation_data.action = bpy.data.actions[act]
    print(act)
    for f in frames:
        sc.frame_set(f)
        row = []
        for b in ('Hand.L', 'Foot.L', 'Hand.R', 'Foot.R'):
            p = arm.matrix_world @ arm.pose.bones[b].tail
            row.append('%s y%.2f z%.2f' % (b, p.y, p.z))
        print(f, ' | '.join(row))
