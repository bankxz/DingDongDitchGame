"""Idle + Walk actions for the Ancient Dragon rig (quaternion keys, loopable)."""
import bpy, math
from mathutils import Quaternion, Vector

def _q(pb, axis, deg):
    """rotation about a WORLD axis (rest-pose frame) expressed in pose-bone local space."""
    rest = pb.bone.matrix_local.to_quaternion()
    local_axis = rest.inverted() @ Vector(axis)
    return Quaternion(local_axis, math.radians(deg))

def key_pose(rig, frame, pose):
    """pose: {bone: [(axis, deg), ...] or ('loc', vec)}"""
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        q = Quaternion()
        loc = Vector((0, 0, 0))
        for item in pose.get(pb.name, []):
            if item[0] == 'loc':
                rest = pb.bone.matrix_local.to_quaternion()
                loc = rest.inverted() @ Vector(item[1])
            else:
                q = _q(pb, *item) @ q
        pb.rotation_quaternion = q
        pb.location = loc
        pb.keyframe_insert('rotation_quaternion', frame=frame)
        pb.keyframe_insert('location', frame=frame)

X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)

def idle_pose(t):
    s = math.sin(2 * math.pi * t); c = math.cos(2 * math.pi * t)
    p = {
        'Hips': [('loc', (0, 0, -0.03 * (1 - c) / 2))],
        'Chest': [(X, 2.0 * s)],
        'Neck1': [(X, -2.5 * s)],
        'Neck2': [(X, -2.0 * s), (Z, 3 * math.sin(2 * math.pi * t + 1))],
        'Head': [(X, 3.0 * s), (Z, 4 * math.sin(2 * math.pi * t + 0.5))],
        'Jaw': [(X, -3 * max(0.0, s))],
    }
    for i in range(9):
        p['Tail%d' % (i + 1)] = [(Z, 3.0 * math.sin(2 * math.pi * t - i * 0.55))]
    for sf, sg in (('_L', 1), ('_R', -1)):
        p['Wing1' + sf] = [(Y, sg * 4.0 * s)]
        p['Wing2' + sf] = [(Y, sg * 3.0 * math.sin(2 * math.pi * t - 0.6))]
    return p

def walk_pose(t):
    ph = 2 * math.pi * t
    p = {
        'Hips': [('loc', (0, 0, 0.05 * abs(math.sin(ph)))), (Z, 3 * math.sin(ph))],
        'Chest': [(Z, -3 * math.sin(ph)), (Y, 2 * math.sin(ph))],
        'Neck1': [(X, 3 * math.sin(2 * ph))],
        'Head': [(X, -3 * math.sin(2 * ph)), (Z, 2 * math.sin(ph))],
    }
    # diagonal gait: FL with RR, FR with RL
    legs = {'_L': 0.0, '_R': math.pi}
    for sf, off in legs.items():
        f = ph + off; r = ph + off + math.pi
        p['UpperArm' + sf] = [(X, 22 * math.sin(f))]
        p['Forearm' + sf] = [(X, -18 * max(0.0, math.cos(f)))]
        p['Hand' + sf] = [(X, -10 * math.sin(f))]
        p['Thigh' + sf] = [(X, 20 * math.sin(r))]
        p['Shin' + sf] = [(X, 22 * max(0.0, math.cos(r)))]
        p['Foot' + sf] = [(X, -12 * math.sin(r))]
    for i in range(9):
        p['Tail%d' % (i + 1)] = [(Z, 5.0 * math.sin(ph - i * 0.6))]
    for sf, sg in (('_L', 1), ('_R', -1)):
        p['Wing1' + sf] = [(Y, sg * 3.0 * math.sin(2 * ph))]
        p['Wing2' + sf] = [(Y, sg * 2.0 * math.sin(2 * ph - 0.5))]
    return p

def _action(rig, name, fn, frames, step):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data_create(); rig.animation_data.action = act
    for f in range(0, frames + 1, step):
        key_pose(rig, f + 1, fn(f / frames))
    act.frame_range = (1, frames + 1)
    return act

def make_actions(rig):
    bpy.context.scene.render.fps = 30
    idle = _action(rig, 'Idle', idle_pose, 90, 5)
    walk = _action(rig, 'Walk', walk_pose, 32, 2)
    rig.animation_data.action = idle
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 91
    return idle, walk
