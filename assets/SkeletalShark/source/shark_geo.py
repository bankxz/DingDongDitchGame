"""Skeletal Shark - voxel part definitions, greedy mesher and stud-texture atlas.

Pure numpy/PIL (no bpy) so it can be iterated on quickly.

Shark coordinate system ("cube" units measured from the LEFT SIDE reference view,
1 cube = one voxel block of the reference, ~14 px on the 1448x1086 sheet):
    i : length axis, 0 = snout tip, grows toward the tail (47.6 = upper tail tip)
    w : lateral axis, 0 = centre line, + = shark's left side
    z : height axis, 0 = bottom of the side-view grid
"""
import math
import numpy as np
from PIL import Image

# ----------------------------------------------------------------------------- palette
# sampled directly from the reference sheet's COLOR PALETTE swatches
BONE = (245, 228, 204)
IVORY = (212, 186, 161)
DARK_BLUE = (30, 52, 103)
BLUE_ACCENT = (80, 129, 193)
CYAN = (80, 251, 254)

# material ids
EMPTY, M_BONE, M_BLUE, M_CYAN, M_TOOTH, M_SOCKET, M_EYE = 0, 1, 2, 3, 4, 5, 6


# ----------------------------------------------------------------------------- helpers
def interp(x, xs, ys):
    return np.interp(x, xs, ys)


def in_poly(px, py, poly):
    """Vectorised even-odd point in polygon."""
    px = np.asarray(px, float)
    py = np.asarray(py, float)
    inside = np.zeros(np.broadcast(px, py).shape, bool)
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        cond = (y1 > py) != (y2 > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            xint = (x2 - x1) * (py - y1) / (y2 - y1 + 1e-12) + x1
        inside ^= cond & (px < xint)
    return inside


def dist_polyline(px, py, pts):
    d = np.full(np.broadcast(px, py).shape, 1e9)
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        vx, vy = x2 - x1, y2 - y1
        t = np.clip(((px - x1) * vx + (py - y1) * vy) / (vx * vx + vy * vy), 0, 1)
        d = np.minimum(d, np.hypot(px - (x1 + t * vx), py - (y1 + t * vy)))
    return d


class Part:
    """A voxel volume in its own local lattice (a, b, c axes) with a 4x4 affine map
    local-cube-units -> shark-cube-units."""

    def __init__(self, name, origin, cell, shape, bone, chunk=None, xf=None):
        self.name = name
        self.origin = np.array(origin, float)  # local coord of voxel (0,0,0) min corner
        self.cell = np.array(cell, float)
        self.M = np.zeros(shape, np.uint8)
        self.bone = bone  # bone name or 'SPINE' (blend by i)
        self.chunk = chunk  # cells along axis 0 per chunk (for bending)
        self.xf = np.eye(4) if xf is None else xf

    def centers(self):
        n = self.M.shape
        a = self.origin[0] + (np.arange(n[0]) + 0.5) * self.cell[0]
        b = self.origin[1] + (np.arange(n[1]) + 0.5) * self.cell[1]
        c = self.origin[2] + (np.arange(n[2]) + 0.5) * self.cell[2]
        return np.meshgrid(a, b, c, indexing="ij")


def make_part(name, lo, hi, cell, fn, bone, chunk=None, xf=None):
    cell = np.array(cell if np.ndim(cell) else [cell] * 3, float)
    lo = np.array(lo, float)
    hi = np.array(hi, float)
    shape = tuple(int(math.ceil((hi[k] - lo[k]) / cell[k])) for k in range(3))
    p = Part(name, lo, cell, shape, bone, chunk, xf)
    A, B, C = p.centers()
    p.M[...] = fn(A, B, C).astype(np.uint8)
    return p


# ----------------------------------------------------------------------------- profiles
# body core (blue) - measured from side view, widths from top/back view
# rib-cage ENVELOPE (outer surface of the ribs) - side view heights, back/front view widths
ENV_TOP = ([12, 16, 19.3, 21.8, 24, 26, 28, 30, 32, 34, 36, 38, 40], [9.6, 9.7, 9.5, 9.2, 8.8, 8.3, 7.8, 7.4, 7.1, 6.8, 6.4, 6.0, 5.7])
ENV_BOT = ([12, 14, 16, 19.3, 21.8, 24, 26, 28, 30, 34, 36, 38, 40], [1.0, 0.7, 0.6, 0.6, 0.8, 1.2, 1.7, 2.2, 2.6, 3.2, 3.6, 3.9, 4.1])
ENV_HW = ([12, 14, 16.4, 19.3, 21.8, 24, 26, 28, 30, 32, 34, 36, 38, 40], [4.7, 5.0, 5.1, 4.6, 4.1, 3.6, 3.1, 2.7, 2.4, 2.1, 1.8, 1.4, 1.0, 0.9])
CORE_INSET = 0.5


def env_top(i):
    return interp(i, *ENV_TOP)


def env_bot(i):
    return interp(i, *ENV_BOT)


def env_hw(i):
    return interp(i, *ENV_HW)


def core_top(i):
    return env_top(i) - CORE_INSET


def core_bot(i):
    return env_bot(i) + CORE_INSET


def core_hw(i):
    return np.maximum(env_hw(i) - CORE_INSET, 0.6)


def superellipse(dw, dz, hw, hh, e=2.6):
    return (np.abs(dw) / np.maximum(hw, 1e-3)) ** e + (np.abs(dz) / np.maximum(hh, 1e-3)) ** e <= 1.0


# skull ------------------------------------------------------------------------
SKULL_POLY = [(0, 7.2), (0, 9.5), (0.5, 9.9), (4.6, 9.9), (5.0, 10.4), (8.6, 10.4), (9.0, 10.1),
              (12.4, 10.1), (12.4, 1.8), (8.8, 1.8), (8.8, 3.8), (8.0, 4.2), (8.0, 5.9), (4.2, 5.9),
              (4.2, 6.6), (3.0, 6.6), (3.0, 7.2)]
SKULL_TOP = ([0, 0.5, 4.6, 5.0, 8.6, 9.0, 12.4], [9.5, 9.9, 9.9, 10.4, 10.4, 10.1, 10.1])
SKULL_HW = ([0, 1, 2, 3, 4, 4.6, 5.5, 6.5, 12.4], [2.3, 2.7, 3.0, 3.3, 3.6, 4.1, 4.5, 4.7, 4.7])
EYE_SOCKET = [(4.0, 7.5), (4.6, 6.9), (7.6, 6.9), (8.2, 7.5), (8.2, 8.9), (7.5, 9.5), (4.7, 9.5), (4.0, 8.8)]


def skull_hw(I, Z, top):
    hw = interp(I, *SKULL_HW)
    # FRONT view: shield-shaped head, narrow crown, widest at the cheeks
    f = np.where(Z > 6.0, 1 - 0.45 * np.clip((Z - 6.0) / np.maximum(top - 6.0, 0.5), 0, 1) ** 1.4, 1.0)
    f = np.where(Z < 4.0, 1 - 0.15 * np.clip((4.0 - Z) / 2.2, 0, 1), f)
    return hw * f


def upper_jaw_bottom(i):
    return np.where(i < 3.0, 7.2, np.where(i < 4.2, 6.6, 5.9))


def skull_fn(I, W, Z):
    top = interp(I, *SKULL_TOP)
    hw = skull_hw(I, Z, top)
    inside = in_poly(I, Z, SKULL_POLY) & (np.abs(W) < hw)
    m = np.where(inside, M_BONE, EMPTY)
    aw = np.abs(W)
    # eye sockets: 1 cube deep, dark floor, glowing eye cube protruding from floor
    sock = in_poly(I, Z, EYE_SOCKET)
    m = np.where(sock & (aw > hw - 1.5), EMPTY, m)
    m = np.where(inside & sock & (aw > hw - 2.0) & (aw <= hw - 1.5), M_SOCKET, m)
    eye = (I > 5.2) & (I < 6.8) & (Z > 7.5) & (Z < 8.9) & (aw > hw - 2.0) & (aw <= hw - 0.5)
    m = np.where(inside & eye, M_EYE, m)
    # nostril pits
    nos = (I > 1.8) & (I < 2.7) & (Z > 8.3) & (Z < 9.1)
    m = np.where(inside & nos & (aw > hw - 0.5), EMPTY, m)
    m = np.where(inside & nos & (aw > hw - 1.0) & (aw <= hw - 0.5), M_SOCKET, m)
    # cheek slot behind the eye
    slot = (I > 10.4) & (I < 11.3) & (Z > 5.4) & (Z < 7.0)
    m = np.where(slot & (aw > hw - 0.5), EMPTY, m)
    # mouth: vaulted palate (side rims hang lower than the roof, FRONT view), throat back wall blue
    hw0 = interp(I, *SKULL_HW)
    m = np.where((I > 0.9) & (I < 8.0) & (Z < 7.2) & (aw < hw0 - 1.0), EMPTY, m)
    throat = inside & (I > 7.9) & (I < 9.4) & (Z < 6.4) & (aw < hw - 0.9)
    m = np.where(throat, M_BLUE, m)
    return m


def skull_bumps(p, seed=11):
    """Add 1x1 cube, half-cube-high blocks on the skull crown and cheeks (deterministic)."""
    A, B, C = p.centers()
    M = p.M
    rng = np.random.default_rng(seed)
    na, nb, nc = M.shape
    added = 0
    for a in range(0, na - 1, 2):
        for b in range(0, nb - 1, 2):
            i = A[a, 0, 0]
            if i < 0.6 or i > 12.0:
                continue
            cols = [np.nonzero(M[a + x, b + y, :])[0] for x in (0, 1) for y in (0, 1)]
            if any(len(c) == 0 for c in cols):
                continue
            top = min(c.max() for c in cols)
            if top + 1 >= nc or rng.random() > 0.22:
                continue
            if any(M[a + x, b + y, top] != M_BONE for x in (0, 1) for y in (0, 1)):
                continue
            if any(M[a + x, b + y, top + 1] for x in (0, 1) for y in (0, 1)):
                continue
            M[a:a + 2, b:b + 2, top + 1] = M_BONE
            added += 1
    # side bumps on the cheek / behind the eye
    for a in range(0, na - 1, 2):
        i = A[a, 0, 0]
        if i < 8.4 or i > 12.0:
            continue
        for c in range(0, nc - 1, 2):
            z = C[0, 0, c]
            if z < 2.5 or z > 9.0 or (5.2 < z < 7.2 and 10.2 < i < 11.5):
                continue
            for side in (0, 1):
                rows = [np.nonzero(M[a + x, :, c + y])[0] for x in (0, 1) for y in (0, 1)]
                if any(len(r) == 0 for r in rows) or rng.random() > 0.22:
                    continue
                edge = max(r.max() for r in rows) if side else min(r.min() for r in rows)
                nbv = edge + (1 if side else -1)
                if nbv < 0 or nbv >= nb:
                    continue
                if any(M[a + x, edge, c + y] != M_BONE for x in (0, 1) for y in (0, 1)):
                    continue
                M[a:a + 2, nbv, c:c + 2] = M_BONE
                added += 1
    return added


def skull_postprocess(p):
    """palate: lowest bone cell of every column in the jaw region becomes blue."""
    A, B, C = p.centers()
    M = p.M
    for a in range(M.shape[0]):
        i = A[a, 0, 0]
        if i < 0.8 or i > 8.0:
            continue
        hw = np.interp(i, *SKULL_HW)
        for b in range(M.shape[1]):
            if abs(B[0, b, 0]) >= hw - 0.9:
                continue
            col = np.nonzero(M[a, b, :])[0]
            if len(col):
                M[a, b, col[0]] = M_BLUE


# lower jaw --------------------------------------------------------------------
JAW_POLY = [(2.6, 1.2), (2.6, 2.9), (4.0, 3.0), (6.0, 3.4), (8.0, 3.9), (9.6, 4.3), (9.6, 1.0), (3.4, 1.0)]
JAW_TOP = ([2.6, 4.0, 6.0, 8.0, 9.6], [2.9, 3.0, 3.4, 3.9, 4.3])
JAW_HW = ([2.6, 4, 6, 9.6], [2.9, 3.6, 4.1, 4.4])


def jaw_fn(I, W, Z):
    hw = interp(I, *JAW_HW)
    top = interp(I, *JAW_TOP)
    aw = np.abs(W)
    inside = in_poly(I, Z, JAW_POLY) & (aw < hw)
    m = np.where(inside, M_BONE, EMPTY)
    # U-shaped trough: carve the top layer, floor (tongue) is blue
    trough = (I > 3.1) & (aw < hw - 1.0)
    m = np.where(inside & trough & (Z > 2.0), EMPTY, m)
    m = np.where(inside & trough & (Z > 1.5) & (Z <= 2.0), M_BLUE, m)
    # hinge blocks hanging under the back of the skull
    hinge = (I > 9.3) & (I < 10.9) & (Z > 0.5) & (Z < 1.9) & (aw < 2.6)
    m = np.where(hinge, M_BONE, m)
    return m


# body core ---------------------------------------------------------------------
def core_fn(I, W, Z):
    top, bot, hw = core_top(I), core_bot(I), core_hw(I)
    zc, hh = (top + bot) / 2, (top - bot) / 2
    return np.where((I > 12.0) & (I < 40.0) & superellipse(W, Z - zc, hw, hh, 2.05), M_BLUE, EMPTY)


# ribs ---------------------------------------------------------------------------
# (centre i, z bottom, z top, thickness, lean a, bow b) measured from rib zoom
# (centre i, bottom z, top z, outer half-width, thickness, lean a, bow b)
# heights from the SIDE view, the nested/shrinking arches from the BACK view
RIBS = [(16.4, 0.6, 9.8, 5.1, 1.3, -0.12, 0.0),
        (19.3, 0.5, 9.5, 4.7, 1.35, -0.10, 0.1),
        (21.8, 0.7, 9.1, 4.3, 1.3, -0.05, 0.5),
        (24.0, 1.0, 8.6, 3.9, 1.15, -0.10, 0.4),
        (25.9, 1.4, 7.8, 3.5, 1.0, -0.05, 0.3)]


def ribs_fn(I, W, Z):
    """Rib arches: shells of a per-rib ellipse; the core fills in behind them."""
    m = np.zeros(I.shape, np.uint8)
    for ic, bot, top, hwo, th, a, b in RIBS:
        zc, hh = (top + bot) / 2, (top - bot) / 2
        u = np.clip((Z - zc) / hh, -1, 1)
        off = a * (Z - zc) + b * (1 - u * u)
        slab = np.abs(I - (ic + off)) < th / 2
        outer = superellipse(W, Z - zc, hwo, hh, 2.0)
        inner = superellipse(W, Z - zc, hwo - 0.7, hh - 0.7, 2.0)
        m[slab & outer & ~inner] = M_BONE
    return m


# spine / vertebrae -------------------------------------------------------------
VERT_TOP = [13.5, 17.8, 20.6, 23.0, 25.0, 27.4]
TAIL_VERTS = [(30.6, 2.8, 6.6, 1.0, 1.9), (34.45, 3.4, 6.0, 1.1, 1.7), (37.9, 3.8, 6.2, 1.0, 1.4)]


def spine_fn(I, W, Z):
    aw = np.abs(W)
    ct = core_top(I)
    m = np.zeros(I.shape, np.uint8)
    bar = (I > 12.5) & (I < 28.5) & (aw < 0.5) & (Z > ct - 0.4) & (Z < ct + 0.5)
    m[bar] = M_BONE
    for v in VERT_TOP:
        pad = (np.abs(I - v) < 0.45) & (aw < 1.5) & (Z > core_top(v) - 0.4) & (Z < core_top(v) + 0.45)
        m[pad] = M_BONE
    tail = (I > 27.0) & (I < 43.5) & (aw < 0.7) & (Z > 4.2) & (Z < 5.5)
    m[tail] = M_BONE
    for ic, zb, zt, th, lat in TAIL_VERTS:
        vert = (np.abs(I - ic) < th / 2) & (aw < 0.7) & (Z > zb) & (Z < zt)
        latb = (np.abs(I - ic) < th / 2) & (aw < lat) & (Z > 4.2) & (Z < 5.5)
        m[vert | latb] = M_BONE
    return m


# flat fins in the side (i,z) plane ---------------------------------------------
DORSAL_POLY = [(15.2, 9.0), (15.2, 9.2), (16.3, 9.9), (17.5, 10.6), (18.3, 11.8), (19.2, 12.7), (20.4, 13.4),
               (21.5, 14.0), (22.4, 14.6), (22.6, 14.1), (22.8, 13.2), (22.9, 11.5), (23.4, 10.6),
               (24.2, 9.6), (24.3, 9.0)]
DORSAL_LEAD = [(15.2, 9.2), (16.3, 9.9), (17.5, 10.6), (18.3, 11.8), (19.2, 12.7), (20.4, 13.4), (21.5, 14.0),
               (22.4, 14.6)]

SPIKES = {
    "S0": [(11.0, 9.8), (12.0, 10.4), (13.0, 11.0), (14.1, 11.7), (13.9, 11.0), (13.5, 10.2), (13.2, 9.6)],
    "S1": [(24.3, 9.0), (25.2, 10.0), (26.2, 10.6), (27.3, 11.1), (27.0, 10.4), (26.4, 9.6), (26.2, 8.6)],
    "S2": [(26.8, 7.8), (27.6, 8.7), (28.4, 9.3), (29.4, 9.9), (29.2, 9.0), (28.8, 8.0), (28.6, 7.2)],
    "S3": [(30.0, 6.6), (30.7, 7.4), (31.4, 8.0), (32.4, 8.6), (32.1, 7.8), (31.8, 6.9), (31.6, 6.2)],
    "S4": [(33.8, 5.8), (34.4, 6.6), (35.0, 7.2), (35.7, 7.8), (35.5, 7.0), (35.2, 6.2), (35.0, 5.6)],
    "V1": [(30.0, 3.6), (31.6, 3.6), (31.8, 2.5), (32.2, 1.4), (32.3, 0.6), (31.4, 1.2), (30.6, 2.2)],
}
BLUE_FINS = {
    "A1": [(27.0, 2.9), (29.2, 3.2), (28.9, 1.8), (28.2, 1.3), (27.4, 1.9)],
    "A2": [(32.8, 4.1), (35.3, 4.1), (35.4, 3.0), (34.7, 2.7), (33.4, 3.2)],
}

TAIL_POLY = [(36.5, 4.2), (37.0, 6.2), (38.0, 7.0), (39.0, 8.4), (40.0, 9.5), (41.0, 10.3), (42.5, 11.0),
             (44.0, 11.7), (45.5, 12.4), (47.0, 13.3), (47.6, 12.9), (46.0, 11.6), (44.9, 10.4), (44.0, 10.2),
             (43.9, 8.2), (43.2, 7.2), (44.3, 7.1), (44.3, 6.2), (42.0, 6.2), (41.8, 5.6), (41.5, 4.2),
             (42.5, 2.5), (43.5, 1.0), (44.3, -0.8), (43.5, -0.9), (42.0, 0.1), (41.0, 0.9), (40.0, 1.8),
             (39.0, 2.5), (38.0, 3.2), (37.3, 4.0)]
TAIL_BLUE_U = [(38.8, 5.6), (40.0, 8.3), (41.5, 9.7), (43.9, 10.8), (43.9, 8.2), (43.0, 7.0), (42.0, 5.6)]
TAIL_BLUE_L = [(39.6, 4.2), (41.5, 4.2), (42.5, 2.5), (43.4, 0.9), (43.8, 0.0), (42.4, 1.1), (41.0, 2.2),
               (40.2, 3.2)]


def dorsal_fn(I, W, Z):
    poly = in_poly(I, Z, DORSAL_POLY)
    bone = (dist_polyline(I, Z, DORSAL_LEAD) < 1.05) | (Z > 13.9)
    # blue web is thick at the root (seen as blue flanks in the FRONT/BACK views)
    t = np.where(Z > 9.6, 0.5 + np.clip(11.8 - Z, 0, 2.2) * 0.6, 0.5)  # flanks sit above the rib arches
    m = np.where(poly & bone & (np.abs(W) < 0.5), M_BONE, EMPTY)
    m = np.where(poly & ~bone & (np.abs(W) < t), M_BLUE, m)
    return m


def spikes_fn(I, W, Z):
    m = np.zeros(I.shape, np.uint8)
    for poly in SPIKES.values():
        m[in_poly(I, Z, poly) & (np.abs(W) < 0.5)] = M_BONE
    return m


def bluefins_fn(I, W, Z):
    m = np.zeros(I.shape, np.uint8)
    for poly in BLUE_FINS.values():
        m[in_poly(I, Z, poly) & (np.abs(W) < 0.5)] = M_BLUE
    return m


def tail_fn(I, W, Z):
    shape = in_poly(I, Z, TAIL_POLY) & (np.abs(W) < 0.5)
    blue = (in_poly(I, Z, TAIL_BLUE_U) | in_poly(I, Z, TAIL_BLUE_L))
    bar = (I > 39.6) & (I < 44.3) & (Z > 6.2) & (Z < 7.0)
    spinebar = (I < 42.0) & (Z > 4.2) & (Z < 5.5)
    blue &= ~bar & ~spinebar
    return np.where(shape, np.where(blue, M_BLUE, M_BONE), EMPTY)


# pectoral fins -----------------------------------------------------------------
PEC_POLY = [(0, -1.9), (0, 1.8), (2.7, 1.7), (5.4, 1.3), (7.6, 0.9), (9.5, 0.45), (10.6, 0.0), (9.5, -0.35),
            (7.6, -0.8), (5.4, -1.3), (2.7, -1.8)]
PEC_ROOT = np.array([13.4, 4.4, 4.2])
PEC_TIP = np.array([21.0, 10.2, 0.0])


def pec_fn(U, V, N):
    shape = in_poly(U, V, PEC_POLY) & (np.abs(N) < 0.45)
    lower = interp(U, [0, 2.7, 5.4, 7.6, 9.5, 10.6], [-1.9, -1.8, -1.3, -0.8, -0.35, 0.0])
    upper = interp(U, [0, 2.7, 5.4, 7.6, 9.5, 10.6], [1.8, 1.7, 1.3, 0.9, 0.45, 0.0])
    blue = (V < upper - 0.85) & (V > lower + 0.75) & (U > 1.0) & (U < 8.2)
    return np.where(shape, np.where(blue, M_BLUE, M_BONE), EMPTY)


def pec_xf(side):
    root = PEC_ROOT * np.array([1, side, 1])
    tip = PEC_TIP * np.array([1, side, 1])
    a = tip - root
    a /= np.linalg.norm(a)
    # blade faces up/out/forward: reads broad in the SIDE, 3/4 and TOP views, as a strip in FRONT
    n0 = np.array([-0.25, 0.55 * side, 0.8])
    n = n0 - n0.dot(a) * a
    n /= np.linalg.norm(n)
    v = np.cross(n, a)
    if v[0] > 0:  # keep +v (leading edge) toward the head
        v, n = -v, -n
    xf = np.eye(4)
    xf[:3, 0], xf[:3, 1], xf[:3, 2], xf[:3, 3] = a, v, n, root
    return xf


# glow cores between the ribs --------------------------------------------------
GLOW = [(14.8, 0.35), (17.95, 0.4), (20.6, 0.35), (23.0, 0.3), (25.0, 0.28)]


def build_parts():
    parts = []
    p = make_part("Skull", (-0.5, -5.5, 1.5), (13.0, 5.5, 11.0), 0.5, skull_fn, "Head")
    skull_postprocess(p)
    skull_bumps(p)
    parts.append(p)
    parts.append(make_part("Jaw", (2.5, -5.0, 0.5), (11.0, 5.0, 4.5), 0.5, jaw_fn, "Jaw"))
    parts.append(make_part("Core", (12.0, -5.5, 0.5), (40.0, 5.5, 10.5), (1.0, 0.5, 0.5), core_fn, "SPINE", chunk=3))
    parts.append(make_part("Ribs", (14.5, -5.5, 0.0), (27.5, 5.5, 10.5), 0.5, ribs_fn, "SPINE"))
    parts.append(make_part("Spine", (12.5, -2.0, 2.5), (44.0, 2.0, 9.5), 0.5, spine_fn, "SPINE", chunk=4))
    parts.append(make_part("Dorsal", (15.0, -2.0, 8.5), (24.5, 2.0, 15.0), 0.5, dorsal_fn, "Dorsal"))
    parts.append(make_part("Spikes", (10.5, -0.5, 0.5), (36.0, 0.5, 12.0), 0.5, spikes_fn, "SPINE"))
    parts.append(make_part("VentralFins", (26.5, -0.5, 1.0), (36.0, 0.5, 4.5), 0.5, bluefins_fn, "SPINE"))
    parts.append(make_part("TailFin", (36.0, -0.5, -1.0), (48.0, 0.5, 13.5), 0.5, tail_fn, "TailFin"))
    for side, bone in ((1, "PectoralL"), (-1, "PectoralR")):
        parts.append(make_part("Pectoral" + bone[-1], (0, -2.0, -0.5), (11.0, 2.0, 0.5), 0.5, pec_fn, bone,
                               xf=pec_xf(side)))
    return parts


# ----------------------------------------------------------------------------- greedy mesher
class Quad:
    __slots__ = ("corners", "normal", "part", "mats", "plane", "uvs", "bone", "kind")


class Occupancy:
    """0.5-cube owner grid in shark space. Used to (1) cull faces hidden inside other parts and
    (2) drop coplanar duplicate faces where parts overlap (these self-shadow to black in renders)."""
    O = np.array([-2.0, -8.0, -3.0])
    R = 0.5

    def __init__(self, parts):
        self.G = np.full((110, 32, 40), -1, np.int16)
        self.prio = {}
        for k, p in reversed(list(enumerate(parts))):  # first part in list wins ownership
            self.prio[p.name] = k
            A, B, C = p.centers()
            filled = p.M > 0
            n = np.maximum(1, np.round(p.cell / self.R).astype(int))
            for da in range(n[0]):
                for db in range(n[1]):
                    for dc in range(n[2]):
                        off = (np.array([da, db, dc]) + 0.5) * self.R - p.cell / 2
                        pts = np.stack([A[filled] + off[0], B[filled] + off[1], C[filled] + off[2]], -1)
                        idx = np.floor((pts - self.O) / self.R).astype(int)
                        self.G[idx[:, 0], idx[:, 1], idx[:, 2]] = k

    def owner(self, pts):
        idx = np.floor((pts - self.O) / self.R).astype(int)
        ok = np.all((idx >= 0) & (idx < np.array(self.G.shape)), -1)
        out = np.full(pts.shape[:-1], -1, np.int16)
        ii = idx[ok]
        out[ok] = self.G[ii[:, 0], ii[:, 1], ii[:, 2]]
        return out


def greedy_mesh(part, occ=None):
    """Returns list of Quad. corners are in part-LOCAL cube units (CCW seen from outside)."""
    M = part.M
    quads = []
    if occ is not None:
        A, B, C = part.centers()
        CEN = np.stack([A, B, C], -1)
    n = M.shape
    pad = np.zeros((n[0] + 2, n[1] + 2, n[2] + 2), np.uint8)
    pad[1:-1, 1:-1, 1:-1] = M
    for d in range(3):
        u, v = (d + 1) % 3, (d + 2) % 3
        for sgn in (-1, 1):
            for s in range(n[d]):
                idx = [slice(1, -1)] * 3
                idx[d] = s + 1
                cur = pad[tuple(idx)]
                idx[d] = s + 1 + sgn
                nb = pad[tuple(idx)]
                mask = np.where((cur > 0) & (nb == 0), cur, 0)
                if occ is not None and mask.any():
                    idx2 = [slice(None)] * 3
                    idx2[d] = s
                    cen = CEN[tuple(idx2)]
                    hid = np.ones(cen.shape[:-1], bool)
                    dup = np.ones(cen.shape[:-1], bool)
                    me = occ.prio.get(part.name, 10 ** 4)
                    for su in (-0.25, 0.25):
                        for sv in (-0.25, 0.25):
                            pt = cen.copy()
                            pt[..., u] += su * part.cell[u]
                            pt[..., v] += sv * part.cell[v]
                            pin = pt.copy()
                            pin[..., d] += sgn * (part.cell[d] / 2 - 0.25)
                            pt[..., d] += sgn * (part.cell[d] / 2 + 0.25)
                            hid &= occ.owner(pt) >= 0
                            ow = occ.owner(pin)
                            dup &= (ow >= 0) & (ow < me)
                    hid |= dup
                    mask = np.where(hid, 0, mask)
                # reorder so rows = u axis, cols = v axis
                axes_left = [k for k in range(3) if k != d]
                mask2 = mask if axes_left == [u, v] else mask.T
                quads += _greedy_2d(part, mask2, d, s, sgn, u, v)
    return quads


def _greedy_2d(part, mask, d, s, sgn, u, v):
    out = []
    H, W = mask.shape
    used = np.zeros_like(mask, bool)
    chunk_u = part.chunk if (part.chunk and u == 0) else None
    chunk_v = part.chunk if (part.chunk and v == 0) else None
    for a in range(H):
        for b in range(W):
            m = mask[a, b]
            if m == 0 or used[a, b]:
                continue
            # extend along v (cols)
            b2 = b + 1
            while b2 < W and mask[a, b2] == m and not used[a, b2] and not (chunk_v and b2 % chunk_v == 0):
                b2 += 1
            a2 = a + 1
            while a2 < H and not (chunk_u and a2 % chunk_u == 0):
                row = mask[a2, b:b2]
                if np.all(row == m) and not used[a2, b:b2].any():
                    a2 += 1
                else:
                    break
            used[a:a2, b:b2] = True
            q = Quad()
            o, c = part.origin, part.cell
            plane = o[d] + (s + (1 if sgn > 0 else 0)) * c[d]
            u0, u1 = o[u] + a * c[u], o[u] + a2 * c[u]
            v0, v1 = o[v] + b * c[v], o[v] + b2 * c[v]

            def P(uu, vv):
                p = [0.0, 0.0, 0.0]
                p[d], p[u], p[v] = plane, uu, vv
                return p

            if sgn > 0:
                q.corners = [P(u0, v0), P(u1, v0), P(u1, v1), P(u0, v1)]
            else:
                q.corners = [P(u0, v0), P(u0, v1), P(u1, v1), P(u1, v0)]
            nrm = [0, 0, 0]
            nrm[d] = sgn
            q.normal = nrm
            q.part = part
            q.mats = mask[a:a2, b:b2].copy()  # (u cells, v cells)
            q.plane = (d, u, v, u0, u1, v0, v1, c[u], c[v])
            q.bone = part.bone
            q.kind = "voxel"
            out.append(q)
    return out


# ----------------------------------------------------------------------------- teeth
def tooth_geometry():
    """Stepped voxel teeth: a small block + pyramid tip. Returns list of
    (verts[list of xyz shark coords], faces[list of index tuples], bone)."""
    teeth = []

    def tooth(i, w, zb, L, base, down, bone, simple=False):
        s = -1 if down else 1
        h1 = L * 0.4
        b = base / 2
        b2 = base * 0.34
        z1 = zb + s * h1
        z2 = zb + s * L
        vs = [(i - b, w - b, zb), (i + b, w - b, zb), (i + b, w + b, zb), (i - b, w + b, zb),
              (i - b, w - b, z1), (i + b, w - b, z1), (i + b, w + b, z1), (i - b, w + b, z1),
              (i - b2, w - b2, z1), (i + b2, w - b2, z1), (i + b2, w + b2, z1), (i - b2, w + b2, z1),
              (i, w, z2)]
        fs = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7),  # block sides
              (8, 9, 12), (9, 10, 12), (10, 11, 12), (11, 8, 12)]
        if simple:  # rear teeth: plain 4-sided pyramid (tri budget)
            vs = vs[:4] + [(i, w, z2)]
            fs = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
        if not down:
            fs = [tuple(reversed(f)) for f in fs]
        teeth.append((vs, fs, bone))

    up_i = [1.1, 2.1, 3.3, 4.4, 5.5, 6.6, 7.5]
    up_L = [1.7, 1.8, 1.7, 1.6, 1.5, 1.3, 1.1]
    for side in (1, -1):
        for k, (i, L) in enumerate(zip(up_i, up_L)):
            hw = float(interp(i, *SKULL_HW))
            tooth(i, side * (hw - 0.5), float(upper_jaw_bottom(np.array(i))) + 0.05, L, 0.75, True, "Head", k >= 3)
    for w in (-1.3, -0.45, 0.45, 1.3):
        tooth(0.5, w, 7.25, 1.6, 0.7, True, "Head")
    lo_i = [3.6, 4.4, 5.2, 6.0, 6.8, 7.6]
    lo_L = [1.25, 1.35, 1.35, 1.25, 1.1, 1.0]
    for side in (1, -1):
        for k, (i, L) in enumerate(zip(lo_i, lo_L)):
            hw = float(interp(i, *JAW_HW))
            tooth(i, side * (hw - 0.5), float(interp(i, *JAW_TOP)) - 0.05, L, 0.68, False, "Jaw", k >= 3)
    for w in (-1.3, -0.45, 0.45, 1.3):
        tooth(2.95, w, float(interp(2.9, *JAW_TOP)) - 0.05, 1.2, 0.64, False, "Jaw")
    return teeth


def glow_boxes():
    """Emissive cyan cores sitting in the gaps between ribs."""
    out = []
    for ic, half in GLOW:
        hw = float(core_hw(ic)) - 0.05
        zb, zt = 4.2, 5.9
        out.append(((ic - half, -hw, zb), (ic + half, hw, zt)))
    return out


# ----------------------------------------------------------------------------- stud texture
def _hash2(a, b, seed):
    h = (np.int64(a) * 73856093) ^ (np.int64(b) * 19349663) ^ np.int64(seed * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def stud_pixels(a, b, mat, seed):
    """a,b: float arrays in cube units on a face. mat: material per pixel.
    Stud look modelled on the user's example meshes: one inset square per block,
    dark upper-left inner edge, light lower-right inner edge, soft block seams."""
    fa, fb = a - np.floor(a), b - np.floor(b)
    ca, cb = np.floor(a), np.floor(b)
    r1 = _hash2(ca, cb, seed)
    r2 = _hash2(ca + 17, cb - 5, seed + 1)
    r3 = _hash2(ca - 3, cb + 11, seed + 2)
    col = np.zeros(a.shape + (3,), float)
    bone_c = np.where((r1 < 0.14)[..., None], np.array(IVORY, float) * 0.5 + np.array(BONE, float) * 0.5,
                      np.array(BONE, float))
    blue_mid = np.array(DARK_BLUE) * 0.65 + np.array(BLUE_ACCENT) * 0.35
    blue_c = np.where((r1 < 0.18)[..., None], blue_mid, np.array(DARK_BLUE, float))
    col = np.where((mat == M_BONE)[..., None], bone_c, col)
    col = np.where((mat == M_BLUE)[..., None], blue_c, col)
    col = np.where((mat == M_SOCKET)[..., None], np.array((20, 40, 95), float), col)
    # subtle per-block tone jitter
    col *= (0.96 + 0.08 * r2)[..., None]
    studded = (mat == M_BONE) | (mat == M_BLUE)
    # block seam (soft dark rim) + bevel highlight
    edge = np.minimum(np.minimum(fa, 1 - fa), np.minimum(fb, 1 - fb))
    seam = np.clip(1 - edge / 0.07, 0, 1)
    col *= (1 - 0.13 * seam * studded)[..., None]
    hl = np.clip(1 - fb / 0.08, 0, 1) * (edge > 0.02)
    col = col + (255 - col) * (0.10 * hl * studded)[..., None]
    # inset square stud
    jit_a = (r2 - 0.5) * 0.10
    jit_b = (r3 - 0.5) * 0.10
    size = 0.19 + 0.04 * r3
    sa, sb = fa - 0.5 - jit_a, fb - 0.5 - jit_b
    ins = (np.abs(sa) < size) & (np.abs(sb) < size)
    lw = 0.055
    dark_edge = ins & ((sa < -size + lw) | (sb > size - lw))
    light_edge = ins & ((sa > size - lw) | (sb < -size + lw)) & ~dark_edge
    outline = (np.abs(sa) < size + 0.035) & (np.abs(sb) < size + 0.035) & ~ins
    col = np.where((studded & ins)[..., None], col * 1.04, col)
    col = np.where((studded & outline)[..., None], col * 0.90, col)
    col = np.where((studded & dark_edge)[..., None], col * 0.80, col)
    col = np.where((studded & light_edge)[..., None], col + (255 - col) * 0.35, col)
    # glow cores / eye
    cyan = np.array(CYAN, float)
    col = np.where((mat == M_CYAN)[..., None], cyan * (0.9 + 0.1 * (1 - seam))[..., None], col)
    eye_c = np.where((np.maximum(np.abs(fa - 0.5), np.abs(fb - 0.5)) < 0.3)[..., None],
                     np.array((225, 255, 255), float), cyan)
    col = np.where((mat == M_EYE)[..., None], eye_c, col)
    emis = ((mat == M_CYAN) | (mat == M_EYE)).astype(float)
    return np.clip(col, 0, 255), emis


class Atlas:
    def __init__(self, size, ppc, pad=2):
        self.size, self.ppc, self.pad = size, ppc, pad
        self.img = np.zeros((size, size, 3), float)
        self.emis = np.zeros((size, size), float)
        self.x = self.y = self.row_h = 0

    def alloc(self, w, h):
        if self.x + w > self.size:
            self.x, self.y, self.row_h = 0, self.y + self.row_h, 0
        if self.y + h > self.size:
            raise RuntimeError("atlas full")
        x, y = self.x, self.y
        self.x += w
        self.row_h = max(self.row_h, h)
        return x, y


def plan_atlas(quads, n_teeth, n_glow, size):
    """choose the largest pixels-per-cube that fits all islands"""
    for ppc in range(40, 3, -1):
        try:
            at = Atlas(size, ppc)
            items = sorted(quads, key=lambda q: -(q.plane[4] - q.plane[3]))
            for q in items:
                d, u, v, u0, u1, v0, v1, cu, cv = q.plane
                at.alloc(int(round((v1 - v0) * ppc)) + 2 * at.pad, int(round((u1 - u0) * ppc)) + 2 * at.pad)
            for _ in range(n_teeth + n_glow + 2):
                at.alloc(ppc + 2 * at.pad, ppc + 2 * at.pad)
            used = (at.y + at.row_h) / size
            return ppc
        except RuntimeError:
            continue
    raise RuntimeError("cannot fit")


def paint_atlas(quads, size, ppc, seed=7):
    """Paint each quad into its own island; sets q.uvs (list of 4 uv tuples, same order as corners)."""
    at = Atlas(size, ppc)
    pad = at.pad
    items = sorted(quads, key=lambda q: -(q.plane[4] - q.plane[3]))
    for q in items:
        d, u, v, u0, u1, v0, v1, cu, cv = q.plane
        wpx = int(round((v1 - v0) * ppc))
        hpx = int(round((u1 - u0) * ppc))
        x, y = at.alloc(wpx + 2 * pad, hpx + 2 * pad)
        # pixel centres -> local face coords (clamped into the quad for padding bleed)
        px = (np.arange(wpx + 2 * pad) - pad + 0.5) / ppc
        py = (np.arange(hpx + 2 * pad) - pad + 0.5) / ppc
        px = np.clip(px, 0.5 / ppc, (v1 - v0) - 0.5 / ppc)
        py = np.clip(py, 0.5 / ppc, (u1 - u0) - 0.5 / ppc)
        PY, PX = np.meshgrid(py, px, indexing="ij")
        # material lookup by cell
        cu_idx = np.clip((PY / cu).astype(int), 0, q.mats.shape[0] - 1)
        cv_idx = np.clip((PX / cv).astype(int), 0, q.mats.shape[1] - 1)
        mat = q.mats[cu_idx, cv_idx]
        A = u0 + PY
        B = v0 + PX
        seed_q = seed + d * 101 + (q.normal[d] > 0) * 7 + hash(q.part.name) % 1000
        col, em = stud_pixels(B, A, mat, seed_q)
        at.img[y:y + hpx + 2 * pad, x:x + wpx + 2 * pad] = col
        at.emis[y:y + hpx + 2 * pad, x:x + wpx + 2 * pad] = em
        # uv for corners. corner (uu,vv) -> pixel (x+pad+(vv-v0)*ppc, y+pad+(uu-u0)*ppc)
        uvs = []
        for cpt in q.corners:
            uu, vv = cpt[u], cpt[v]
            pxx = x + pad + (vv - v0) * ppc
            pyy = y + pad + (uu - u0) * ppc
            uvs.append((pxx / size, 1 - pyy / size))
        q.uvs = uvs
    return at


def paint_solid_tiles(at, specs):
    """specs: list of (kind) -> returns uv rects for teeth / glow tiles"""
    rects = []
    ppc, pad, size = at.ppc, at.pad, at.size
    for kind in specs:
        x, y = at.alloc(ppc + 2 * pad, ppc + 2 * pad)
        n = ppc + 2 * pad
        t = np.linspace(0, 1, n)
        if kind == "tooth":
            g = t[:, None] * np.ones((1, n))
            col = np.array(IVORY, float)[None, None] * (1 - g[..., None]) + np.array((252, 246, 232), float)[None, None] * g[..., None]
            em = np.zeros((n, n))
        else:  # glow
            r = np.hypot(t[:, None] - 0.5, t[None, :] - 0.5)
            col = np.array(CYAN, float)[None, None] + (np.array((220, 255, 255), float) - np.array(CYAN, float))[None, None] * np.clip(1 - r / 0.45, 0, 1)[..., None] * 0.6
            em = np.ones((n, n))
        at.img[y:y + n, x:x + n] = col
        at.emis[y:y + n, x:x + n] = em
        rects.append(((x + pad + 1) / size, 1 - (y + pad + ppc - 1) / size, (x + pad + ppc - 1) / size, 1 - (y + pad + 1) / size))
    return rects


def build_all(size=1024):
    parts = build_parts()
    order = ["Skull", "Spine", "Ribs", "TailFin", "Dorsal", "Spikes", "VentralFins", "Core"]
    byname = {p.name: p for p in parts}
    static = [byname[n] for n in order]
    occ_all = Occupancy(static)
    occ_skull = Occupancy([byname["Skull"], byname["Jaw"]])
    quads = []
    for p in parts:
        if p.name == "Jaw":
            quads += greedy_mesh(p, occ_skull)
        elif p in static:
            quads += greedy_mesh(p, occ_all)
        else:
            quads += greedy_mesh(p)
    # low-priority fill parts sit a hair inside the others: no coplanar (self-shadowing) faces left
    for q in quads:
        if q.part.name in ("Core", "VentralFins"):
            d = q.plane[0]
            for c in q.corners:
                c[d] -= 0.03 * q.normal[d]
    teeth = tooth_geometry()
    glows = glow_boxes()
    ppc = plan_atlas(quads, 1, 1, size)
    at = paint_atlas(quads, size, ppc)
    tooth_rect, glow_rect = paint_solid_tiles(at, ["tooth", "glow"])
    return dict(parts=parts, quads=quads, teeth=teeth, glows=glows, atlas=at, ppc=ppc,
                tooth_rect=tooth_rect, glow_rect=glow_rect)


def tri_count(res):
    t = 2 * len(res["quads"])
    for vs, fs, _ in res["teeth"]:
        t += sum(len(f) - 2 for f in fs)
    t += 12 * len(res["glows"])
    return t


if __name__ == "__main__":
    import sys, time
    t0 = time.time()
    res = build_all()
    per = {}
    for q in res["quads"]:
        per[q.part.name] = per.get(q.part.name, 0) + 2
    print("tris per part", per)
    print("teeth tris", sum(sum(len(f) - 2 for f in fs) for _, fs, _ in res["teeth"]), "glow", 12 * len(res["glows"]))
    print("TOTAL TRIS", tri_count(res), "ppc", res["ppc"], "time", round(time.time() - t0, 1))
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    Image.fromarray(res["atlas"].img.astype(np.uint8)).save(out + "/atlas_preview.png")
