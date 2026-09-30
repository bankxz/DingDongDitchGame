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
def bone_specs():
    g = kg
    b = []   # (name, head, tail, parent, connected)
    b.append(('Root', (0, 0, 0), (0, -0.3, 0), None, False))
    b.append(('Hips', (0, 0.58, 0.845), (0, 0.30, 0.835), 'Root', False))
    b.append(('Spine', (0, 0.30, 0.835), (0, 0.02, 0.84), 'Hips', True))
    b.append(('Chest', (0, 0.02, 0.84), (0, -0.20, 0.88), 'Spine', True))
    b.append(('Neck1', (0, -0.18, 0.93), (0, -0.28, 1.10), 'Chest', False))
    b.append(('Neck2', (0, -0.28, 1.10), (0, -0.35, 1.30), 'Neck1', True))
    b.append(('Head', (0, -0.35, 1.38), (0, -0.64, 1.30), 'Neck2', False))
    for sx, sfx in ((1, '_L'), (-1, '_R')):
        m = lambda p: kg.mx(p, sx)
        b.append(('Ear' + sfx, m(g.EAR_BASE), m(g.EAR_TIP), 'Head', False))
        fl, hl = [m(p) for p in g.FRONT_LEG], [m(p) for p in g.HIND_LEG]
        b.append(('FrontLegUpper' + sfx, fl[0], fl[1], 'Chest', False))
        b.append(('FrontLegLower' + sfx, fl[1], fl[2], 'FrontLegUpper' + sfx, True))
        b.append(('FrontPaw' + sfx, fl[2], m(g.FRONT_PAW[2]), 'FrontLegLower' + sfx, True))
        b.append(('HindLegUpper' + sfx, hl[0], hl[1], 'Hips', False))
        b.append(('HindLegLower' + sfx, hl[1], hl[2], 'HindLegUpper' + sfx, True))
        b.append(('HindFoot' + sfx, hl[2], hl[3], 'HindLegLower' + sfx, True))
        b.append(('HindPaw' + sfx, hl[3], m(g.HIND_PAW[2]), 'HindFoot' + sfx, True))
        t = m(g.TASSEL_TOP)
        b.append(('Tassel' + sfx, t, t + kg.v3(0, 0, -0.40), 'Chest', False))
    b.append(('TailBase', g.TAIL_BASE, g.TAIL_BASE + kg.v3(0, 0.14, 0.05), 'Hips', False))
    for spec in g.TAIL_SPECS:
        pts = g.tail_bone_points(spec)
        par = 'TailBase'
        for k in range(3):
            nm = f'{spec[0]}_{k + 1}'
            b.append((nm, pts[k], pts[k + 1], par, k > 0))
            par = nm
    return b


def build_rig(ob, md):
    arm_data = bpy.data.armatures.new('Kitsune_Armature')
    arm = bpy.data.objects.new('Kitsune_Rig', arm_data)
    bpy.context.scene.collection.objects.link(arm)
    arm_data.display_type = 'STICK'
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.view_layer.objects:
        o.select_set(o == arm)
    bpy.ops.object.mode_set(mode='EDIT')
    X = Vector((1, 0, 0))
    specs = bone_specs()
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

    # skin weights (max 4 influences, normalised)
    names = {s[0] for s in specs}
    groups = {n: ob.vertex_groups.new(name=n) for n in [s[0] for s in specs]}
    for vi, w in enumerate(md.weights):
        items = sorted(((k, v) for k, v in w.items() if v > 1e-4), key=lambda kv: -kv[1])[:4]
        tot = sum(v for _, v in items)
        for k, v in items:
            assert k in names, k
            groups[k].add([vi], v / tot, 'REPLACE')
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
AX = (1, 0, 0)   # +angle about world X: tops tip forward (-Y), feet swing back (+Y)


def tail_sway(P, p, amp, freq=1, lag=0.75, spread=0.9, side_amp=None):
    side_amp = amp * 1.2 if side_amp is None else side_amp
    for i, tn in enumerate(TAILS):
        ph = i * spread
        for k in range(3):
            a = amp * (0.6 + 0.4 * k)
            P.local(f'{tn}_{k + 1}', (1, 0, 0), a * math.sin(freq * p - lag * k - ph))
            P.local(f'{tn}_{k + 1}', (0, 0, 1), side_amp * (0.6 + 0.4 * k) * math.sin(freq * p - lag * k - ph * 1.3 + 1.1))


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
    P.world('Head', (0, 0, 1), 0.12 * math.sin(p))       # slow look around
    P.world('Head', AX, 0.04 * math.sin(2 * p + 1.0))
    P.world('Neck2', (0, 0, 1), 0.05 * math.sin(p - 0.4))
    # ear flicks
    t = f / N
    for sfx, sx in SIDES:
        flick = math.exp(-((t - (0.30 if sx > 0 else 0.72)) / 0.025) ** 2)
        P.world('Ear' + sfx, (0, 1, 0), -sx * 0.25 * flick)
        P.world('Tassel' + sfx, AX, 0.05 * math.sin(p + 0.5 * sx))
        P.world('Tassel' + sfx, (0, 1, 0), 0.03 * math.sin(2 * p + sx))
    P.world('TailBase', AX, 0.03 * math.sin(p))
    tail_sway(P, p, 0.07)
    P.world('Hips', (0, 1, 0), 0.01 * math.sin(p))
    return P


def pose_run(arm, f, N):
    P = Pose(arm)
    p = 2 * math.pi * f / N
    s = S()
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
    # tails stream behind: fan collapses toward +Y and lowers, with flowing waves
    P.world('TailBase', AX, 0.10)
    for i, tn in enumerate(kg.TAIL_SPECS):
        P.toward(f'{tn[0]}_1', (0, 1, -0.15), 0.42)
    tail_sway(P, p, 0.11, freq=1, lag=0.9, spread=0.7, side_amp=0.08)
    return P


def pose_sleep(arm, f, N):
    P = Pose(arm)
    p = 2 * math.pi * f / N
    s = S()
    br = math.sin(2 * p)                     # two slow breaths per loop (5 s)
    P.move('Root', (0, 0, -0.50 * s))
    # body curls slightly to the left, chest breathes
    P.world('Hips', (0, 0, 1), -0.10)
    P.world('Chest', (0, 0, 1), 0.14)
    P.world('Spine', AX, -0.02 * br)
    P.world('Chest', AX, 0.03 * br)
    P.move('Chest', (0, 0, 0.008 * s * br))
    # front legs: sphinx pose - elbows back on the ground, forearms forward
    for sfx, sx in SIDES:
        P.world('FrontLegUpper' + sfx, AX, 0.55)
        P.world('FrontLegLower' + sfx, AX, -2.05 + 0.04 * sx)
        P.world('FrontPaw' + sfx, AX, 0.45)
        # hind legs folded under the body
        P.world('HindLegUpper' + sfx, AX, -0.95)
        P.world('HindLegUpper' + sfx, (0, 1, 0), 0.25 * sx)
        P.world('HindLegLower' + sfx, AX, 1.75)
        P.world('HindFoot' + sfx, AX, -1.25)
        P.world('HindPaw' + sfx, AX, 0.35)
        P.world('Ear' + sfx, AX, -0.35)                     # relaxed, laid back
        P.world('Ear' + sfx, (0, 1, 0), -0.25 * sx)
        P.world('Tassel' + sfx, (0, 1, 0), 0.9 * sx)         # tassels resting on the ground
    # head down, chin resting on the front paws, turned toward the curl
    P.world('Neck1', AX, 0.70)
    P.world('Neck2', AX, 0.35 + 0.015 * br)
    P.world('Neck1', (0, 0, 1), 0.18)
    P.world('Head', AX, -0.70)
    P.world('Head', (0, 0, 1), 0.15)
    # tails: lowered fan draped around the body and swept forward on the left side
    order = [3, 1, 5, 0, 7, 2, 4, 6]            # stacking order around the body
    for rank, i in enumerate(order):
        tn = kg.TAIL_SPECS[i][0]
        beta = math.radians(-25 + rank * 22)     # 0 = straight back, 90 = creature's left side
        tgt = (math.sin(beta) * 1.0, math.cos(beta), 0.10 + 0.07 * (rank % 3))
        P.aim(f'{tn}_1', tgt, 1.0)
        P.world(f'{tn}_2', (0, 0, 1), 0.28)      # curl toward the head
        P.world(f'{tn}_3', (0, 0, 1), 0.32)
    tail_sway(P, p, 0.025, freq=1, lag=0.8, spread=1.1, side_amp=0.02)
    return P


ANIMS = {
    'Kitsune_Idle': (pose_idle, 120),
    'Kitsune_Sleep': (pose_sleep, 150),
    'Kitsune_Run': (pose_run, 20),
}


def eval_min_z(arm, ob, frame):
    bpy.context.scene.frame_set(frame)
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    oe.to_mesh_clear()
    return co.reshape(-1, 3)[:, 2].min()


def bake_action(arm, ob, name, fn, N, ground=True, per_frame=False, hop=None):
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
            offs.append(-eval_min_z(arm, ob, f))
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
            mins.append(eval_min_z(arm, ob, f))
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
    for name, (fn, N) in ANIMS.items():
        if name == 'Kitsune_Run':
            act, off = bake_action(arm, ob, name, fn, N, per_frame=True, hop=hop)
        else:
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
