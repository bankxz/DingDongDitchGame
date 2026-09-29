"""Create the Idle and Walk actions on the LavaScorpion rig (run after build_scorpion.py).

Rotations are authored as armature-space rotations about each bone's head and converted to
pose-bone local quaternions (basis = Rrest^-1 * R * Rrest), so they compose correctly down the chain.
Every frame is keyed (linear) so both clips loop seamlessly. Walk is in place (Roblox moves the model).
"""
import math
import os

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.normpath(os.path.join(HERE, "..", "LavaScorpion.blend"))
bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
sc.render.fps = 30
arm = bpy.data.objects["LavaScorpion"]
bones = arm.data.bones
TAU = 2 * math.pi

for pb in arm.pose.bones:
    pb.rotation_mode = "QUATERNION"


def R(axis, deg):
    return Matrix.Rotation(math.radians(deg), 3, Vector(axis).normalized())


def set_pose(rots, locs):
    """rots: bone -> 3x3 armature-space rotation; locs: bone -> armature-space offset."""
    for pb in arm.pose.bones:
        rest = bones[pb.name].matrix_local.to_3x3()
        m = rots.get(pb.name, Matrix.Identity(3))
        q = (rest.inverted() @ m @ rest).to_quaternion()
        pb.rotation_quaternion = q
        pb.location = rest.inverted() @ locs.get(pb.name, Vector())


def key_all(frame):
    for pb in arm.pose.bones:
        pb.keyframe_insert("rotation_quaternion", frame=frame)
        pb.keyframe_insert("location", frame=frame)


def fcurves(action):
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    out = []
    for layer in action.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


LEGS = [(f"Leg{i}", side, s) for i in range(1, 5) for side, s in (("L", 1), ("R", -1))]


def leg_axes(n, side):
    b1 = bones[f"{n}_1.{side}"]
    b3 = bones[f"{n}_3.{side}"]
    hip = b1.head_local
    foot = b3.tail_local
    d = foot - hip
    dh = Vector((d.x, d.y, 0))
    reach = dh.length
    dh.normalize()
    k = Vector((0, 0, 1)).cross(dh)  # rotating +angle about k swings the leg DOWN
    return k, reach


LEG_AX = {(n, side): leg_axes(n, side) for n, side, s in LEGS}


def make_action(name, frames, pose_fn):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data_create()
    arm.animation_data.action = act
    for f in range(frames + 1):
        rots, locs = pose_fn(f / frames)
        set_pose(rots, locs)
        key_all(f + 1)
    for fc in fcurves(act):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    act.frame_range = (1, frames + 1)
    print(f"ACTION {name}: frames 1..{frames + 1}, fcurves={len(fcurves(act))}")
    return act


# ------------------------------------------------------------------ IDLE (4 s)
def idle(t):
    rots, locs = {}, {}
    bob = 0.02 * math.sin(TAU * t)
    locs["Body"] = Vector((0, 0, bob))
    rots["Body"] = R((1, 0, 0), 1.2 * math.sin(TAU * t + 0.6))
    for i in range(1, 7):
        rots[f"Tail{i}"] = R((1, 0, 0), 2.2 * math.sin(TAU * t - i * 0.45)) @ R((0, 0, 1), 1.6 * math.sin(TAU * t - i * 0.35))
    # stinger: slow sway + two quick twitches per loop
    tw = math.exp(-((t - 0.3) % 1 * 14) ** 2) + math.exp(-((t - 0.8) % 1 * 14) ** 2)
    rots["Stinger"] = R((1, 0, 0), 3 * math.sin(TAU * t) - 9 * tw)
    for side, s in (("L", 1), ("R", -1)):
        ph = 0 if s > 0 else 0.5
        rots[f"Arm1.{side}"] = R((0, 0, 1), 3 * s * math.sin(TAU * (t + ph)))
        rots[f"Hand.{side}"] = R((1, 0, 0), 3 * math.sin(TAU * (t + ph) + 1))
        opn = 0.5 - 0.5 * math.cos(TAU * 2 * (t + ph))  # open/close twice per loop
        rots[f"Finger.{side}"] = R((0, 0, 1), -s * 14 * opn)
    # keep the feet planted while the body breathes
    for n, side, s in LEGS:
        k, reach = LEG_AX[(n, side)]
        th = math.degrees(bob / reach)
        rots[f"{n}_1.{side}"] = R(k, th)
        rots[f"{n}_2.{side}"] = Matrix.Identity(3)
    return rots, locs


# ------------------------------------------------------------------ WALK (32 frames)
GROUP_A = {("Leg1", "L"), ("Leg2", "R"), ("Leg3", "L"), ("Leg4", "R")}
STRIDE, LIFT, TUCK = 13.0, 20.0, 12.0


def walk(t):
    rots, locs = {}, {}
    bob = 0.025 * math.cos(TAU * 2 * t)
    locs["Body"] = Vector((0, 0, bob))
    rots["Body"] = R((0, 1, 0), 1.8 * math.sin(TAU * t)) @ R((0, 0, 1), 1.5 * math.sin(TAU * t))
    for n, side, s in LEGS:
        p = (t + (0.0 if (n, side) in GROUP_A else 0.5)) % 1.0
        k, reach = LEG_AX[(n, side)]
        if p < 0.5:  # stance: foot on the ground sweeping backwards
            u = p / 0.5
            yaw = s * STRIDE * (2 * u - 1)
            lift = 0.0
        else:        # swing: foot lifts and travels forwards
            u = (p - 0.5) / 0.5
            yaw = s * STRIDE * (1 - 2 * u)
            lift = LIFT * math.sin(math.pi * u)
        # body bob compensation keeps planted feet on the floor
        comp = math.degrees(bob / reach)
        rots[f"{n}_1.{side}"] = R((0, 0, 1), yaw) @ R(k, -lift + comp)
        rots[f"{n}_2.{side}"] = R(k, TUCK * (lift / LIFT))
    for i in range(1, 7):
        rots[f"Tail{i}"] = R((0, 0, 1), 3.0 * math.sin(TAU * t - i * 0.5)) @ R((1, 0, 0), 2.0 * math.sin(TAU * 2 * t - i * 0.4))
    rots["Stinger"] = R((1, 0, 0), 4 * math.sin(TAU * 2 * t - 3.0))
    for side, s in (("L", 1), ("R", -1)):
        ph = 0 if s > 0 else 0.5
        rots[f"Arm1.{side}"] = R((0, 0, 1), 5 * s * math.sin(TAU * (t + ph)))
        rots[f"Hand.{side}"] = R((1, 0, 0), -4 + 3 * math.sin(TAU * (t + ph)))
        rots[f"Finger.{side}"] = R((0, 0, 1), -s * 6 * (0.5 - 0.5 * math.cos(TAU * (t + ph))))
    return rots, locs


idle_act = make_action("Idle", 120, idle)
walk_act = make_action("Walk", 32, walk)

# leave the rig in rest pose with Idle assigned; each clip also gets its own NLA track for easy preview
for act in (idle_act, walk_act):
    tr = arm.animation_data.nla_tracks.new()
    tr.name = act.name
    st = tr.strips.new(act.name, 1, act)
    tr.mute = act.name != "Idle"
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_quaternion = Quaternion()
    pb.location = Vector()
sc.frame_start, sc.frame_end = 1, 121
bpy.ops.wm.save_as_mainfile(filepath=BLEND, relative_remap=True)
print("saved", BLEND)
