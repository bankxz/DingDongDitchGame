"""Build the voxel sea drake for Roblox: mesh, baked stud atlas, rig, RefPose/Idle/Walk.

Run headless:  python3 build_drake.py        (bpy module, Blender 4.2)

Conventions
- 1 Blender unit = 1 stud (scene unit scale 0.01). Faces -Y, Z up, belly on Z=0.
- Bind (rest) pose is animation-friendly: straight spine lying flat, head level,
  limbs/fins spread out, jaw relaxed. The reference sheet's raised-neck S-curve
  is the `RefPose` action; Idle and Walk are built on top of it.
- Built as the right half (x >= 0), baked, then mirrored so halves share UVs.
"""
import math
import os

import bpy  # noqa: I001  (must precede bmesh/mathutils when run as a module)
import bmesh
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
TILES = os.path.join(ROOT, "textures", "tiles")
TEX = os.path.join(ROOT, "textures")
EXPORT = os.path.join(ROOT, "export")
os.makedirs(EXPORT, exist_ok=True)
ATLAS = 1024
FPS = 30

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 0.01
scene.render.fps = FPS

M_BODY, M_BELLY, M_FIN, M_TOOTH, M_MOUTH, M_EYE, M_TEAL = range(7)
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


def lerp(a, b, t):
    return a + (b - a) * t


class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("tile")
        self.deform = self.bm.verts.layers.deform.verify()
        self.groups = []

    def gi(self, name):
        if name not in self.groups:
            self.groups.append(name)
        return self.groups.index(name)

    def vert(self, co, wts):
        v = self.bm.verts.new(co)
        for g, w in wts.items():
            if w > 1e-4:
                v[self.deform][self.gi(g)] = w
        return v

    def face(self, vs, mat, uvs=None):
        f = self.bm.faces.new(vs)
        f.material_index = mat
        if uvs:
            for lp, uv in zip(f.loops, uvs):
                lp[self.uv].uv = uv
        return f


B = Builder()

# ----------------------------------------------------------------------------
# spine: straight along +Y (neck base y=0 -> tail tip y=BODY_L)
# ----------------------------------------------------------------------------
BODY_L = 24.0
# (t, half width, half height) measured from SIDE (height) and TOP (width) views
# measured from the SIDE view (0.042 studs/px): chest/mid-body ~4.6 studs tall
PROFILE = [(0.0, 0.92, 1.10), (0.08, 1.05, 1.55), (0.18, 1.22, 2.25), (0.35, 1.25, 2.35), (0.55, 1.12, 2.0),
           (0.62, 0.98, 1.62), (0.82, 0.62, 0.95), (0.92, 0.42, 0.60), (1.0, 0.25, 0.35)]


def prof(t):
    for (t0, w0, h0), (t1, w1, h1) in zip(PROFILE, PROFILE[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0)
            return lerp(w0, w1, f), lerp(h0, h1, f)
    return PROFILE[-1][1:]


def spine_pt(t):
    w, h = prof(t)
    return Vector((0, t * BODY_L, h + 0.02))


# spine bones (segment j spans SP_T[j]..SP_T[j+1])
SP_T = [0, 0.09, 0.18, 0.26, 0.34, 0.42, 0.50, 0.58, 0.67, 0.76, 0.84, 0.92, 1.0]
SP_N = ["Neck2", "Neck1", "Chest", "Spine1", "Spine2", "Spine3", "Spine4", "Spine5", "Tail1", "Tail2", "Tail3", "Tail4"]
MIDS = [(a + b) / 2 for a, b in zip(SP_T, SP_T[1:])]


def spine_w(t):
    if t <= MIDS[0]:
        return {SP_N[0]: 1.0}
    if t >= MIDS[-1]:
        return {SP_N[-1]: 1.0}
    for j in range(len(MIDS) - 1):
        if MIDS[j] <= t <= MIDS[j + 1]:
            f = (t - MIDS[j]) / (MIDS[j + 1] - MIDS[j])
            return {SP_N[j]: 1 - f, SP_N[j + 1]: f}


def seg_bone(t):
    for j in range(len(SP_N)):
        if t <= SP_T[j + 1]:
            return SP_N[j]
    return SP_N[-1]


# body tube: 12-vert blocky section, belly band on the underside
RINGS = 36
c = 0.62
SECT = [(c, -1), (1, -c), (1, 0.0), (1, 0.4), (1, c), (c, 1), (-c, 1), (-1, c), (-1, 0.4), (-1, 0.0), (-1, -c), (-c, -1)]
BELLY = {11, 0, 10}
rings = []
for i in range(RINGS + 1):
    t = i / RINGS
    w, h = prof(t)
    p = spine_pt(t)
    wts = spine_w(t)
    rings.append([B.vert(p + X * sx * w + Z * sy * h, wts) for sx, sy in SECT])
for i in range(RINGS):
    for k in range(12):
        kk = (k + 1) % 12
        B.face([rings[i][k], rings[i][kk], rings[i + 1][kk], rings[i + 1][k]], M_BELLY if k in BELLY else M_BODY)
tail_tip = B.vert(spine_pt(1.0) + Y * 0.25, {"Tail4": 1.0})
for k in range(12):
    B.face([rings[-1][k], rings[-1][(k + 1) % 12], tail_tip], M_BELLY if k in BELLY else M_BODY)
B.face(list(reversed(rings[0])), M_BELLY)   # throat/chest front (cream in FRONT view)


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def frustum(b, bw, bh, f, fw, fh, mats, wts, up=Z):
    """Blocky tapered box from back centre b (w,h half sizes) to front centre f."""
    b, f = Vector(b), Vector(f)
    fwd = (f - b).normalized()
    side = up.cross(fwd).normalized()
    upv = fwd.cross(side).normalized()
    rect = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    bv = [B.vert(b + side * sx * bw + upv * sy * bh, wts) for sx, sy in rect]
    fv = [B.vert(f + side * sx * fw + upv * sy * fh, wts) for sx, sy in rect]
    names = ["bottom", "right", "top", "left"]
    for e in range(4):
        n = (e + 1) % 4
        B.face([bv[e], bv[n], fv[n], fv[e]], mats.get(names[e], mats["default"]))
    B.face(list(reversed(bv)), mats.get("back", mats["default"]))
    B.face(fv, mats.get("front", mats["default"]))


def spike(b, tip, width, mat, wts, sides=4):
    b, tip = Vector(b), Vector(tip)
    ax = (tip - b).normalized()
    u = ax.cross(Z if abs(ax.dot(Z)) < 0.9 else X).normalized()
    v = ax.cross(u).normalized()
    ring = [B.vert(b + (u * math.cos(a) + v * math.sin(a)) * width, wts)
            for a in [2 * math.pi * k / sides + math.pi / 4 for k in range(sides)]]
    tv = B.vert(tip, wts)
    for k in range(sides):
        B.face([ring[k], ring[(k + 1) % sides], tv], mat)
    B.face(list(reversed(ring)), mat)


def blade(base, tip, e1, length, thick, wts, mat=M_FIN, bulge=0.32):
    """Crystal fin blade: leaf-shaped plate from a base edge (along e1) to a tip."""
    base, tip, e1 = Vector(base), Vector(tip), Vector(e1).normalized()
    ax = tip - base
    n = e1.cross(ax).normalized()
    bf = base - e1 * length * 0.5
    bb = base + e1 * length * 0.5
    mid = base + ax * 0.55 - e1 * length * bulge
    prof_ = [bf, mid, tip, bb]
    L2 = ax.length_squared

    def uv(p):
        return (min(max((p - bf).dot(e1) / (length * 1.3) + 0.15, 0), 1), min(max((p - base).dot(ax) / L2, 0), 1))

    th = [thick, thick * 0.8, thick * 0.3, thick]
    fr = [B.vert(p + n * t, wts) for p, t in zip(prof_, th)]
    bk = [B.vert(p - n * t, wts) for p, t in zip(prof_, th)]
    uvs = [uv(p) for p in prof_]
    B.face(fr, mat, uvs)
    B.face(list(reversed(bk)), mat, list(reversed(uvs)))
    for i in range(4):
        j = (i + 1) % 4
        B.face([bk[i], bk[j], fr[j], fr[i]], mat, [uvs[i], uvs[j], uvs[j], uvs[i]])


# ----------------------------------------------------------------------------
# head (FRONT + SIDE + close-ups).  head base at y~0.8, nose at y=-4.2
# ----------------------------------------------------------------------------
HW = {"Head": 1.0}
JW = {"Jaw": 1.0}
BODYM = {"default": M_BODY}
frustum((0, 1.0, 1.40), 1.30, 1.15, (0, -1.25, 1.45), 1.45, 1.20, BODYM, HW)          # cranium
frustum((0, -1.0, 1.55), 1.18, 0.50, (0, -4.25, 1.45), 0.78, 0.40,
        {"default": M_BODY, "bottom": M_MOUTH}, HW)                                    # upper snout
frustum((0, -3.2, 1.95), 0.55, 0.12, (0, -4.15, 1.85), 0.45, 0.10, BODYM, HW)          # nose bridge
frustum((0, -1.2, 2.05), 0.30, 0.18, (0, -3.4, 1.98), 0.26, 0.12, BODYM, HW)           # snout ridge
# lower jaw, relaxed-open in bind pose (hinge at y=-0.4, z=0.95)
HINGE = Vector((0, -0.4, 0.95))
JAW_OPEN = math.radians(18)
jr = Matrix.Rotation(JAW_OPEN, 3, X)   # +X rotation tips a -Y vector downward


def jaw_p(y, z):
    return HINGE + jr @ Vector((0, y, z))


frustum(jaw_p(0.3, -0.05), 1.05, 0.40, jaw_p(-3.55, -0.10), 0.62, 0.26,
        {"default": M_BELLY, "top": M_MOUTH}, JW)
frustum(jaw_p(-0.2, -0.05), 0.80, 0.08, jaw_p(-2.8, 0.14), 0.50, 0.05, {"default": M_MOUTH}, JW)  # tongue
# teeth: upper row points down, lower row up (cream), front fangs larger
for i, (y, s) in enumerate([(-4.0, 0.34), (-3.45, 0.24), (-2.95, 0.22), (-2.45, 0.2), (-1.95, 0.18), (-1.45, 0.16)]):
    x = lerp(0.72, 1.12, (y + 4.0) / 2.6) - 0.08
    spike((x, y, 1.08), (x - 0.02, y + 0.02, 1.08 - (0.75 if i == 0 else 0.45)), s * 0.55, M_TOOTH, HW)
for i, (y, s) in enumerate([(-3.35, 0.3), (-2.85, 0.22), (-2.35, 0.2), (-1.85, 0.18)]):
    x = lerp(0.55, 0.9, (y + 3.35) / 1.5)
    b = jaw_p(y, 0.28)
    spike(b.copy() + X * x, b + X * x + Z * (0.6 if i == 0 else 0.4), s * 0.55, M_TOOTH, JW)
# eyes: slanted white insets, inner corner low (angry), under the brow plate
eye = [Vector(p) for p in [(0.38, -1.34, 2.08), (1.36, -1.02, 2.14), (1.40, -1.00, 2.58), (0.42, -1.32, 2.30)]]
exs = [p.x for p in eye]
ezs = [p.z for p in eye]
en = Vector((0.33, -0.94, 0)).normalized()
ef = [B.vert(p + en * 0.10, HW) for p in eye]
eb = [B.vert(p - en * 0.25, HW) for p in eye]
B.face(ef, M_EYE, [(1 - (p.x - min(exs)) / (max(exs) - min(exs)), (p.z - min(ezs)) / (max(ezs) - min(ezs))) for p in eye])
for i in range(4):
    j = (i + 1) % 4
    B.face([eb[i], eb[j], ef[j], ef[i]], M_EYE, [(0.02, 0.02)] * 4)
# brow plates: thick blue blocks from the snout ridge up and out to the temples
frustum((0.25, -1.5, 2.55), 0.22, 0.20, (1.6, -0.85, 3.02), 0.26, 0.26, BODYM, HW, up=Vector((0, -0.4, 1)))
frustum((1.3, -0.95, 2.8), 0.30, 0.25, (1.6, 0.9, 2.7), 0.26, 0.22, BODYM, HW)       # temple ridge
# teal cheek plates under the eyes
frustum((1.25, -1.5, 1.45), 0.18, 0.28, (1.35, 0.2, 1.3), 0.20, 0.34, {"default": M_TEAL}, HW)
# head crest & frill blades (FRONT: central crest + wide cheek frills; SIDE: swept back)
blade((0.0, -0.5, 2.55), (0.0, 0.1, 5.1), Y, 2.0, 0.42, HW)                         # centre crest
blade((0.55, 0.0, 2.5), (1.0, 1.4, 4.7), Y, 2.0, 0.36, HW)                          # crown pair
blade((0.95, 0.9, 2.2), (1.7, 3.1, 3.4), Y, 1.9, 0.34, HW)                          # swept back
blade((1.35, -0.5, 2.3), (3.3, 0.2, 3.3), Vector((0, 0.35, 1)), 1.8, 0.36, HW)      # temple frill
blade((1.45, -0.1, 1.55), (3.4, 0.6, 1.5), Vector((0, 0.35, 1)), 1.7, 0.34, HW)     # cheek frill
blade((1.3, 0.3, 0.95), (2.7, 1.1, 0.3), Vector((0, 0.35, 1)), 1.3, 0.3, HW)        # jaw frill

# ----------------------------------------------------------------------------
# dorsal fins: 8 pairs (SIDE: tall swept blades; TOP: V chevrons)
# ----------------------------------------------------------------------------
DORSAL = [(0.04, 2.5), (0.15, 2.6), (0.26, 2.5), (0.37, 2.3), (0.48, 2.1), (0.59, 1.9), (0.70, 1.6), (0.80, 1.3)]
for t, hgt in DORSAL:
    w, h = prof(t)
    p = spine_pt(t)
    base = p + Z * (h * 0.92) + X * (w * 0.35)
    tip = base + Z * hgt + Y * hgt * 0.6 + X * hgt * 0.08
    blade(base, tip, Y, hgt * 0.95, 0.26, {seg_bone(t): 1.0}, bulge=0.45)

# ----------------------------------------------------------------------------
# side fins (4 per side): front limb with claws + 3 finned stubs
# ----------------------------------------------------------------------------
LIMB_BONES = []   # (name, head, tail, parent)
# limb 1: shoulder -> elbow -> paw, blocky blue arm, cyan claws, teal fin on the forearm
sh = spine_pt(0.22) + X * 1.0 - Z * 0.6
el = Vector((3.0, sh.y - 0.6, 3.5))
wr = Vector((4.05, sh.y - 1.0, 2.1))
pw = Vector((4.1, sh.y - 1.3, 0.4))
frustum(sh, 0.78, 0.78, el, 0.74, 0.74, BODYM, {"Limb1_1_R": 1.0}, up=Z)
frustum(el, 0.74, 0.74, wr, 0.64, 0.64, BODYM, {"Limb1_2_R": 1.0}, up=Vector((1, 0, 0.3)))
frustum(wr, 0.64, 0.64, pw, 0.48, 0.5, BODYM, {"Limb1_2_R": 1.0}, up=X)
for dx, dy in ((0.1, -0.3), (0.3, 0.1), (-0.15, 0.25)):
    blade(pw + Vector((dx, dy, 0.25)), pw + Vector((dx * 1.5 + 0.15, dy - 0.5, -0.65)), Y, 0.55, 0.14, {"Limb1_2_R": 1.0})
for f_, hgt in ((0.25, 1.5), (0.7, 1.3)):
    b_ = el.lerp(wr, f_) + Vector((0.3, 0, 0.3))
    blade(b_, b_ + Vector((1.1, 0.8, 1.0)) * (hgt / 1.5), Y, 1.3, 0.2, {"Limb1_2_R": 1.0})
# tall outer blade rising from the wrist (FRONT view: cyan horns at the bottom corners)
blade(wr + X * 0.4, wr + Vector((0.6, 0.4, 3.0)), Y, 1.4, 0.3, {"Limb1_2_R": 1.0})
b_ = sh.lerp(el, 0.6) + Z * 0.35
blade(b_, b_ + Vector((0.5, 0.9, 1.6)), Y, 1.3, 0.2, {"Limb1_1_R": 1.0})
LIMB_BONES += [("Limb1_1_R", sh, el, seg_bone(0.22)), ("Limb1_2_R", el, pw, "Limb1_1_R")]
# limbs 2-4: short stub + big swept fin blade (SIDE/TOP)
for n, (t, size) in enumerate([(0.42, 3.2), (0.60, 2.8), (0.78, 2.3)], start=2):
    w, h = prof(t)
    p = spine_pt(t)
    s0 = p + X * (w * 0.8) - Z * (h * 0.45)
    s1 = s0 + Vector((0.55, 0.1, -0.15))
    name = f"Fin{n}_R"
    frustum(s0, 0.20, 0.22, s1, 0.17, 0.18, BODYM, {name: 1.0})
    blade(s1, s1 + Vector((size * 0.75, size * 0.85, -size * 0.25)), Y, size * 0.7, 0.3, {name: 1.0})
    LIMB_BONES.append((name, s0, s1 + Vector((size * 0.75, size * 0.85, -size * 0.25)) * 0.5 + s1 * 0.5, seg_bone(t)))

# ----------------------------------------------------------------------------
# tail fan: 6 blades per side (TOP: 3 splayed; SIDE: up/down fan)
# ----------------------------------------------------------------------------
tb = spine_pt(0.97)
TF = {"TailFan": 1.0}
for ang, ln in ((14, 3.8), (32, 3.3), (52, 2.6)):
    a = math.radians(ang)
    tip = tb + Vector((math.sin(a) * ln, math.cos(a) * ln, 0.05))
    blade(tb + X * 0.12, tip, Y, 1.7, 0.24, TF, bulge=0.4)
for ang, ln in ((28, 3.1), (58, 2.3), (-30, 2.2)):
    a = math.radians(ang)
    tip = tb + Vector((0.35, math.cos(a) * ln, math.sin(a) * ln))
    blade(tb + X * 0.14 + Z * 0.1, tip, Y, 1.6, 0.24, TF, bulge=0.4)

HEAD_S = 1.15
PIVOT = Vector((0, 0.9, 1.1))
HEAD_OFF = Vector((0, -0.25, 1.6))   # head sits high on the body front, level with the back (SIDE view)


def hs(v):
    return PIVOT + (Vector(v) - PIVOT) * HEAD_S + HEAD_OFF


hi, ji = B.gi("Head"), B.gi("Jaw")
for v in B.bm.verts:
    d = v[B.deform]
    if d.get(hi, 0) > 0.999 or d.get(ji, 0) > 0.999:
        v.co = hs(v.co)
HINGE = hs(HINGE)
_jp = jaw_p


def jaw_p(y, z):  # noqa: F811  (scaled jaw points for the rig)
    return hs(_jp(y, z))


# ----------------------------------------------------------------------------
# object: bisect to right half, materials, bake, mirror
# ----------------------------------------------------------------------------
bm = B.bm
bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(1, 0, 0), clear_inner=True)
bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-4)
for v in bm.verts:
    if abs(v.co.x) < 1e-4:
        v.co.x = 0.0
mesh = bpy.data.meshes.new("Drake")
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new("Drake", mesh)
scene.collection.objects.link(obj)
for g in B.groups:
    obj.vertex_groups.new(name=g)
for g in list(B.groups):
    if g.endswith("_R"):
        obj.vertex_groups.new(name=g[:-2] + "_L")
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
for p in mesh.polygons:
    p.use_smooth = False
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")


def img(name, cs="sRGB"):
    im = bpy.data.images.load(os.path.join(TILES, name), check_existing=True)
    im.colorspace_settings.name = cs
    return im


def src_mat(name, tile=None, flat=None, box=None, bump=0.9):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.name = "BSDF"
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.name = "EMIT"
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    if flat is not None:
        bsdf.inputs["Base Color"].default_value = (*flat, 1)
        emit.inputs["Color"].default_value = (*flat, 1)
        return m
    if box:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        ab = nt.nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (box,) * 3
        nt.links.new(tc.outputs["Object"], sep.inputs[0])
        nt.links.new(sep.outputs[0], ab.inputs[0])
        nt.links.new(ab.outputs[0], comb.inputs[0])
        nt.links.new(sep.outputs[1], comb.inputs[1])
        nt.links.new(sep.outputs[2], comb.inputs[2])
        nt.links.new(comb.outputs[0], mp.inputs[0])
        vec = mp.outputs[0]
    else:
        un = nt.nodes.new("ShaderNodeUVMap")
        un.uv_map = "tile"
        vec = un.outputs[0]
    ct = nt.nodes.new("ShaderNodeTexImage")
    ct.image = img(f"{tile}_color.png")
    nt.links.new(vec, ct.inputs[0])
    nt.links.new(ct.outputs[0], bsdf.inputs["Base Color"])
    nt.links.new(ct.outputs[0], emit.inputs["Color"])
    if tile != "eye":
        ht = nt.nodes.new("ShaderNodeTexImage")
        ht.image = img(f"{tile}_height.png", "Non-Color")
        nt.links.new(vec, ht.inputs[0])
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump
        bp.inputs["Distance"].default_value = 0.05
        nt.links.new(ht.outputs[0], bp.inputs["Height"])
        nt.links.new(bp.outputs[0], bsdf.inputs["Normal"])
    if box:
        for n_ in nt.nodes:
            if n_.type == "TEX_IMAGE":
                n_.projection = "BOX"
                n_.projection_blend = 0.15
    return m


for m in [src_mat("SRC_body", "body", box=0.5), src_mat("SRC_belly", "belly", box=0.5),
          src_mat("SRC_fin", "fin"), src_mat("SRC_tooth", flat=(0.95, 0.90, 0.84)),
          src_mat("SRC_mouth", flat=(0.012, 0.28, 0.30)), src_mat("SRC_eye", "eye"),
          src_mat("SRC_teal", "teal", box=0.6)]:
    obj.data.materials.append(m)

atlas = mesh.uv_layers.new(name="UVMap")
mesh.uv_layers.active = atlas
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(58), island_margin=0.005, area_weight=0.0, correct_aspect=True)
bpy.ops.uv.pack_islands(margin=0.003, rotate=True)
bpy.ops.object.mode_set(mode="OBJECT")

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16
scene.render.bake.margin = 6
color_img = bpy.data.images.new("Drake_Color", ATLAS, ATLAS)
normal_img = bpy.data.images.new("Drake_Normal", ATLAS, ATLAS)
normal_img.colorspace_settings.name = "Non-Color"


def set_targets(image, emit):
    for m in obj.data.materials:
        nt = m.node_tree
        n = nt.nodes.get("BAKE") or nt.nodes.new("ShaderNodeTexImage")
        n.name = "BAKE"
        n.image = image
        un = nt.nodes.get("BAKEUV") or nt.nodes.new("ShaderNodeUVMap")
        un.name = "BAKEUV"
        un.uv_map = "UVMap"
        nt.links.new(un.outputs[0], n.inputs[0])
        nt.nodes.active = n
        out = [x for x in nt.nodes if x.type == "OUTPUT_MATERIAL"][0]
        nt.links.new((nt.nodes["EMIT"] if emit else nt.nodes["BSDF"]).outputs[0], out.inputs[0])


set_targets(color_img, True)
bpy.ops.object.bake(type="EMIT", uv_layer="UVMap")
set_targets(normal_img, False)
scene.cycles.samples = 4
bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT", uv_layer="UVMap")
color_path = os.path.join(TEX, "Drake_Color.png")
normal_path = os.path.join(TEX, "Drake_Normal.png")
for im, fill in ((color_img, (0.004, 0.055, 0.73)), (normal_img, (0.5, 0.5, 1.0))):
    px = np.empty(ATLAS * ATLAS * 4, np.float32)
    im.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    px[px[:, :3].sum(1) < 1e-6, :3] = fill
    im.pixels.foreach_set(px.ravel())
for im, p in ((color_img, color_path), (normal_img, normal_path)):
    im.filepath_raw = p
    im.file_format = "PNG"
    im.save()

final = bpy.data.materials.new("Drake")
final.use_nodes = True
nt = final.node_tree
bsdf = nt.nodes["Principled BSDF"]
ct = nt.nodes.new("ShaderNodeTexImage")
ct.image = bpy.data.images.load(color_path)
nm = nt.nodes.new("ShaderNodeTexImage")
nm.image = bpy.data.images.load(normal_path)
nm.image.colorspace_settings.name = "Non-Color"
nmap = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(ct.outputs[0], bsdf.inputs["Base Color"])
nt.links.new(nm.outputs[0], nmap.inputs["Color"])
nt.links.new(nmap.outputs[0], bsdf.inputs["Normal"])
bsdf.inputs["Roughness"].default_value = 0.7
bsdf.inputs["Specular IOR Level"].default_value = 0.25
# spikes/fins get their own material slot -> split into their own skinned mesh so
# Roblox can give that MeshPart a different Material (e.g. Neon)
spike_faces = [p.index for p in mesh.polygons if p.material_index == M_FIN]
spike_mat = final.copy()
spike_mat.name = "Drake_Spikes"
obj.data.materials.clear()
obj.data.materials.append(final)
obj.data.materials.append(spike_mat)
for p in mesh.polygons:
    p.material_index = 0
for i in spike_faces:
    mesh.polygons[i].material_index = 1
mesh.uv_layers.remove(mesh.uv_layers["tile"])

mir = obj.modifiers.new("Mirror", "MIRROR")
mir.use_axis = (True, False, False)
mir.use_mirror_merge = True
mir.merge_threshold = 1e-3
mir.use_mirror_vertex_groups = True
bpy.ops.object.modifier_apply(modifier="Mirror")
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.mesh.separate(type="MATERIAL")
bpy.ops.object.mode_set(mode="OBJECT")
spikes = [o for o in bpy.context.selected_objects if o is not obj][0]
if spikes.data.materials[0].name != "Drake_Spikes":   # separate may keep either half on the original
    obj, spikes = spikes, obj
spikes.name, spikes.data.name = "Drake_Spikes", "Drake_Spikes"
obj.name, obj.data.name = "Drake", "Drake"
for o, m in ((obj, "Drake"), (spikes, "Drake_Spikes")):
    o.data.materials.clear()
    o.data.materials.append(bpy.data.materials[m])
mesh = obj.data
MESHES = [obj, spikes]
TRIS = 0
for o in MESHES:
    o.data.calc_loop_triangles()
    TRIS += len(o.data.loop_triangles)
print("TRIS", TRIS, "spike tris", len(spikes.data.loop_triangles))
if TRIS >= 5000:
    raise SystemExit(f"triangle budget exceeded: {TRIS}")

# ----------------------------------------------------------------------------
# armature (rest = straight, flat)
# ----------------------------------------------------------------------------
arm_data = bpy.data.armatures.new("DrakeRig")
rig = bpy.data.objects.new("DrakeRig", arm_data)
scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones


def bone(name, head, tail, parent=None, connect=False):
    b = eb.new(name)
    b.head, b.tail = Vector(head), Vector(tail)
    b.align_roll(Z if abs((b.tail - b.head).normalized().dot(Z)) < 0.9 else Y)
    if parent:
        b.parent = eb[parent]
        b.use_connect = connect
    return b


bone("Root", (0, spine_pt(0.22).y, 0), (0, spine_pt(0.22).y, 1.0))
bone("Chest", spine_pt(0.18), spine_pt(0.26), "Root")
bone("Neck1", spine_pt(0.18), spine_pt(0.09), "Chest")
bone("Neck2", spine_pt(0.09), spine_pt(0.0), "Neck1", True)
bone("Head", hs((0, 0.8, 1.4)), hs((0, -4.2, 1.6)), "Neck2")
bone("Jaw", HINGE, jaw_p(-3.5, 0), "Head")
prev = "Chest"
for j in range(3, len(SP_N)):
    bone(SP_N[j], spine_pt(SP_T[j]), spine_pt(SP_T[j + 1]), prev, prev != "Chest")
    prev = SP_N[j]
bone("TailFan", spine_pt(1.0), spine_pt(1.0) + Y * 2.5, "Tail4", True)
for side, sx in (("R", 1), ("L", -1)):
    for name, h, t, par in LIMB_BONES:
        nm_ = name[:-2] + "_" + side
        par_ = par if not par.endswith("_R") else par[:-2] + "_" + side
        hh, tt = h.copy(), t.copy()
        hh.x *= sx
        tt.x *= sx
        bone(nm_, hh, tt, par_)
bpy.ops.object.mode_set(mode="OBJECT")
for o in MESHES:
    o.parent = rig
    mod = o.modifiers.new("Armature", "ARMATURE")
    mod.object = rig
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.vertex_group_limit_total(limit=4)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)


# ----------------------------------------------------------------------------
# poses & animations  (rotations given about armature-space axes at rest)
# ----------------------------------------------------------------------------
def rw(pb, axis, deg):
    M = pb.bone.matrix_local.to_3x3()
    q = (M.inverted() @ Matrix.Rotation(math.radians(deg), 3, axis) @ M).to_quaternion()
    pb.rotation_quaternion = q @ pb.rotation_quaternion


def P(n):
    return rig.pose.bones[n]


def ref_pose():
    """The reference sheet pose: neck raised in an S, head level, jaw wide, tail tip up."""
    rw(P("Neck1"), X, -26)   # forward-pointing bones: negative X raises (chest lifts off the ground)
    rw(P("Neck2"), X, -14)
    rw(P("Head"), X, 38)     # nose tipped down ~12 deg as in the SIDE view
    rw(P("Jaw"), X, 6)
    rw(P("Chest"), X, 2)
    for n, d in (("Spine1", 3), ("Spine2", 2), ("Spine3", -3), ("Spine4", -3), ("Spine5", -1), ("Tail1", 2),
                 ("Tail2", 3), ("Tail3", 5), ("Tail4", 7), ("TailFan", 8)):
        rw(P(n), X, d)
    for side, s in (("R", 1), ("L", -1)):
        rw(P(f"Limb1_1_{side}"), Z, -8 * s)
        for n in (2, 3, 4):
            rw(P(f"Fin{n}_{side}"), Y, 18 * s)


def reset():
    for pb in rig.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)


def idle(ph):
    ref_pose()
    br = math.sin(ph)
    rw(P("Neck1"), X, -2.5 * br)
    rw(P("Neck2"), X, -1.5 * math.sin(ph - 0.5))
    rw(P("Head"), X, 2.5 * math.sin(ph - 1.0))
    rw(P("Head"), Z, 3 * math.sin(ph * 1 + 0.3))
    rw(P("Jaw"), X, 5 * (0.5 + 0.5 * math.sin(ph * 2)))
    P("Root").location = (0, 0.04 * br, 0)
    for k, n in enumerate(["Spine3", "Spine4", "Spine5", "Tail1", "Tail2", "Tail3", "Tail4", "TailFan"]):
        rw(P(n), Z, (2 + k * 0.9) * math.sin(ph - 0.6 * k))
    for side, s in (("R", 1), ("L", -1)):
        off = 0 if side == "R" else 0.8
        rw(P(f"Limb1_1_{side}"), Y, 4 * s * math.sin(ph + off))
        for i, n in enumerate((2, 3, 4)):
            rw(P(f"Fin{n}_{side}"), Z, 8 * s * math.sin(ph * 2 - i * 0.7 + off))


def walk(ph):
    ref_pose()
    chain = ["Chest", "Spine1", "Spine2", "Spine3", "Spine4", "Spine5", "Tail1", "Tail2", "Tail3", "Tail4", "TailFan"]
    for k, n in enumerate(chain):
        rw(P(n), Z, (5 + 1.7 * k) * math.sin(ph - 0.75 * k))
    rw(P("Neck1"), Z, -5 * math.sin(ph + 0.75))    # keep the head steady against the slither
    rw(P("Neck2"), Z, -3 * math.sin(ph + 1.5))
    rw(P("Head"), X, 3 * math.sin(2 * ph))
    rw(P("Jaw"), X, 3 * math.sin(2 * ph + 1))
    P("Root").location = (0, 0.08 * math.cos(2 * ph), 0)
    for side, s in (("R", 1), ("L", -1)):
        p = ph + (0 if side == "R" else math.pi)
        rw(P(f"Limb1_1_{side}"), Z, 28 * s * math.sin(p))                # paddle fore/aft
        rw(P(f"Limb1_1_{side}"), Y, -14 * s * max(0.0, math.cos(p)))     # lift on the return stroke
        rw(P(f"Limb1_2_{side}"), Y, 10 * s * math.sin(p - 0.8))
        for i, n in enumerate((2, 3, 4)):
            rw(P(f"Fin{n}_{side}"), Z, 22 * s * math.sin(p - 0.9 * (i + 1)))


def bake_action(name, frames, fn, step=2):
    act = bpy.data.actions.new(name)
    rig.animation_data_create()
    rig.animation_data.action = act
    for f in range(0, frames + 1, step):
        reset()
        fn(2 * math.pi * f / max(frames, 1))
        for pb in rig.pose.bones:
            pb.keyframe_insert("rotation_quaternion", frame=f + 1)
            pb.keyframe_insert("location", frame=f + 1)
    act.frame_range = (1, max(frames + 1, 2))
    act.use_frame_range = True
    act.use_cyclic = frames > 0
    act.use_fake_user = True
    return act


ref_act = bake_action("RefPose", 0, lambda ph: ref_pose(), step=1)
idle_act = bake_action("Idle", 90, idle)
walk_act = bake_action("Walk", 40, walk)
for act in (idle_act, walk_act):
    tr = rig.animation_data.nla_tracks.new()
    tr.name = act.name
    tr.strips.new(act.name, 1, act)
    tr.mute = True
rig.animation_data.action = None
reset()

bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "Drake.blend"), compress=True)


def export_fbx(path, action):
    rig.animation_data.action = action
    reset()
    if action:
        scene.frame_start, scene.frame_end = int(action.frame_range[0]), int(action.frame_range[1])
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for o in MESHES:
        o.select_set(True)
    bpy.ops.export_scene.fbx(
        filepath=path, use_selection=True, object_types={"MESH", "ARMATURE"},
        apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS", axis_forward="-Z", axis_up="Y",
        use_mesh_modifiers=False, mesh_smooth_type="FACE", add_leaf_bones=False,
        primary_bone_axis="Y", secondary_bone_axis="X", armature_nodetype="NULL",
        bake_anim=action is not None, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0,
        path_mode="COPY", embed_textures=True)


export_fbx(os.path.join(EXPORT, "Drake_Rig.fbx"), None)
export_fbx(os.path.join(EXPORT, "Drake_Idle.fbx"), idle_act)
export_fbx(os.path.join(EXPORT, "Drake_Walk.fbx"), walk_act)
rig.animation_data.action = None
reset()
ref_act.use_fake_user = True
bpy.ops.export_scene.gltf(filepath=os.path.join(EXPORT, "Drake.glb"), export_format="GLB", use_selection=True,
                          export_yup=True, export_animations=True, export_animation_mode="ACTIONS",
                          export_skins=True, export_apply=False)
print("BONES", len(arm_data.bones), "TRIS", TRIS, "VERTS", len(mesh.vertices))
