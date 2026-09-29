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
DENSITY = float(os.environ.get("DINO_DENSITY", "0.5"))
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
    PRIMS.append(dict(verts=verts, faces=faces, group=group, bone=bone, mirror=mirror, smooth=False))


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


# ==========================================================================
# THE DINOSAUR  (x, s, z)   s = 0 at snout tip, grows toward the tail
# ==========================================================================
def V(x, s, z):
    return Vector((x, s, z))


# ---------------- lofted (rounded) forms -------------------------------------
class Loft:
    """Elliptical tube through ring centres; rings = [(centre, rx, rw, weights)]."""

    def __init__(self, rings, sides):
        self.rings, self.sides = rings, sides
        self.frames = []
        n = len(rings)
        for k, (c, rx, rw, wts) in enumerate(rings):
            a = rings[max(k - 1, 0)][0]
            b = rings[min(k + 1, n - 1)][0]
            t = (b - a).normalized()
            u = Vector((1, 0, 0))
            u = (u - t * u.dot(t)).normalized()
            w = u.cross(t)
            if w.z < -0.5 or (abs(w.z) < 0.5 and w.y < 0):
                w = -w
            self.frames.append((t, u, w))

    def angle(self, j):
        return math.pi / 2 + math.pi / self.sides + j * math.tau / self.sides

    def point(self, kf, a, out=0.0):
        """surface point, outward normal and tangent at fractional ring index kf, angle a."""
        k = min(int(kf), len(self.rings) - 2)
        f = kf - k
        pts, nrm, tng = [], [], []
        for kk in (k, k + 1):
            c, rx, rw, _ = self.rings[kk]
            t, u, w = self.frames[kk]
            pts.append(c + u * (rx * math.cos(a)) + w * (rw * math.sin(a)))
            nrm.append((u * (math.cos(a) / max(rx, 1e-3)) + w * (math.sin(a) / max(rw, 1e-3))).normalized())
            tng.append(t)
        p = pts[0].lerp(pts[1], f)
        n = nrm[0].lerp(nrm[1], f).normalized()
        t = tng[0].lerp(tng[1], f).normalized()
        return p + n * out, n, t

    def weights_at(self, kf):
        return self.rings[min(int(round(kf)), len(self.rings) - 1)][3]


def loft(L, mat, group="body", mirror=False, cap0=False, cap1=False, frame=IDENT, matfn=None):
    rings, S = L.rings, L.sides
    verts, weights, faces = [], [], []
    for k, (c, rx, rw, wts) in enumerate(rings):
        t, u, w = L.frames[k]
        for j in range(S):
            a = L.angle(j)
            verts.append(c + u * (rx * math.cos(a)) + w * (rw * math.sin(a)))
            weights.append(wts)
    for k in range(len(rings) - 1):
        for j in range(S):
            j1 = (j + 1) % S
            ids = (k * S + j, k * S + j1, (k + 1) * S + j1, (k + 1) * S + j)
            m = matfn(k, j) if matfn else mat
            wd = (verts[ids[1]] - verts[ids[0]]).length
            ht = (verts[ids[3]] - verts[ids[0]]).length
            faces.append((ids, cell_uvs(m, wd, ht)))
    # make winding outward
    ids = faces[0][0]
    fn = (verts[ids[1]] - verts[ids[0]]).cross(verts[ids[3]] - verts[ids[0]])
    _, n0, _ = L.point(0.0, (L.angle(0) + L.angle(1)) / 2)
    if fn.dot(n0) < 0:
        faces = [(tuple(reversed(i)), list(reversed(u))) for i, u in faces]
    for which, do in ((0, cap0), (len(rings) - 1, cap1)):
        if not do:
            continue
        c, rx, rw, wts = rings[which]
        ci = len(verts)
        verts.append(c.copy())
        weights.append(wts)
        t = L.frames[which][0]
        sgn = -1 if which == 0 else 1
        m = matfn(which, -1) if matfn else mat
        q = cell_uvs(m, 1, 1)
        for j in range(S):
            j1 = (j + 1) % S
            a, b = which * S + j, which * S + j1
            tri = (a, b, ci)
            fn = (verts[b] - verts[a]).cross(verts[ci] - verts[a])
            if fn.dot(t * sgn) < 0:
                tri = (b, a, ci)
            faces.append((tri, [q[0], q[1], ((q[2][0] + q[3][0]) / 2, q[2][1])]))
    verts = [frame(v) for v in verts]
    PRIMS.append(dict(verts=verts, faces=faces, group=group, bone=None, weights=weights,
                      mirror=mirror, smooth=True))


def oriented_box(p, n, t, sa, sb, sn, mat, bone, mirror, frame=IDENT, group="body", uv=None, roll=12, tilt=8):
    """Block whose local z follows surface normal n, sunk into the surface at p."""
    z = n.normalized()
    y = (t - z * t.dot(z)).normalized()
    R = Matrix((y.cross(z), y, z)).transposed()
    R = R @ Matrix.Rotation(math.radians(rng.uniform(-roll, roll)), 3, "Z") \
          @ Matrix.Rotation(math.radians(rng.uniform(-tilt, tilt)), 3, "X")
    f = lambda v: frame(p + R @ v)
    box(-sa / 2, sa / 2, -sb / 2, sb / 2, -sn, 0.0, mat, bone, frame=f, skip=("-z",), mirror=mirror,
        group=group, uv=uv)


def dominant(w):
    return max(w.items(), key=lambda kv: kv[1])[0]


def loft_blocks(L, n, k_range, a_range, tan_p=0.15, size=(0.9, 1.45), out=(0.12, 0.45), half=False,
                mirror=False, frame=IDENT, thick=(0.55, 0.8)):
    n = int(round(n * DENSITY))
    for _ in range(n):
        kf = rng.uniform(*k_range)
        a = rng.uniform(*a_range)
        mir = mirror
        if half:
            if abs(math.cos(a)) < 0.12:
                a, mir = math.pi / 2, False
            else:
                mir = True
        o = rng.uniform(*out)
        p, nn, t = L.point(kf, a, out=o)
        sa, sb = rng.uniform(*size), rng.uniform(*size)
        if rng.random() < 0.15:
            sb *= 1.5
        mat = "tan" if rng.random() < tan_p else "navy"
        oriented_box(p, nn, t, sa, sb, rng.uniform(*thick) + o, mat, dominant(L.weights_at(kf)), mir, frame=frame)


def w1(b):
    return {b: 1.0}


def w2(a, b, f=0.5):
    return {a: 1 - f, b: f}


# ---------------- BODY: neck -> chest -> hips -> tail tip (one smooth loft) -----
BODY = Loft([
    (V(0, 5.6, 9.9), 2.0, 1.75, w1("Neck")),
    (V(0, 7.6, 9.8), 2.55, 2.3, w1("Neck")),
    (V(0, 9.6, 9.3), 3.3, 3.05, w2("Neck", "Chest", 0.6)),
    (V(0, 11.6, 8.8), 3.85, 3.45, w1("Chest")),
    (V(0, 13.6, 8.5), 3.9, 3.35, w1("Chest")),
    (V(0, 15.4, 8.3), 3.8, 3.2, w2("Chest", "Hips")),
    (V(0, 17.6, 8.2), 3.75, 3.1, w1("Hips")),
    (V(0, 19.8, 7.9), 3.3, 2.75, w2("Hips", "Tail1", 0.3)),
    (V(0, 22.0, 7.2), 2.55, 2.25, w1("Tail1")),
    (V(0, 24.0, 6.4), 2.0, 1.9, w2("Tail1", "Tail2")),
    (V(0, 26.0, 5.6), 1.6, 1.6, w1("Tail2")),
    (V(0, 27.6, 4.85), 1.35, 1.35, w2("Tail2", "Tail3")),
    (V(0, 29.3, 4.2), 1.1, 1.1, w1("Tail3")),
    (V(0, 30.8, 3.6), 0.85, 0.9, w2("Tail3", "Tail4")),
    (V(0, 32.6, 2.9), 0.55, 0.6, w1("Tail4")),
    (V(0, 34.4, 2.2), 0.12, 0.14, w1("Tail4")),
], 12)
loft(BODY, "navy", cap1=True)
NB = len(BODY.rings) - 1
up_side = (-0.35 * math.pi, 0.5 * math.pi)
loft_blocks(BODY, 34, (0.0, 3.0), up_side, tan_p=0.4, half=True)          # neck
loft_blocks(BODY, 44, (2.0, 7.2), up_side, tan_p=0.18, half=True)         # chest + hips
loft_blocks(BODY, 10, (2.2, 7.0), (-0.5 * math.pi, -0.3 * math.pi), tan_p=0.0, half=True,
            out=(0.05, 0.2))                                              # belly
loft_blocks(BODY, 36, (7.0, 13.5), up_side, tan_p=0.22, half=True, size=(0.7, 1.15))   # tail
# tan armour patches (irregular clusters like the reference flank "F" plate)
for kr, ar, cnt in (((3.2, 4.4), (-0.05, 0.45), 6), ((1.4, 2.4), (0.55, 1.2), 5)):
    loft_blocks(BODY, cnt, kr, ar, tan_p=1.0, half=True, size=(1.0, 1.3), out=(0.25, 0.5))


def body_top(s):
    """highest surface z of the body loft at distance s (for crystal bases)."""
    for k in range(NB):
        s0, s1 = BODY.rings[k][0].y, BODY.rings[k + 1][0].y
        if s <= s1:
            f = (s - s0) / (s1 - s0)
            return BODY.point(k + f, math.pi / 2)[0].z
    return BODY.rings[-1][0].z


def body_side(s, a):
    for k in range(NB):
        if s <= BODY.rings[k + 1][0].y:
            f = (s - BODY.rings[k][0].y) / (BODY.rings[k + 1][0].y - BODY.rings[k][0].y)
            return BODY.point(k + f, a)
    return BODY.point(NB - 0.01, a)


# glow cracks flush with the flank surface
for s, a in ((10.8, -0.1), (12.9, 0.35), (13.6, -0.45), (16.2, 0.4), (19.0, -0.2)):
    p, nn, t = body_side(s, a)
    oriented_box(p + nn * 0.06, nn, t, 0.3, 1.5, 0.3, None, "Chest" if s < 15 else "Hips", True,
                 group="glow", uv="glow", roll=25, tilt=0)

# ---------------- HEAD (bone Head) -------------------------------------------
H = "Head"
HEAD = Loft([
    (V(0, 0.6, 10.15), 1.0, 0.75, w1(H)),
    (V(0, 1.6, 10.3), 1.6, 1.0, w1(H)),
    (V(0, 3.2, 10.6), 2.0, 1.3, w1(H)),
    (V(0, 4.9, 10.7), 2.4, 1.45, w1(H)),
    (V(0, 6.6, 10.3), 2.5, 1.65, w1(H)),
    (V(0, 7.8, 9.9), 2.1, 1.6, w1(H)),
], 10)
loft(HEAD, "navy", cap0=True,
     matfn=lambda k, j: "tan" if (k <= 1 and j in (0, 1, 8, 9)) or k == 0 and j == -1 else "navy")
loft_blocks(HEAD, 14, (2.3, 4.6), (-0.1 * math.pi, 0.5 * math.pi), tan_p=0.45, half=True, size=(0.8, 1.2))
loft_blocks(HEAD, 6, (0.2, 2.0), (0.1 * math.pi, 0.5 * math.pi), tan_p=0.9, half=True, size=(0.7, 1.0),
            out=(0.05, 0.25))
box(-1.1, 1.1, 3.3, 5.5, 11.55, 12.15, "tan", H, skip=("-z",))          # forehead plate
box(-1.7, 1.7, 0.9, 5.8, 9.1, 9.5, "tan", H)                            # upper lip rail
for sx in (1,):
    f = rot_frame((1.6, 3.5, 11.4), "Y", math.radians(-18))
    box(0.95, 2.25, 2.85, 4.2, 11.0, 11.85, "tan", H, frame=f, skip=("-z",), mirror=True)  # brow ridge
    box(1.45, 2.3, 2.55, 3.35, 10.35, 11.0, bone=H, group="glow", uv="glow", mirror=True)   # eye
# mouth glow + throat
box(-1.45, 1.45, 1.3, 6.2, 8.2, 9.3, bone=H, group="glow", uv="mouth")
# upper teeth (hang down)
for x in (-1.1, -0.37, 0.37, 1.1):
    pyramid(V(x, 1.05, 9.15), (0, 0, -1), 0.75 if abs(x) > 1 else 0.5, 0.2, H)
for s, L in ((1.9, 0.6), (2.9, 0.5), (3.9, 0.55), (4.9, 0.45)):
    pyramid(V(1.5, s, 9.15), (0.15, 0, -1), L, 0.2, H, mirror=True)

# ---------------- JAW (bone Jaw), modelled open like the reference -------
J = "Jaw"
JAW_PIVOT = (0.0, 5.7, 9.0)
jf = rot_frame(JAW_PIVOT, "X", math.radians(22))
JAW = Loft([
    (V(0, 0.9, 8.0), 1.05, 0.5, w1(J)),
    (V(0, 2.2, 8.05), 1.5, 0.55, w1(J)),
    (V(0, 4.1, 8.1), 1.75, 0.6, w1(J)),
    (V(0, 6.2, 8.25), 1.8, 0.7, w1(J)),
], 8)
loft(JAW, "tan", cap0=True, frame=jf, matfn=lambda k, j: "navy" if j in (3, 4) else "tan")
loft_blocks(JAW, 5, (0.3, 2.6), (-0.2 * math.pi, 0.2 * math.pi), tan_p=1.0, half=True, size=(0.6, 0.9),
            out=(0.05, 0.2), frame=jf, thick=(0.4, 0.55))
for x in (-1.0, -0.33, 0.33, 1.0):
    pyramid(jf(V(x, 1.25, 8.45)), (0, 0, 1), 0.65 if abs(x) > 0.5 else 0.5, 0.2, J)
for s in (2.2, 3.2, 4.2, 5.1):
    pyramid(jf(V(1.4, s, 8.5)), (0.1, 0, 1), 0.45, 0.18, J, mirror=True)
for s, L in ((1.9, 0.8), (3.2, 0.95), (4.6, 0.8)):                      # jaw-side horn spikes
    pyramid(jf(V(1.65, s, 8.3)), (0.75, 0.35, 0.6), L, 0.28, J, mat="tan", mirror=True)
pyramid(jf(V(0.0, 0.9, 7.6)), (0, -0.6, -0.8), 0.6, 0.3, J, mat="tan")  # chin spike


# ---------------- LEGS: tapered rounded limbs, claw toes --------------------
def claw(base, d, L, wdt, hgt, bone):
    f = dir_frame(base, d)
    box(-wdt / 2, wdt / 2, 0, L, -hgt / 2, hgt / 2, "tan", bone, frame=f, taper=(0.45, 0.45),
        skip=("-y",), mirror=True)


def leg(x, rings, foot, toes, bones, tan_cells):
    U, F, Hd = bones
    LEG = Loft([(V(x + dx, s, z), rx, rs, w) for (dx, s, z, rx, rs, w) in rings], 8)
    loft(LEG, "navy", mirror=True,
         matfn=lambda k, j: "tan" if (j == 3 and k in (2, 3)) or (j in (4, 5) and k == 1) else "navy")
    FOOT = Loft([(V(x, s, z), rx, rz, w1(Hd)) for (s, z, rx, rz) in foot], 8)
    loft(FOOT, "navy", mirror=True, cap1=True)
    for dx, L in toes:
        claw(V(x + dx, foot[-1][0] + 0.4, 0.6), (dx * 0.15, -1, -0.28), L, 1.0, 0.95, Hd)
    loft_blocks(LEG, 14, (0.3, 2.0), (-0.9 * math.pi, 0.9 * math.pi), tan_p=0.2, mirror=True)
    loft_blocks(LEG, 9, (2.0, 4.6), (-0.9 * math.pi, 0.9 * math.pi), tan_p=0.25, mirror=True,
                size=(0.75, 1.15))
    loft_blocks(LEG, tan_cells, (0.4, 2.2), (-0.35 * math.pi, 0.25 * math.pi), tan_p=1.0, mirror=True,
                size=(1.0, 1.3), out=(0.2, 0.45))
    return LEG


FRONT = leg(4.3, [
    (-0.4, 10.4, 11.0, 2.3, 2.8, w1("UpperArm.L")),
    (0.1, 10.3, 8.2, 2.45, 2.85, w1("UpperArm.L")),
    (0.1, 10.15, 5.8, 2.1, 2.35, w2("UpperArm.L", "Forearm.L", 0.2)),
    (0.0, 10.05, 4.0, 1.75, 2.0, w2("UpperArm.L", "Forearm.L", 0.6)),
    (0.0, 9.75, 2.3, 1.55, 1.75, w1("Forearm.L")),
    (0.0, 9.6, 1.1, 1.6, 1.85, w2("Forearm.L", "Hand.L", 0.6)),
], [(11.3, 0.75, 1.7, 0.75), (9.5, 0.82, 1.95, 0.82), (7.7, 0.7, 1.85, 0.65)],
    [(-1.25, 1.4), (0.0, 1.55), (1.25, 1.4)], ("UpperArm.L", "Forearm.L", "Hand.L"), 6)
REAR = leg(4.25, [
    (-0.4, 18.0, 10.9, 2.35, 3.1, w1("Thigh.L")),
    (0.1, 18.0, 8.0, 2.5, 3.1, w1("Thigh.L")),
    (0.1, 17.6, 5.6, 2.1, 2.45, w2("Thigh.L", "Shin.L", 0.2)),
    (0.0, 17.45, 4.0, 1.75, 2.0, w2("Thigh.L", "Shin.L", 0.6)),
    (0.0, 17.8, 2.3, 1.55, 1.75, w1("Shin.L")),
    (0.0, 17.9, 1.1, 1.6, 1.85, w2("Shin.L", "Foot.L", 0.6)),
], [(19.6, 0.75, 1.7, 0.75), (17.7, 0.82, 1.95, 0.82), (15.9, 0.7, 1.85, 0.65)],
    [(-1.2, 1.3), (0.0, 1.45), (1.2, 1.3)], ("Thigh.L", "Shin.L", "Foot.L"), 7)
# side toes
claw(V(5.9, 9.5, 0.55), (1, -0.2, -0.2), 0.9, 0.8, 0.8, "Hand.L")
claw(V(5.9, 17.8, 0.55), (1, -0.2, -0.2), 0.8, 0.8, 0.8, "Foot.L")
# joint glow
for (lp, kf, a, bone) in ((FRONT, 2.6, 0.2, "UpperArm.L"), (REAR, 2.6, 0.1, "Thigh.L"),
                          (FRONT, 0.9, -2.6, "UpperArm.L"), (REAR, 0.9, 2.8, "Thigh.L")):
    p, nn, t = lp.point(kf, a)
    oriented_box(p + nn * 0.06, nn, t, 1.2, 0.3, 0.3, None, bone, True, group="glow", uv="glow", roll=20, tilt=0)


# ---------------- CRYSTALS ----------------
back = Vector((0, 1, 0))
up = Vector((0, 0, 1))
SPINE = [  # s, base z, length, radius, bone
    (3.4, 11.9, 1.7, 0.42, "Head"),
    (4.9, 12.0, 2.5, 0.55, "Head"),
    (6.9, None, 2.6, 0.55, "Neck"),
    (9.3, None, 3.1, 0.62, "Neck"),
    (11.6, None, 3.5, 0.68, "Chest"),
    (13.5, None, 3.3, 0.66, "Chest"),
    (15.4, None, 3.9, 0.72, "Hips"),
    (17.2, None, 3.5, 0.68, "Hips"),
    (19.0, None, 3.2, 0.64, "Hips"),
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
        z = body_top(s) - 0.05
    L *= 1.25
    r *= 1.2
    crystal(V(0, s, z), up + back * 0.55, L, r, bone)
    if L > 1.4:  # flanking pair of smaller crystals (top view shows a cluster at each spine step)
        crystal(V(0.75, s + 0.5, z - 0.25), up + back * 0.45 + Vector((0.5, 0, 0)), L * 0.55, r * 0.7,
                bone, mirror=True)
# tan stone spikes between crystals on the neck/shoulders (reference hero view)
for s, z, L in ((8.1, 12.2, 2.0), (10.6, 12.8, 2.4), (5.9, 11.9, 1.4)):
    f = dir_frame(V(0, s, body_top(s) - 0.3), up + back * 0.3)
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
        q = body_side(base[1], 0.35)[0]
        base = (q.x - 0.1, base[1], q.z)
    crystal(V(*base), d, L, r, bone, mirror=True)


# ==========================================================================
# assemble meshes
# ==========================================================================
def flip_name(b):
    return b[:-2] + ".R" if b and b.endswith(".L") else b


def mirrored(pr):
    verts = [Vector((-v.x, v.y, v.z)) for v in pr["verts"]]
    faces = [(tuple(reversed(ids)), list(reversed(uvs))) for ids, uvs in pr["faces"]]
    out = dict(pr, verts=verts, faces=faces, bone=flip_name(pr["bone"]), mirror=False)
    if pr.get("weights"):
        out["weights"] = [{flip_name(k): v for k, v in w.items()} for w in pr["weights"]]
    return out


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
    verts, faces, uvs, vw, smooth = [], [], [], [], []
    for pr in prims:
        o = len(verts)
        for i, v in enumerate(pr["verts"]):
            verts.append((v.x, v.y - S_OFF, v.z * Z_SCALE))
            vw.append(pr["weights"][i] if pr.get("weights") else {pr["bone"]: 1.0})
        for ids, fuv in pr["faces"]:
            faces.append(tuple(o + i for i in ids))
            uvs.append(fuv)
            smooth.append(pr.get("smooth", False))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    uvl = me.uv_layers.new(name="UVMap")
    for poly, fuv in zip(me.polygons, uvs):
        for li, uv in zip(poly.loop_indices, fuv):
            uvl.data[li].uv = uv
    for poly, sm in zip(me.polygons, smooth):
        poly.use_smooth = sm
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    groups = {}
    for i, w in enumerate(vw):
        for b, val in w.items():
            if b not in groups:
                groups[b] = ob.vertex_groups.new(name=b)
            groups[b].add([i], val, "REPLACE")
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
