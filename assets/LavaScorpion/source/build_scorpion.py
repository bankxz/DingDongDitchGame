"""Build the rigged Lava Scorpion in Blender (run: python3 build_scorpion.py  -- uses the `bpy` module).

Conventions: Z up, scorpion faces -Y (Blender FRONT view), 1 unit = 1 m. Ground at Z=0.
Every block is a 12-tri box bound 100% to one bone (rigid, Roblox-friendly skinning).
Studs are TEXTURE ONLY (atlas from make_textures.py); nothing stud-shaped is modelled.
"""
import json
import math
import os

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
TEX = os.path.join(ROOT, "textures")
ATLAS = json.load(open(os.path.join(HERE, "atlas_regions.json")))
P = 0.2  # world size of one stud

# ------------------------------------------------------------------ helpers
BONES = {}   # name -> (head, tail, parent)
BOXES = []   # dicts


def V(*a):
    return Vector(a)


def bone(name, head, tail, parent=None):
    BONES[name] = (Vector(head), Vector(tail), parent)


def frame(d, up=(0, 0, 1)):
    """Rotation whose local +Y = d and local +Z is as close to `up` as possible."""
    y = Vector(d).normalized()
    u = Vector(up)
    z = u - y * u.dot(y)
    if z.length < 1e-4:
        u = Vector((1, 0, 0)) if abs(y.x) < 0.9 else Vector((0, 1, 0))
        z = u - y * u.dot(y)
    z.normalize()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed()


def box(bone_name, center, size, rot=None, taper=(1.0, 1.0), tip_off=(0.0, 0.0), kind="R", crack=False):
    """kind: 'R' rock (auto stud count) | 'H0'..'H3' hot gradient | 'EYE'."""
    BOXES.append(dict(bone=bone_name, c=Vector(center), s=Vector(size), r=rot or Matrix.Identity(3),
                      taper=taper, off=tip_off, kind=kind, crack=crack))


def seg(bone_name, p0, p1, w, h, kind="R", taper=(1.0, 1.0), up=(0, 0, 1), ext=0.03, split=1, kinds=None,
        tapers=None):
    """Blocks filling the segment p0->p1 (optionally split into `split` cubes along its length)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    R = frame(d, up)
    for i in range(split):
        a = p0 + d * (i / split)
        b = p0 + d * ((i + 1) / split)
        c = (a + b) / 2
        k = kinds[i] if kinds else kind
        t = tapers[i] if tapers else (taper if i == split - 1 else (1.0, 1.0))
        # width shrink along a tapered multi-cube segment
        box(bone_name, c, (w, L / split + ext, h), R, t, kind=k)


def stepped(bone_name, pts, widths, kinds, tip_w=0.03, flat=0.9):
    """Blocky claw/stinger: stacked untapered cubes along a curve, last piece tapers to a point."""
    n = len(pts) - 1
    for i in range(n):
        d = pts[i + 1] - pts[i]
        w = widths[i]
        t = (tip_w / w, tip_w / w) if i == n - 1 else (1.0, 1.0)
        box(bone_name, (pts[i] + pts[i + 1]) / 2, (w, d.length + (0.05 if i < n - 1 else 0.02), w * flat),
            frame(d), t, kind=kinds[i])


import random
RNG = random.Random(11)


def cluster(bone_name, center, R, counts, cube, kinds=None, jitter=0.03, grow=1.06):
    """Grid of jittered cubes (the reference's 'cube cluster' look). kinds(ix,iy,iz)->kind."""
    nx, ny, nz = counts
    for ix in range(nx):
        for iy in range(ny):
            for iz in range(nz):
                if 0 < ix < nx - 1 and 0 < iy < ny - 1 and 0 < iz < nz - 1:
                    continue  # hidden interior cube
                off = Vector(((ix - (nx - 1) / 2) * cube, (iy - (ny - 1) / 2) * cube, (iz - (nz - 1) / 2) * cube))
                off += Vector([RNG.uniform(-jitter, jitter) for _ in range(3)])
                sz = cube * grow * RNG.uniform(0.94, 1.06)
                k = kinds(ix, iy, iz) if kinds else "D"
                box(bone_name, Vector(center) + R @ off, (sz, sz, sz), R, kind=k)


def bumps(bone_name, center, size, R, n, cube=0.22, faces=("top", "side"), seed=0):
    """Scatter protruding cubes over the visible faces of a slab."""
    r = random.Random(seed)
    sx, sy, sz = size
    for _ in range(n):
        f = r.choice(faces)
        if f == "top":
            p = Vector((r.uniform(-sx / 2 + cube / 2, sx / 2 - cube / 2), r.uniform(-sy / 2 + cube / 2, sy / 2 - cube / 2),
                        sz / 2 + cube * r.uniform(-0.3, -0.1)))
        else:
            sgn = r.choice((1, -1))
            p = Vector((sgn * (sx / 2 + cube * r.uniform(-0.35, -0.15)), r.uniform(-sy / 2 + cube / 2, sy / 2 - cube / 2),
                        r.uniform(-sz / 2 + cube / 2, sz / 2 - cube / 2)))
        c = cube * r.uniform(0.9, 1.1)
        box(bone_name, Vector(center) + R @ p, (c, c, c), R, kind="D")


def mirror_x(p, s):
    return Vector((p[0] * s, p[1], p[2]))


# ------------------------------------------------------------------ skeleton + blocks
bone("Root", (0, 0, 0), (0, -0.5, 0))
bone("Body", (0, 0.45, 0.85), (0, -0.55, 0.85), "Root")

# --- body: head, three carapace plates, belly, side lumps  (Y -1.25 .. 1.24, top ~1.37, bottom 0.42)
B = "Body"
box(B, (0, -1.1, 0.7), (0.56, 0.3, 0.46), kind="J")                     # head front block (eyes)
box(B, (0, -1.02, 1.03), (0.5, 0.36, 0.22), kind="J")                   # head top block
for s in (1, -1):
    box(B, (s * 0.34, -1.05, 0.72), (0.2, 0.34, 0.36), kind="J")       # cheeks
    box(B, (s * 0.14, -1.14, 0.42), (0.2, 0.2, 0.14), kind="J")        # mandible cubes
    eye_rot = Matrix.Rotation(math.radians(-24 * s), 3, "Y")
    box(B, (s * 0.15, -1.255, 0.66), (0.15, 0.03, 0.085), eye_rot, kind="EYE")

box(B, (0, -0.47, 1.2), (0.96, 0.92, 0.3), crack=True)        # front plate (top)
box(B, (0, -0.47, 0.8), (1.04, 0.96, 0.6), kind="J")                    # front core
box(B, (0, 0.33, 1.24), (0.84, 0.62, 0.3), crack=True)        # mid plate (top)
box(B, (0, 0.33, 0.82), (1.06, 0.66, 0.6), kind="J")                    # mid core
box(B, (0, 0.95, 1.18), (0.74, 0.56, 0.28), crack=True)       # rear plate (top)
box(B, (0, 0.95, 0.8), (0.92, 0.58, 0.56), kind="J")                    # rear core
box(B, (0, 0.0, 0.5), (0.8, 2.1, 0.16))                       # belly
for s in (1, -1):
    for j, y in enumerate((-0.75, -0.3, 0.15, 0.6, 1.0)):
        box(B, (s * 0.56, y, 0.86), (0.18, 0.28, 0.3), kind="D")  # side lumps
        if j % 2 == 0:
            box(B, (s * 0.5, y + 0.2, 0.6), (0.14, 0.24, 0.2), kind="D")
    box(B, (s * 0.24, -0.62, 1.4), (0.24, 0.24, 0.1))        # raised top cubes
    box(B, (s * 0.2, 0.18, 1.44), (0.22, 0.22, 0.1))
    box(B, (s * 0.46, -0.2, 1.1), (0.14, 0.3, 0.26))
box(B, (0, 0.9, 1.37), (0.26, 0.26, 0.1))
I3 = Matrix.Identity(3)
bumps(B, (0, -0.47, 1.2), (0.96, 0.92, 0.3), I3, 6, 0.24, seed=1)
bumps(B, (0, 0.33, 1.24), (0.84, 0.62, 0.3), I3, 5, 0.22, seed=2)
bumps(B, (0, 0.95, 1.18), (0.74, 0.56, 0.28), I3, 4, 0.22, seed=3)
bumps(B, (0, -0.47, 0.8), (1.04, 0.96, 0.6), I3, 6, 0.24, faces=("side",), seed=4)
bumps(B, (0, 0.33, 0.82), (1.06, 0.66, 0.6), I3, 5, 0.24, faces=("side",), seed=5)
bumps(B, (0, 0.95, 0.8), (0.92, 0.58, 0.56), I3, 4, 0.22, faces=("side",), seed=6)
bumps(B, (0, -1.02, 1.03), (0.5, 0.36, 0.22), I3, 2, 0.18, faces=("top",), seed=7)

# --- tail: 6 segments (each 2 cube columns -> glowing centre seam) + stinger
TJ = [V(0, 1.12, 1.22), V(0, 1.42, 1.47), V(0, 1.58, 1.87), V(0, 1.47, 2.27),
      V(0, 1.18, 2.5), V(0, 0.8, 2.56), V(0, 0.45, 2.43)]
TW = [0.54, 0.52, 0.5, 0.48, 0.46, 0.44]
parent = "Body"
for i in range(6):
    n = f"Tail{i + 1}"
    bone(n, TJ[i], TJ[i + 1], parent)
    parent = n
    d = TJ[i + 1] - TJ[i]
    R = frame(d, V(0, -d.z, d.y))      # local X = lateral, so the 2 columns split left/right
    c = (TJ[i] + TJ[i + 1]) / 2
    L = d.length + 0.07
    w = TW[i]
    for sx_ in (1, -1):
        box(n, c + R @ V(sx_ * w / 4, RNG.uniform(-0.015, 0.015), 0), (w / 2 + 0.01, L, w), R)
    # side knobs (lumpy cube-cluster silhouette)
    for sx_ in (1, -1):
        box(n, c + R @ V(sx_ * (w / 2 + 0.03), 0.03 * sx_, RNG.uniform(-0.1, 0.1)), (0.1, L * 0.5, w * 0.45), R,
            kind="D")

bone("Stinger", TJ[6], V(0, 0.05, 1.6), "Tail6")
ST = "Stinger"
bulb_d = V(0, -0.34, -0.2)
Rb = frame(bulb_d, V(0, -0.2, 0.34))
cb = TJ[6] + bulb_d * 0.5
box(ST, cb, (0.46, 0.46, 0.46), Rb, kind="H0")
box(ST, cb + Rb @ V(0, 0.02, 0.22), (0.34, 0.3, 0.1), Rb, kind="H0")
h0 = TJ[6] + bulb_d
pts = [h0, h0 + V(0, -0.09, -0.2), h0 + V(0, -0.15, -0.42), h0 + V(0, -0.17, -0.64), h0 + V(0, -0.14, -0.86)]
stepped(ST, pts, [0.4, 0.34, 0.27, 0.2], ["H1", "H1", "H2", "H2"], flat=1.0)

# --- pincers (big hand, long outer finger curving in & down, shorter movable inner finger)
for s, side in ((1, "L"), (-1, "R")):
    S0, S1, S2, S3 = V(s * 0.5, -0.85, 0.85), V(s * 0.8, -0.8, 0.9), V(s * 0.93, -0.95, 0.78), V(s * 0.98, -1.95, 0.72)
    bone(f"Arm1.{side}", S0, S1, "Body")
    bone(f"Arm2.{side}", S1, S2, f"Arm1.{side}")
    bone(f"Hand.{side}", S2, S3, f"Arm2.{side}")
    seg(f"Arm1.{side}", S0, S1, 0.3, 0.32, ext=0.14, kind="J")
    seg(f"Arm2.{side}", S1, S2, 0.3, 0.3, ext=0.14, kind="J")
    box(f"Arm2.{side}", S1 + V(0, 0, 0.14), (0.28, 0.28, 0.14))
    H = f"Hand.{side}"
    Rh = frame(S3 - S2)
    # hand = 2 x 3 x 2 cluster of studded cubes; front-bottom row lava-lit like the pincer close-up
    cluster(H, V(s * 0.95, -1.44, 0.8), Rh, (2, 3, 2), 0.34,
            kinds=lambda ix, iy, iz: "H0" if (iy == 2 and iz == 0 and ix == (1 if s > 0 else 0)) else ("J" if iy == 0 else "D"))
    box(H, V(s * 0.95, -1.42, 0.8), (0.6, 0.96, 0.6), Rh)                    # filler core (no holes)
    cluster(H, V(s * 0.92, -1.3, 1.16), Rh, (2, 2, 1), 0.26)                 # top ridge cubes
    box(H, V(s * 1.3, -1.5, 0.84), (0.16, 0.3, 0.3), Rh)                     # outer knuckle
    box(H, V(s * 1.28, -1.2, 0.72), (0.14, 0.26, 0.26), Rh)
    box(H, V(s * 0.6, -1.3, 0.9), (0.12, 0.28, 0.28), Rh)                    # inner knuckle
    F = [V(s * 1.12, -1.96, 0.78), V(s * 1.14, -2.22, 0.7), V(s * 1.08, -2.46, 0.58), V(s * 0.92, -2.68, 0.42),
         V(s * 0.6, -2.86, 0.22)]
    stepped(H, F, [0.48, 0.42, 0.34, 0.26], ["H0", "H1", "H1", "H2"])
    G = [V(s * 0.74, -1.95, 0.6), V(s * 0.72, -2.18, 0.54), V(s * 0.66, -2.4, 0.44), V(s * 0.56, -2.58, 0.3)]
    bone(f"Finger.{side}", G[0], G[3], H)
    stepped(f"Finger.{side}", G, [0.34, 0.27, 0.2], ["H1", "H1", "H2"])

# --- 8 legs (4 per side): femur up/out to a high knee, tibia down/out, glowing foot
LEG_Y = [-0.5, 0.05, 0.6, 1.0]
LEG_A = [25, 5, -12, -38]          # degrees, + = angled forward
for s, side in ((1, "L"), (-1, "R")):
    for i in range(4):
        a = math.radians(LEG_A[i])
        dirh = V(s * math.cos(a), -math.sin(a), 0)
        Bp = V(s * 0.55, LEG_Y[i], 0.85)
        K = Bp + dirh * 0.58 + V(0, 0, 0.3)
        A = K + dirh * 0.6 + V(0, 0, -0.82)
        Fp = A + dirh * 0.1 + V(0, 0, -0.3)
        n = f"Leg{i + 1}"
        bone(f"{n}_1.{side}", Bp, K, "Body")
        bone(f"{n}_2.{side}", K, A, f"{n}_1.{side}")
        bone(f"{n}_3.{side}", A, Fp, f"{n}_2.{side}")
        box(f"{n}_1.{side}", Bp, (0.28, 0.28, 0.28), frame(dirh))         # coxa cube
        seg(f"{n}_1.{side}", Bp, K, 0.31, 0.31, split=2, ext=0.02, kind="J")
        box(f"{n}_1.{side}", K, (0.33, 0.33, 0.33), frame(dirh))             # knee cube
        seg(f"{n}_2.{side}", K, A, 0.29, 0.29, split=3, ext=0.02, kinds=["J", "J", "J"], up=dirh)
        seg(f"{n}_3.{side}", A, Fp + (Fp - A).normalized() * 0.02, 0.28, 0.28, split=2, ext=0.01,
            kinds=["H1", "H2"], tapers=[(1, 1), (0.55, 0.55)], up=dirh)


# ------------------------------------------------------------------ mesh generation
def pick_cell(kind, nu, nv, crack, face_is_top):
    if kind not in ("R", "J", "D"):
        return kind
    nu, nv = max(1, min(3, nu)), max(1, min(3, nv))
    if crack and face_is_top and (nu, nv) in ((2, 2), (3, 3), (3, 2), (2, 3)):
        return {(2, 2): "R22C", (3, 3): "R33C"}.get((nu, nv), "R32C")
    return f"{kind}{nu}{nv}"


verts, faces, uvs, face_bone = [], [], [], []
# local corner lookup: (sx, sy, sz) signs
FACES = [  # (normal axis, sign, u axis, v axis)
    (0, 1, 2, 1), (0, -1, 2, 1), (2, 1, 0, 1), (2, -1, 0, 1), (1, 1, 0, 2), (1, -1, 0, 2)]
for bx in BOXES:
    sx, sy, sz = bx["s"]
    tx, tz = bx["taper"]

    def corner(cs):
        x, y, z = cs[0] * sx / 2, cs[1] * sy / 2, cs[2] * sz / 2
        if cs[1] > 0:
            x, z = x * tx + bx["off"][0], z * tz + bx["off"][1]
        return bx["c"] + bx["r"] @ Vector((x, y, z))

    center = bx["c"]
    for ax, sign, ua, va in FACES:
        quad = []
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            cs = [0, 0, 0]
            cs[ax] = sign
            cs[ua] = a
            cs[va] = b
            quad.append((tuple(cs), (a + 1) / 2, (b + 1) / 2))
        pts = [corner(q[0]) for q in quad]
        nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        fc = sum(pts, Vector()) / 4
        if nrm.dot(fc - center) < 0:
            quad.reverse()
            pts.reverse()
        # stud counts from face size
        du = ((pts[1] - pts[0]).length + (pts[2] - pts[3]).length) / 2
        dv = ((pts[3] - pts[0]).length + (pts[2] - pts[1]).length) / 2
        # quad is ordered (u,v) = (0,0),(1,0),(1,1),(0,1) possibly reversed; recompute sizes by uv
        uvq = [(q[1], q[2]) for q in quad]
        eu = [pts[k] for k in range(4)]
        size_u = size_v = 0
        for k in range(4):
            kn = (k + 1) % 4
            L = (eu[kn] - eu[k]).length
            if abs(uvq[kn][0] - uvq[k][0]) > 0.5:
                size_u += L / 2
            else:
                size_v += L / 2
        wn = (bx["r"] @ Vector([1 if i == ax else 0 for i in range(3)]) * sign)
        cell = pick_cell(bx["kind"], round(size_u / P), round(size_v / P), bx["crack"], wn.z > 0.8)
        u0, v0, u1, v1 = ATLAS[cell]
        pad = 2 / 1024
        base = len(verts)
        for p, (uu, vv) in zip(pts, uvq):
            verts.append(p)
            uvs.append((u0 + pad + uu * (u1 - u0 - 2 * pad), v0 + pad + vv * (v1 - v0 - 2 * pad)))
        faces.append((base, base + 1, base + 2, base + 3))
        face_bone.append(bx["bone"])

# ------------------------------------------------------------------ scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"

# armature
arm_data = bpy.data.armatures.new("ARM-LavaScorpion")
arm = bpy.data.objects.new("LavaScorpion", arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
for name, (h, t, par) in BONES.items():
    eb = arm_data.edit_bones.new(name)
    eb.head, eb.tail = h, t
    # roll so bone Z points up (or back for vertical bones) for predictable local axes
    eb.align_roll(Vector((0, 0, 1)) if abs((t - h).normalized().z) < 0.9 else Vector((0, 1, 0)))
for name, (h, t, par) in BONES.items():
    if par:
        eb = arm_data.edit_bones[name]
        eb.parent = arm_data.edit_bones[par]
        eb.use_connect = False
bpy.ops.object.mode_set(mode="OBJECT")
arm_data.display_type = "STICK"

# mesh
me = bpy.data.meshes.new("GEO-LavaScorpion")
me.from_pydata([tuple(v) for v in verts], [], faces)
me.update()
uvl = me.uv_layers.new(name="UVMap")
for poly in me.polygons:
    for li in poly.loop_indices:
        uvl.data[li].uv = uvs[me.loops[li].vertex_index]
obj = bpy.data.objects.new("GEO-LavaScorpion", me)
scene.collection.objects.link(obj)
for name in BONES:
    obj.vertex_groups.new(name=name)
groups = {}
for fi, poly in enumerate(me.polygons):
    groups.setdefault(face_bone[fi], []).extend(poly.vertices)
for name, vs in groups.items():
    obj.vertex_groups[name].add(list(set(vs)), 1.0, "REPLACE")
obj.parent = arm
mod = obj.modifiers.new("Armature", "ARMATURE")
mod.object = arm
for p in me.polygons:
    p.use_smooth = False

# material
mat = bpy.data.materials.new("MAT-LavaScorpion")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]


def teximg(fname, cs, loc):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(os.path.join(TEX, fname))
    n.image.colorspace_settings.name = cs
    n.interpolation = "Linear"
    n.location = loc
    return n


tc = teximg("LavaScorpion_Color.png", "sRGB", (-600, 300))
te = teximg("LavaScorpion_Emission.png", "sRGB", (-600, 0))
tn = teximg("LavaScorpion_Normal.png", "Non-Color", (-600, -300))
nm = nt.nodes.new("ShaderNodeNormalMap")
nm.inputs["Strength"].default_value = 1.0
nt.links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(te.outputs["Color"], bsdf.inputs["Emission Color"])
bsdf.inputs["Emission Strength"].default_value = 1.2
nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
bsdf.inputs["Roughness"].default_value = 0.75
bsdf.inputs["Specular IOR Level"].default_value = 0.12
obj.data.materials.append(mat)

tris = sum(len(p.vertices) - 2 for p in me.polygons)
print(f"BUILD boxes={len(BOXES)} faces={len(me.polygons)} tris={tris} verts={len(me.vertices)} bones={len(BONES)}")
out = os.path.join(ROOT, "LavaScorpion.blend")
bpy.ops.wm.save_as_mainfile(filepath=out, relative_remap=True)
print("saved", out)
