"""Builds SkeletalShark.blend (mesh + stud atlas + rig + Idle/Walk/Run/Attack) and the
Roblox-ready FBX files. Run with a Python that has the `bpy` module (Blender 4.2):

    python build_blend.py <output_dir>
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shark_geo as G  # noqa: E402

OUT = os.path.abspath(sys.argv[-1] if len(sys.argv) > 1 else ".")
S = 0.3  # blender units per voxel cube -> shark is ~14.4 units long
I_CENTER = 24.0
Z_OFF = 1.0  # lowest point (tail / pectoral tips) sits on Z=0
FPS = 30


def to_world(p):
    i, w, z = p
    return Vector((w * S, (i - I_CENTER) * S, (z + Z_OFF) * S))


# ----------------------------------------------------------------------------- scene reset
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = FPS
scene.unit_settings.system = "METRIC"
# Roblox export convention: unit scale 0.01 + "FBX Units Scale" => 1 Blender unit = 1 stud
scene.unit_settings.scale_length = 0.01
scene.unit_settings.length_unit = "CENTIMETERS"

res = G.build_all(1024)
atlas = res["atlas"]
os.makedirs(OUT, exist_ok=True)
tex_dir = os.path.join(OUT, "textures")
os.makedirs(tex_dir, exist_ok=True)
color_path = os.path.join(tex_dir, "SkeletalShark_Color.png")
emis_path = os.path.join(tex_dir, "SkeletalShark_Emissive.png")
Image.fromarray(np.clip(atlas.img, 0, 255).astype(np.uint8)).save(color_path)
Image.fromarray((atlas.emis * 255).astype(np.uint8)).save(emis_path)

# ----------------------------------------------------------------------------- mesh data
verts, faces, uvs, vbone, vshark = [], [], [], [], []


def add_face(pts_shark, face_uvs, bone):
    base = len(verts)
    for p in pts_shark:
        verts.append(to_world(p))
        vshark.append(p)
        vbone.append(bone)
    # shark (i,w,z)->(Y,X,Z) swaps two axes => reverse winding to keep normals outward
    idx = list(range(base, base + len(pts_shark)))[::-1]
    faces.append(idx)
    uvs.append(list(face_uvs)[::-1])


for q in res["quads"]:
    xf = q.part.xf
    pts = []
    for c in q.corners:
        v = xf @ np.array([c[0], c[1], c[2], 1.0])
        pts.append(tuple(v[:3]))
    add_face(pts, q.uvs, q.bone)

u0, v0, u1, v1 = res["tooth_rect"]
for vs, fs, bone in res["teeth"]:
    zs = [p[2] for p in vs]
    zmin, zmax = min(zs), max(zs)
    for f in fs:
        pts = [vs[k] for k in f]
        # gradient tile: base (ivory) -> tip (white)
        fu = []
        for p in pts:
            t = (p[2] - zmin) / max(zmax - zmin, 1e-6)
            down = bone == "Head"
            t = 1 - t if not down else t
            t = 1 - t
            fu.append((u0 + (u1 - u0) * (0.3 + 0.4 * ((p[0] + p[1]) % 1.0)), v0 + (v1 - v0) * t))
        add_face(pts, fu, bone)

gu0, gv0, gu1, gv1 = res["glow_rect"]
for (a0, b0, c0), (a1, b1, c1) in res["glows"]:
    X = [a0, a1]
    Yw = [b0, b1]
    Zc = [c0, c1]
    cube_faces = [((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)),
                  ((1, 0, 0), (1, 0, 1), (1, 1, 1), (1, 1, 0)),
                  ((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 0, 0)),
                  ((0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)),
                  ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)),
                  ((0, 0, 1), (0, 1, 1), (1, 1, 1), (1, 0, 1))]
    guv = [(gu0, gv0), (gu1, gv0), (gu1, gv1), (gu0, gv1)]
    for cf in cube_faces:
        pts = [(X[a], Yw[b], Zc[c]) for a, b, c in cf]
        add_face(pts, guv, "SPINE")

mesh = bpy.data.meshes.new("SkeletalShark")
mesh.from_pydata([tuple(v) for v in verts], [], faces)
mesh.update()
uvl = mesh.uv_layers.new(name="UVMap")
for poly, fu in zip(mesh.polygons, uvs):
    for li, uv in zip(poly.loop_indices, fu):
        uvl.data[li].uv = uv
for p in mesh.polygons:
    p.use_smooth = False
mesh.validate(clean_customdata=False)
obj = bpy.data.objects.new("SkeletalShark", mesh)
scene.collection.objects.link(obj)

# merge coincident verts that share bone *and* uv island is not possible (per-quad UVs), keep as is.

# ----------------------------------------------------------------------------- material
mat = bpy.data.materials.new("M_SkeletalShark")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
img = bpy.data.images.load(color_path)
img.colorspace_settings.name = "sRGB"
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
tex.interpolation = "Closest"
tex.location = (-500, 200)
emi = bpy.data.images.load(emis_path)
emi.colorspace_settings.name = "Non-Color"
etex = nt.nodes.new("ShaderNodeTexImage")
etex.image = emi
etex.interpolation = "Closest"
etex.location = (-500, -150)
mul = nt.nodes.new("ShaderNodeMath")
mul.operation = "MULTIPLY"
mul.inputs[1].default_value = 4.0
mul.location = (-200, -150)
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
nt.links.new(etex.outputs["Color"], mul.inputs[0])
nt.links.new(mul.outputs[0], bsdf.inputs["Emission Strength"])
bsdf.inputs["Roughness"].default_value = 0.6
bsdf.inputs["Specular IOR Level"].default_value = 0.35
obj.data.materials.append(mat)

# ----------------------------------------------------------------------------- armature
BONES = {
    # name: (head shark coords, parent)
    "Root": ((I_CENTER, 0, -Z_OFF), None),
    "Torso": ((12.5, 0, 5.2), "Root"),
    "Head": ((12.5, 0, 6.0), "Torso"),
    "Jaw": ((9.2, 0, 3.2), "Head"),
    "Spine2": ((19.0, 0, 5.1), "Torso"),
    "Tail1": ((25.5, 0, 5.0), "Spine2"),
    "Tail2": ((31.0, 0, 4.9), "Tail1"),
    "TailFin": ((37.0, 0, 4.9), "Tail2"),
    "Dorsal": ((19.5, 0, 9.0), "Spine2"),
    "PectoralL": (tuple(G.PEC_ROOT), "Torso"),
    "PectoralR": (tuple(G.PEC_ROOT * np.array([1, -1, 1])), "Torso"),
}
BONE_LEN = {"Root": 2.0, "Torso": 6.5, "Spine2": 6.5, "Tail1": 5.5, "Tail2": 6.0, "TailFin": 7.0}

arm_data = bpy.data.armatures.new("SkeletalSharkRig")
arm = bpy.data.objects.new("SkeletalSharkRig", arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
for name, (head, parent) in BONES.items():
    eb = arm_data.edit_bones.new(name)
    h = to_world(head)
    eb.head = h
    eb.tail = h + Vector((0, BONE_LEN.get(name, 1.5) * S, 0))
    eb.roll = 0.0
for name, (head, parent) in BONES.items():
    if parent:
        arm_data.edit_bones[name].parent = arm_data.edit_bones[parent]
bpy.ops.object.mode_set(mode="OBJECT")

# ----------------------------------------------------------------------------- weights
SPINE_SEG = [("Torso", 12.5), ("Spine2", 19.0), ("Tail1", 25.5), ("Tail2", 31.0), ("TailFin", 37.0)]
BLEND = 1.2


def spine_weights(i):
    names = [n for n, _ in SPINE_SEG]
    starts = [s for _, s in SPINE_SEG]
    k = 0
    for j, s in enumerate(starts):
        if i >= s:
            k = j
    w = {names[k]: 1.0}
    # blend with previous bone near the start boundary
    if k > 0 and i < starts[k] + BLEND:
        t = (i - (starts[k] - BLEND)) / (2 * BLEND)
        t = max(0.0, min(1.0, t))
        t = t * t * (3 - 2 * t)
        w = {names[k]: t, names[k - 1]: 1 - t}
    elif k + 1 < len(starts) and i > starts[k + 1] - BLEND:
        t = (i - (starts[k + 1] - BLEND)) / (2 * BLEND)
        t = max(0.0, min(1.0, t))
        t = t * t * (3 - 2 * t)
        w = {names[k]: 1 - t, names[k + 1]: t}
    return w


groups = {n: obj.vertex_groups.new(name=n) for n in BONES if n != "Root"}
for vi, (b, p) in enumerate(zip(vbone, vshark)):
    if b == "SPINE":
        for n, wt in spine_weights(p[0]).items():
            if wt > 1e-4:
                groups[n].add([vi], wt, "REPLACE")
    else:
        groups[b].add([vi], 1.0, "REPLACE")

obj.parent = arm
mod = obj.modifiers.new("Armature", "ARMATURE")
mod.object = arm

# ----------------------------------------------------------------------------- animations
D = math.radians


def sin(x):
    return math.sin(2 * math.pi * x)


def pose_channels(fn, n_frames, loop=True):
    """fn(t, f) -> {bone: {'rot': (x,y,z) deg, 'loc': (x,y,z)}}; keys every frame."""
    act = bpy.data.actions.new(fn.__name__.capitalize())
    arm.animation_data_create()
    arm.animation_data.action = act
    for pb in arm.pose.bones:
        pb.rotation_mode = "XYZ"
    last = n_frames if loop else n_frames - 1
    for f in range(0, last + 1):
        t = (f % n_frames) / n_frames if loop else f / (n_frames - 1)
        pose = fn(t, f)
        for pb in arm.pose.bones:
            d = pose.get(pb.name, {})
            r = d.get("rot", (0, 0, 0))
            pb.rotation_euler = (D(r[0]), D(r[1]), D(r[2]))
            pb.location = d.get("loc", (0, 0, 0))
            pb.keyframe_insert("rotation_euler", frame=f + 1)
            pb.keyframe_insert("location", frame=f + 1)
    act.frame_range = (1, last + 1)
    act.use_frame_range = True
    act.use_cyclic = loop
    act.use_fake_user = True
    return act


def wave(t, amps, lag, extra=None):
    out = {}
    for k, (b, a) in enumerate(amps):
        out[b] = {"rot": (0, 0, a * sin(t - lag * k))}
    return out


def idle(t, f):
    p = wave(t, [("Torso", 1.0), ("Spine2", 1.8), ("Tail1", 2.8), ("Tail2", 3.6), ("TailFin", 4.5)], 0.12)
    p["Root"] = {"loc": (0, 0, 0.07 * sin(t)), "rot": (1.5 * sin(t + 0.1), 0, 0)}
    p["Head"] = {"rot": (2.0 * sin(t + 0.25), 0, -1.0 * sin(t))}
    p["Jaw"] = {"rot": (-3.0 + 4.0 * sin(2 * t), 0, 0)}
    p["PectoralL"] = {"rot": (0, -7 * sin(t), 3 * sin(t + 0.25))}
    p["PectoralR"] = {"rot": (0, 7 * sin(t), -3 * sin(t + 0.25))}
    p["Dorsal"] = {"rot": (0, 0, -2 * sin(t - 0.3))}
    return p


def walk(t, f):
    p = wave(t, [("Torso", 2), ("Spine2", 4), ("Tail1", 6), ("Tail2", 8), ("TailFin", 10)], 0.1)
    p["Root"] = {"loc": (0, 0, 0.05 * sin(2 * t)), "rot": (1.0 * sin(2 * t), 2.0 * sin(t), -2.0 * sin(t + 0.15))}
    p["Head"] = {"rot": (1.5 * sin(2 * t + 0.2), 0, -4 * sin(t + 0.05))}
    p["Jaw"] = {"rot": (2 * sin(t), 0, 0)}
    p["PectoralL"] = {"rot": (0, -10 * sin(t + 0.25), 5 + 4 * sin(t))}
    p["PectoralR"] = {"rot": (0, 10 * sin(t + 0.25), -5 - 4 * sin(t))}
    p["Dorsal"] = {"rot": (0, 0, -4 * sin(t - 0.2))}
    return p


def run(t, f):
    p = wave(t, [("Torso", 3), ("Spine2", 6), ("Tail1", 9), ("Tail2", 12), ("TailFin", 14)], 0.1)
    p["Root"] = {"loc": (0, -0.1, 0.08 * sin(2 * t)), "rot": (5 + 2 * sin(2 * t), 3 * sin(t), -3 * sin(t + 0.15))}
    p["Head"] = {"rot": (-3 + 2 * sin(2 * t + 0.2), 0, -6 * sin(t + 0.05))}
    p["Jaw"] = {"rot": (6 + 3 * sin(2 * t), 0, 0)}
    p["PectoralL"] = {"rot": (0, -10 - 8 * sin(t + 0.25), 22)}
    p["PectoralR"] = {"rot": (0, 10 + 8 * sin(t + 0.25), -22)}
    p["Dorsal"] = {"rot": (0, 0, -7 * sin(t - 0.2))}
    return p


ATTACK_KEYS = [
    # frame, root loc Y, root rotX, head X, head Z, jaw X, tail wave (T1,T2,TF), pec up, torso Z
    (0, 0.0, 0, 0, 0, 0, (0, 0, 0), 0),
    (9, 0.40, -9, -6, 0, 18, (8, 12, 14), 16),
    (15, -1.30, 6, 4, 0, 24, (-8, -12, -14), -6),
    (18, -1.40, 7, 8, 0, -20, (-4, -6, -8), -4),
    (21, -1.30, 5, 4, 7, 6, (3, 4, 5), 0),
    (24, -1.25, 5, 6, -7, -18, (5, 6, 8), 0),
    (28, -0.90, 3, 2, 3, 2, (-3, -4, -5), 4),
    (40, 0.0, 0, 0, 0, 0, (0, 0, 0), 0),
]


def attack(t, f):
    keys = ATTACK_KEYS
    for a, b in zip(keys[:-1], keys[1:]):
        if a[0] <= f <= b[0]:
            u = (f - a[0]) / (b[0] - a[0])
            u = u * u * (3 - 2 * u)
            k = [None] * 8
            k[0] = f
            vals = []
            for idx in range(1, 8):
                va, vb = a[idx], b[idx]
                if isinstance(va, tuple):
                    vals.append(tuple(x + (y - x) * u for x, y in zip(va, vb)))
                else:
                    vals.append(va + (vb - va) * u)
            ry, rx, hx, hz, jx, tw, pu = vals
            break
    p = {
        "Root": {"loc": (0, ry, 0.05 * abs(ry)), "rot": (rx, 0, 0)},
        "Head": {"rot": (hx, 0, hz)},
        "Jaw": {"rot": (jx, 0, 0)},
        "Tail1": {"rot": (0, 0, tw[0])},
        "Tail2": {"rot": (0, 0, tw[1])},
        "TailFin": {"rot": (0, 0, tw[2])},
        "Spine2": {"rot": (0, 0, tw[0] * 0.35)},
        "PectoralL": {"rot": (0, -pu, 0)},
        "PectoralR": {"rot": (0, pu, 0)},
    }
    return p


ANIMS = [("Idle", idle, 90, True), ("Walk", walk, 40, True), ("Run", run, 24, True), ("Attack", attack, 41, False)]
actions = {}
for name, fn, n, loop in ANIMS:
    fn.__name__ = name.lower()
    act = pose_channels(fn, n, loop)
    act.name = name
    actions[name] = act

# rest pose restored, no active action on the saved rig (NLA keeps the clips)
for name, act in actions.items():
    tr = arm.animation_data.nla_tracks.new()
    tr.name = name
    st = tr.strips.new(name, int(act.frame_range[0]), act)
    tr.mute = True
arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.rotation_euler = (0, 0, 0)
    pb.location = (0, 0, 0)

scene.frame_start, scene.frame_end = 1, 90
print("TRIS", sum(len(p.vertices) - 2 for p in mesh.polygons), "VERTS", len(mesh.vertices), "PPC", res["ppc"])

# pack texture so the .blend is self contained
img.pack()
emi.pack()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "SkeletalShark.blend"))


# ----------------------------------------------------------------------------- FBX export
def export_fbx(path, action=None):
    for o in bpy.context.view_layer.objects:
        o.select_set(o in (obj, arm))
    bpy.context.view_layer.objects.active = arm
    arm.animation_data.action = action
    for tr in arm.animation_data.nla_tracks:
        tr.mute = True
    scene.name = action.name if action is not None else "SkeletalShark"
    if action is not None:
        scene.frame_start, scene.frame_end = int(action.frame_range[0]), int(action.frame_range[1])
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"ARMATURE", "MESH"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", bake_space_transform=False,
        axis_forward="-Z", axis_up="Y", use_mesh_modifiers=True, mesh_smooth_type="FACE",
        add_leaf_bones=False, primary_bone_axis="Y", secondary_bone_axis="X",
        use_armature_deform_only=False, armature_nodetype="NULL",
        bake_anim=action is not None, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True, bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0, embed_textures=True, path_mode="COPY")


fbx_dir = os.path.join(OUT, "fbx")
os.makedirs(fbx_dir, exist_ok=True)
export_fbx(os.path.join(fbx_dir, "SkeletalShark.fbx"), None)
for name, act in actions.items():
    export_fbx(os.path.join(fbx_dir, f"SkeletalShark_{name}.fbx"), act)
arm.animation_data.action = None
print("EXPORT_DONE")
