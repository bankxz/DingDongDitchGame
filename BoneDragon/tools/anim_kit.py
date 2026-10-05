"""anim_kit - pose helpers + IK-solve-then-bake for looping Roblox clips (headless bpy).

    import anim_kit as A
    A.bind(arm)                                   # the armature object
    legs = {'FL': ('UpperArm.L', 'Forearm.L', 'Hand.L', 0.25), ...}   # upper, lower, foot, gait phase
    A.add_leg_ik(legs, root='Root')
    clips = [('Idle', 90, pose_idle, False), ('Walk', 40, pose_walk, False),
             ('FlyIdle', 60, pose_fly, True)]     # (name, frames, pose_fn(f, n), flying)
    A.bake_clips(clips, legs, step={'Idle': 2})   # samples with IK, deletes IK, writes FK actions

pose_fn(f, n) sets pose bones for frame f: use set_rot(bone, (axis, deg), ...) for rotations
about ARMATURE-space axes and world_loc(bone, delta) for translations; drive everything with
S(f, n, phase) so frame n == frame 0 (seamless loop). Flying clips set IK influence 0 so legs
can tuck; the Root bone is never keyed away from rest (lift the Torso instead).
Axis cheat-sheet (model faces -Y, Z up): +X rotation pitches a forward-pointing part DOWN and
swings a downward-pointing limb BACKWARD; +Y rotation lowers the +X (left) side.
"""
import math
from mathutils import Vector as V, Matrix, Quaternion

arm = None
def bind(armature): 
    global arm; arm = armature

S = lambda f, n, ph=0.0: math.sin(2 * math.pi * (f / n + ph))
def flap(w):
    """0 at the top of the upstroke, 1 at the bottom of the downstroke (w = beat phase)."""
    return 0.5 - 0.5 * math.cos(2 * math.pi * w)

def reset_pose():
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'; pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)

def world_rot(name, axis, deg):
    R = arm.data.bones[name].matrix_local.to_3x3()
    return (R.inverted() @ Matrix.Rotation(math.radians(deg), 3, V(axis)) @ R).to_quaternion()

def set_rot(name, *rots):
    q = Quaternion()
    for axis, deg in rots: q = world_rot(name, axis, deg) @ q
    arm.pose.bones[name].rotation_quaternion = q

def world_loc(name, delta):
    return arm.data.bones[name].matrix_local.to_3x3().inverted() @ V(delta)

def key(frame, names):
    for n in names:
        pb = arm.pose.bones[n]
        pb.keyframe_insert('location', frame=frame, group=n); pb.keyframe_insert('rotation_quaternion', frame=frame, group=n)

def new_action(name):
    import bpy
    if arm.animation_data is None: arm.animation_data_create()
    act = bpy.data.actions.new(name); act.use_fake_user = True; arm.animation_data.action = act
    return act

def add_leg_ik(legs, root='Root'):
    """Temporary IK target per leg at the foot bone; foot copies the target's rotation."""
    import bpy
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
    for leg, (up, lo, ft, ph) in legs.items():
        src = arm.data.edit_bones[ft]; eb = arm.data.edit_bones.new('IK_' + leg)
        eb.head, eb.tail, eb.roll = src.head, src.tail, src.roll
        eb.parent = arm.data.edit_bones[root]; eb.use_deform = False
    bpy.ops.object.mode_set(mode='POSE')
    for leg, (up, lo, ft, ph) in legs.items():
        c = arm.pose.bones[lo].constraints.new('IK'); c.target = arm; c.subtarget = 'IK_' + leg
        c.chain_count = 2; c.use_tail = True
        c2 = arm.pose.bones[ft].constraints.new('COPY_ROTATION'); c2.target = arm; c2.subtarget = 'IK_' + leg

def foot_offset(p, stride=1.7, lift=0.55, duty=0.62):
    """In-place gait: stance slides the foot back (+Y), swing returns it forward, lifted."""
    if p < duty: return (-stride / 2 + stride * p / duty, 0.0)
    t = (p - duty) / (1 - duty); e = 0.5 - 0.5 * math.cos(math.pi * t)
    return (stride / 2 - stride * e, lift * math.sin(math.pi * t))

def bake_clips(clips, legs, step=None):
    """Sample every clip with constraints live, then remove IK bones/constraints and write
    plain FK actions (location + quaternion on deform bones) - Roblox imports these cleanly."""
    import bpy
    step = step or {}; sc = bpy.context.scene; sc.render.fps = 30
    deform = [b.name for b in arm.data.bones if not b.name.startswith('IK_')]
    allb = [b.name for b in arm.data.bones]
    cons = [c for leg, (up, lo, ft, ph) in legs.items() for c in (*arm.pose.bones[lo].constraints, *arm.pose.bones[ft].constraints)]
    baked = {}
    for name, n, fn, flying in clips:
        for c in cons: c.influence = 0.0 if flying else 1.0
        src = new_action(name + 'Src')
        for f in range(n + 1): reset_pose(); fn(f, n); key(f, allb)
        baked[name] = {}
        for f in range(n + 1):
            sc.frame_set(f); bpy.context.view_layer.update()
            baked[name][f] = {b: arm.pose.bones[b].matrix.copy() for b in deform}
        arm.animation_data.action = None; bpy.data.actions.remove(src)
    for leg, (up, lo, ft, ph) in legs.items():
        for pb in (arm.pose.bones[lo], arm.pose.bones[ft]):
            for c in list(pb.constraints): pb.constraints.remove(c)
    bpy.ops.object.mode_set(mode='EDIT')
    for leg in legs: arm.data.edit_bones.remove(arm.data.edit_bones['IK_' + leg])
    bpy.ops.object.mode_set(mode='POSE')
    acts = {}
    for name, n, fn, flying in clips:
        act = acts[name] = new_action(name); reset_pose()
        for f in range(0, n + 1, step.get(name, 1)):
            for bn in deform:
                bone = arm.data.bones[bn]; P = baked[name][f][bn]
                basis = (bone.matrix_local.inverted() @ bone.parent.matrix_local @ baked[name][f][bone.parent.name].inverted() @ P
                         if bone.parent else bone.matrix_local.inverted() @ P)
                loc, rot, _ = basis.decompose()
                pb = arm.pose.bones[bn]; pb.location = loc; pb.rotation_quaternion = rot
            key(f, deform)
        act.frame_range = (0, n); act.use_frame_range = True; act.use_cyclic = True
    reset_pose(); bpy.ops.object.mode_set(mode='OBJECT')
    return acts
