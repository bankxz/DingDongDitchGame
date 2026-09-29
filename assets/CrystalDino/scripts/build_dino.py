"""Build the CrystalDino (blocky crystal-backed quadruped) in Blender.

Run:  python3 build_dino.py            (uses the pip `bpy` module)
  or: blender -b -P build_dino.py

Produces ../CrystalDino.blend with:
  CrystalDino_Rig    armature (deform bones + IK controllers)
  CrystalDino_Body   skinned mesh, stud texture atlas
  CrystalDino_Glow   skinned mesh (crystals, eyes, mouth glow, glow cracks)
  actions Idle / Walk

Modelling units: 1 Blender unit = 1 block = 1 Roblox stud.
Spec coordinates are (x, s, z): s = distance back from the snout tip,
converted to Blender Y = s - S_OFF so the dino faces -Y (Roblox forward).
"""
import math
import os
import random

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEX = os.path.join(ROOT, "textures")
S_OFF = 14.0
Z_SCALE = 0.92  # measured reference back-height / length ratio
DENSITY = float(os.environ.get("DINO_DENSITY", "1.0"))
TRI_BUDGET = 4990

rng = random.Random(11)

# --------------------------------------------------------------------------
# UV atlas helpers (see make_textures.py for the layout)
# --------------------------------------------------------------------------
CELL = 64
REG = {"navy": (0, 0, 10, 16), "tan": (640, 0, 6, 9)}


def px(x, y):
    return (x / 1024.0, 1.0 - y / 1024.0)


def cell_uvs(mat, w, h):
    x0, y0, cols, rows = REG[mat]
    nu, nv = max(1, round(w)), max(1, round(h))
    swap = (nu > cols or nv > rows) and (nv <= cols and nu <= rows)
    if swap:
        nu, nv = nv, nu
    nu, nv = min(nu, cols), min(nv, rows)
    ci, cj = rng.randint(0, cols - nu), rng.randint(0, rows - nv)
    ux0, vy0 = x0 + ci * CELL, y0 + cj * CELL
    ux1, vy1 = ux0 + nu * CELL, vy0 + nv * CELL
    A, B, C, D = px(ux0, vy1), px(ux1, vy1), px(ux1, vy0), px(ux0, vy0)
    return [A, D, C, B] if swap else [A, B, C, D]


GLOW_UV = [px(662, 1000), px(746, 1000), px(746, 852), px(662, 852)]
MOUTH_UV = [px(900, 1016), px(1020, 1016), px(1020, 840), px(900, 840)]


# --------------------------------------------------------------------------
# primitive records
# --------------------------------------------------------------------------
PRIMS = []


def add_prim(verts, faces, group, bone, mirror):
    PRIMS.append(dict(verts=verts, faces=faces, group=group, bone=bone, mirror=mirror))


IDENT = lambda v: v


def rot_frame(pivot, axis, angle):
    R = Matrix.Rotation(angle, 3, axis)
    pv = Vector(pivot)
    return lambda v: pv + R @ (v - pv)


def seg_frame(p0, p1):
    """Local y runs from p0 to p1; local x = world x."""
    p0, p1 = Vector(p0), Vector(p1)
    a = (p1 - p0).normalized()
    X = Vector((1, 0, 0))
    X = (X - a * X.dot(a)).normalized()
    Z = X.cross(a)
    R = Matrix((X, a, Z)).transposed()
    return lambda v: p0 + R @ v


def dir_frame(origin, d):
    """Local +y along direction d, rooted at origin."""
    d = Vector(d).normalized()
    ref = Vector((1, 0, 0)) if abs(d.x) < 0.9 else Vector((0, 1, 0))
    X = (ref - d * ref.dot(d)).normalized()
    Z = X.cross(d)
    R = Matrix((X, d, Z)).transposed()
    o = Vector(origin)
    return lambda v: o + R @ v


FACES = {
    "+x": ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),
    "-x": ((0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)),
    "+y": ((1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)),
    "-y": ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
    "+z": ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
    "-z": ((0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)),
}
OPP = {"+x": "-x", "-x": "+x", "+y": "-y", "-y": "+y", "+z": "-z", "-z": "+z"}


def box(x0, x1, y0, y1, z0, z1, mat="navy", bone="Chest", frame=IDENT, skip=(), taper=(1, 1),
        group="body", mirror=False, uv=None):
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    idx, verts = {}, []
    for ix in (0, 1):
        for iy in (0, 1):
            for iz in (0, 1):
                x = x1 if ix else x0
                y = y1 if iy else y0
                z = z1 if iz else z0
                if iy:
                    x = cx + (x - cx) * taper[0]
                    z = cz + (z - cz) * taper[1]
                idx[(ix, iy, iz)] = len(verts)
                verts.append(Vector((x, y, z)))
    faces = []
    for name, cs in FACES.items():
        if name in skip:
            continue
        ids = [idx[c] for c in cs]
        w = (verts[ids[1]] - verts[ids[0]]).length
        h = (verts[ids[3]] - verts[ids[0]]).length
        if uv == "glow":
            uvs = GLOW_UV
        elif uv == "mouth":
            uvs = MOUTH_UV
        else:
            uvs = cell_uvs(mat, w, h)
        faces.append((tuple(ids), uvs))
    add_prim([frame(v) for v in verts], faces, group, bone, mirror)


def crystal(base, d, length, radius, bone, sides=None, sink=0.5, mirror=False, lean_twist=None):
    sides = sides or (5 if length > 1.6 else 4)
    d = Vector(d).normalized()
    t = d.orthogonal().normalized()
    b = d.cross(t)
    base0 = Vector(base) - d * sink
    rot0 = rng.uniform(0, math.tau) if lean_twist is None else lean_twist
    angs = [rot0 + k * math.tau / sides for k in range(sides)]
    ring0 = [base0 + (t * math.cos(a) + b * math.sin(a)) * radius for a in angs]
    midc = base0 + d * (sink + length * 0.58)
    ring1 = [midc + (t * math.cos(a) + b * math.sin(a)) * radius * 0.95 for a in angs]
    tip = base0 + d * (sink + length)
    verts = ring0 + ring1 + [tip]
    faces = []
    for k in range(sides):
        k1 = (k + 1) % sides
        c = (k + rng.randint(0, 5)) % 6
        u0, u1 = 640 + c * 64 + 3, 640 + c * 64 + 61
        faces.append(((k, k1, sides + k1, sides + k),
                      [px(u0, 830), px(u1, 830), px(u1, 690), px(u0, 690)]))
        faces.append(((sides + k, sides + k1, 2 * sides),
                      [px(u0, 690), px(u1, 690), px((u0 + u1) / 2, 579)]))
    add_prim(verts, faces, "glow", bone, mirror)


def pyramid(base, d, length, half, bone, mat="bone", mirror=False, sides=4, group="body"):
    """Tooth / claw / horn: open-based pyramid (no hidden base face)."""
    d = Vector(d).normalized()
    t = d.orthogonal().normalized()
    b = d.cross(t)
    base = Vector(base)
    ring = [base + (t * math.cos(a) + b * math.sin(a)) * half
            for a in [math.pi / 4 + k * math.tau / sides for k in range(sides)]]
    tip = base + d * length
    verts = ring + [tip]
    faces = []
    for k in range(sides):
        k1 = (k + 1) % sides
        if mat == "bone":
            uvs = [px(775, 1020), px(890, 1020), px(832, 838)]
        else:
            q = cell_uvs(mat, 1, 1)
            uvs = [q[0], q[1], ((q[2][0] + q[3][0]) / 2, q[2][1])]
        faces.append(((k, k1, sides), uvs))
    add_prim(verts, faces, group, bone, mirror)


# --------------------------------------------------------------------------
# surface block scatter (the lumpy voxel silhouette of the reference)
# --------------------------------------------------------------------------
def scatter(x0, x1, y0, y1, z0, z1, faces, bone, frame=IDENT, p=0.5, tan_p=0.15, taper=(1, 1),
            step=1.3, half=False, mirror=False, out=(0.2, 0.75), size=(0.9, 1.5), ylim=None):
    p *= DENSITY
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2

    def ext(y):
        f = (y - y0) / max(y1 - y0, 1e-6)
        sx = 1 + (taper[0] - 1) * f
        sz = 1 + (taper[1] - 1) * f
        return (cx - (cx - x0) * sx, cx + (x1 - cx) * sx, cz - (cz - z0) * sz, cz + (z1 - cz) * sz)

    def frange(a, b):
        n = max(1, int((b - a) / step))
        st = (b - a) / n
        return [a + st * (i + 0.5) for i in range(n)]

    for face in faces:
        yr = ylim or (y0, y1)
        if face in ("+z", "-z"):
            xa = (0.0, x1) if half else (x0, x1)
            grid = [(a, b) for a in frange(*xa) for b in frange(*yr)]
        elif face in ("+x", "-x"):
            grid = [(a, b) for a in frange(*yr) for b in frange(z0, z1)]
        else:
            xa = (0.0, x1) if half else (x0, x1)
            grid = [(a, b) for a in frange(*xa) for b in frange(z0, z1)]
        for a, b in grid:
            if rng.random() > p:
                continue
            a += rng.uniform(-0.2, 0.2)
            b += rng.uniform(-0.2, 0.2)
            sa, sb = rng.uniform(*size), rng.uniform(*size)
            if rng.random() < 0.18:
                sa *= 1.6
            sn = rng.uniform(0.8, 1.15)
            o = rng.uniform(*out)
            mat = "tan" if rng.random() < tan_p else "navy"
            mir = mirror
            if face in ("+z", "-z"):
                x, y = a, b
                ex = ext(y)
                zf = ex[3] if face == "+z" else ex[2]
                if half:
                    if abs(x) < 0.5:
                        x, mir = 0.0, False
                    else:
                        mir = True
                zc = zf + (o - sn / 2) * (1 if face == "+z" else -1)
                bx = (x - sa / 2, x + sa / 2, y - sb / 2, y + sb / 2, zc - sn / 2, zc + sn / 2)
            elif face in ("+x", "-x"):
                y, z = a, b
                ex = ext(y)
                xf = ex[1] if face == "+x" else ex[0]
                if z + sb / 2 > ex[3] + 0.3 or z - sb / 2 < ex[2] - 0.3:
                    continue
                xc = xf + (o - sn / 2) * (1 if face == "+x" else -1)
                bx = (xc - sn / 2, xc + sn / 2, y - sa / 2, y + sa / 2, z - sb / 2, z + sb / 2)
                if half:
                    mir = True
            else:
                x, z = a, b
                yf = y1 if face == "+y" else y0
                ex = ext(yf)
                if half:
                    if abs(x) < 0.5:
                        x, mir = 0.0, False
                    else:
                        mir = True
                yc = yf + (o - sn / 2) * (1 if face == "+y" else -1)
                bx = (x - sa / 2, x + sa / 2, yc - sn / 2, yc + sn / 2, z - sb / 2, z + sb / 2)
            box(*bx, mat=mat, bone=bone, frame=frame, skip=(OPP[face],), mirror=mir)


# ==========================================================================
# THE DINOSAUR  (x, s, z)   s = 0 at snout tip, grows toward the tail
# ==========================================================================
def V(x, s, z):
    return Vector((x, s, z))


def tan_cluster(xf, cells, bone, mat="tan", out=(0.3, 0.6)):
    """Irregular stacked tan armour made of blocks on an outward (+x) face."""
    for (s, z) in cells:
        sa, sb, sn = rng.uniform(1.0, 1.25), rng.uniform(1.0, 1.2), rng.uniform(0.8, 1.0)
        o = rng.uniform(*out)
        xc = xf + o - sn / 2
        box(xc - sn / 2, xc + sn / 2, s - sa / 2, s + sa / 2, z - sb / 2, z + sb / 2, mat, bone,
            skip=("-x",), mirror=True)


# ---------------- HEAD (bone Head) ----------------
H = "Head"
box(-1.95, 1.95, 3.0, 6.6, 9.7, 11.7, "navy", H)                       # skull
box(-1.5, 1.5, 0.9, 3.3, 9.45, 10.8, "navy", H, skip=("+y",))         # snout
box(-1.2, 1.2, 0.7, 3.2, 10.6, 11.35, "tan", H)                        # snout top plate
box(-0.85, 0.85, 0.55, 1.0, 9.7, 10.75, "tan", H, skip=("+y",))        # nose front
box(-1.3, 1.3, 3.2, 5.6, 11.6, 12.15, "tan", H, skip=("-z",))          # forehead plate
box(-1.75, 1.75, 0.9, 5.8, 9.1, 9.6, "tan", H)                         # upper lip rail
for sx in (1,):
    box(0.95, 2.25, 2.85, 4.2, 11.0, 11.95, "tan", H, skip=("-z",), mirror=True)  # brow ridge
    box(1.9, 2.5, 4.3, 6.6, 8.9, 11.2, "navy", H, skip=("-x",), mirror=True)    # cheek / hinge
    box(1.2, 2.15, 2.7, 3.5, 10.25, 11.0, bone=H, group="glow", uv="glow", mirror=True)  # eye
scatter(-1.95, 1.95, 3.0, 6.6, 9.7, 11.7, ["+z"], H, p=0.55, tan_p=0.55, half=True, ylim=(5.4, 6.6))
scatter(-1.55, 1.55, 0.8, 3.3, 9.45, 11.05, ["+x"], H, p=0.35, tan_p=0.9, half=True, out=(0.15, 0.3), size=(0.7, 1.0))
scatter(-1.95, 2.5, 4.3, 6.6, 9.0, 11.4, ["+x"], H, p=0.5, tan_p=0.3, half=True)
# mouth glow + throat
box(-1.45, 1.45, 1.3, 6.2, 8.2, 9.3, bone=H, group="glow", uv="mouth")
# upper teeth (hang down)
for x in (-1.1, -0.37, 0.37, 1.1):
    pyramid(V(x, 1.05, 9.15), (0, 0, -1), 0.75 if abs(x) > 1 else 0.5, 0.2, H)
for s, L in ((1.9, 0.6), (2.9, 0.5), (3.9, 0.55), (4.9, 0.45)):
    pyramid(V(1.55, s, 9.15), (0.15, 0, -1), L, 0.2, H, mirror=True)

# ---------------- JAW (bone Jaw), modelled open like the reference -------
J = "Jaw"
JAW_PIVOT = (0.0, 5.7, 9.0)
jf = rot_frame(JAW_PIVOT, "X", math.radians(22))
box(-1.7, 1.7, 1.2, 6.0, 7.6, 8.55, "tan", J, frame=jf)                  # lower jaw
box(-1.3, 1.3, 1.6, 5.4, 7.2, 7.65, "navy", J, frame=jf, skip=("+z",))   # jaw underside
box(-1.05, 1.05, 0.9, 2.1, 7.35, 8.4, "tan", J, frame=jf)                # chin
scatter(-1.7, 1.7, 1.2, 6.0, 7.6, 8.55, ["+x"], J, frame=jf, p=0.35, tan_p=0.8, half=True,
        out=(0.15, 0.35), size=(0.6, 0.9))
for x in (-1.0, -0.33, 0.33, 1.0):
    pyramid(jf(V(x, 1.25, 8.5)), (0, 0, 1), 0.65 if abs(x) > 0.5 else 0.5, 0.2, J)
for s in (2.2, 3.2, 4.2, 5.1):
    pyramid(jf(V(1.45, s, 8.5)), (0.1, 0, 1), 0.45, 0.18, J, mirror=True)
for s, L in ((1.9, 0.8), (3.2, 0.95), (4.6, 0.8)):                      # jaw-side horn spikes
    pyramid(jf(V(1.75, s, 8.3)), (0.75, 0.35, 0.6), L, 0.28, J, mat="tan", mirror=True)
pyramid(jf(V(0.0, 1.0, 7.4)), (0, -0.6, -0.8), 0.6, 0.3, J, mat="tan")  # chin spike

# ---------------- NECK (bone Neck) ----------------
N = "Neck"
box(-2.35, 2.35, 5.6, 9.9, 7.9, 11.3, "navy", N, skip=("+y",))
box(-1.8, 1.8, 5.6, 9.9, 11.2, 12.0, "navy", N, skip=("-z", "+y"))
box(-1.8, 1.8, 5.9, 9.2, 6.7, 7.4, "navy", N, skip=("+z",))            # throat
box(-1.45, 1.45, 6.2, 9.3, 11.8, 12.5, "tan", N, skip=("-z",))         # neck top plate
scatter(-2.35, 2.35, 5.6, 9.9, 7.3, 11.9, ["+z"], N, p=0.55, tan_p=0.45, half=True)
scatter(-2.35, 2.35, 5.6, 9.9, 7.3, 11.9, ["+x"], N, p=0.6, tan_p=0.3, half=True)

# ---------------- CHEST (bone Chest) ----------------
C = "Chest"
box(-3.8, 3.8, 9.0, 14.6, 6.3, 11.4, "navy", C)
box(-3.1, 3.1, 9.0, 14.6, 11.3, 12.3, "navy", C, skip=("-z",))
box(-3.0, 3.0, 9.2, 14.6, 5.3, 6.4, "navy", C, skip=("+z",))
box(-2.9, 2.9, 9.4, 13.6, 12.1, 12.9, "navy", C, skip=("-z",))         # shoulder hump
box(-3.0, 3.0, 8.3, 9.1, 5.8, 10.8, "navy", C, skip=("+y",))           # chest front
box(-1.8, 1.8, 10.0, 12.6, 12.8, 13.3, "tan", C, skip=("-z",))         # hump plate
tan_cluster(3.8, [(12.9, 10.6), (14.0, 10.6), (12.9, 9.5), (12.9, 8.4), (14.0, 8.4), (13.1, 7.3)], C)
scatter(-3.8, 3.8, 9.0, 14.6, 5.4, 12.2, ["+z"], C, p=0.5, tan_p=0.3, half=True)
scatter(-3.8, 3.8, 9.0, 14.6, 5.4, 12.2, ["+x"], C, p=0.45, tan_p=0.15, half=True)
scatter(-3.0, 3.0, 8.3, 9.1, 5.8, 10.8, ["-y"], C, p=0.5, tan_p=0.2, half=True)
scatter(-3.8, 3.8, 9.0, 14.6, 5.4, 12.2, ["-z"], C, p=0.1, tan_p=0.0, half=True, out=(0.2, 0.4))
for (s, z) in ((11.0, 7.0), (12.9, 9.6), (13.9, 6.6)):                  # glow cracks
    box(3.72, 3.9, s - 0.8, s + 0.8, z - 0.18, z + 0.18, bone=C, group="glow", uv="glow",
        skip=("-x",), mirror=True)

# stepped chest / dewlap mass between the front legs (front view)
box(-2.4, 2.4, 8.2, 11.0, 3.9, 5.6, "navy", C, skip=("+z",))
box(-1.5, 1.5, 8.4, 10.4, 3.0, 4.0, "navy", C, skip=("+z",))
box(-1.1, 1.1, 7.9, 8.5, 4.2, 5.8, "tan", C, skip=("+y",))

# ---------------- HIPS (bone Hips) ----------------
P = "Hips"
box(-3.7, 3.7, 14.3, 20.4, 5.9, 10.3, "navy", P, skip=("-y",))
box(-3.0, 3.0, 14.3, 20.4, 10.2, 11.2, "navy", P, skip=("-z", "-y"))
box(-2.9, 2.9, 14.3, 20.0, 5.0, 6.0, "navy", P, skip=("+z", "-y"))
box(-2.6, 2.6, 14.5, 19.4, 11.0, 11.7, "navy", P, skip=("-z",))
scatter(-3.7, 3.7, 14.3, 20.4, 5.0, 11.1, ["+z"], P, p=0.5, tan_p=0.2, half=True)
scatter(-3.7, 3.7, 14.3, 20.4, 5.0, 11.1, ["+x"], P, p=0.45, tan_p=0.12, half=True)
scatter(-3.7, 3.7, 14.3, 20.4, 5.0, 11.1, ["-z"], P, p=0.1, tan_p=0.0, half=True, out=(0.2, 0.4))
for (s, z) in ((16.0, 9.8), (19.3, 7.0)):
    box(3.62, 3.8, s - 0.7, s + 0.7, z - 0.18, z + 0.18, bone=P, group="glow", uv="glow",
        skip=("-x",), mirror=True)

# ---------------- TAIL (bones Tail1..Tail4) ----------------
TAIL = [  # s, centre z, width, height
    (20.0, 7.9, 5.4, 5.4),
    (24.0, 6.4, 4.0, 4.0),
    (27.6, 4.8, 2.9, 3.0),
    (30.8, 3.6, 1.9, 2.0),
    (34.0, 2.3, 1.0, 1.1),
]


def tail_at(s):
    """(centre z, half width, half height) of the tail at distance s."""
    for (s0, z0, w0, h0), (s1, z1, w1, h1) in zip(TAIL, TAIL[1:]):
        if s <= s1:
            f = (s - s0) / (s1 - s0)
            return z0 + (z1 - z0) * f, (w0 + (w1 - w0) * f) / 2, (h0 + (h1 - h0) * f) / 2
    return TAIL[-1][1], TAIL[-1][2] / 2, TAIL[-1][3] / 2
for i in range(4):
    s0, z0, w0, h0 = TAIL[i]
    s1, z1, w1, h1 = TAIL[i + 1]
    bone = "Tail%d" % (i + 1)
    ov = 0.35 if i < 3 else 0.0
    f = seg_frame(V(0, s0, z0), V(0, s1, z1))
    L = (V(0, s1, z1) - V(0, s0, z0)).length
    box(-w0 / 2, w0 / 2, -0.2, L + ov, -h0 / 2, h0 / 2, "navy", bone, frame=f,
        taper=(w1 / w0, h1 / h0), skip=("-y",) if i else ())
    scatter(-w0 / 2, w0 / 2, 0, L, -h0 / 2, h0 / 2, ["+z"], bone, frame=f, taper=(w1 / w0, h1 / h0),
            p=0.5, tan_p=0.18, half=True, size=(0.7, 1.1) if i > 1 else (0.85, 1.3))
    scatter(-w0 / 2, w0 / 2, 0, L, -h0 / 2, h0 / 2, ["+x"], bone, frame=f, taper=(w1 / w0, h1 / h0),
            p=0.45, tan_p=0.3, half=True, size=(0.6, 1.0) if i > 1 else (0.8, 1.2))


# ---------------- LEGS ----------------
def front_leg():
    U, F, Hd = "UpperArm.L", "Forearm.L", "Hand.L"
    box(2.6, 6.0, 8.0, 12.9, 4.2, 9.6, "navy", U, mirror=True)
    tan_cluster(6.0, [(9.0, 8.6), (10.1, 8.7), (11.2, 8.4), (9.3, 7.5), (10.4, 7.4), (9.8, 6.3), (9.6, 5.2)], U)
    scatter(2.6, 6.0, 8.0, 12.9, 4.2, 9.6, ["+x", "-y", "+y"], U, p=0.6, tan_p=0.3, mirror=True)
    scatter(2.6, 6.0, 8.0, 12.9, 4.2, 9.6, ["+z"], U, p=0.5, tan_p=0.3, mirror=True, ylim=(8.0, 9.0))
    box(2.8, 5.7, 7.8, 11.3, 1.2, 4.9, "navy", F, mirror=True)
    box(3.1, 5.4, 7.35, 7.85, 1.6, 4.4, "tan", F, skip=("+y",), mirror=True)       # shin guard
    scatter(2.8, 5.7, 7.8, 11.3, 1.2, 4.9, ["+x", "+y", "-x"], F, p=0.45, tan_p=0.25, mirror=True)
    box(2.4, 6.1, 7.0, 11.2, 0.0, 1.45, "navy", Hd, mirror=True)
    for x in (2.85, 4.25, 5.65):
        box(x - 0.6, x + 0.6, 5.8, 7.1, 0.0, 1.3, "tan", Hd, skip=("+y",), mirror=True)
        box(x - 0.48, x + 0.48, 5.35, 5.85, 0.0, 0.9, "tan", Hd, skip=("+y",), mirror=True)  # toe tip
    box(6.05, 6.7, 8.6, 9.9, 0.0, 1.0, "tan", Hd, skip=("-x",), mirror=True)          # side toe


def rear_leg():
    T, S, Ft = "Thigh.L", "Shin.L", "Foot.L"
    box(2.5, 6.0, 15.2, 20.8, 4.3, 10.3, "navy", T, mirror=True)
    tan_cluster(6.0, [(16.8, 9.2), (17.9, 9.3), (19.0, 9.1), (17.2, 8.1), (17.4, 7.0), (18.5, 7.0),
                      (17.3, 5.9), (16.6, 4.9)], T)
    scatter(2.5, 6.0, 15.2, 20.8, 4.3, 10.3, ["+x", "-y", "+y"], T, p=0.55, tan_p=0.25, mirror=True)
    box(2.8, 5.7, 16.0, 19.8, 1.2, 4.8, "navy", S, mirror=True)
    box(3.2, 5.3, 15.55, 16.05, 1.8, 4.1, "tan", S, skip=("+y",), mirror=True)
    scatter(2.8, 5.7, 16.0, 19.8, 1.2, 4.8, ["+x", "+y", "-x"], S, p=0.4, tan_p=0.25, mirror=True)
    box(2.4, 6.0, 15.0, 19.9, 0.0, 1.45, "navy", Ft, mirror=True)
    for x in (2.9, 4.2, 5.5):
        box(x - 0.58, x + 0.58, 13.8, 15.1, 0.0, 1.2, "tan", Ft, skip=("+y",), mirror=True)
        box(x - 0.46, x + 0.46, 13.35, 13.85, 0.0, 0.85, "tan", Ft, skip=("+y",), mirror=True)


front_leg()
rear_leg()
for (x0, x1, s0, s1, z0, z1, bone) in (
        (3.7, 3.95, 8.9, 10.3, 5.4, 6.2, "Chest"), (5.95, 6.15, 11.2, 12.4, 5.9, 6.5, "UpperArm.L"),
        (5.6, 5.8, 9.3, 10.5, 4.2, 4.7, "Forearm.L"), (3.6, 3.85, 19.8, 20.8, 5.5, 6.3, "Hips"),
        (5.9, 6.1, 19.4, 20.5, 4.4, 5.0, "Thigh.L"), (3.7, 3.95, 11.8, 12.8, 5.6, 6.2, "Chest")):
    box(x0, x1, s0, s1, z0, z1, bone=bone, group="glow", uv="glow", skip=("-x",), mirror=True)

# ---------------- CRYSTALS ----------------
back = Vector((0, 1, 0))
up = Vector((0, 0, 1))
SPINE = [  # s, base z, length, radius, bone
    (3.4, 11.9, 1.7, 0.42, "Head"),
    (4.9, 12.0, 2.5, 0.55, "Head"),
    (6.9, 12.3, 2.6, 0.55, "Neck"),
    (9.3, 12.6, 3.1, 0.62, "Neck"),
    (11.6, 13.1, 3.5, 0.68, "Chest"),
    (13.5, 12.6, 3.3, 0.66, "Chest"),
    (15.4, 11.4, 3.9, 0.72, "Hips"),
    (17.2, 11.4, 3.5, 0.68, "Hips"),
    (19.0, 11.0, 3.2, 0.64, "Hips"),
    (21.0, None, 2.9, 0.6, "Tail1"),
    (22.8, None, 2.5, 0.54, "Tail1"),
    (24.8, None, 2.1, 0.48, "Tail2"),
    (26.6, None, 1.8, 0.42, "Tail2"),
    (28.4, None, 1.45, 0.36, "Tail3"),
    (30.2, None, 1.15, 0.3, "Tail3"),
    (31.9, None, 0.9, 0.26, "Tail4"),
    (33.4, None, 0.6, 0.2, "Tail4"),
]
for s, z, L, r, bone in SPINE:
    if z is None:
        tz, tw, th = tail_at(s)
        z = tz + th - 0.05
    L *= 1.25
    r *= 1.2
    crystal(V(0, s, z), up + back * 0.55, L, r, bone)
    if L > 1.4:  # flanking pair of smaller crystals (top view shows a cluster at each spine step)
        crystal(V(0.75, s + 0.5, z - 0.25), up + back * 0.45 + Vector((0.5, 0, 0)), L * 0.55, r * 0.7,
                bone, mirror=True)
# tan stone spikes between crystals on the neck/shoulders (reference hero view)
for s, z, L in ((8.1, 12.2, 2.0), (10.6, 12.8, 2.4), (5.9, 11.9, 1.4)):
    f = dir_frame(V(0, s, z - 0.3), up + back * 0.3)
    box(-0.5, 0.5, 0, L, -0.45, 0.45, "tan", "Neck" if s < 10 else "Chest", frame=f, taper=(0.25, 0.25),
        skip=("-y",))
# side crystals
SIDE = [  # base (x,s,z), direction, length, radius, bone
    ((1.3, 5.3, 11.8), (0.55, 0.35, 1), 2.0, 0.48, "Head"),      # head side crest
    ((2.45, 5.8, 10.6), (1, 0.6, 0.4), 1.2, 0.32, "Head"),       # cheek
    ((5.2, 10.4, 9.3), (0.55, 0.2, 1), 3.3, 0.72, "UpperArm.L"),  # shoulder
    ((5.9, 11.8, 8.2), (1, 0.4, 0.6), 1.9, 0.48, "UpperArm.L"),
    ((5.6, 8.6, 6.4), (1, -0.3, 0.5), 1.6, 0.42, "UpperArm.L"),
    ((5.6, 10.6, 3.2), (1, 0.6, 0.3), 1.8, 0.45, "Forearm.L"),  # elbow/forearm
    ((5.5, 8.4, 2.0), (1, -0.2, 0.2), 1.1, 0.32, "Forearm.L"),
    ((3.9, 13.0, 10.9), (0.7, 0.3, 1), 2.3, 0.52, "Chest"),     # flank
    ((3.8, 11.0, 7.4), (1, 0.2, 0.4), 1.4, 0.36, "Chest"),
    ((5.8, 18.6, 9.6), (0.7, 0.4, 1), 2.6, 0.6, "Thigh.L"),     # hip
    ((6.0, 16.8, 6.6), (1, 0.3, 0.3), 1.5, 0.4, "Thigh.L"),
    ((5.6, 17.6, 2.9), (1, 0.5, 0.3), 1.3, 0.36, "Shin.L"),
    ((3.7, 16.2, 10.4), (0.6, 0.3, 1), 1.7, 0.42, "Hips"),
    ((None, 21.8, None), (1, 0.5, 0.7), 1.2, 0.34, "Tail1"),
    ((None, 24.8, None), (1, 0.5, 0.6), 1.0, 0.3, "Tail2"),
    ((None, 27.8, None), (1, 0.5, 0.6), 0.85, 0.26, "Tail3"),
    ((None, 30.4, None), (1, 0.5, 0.6), 0.7, 0.22, "Tail3"),
    ((None, 32.9, None), (1, 0.6, 0.6), 0.5, 0.18, "Tail4"),
]
for base, d, L, r, bone in SIDE:
    if base[0] is None:
        tz, tw, th = tail_at(base[1])
        base = (tw - 0.1, base[1], tz + th * 0.3)
    crystal(V(*base), d, L, r, bone, mirror=True)


# ==========================================================================
# assemble meshes
# ==========================================================================
def mirrored(pr):
    bone = pr["bone"]
    if bone.endswith(".L"):
        bone = bone[:-2] + ".R"
    verts = [Vector((-v.x, v.y, v.z)) for v in pr["verts"]]
    faces = [(tuple(reversed(ids)), list(reversed(uvs))) for ids, uvs in pr["faces"]]
    return dict(verts=verts, faces=faces, group=pr["group"], bone=bone, mirror=False)


ALL = []
for pr in PRIMS:
    ALL.append(pr)
    if pr["mirror"]:
        ALL.append(mirrored(pr))


def tri_count(prims):
    return sum(len(ids) - 2 for pr in prims for ids, _ in pr["faces"])


TRIS = tri_count(ALL)
print("TRIS", TRIS, "prims", len(ALL))
if TRIS > TRI_BUDGET:
    raise SystemExit("TRI BUDGET EXCEEDED: %d" % TRIS)

# fresh scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"


def build_mesh(name, group):
    prims = [p for p in ALL if p["group"] == group]
    verts, faces, uvs, vbone = [], [], [], []
    for pr in prims:
        o = len(verts)
        for v in pr["verts"]:
            verts.append((v.x, v.y - S_OFF, v.z * Z_SCALE))
            vbone.append(pr["bone"])
        for ids, fuv in pr["faces"]:
            faces.append(tuple(o + i for i in ids))
            uvs.append(fuv)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    for poly, fuv in zip(me.polygons, uvs):
        for li, uv in zip(poly.loop_indices, fuv):
            uvl.data[li].uv = uv
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    for b in sorted(set(vbone)):
        vg = ob.vertex_groups.new(name=b)
        vg.add([i for i, bb in enumerate(vbone) if bb == b], 1.0, "REPLACE")
    return ob


body = build_mesh("CrystalDino_Body", "body")
glow = build_mesh("CrystalDino_Glow", "glow")


# ---------------- materials ----------------
def img(name, colorspace):
    im = bpy.data.images.load(os.path.join(TEX, name), check_existing=True)
    im.colorspace_settings.name = colorspace
    return im


def make_mat(name, emission_strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexImage")
    tc.image = img("CrystalDino_Color.png", "sRGB")
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = img("CrystalDino_Normal.png", "Non-Color")
    tr = nt.nodes.new("ShaderNodeTexImage")
    tr.image = img("CrystalDino_Roughness.png", "Non-Color")
    te = nt.nodes.new("ShaderNodeTexImage")
    te.image = img("CrystalDino_Emission.png", "sRGB")
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(tr.outputs["Color"], bsdf.inputs["Roughness"])
    nt.links.new(te.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = emission_strength
    for n in (tc, tn, tr, te):
        n.interpolation = "Linear"
    return m


body.data.materials.append(make_mat("MAT_CrystalDino", 3.0))
glow.data.materials.append(make_mat("MAT_CrystalDino_Glow", 4.0))

# ==========================================================================
# armature
# ==========================================================================
BONES = [  # name, head(x,s,z), tail(x,s,z), parent, deform
    ("Root", (0, 14, 0), (0, 14, 1.5), None, True),
    ("Hips", (0, 17.2, 8.2), (0, 14.2, 8.8), "Root", True),
    ("Chest", (0, 14.2, 8.8), (0, 9.6, 9.6), "Hips", True),
    ("Neck", (0, 9.6, 9.6), (0, 6.2, 10.0), "Chest", True),
    ("Head", (0, 6.2, 10.0), (0, 1.5, 10.4), "Neck", True),
    ("Jaw", (0, 5.7, 9.0), (0, 1.3, 7.7), "Head", True),
    ("Tail1", (0, 20.0, 7.9), (0, 24.0, 6.4), "Hips", True),
    ("Tail2", (0, 24.0, 6.4), (0, 27.6, 4.8), "Tail1", True),
    ("Tail3", (0, 27.6, 4.8), (0, 30.8, 3.6), "Tail2", True),
    ("Tail4", (0, 30.8, 3.6), (0, 34.0, 2.3), "Tail3", True),
    ("UpperArm.L", (4.3, 10.4, 8.4), (4.3, 10.2, 4.0), "Chest", True),
    ("Forearm.L", (4.3, 10.2, 4.0), (4.3, 9.6, 1.2), "UpperArm.L", True),
    ("Hand.L", (4.3, 9.6, 1.2), (4.3, 6.0, 0.6), "Forearm.L", True),
    ("Thigh.L", (4.25, 18.0, 8.8), (4.25, 17.4, 4.2), "Hips", True),
    ("Shin.L", (4.25, 17.4, 4.2), (4.25, 17.9, 1.2), "Thigh.L", True),
    ("Foot.L", (4.25, 17.9, 1.2), (4.25, 14.0, 0.6), "Shin.L", True),
    # IK controllers (not exported: non-deform)
    ("HandCtrl.L", (4.3, 9.6, 1.2), (4.3, 6.0, 0.6), "Root", False),
    ("FootCtrl.L", (4.25, 17.9, 1.2), (4.25, 14.0, 0.6), "Root", False),
]
full = []
for n, h, t, p, d in BONES:
    full.append((n, h, t, p, d))
    if n.endswith(".L"):
        mir = lambda q: (-q[0], q[1], q[2])
        full.append((n[:-2] + ".R", mir(h), mir(t), (p[:-2] + ".R") if p and p.endswith(".L") else p, d))

arm_data = bpy.data.armatures.new("CrystalDino_Rig")
arm = bpy.data.objects.new("CrystalDino_Rig", arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm_data.edit_bones
for n, h, t, p, d in full:
    b = eb.new(n)
    b.head = (h[0], h[1] - S_OFF, h[2] * Z_SCALE)
    b.tail = (t[0], t[1] - S_OFF, t[2] * Z_SCALE)
    b.roll = 0.0
    b.use_deform = d
for n, h, t, p, d in full:
    if p:
        eb[n].parent = eb[p]
        eb[n].use_connect = False
bpy.ops.object.mode_set(mode="OBJECT")

for ob in (body, glow):
    ob.parent = arm
    mod = ob.modifiers.new("Armature", "ARMATURE")
    mod.object = arm

# IK setup
pb = arm.pose.bones
for side in ("L", "R"):
    for mid, end, ctrl in (("Forearm", "Hand", "HandCtrl"), ("Shin", "Foot", "FootCtrl")):
        ik = pb["%s.%s" % (mid, side)].constraints.new("IK")
        ik.target = arm
        ik.subtarget = "%s.%s" % (ctrl, side)
        ik.chain_count = 2
        ik.use_stretch = False
        cr = pb["%s.%s" % (end, side)].constraints.new("COPY_ROTATION")
        cr.target = arm
        cr.subtarget = "%s.%s" % (ctrl, side)
for b in pb:
    b.rotation_mode = "QUATERNION"

# ==========================================================================
# animations
# ==========================================================================
scene.render.fps = 30


def rest3(name):
    return arm.data.bones[name].matrix_local.to_3x3()


def qrot(name, *axis_angles):
    """Rotation about armature-space axes, expressed in the bone's local frame."""
    M = rest3(name)
    Mi = M.inverted()
    q = Quaternion()
    for axis, ang in axis_angles:
        q = Quaternion(Mi @ Vector(axis), ang) @ q
    return q


def vloc(name, v):
    return rest3(name).inverted() @ Vector(v)


def key(name, frame, loc=None, rot=None):
    b = pb[name]
    if loc is not None:
        b.location = loc
        b.keyframe_insert("location", frame=frame, group=name)
    if rot is not None:
        b.rotation_quaternion = rot
        b.keyframe_insert("rotation_quaternion", frame=frame, group=name)


X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
TAU = math.tau
rad = math.radians


def reset_pose():
    for b in pb:
        b.location = (0, 0, 0)
        b.rotation_quaternion = (1, 0, 0, 0)


def new_action(name):
    reset_pose()
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    arm.animation_data_create()
    arm.animation_data.action = act
    return act


# ---------------- Idle (90 frames loop, 3 s) ----------------
IDLE_N = 90
new_action("Idle")
for f in range(0, IDLE_N + 1, 3):
    t = f / IDLE_N
    br = math.sin(TAU * t)                  # breathing
    key("Hips", f + 1, loc=vloc("Hips", (0, 0, -0.12 * (0.5 - 0.5 * math.cos(TAU * t)))),
        rot=qrot("Hips", (X, rad(0.8) * br)))
    key("Chest", f + 1, rot=qrot("Chest", (X, rad(-1.6) * br)))
    key("Neck", f + 1, rot=qrot("Neck", (X, rad(-3.0) * math.sin(TAU * t - 0.6)),
                                 (Z, rad(2.5) * math.sin(TAU * t * 1))))
    key("Head", f + 1, rot=qrot("Head", (X, rad(2.0) * math.sin(TAU * t - 1.2)),
                                 (Z, rad(4.0) * math.sin(TAU * t - 0.5))))
    key("Jaw", f + 1, rot=qrot("Jaw", (X, rad(5.0) * (0.5 - 0.5 * math.cos(TAU * t)))))
    for i in range(4):
        key("Tail%d" % (i + 1), f + 1, rot=qrot("Tail%d" % (i + 1),
            (Z, rad(3.0 + 1.5 * i) * math.sin(TAU * t - 0.7 * i)),
            (X, rad(1.0) * math.sin(TAU * t - 0.5 * i))))
    for c in ("HandCtrl.L", "HandCtrl.R", "FootCtrl.L", "FootCtrl.R"):
        key(c, f + 1, loc=Vector((0, 0, 0)), rot=Quaternion())
    for b in ("UpperArm.L", "UpperArm.R", "Thigh.L", "Thigh.R", "Forearm.L", "Forearm.R",
              "Shin.L", "Shin.R", "Hand.L", "Hand.R", "Foot.L", "Foot.R"):
        key(b, f + 1, rot=Quaternion())

# ---------------- Walk (40 frames loop, in place, diagonal gait) ----------------
WALK_N = 40
STRIDE = 2.2
LIFT = 0.9
DUTY = 0.6
new_action("Walk")


def foot_cycle(t):
    """returns (forward offset along -Y world, lift) for phase t in [0,1)."""
    t %= 1.0
    if t < DUTY:  # stance: foot slides back from +S/2 to -S/2
        u = t / DUTY
        return STRIDE * (0.5 - u), 0.0, 0.0
    u = (t - DUTY) / (1 - DUTY)  # swing: forward and up
    fwd = STRIDE * (-0.5 + (0.5 - 0.5 * math.cos(math.pi * u)))
    lift = LIFT * math.sin(math.pi * u)
    pitch = rad(-18) * math.sin(math.pi * u) * (1 - u)
    return fwd, lift, pitch


PHASE = {"HandCtrl.L": 0.0, "FootCtrl.R": 0.0, "HandCtrl.R": 0.5, "FootCtrl.L": 0.5}
for f in range(0, WALK_N + 1, 2):
    t = f / WALK_N
    for c, ph in PHASE.items():
        fwd, lift, pitch = foot_cycle(t + ph)
        key(c, f + 1, loc=vloc(c, (0, -fwd, lift)), rot=qrot(c, (X, pitch)))
    bob = -0.14 * math.cos(2 * TAU * t)
    key("Hips", f + 1, loc=vloc("Hips", (0.08 * math.sin(TAU * t), 0, bob - 0.2)),
        rot=qrot("Hips", (Y, rad(2.5) * math.sin(TAU * t)), (Z, rad(3.0) * math.sin(TAU * t))))
    key("Chest", f + 1, rot=qrot("Chest", (Y, rad(-3.0) * math.sin(TAU * t)),
                                  (Z, rad(-5.0) * math.sin(TAU * t)),
                                  (X, rad(1.0) * math.sin(2 * TAU * t))))
    key("Neck", f + 1, rot=qrot("Neck", (Z, rad(3.0) * math.sin(TAU * t - 0.8)),
                                 (X, rad(-2.5) * math.sin(2 * TAU * t - 0.6))))
    key("Head", f + 1, rot=qrot("Head", (Z, rad(3.0) * math.sin(TAU * t - 1.4)),
                                 (X, rad(2.0) * math.sin(2 * TAU * t - 1.2))))
    key("Jaw", f + 1, rot=qrot("Jaw", (X, rad(3.0) * (0.5 - 0.5 * math.cos(2 * TAU * t)))))
    for i in range(4):
        key("Tail%d" % (i + 1), f + 1, rot=qrot("Tail%d" % (i + 1),
            (Z, rad(5.0 + 2.0 * i) * math.sin(TAU * t - 0.8 - 0.7 * i)),
            (X, rad(1.5) * math.sin(2 * TAU * t - 0.6 * i))))
    for b in ("UpperArm.L", "UpperArm.R", "Thigh.L", "Thigh.R", "Forearm.L", "Forearm.R",
              "Shin.L", "Shin.R", "Hand.L", "Hand.R", "Foot.L", "Foot.R"):
        key(b, f + 1, rot=Quaternion())

for act in bpy.data.actions:
    for fc in act.fcurves:
        fc.modifiers.new("CYCLES")

arm.animation_data.action = bpy.data.actions["Idle"]
scene.frame_start, scene.frame_end = 1, IDLE_N
scene.frame_set(1)
reset_pose()

out = os.path.join(ROOT, "CrystalDino.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("saved", out, "body tris", sum(len(p.vertices) - 2 for p in body.data.polygons),
      "glow tris", sum(len(p.vertices) - 2 for p in glow.data.polygons))
