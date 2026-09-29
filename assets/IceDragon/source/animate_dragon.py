# Executed from build_dragon.py (shares its globals: bpy, arm, BONES, V, math ...).
# Creates two looping actions on the rig: "Idle" (90 f) and "Walk" (40 f, in place), 30 fps.
from mathutils import Matrix, Quaternion

scene.render.fps = 30
DEFORM = list(BONES.keys())

def reset_pose():
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)

def world_rot(name, axis, deg):
    """Quaternion that rotates bone `name` about an armature-space axis."""
    R = arm.data.bones[name].matrix_local.to_3x3()
    q = Matrix.Rotation(math.radians(deg), 3, V(axis)).to_quaternion()
    return (R.inverted() @ q.to_matrix() @ R).to_quaternion()

def world_loc(name, delta):
    return arm.data.bones[name].matrix_local.to_3x3().inverted() @ V(delta)

def set_rot(name, *rots):
    q = Quaternion()
    for axis, deg in rots:
        q = world_rot(name, axis, deg) @ q
    arm.pose.bones[name].rotation_quaternion = q

def key_all(frame, names):
    for n in names:
        pb = arm.pose.bones[n]
        pb.keyframe_insert('location', frame=frame, group=n)
        pb.keyframe_insert('rotation_quaternion', frame=frame, group=n)

def new_action(name):
    if arm.animation_data is None: arm.animation_data_create()
    act = bpy.data.actions.new(name); act.use_fake_user = True
    arm.animation_data.action = act
    return act

S = lambda f, n, ph=0.0: math.sin(2 * math.pi * (f / n + ph))

def neck_side(k): return {'C': 0.0, 'L': 1.0, 'R': -1.0}[k]

# ---------------------------------------------------------------- IDLE ----
def pose_idle(f, N=90):
    b = S(f, N)
    arm.pose.bones['Torso'].location = world_loc('Torso', (0, 0, 0.07 * b))
    set_rot('Torso', ((1, 0, 0), 1.2 * b))
    set_rot('Pelvis', ((1, 0, 0), -0.8 * b))
    for k in 'CLR':
        ph = {'C': 0.0, 'L': 0.18, 'R': 0.36}[k]; sd = neck_side(k)
        for i in (1, 2, 3):
            set_rot(f'Neck{k}{i}', ((1, 0, 0), 2.5 * S(f, N, ph + 0.05 * i)), ((0, 0, 1), 3.0 * S(f, N, ph + 0.25) + 1.5 * sd * S(f, N / 2, ph)))
        set_rot(f'Head{k}', ((1, 0, 0), -4.0 * S(f, N, ph + 0.15)), ((0, 0, 1), -3.0 * S(f, N, ph + 0.3)))
        snap = max(0.0, S(f, N, ph + 0.6)) ** 6          # one jaw snap per loop
        jaw_axis = arm.data.bones[f'Head{k}'].matrix_local.to_3x3() @ V((1, 0, 0))
        set_rot(f'Jaw{k}', (jaw_axis, 4.0 * S(f, N, ph) - 10.0 * snap))
    for side, sg in (('L', 1), ('R', -1)):
        set_rot(f'Wing1.{side}', ((0, 1, 0), -sg * 5.0 * S(f, N, 0.1)), ((1, 0, 0), 2.0 * S(f, N, 0.1)))
        set_rot(f'Wing2.{side}', ((0, 1, 0), -sg * 4.0 * S(f, N, 0.2)))
        set_rot(f'Wing3.{side}', ((0, 1, 0), -sg * 5.0 * S(f, N, 0.3)))
    for i in range(1, 6):
        set_rot(f'Tail{i}', ((0, 0, 1), (3.0 + 1.5 * i) * S(f, N, -0.08 * i)), ((1, 0, 0), 1.5 * S(f, N, 0.1 - 0.05 * i)))

bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='POSE')

# ---------------------------------------------------------------- WALK ----
# Legs are solved with temporary IK bones, then baked to plain FK keys.
bpy.ops.object.mode_set(mode='EDIT')
LEGS = {  # leg: (upper, lower, foot, phase)
    'HL': ('Thigh.L', 'Shin.L', 'Foot.L', 0.00),
    'FL': ('UpperArm.L', 'Forearm.L', 'Hand.L', 0.25),
    'HR': ('Thigh.R', 'Shin.R', 'Foot.R', 0.50),
    'FR': ('UpperArm.R', 'Forearm.R', 'Hand.R', 0.75),
}
for leg, (up, lo, ft, ph) in LEGS.items():
    src = arm.data.edit_bones[ft]
    eb = arm.data.edit_bones.new('IK_' + leg); eb.head = src.head; eb.tail = src.tail; eb.roll = src.roll
    eb.parent = arm.data.edit_bones['Root']; eb.use_deform = False
bpy.ops.object.mode_set(mode='POSE')
for leg, (up, lo, ft, ph) in LEGS.items():
    c = arm.pose.bones[lo].constraints.new('IK'); c.target = arm; c.subtarget = 'IK_' + leg; c.chain_count = 2
    c.use_tail = True    # lower bone's tail (ankle == foot head) reaches the target
    c2 = arm.pose.bones[ft].constraints.new('COPY_ROTATION'); c2.target = arm; c2.subtarget = 'IK_' + leg
# IK aims the lower bone's tail at the target head; foot head == lower tail, good.

N = 40; STRIDE = 1.7; LIFT = 0.55; DUTY = 0.62
def foot_offset(p):
    """returns (dy, dz) in world space for gait phase p in [0,1)."""
    if p < DUTY:                                   # stance: slide back (ground moves +Y)
        t = p / DUTY
        return (-STRIDE / 2 + STRIDE * t, 0.0)
    t = (p - DUTY) / (1 - DUTY)                    # swing: return forward, lifted
    e = 0.5 - 0.5 * math.cos(math.pi * t)
    return (STRIDE / 2 - STRIDE * e, LIFT * math.sin(math.pi * t))

ALL = DEFORM + ['IK_' + l for l in LEGS]
def pose_walk(f, N=40):
    for leg, (up, lo, ft, ph) in LEGS.items():
        p = ((f / N) + ph) % 1.0
        dy, dz = foot_offset(p)
        arm.pose.bones['IK_' + leg].location = world_loc('IK_' + leg, (0, dy, dz))
        tilt = 18.0 * math.sin(math.pi * (p - DUTY) / (1 - DUTY)) if p >= DUTY else 0.0
        set_rot('IK_' + leg, ((1, 0, 0), -tilt))
    b2 = S(f, N / 2)
    arm.pose.bones['Torso'].location = world_loc('Torso', (0.05 * S(f, N), 0, 0.09 * b2 - 0.05))
    set_rot('Torso', ((0, 1, 0), 2.0 * S(f, N)), ((0, 0, 1), 2.0 * S(f, N, 0.25)))
    set_rot('Pelvis', ((0, 1, 0), -2.5 * S(f, N, 0.5)), ((0, 0, 1), -3.0 * S(f, N, 0.25)))
    for k in 'CLR':
        ph = {'C': 0.0, 'L': 0.12, 'R': 0.24}[k]
        for i in (1, 2, 3):
            set_rot(f'Neck{k}{i}', ((1, 0, 0), 3.0 * S(f, N / 2, ph + 0.1 * i)), ((0, 0, 1), 2.5 * S(f, N, ph + 0.3)))
        set_rot(f'Head{k}', ((1, 0, 0), -6.0 * S(f, N / 2, ph + 0.3)))
        jaw_axis = arm.data.bones[f'Head{k}'].matrix_local.to_3x3() @ V((1, 0, 0))
        set_rot(f'Jaw{k}', (jaw_axis, 3.0 * S(f, N / 2, ph)))
    for side, sg in (('L', 1), ('R', -1)):
        set_rot(f'Wing1.{side}', ((0, 1, 0), -sg * 6.0 * S(f, N / 2, 0.1)), ((0, 0, 1), sg * 3.0 * S(f, N)))
        set_rot(f'Wing2.{side}', ((0, 1, 0), -sg * 5.0 * S(f, N / 2, 0.2)))
        set_rot(f'Wing3.{side}', ((0, 1, 0), -sg * 6.0 * S(f, N / 2, 0.3)))
    for i in range(1, 6):
        set_rot(f'Tail{i}', ((0, 0, 1), (4.0 + 2.0 * i) * S(f, N, 0.15 - 0.08 * i)), ((1, 0, 0), 2.0 * S(f, N / 2, -0.06 * i)))

# sample both clips with IK active (idle keeps IK targets at rest => planted feet)
baked = {}
for name, n, fn in (('Idle', 90, pose_idle), ('Walk', 40, pose_walk)):
    src = new_action(name + 'Src')
    for f in range(0, n + 1):
        reset_pose(); fn(f, n); key_all(f, ALL)
    baked[name] = {}
    for f in range(0, n + 1):
        scene.frame_set(f); bpy.context.view_layer.update()
        baked[name][f] = {b: arm.pose.bones[b].matrix.copy() for b in DEFORM}
    arm.animation_data.action = None
    bpy.data.actions.remove(src)

# bake: rebuild FK keys from the sampled armature-space matrices
for leg, (up, lo, ft, ph) in LEGS.items():
    for pb in (arm.pose.bones[lo], arm.pose.bones[ft]):
        for c in list(pb.constraints): pb.constraints.remove(c)
bpy.ops.object.mode_set(mode='EDIT')
for leg in LEGS:
    arm.data.edit_bones.remove(arm.data.edit_bones['IK_' + leg])
bpy.ops.object.mode_set(mode='POSE')
acts = {}
for name, n in (('Idle', 90), ('Walk', 40)):
    act = acts[name] = new_action(name)
    reset_pose()
    for f in range(0, n + 1, 1 if name == 'Walk' else 2):
        for bn in DEFORM:
            bone_ = arm.data.bones[bn]; P = baked[name][f][bn]
            if bone_.parent:
                basis = bone_.matrix_local.inverted() @ bone_.parent.matrix_local @ baked[name][f][bone_.parent.name].inverted() @ P
            else:
                basis = bone_.matrix_local.inverted() @ P
            loc, rot, _ = basis.decompose()
            pb = arm.pose.bones[bn]; pb.location = loc; pb.rotation_quaternion = rot
        key_all(f, DEFORM)
idle, walk = acts['Idle'], acts['Walk']

# looping: keep keys linear-ish smooth, make sure the actions have their ranges set
for act, n in ((idle, 90), (walk, 40)):
    act.frame_range = (0, n); act.use_frame_range = True; act.use_cyclic = True
reset_pose()
arm.animation_data.action = idle
bpy.ops.object.mode_set(mode='OBJECT')
scene.frame_start = 0; scene.frame_end = 90
print('ANIM idle keys', len(idle.fcurves), 'walk keys', len(walk.fcurves))
