"""Procedural geometry for the Stud Drake (sea-serpent drake from the reference sheet).

Pure-python mesh builder: produces verts, faces, per-face palette index and
per-vertex bone weights. Rest pose = side-view profile, straight in top view.
Axes: X = lateral, -Y = forward (snout), +Z = up. 1 unit = 1 m, length 8 m.
"""
import math
import random
import numpy as np
from mathutils import Vector, Matrix

# ---------------------------------------------------------------- palette
# sampled from the reference sheet colour swatches
PALETTE = {
    'NAVY':  (9, 35, 111),
    'ROYAL': (5, 66, 223),
    'CYAN':  (20, 199, 250),
    'TEAL':  (15, 188, 175),
    'AQUA':  (156, 243, 228),
    'CREAM': (254, 247, 238),
    'EYE':   (248, 246, 255),
    'PUPIL': (38, 18, 92),
    'MOUTH': (10, 120, 140),
}
PAL_NAMES = list(PALETTE.keys())
C = {k: i for i, k in enumerate(PAL_NAMES)}

rng = random.Random(7)


def blue():
    """Body blocks: mix of royal and navy like the reference bricks."""
    return C['NAVY'] if rng.random() < 0.33 else C['ROYAL']


LENGTH = 8.0
Y0 = -4.0


def Y(s):
    return Y0 + LENGTH * s


# side-view profile stations: s, centre z, half height, half width
STATIONS = np.array([
    # s     zc    hh    hw
    [0.105, 1.10, 0.30, 0.23],
    [0.170, 1.08, 0.36, 0.25],
    [0.210, 1.00, 0.45, 0.27],
    [0.270, 0.85, 0.52, 0.31],
    [0.340, 0.63, 0.52, 0.32],
    [0.410, 0.50, 0.44, 0.29],
    [0.550, 0.42, 0.35, 0.24],
    [0.680, 0.41, 0.27, 0.19],
    [0.790, 0.44, 0.22, 0.15],
    [0.860, 0.52, 0.16, 0.11],
    [0.920, 0.64, 0.10, 0.07],
    [0.950, 0.70, 0.05, 0.04],
])


def _smooth_interp(s, col):
    xs = STATIONS[:, 0]
    ys = STATIONS[:, col]
    # Catmull-Rom through stations
    s = float(np.clip(s, xs[0], xs[-1]))
    i = int(np.searchsorted(xs, s) - 1)
    i = max(0, min(i, len(xs) - 2))
    t = (s - xs[i]) / (xs[i + 1] - xs[i])
    p0 = ys[max(i - 1, 0)]; p1 = ys[i]; p2 = ys[i + 1]; p3 = ys[min(i + 2, len(xs) - 1)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                  (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


BODY_H = 1.18   # bulk multipliers (front/3-4 views read much chunkier than the side-view trace)
BODY_W = 1.30


def ZC(s): return _smooth_interp(s, 1) + 0.06 * max(0.0, 1 - abs(s - 0.4) / 0.4)
def HH(s): return _smooth_interp(s, 2) * BODY_H
def HW(s): return _smooth_interp(s, 3) * BODY_W


def spine_point(s):
    return Vector((0.0, Y(s), ZC(s)))


def spine_frame(s):
    e = 0.004
    t = (spine_point(s + e) - spine_point(s - e)).normalized()
    up = Vector((0.0, -t.z, t.y)).normalized()
    return t, up


# ---------------------------------------------------------------- skeleton
HEAD_ORIGIN = Vector((0.0, Y(0.125), 1.10))
JAW_HINGE_LOCAL = (-0.05, -0.12)       # (f, z) in head-local coords
JAW_OPEN = math.radians(40)

# spine bones along s (front chain points toward the head, back chain toward the tail)
SPINE_BONES = [
    # name, s_head, s_tail
    ('Neck2', 0.21, 0.125),
    ('Neck1', 0.29, 0.21),
    ('Spine2', 0.37, 0.29),
    ('Spine1', 0.45, 0.37),
    ('Spine3', 0.45, 0.53),
    ('Spine4', 0.53, 0.61),
    ('Tail1', 0.61, 0.69),
    ('Tail2', 0.69, 0.77),
    ('Tail3', 0.77, 0.84),
    ('Tail4', 0.84, 0.90),
    ('Tail5', 0.90, 0.965),
]
# ordered from head to tail with centre param, for weight blending
_CHAIN = sorted([(0.5 * (a + b), n) for n, a, b in SPINE_BONES])


def spine_weights(s):
    if s <= _CHAIN[0][0]:
        return {_CHAIN[0][1]: 1.0}
    if s >= _CHAIN[-1][0]:
        return {_CHAIN[-1][1]: 1.0}
    for (c0, n0), (c1, n1) in zip(_CHAIN, _CHAIN[1:]):
        if c0 <= s <= c1:
            t = (s - c0) / (c1 - c0)
            t = t * t * (3 - 2 * t)
            if n0 == n1:
                return {n0: 1.0}
            return {n0: 1.0 - t, n1: t}
    return {_CHAIN[-1][1]: 1.0}


def s_of_y(y):
    return (y - Y0) / LENGTH


# ---------------------------------------------------------------- builder
class MeshBuilder:
    def __init__(self):
        self.v = []
        self.w = []
        self.f = []
        self.fc = []
        self.fix = []   # desired outward direction for open faces, or None
        self.part = []

    def vert(self, co, w):
        self.v.append(Vector(co))
        self.w.append(dict(w))
        return len(self.v) - 1

    def face(self, idx, col, part='', fix=None):
        if len(idx) > 4:   # fan-triangulate n-gons (keeps tangent space exportable)
            for k in range(1, len(idx) - 1):
                self.face((idx[0], idx[k], idx[k + 1]), col, part, fix)
            return
        self.f.append(tuple(idx))
        self.fc.append(col)
        self.fix.append(fix)
        self.part.append(part)

    def tris(self):
        return sum(len(f) - 2 for f in self.f)


# ---------------------------------------------------------------- body tube
RING = [(0.62, 1.0), (1.0, 0.45), (1.0, -0.32), (0.97, -0.84), (0.45, -1.0),
        (-0.45, -1.0), (-0.97, -0.84), (-1.0, -0.32), (-1.0, 0.45), (-0.62, 1.0)]
# edge j joins RING[j] -> RING[j+1]; belly edges are cream
BELLY_EDGES = {2, 3, 4, 5, 6}


def build_body(mb):
    ss = list(np.linspace(0.105, 0.30, 9)) + list(np.linspace(0.30, 0.95, 27))[1:]
    rings = []
    for s in ss:
        c = spine_point(s)
        t, up = spine_frame(s)
        x = Vector((1, 0, 0))
        hh, hw = HH(s), HW(s)
        ring = []
        for u, v in RING:
            p = c + x * (u * hw) + up * (v * hh)
            w = {'Head': 1.0} if s < 0.12 else spine_weights(s)
            ring.append(mb.vert(p, w))
        rings.append((s, ring))
    n = len(RING)
    for (s0, r0), (s1, r1) in zip(rings, rings[1:]):
        for j in range(n):
            a, b = r0[j], r0[(j + 1) % n]
            c_, d = r1[(j + 1) % n], r1[j]
            if j in BELLY_EDGES:
                col = C['CREAM']
            else:
                col = blue()
            mb.face((a, b, c_, d), col, 'body')
    # front cap (buried in the head)
    mb.face(tuple(reversed(rings[0][1])), C['NAVY'], 'body')
    # tail tip
    s_tip = 0.965
    tip = mb.vert(spine_point(s_tip) + Vector((0, 0, 0.0)), spine_weights(s_tip))
    last = rings[-1][1]
    for j in range(n):
        mb.face((last[j], last[(j + 1) % n], tip), blue(), 'body')
    return rings


# ---------------------------------------------------------------- blades
SCHEMES = {
    # quads(+N), tips(+N), quads(-N), tips(-N), base cap
    'crystal': ('CYAN', 'AQUA', 'TEAL', 'CYAN', 'ROYAL'),
    'teal':    ('TEAL', 'AQUA', 'CYAN', 'TEAL', 'ROYAL'),
    'aqua':    ('AQUA', 'CYAN', 'CYAN', 'AQUA', 'ROYAL'),
    'royal':   ('ROYAL', 'CYAN', 'NAVY', 'ROYAL', 'NAVY'),
    'navy':    ('NAVY', 'ROYAL', 'ROYAL', 'NAVY', 'NAVY'),
}


def blade(mb, base, direction, length, width_hint, w, scheme='crystal', width=0.42,
          thick=0.12, bend=None, part='fin', mid=0.42):
    """Faceted crystal spike (flattened bipyramid), 14 tris."""
    P = Vector(base)
    D = Vector(direction).normalized()
    Wh = Vector(width_hint)
    W = (Wh - D * Wh.dot(D))
    if W.length < 1e-4:
        W = D.orthogonal()
    W.normalize()
    N = D.cross(W).normalized()
    wd = length * width
    th = length * thick
    M = P + D * (length * mid)
    T = P + D * length
    if bend is not None:
        T = T + Vector(bend) * length
    b0 = mb.vert(P + W * wd * 0.40, w)
    b2 = mb.vert(P + N * th * 0.45, w)
    b1 = mb.vert(P - W * wd * 0.40, w)
    b3 = mb.vert(P - N * th * 0.45, w)
    m0 = mb.vert(M + W * wd, w)
    m2 = mb.vert(M + N * th, w)
    m1 = mb.vert(M - W * wd * 0.55, w)
    m3 = mb.vert(M - N * th, w)
    t = mb.vert(T, w)
    qp, tp, qn, tn, cap = [C[k] for k in SCHEMES[scheme]]
    mb.face((b0, b2, b1, b3), cap, part)
    mb.face((b0, m0, m2, b2), qp, part)
    mb.face((b2, m2, m1, b1), qp, part)
    mb.face((b1, m1, m3, b3), qn, part)
    mb.face((b3, m3, m0, b0), qn, part)
    mb.face((m0, t, m2), tp, part)
    mb.face((m2, t, m1), tp, part)
    mb.face((m1, t, m3), tn, part)
    mb.face((m3, t, m0), tn, part)
    return T


FIN_THICK = 1.8

SAIL_SCHEMES = {  # front facets, rear facets
    'crystal': ('CYAN', 'AQUA'),
    'cyan': ('CYAN', 'TEAL'),
    'teal': ('TEAL', 'CYAN'),
    'royal': ('ROYAL', 'NAVY'),
    'blue': ('ROYAL', 'ROYAL'),
}


def sail(mb, B, T, U, bl, h, lean, th, w, scheme='crystal', bulge=0.22, part='fin'):
    """Broad shark-fin leaf: base edge along T, tip at U*h + T*lean. 8 tris, closed."""
    th *= FIN_THICK
    B = Vector(B); T = Vector(T).normalized(); U = Vector(U)
    U = (U - T * U.dot(T)).normalized()
    X = T.cross(U).normalized()
    bf = B - T * bl * 0.5
    bb = B + T * bl * 0.5
    tip = B + U * h + T * lean
    fm = bf + (tip - bf) * 0.5 - T * bl * bulge + U * 0.0
    bm = bb + (tip - bb) * 0.45 - T * bl * 0.10
    cen = (bf + bb + tip + fm) * 0.25
    ids = [mb.vert(p, w) for p in (bf, fm, tip, bm, bb)]
    rp = mb.vert(cen + X * th, w)
    rn = mb.vert(cen - X * th, w)
    fc, rc = [C[k] for k in SAIL_SCHEMES[scheme]]
    ring = ids  # bf, fm, tip, bm, bb (closed loop back to bf)
    cols = [fc, fc, rc, rc, rc]
    for i in range(5):
        a, b = ring[i], ring[(i + 1) % 5]
        mb.face((a, b, rp), cols[i], part)
        mb.face((b, a, rn), cols[i] if i != 1 else C[SAIL_SCHEMES[scheme][1]], part)
    return tip


def box(mb, center, axes, half, w, cols, part='box'):
    """Oriented box. axes = (X, Y, Z) unit vectors; cols = colour or 6-tuple."""
    cx = Vector(center)
    X, Yv, Z = [Vector(a) for a in axes]
    hx, hy, hz = half
    idx = []
    for sx, sy, sz in [(-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                       (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]:
        idx.append(mb.vert(cx + X * sx * hx + Yv * sy * hy + Z * sz * hz, w))
    if isinstance(cols, int):
        cols = [cols] * 6
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for fi, fcs in enumerate(faces):
        mb.face(tuple(idx[k] for k in fcs), cols[fi], part + ('_hidden' if fi == 0 and part == 'brick' else ''))


def beam(mb, a, b, thick, up_hint, w, col, part='beam'):
    a = Vector(a); b = Vector(b)
    Xv = (b - a)
    L = Xv.length
    Xv.normalize()
    Z = Vector(up_hint)
    Z = (Z - Xv * Z.dot(Xv)).normalized()
    Yv = Z.cross(Xv).normalized()
    box(mb, (a + b) * 0.5, (Xv, Yv, Z), (L * 0.5, thick[0], thick[1]), w, col, part)


def pyramid(mb, base, direction, length, half, w, col, side_hint=(1, 0, 0), part='tooth'):
    P = Vector(base)
    D = Vector(direction).normalized()
    S = Vector(side_hint)
    S = (S - D * S.dot(D)).normalized()
    F = D.cross(S).normalized()
    q = [mb.vert(P + S * sx * half + F * sf * half, w) for sx, sf in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
    tipc = P + D * length
    tq = [mb.vert(tipc + S * sx * half * 0.35 + F * sf * half * 0.35, w) for sx, sf in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
    mb.face((q[3], q[2], q[1], q[0]), col, part)
    mb.face(tuple(tq), col, part)
    for i in range(4):
        mb.face((q[i], q[(i + 1) % 4], tq[(i + 1) % 4], tq[i]), col, part)


# ---------------------------------------------------------------- head
# head-local coords: x lateral, f forward (toward snout), z up; origin HEAD_ORIGIN
HS = 1.22   # head scale (reference head is chunky relative to body)


HSX = 1.22     # extra head width (front view: broad, heavy-browed head)
HSZ = 1.10


def H(x, f, z):
    return Vector((HEAD_ORIGIN.x + x * HS * HSX, HEAD_ORIGIN.y - f * HS, HEAD_ORIGIN.z + z * HS * HSZ))


def Hd(dx, df, dz):
    return Vector((dx, -df, dz))


# upper-head loft stations: f, w(mid), wt(top), zt, zm, wl(lip), zb, wb(bottom)
HEAD_ST = [
    (-0.18, 0.28, 0.20, 0.24, 0.05, 0.27, -0.12, 0.25),
    (0.08, 0.37, 0.25, 0.31, 0.08, 0.35, -0.12, 0.33),
    (0.35, 0.34, 0.24, 0.29, 0.06, 0.33, -0.12, 0.31),
    (0.62, 0.28, 0.20, 0.22, 0.03, 0.27, -0.12, 0.25),
    (0.86, 0.24, 0.17, 0.18, 0.01, 0.23, -0.12, 0.21),
    (1.00, 0.21, 0.14, 0.14, 0.00, 0.20, -0.12, 0.18),
]
LIP = 0.055


def head_st(f):
    fs = [s[0] for s in HEAD_ST]
    f = min(max(f, fs[0]), fs[-1])
    for a, b in zip(HEAD_ST, HEAD_ST[1:]):
        if a[0] <= f <= b[0]:
            t = (f - a[0]) / (b[0] - a[0])
            return tuple(a[k] + (b[k] - a[k]) * t for k in range(8))
    return HEAD_ST[-1]


def skull_x(f, z):
    _, w, wt, zt, zm, wl, zb, wb = head_st(f)
    if z >= zm:
        t = (z - zm) / (zt - zm)
        return w + (wt - w) * t
    t = (zm - z) / (zm - (zb + LIP))
    return w + (wl - w) * t


def build_head(mb):
    WH = {'Head': 1.0}
    rings = []
    for (f, w, wt, zt, zm, wl, zb, wb) in HEAD_ST:
        pts = [(wt, zt), (w, zm), (wl, zb + LIP), (wb, zb), (-wb, zb), (-wl, zb + LIP), (-w, zm), (-wt, zt)]
        rings.append([mb.vert(H(x, f, z), WH) for x, z in pts])
    n = 8
    # edge colours: 0 chamfer,1 side,2 lip,3 mouth roof,4 lip,5 side,6 chamfer,7 top
    for ri, (r0, r1) in enumerate(zip(rings, rings[1:])):
        for j in range(n):
            if j in (2, 4):
                col = C['TEAL']
            elif j == 3:
                col = C['MOUTH']
            else:
                col = blue()
            mb.face((r0[j], r1[j], r1[(j + 1) % n], r0[(j + 1) % n]), col, 'head')
    mb.face(tuple(rings[0]), C['NAVY'], 'head')
    mb.face(tuple(reversed(rings[-1])), C['ROYAL'], 'head')

    # snout block + nostril bridge
    box(mb, H(0, 0.86, 0.17), (Hd(1, 0, 0), Hd(0, 1, 0), Hd(0, 0, 1)), (0.12, 0.13, 0.05), WH, C['ROYAL'], 'head')
    box(mb, H(0, 0.55, 0.26), (Hd(1, 0, 0), Hd(0, 1, 0), Hd(0, 0, 1)), (0.09, 0.16, 0.04), WH, C['NAVY'], 'head')

    for sgn in (1, -1):
        # brow ridge: outer-back high -> inner-front low (angry V)
        beam(mb, H(sgn * 0.33, -0.08, 0.30), H(sgn * 0.10, 0.52, 0.24), (0.075, 0.075),
             Hd(0, 0, 1), WH, C['ROYAL'], 'brow')
        # cheek plate under the eye
        beam(mb, H(sgn * 0.36, -0.10, 0.02), H(sgn * 0.30, 0.45, 0.00), (0.05, 0.06),
             Hd(sgn, 0, 0.3), WH, C['NAVY'], 'head')

        # eye (white angry wedge) + pupil, on a plane facing forward-out under the brow
        n = Vector((sgn * 0.72, 0.58, 0.38)).normalized()           # local (x, f, z)
        hz = Vector((0, 0, 1)).cross(n).normalized() * sgn          # points toward snout/inner
        vt = n.cross(hz).normalized() * sgn
        if vt.z < 0:
            vt = -vt
        cx, cf, cz = sgn * (skull_x(0.36, 0.17) + 0.05), 0.36, 0.17
        def eye_pt(a, b, off):
            q = Vector((cx, cf, cz)) + hz * a + vt * b + n * off
            return H(q.x, q.y, q.z)
        eye = [(-0.19, 0.11), (0.17, 0.005), (0.14, -0.07), (-0.07, -0.095), (-0.20, -0.03)]
        ids = [mb.vert(eye_pt(a, b, 0.0), WH) for a, b in eye]
        mb.face(tuple(ids), C['EYE'], 'eye', fix=Hd(n.x, n.y, n.z))
        pup = [(0.03, 0.06), (0.12, 0.022), (0.10, -0.06), (0.045, -0.075)]
        ids = [mb.vert(eye_pt(a, b, 0.008), WH) for a, b in pup]
        mb.face(tuple(ids), C['PUPIL'], 'eye', fix=Hd(n.x, n.y, n.z))
        # navy socket block behind the eye (bridges eye plane to skull)
        sc_ = Vector((cx, cf, cz)) - n * 0.055
        box(mb, H(sc_.x, sc_.y, sc_.z), (Hd(hz.x, hz.y, hz.z), Hd(vt.x, vt.y, vt.z), Hd(n.x, n.y, n.z)),
            (0.21 * HS, 0.11 * HS, 0.05 * HS), WH, C['NAVY'], 'head')

        # upper teeth
        for f, L, hs in [(0.14, 0.15, 0.055), (0.33, 0.16, 0.055), (0.52, 0.15, 0.05), (0.72, 0.13, 0.05)]:
            wb = head_st(f)[7]
            pyramid(mb, H(sgn * (wb - 0.04), f, -0.10), Hd(0, 0, -1), L, hs, WH, C['CREAM'])
        pyramid(mb, H(sgn * 0.09, 0.93, -0.10), Hd(0, 0.15, -1), 0.21, 0.06, WH, C['CREAM'])

    # ---- crest / frill spikes (head-mounted)
    X = (1, 0, 0)
    blade(mb, H(0, 0.02, 0.26), Hd(0, -0.50, 0.87), 0.62, Hd(0, 1, 0), WH, 'crystal', part='crest')
    blade(mb, H(0, -0.18, 0.20), Hd(0, -0.72, 0.70), 0.58, Hd(0, 1, 0), WH, 'aqua', part='crest')
    for sgn in (1, -1):
        blade(mb, H(sgn * 0.17, 0.05, 0.25), Hd(sgn * 0.32, -0.55, 0.77), 0.55, Hd(0, 1, 0), WH, 'teal', part='crest')
        blade(mb, H(sgn * 0.30, -0.10, 0.28), Hd(sgn * 0.35, -0.85, 0.40), 0.62, Hd(0, 0, 1), WH, 'royal', part='crest')
        blade(mb, H(sgn * 0.26, -0.12, 0.10), Hd(sgn * 0.62, -0.72, 0.30), 0.50, Hd(0, 0, 1), WH, 'royal', part='crest')
        blade(mb, H(sgn * 0.30, -0.08, 0.16), Hd(sgn * 0.78, -0.45, 0.45), 0.72, Hd(0, 0, 1), WH, 'crystal', part='crest')
        blade(mb, H(sgn * 0.32, -0.14, 0.00), Hd(sgn * 0.88, -0.45, -0.05), 0.60, Hd(0, 0, 1), WH, 'teal', part='crest')
        blade(mb, H(sgn * 0.28, -0.08, -0.14), Hd(sgn * 0.70, -0.50, -0.50), 0.45, Hd(0, 0, 1), WH, 'crystal', part='crest')


def jaw_xform(f, z):
    """closed-jaw local (f,z) -> open-jaw local (f,z)."""
    hf, hz = JAW_HINGE_LOCAL
    df, dz = f - hf, z - hz
    ca, sa = math.cos(JAW_OPEN), math.sin(JAW_OPEN)
    return hf + df * ca + dz * sa, hz - df * sa + dz * ca


def JH(x, f, z):
    f2, z2 = jaw_xform(f, z)
    return H(x, f2, z2)


JAW_ST = [  # f, wt(top), w(mid), zm, wb(bottom), zb
    (-0.12, 0.28, 0.31, -0.26, 0.25, -0.48),
    (0.30, 0.28, 0.30, -0.25, 0.24, -0.45),
    (0.62, 0.23, 0.25, -0.24, 0.20, -0.42),
    (0.95, 0.18, 0.19, -0.23, 0.16, -0.39),
]


def build_jaw(mb):
    WJ = {'Jaw': 1.0}
    zt = -0.12
    rings = []
    for f, wt, w, zm, wb, zb in JAW_ST:
        pts = [(wt, zt), (w, zm), (wb, zb), (-wb, zb), (-w, zm), (-wt, zt)]
        rings.append([mb.vert(JH(x, f, z), WJ) for x, z in pts])
    n = 6
    for r0, r1 in zip(rings, rings[1:]):
        for j in range(n):
            if j == 5:
                col = C['MOUTH']
            elif j in (0, 4):
                col = C['CREAM'] if rng.random() < 0.7 else C['ROYAL']
            else:
                col = C['CREAM']
            mb.face((r0[j], r0[(j + 1) % n], r1[(j + 1) % n], r1[j]), col, 'jaw')
    mb.face(tuple(reversed(rings[0])), C['ROYAL'], 'jaw')
    mb.face(tuple(rings[-1]), C['CREAM'], 'jaw')
    # tongue
    beam(mb, JH(0, 0.0, -0.13), JH(0, 0.70, -0.13), (0.10, 0.025), Hd(0, 0, 1), WJ, C['TEAL'], 'jaw')
    for sgn in (1, -1):
        for f, L in [(0.15, 0.11), (0.35, 0.12), (0.55, 0.11), (0.75, 0.10)]:
            wt = 0.28 if f < 0.3 else 0.26 if f < 0.6 else 0.22
            base = JH(sgn * (wt - 0.05), f, -0.13)
            up = JH(0, f, 1.0) - JH(0, f, 0.0)
            pyramid(mb, base, up, L * 1.25, 0.052, WJ, C['CREAM'])
        base = JH(sgn * 0.08, 0.90, -0.13)
        up = JH(0, 0.95, 1.0) - JH(0, 0.9, 0.0)
        pyramid(mb, base, up, 0.20, 0.06, WJ, C['CREAM'])
        # cheek webbing (mouth corner), two-bone weighted
        a = mb.vert(H(sgn * 0.30, 0.28, -0.12), {'Head': 1.0})
        b = mb.vert(H(sgn * 0.29, -0.10, -0.08), {'Head': 0.5, 'Jaw': 0.5})
        c = mb.vert(JH(sgn * 0.29, 0.28, -0.13), WJ)
        ids = (a, b, c) if sgn > 0 else (c, b, a)
        mb.face(ids, C['MOUTH'], 'web', fix=Vector((sgn, 0, 0)))


# ---------------------------------------------------------------- fins
DORSAL = [  # s, height
    (0.27, 0.90), (0.36, 0.86), (0.45, 0.76), (0.52, 0.68),
    (0.60, 0.60), (0.66, 0.52), (0.72, 0.45), (0.77, 0.36)]
SIDE = [  # s, size
    (0.25, 1.10), (0.35, 1.15), (0.53, 1.00), (0.62, 0.78)]
TAIL = [  # s, direction(out, back, up), length, scheme
    (0.70, (0.72, 0.62, 0.10), 0.42, 'crystal'),
    (0.78, (0.72, 0.62, 0.15), 0.38, 'teal'),
    (0.83, (0.70, 0.62, 0.25), 0.40, 'crystal'),
    (0.875, (0.30, 0.52, 0.82), 1.15, 'crystal'),
    (0.90, (0.66, 0.60, 0.42), 1.20, 'teal'),
    (0.925, (0.82, 0.58, -0.05), 1.05, 'crystal'),
]


def build_fins(mb):
    for s, h in DORSAL:
        c = spine_point(s)
        t, up = spine_frame(s)
        top = c + up * (HH(s) * 0.90)
        w = spine_weights(s)
        # blue brick root, big two-tone crystal leaf, splayed teal side leaves (chevron seen from above)
        sail(mb, top - up * 0.02, t, up, h * 1.15, h * 0.42, h * 0.30, 0.08, w, 'royal', bulge=0.3, part='dorsal')
        sail(mb, top + t * 0.04, t, up, h * 1.00, h, h * 0.50, 0.06, w, 'crystal', bulge=0.32, part='dorsal')
        for sgn in (1, -1):
            U = up * 0.80 + Vector((sgn * 0.45, 0, 0))
            sail(mb, top + t * 0.10 + Vector((sgn * 0.05, 0, 0)), t, U, h * 0.55, h * 0.55, h * 0.45, 0.04, w,
                 'teal', part='dorsal')
    # big neck crest spike (behind the head crest)
    s = 0.175
    c = spine_point(s); t, up = spine_frame(s)
    sail(mb, c + up * HH(s) * 0.88, t, up, 0.55, 0.78, 0.45, 0.06, spine_weights(s), 'crystal', part='dorsal')
    sail(mb, c + up * HH(s) * 0.85, t, up, 0.60, 0.36, 0.25, 0.08, spine_weights(s), 'royal', part='dorsal')

    for i, (s, k) in enumerate(SIDE):
        c = spine_point(s)
        t, up = spine_frame(s)
        for sgn in (1, -1):
            name = f'Fin{"L" if sgn > 0 else "R"}{i + 1}'
            w = {name: 1.0}
            X = Vector((sgn, 0, 0))
            base = c + X * (HW(s) * 0.85) - up * (HH(s) * 0.25)
            if i == 0:   # front flipper: big crescent "horn" arc (front view), out-up then down then curling in
                tip1 = sail(mb, base + up * 0.05, up + t * 0.2, X * 0.85 + up * 0.40, 0.40 * k, 0.55 * k, 0.0, 0.09, w,
                            'royal', bulge=0.2, part='side')
                p2 = base + (tip1 - base) * 0.85
                tip2 = sail(mb, p2, X + t * 0.3, X * 0.30 - up * 0.95, 0.34 * k, 0.62 * k, 0.05 * k, 0.09, w,
                            'royal', bulge=0.2, part='side')
                p3 = p2 + (tip2 - p2) * 0.80
                sail(mb, p3, X - t * 0.2, -X * 0.50 - up * 0.80 - t * 0.25, 0.26 * k, 0.40 * k, 0.0, 0.07, w,
                     'crystal', bulge=0.25, part='side')
                sail(mb, base + (tip1 - base) * 0.55 + up * 0.05, X + t * 0.2, up * 0.8 + X * 0.5, 0.24 * k,
                     0.26 * k, 0.10 * k, 0.05, w, 'teal', part='side')
                sail(mb, p2 + (tip2 - p2) * 0.4 + X * 0.05, up + t * 0.2, X * 0.9 + up * 0.3, 0.22 * k, 0.24 * k,
                     0.0, 0.05, w, 'crystal', part='side')
            else:
                U1 = X * 0.72 - up * 0.70
                tip1 = sail(mb, base, t, U1, 0.60 * k, 0.40 * k, 0.25 * k, 0.09, w, 'royal', bulge=0.3,
                            part='side')
                p2 = base + (tip1 - base) * 0.50
                sail(mb, p2 + t * 0.05, t, X * 0.58 - up * 0.82, 0.75 * k, 0.95 * k, 0.70 * k, 0.07, w,
                     'crystal', bulge=0.35, part='side')
                sail(mb, p2 + t * 0.12 - up * 0.03, t, X * 0.70 - up * 0.70, 0.45 * k, 0.60 * k, 0.55 * k, 0.05, w,
                     'teal', bulge=0.3, part='side')

    for s, (o, b, u), L, sch in TAIL:
        c = spine_point(s)
        t, up = spine_frame(s)
        w = spine_weights(s)
        for sgn in (1, -1):
            X = Vector((sgn, 0, 0))
            d = (X * o + t * b + up * u).normalized()
            # sail with base along the tail, height along the out/up component of d
            U = X * o + up * u
            lean = L * b
            base = c + X * HW(s) * 0.5 + up * (HH(s) * 0.3 if u > 0.5 else 0)
            sch2 = 'crystal' if sch == 'crystal' else 'teal'
            sail(mb, base, t, U, L * 0.80, L * U.length, lean, 0.05, w, sch2, bulge=0.35, part='tail')
            if L > 0.6:
                sail(mb, base - t * 0.05, t, U, L * 0.40, L * U.length * 0.45, lean * 0.4, 0.06, w, 'royal',
                     part='tail')
    # tail tip leaves
    s = 0.935
    c = spine_point(s); t, up = spine_frame(s)
    sail(mb, c, t, up * 0.3 + Vector((1, 0, 0)) * 0.0 + up, 0.30, 0.25, 0.85, 0.05, spine_weights(s), 'crystal',
         part='tail')
    sail(mb, c, t, -up, 0.30, 0.15, 0.70, 0.05, spine_weights(s), 'teal', part='tail')


def build_bricks(mb):
    """Brick mosaic on the flanks: staggered rows of slightly proud bricks like the reference build."""
    rows = [(0.62, 0.0, None), (0.10, 0.5, None), (-0.58, 0.0, 'CREAM')]
    for v, stagger, colname in rows:
        s = 0.135 + stagger * 0.034
        while s < 0.87:
            c = spine_point(s)
            t, up = spine_frame(s)
            hh, hw = HH(s), HW(s)
            w = spine_weights(s)
            step = 0.034 if s < 0.6 else 0.03
            L = LENGTH * step * 0.5 * (0.80 + 0.1 * rng.random())
            Hh = hh * (0.20 + 0.05 * rng.random())
            off = 0.012 + 0.02 * rng.random()
            col = C[colname] if colname else (C['NAVY'] if rng.random() < 0.38 else C['ROYAL'])
            for u in (1.0, -1.0):
                uu = u * (1.0 if abs(v) < 0.5 else 0.97)
                p = c + Vector((uu * hw, 0, 0)) + up * (v * hh)
                n = Vector((u, 0, 0))
                side = n.cross(t).normalized()
                box(mb, p + n * off, (t, side, n), (L, Hh, 0.03), w, col, 'brick')
            s += step


def build_all():
    mb = MeshBuilder()
    build_body(mb)
    build_head(mb)
    build_jaw(mb)
    build_fins(mb)
    build_bricks(mb)
    return mb
