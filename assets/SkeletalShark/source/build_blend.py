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
import shark_lowpoly as L  # noqa: E402
import stud_bake as SB  # noqa: E402
import bmesh  # noqa: E402

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

os.makedirs(OUT, exist_ok=True)
tex_dir = os.path.join(OUT, "textures")
os.makedirs(tex_dir, exist_ok=True)
color_path = os.path.join(tex_dir, "SkeletalShark_Color.png")
emis_path = os.path.join(tex_dir, "SkeletalShark_Emissive.png")

# ----------------------------------------------------------------------------- mesh (smooth low-poly)
lp = L.build_all()
MAT_IDS = {n: k for k, n in enumerate(SB.MATS)}
parts = sorted(set(lp.FP))
BONE_LIST = ["SPINE", "Head", "Jaw", "Dorsal", "TailFin", "PectoralL", "PectoralR"]


def make_obj(name, verts, faces, fmat, fpart, vbone_names):
    """Mesh object in world space with face (material, part) and vertex (bone) attributes."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(to_world(p)) for p in verts], [], [f[::-1] for f in faces])
    me.update()
    am = me.attributes.new("shark_mat", "INT", "FACE")
    ap = me.attributes.new("shark_part", "INT", "FACE")
    ab = me.attributes.new("shark_bone", "INT", "POINT")
    for k in range(len(faces)):
        am.data[k].value = fmat[k]
        ap.data[k].value = fpart[k]
    for k, bn in enumerate(vbone_names):
        ab.data[k].value = BONE_LIST.index(bn)
    bmx = bmesh.new()
    bmx.from_mesh(me)
    bmesh.ops.recalc_face_normals(bmx, faces=bmx.faces[:])  # outward normals: required by the boolean
    bmx.to_mesh(me)
    bmx.free()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob


def subset(sel):
    fids = [k for k in range(len(lp.F)) if sel(lp.FP[k])]
    used = sorted({v for k in fids for v in lp.F[k]})
    remap = {v: n for n, v in enumerate(used)}
    return ([lp.V[v] for v in used], [[remap[v] for v in lp.F[k]] for k in fids],
            [MAT_IDS[lp.FM[k]] for k in fids], [parts.index(lp.FP[k]) for k in fids], [lp.VB[v] for v in used])


skull = make_obj("Skull", *subset(lambda p: p == "skull"))
rest = make_obj("SkeletalShark", *subset(lambda p: p != "skull"))
# eye canals: boolean-cut two round tunnels into the skull; the tunnel walls become dark socket faces
cv, cf = L.eye_canal_cutter()
cutter = make_obj("EyeCanalCutter", cv, cf, [MAT_IDS["socket"]] * len(cf), [parts.index("skull")] * len(cf),
                  ["Head"] * len(cv))
bmod = skull.modifiers.new("Canal", "BOOLEAN")
bmod.operation = "DIFFERENCE"
bmod.solver = "EXACT"
bmod.object = cutter
bmod.use_self = True
bmod.use_hole_tolerant = True
bpy.context.view_layer.objects.active = skull
bpy.ops.object.modifier_apply(modifier=bmod.name)
print("CANAL skull faces", len(skull.data.polygons), "socket faces",
      sum(1 for d in skull.data.attributes["shark_mat"].data if d.value == MAT_IDS["socket"]))
bpy.data.objects.remove(cutter, do_unlink=True)
for d in skull.data.attributes["shark_bone"].data:
    d.value = BONE_LIST.index("Head")
bpy.ops.object.select_all(action="DESELECT")
skull.select_set(True)
rest.select_set(True)
bpy.context.view_layer.objects.active = rest
bpy.ops.object.join()
obj = rest
mesh = obj.data
mesh.name = "SkeletalShark"
bm = bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
bm.to_mesh(mesh)
bm.free()
for p in mesh.polygons:
    p.use_smooth = False
# per-vertex shark coords + bone rule, read back after boolean/join/triangulate
vshark = [((v.co.y / S) + I_CENTER, v.co.x / S, v.co.z / S - Z_OFF) for v in mesh.vertices]
vbone = [BONE_LIST[d.value] for d in mesh.attributes["shark_bone"].data]

# UVs: smart project (planar islands, uniform texel density) then bake the stud atlas
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.006, area_weight=0.0,
                         correct_aspect=True, scale_to_bounds=False)
bpy.ops.object.mode_set(mode="OBJECT")
# flat-colour islands (teeth, glow, eye, sockets) get little texture space -> more pixels for studs
from bpy_extras import mesh_utils  # noqa: E402

_uv = mesh.uv_layers.active
_mat = mesh.attributes["shark_mat"]
for isl in mesh_utils.mesh_linked_uv_islands(mesh):
    if any(_mat.data[p].value in (0, 1) for p in isl):  # only shrink islands with no studded faces
        continue
    loops = [li for p in isl for li in mesh.polygons[p].loop_indices]
    c = sum((_uv.data[li].uv for li in loops), start=_uv.data[loops[0]].uv * 0) / len(loops)
    for li in loops:
        _uv.data[li].uv = c + (_uv.data[li].uv - c) * 0.25
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.select_all(action="SELECT")
bpy.ops.uv.pack_islands(rotate=True, margin=0.003)
bpy.ops.object.mode_set(mode="OBJECT")
uvl = mesh.uv_layers.active
uvl.name = "UVMap"
from bpy_extras import mesh_utils  # noqa: E402

isl_of = np.zeros(len(mesh.polygons), np.int32)
for k, isl in enumerate(mesh_utils.mesh_linked_uv_islands(mesh)):
    isl_of[isl] = k
T = len(mesh.polygons)
UV = np.zeros((T, 3, 2))
POS = np.zeros((T, 3, 3))
NRM = np.zeros((T, 3))
MT = np.array([mesh.attributes["shark_mat"].data[k].value for k in range(T)])
PT = np.array([mesh.attributes["shark_part"].data[k].value for k in range(T)])
for t, poly in enumerate(mesh.polygons):
    for c, li in enumerate(poly.loop_indices):
        UV[t, c] = uvl.data[li].uv
        POS[t, c] = vshark[mesh.loops[li].vertex_index]
    NRM[t] = (poly.normal.y, poly.normal.x, poly.normal.z)  # world (X=w, Y=i) -> shark (i, w, z)
# height range per part (per tooth for teeth) for the painted gradient
ZR = np.zeros((T, 2))
for pi in range(len(parts)):
    sel = PT == pi
    if parts[pi] == "teeth":
        for t in np.nonzero(sel)[0]:
            ZR[t] = (POS[t, :, 2].min(), POS[t, :, 2].max())
    else:
        ZR[sel] = (POS[sel, :, 2].min(), POS[sel, :, 2].max())
# stud frames: world-aligned everywhere except the tilted pectorals (use the fin's own axes)
FR = np.tile(np.eye(3), (T, 1, 1))
for t, poly in enumerate(mesh.polygons):
    bn = vbone[mesh.loops[poly.loop_indices[0]].vertex_index]
    if bn in ("PectoralL", "PectoralR"):
        FR[t] = G.pec_xf(1 if bn == "PectoralL" else -1)[:3, :3].T
_hw = L.hw_at(L.EYE_C[0])
EYES = [(L.EYE_C[0], _hw - 0.7, L.EYE_C[1]), (L.EYE_C[0], -_hw + 0.7, L.EYE_C[1])]
# bake at 2048 and downsample -> anti-aliased studs in the 1024 texture Roblox uses
img_arr, emis_arr, PPC = SB.bake(UV, POS, NRM, MT, isl_of, ZR, FR, EYES, 2048)
PPC /= 2
Image.fromarray(img_arr.astype(np.uint8)).resize((1024, 1024), Image.LANCZOS).save(color_path)
Image.fromarray((emis_arr * 255).astype(np.uint8)).resize((1024, 1024), Image.LANCZOS).save(emis_path)

# ----------------------------------------------------------------------------- material
mat = bpy.data.materials.new("M_SkeletalShark")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
img = bpy.data.images.load(color_path)
img.colorspace_settings.name = "sRGB"
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = img
tex.interpolation = "Linear"
tex.location = (-500, 200)
emi = bpy.data.images.load(emis_path)
emi.colorspace_settings.name = "Non-Color"
etex = nt.nodes.new("ShaderNodeTexImage")
etex.image = emi
etex.interpolation = "Linear"
etex.location = (-500, -150)
mul = nt.nodes.new("ShaderNodeMath")
mul.operation = "MULTIPLY"
mul.inputs[1].default_value = 2.0
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
print("TRIS", sum(len(p.vertices) - 2 for p in mesh.polygons), "VERTS", len(mesh.vertices), "PPC", round(PPC, 1))

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
