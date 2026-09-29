# Stage 2: armature, skin weights, Idle + Walk actions, and Roblox-ready exports.
# Rest pose = neutral square stance (the quadruped equivalent of a T-pose): legs straight and
# vertical, left/right symmetric, head/neck/tail in a relaxed neutral line.
import sys, os, bpy, math
from mathutils import Vector, Quaternion, Matrix, Euler

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
FPS = 30
IDLE_LEN = 120      # 4.0 s loop
WALK_LEN = 32       # ~1.07 s loop (one full stride)

bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'src', 'LavaHorse_stage1.blend'))
sc = bpy.context.scene
sc.render.fps = FPS
horse = bpy.data.objects['LavaHorse']

# ------------------------------------------------------------------ armature
sys.path.insert(0, os.path.dirname(__file__))
from build_geo import remap_z, HEAD_SCALE, HEAD_PIVOT   # same transforms the mesh was built with
HEAD_BONES = {'Head', 'Ear.L', 'Ear.R'}

LX = 1.15
BONES = [  # name, head, tail, parent   (authored coordinates; remapped below)
    ('Root', (0, 0, 0), (0, 0, 1.0), None),
    ('Torso', (0, 0.2, 3.0), (0, 0.2, 3.8), 'Root'),
    ('Chest', (0, -0.6, 3.0), (0, -2.2, 3.2), 'Torso'),
    ('Hips', (0, 0.8, 3.0), (0, 2.6, 3.2), 'Torso'),
    ('Neck', (0, -2.3, 3.6), (0, -2.95, 5.0), 'Chest'),
    ('Head', (0, -2.95, 5.0), (0, -4.8, 4.3), 'Neck'),
    ('Tail1', (0, 2.9, 3.85), (0, 4.2, 3.7), 'Hips'),
    ('Tail2', (0, 4.2, 3.7), (0, 5.4, 2.2), 'Tail1'),
]
for s, side in ((1, 'L'), (-1, 'R')):
    x = s * LX
    BONES += [
        ('Ear.' + side, (s * 0.45, -3.3, 5.62), (s * 0.48, -3.38, 6.42), 'Head'),
        ('FrontUpper.' + side, (x, -1.9, 3.3), (x, -1.9, 1.87), 'Chest'),
        ('FrontLower.' + side, (x, -1.9, 1.87), (x, -1.9, 0.86), 'FrontUpper.' + side),
        ('FrontHoof.' + side, (x, -1.9, 0.86), (x, -1.9, 0.05), 'FrontLower.' + side),
        ('HindUpper.' + side, (x, 2.5, 3.3), (x, 2.72, 1.9), 'Hips'),
        ('HindLower.' + side, (x, 2.72, 1.9), (x, 2.86, 0.86), 'HindUpper.' + side),
        ('HindHoof.' + side, (x, 2.86, 0.86), (x, 2.88, 0.05), 'HindLower.' + side),
    ]
RIGID_BONES = {'Tail2'}   # the tail tip dips below the leg band but belongs to a rigid part


def rz(p, name):
    if name in HEAD_BONES:
        p = tuple(HEAD_PIVOT + (Vector(p) - HEAD_PIVOT) * HEAD_SCALE)
    x, y, z = p
    if name in RIGID_BONES:
        return (x, y, z + (remap_z(3.7) - 3.7))
    return (x, y, remap_z(z))


BONES = [(n, rz(h, n), rz(t, n), par) for n, h, t, par in BONES]

arm_data = bpy.data.armatures.new('LavaHorseRig')
rig = bpy.data.objects.new('LavaHorseRig', arm_data)
sc.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode='EDIT')
for name, h, t, parent in BONES:
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail, eb.roll = h, t, 0.0
    if parent:
        eb.parent = arm_data.edit_bones[parent]
        eb.use_connect = False
bpy.ops.object.mode_set(mode='OBJECT')
arm_data.display_type = 'STICK'

# skin: mesh already carries vertex groups named after bones (assigned per part in build_geo)
horse.parent = rig
mod = horse.modifiers.new('Armature', 'ARMATURE')
mod.object = rig
bpy.context.view_layer.objects.active = horse
horse.select_set(True)
bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
bone_names = {b[0] for b in BONES}
stray = [g.name for g in horse.vertex_groups if g.name not in bone_names]
assert not stray, stray
unweighted = sum(1 for v in horse.data.vertices if not v.groups)
print('WEIGHTS unweighted verts:', unweighted)
assert unweighted == 0

# ------------------------------------------------------------------ animation helpers
for pb in rig.pose.bones:
    pb.rotation_mode = 'QUATERNION'


def qworld(bone_name, axis, deg):
    """Rotation about a world-space axis expressed in the bone's rest-local space."""
    b = rig.data.bones[bone_name]
    ax = (b.matrix_local.to_3x3().inverted() @ Vector(axis)).normalized()
    return Quaternion(ax, math.radians(deg))


def pose_rot(name, *rots):
    q = Quaternion()
    for axis, deg in rots:
        q = qworld(name, axis, deg) @ q
    rig.pose.bones[name].rotation_quaternion = q


def pose_loc(name, world_offset):
    b = rig.data.bones[name]
    rig.pose.bones[name].location = b.matrix_local.to_3x3().inverted() @ Vector(world_offset)


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


def reset_pose():
    for pb in rig.pose.bones:
        pb.rotation_quaternion = Quaternion()
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


def key_all(frame):
    for pb in rig.pose.bones:
        pb.keyframe_insert('rotation_quaternion', frame=frame, group=pb.name)
        pb.keyframe_insert('location', frame=frame, group=pb.name)


def make_action(name, length, pose_fn):
    rig.animation_data_create()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data.action = act
    for f in range(0, length + 1):
        t = f / length
        reset_pose()
        pose_fn(t)
        key_all(f)
    act.frame_range = (0, length)
    act.use_frame_range = True
    act.use_cyclic = True
    return act


TAU = 2 * math.pi


def idle_pose(t):
    br = math.sin(TAU * t * 2)                  # two breaths per loop
    pose_loc('Torso', (0, 0, 0.035 * br))
    for s in 'LR':                                # keep hooves planted while the torso breathes
        pose_loc(f'FrontUpper.{s}', (0, 0, -0.035 * br))
        pose_loc(f'HindUpper.{s}', (0, 0, -0.035 * br))
    pose_rot('Chest', (X, -0.8 * br))
    look = math.sin(TAU * t)
    pose_rot('Neck', (X, -2.5 * math.sin(TAU * t + 0.6) - 1.5 * br), (Z, 4 * look))
    pose_rot('Head', (X, 4 * math.sin(TAU * t * 2 + 1.2)), (Z, 6 * look), (Y, 3 * math.sin(TAU * t)))
    # ear twitch (quick flick around 60 % of the loop), otherwise gentle drift
    tw = math.exp(-((t - 0.6) / 0.03) ** 2)
    pose_rot('Ear.L', (X, 8 * tw + 2 * br), (Y, -10 * tw))
    pose_rot('Ear.R', (X, 3 * math.sin(TAU * t + 2) + 2 * br))
    # flame tail: slow sway + flicker
    pose_rot('Tail1', (Z, 7 * math.sin(TAU * t)), (X, 3 * math.sin(TAU * t * 3)))
    pose_rot('Tail2', (Z, 11 * math.sin(TAU * t - 0.9)), (X, 4 * math.sin(TAU * t * 3 - 1.1)))
    pose_rot('Hips', (Y, 1.2 * math.sin(TAU * t)))


def walk_pose(t):
    # lateral-sequence four-beat walk: LH -> LF -> RH -> RF
    phases = {'HindUpper.L': 0.0, 'FrontUpper.L': 0.25, 'HindUpper.R': 0.5, 'FrontUpper.R': 0.75}
    for up, p in phases.items():
        phi = TAU * (t + p)
        swing = -24 * math.sin(phi) if up.startswith('Front') else -20 * math.sin(phi)
        lift = max(0.0, math.cos(phi)) ** 1.5     # swing phase (leg travelling forward)
        pose_rot(up, (X, swing))
        low = up.replace('Upper', 'Lower')
        hoof = up.replace('Upper', 'Hoof')
        if up.startswith('Front'):
            pose_rot(low, (X, 55 * lift))          # knee folds, hoof tucks back
            pose_rot(hoof, (X, 25 * lift))
        else:
            pose_rot(low, (X, -30 * lift))         # hock flexes
            pose_rot(hoof, (X, 45 * lift))
    bob = math.cos(TAU * t * 2)
    pose_loc('Torso', (0, 0, -0.05 + 0.06 * bob))
    pose_rot('Chest', (Y, 2.0 * math.sin(TAU * t)), (X, 1.2 * bob))
    pose_rot('Hips', (Y, -2.0 * math.sin(TAU * t + 0.5)), (X, -1.0 * bob))
    pose_rot('Neck', (X, 4 * math.cos(TAU * t * 2 + 0.6)))
    pose_rot('Head', (X, -3 * math.cos(TAU * t * 2 + 1.0)))
    pose_rot('Ear.L', (X, 3 * math.sin(TAU * t * 2)))
    pose_rot('Ear.R', (X, 3 * math.sin(TAU * t * 2 + 0.5)))
    pose_rot('Tail1', (Z, 9 * math.sin(TAU * t)), (X, -3 + 3 * bob))
    pose_rot('Tail2', (Z, 14 * math.sin(TAU * t - 1.0)), (X, 4 * math.cos(TAU * t * 2 - 0.8)))


idle = make_action('Idle', IDLE_LEN, idle_pose)
walk = make_action('Walk', WALK_LEN, walk_pose)
reset_pose()

# NLA: one muted track per clip so the .blend shows both; active action = Idle
ad = rig.animation_data
for act in (walk, idle):
    tr = ad.nla_tracks.new(); tr.name = act.name
    tr.strips.new(act.name, 0, act)
    tr.mute = True
ad.action = idle
sc.frame_start, sc.frame_end = 0, IDLE_LEN

# ------------------------------------------------------------------ exports
os.makedirs(os.path.join(ROOT, 'export'), exist_ok=True)
# Roblox reads one diffuse texture per MeshPart; embed the 1024 atlas (Roblox's in-game max)
col_img = [n for n in horse.data.materials[0].node_tree.nodes if n.type == 'TEX_IMAGE' and 'Color' in n.image.name][0].image
small = bpy.data.images.load(os.path.join(ROOT, 'textures', 'LavaHorse_Color_1024.png'))
small.name = 'LavaHorse_Color_1024'


def use_texture(img):
    for n in horse.data.materials[0].node_tree.nodes:
        if n.type == 'TEX_IMAGE' and 'Color' in n.image.name:
            n.image = img


def select_export_objs():
    bpy.ops.object.select_all(action='DESELECT')
    for o in (rig, horse):
        o.select_set(True)
    bpy.context.view_layer.objects.active = rig


def export_fbx(path, action):
    ad.action = action
    for tr in ad.nla_tracks:
        tr.mute = True
    select_export_objs()
    kw = dict(filepath=path, use_selection=True, object_types={'ARMATURE', 'MESH'},
              apply_unit_scale=True, apply_scale_options='FBX_SCALE_ALL', axis_forward='-Z', axis_up='Y',
              bake_space_transform=False, use_mesh_modifiers=False, mesh_smooth_type='FACE',
              add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
              use_armature_deform_only=False, embed_textures=True, path_mode='COPY',
              bake_anim=action is not None)
    if action is not None:
        sc.frame_start, sc.frame_end = int(action.frame_range[0]), int(action.frame_range[1])
        kw.update(bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
                  bake_anim_force_startend_keying=True, bake_anim_step=1.0, bake_anim_simplify_factor=0.0)
    sc.name = action.name if action is not None else 'LavaHorse'   # FBX take name shown in Roblox
    bpy.ops.export_scene.fbx(**kw)
    print('EXPORTED', path, os.path.getsize(path))


use_texture(small)
reset_pose(); ad.action = None
export_fbx(os.path.join(ROOT, 'export', 'LavaHorse.fbx'), None)
export_fbx(os.path.join(ROOT, 'export', 'LavaHorse_Idle.fbx'), idle)
export_fbx(os.path.join(ROOT, 'export', 'LavaHorse_Walk.fbx'), walk)

# glTF/GLB with both clips (Roblox's 3D Importer also accepts .glb)
ad.action = None
for tr in ad.nla_tracks:
    tr.mute = False
select_export_objs()
bpy.ops.export_scene.gltf(filepath=os.path.join(ROOT, 'export', 'LavaHorse.glb'), export_format='GLB',
                          use_selection=True, export_yup=True, export_apply=False, export_animations=True,
                          export_animation_mode='ACTIONS', export_skins=True, export_materials='EXPORT',
                          export_image_format='AUTO')
print('EXPORTED glb')

use_texture(col_img)
for tr in ad.nla_tracks:
    tr.mute = True
ad.action = idle
sc.frame_start, sc.frame_end = 0, IDLE_LEN
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'LavaHorse.blend'), relative_remap=True)
print('TRIS', sum(len(p.vertices) - 2 for p in horse.data.polygons), 'BONES', len(rig.data.bones))
print('STAGE2_OK')
