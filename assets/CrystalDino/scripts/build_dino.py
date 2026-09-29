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
DENSITY = float(os.environ.get("DINO_DENSITY", "0.38"))
TRI_BUDGET = 4990

rng = random.Random(11)

# --------------------------------------------------------------------------
# UV atlas helpers (see make_textures.py for the layout)
# --------------------------------------------------------------------------
CELL = 64
REG = {"navy": (0, 0, 10, 16), "tan": (640, 0, 6, 9), "gum": (896, 832, 1, 3), "tongue": (960, 832, 1, 3)}


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


def stud_uvs(mat, pts):
    """Atlas UVs for a face whose vertices have 2D coords `pts` measured in studs.
    One texture cell = one stud exactly, so the inlet grid never stretches. The inlet texture is
    periodic per cell, so the face is shifted by whole cells to fit the region: the fractional
    phase is kept, which also keeps neighbouring faces seamless."""
    if mat not in ("navy", "tan"):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        q = cell_uvs(mat, max(xs) - min(xs), max(ys) - min(ys))
        return (q * 2)[: len(pts)]
    x0, y0, cols, rows = REG[mat]
    mu, mv = math.floor(min(p[0] for p in pts)), math.floor(min(p[1] for p in pts))
    loc = [(p[0] - mu, p[1] - mv) for p in pts]
    su, sv = max(l[0] for l in loc), max(l[1] for l in loc)
    k = min(1.0, cols / max(su, 1e-6), rows / max(sv, 1e-6))   # only shrinks faces bigger than the region
    loc = [(a * k, b * k) for a, b in loc]
    nu, nv = math.ceil(su * k - 1e-6), math.ceil(sv * k - 1e-6)
    ci, cj = rng.randint(0, cols - max(nu, 1)), rng.randint(0, rows - max(nv, 1))
    return [px(x0 + (ci + a) * CELL, y0 + (cj + nv - b) * CELL) for a, b in loc]


def planar_uvs(mat, pts3):
    """stud_uvs for an arbitrary planar polygon given its 3D vertices (in studs)."""
    e1 = (pts3[1] - pts3[0]).normalized()
    n = (pts3[1] - pts3[0]).cross(pts3[-1] - pts3[0])
    e2 = n.cross(e1).normalized() if n.length > 1e-9 else e1.orthogonal().normalized()
    return stud_uvs(mat, [((p - pts3[0]).dot(e1), (p - pts3[0]).dot(e2)) for p in pts3])


GLOW_UV = [px(662, 1000), px(746, 1000), px(746, 852), px(662, 852)]
MOUTH_UV = [px(900, 1016), px(1020, 1016), px(1020, 840), px(900, 840)]
PUPIL_UV = [px(650, 1020), px(758, 1020), px(704, 1006)]
IRIS_UV = [px(652, 862), px(756, 862), px(704, 928)]  # rim, rim, bright centre


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
            uvs = planar_uvs(mat, [verts[i] for i in ids])
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

    def __init__(self, rings, sides, sq=2.0, ref=None):
        self.rings, self.sides, self.sq = rings, sides, sq
        self.frames = []
        n = len(rings)
        for k, (c, rx, rw, wts) in enumerate(rings):
            a = rings[max(k - 1, 0)][0]
            b = rings[min(k + 1, n - 1)][0]
            t = (b - a).normalized()
            if ref is not None:            # frame from an up vector (path may run along x)
                w_ = (Vector(ref) - t * Vector(ref).dot(t)).normalized()
                u = w_.cross(t).normalized()
            else:
                u = Vector((1, 0, 0))
                u = (u - t * u.dot(t)).normalized()
            w = u.cross(t)
            if w.z < -0.5 or (abs(w.z) < 0.5 and w.y < 0):
                w = -w
            self.frames.append((t, u, w))

    def angle(self, j):
        return math.pi / 2 + math.pi / self.sides + j * math.tau / self.sides

    def cs(self, a):
        """superellipse cos/sin (sq=2 ellipse, sq>2 rounded square)."""
        c, s_ = math.cos(a), math.sin(a)
        e = 2.0 / self.sq
        return math.copysign(abs(c) ** e, c), math.copysign(abs(s_) ** e, s_)

    def point(self, kf, a, out=0.0):
        """surface point, outward normal and tangent at fractional ring index kf, angle a."""
        k = min(int(kf), len(self.rings) - 2)
        f = kf - k
        pts, nrm, tng = [], [], []
        for kk in (k, k + 1):
            c, rx, rw, _ = self.rings[kk]
            t, u, w = self.frames[kk]
            ca, sa = self.cs(a)
            pts.append(c + u * (rx * ca) + w * (rw * sa))
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
            ca, sa = L.cs(a)
            verts.append(c + u * (rx * ca) + w * (rw * sa))
            weights.append(wts)
    # continuous surface coordinates in studs: U around each ring, Vc along the loft
    U = [[0.0] * (S + 1) for _ in rings]
    Vc = [[0.0] * S for _ in rings]
    for k in range(len(rings)):
        for j in range(S):
            U[k][j + 1] = U[k][j] + (verts[k * S + (j + 1) % S] - verts[k * S + j]).length
            if k:
                Vc[k][j] = Vc[k - 1][j] + (verts[k * S + j] - verts[(k - 1) * S + j]).length
    for k in range(len(rings) - 1):
        for j in range(S):
            j1 = (j + 1) % S
            ids = (k * S + j, k * S + j1, (k + 1) * S + j1, (k + 1) * S + j)
            m = matfn(k, j) if matfn else mat
            # orthonormal projection onto the face (no shear, so inlets stay square), offset by the
            # face's running surface coordinates so the inlet grid stays in phase with its neighbours
            p0 = verts[ids[0]]
            e1 = (verts[ids[1]] - p0).normalized()
            nrm = (verts[ids[1]] - p0).cross(verts[ids[3]] - p0)
            e2 = nrm.cross(e1).normalized()
            if (verts[ids[3]] - p0).dot(e2) < 0:
                e2 = -e2
            pts = [(U[k][j] + (verts[i] - p0).dot(e1), Vc[k][j] + (verts[i] - p0).dot(e2)) for i in ids]
            faces.append((ids, stud_uvs(m, pts)))
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
        _, uu, ww = L.frames[which]
        for j in range(S):
            j1 = (j + 1) % S
            a, b = which * S + j, which * S + j1
            tri = (a, b, ci)
            fn = (verts[b] - verts[a]).cross(verts[ci] - verts[a])
            if fn.dot(t * sgn) < 0:
                tri = (b, a, ci)
            cap = [((verts[i] - c).dot(uu), (verts[i] - c).dot(ww)) for i in tri]
            faces.append((tri, stud_uvs(m, cap)))
    verts = [frame(v) for v in verts]
    PRIMS.append(dict(verts=verts, faces=faces, group=group, bone=None, weights=weights,
                      mirror=mirror, smooth=True))
    return PRIMS[-1]


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
                mirror=False, frame=IDENT, thick=(0.55, 0.8), avoid=()):
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
        reach = 0.75 * max(sa, sb)  # block half-diagonal, so no corner pokes into the keep-clear zone
        if any((Vector((abs(p.x), p.y, p.z)) - c).length < r + reach for c, r in avoid):
            continue
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
    # measured from the reference side view: ~5 studs long, ~4 tall, blunt squared snout
    (V(0, 1.05, 10.12), 0.88, 0.95, w1(H)),     # smaller squared nose
    (V(0, 1.95, 10.35), 1.1, 1.2, w1(H)),         # dip -> small concave curve along the nose bridge
    (V(0, 3.2, 10.9), 1.6, 1.68, w1(H)),
    (V(0, 4.6, 11.05), 2.2, 1.92, w1(H)),
    (V(0, 5.8, 10.9), 2.25, 1.85, w1(H)),
    (V(0, 6.9, 10.6), 2.0, 1.6, w1(H)),
], 12, sq=3.6)
head_prim = loft(HEAD, "navy", cap0=True, cap1=True,
                 matfn=lambda k, j: "tan" if (k <= 1 and j in (0, 1, 10, 11)) or k == 0 and j == -1 else "navy")


# ---- eye: almond socket carved into the head, gem eyeball with a slit pupil ----
def eye_frame():
    """Socket centre on the head surface and its (e1 along, e2 up, n out) frame, +x side."""
    kf = 2 + (4.0 - 3.2) / 1.4          # just behind the snout, where the head is widest
    p, n0, t = HEAD.point(kf, 0.3)
    n = (n0 + Vector((0, -1.35, 0.1))).normalized()   # socket faces forward-out (visible front and side)
    e1 = (t - n * t.dot(n)).normalized()
    e1 = Matrix.Rotation(math.radians(16), 3, n) @ e1      # slanted: back corner higher (fierce look)
    e2 = n.cross(e1).normalized()
    return p, e1, e2, n


EYE_SCALE = 1.6   # reference eyes are large glowing almonds (~2.4 x 1 studs)
ALMOND = [(a * EYE_SCALE, b * EYE_SCALE) for a, b in
          [(0.74, 0.0), (0.34, 0.31), (-0.36, 0.29), (-0.74, 0.02), (-0.34, -0.27), (0.36, -0.25)]]


def almond_prism(c, e1, e2, n, d0, d1, s0, s1, shift0=Vector()):
    """closed almond prism from depth d0 (scale s0, offset shift0) to d1 (scale s1) along n."""
    ring0 = [c + n * d0 + shift0 + (e1 * a + e2 * b) * s0 for a, b in ALMOND]
    ring1 = [c + n * d1 + (e1 * a + e2 * b) * s1 for a, b in ALMOND]
    verts = ring0 + ring1
    k = len(ALMOND)
    faces = [(i, (i + 1) % k, k + (i + 1) % k, k + i) for i in range(k)]
    faces += [tuple(range(k - 1, -1, -1)), tuple(range(k, 2 * k))]
    # make winding outward
    ctr = sum(verts, Vector()) / len(verts)
    out = []
    for f in faces:
        a, b, cc = verts[f[0]], verts[f[1]], verts[f[2]]
        fn = (b - a).cross(cc - a)
        fc = sum((verts[i] for i in f), Vector()) / len(f)
        out.append(f if fn.dot(fc - ctr) > 0 else tuple(reversed(f)))
    return verts, out


def fuse(prim, others, bone):
    """Boolean-union other closed prims into prim, in place, keeping every part's UVs."""
    carve(prim, [(o["verts"], [f for f, _ in o["faces"]], [u for _, u in o["faces"]]) for o in others], bone,
          op="UNION")


def carve(prim, cutters, bone, op="DIFFERENCE"):
    """Boolean-subtract closed cutter meshes from a closed prim, in place (socket walls stay flat)."""
    sc = bpy.context.scene
    me = bpy.data.meshes.new("carve_src")
    me.from_pydata([tuple(v) for v in prim["verts"]], [], [f for f, _ in prim["faces"]])
    uvl = me.uv_layers.new(name="UVMap")
    for poly, (_, fuv) in zip(me.polygons, prim["faces"]):
        poly.use_smooth = True
        for li, uv in zip(poly.loop_indices, fuv):
            uvl.data[li].uv = uv
    src = bpy.data.objects.new("carve_src", me)
    sc.collection.objects.link(src)
    cv, cf = [], []
    cu = []
    for cutter in cutters:
        verts, faces = cutter[0], cutter[1]
        uvs = cutter[2] if len(cutter) > 2 else [None] * len(faces)
        o = len(cv)
        cv += verts
        cf += [tuple(o + i for i in f) for f in faces]
        cu += uvs
    cme = bpy.data.meshes.new("carve_cut")
    cme.from_pydata([tuple(v) for v in cv], [], cf)
    cuv = cme.uv_layers.new(name="UVMap")
    for poly, fuv in zip(cme.polygons, cu):
        poly.use_smooth = fuv is not None
        if fuv is None:
            q = cell_uvs("navy", 1, 1)
            fuv = (q * 3)[: len(poly.loop_indices)]
        for li, uv in zip(poly.loop_indices, fuv):
            cuv.data[li].uv = uv
    cut = bpy.data.objects.new("carve_cut", cme)
    sc.collection.objects.link(cut)
    cut.hide_render = True
    mod = src.modifiers.new("Socket", "BOOLEAN")
    mod.operation, mod.solver, mod.object = op, "EXACT", cut
    ev = src.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m2 = ev.to_mesh()
    uv2 = m2.uv_layers["UVMap"]
    prim["verts"] = [v.co.copy() for v in m2.vertices]
    prim["faces"] = [(tuple(p.vertices), [tuple(uv2.data[li].uv) for li in p.loop_indices]) for p in m2.polygons]
    prim["smooth"] = [p.use_smooth for p in m2.polygons]
    prim["weights"] = [{bone: 1.0}] * len(prim["verts"])
    ev.to_mesh_clear()
    for ob in (src, cut):
        bpy.data.objects.remove(ob)


EYE_C, EYE_E1, EYE_E2, EYE_N = eye_frame()
mir_v = lambda v: Vector((-v.x, v.y, v.z))
sockets = []
for sgn in (1, -1):
    m = (lambda v: v) if sgn > 0 else mir_v
    c, e1, e2, n = m(EYE_C), m(EYE_E1), m(EYE_E2), m(EYE_N)
    # outer rim skewed forward: the socket flares open toward the snout so the eye reads from the front
    sockets.append(almond_prism(c, e1, e2, n, 0.9, -0.95, 1.05, 0.8, shift0=Vector((0, -0.15, 0))))
carve(head_prim, sockets, H)


def head_surface(x, s_):
    """Point + outward normal on the upper head surface at lateral offset x, distance s_."""
    ys = [r[0].y for r in HEAD.rings]
    k = max(i for i in range(len(ys) - 1) if ys[i] <= s_) if s_ >= ys[0] else 0
    kf = min(k + (s_ - ys[k]) / (ys[k + 1] - ys[k]), len(ys) - 1.001)
    best = min((abs(HEAD.point(kf, a)[0].x - x), a) for a in [i * math.pi / 200 for i in range(-20, 101)])
    p, n, _ = HEAD.point(kf, best[1])
    return p, n


# Brow ridge (reference): one heavy, smooth ridge per side, low at the inner front corner just over the
# eye and sweeping up and back to the top outer corner of the skull (angry V from the front). Each
# ring is seated on the skull surface (60% buried) and the ridge is boolean-unioned into the head
# mesh, so it grows out of the skull with no seam or gap.
BROW_SPEC = [  # x, s, half-width, half-height, lift above the skull surface
    (0.9, 2.7, 0.48, 0.34, 0.62),     # blunt squared front edge overhanging the eye
    (1.3, 3.3, 0.66, 0.4, 0.64),
    (1.75, 4.3, 0.72, 0.4, 0.4),
    (1.95, 5.35, 0.6, 0.34, 0.2),
    (1.9, 6.3, 0.25, 0.16, -0.05),
]
rings = []
for x, s_, rx, rw, lift in BROW_SPEC:
    p, n = head_surface(x, s_)
    rings.append((p + n * (lift - rw * 0.6), rx, rw, w1(H)))
BROW = Loft([(c, rx / 0.7071, rw / 0.7071, w) for c, rx, rw, w in rings], 4)   # rectangular section: flat top, crisp edges
brow_r = loft(BROW, "tan", cap0=True, cap1=True)
PRIMS.remove(brow_r)
brow_l = dict(brow_r, verts=[mir_v(v) for v in brow_r["verts"]],
              faces=[(tuple(reversed(f)), list(reversed(u))) for f, u in brow_r["faces"]])
fuse(head_prim, [brow_r, brow_l], H)

# eyeball: faceted gem sitting deep in the socket, deep blue rim -> bright centre
rim = [EYE_C + EYE_N * -0.5 + (EYE_E1 * a + EYE_E2 * b) * 0.88 for a, b in ALMOND]
apex = EYE_C + EYE_N * -0.22 + EYE_E1 * 0.04
faces = [((i, (i + 1) % 6, 6), IRIS_UV) for i in range(6)]
fn = (rim[1] - rim[0]).cross(apex - rim[0])
if fn.dot(EYE_N) < 0:
    faces = [((b, a, c), [u[1], u[0], u[2]]) for (a, b, c), u in faces]
add_prim(rim + [apex], faces, "glow", H, True)
# slit pupil: white-hot core, raised just in front of the eyeball
pc = EYE_C + EYE_N * -0.23 + EYE_E1 * 0.04
pv = [pc + EYE_E2 * 0.36, pc + EYE_E1 * 0.13, pc - EYE_E2 * 0.36, pc - EYE_E1 * 0.13]
ptip = pc + EYE_N * 0.12
faces = [((i, (i + 1) % 4, 4), PUPIL_UV) for i in range(4)]
fn = (pv[1] - pv[0]).cross(ptip - pv[0])
if fn.dot(EYE_N) < 0:
    faces = [((b, a, c), [u[1], u[0], u[2]]) for (a, b, c), u in faces]
add_prim(pv + [ptip], faces, "glow", H, True)

EYE_AVOID = [(EYE_C, 2.0), (EYE_C + EYE_N * 1.1, 1.3), (EYE_C + Vector((0, -1.6, 0)), 1.4), (EYE_C + Vector((-0.4, -2.6, 0)), 1.2)]  # socket + sight lines
loft_blocks(HEAD, 14, (2.3, 4.6), (-0.1 * math.pi, 0.5 * math.pi), tan_p=0.45, half=True, size=(0.8, 1.2),
            avoid=EYE_AVOID)
loft_blocks(HEAD, 6, (0.2, 2.0), (0.1 * math.pi, 0.5 * math.pi), tan_p=0.9, half=True, size=(0.7, 1.0),
            out=(0.05, 0.25), avoid=EYE_AVOID)
box(-1.2, 1.2, 3.2, 5.6, 12.45, 13.05, "tan", H, skip=("-z",))          # forehead plate
# upper lip rim: a rounded U-shaped band that follows the mouth opening (not a flat plank)
LIP_PATH = [(1.5, 5.8), (1.52, 4.6), (1.48, 3.4), (1.38, 2.4), (1.15, 1.6), (0.7, 1.12), (0.0, 0.98)]
LIP_PATH = LIP_PATH + [(-x, s_) for x, s_ in reversed(LIP_PATH[:-1])]
LIP_Z = 9.3
LIP = Loft([(V(x, s_, LIP_Z), 0.3, 0.2, w1(H)) for x, s_ in LIP_PATH], 6, sq=3.0, ref=(0, 0, 1))
loft(LIP, "tan", cap0=True, cap1=True)


def along(path, step, start, end):
    """Points spaced `step` apart along a 2D polyline, between arc lengths start..end."""
    segs, total = [], 0.0
    for (x0, y0), (x1, y1) in zip(path, path[1:]):
        L_ = math.hypot(x1 - x0, y1 - y0)
        segs.append((x0, y0, x1, y1, total, L_))
        total += L_
    out, d = [], start
    while d <= total - end + 1e-6:
        for x0, y0, x1, y1, t0, L_ in segs:
            if d <= t0 + L_:
                f = (d - t0) / L_
                out.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f, d / total))
                break
        d += step
    return out

# mouth interior: roof of the mouth and back of the throat (gum red, open mouth - no solid block)
box(-1.25, 1.25, 1.55, 6.3, 9.0, 9.2, "gum", H, skip=("+z",))            # palate (tucked inside the lip rim)
box(-1.45, 1.45, 5.95, 6.35, 7.6, 9.1, "gum", H, skip=("+y",))          # throat wall
# upper teeth: a packed row following the lip rim, bases buried in it (no gaps); fangs at the corners
for i, (x, s_, f) in enumerate(along(LIP_PATH, 0.46, 0.6, 0.6)):
    fang = abs(f - 0.5) > 0.2 and abs(f - 0.5) < 0.3
    L_ = 0.95 if fang else (0.7 if i % 2 else 0.55)
    pyramid(V(x, s_, LIP_Z), (x * 0.06, 0, -1), L_ + 0.2, 0.27, H)

# ---------------- JAW (bone Jaw), modelled open like the reference -------
J = "Jaw"
JAW_PIVOT = (0.0, 5.7, 9.0)
jf = rot_frame(JAW_PIVOT, "X", math.radians(22))
JAW = Loft([
    # deeper, wider lower jaw (reference: ~2 studs deep)
    (V(0, 0.9, 7.85), 1.3, 0.75, w1(J)),
    (V(0, 2.2, 7.75), 1.7, 0.88, w1(J)),
    (V(0, 4.1, 7.7), 1.95, 0.98, w1(J)),
    (V(0, 6.2, 7.8), 2.0, 1.05, w1(J)),
], 8, sq=3.6)
loft(JAW, "tan", cap0=True, frame=jf, matfn=lambda k, j: "navy" if j in (3, 4) else "gum" if j == 7 else "tan")
loft_blocks(JAW, 5, (0.3, 2.6), (-0.2 * math.pi, 0.2 * math.pi), tan_p=1.0, half=True, size=(0.6, 0.9),
            out=(0.05, 0.2), frame=jf, thick=(0.4, 0.55))


def jaw_top(s_):
    """(half width, top z) of the lower jaw loft at distance s_ (jaw local space)."""
    for (c0, rx0, rw0, _), (c1, rx1, rw1, _) in zip(JAW.rings, JAW.rings[1:]):
        if s_ <= c1.y:
            f = max(0.0, (s_ - c0.y) / (c1.y - c0.y))
            return rx0 + (rx1 - rx0) * f, c0.z + rw0 + (c1.z + rw1 - c0.z - rw0) * f
    return JAW.rings[-1][1], JAW.rings[-1][0].z + JAW.rings[-1][2]


# lower teeth: packed rows seated in the gums along the jaw rim (bases buried so there are no gaps)
for i in range(5):
    x = -0.9 + i * 0.45
    hw, tz = jaw_top(1.25)
    pyramid(jf(V(x, 1.25, tz - 0.2)), (0, 0, 1), (0.7 if abs(x) > 0.5 else 0.5) + 0.2, 0.26, J)
for i in range(8):
    s_ = 1.75 + i * 0.5
    hw, tz = jaw_top(s_)
    pyramid(jf(V(hw * 0.78, s_, tz - 0.2)), (0.1, 0, 1), (0.6 if i % 2 else 0.45) + 0.2, 0.26, J, mirror=True)
# tongue: rounded, tapering to a tip, lying on the floor of the lower jaw
TONGUE = Loft([(V(0, s_, jaw_top(s_)[1] + dz), rx, rw, w1(J)) for s_, dz, rx, rw in (
    (1.75, 0.02, 0.45, 0.14),
    (2.5, 0.08, 0.8, 0.22),
    (3.7, 0.12, 0.98, 0.26),
    (5.0, 0.1, 0.95, 0.26),
    (6.1, 0.02, 0.85, 0.22),
)], 8, sq=2.4)
loft(TONGUE, "tongue", cap0=True, frame=jf)
for s, L in ((1.9, 0.8), (3.2, 0.95), (4.6, 0.8)):                      # jaw-side horn spikes
    pyramid(jf(V(1.9, s, 8.0)), (0.75, 0.35, 0.6), L, 0.3, J, mat="tan", mirror=True)
pyramid(jf(V(0.0, 0.8, 7.2)), (0, -0.6, -0.8), 0.7, 0.34, J, mat="tan")  # chin spike


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
    (3.6, 12.6, 1.7, 0.42, "Head"),
    (5.0, 12.8, 2.5, 0.55, "Head"),
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
    ((1.4, 5.3, 12.4), (0.55, 0.35, 1), 2.0, 0.48, "Head"),      # head side crest
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
        sm = pr.get("smooth", False)
        smooth += sm if isinstance(sm, list) else [sm] * len(pr["faces"])
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
