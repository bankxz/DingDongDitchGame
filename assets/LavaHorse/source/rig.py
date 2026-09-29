"""Stage 2+3: LavaHorse_Rig, rigid skin weights (every face follows exactly one bone, so blocky segments never
stretch), LavaHorse_Idle + LavaHorse_Walk actions.  python3 rig.py -> out/LavaHorse_Source.blend"""
import os
import sys, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Quaternion
import design as D

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build') + '/'
W = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'build') + '/'
FPS = 30
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def make_rig():
    arm = bpy.data.armatures.new('LavaHorse_Armature')
    rig = bpy.data.objects.new('LavaHorse_Rig', arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    eb = {}
    for name, h, t, parent in D.bones():
        b = arm.edit_bones.new(name)
        b.head = Vector(h) * D.S
        b.tail = Vector(t) * D.S
        if parent:
            b.parent = eb[parent]
            b.use_connect = False
        eb[name] = b
    for b in arm.edit_bones:
        b.align_roll(Vector((0, 0, 1)) if abs(b.vector.normalized().z) < 0.9 else Vector((0, -1, 0)))
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.display_type = 'STICK'
    return rig


def skin(rig):
    fb = json.load(open(W + 'face_bones.json'))
    names = {b.name for b in rig.data.bones}
    bad = 0
    for obj in D.OBJECTS:
        o = bpy.data.objects[obj]
        me = o.data
        bones = fb[obj]
        assert len(bones) == len(me.polygons), (obj, len(bones), len(me.polygons))
        vb = {}
        for poly, b in zip(me.polygons, bones):
            for vi in poly.vertices:
                if vb.setdefault(vi, b) != b:
                    bad += 1
        groups = {}
        for vi, b in vb.items():
            assert b in names, b
            g = groups.get(b) or o.vertex_groups.new(name=b)
            groups[b] = g
            g.add([vi], 1.0, 'REPLACE')
        mod = o.modifiers.new('Armature', 'ARMATURE')
        mod.object = rig
        o.parent = rig
    print('skin: conflicting vertex bones', bad)


# ------------------------------------------------------------------ posing helpers (world-axis rotations)
def q_world(pb, axis, deg):
    rest = pb.bone.matrix_local.to_3x3()
    return Quaternion((rest.inverted() @ axis).normalized(), math.radians(deg))


def rot(pb, *pairs):
    q = Quaternion()
    for axis, deg in pairs:
        q = q_world(pb, axis, deg) @ q
    pb.rotation_quaternion = q


def loc_world(pb, v):
    pb.location = pb.bone.matrix_local.to_3x3().inverted() @ Vector(v)


def reset(rig):
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
        pb.scale = Vector((1, 1, 1))


def new_action(rig, name):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = act


def key_all(rig, frame):
    for pb in rig.pose.bones:
        pb.keyframe_insert('rotation_quaternion', frame=frame)
        pb.keyframe_insert('location', frame=frame)


def hoof_min_z(rig):
    bpy.context.view_layer.update()
    hoof = bpy.data.objects[D.HOOVES]
    dg = bpy.context.evaluated_depsgraph_get()
    ev = hoof.evaluated_get(dg)
    me = ev.to_mesh()
    z = min((hoof.matrix_world @ v.co).z for v in me.vertices)
    ev.to_mesh_clear()
    return z


def ground(rig, frame):
    """lift the whole horse so the lowest hoof point sits exactly on the ground (no sinking), then key"""
    P = rig.pose.bones
    z = hoof_min_z(rig)
    if z < 0:
        cur = P['Hips'].bone.matrix_local.to_3x3() @ P['Hips'].location
        loc_world(P['Hips'], (cur.x, cur.y, cur.z - z))
    key_all(rig, frame)


def idle(rig, seconds=3.0):
    frames = int(round(seconds * FPS))
    new_action(rig, 'LavaHorse_Idle')
    P = rig.pose.bones
    for f in range(frames + 1):
        w = 2 * math.pi * (f % frames) / frames
        reset(rig)
        loc_world(P['Hips'], (0, 0, 0.035 * math.sin(w)))                       # breathing rise / fall
        rot(P['Chest'], (X, 1.2 * math.sin(w)))
        rot(P['Neck'], (X, 2.5 * math.sin(w - 0.6)), (Z, 3.0 * math.sin(w * 0.5 + 0.3) * 0 + 2.0 * math.sin(w)))
        rot(P['Head'], (X, -3.0 * math.sin(w - 1.0)), (Z, 4.0 * math.sin(w + 0.4)))
        rot(P['Jaw'], (X, 1.5 * max(0.0, math.sin(2 * w))))
        for i, b in enumerate(('Tail_1', 'Tail_2', 'Tail_3')):
            rot(P[b], (Z, (5 + 3 * i) * math.sin(w - 0.7 * i)), (X, 2.0 * math.sin(2 * w - 0.5 * i)))
        for i, b in enumerate(('Mane_1', 'Mane_2', 'Mane_3')):
            rot(P[b], (X, 3.0 * math.sin(w - 0.5 * i)), (Z, 2.0 * math.sin(2 * w - 0.4 * i)))
        ground(rig, f + 1)
    return frames


def walk(rig, seconds=1.2):
    """4-beat lateral walk (LH, LF, RH, RF), in place, loopable. Upper leg swings about the shoulder / hip,
    lower leg folds during the swing phase so the hoof clears the ground; hooves stay level."""
    frames = int(round(seconds * FPS))
    new_action(rig, 'LavaHorse_Walk')
    P = rig.pose.bones
    offs = {('Back', 'L'): 0.0, ('Front', 'L'): 0.25, ('Back', 'R'): 0.5, ('Front', 'R'): 0.75}
    duty = 0.62
    for f in range(frames + 1):
        ph = (f % frames) / frames
        w = 2 * math.pi * ph
        reset(rig)
        loc_world(P['Hips'], (0, 0, 0.05 * math.cos(4 * w)))                     # small bob every footfall
        rot(P['Hips'], (Y, 2.0 * math.sin(w)), (Z, 1.5 * math.sin(w)))
        rot(P['Chest'], (Y, -2.0 * math.sin(w)), (Z, -1.5 * math.sin(w)))
        rot(P['Neck'], (X, 4.0 * math.sin(2 * w)))                             # head nods with the stride
        rot(P['Head'], (X, -2.5 * math.sin(2 * w - 0.6)))
        for i, b in enumerate(('Tail_1', 'Tail_2', 'Tail_3')):
            rot(P[b], (Z, (6 + 4 * i) * math.sin(w - 0.8 * i)), (X, 3.0 * math.sin(2 * w - 0.6 * i)))
        for i, b in enumerate(('Mane_1', 'Mane_2', 'Mane_3')):
            rot(P[b], (X, 4.0 * math.sin(2 * w - 0.6 * i - 0.8)))
        for (leg, side), off in offs.items():
            p = (ph - off) % 1.0
            amp = 22.0 if leg == 'Front' else 20.0
            if p < duty:                        # stance: hoof moves front -> back
                s = p / duty
                sw = amp * (1 - 2 * s)
                bend = 0.0
            else:                               # swing: back -> front with the lower leg folded
                s = (p - duty) / (1 - duty)
                sm = s * s * (3 - 2 * s)
                sw = amp * (-1 + 2 * sm)
                bend = 38.0 * math.sin(math.pi * s)
            # +X rotation tips the hoof backward for these bones (tail points down): swing forward = negative
            rot(P[f'{leg}Leg_Upper_{side}'], (X, -sw))
            fold = bend if leg == 'Front' else -bend     # front knees fold back, hocks fold forward
            rot(P[f'{leg}Leg_Lower_{side}'], (X, fold))
            rot(P[f'{leg}Hoof_{side}'], (X, sw - fold))  # keep the hoof sole level
        ground(rig, f + 1)
    return frames


def lowest_hoof(rig, action, frames):
    """min Z of any hoof-sole vertex over the action (ground contact check, studs)"""
    rig.animation_data.action = bpy.data.actions[action]
    hoof = bpy.data.objects[D.HOOVES]
    worst_low, worst_high_stance = 9.0, 0.0
    for f in range(1, frames + 2):
        bpy.context.scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        me = hoof.evaluated_get(dg).to_mesh()
        zs = [(hoof.matrix_world @ v.co).z for v in me.vertices]
        worst_low = min(worst_low, min(zs))
        hoof.evaluated_get(dg).to_mesh_clear()
    return worst_low


def main():
    bpy.ops.wm.open_mainfile(filepath=OUT + 'LavaHorse_stage1.blend')
    bpy.context.scene.render.fps = FPS
    rig = make_rig()
    skin(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='POSE')
    n_idle = idle(rig)
    n_walk = walk(rig)
    bpy.ops.object.mode_set(mode='OBJECT')
    for a in ('LavaHorse_Idle', 'LavaHorse_Walk'):
        n = n_idle if a.endswith('Idle') else n_walk
        print(a, 'frames', n + 1, 'lowest hoof point (studs, ground = 0):', round(lowest_hoof(rig, a, n), 3))
    rig.animation_data.action = None
    reset(rig)
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=OUT + 'LavaHorse_Source.blend', relative_remap=True)
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()
    print('bones', len(rig.data.bones))


if __name__ == '__main__':
    main()
