"""
Armature, skin weights, animations and exports for the kitsune.

Rig (50 bones, all deform):
  Root
  └ Hips ─ Spine ─ Chest ─ Neck1 ─ Neck2 ─ Head ─ Ear_L / Ear_R
     │               ├ FrontLegUpper_L/R ─ FrontLegLower ─ FrontPaw
     │               └ Tassel_L/R
     ├ HindLegUpper_L/R ─ HindLegLower ─ HindFoot ─ HindPaw
     └ TailBase ─ Tail1..8_1 ─ _2 ─ _3
"""
import math
import os

import numpy as np
import bpy
from mathutils import Vector, Quaternion, Matrix

import kitsune_geo as kg

FPS = 30


def S():
    import build_kitsune
    return build_kitsune.WORLD_SCALE


def V(p):
    return Vector(tuple(float(x) * S() for x in p))


# ------------------------------------------------------------------ bones
def group_points(ob, name):
    """World-unit (shoulder-height) positions of the vertices weighted to a group."""
    g = ob.vertex_groups.get(name)
    if g is None:
        return None
    pts = [v.co for v in ob.data.vertices if any(e.group == g.index and e.weight > 0.5 for e in v.groups)]
    return np.array([tuple(p) for p in pts]) / S() if pts else None


def bone_specs(ob=None):
    """Bone layout for the v28 anatomy (unit = shoulder height)."""
    g = kg
    v3 = kg.v3
    nk = [v3(0, -0.34, 0.83), v3(0, -0.43, 0.99), v3(0, -0.50, 1.14), v3(0, -0.57, 1.27), v3(0, -0.65, 1.36)]
    nose = v3(0, float(g.HEAD_KEYS[-1, 0]), float(g.HEAD_KEYS[-1, 1]))
    b = []   # (name, head, tail, parent, connected)
    b.append(('Root', (0, 0, 0), (0, -0.3, 0), None, False))
    b.append(('Hips', (0, 0.50, 0.82), (0, 0.24, 0.82), 'Root', False))
    b.append(('Spine', (0, 0.24, 0.82), (0, -0.04, 0.83), 'Hips', True))
    b.append(('Chest', (0, -0.04, 0.83), (0, -0.34, 0.86), 'Spine', True))
    b.append(('Neck1', (0, -0.38, 0.90), (0, -0.50, 1.15), 'Chest', False))
    b.append(('Neck2', (0, -0.50, 1.15), (0, -0.60, 1.32), 'Neck1', True))
    b.append(('Head', (0, -0.60, 1.36), tuple(nose), 'Neck2', False))
    for sx, sfx in ((1, '_L'), (-1, '_R')):
        m = lambda p: kg.mx(p, sx)
        b.append(('Ear' + sfx, m(g.EAR_BASE), m(g.EAR_TIP), 'Head', False))
        fl, hl = [m(p) for p in g.FRONT_LEG], [m(p) for p in g.HIND_LEG]
        b.append(('FrontLegUpper' + sfx, fl[0], fl[1], 'Chest', False))
        b.append(('FrontLegLower' + sfx, fl[1], fl[2], 'FrontLegUpper' + sfx, True))
        b.append(('FrontPaw' + sfx, fl[2], m(g.FRONT_PAW_C + v3(0, -0.12, -0.03)), 'FrontLegLower' + sfx, True))
        b.append(('HindLegUpper' + sfx, hl[0], hl[1], 'Hips', False))
        b.append(('HindLegLower' + sfx, hl[1], hl[2], 'HindLegUpper' + sfx, True))
        b.append(('HindFoot' + sfx, hl[2], hl[3], 'HindLegLower' + sfx, True))
        b.append(('HindPaw' + sfx, hl[3], m(g.HIND_PAW_C + v3(0, -0.12, -0.03)), 'HindFoot' + sfx, True))
        # tassel: measured on the final mesh (it is seated onto the fur after the sculpt)
        tp = group_points(ob, 'Tassel' + sfx) if ob is not None else None
        if tp is not None:
            top = tp[tp[:, 2].argmax()].copy()
            top[0] = abs(top[0]) * sx
            top = top + v3(0, 0, 0.06)
        else:
            top = m(g.TASSEL_TOP)
        b.append(('Tassel' + sfx, tuple(top), tuple(top + v3(0, 0, -0.40)), 'Chest', False))
    b.append(('TailBase', g.TAIL_BASE, g.TAIL_BASE + v3(0, 0.14, 0.05), 'Hips', False))
    # eyes: tiny bones so the sleep pose can close them (lens sinks into the socket)
    for sx, sfx in ((1, '_L'), (-1, '_R')):
        ep = group_points(ob, 'Eye' + sfx) if ob is not None else None
        c = ep.mean(0) if ep is not None else kg.mx(v3(0.14, -0.80, 1.40), sx)
        b.append(('Eye' + sfx, tuple(c), tuple(c + kg.norm(v3(sx * 0.42, -0.46, 0.78)) * 0.05), 'Head', False))
    for spec in g.tuned_specs():
        pts = g.tail_bone_points(spec)
        par = 'TailBase'
        for k in range(g.TAIL_NB):
            nm = f'{spec[0]}_{k + 1}'
            b.append((nm, pts[k], pts[k + 1], par, k > 0))
            par = nm
    return b


def build_rig(ob, md=None):
    """Armature for the finished mesh.  Skin weights come from the vertex groups
    the build already transferred onto the sculpted body / accessories; they are
    limited to 4 influences and normalised (Roblox skinning)."""
    arm_data = bpy.data.armatures.new('Kitsune_Armature')
    arm = bpy.data.objects.new('Kitsune_Rig', arm_data)
    bpy.context.scene.collection.objects.link(arm)
    arm_data.display_type = 'STICK'
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(o == arm)
    bpy.ops.object.mode_set(mode='EDIT')
    X = Vector((1, 0, 0))
    specs = bone_specs(ob)
    for name, h, t, par, conn in specs:
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail = V(h), V(t)
        d = (eb.tail - eb.head).normalized()
        # sagittal bones: local X == world X so X-rotations are clean pitch
        if abs(d.x) < 0.35:
            z = X.cross(d)
        else:
            z = Vector((0, 0, 1)) - d * d.z
        if z.length > 1e-6:
            eb.align_roll(z.normalized())
        eb.use_deform = True
    for name, h, t, par, conn in specs:
        if par:
            eb = arm_data.edit_bones[name]
            eb.parent = arm_data.edit_bones[par]
            eb.use_connect = conn
    bpy.ops.object.mode_set(mode='OBJECT')

    # weights: drop groups that are not bones, limit to 4, normalise
    names = {s[0] for s in specs}
    for vg in list(ob.vertex_groups):
        if vg.name not in names:
            print('RIG dropping non-bone group', vg.name)
            ob.vertex_groups.remove(vg)
    bpy.context.view_layer.objects.active = ob
    for o in bpy.context.view_layer.objects:
        o.select_set(o == ob)
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    unweighted = sum(1 for v in ob.data.vertices if not v.groups)
    print('RIG bones', len(specs), 'groups', len(ob.vertex_groups), 'unweighted verts', unweighted)
    ob.parent = arm
    mod = ob.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return arm


# ------------------------------------------------------------ pose helpers
class Pose:
    """Collects local rotations / translations for one frame."""

    def __init__(self, arm):
        self.arm = arm
        self.rot = {}
        self.loc = {}

    def _R(self, name):
        return self.arm.data.bones[name].matrix_local.to_3x3()

    def world(self, name, axis, ang):
        """Rotate bone about a world-space axis (rest orientation)."""
        ax = (self._R(name).inverted() @ Vector(axis)).normalized()
        self.local(name, ax, ang)

    def local(self, name, axis, ang):
        q = Quaternion(Vector(axis), ang)
        self.rot[name] = self.rot.get(name, Quaternion()) @ q

    def toward(self, name, target_dir, ang):
        """Rotate bone so its direction swings toward target_dir by ang."""
        b = self.arm.data.bones[name]
        d = (b.tail_local - b.head_local).normalized()
        ax = d.cross(Vector(target_dir))
        if ax.length < 1e-6:
            return
        self.world(name, ax.normalized(), ang)

    def aim(self, name, target_dir, weight=1.0):
        """Rotate bone (from rest) so it points along target_dir (x weight)."""
        b = self.arm.data.bones[name]
        d = (b.tail_local - b.head_local).normalized()
        t = Vector(target_dir).normalized()
        ax = d.cross(t)
        if ax.length < 1e-6:
            return
        ang = d.angle(t) * weight
        self.world(name, ax.normalized(), ang)

    def world_delta(self, name):
        """Accumulated world-space rotation of a bone relative to its rest pose."""
        b = self.arm.data.bones[name]
        qp = self.world_delta(b.parent.name) if b.parent else Quaternion()
        B = b.matrix_local.to_3x3()
        R = self.rot.get(name, Quaternion()).to_matrix()
        return qp @ (B @ R @ B.inverted()).to_quaternion()

    def set_dir(self, name, target_dir):
        """Point a bone along a world direction, taking the parents' current pose
        into account (proper FK chain aiming)."""
        b = self.arm.data.bones[name]
        d = (b.tail_local - b.head_local).normalized()
        qc = d.rotation_difference(Vector(target_dir).normalized())
        qp = self.world_delta(b.parent.name) if b.parent else Quaternion()
        B = b.matrix_local.to_3x3()
        M = B.inverted() @ (qp.inverted() @ qc).to_matrix() @ B
        self.rot[name] = M.to_quaternion()

    def move(self, name, world_vec):
        loc = self._R(name).inverted() @ Vector(world_vec)
        self.loc[name] = self.loc.get(name, Vector()) + loc

    def apply(self, frame):
        for pb in self.arm.pose.bones:
            pb.rotation_quaternion = self.rot.get(pb.name, Quaternion())
            pb.location = self.loc.get(pb.name, Vector())
            pb.keyframe_insert('rotation_quaternion', frame=frame, group=pb.name)
            pb.keyframe_insert('location', frame=frame, group=pb.name)


SIDES = (('_L', 1), ('_R', -1))
TAILS = [s[0] for s in kg.TAIL_SPECS]
NB = kg.TAIL_NB
AX = (1, 0, 0)   # +angle about world X: tops tip forward (-Y), feet swing back (+Y)
ZAX = (0, 0, 1)
EYE_N = {1: kg.norm(kg.v3(0.42, -0.46, 0.78)), -1: kg.norm(kg.v3(-0.42, -0.46, 0.78))}


def tail_tip_side(i):
    """-1 / 0 / +1: which side of the fan a tail sits on (for fanning in / out)."""
    x = kg.tuned_specs()[i][1][0]
    return 0 if abs(x) < 0.1 else (1 if x > 0 else -1)


def tail_wave(P, p, amp, freq=1, lag=0.75, spread=0.85, side_amp=None, harm=0.25):
    """Majestic flowing tails: a wave travels from the base to the tip of every
    tail (later bones lag behind and swing wider), each tail offset in phase so
    the fan ripples like flames.  A second harmonic keeps it from looking
    mechanical.  Integer freq keeps the loop seamless."""
    side_amp = amp * 1.15 if side_amp is None else side_amp
    for i, tn in enumerate(TAILS):
        ph = i * spread
        for k in range(NB):
            w = 0.45 + 0.55 * k / (NB - 1)                       # tips swing wider
            q = freq * p - lag * k - ph
            P.local(f'{tn}_{k + 1}', (1, 0, 0), amp * w * (math.sin(q) + harm * math.sin(2 * q + 0.7)))
            P.local(f'{tn}_{k + 1}', (0, 0, 1),
                    side_amp * w * (math.sin(q * 1.0 - ph * 0.3 + 1.1) + harm * math.sin(2 * q + 2.1)))


def tail_fan(P, ang):
    """Spread (ang > 0) or gather (ang < 0) the whole fan around the tail root."""
    for i, tn in enumerate(TAILS):
        sd = tail_tip_side(i)
        if sd:
            P.world(f'{tn}_1', ZAX, -sd * ang)
            P.world(f'{tn}_1', (0, 1, 0), sd * ang * 0.6)
        else:
            P.world(f'{tn}_1', AX, -ang * 0.8)


# -------------------------------------------------------------- animations
def pose_idle(arm, f, N):
    P = Pose(arm)
    p = 2 * math.pi * f / N
    s = S()
    br = math.sin(2 * p)                                  # two breaths per loop
    P.world('Spine', AX, -0.012 * br)
    P.world('Chest', AX, 0.018 * br)
    P.move('Chest', (0, 0, 0.006 * s * br))
    P.world('Neck1', AX, 0.03 * math.sin(p + 0.6))
    P.world('Head', ZAX, 0.12 * math.sin(p))             # slow look around
    P.world('Head', AX, 0.04 * math.sin(2 * p + 1.0))
    P.world('Neck2', ZAX, 0.05 * math.sin(p - 0.4))
    # ear flicks
    t = f / N
    for sfx, sx in SIDES:
        flick = math.exp(-((t - (0.30 if sx > 0 else 0.72)) / 0.025) ** 2)
        P.world('Ear' + sfx, (0, 1, 0), -sx * 0.25 * flick)
        P.world('Tassel' + sfx, AX, 0.05 * math.sin(p + 0.5 * sx))
        P.world('Tassel' + sfx, (0, 1, 0), 0.03 * math.sin(2 * p + sx))
    # tails: the fan slowly lifts and spreads, then settles, while every tail
    # carries its own travelling wave
    P.world('TailBase', AX, -0.05 - 0.05 * math.sin(p))
    tail_fan(P, 0.07 + 0.07 * math.sin(p + 0.4))
    for tn in ('Tail6', 'Tail7', 'Tail8'):               # lower tails clear the ground
        P.world(f'{tn}_1', AX, -0.12)
    tail_wave(P, p, 0.11, freq=1, lag=0.80, spread=0.85)
    P.world('Hips', (0, 1, 0), 0.01 * math.sin(p))
    return P


def pose_run(arm, f, N):
    P = Pose(arm)
    p = 2 * math.pi * f / N
    # rotary gallop phase offsets (fraction of the stride)
    ph = {'HindLeg_L': 0.00, 'HindLeg_R': 0.10, 'FrontLeg_L': 0.46, 'FrontLeg_R': 0.56}
    for sfx, sx in SIDES:
        q = p - 2 * math.pi * ph['FrontLeg' + sfx]
        fwd = math.cos(q)                     # +1 = reaching forward
        lift = max(0.0, -math.sin(q))         # swing phase (leg travelling forward)
        P.world('FrontLegUpper' + sfx, AX, -0.50 * fwd)
        P.world('FrontLegLower' + sfx, AX, 1.05 * lift ** 1.3 - 0.10 * fwd)
        P.world('FrontPaw' + sfx, AX, 0.65 * lift + 0.15 * max(0, fwd))
        q = p - 2 * math.pi * ph['HindLeg' + sfx]
        fwd = math.cos(q)
        lift = max(0.0, -math.sin(q))
        P.world('HindLegUpper' + sfx, AX, -0.48 * fwd)
        P.world('HindLegLower' + sfx, AX, 0.55 * lift - 0.08 * fwd)
        P.world('HindFoot' + sfx, AX, -0.65 * lift - 0.15 * max(0, -fwd))
        P.world('HindPaw' + sfx, AX, 0.35 * lift)
        P.world('Ear' + sfx, AX, -0.55)                                 # ears pinned back
        P.world('Tassel' + sfx, AX, 0.55 + 0.25 * math.sin(p + 0.8))    # tassels fly back
        P.world('Tassel' + sfx, (0, 1, 0), 0.12 * sx * math.sin(p))
    # spine flexion / extension, body bob, head counter-motion
    flex = math.sin(p - 0.6)
    P.world('Hips', AX, 0.13 * flex)
    P.world('Chest', AX, -0.10 * flex)
    P.world('Spine', AX, 0.04 * flex)
    P.world('Root', AX, 0.05 * math.sin(p - 0.3))
    P.world('Neck1', AX, 0.30 + 0.06 * math.sin(p + 1.2))
    P.world('Neck2', AX, 0.12)
    P.world('Head', AX, -0.34 - 0.07 * math.sin(p + 1.2))
    # tails stream out behind like banners: the fan sweeps back and rises a
    # little, stays spread, and long waves roll down every tail
    P.world('TailBase', AX, 0.06 + 0.04 * math.sin(p - 1.0))
    for tn in TAILS:
        P.toward(f'{tn}_1', (0, 1, 0.05), 0.40)
    tail_fan(P, 0.10)
    tail_wave(P, p, 0.13, freq=1, lag=1.05, spread=0.55, side_amp=0.10, harm=0.15)
    return P


def pose_sleep(arm, f, N):
    """Curled up like a sleeping fox (reference): lying flat, legs tucked under,
    chin resting on the ground, eyes closed, the tails swept round the left side
    so the tips lie beside the face.  Slow breathing, a sleepy tail-tip twitch."""
    P = Pose(arm)
    p = 2 * math.pi * f / N
    s = S()
    br = math.sin(2 * p)                     # two slow breaths per loop (5 s)
    P.move('Root', (0, 0, -0.46 * s))
    # body: flat on the belly, gently curved toward the tails (left)
    P.world('Hips', ZAX, -0.22)                           # body curls into a C toward the left
    P.world('Spine', ZAX, 0.30)
    P.world('Chest', ZAX, 0.30)
    P.world('Spine', AX, -0.015 * br)
    P.world('Chest', AX, 0.025 * br)
    P.move('Chest', (0, 0, 0.007 * s * br))
    for sfx, sx in SIDES:
        # legs rest ON the ground, clear of the body (folding them under made
        # them disappear into the belly): front legs stretched forward under
        # the chin, hind legs folded beside the haunches like a resting fox
        P.set_dir('FrontLegUpper' + sfx, (sx * 0.14, -0.82, -0.55))
        P.set_dir('FrontLegLower' + sfx, (sx * 0.04, -0.99, -0.06))
        P.set_dir('FrontPaw' + sfx, (0.0, -0.99, -0.04))
        P.set_dir('HindLegUpper' + sfx, (sx * 0.68, -0.55, -0.42))
        P.set_dir('HindLegLower' + sfx, (sx * 0.35, 0.93, -0.08))
        P.set_dir('HindFoot' + sfx, (sx * 0.22, -0.97, -0.06))
        P.set_dir('HindPaw' + sfx, (sx * 0.10, -0.99, -0.03))
        # ears relaxed back, eyes closed (lens sinks into the socket)
        P.world('Ear' + sfx, AX, -0.40)
        P.world('Ear' + sfx, (0, 1, 0), -0.20 * sx)
        P.move('Eye' + sfx, tuple(-EYE_N[sx] * 0.040 * s))
        P.world('Tassel' + sfx, (0, 1, 0), 0.9 * sx)        # tassels resting on the ground
    # head: neck lowered, chin on the ground, turned a little toward the tails
    P.world('Neck1', AX, 0.85)
    P.world('Neck2', AX, 0.40 + 0.012 * br)
    P.world('Neck1', ZAX, 0.38)
    P.world('Head', AX, -0.85)
    P.world('Head', ZAX, 0.35)
    P.world('Head', (0, 1, 0), 0.10)
    # tails: one fluffy blanket swept round the LEFT side toward the head, lying
    # on the ground.  Every bone is steered along an explicit curled path
    # (heading 0 = straight back, 90 = left side, 180 = toward the head).
    order = [6, 3, 7, 1, 0, 2, 4, 5]                      # bottom of the stack -> top
    for rank, i in enumerate(order):
        tn = TAILS[i]
        h0 = 50 + rank * 4.0                               # first bone: back-left
        dh = 60 - rank * 1.5                               # extra curl per bone (tips fan by the face)
        for k in range(NB):
            hd = math.radians(h0 + dh * k)
            pitch = -0.55 if k == 0 else (0.06 if k == 1 else 0.0) + 0.025 * (rank % 4)
            d = (math.sin(hd) * math.cos(pitch), math.cos(hd) * math.cos(pitch), math.sin(pitch))
            P.set_dir(f'{tn}_{k + 1}', d)
        twitch = 0.05 * math.sin(p - rank * 0.6)          # sleepy tip twitch
        P.local(f'{tn}_{NB}', (0, 0, 1), twitch)
    return P


ANIMS = {
    'Kitsune_Idle': (pose_idle, 120),
    'Kitsune_Sleep': (pose_sleep, 150),
    'Kitsune_Run': (pose_run, 20),
}


FOOT_BONES = ('FrontPaw_L', 'FrontPaw_R', 'HindPaw_L', 'HindPaw_R')


def foot_mask(ob):
    """Vertices that must touch the ground when standing / running (paws + claws)."""
    gi = {ob.vertex_groups[n].index for n in FOOT_BONES if n in ob.vertex_groups}
    return np.array([any(e.group in gi and e.weight > 0.5 for e in v.groups) for v in ob.data.vertices])


def eval_min_z(arm, ob, frame, mask=None):
    bpy.context.scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    oe.to_mesh_clear()
    z = co.reshape(-1, 3)[:, 2]
    return (z[mask] if mask is not None else z).min()


def bake_action(arm, ob, name, fn, N, ground=True, per_frame=False, hop=None, mask=None):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data_create()
    arm.animation_data.action = act
    # optional ground correction: measure the pose, then shift Root so the
    # lowest point over the loop touches the ground
    offset = 0.0
    if per_frame:
        offs = []
        for f in range(N + 1):
            fn(arm, f, N).apply(f)
        for f in range(N + 1):
            offs.append(-eval_min_z(arm, ob, f, mask))
        offs = np.array(offs)
        offs[-1] = offs[0]
        # light smoothing keeps contact without jitter; optional airborne hop
        sm = (np.roll(offs[:-1], 1) + 2 * offs[:-1] + np.roll(offs[:-1], -1)) / 4
        offs = np.r_[sm, sm[0]]
        for fc in list(act.fcurves):
            act.fcurves.remove(fc)
        for f in range(N + 1):
            P = fn(arm, f, N)
            P.move('Root', (0, 0, offs[f] + (hop(f, N) if hop else 0.0)))
            P.apply(f)
        for fc in act.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
        act.frame_range = (0, N)
        return act, float(offs.mean())
    if ground:
        mins = []
        for f in range(0, N + 1, 3):
            fn(arm, f, N).apply(f)
        for f in range(0, N + 1, 3):
            mins.append(eval_min_z(arm, ob, f, mask))
        offset = -min(mins)
        for fc in list(act.fcurves):
            act.fcurves.remove(fc)
    for f in range(N + 1):
        P = fn(arm, f, N)
        if offset:
            P.move('Root', (0, 0, offset))
        P.apply(f)
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    act.frame_range = (0, N)
    act['loop'] = True
    return act, offset


def build_actions(arm, ob):
    sc = bpy.context.scene
    sc.render.fps = FPS
    info = {}
    s = S()
    hop = lambda f, N: s * 0.05 * max(0.0, math.sin(2 * math.pi * f / N - 2.2)) ** 2   # suspension phase
    feet = foot_mask(ob)
    for name, (fn, N) in ANIMS.items():
        if name == 'Kitsune_Run':
            act, off = bake_action(arm, ob, name, fn, N, per_frame=True, hop=hop, mask=feet)
        elif name == 'Kitsune_Idle':
            act, off = bake_action(arm, ob, name, fn, N, ground=True, mask=feet)
        else:                                   # sleeping: the body itself rests on the ground
            act, off = bake_action(arm, ob, name, fn, N, ground=True)
        info[name] = dict(frames=N, seconds=N / FPS, ground_offset=off)
        print('ACTION', name, N, 'frames, ground offset', round(off, 4))
    # NLA: one muted track per action so the .blend shows all three
    arm.animation_data.action = None
    for name in ANIMS:
        tr = arm.animation_data.nla_tracks.new()
        tr.name = name
        tr.strips.new(name, 0, bpy.data.actions[name])
        tr.mute = True
    arm.animation_data.action = bpy.data.actions['Kitsune_Idle']
    sc.frame_start, sc.frame_end = 0, 120
    return info


# -------------------------------------------------------------- exports
def fbx(path, objs, anim, actions_all=False):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH'},
        apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y',
        bake_space_transform=False, use_mesh_modifiers=True, mesh_smooth_type='FACE',
        use_tspace=True, add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
        use_armature_deform_only=True, armature_nodetype='NULL',
        bake_anim=anim, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=actions_all, bake_anim_force_startend_keying=True,
        bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
        path_mode='COPY' if not anim else 'STRIP', embed_textures=not anim)


def finalize_and_export(arm, ob, out, md):
    import json
    import build_kitsune as bk
    sc = bpy.context.scene
    ob.data.name = 'Kitsune_Mesh'
    # rest pose for the model FBX
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = Vector()
    sc.frame_set(0)
    os.makedirs(os.path.join(out, 'Animations'), exist_ok=True)
    # tracks muted -> FBX exporter should not pick them up
    fbx(os.path.join(out, 'Kitsune.fbx'), [arm, ob], anim=False)
    for name in ANIMS:
        arm.animation_data.action = bpy.data.actions[name]
        sc.frame_start, sc.frame_end = 0, ANIMS[name][1]
        fbx(os.path.join(out, 'Animations', name + '.fbx'), [arm, ob], anim=True)
    arm.animation_data.action = bpy.data.actions['Kitsune_Idle']
    sc.frame_start, sc.frame_end = 0, 120
    for img in bpy.data.images:
        if img.filepath:
            img.pack()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, 'Kitsune.blend'), compress=True)
