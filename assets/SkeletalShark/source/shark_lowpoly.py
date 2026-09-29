"""Skeletal Shark - smooth low-poly build (lofted / extruded pieces, no voxel stair-steps).

Same shark coordinate system and reference measurements as shark_geo.py:
    i = length (0 = snout tip), w = lateral (+ = shark's left), z = height, in "cube" units.
Every piece is a closed shell; faces carry a material tag used by the texture baker.
"""
import math

import numpy as np

import shark_geo as G

BONE, BLUE, CYAN, SOCKET, TOOTH, EYE, PUPIL = "bone", "blue", "cyan", "socket", "tooth", "eye", "pupil"


class Mesh:
    def __init__(self):
        self.V, self.VB, self.F, self.FM, self.FP = [], [], [], [], []

    def v(self, p, bone):
        self.V.append(np.asarray(p, float))
        self.VB.append(bone)
        return len(self.V) - 1

    def f(self, idx, mat, part):
        self.F.append(list(idx))
        self.FM.append(mat)
        self.FP.append(part)


# ----------------------------------------------------------------------------- primitives
def loft(m, sections, side_mat, bone, part, cap0=None, cap1=None):
    """sections: list of (n,3) point rings (shark coords). side_mat: mat or fn(k)->mat."""
    n = len(sections[0])
    ids = [[m.v(p, bone) for p in sec] for sec in sections]
    for s in range(len(sections) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            mat = side_mat(k) if callable(side_mat) else side_mat
            m.f([ids[s][k], ids[s][k2], ids[s + 1][k2], ids[s + 1][k]], mat, part)
    base = side_mat(0) if callable(side_mat) else side_mat
    if cap0 is not False:  # False = hidden inside another piece, skip (saves texture space)
        m.f(ids[0][::-1], cap0 or base, part)
    if cap1 is not False:
        m.f(ids[-1], cap1 or base, part)


def prism(m, poly, to3d, mat, bone, part, side_mat=None):
    """Extrude a 2D polygon: to3d(a, b, s) with s = -1 / +1 for the two caps."""
    lo = [m.v(to3d(a, b, -1), bone) for a, b in poly]
    hi = [m.v(to3d(a, b, +1), bone) for a, b in poly]
    n = len(poly)
    m.f(lo[::-1], mat, part)
    m.f(hi, mat, part)
    for k in range(n):
        k2 = (k + 1) % n
        m.f([lo[k], lo[k2], hi[k2], hi[k]], side_mat or mat, part)


def box(m, lo, hi, mat, bone, part):
    (a0, b0, c0), (a1, b1, c1) = lo, hi
    prism(m, [(a0, c0), (a1, c0), (a1, c1), (a0, c1)], lambda a, c, s: (a, b0 if s < 0 else b1, c), mat, bone, part)


def side_prism(m, poly_iz, w_in, w_out, mat, bone, part, mirror=True):
    """Polygon in the side (i,z) plane, extruded laterally between w_in(i,z) and w_out(i,z)."""
    for sd in ((1, -1) if mirror else (1,)):
        prism(m, poly_iz, lambda a, c, s, sd=sd: (a, sd * (w_out(a, c) if s > 0 else w_in(a, c)), c), mat, bone, part)


def fin(m, poly_iz, half, mat, bone, part):
    prism(m, poly_iz, lambda a, c, s: (a, s * half, c), mat, bone, part)


def pyramid(m, base_c, base, tip, bone, part, mat=TOOTH):
    i, w, z = base_c
    b = base / 2
    ids = [m.v((i + da, w + dw, z), bone) for da, dw in ((-b, -b), (b, -b), (b, b), (-b, b))]
    t = m.v(tip, bone)
    m.f(ids, mat, part)
    for k in range(4):
        m.f([ids[k], ids[(k + 1) % 4], t], mat, part)


# ----------------------------------------------------------------------------- skull
SNOUT_I = [0.0, 0.6, 2.0, 3.2, 4.4, 5.6, 7.0, 8.8]
SNOUT_BOT = ([0, 2.8, 4.0, 5.0, 8.8], [7.1, 7.0, 6.3, 5.9, 5.9])
TOP = ([0, 0.6, 4.6, 5.4, 8.6, 9.0, 12.4], [9.3, 9.8, 9.9, 10.4, 10.4, 10.1, 10.1])
HW = ([0, 1, 2, 3, 4, 4.6, 5.5, 6.5, 12.4], [2.3, 2.7, 3.0, 3.3, 3.6, 4.1, 4.5, 4.7, 4.7])


def skull_section(i, bot, top, hw, top_frac=0.22, bot_frac=0.2, hwt=0.55, hwb=0.85):
    h = top - bot
    zu, zl = top - top_frac * h, bot + bot_frac * h
    return np.array([(i, hwt * hw, top), (i, hw, zu), (i, hw, zl), (i, hwb * hw, bot),
                     (i, -hwb * hw, bot), (i, -hw, zl), (i, -hw, zu), (i, -hwt * hw, top)])


def hw_at(i):
    return float(np.interp(i, *HW))


def build_skull(m):
    secs = [skull_section(i, np.interp(i, *SNOUT_BOT), np.interp(i, *TOP), hw_at(i)) for i in SNOUT_I]
    # bottom face of the snout = palate (dark blue); everything else bone
    loft(m, secs, lambda k: BLUE if k == 3 else BONE, "Head", "skull")
    cran_i = [8.0, 9.4, 11.0, 12.4]
    secs = [skull_section(i, 1.8, np.interp(i, *TOP), 4.7, 0.25, 0.25, 0.55, 0.8) for i in cran_i]
    loft(m, secs, BONE, "Head", "skull", cap0=BLUE)  # front cap = back wall of the mouth
    # eye canal is cut into the skull with a boolean in build_blend.py (see eye_canal_cutter);
    # brow ridge above and cheekbone below frame the round canal like the reference
    frame = lambda a, c: hw_at(a) + 0.45  # noqa: E731
    side_prism(m, [(4.2, 9.25), (8.3, 9.25), (8.0, 10.0), (4.7, 10.05)], lambda a, c: hw_at(a) - 0.6, frame,
               BONE, "Head", "skull")
    side_prism(m, [(4.5, 6.45), (8.0, 6.45), (7.7, 7.1), (4.8, 7.1)], lambda a, c: hw_at(a) - 0.6, frame,
               BONE, "Head", "skull")
    for sd in (1, -1):
        # nostril pit, cheek slot
        box(m, (1.8, 2.75 if sd > 0 else -3.15, 8.3), (2.7, 3.15 if sd > 0 else -2.75, 9.05), SOCKET, "Head", "skull")
        box(m, (10.4, 4.45 if sd > 0 else -4.9, 5.4), (11.3, 4.9 if sd > 0 else -4.45, 7.0), SOCKET, "Head", "skull")
    # chunky raised plates on the crown / cheeks (the reference skull is built of blocks)
    plates = [(1.2, 3.0, -1.2, 1.2, 9.8), (5.6, 7.4, -2.0, -0.4, 10.4), (5.6, 7.4, 0.4, 2.0, 10.4),
              (9.4, 11.2, -1.5, 1.5, 10.1), (3.0, 4.4, -1.6, -0.2, 9.9)]
    for a0, a1, b0, b1, z in plates:
        box(m, (a0, b0, z - 0.2), (a1, b1, z + 0.35), BONE, "Head", "skull")
    for sd in (1, -1):
        box(m, (9.2, sd * 4.5 if sd > 0 else -5.05, 2.6), (11.8, 5.05 if sd > 0 else -4.5, 4.4), BONE, "Head", "skull")
        box(m, (9.0, sd * 4.5 if sd > 0 else -5.0, 7.6), (12.0, 5.0 if sd > 0 else -4.5, 9.0), BONE, "Head", "skull")


# ----------------------------------------------------------------------------- lower jaw
JAW_I = [2.6, 3.4, 5.0, 6.5, 8.0, 9.6]
JAW_TOP = ([2.6, 4.0, 6.0, 8.0, 9.6], [2.9, 3.0, 3.4, 3.9, 4.3])
JAW_HW = ([2.6, 4, 6, 9.6], [2.9, 3.6, 4.1, 4.4])


def build_jaw(m):
    """Solid lower jaw (bevelled top) with a raised blue tongue plate; the teeth are embedded in its rim."""
    secs, tongue = [], []
    for i in JAW_I:
        top = float(np.interp(i, *JAW_TOP))
        hw = float(np.interp(i, *JAW_HW))
        bot = 1.2 if i < 3.0 else 1.0
        secs.append(np.array([(i, -(hw - 0.25), top), (i, -hw, top - 0.2), (i, -0.9 * hw, bot),
                              (i, 0.9 * hw, bot), (i, hw, top - 0.2), (i, hw - 0.25, top)]))
        if i >= 3.4:
            ti = max(i, 3.9)
            tw = hw - 1.0
            tongue.append(np.array([(ti, -tw, top - 0.1), (ti, tw, top - 0.1), (ti, tw, top + 0.12),
                                    (ti, -tw, top + 0.12)]))
    loft(m, secs, BONE, "Jaw", "jaw")
    loft(m, tongue, BLUE, "Jaw", "jaw")
    box(m, (9.3, -2.6, 0.5), (10.9, 2.6, 1.9), BONE, "Jaw", "jaw")
    box(m, (3.0, -1.6, 0.7), (6.0, 1.6, 1.25), BONE, "Jaw", "jaw")  # chin block


# ----------------------------------------------------------------------------- teeth
def build_teeth(m):
    up_i = [1.1, 2.1, 3.3, 4.4, 5.5, 6.6, 7.5]
    up_L = [1.7, 1.8, 1.7, 1.6, 1.5, 1.3, 1.1]
    for sd in (1, -1):
        for i, L in zip(up_i, up_L):
            zb = float(np.interp(i, *SNOUT_BOT))
            w = sd * (0.85 * hw_at(i) - 0.4)
            pyramid(m, (i, w, zb + 0.3), 0.75, (i, w, zb - L), "Head", "teeth")
    for w in (-1.3, -0.45, 0.45, 1.3):
        pyramid(m, (0.55, w, 7.4), 0.7, (0.55, w, 7.2 - 1.6), "Head", "teeth")
    lo_i = [3.6, 4.4, 5.2, 6.0, 6.8, 7.6]
    lo_L = [1.25, 1.35, 1.35, 1.25, 1.1, 1.0]
    for sd in (1, -1):
        for i, L in zip(lo_i, lo_L):
            zb = float(np.interp(i, *JAW_TOP))
            w = sd * (float(np.interp(i, *JAW_HW)) - 0.4)
            pyramid(m, (i, w, zb - 0.3), 0.68, (i, w, zb + L), "Jaw", "teeth")
    for w in (-1.3, -0.45, 0.45, 1.3):
        pyramid(m, (3.0, w, 2.6), 0.64, (3.0, w, 2.9 + 1.1), "Jaw", "teeth")


# ----------------------------------------------------------------------------- body
def ring(i, hw, zc, hh, n=10, e=2.2, lift=0.0):
    pts = []
    for k in range(n):
        t = 2 * math.pi * (k + 0.5) / n
        s, c = math.sin(t), math.cos(t)
        pts.append((i, hw * math.copysign(abs(s) ** (2 / e), s), zc + hh * math.copysign(abs(c) ** (2 / e), c)))
    return np.array(pts)


def build_core(m):
    I = list(np.arange(12.0, 38.01, 1.3)) + [39.6, 41.0]
    secs = []
    for i in I:
        top, bot, hw = float(G.core_top(i)), float(G.core_bot(i)), float(G.core_hw(i))
        secs.append(ring(i, hw, (top + bot) / 2, (top - bot) / 2))
    loft(m, secs, BLUE, "SPINE", "core", cap0=False)


def build_ribs(m, n=16):
    for ic, bot, top, hwo, th, a, b in G.RIBS:
        zc, hh = (top + bot) / 2, (top - bot) / 2
        rings = []
        for k in range(n):
            t = 2 * math.pi * k / n
            s, c = math.sin(t), math.cos(t)
            z_o = zc + hh * c
            u = c
            off = a * (z_o - zc) + b * (1 - u * u)
            ii = ic + off
            po = (hwo * s, zc + hh * c)
            pi_ = ((hwo - 0.7) * s, zc + (hh - 0.7) * c)
            rings.append([(ii - th / 2, po[0], po[1]), (ii + th / 2, po[0], po[1]),
                          (ii + th / 2, pi_[0], pi_[1]), (ii - th / 2, pi_[0], pi_[1])])
        ids = [[m.v(p, "SPINE") for p in r] for r in rings]
        for k in range(n):
            k2 = (k + 1) % n
            for q in range(4):
                q2 = (q + 1) % 4
                m.f([ids[k][q], ids[k][q2], ids[k2][q2], ids[k2][q]], BONE, "ribs")


def build_spine(m):
    # dorsal ridge bar following the back
    secs = []
    for i in list(np.arange(12.5, 36.6, 1.3)) + [37.5]:
        ct = float(G.core_top(i))
        secs.append(np.array([(i, 0.45, ct + 0.5), (i, 0.45, ct - 0.4), (i, -0.45, ct - 0.4), (i, -0.45, ct + 0.5)]))
    loft(m, secs, BONE, "SPINE", "spine")
    for v in G.VERT_TOP:
        ct = float(G.core_top(v))
        box(m, (v - 0.45, -1.5, ct - 0.35), (v + 0.45, 1.5, ct + 0.45), BONE, "SPINE", "spine")
    # tail spine bar + vertebra crosses
    secs = [np.array([(i, 0.7, 5.5), (i, 0.7, 4.2), (i, -0.7, 4.2), (i, -0.7, 5.5)]) for i in np.arange(27.0, 43.6, 1.5)]
    loft(m, secs, BONE, "SPINE", "spine")
    for ic, zb, zt, th, lat in G.TAIL_VERTS:
        box(m, (ic - th / 2, -0.75, zb), (ic + th / 2, 0.75, zt), BONE, "SPINE", "spine")
        box(m, (ic - th / 2, -lat, 4.1), (ic + th / 2, lat, 5.6), BONE, "SPINE", "spine")


# ----------------------------------------------------------------------------- fins
DORSAL_BLUE = [(17.6, 9.2), (18.7, 10.8), (19.8, 12.0), (21.0, 12.9), (21.9, 13.35), (22.2, 12.9), (22.4, 11.4),
               (22.9, 10.5), (23.6, 9.6), (23.8, 9.2)]
TAIL_BLUE_U = [(39.9, 7.2), (40.7, 8.6), (41.9, 9.7), (43.8, 10.7), (43.8, 8.3), (43.0, 7.2)]
TAIL_BLUE_L = [(39.8, 4.1), (41.4, 4.1), (42.4, 2.5), (43.3, 0.9), (43.7, 0.1), (42.4, 1.1), (41.0, 2.2), (40.3, 3.2)]
PEC_BLUE = [(1.0, 0.95), (2.7, 0.85), (5.4, 0.45), (7.6, 0.1), (8.3, -0.05), (7.6, -0.15), (5.4, -0.55),
            (2.7, -1.05), (1.0, -1.1)]


def seat(poly, zcut, znew):
    """Push every outline point at/below zcut down to znew so the fin is embedded in the body."""
    return [(a, znew if c <= zcut else c) for a, c in poly]


def build_fins(m):
    # fins are sunk into the back so they grow out of the spine ridge (no floating seam)
    fin(m, seat(G.DORSAL_POLY, 9.25, 8.3), 0.45, BONE, "Dorsal", "dorsal")
    fin(m, seat(DORSAL_BLUE, 9.25, 8.4), 0.62, BLUE, "Dorsal", "dorsal")
    # tapered blue root fairing: wide on the spine ridge, narrowing into the fin blade
    secs = []
    for i, k in ((15.9, 0.25), (17.4, 0.8), (19.5, 1.0), (21.6, 1.0), (23.3, 0.8), (24.4, 0.25)):
        zb = float(G.core_top(i)) - 0.2
        zt = 10.3 if 17 < i < 23.5 else 9.8
        secs.append(np.array([(i, 0.62, zt), (i, 0.62 + 0.75 * k, zb + 0.5), (i, 0.5 + 0.75 * k, zb),
                              (i, -0.5 - 0.75 * k, zb), (i, -0.62 - 0.75 * k, zb + 0.5), (i, -0.62, zt)]))
    loft(m, secs, BLUE, "Dorsal", "dorsal")
    for name, poly in G.SPIKES.items():
        base_z = float(G.core_top(np.mean([p[0] for p in poly]))) if name != "V1" else None
        if name == "S0":
            fin(m, poly, 0.4, BONE, "Head", "spikes")
        elif name == "V1":
            fin(m, [(a, c if c < 3.5 else c + 0.8) for a, c in poly], 0.4, BONE, "SPINE", "spikes")
        else:
            fin(m, seat(poly, min(p[1] for p in poly) + 0.6, base_z - 0.6), 0.4, BONE, "SPINE", "spikes")
    # collar where the tail stem enters the tail fin
    box(m, (36.2, -0.95, 3.7), (38.6, 0.95, 6.3), BONE, "TailFin", "tail")
    for name, poly in G.BLUE_FINS.items():
        fin(m, poly, 0.4, BLUE, "SPINE", "ventral")
    fin(m, G.TAIL_POLY, 0.45, BONE, "TailFin", "tail")
    fin(m, TAIL_BLUE_U, 0.62, BLUE, "TailFin", "tail")
    fin(m, TAIL_BLUE_L, 0.62, BLUE, "TailFin", "tail")
    for sd, bone in ((1, "PectoralL"), (-1, "PectoralR")):
        xf = G.pec_xf(sd)

        def to3d(u, v, s, half, xf=xf):
            p = xf @ np.array([u, v, s * half, 1.0])
            return tuple(p[:3])
        prism(m, G.PEC_POLY, lambda u, v, s: to3d(u, v, s, 0.4), BONE, bone, "pectoral")
        prism(m, PEC_BLUE, lambda u, v, s: to3d(u, v, s, 0.56), BLUE, bone, "pectoral")


def build_glow(m):
    for ic, half in G.GLOW:
        hw = float(G.core_hw(ic)) - 0.05
        box(m, (ic - half * 0.8, -hw, 3.6), (ic + half * 0.8, hw, 6.4), CYAN, "SPINE", "glow")


# ----------------------------------------------------------------------------- eyes
EYE_C = (6.1, 8.15)      # (i, z) centre of the eye canal
CANAL_R = 0.92           # canal radius
IRIS_R = 0.68            # neon iris radius
CANAL_DEPTH = 1.35       # how far the canal goes into the skull (from the skull side)


def disc(m, ci, cz, rx, rz, w0, w1, dome, sd, mat, bone, part, n=16):
    """Circular/elliptical disc along the lateral axis, back at w0, front at w1, domed front."""
    back = [m.v((ci + rx * math.cos(2 * math.pi * k / n), sd * w0, cz + rz * math.sin(2 * math.pi * k / n)), bone)
            for k in range(n)]
    front = [m.v((ci + rx * math.cos(2 * math.pi * k / n), sd * w1, cz + rz * math.sin(2 * math.pi * k / n)), bone)
             for k in range(n)]
    tip = m.v((ci, sd * (w1 + dome), cz), bone)
    m.f(back[::-1], mat, part)
    for k in range(n):
        k2 = (k + 1) % n
        m.f([back[k], back[k2], front[k2], front[k]], mat, part)
        m.f([front[k], front[k2], tip], mat, part)


def eye_canal_cutter(n=16):
    """Boolean cutters for the eye canals: a tapered, slightly almond-shaped funnel tilted down toward the
    snout - wide bevelled mouth at the skull surface, narrowing into the canal that holds the eye."""
    ci, cz = EYE_C
    hw = hw_at(ci)
    tilt = 0.22
    # (lateral depth offset from the skull side, horizontal radius, vertical radius)
    rings = [(1.6, 1.55, 1.25), (0.0, 1.22, 0.98), (-0.35, 0.98, 0.86), (-0.75, 0.86, 0.8),
             (-CANAL_DEPTH, 0.8, 0.78)]
    verts, faces = [], []
    for sd in (1, -1):
        base = len(verts)
        for off, rx, rz in rings:
            for k in range(n):
                t = 2 * math.pi * k / n
                di, dz = rx * math.cos(t), rz * math.sin(t)
                verts.append((ci + di * math.cos(tilt) - dz * math.sin(tilt), sd * (hw + off),
                              cz + di * math.sin(tilt) + dz * math.cos(tilt)))
        nr = len(rings)
        faces.append([base + k for k in range(n)][::-1])
        faces.append([base + (nr - 1) * n + k for k in range(n)])
        for r in range(nr - 1):
            for k in range(n):
                k2 = (k + 1) % n
                faces.append([base + r * n + k, base + r * n + k2, base + (r + 1) * n + k2, base + (r + 1) * n + k])
    return verts, faces


def build_eyes(m):
    ci, cz = EYE_C
    hw = hw_at(ci)
    back = hw - CANAL_DEPTH + 0.05
    front = hw - 0.72
    for sd in (1, -1):
        disc(m, ci, cz, IRIS_R, IRIS_R, back, front, 0.14, sd, EYE, "Head", "eye")
        # vertical pupil (shark-like), sitting proud of the domed iris
        disc(m, ci, cz, 0.2, 0.4, front + 0.02, front + 0.13, 0.04, sd, PUPIL, "Head", "eye", n=12)


def build_all():
    m = Mesh()
    build_skull(m)
    build_eyes(m)
    build_jaw(m)
    build_teeth(m)
    build_core(m)
    build_ribs(m)
    build_spine(m)
    build_fins(m)
    build_glow(m)
    return m


def tri_count(m):
    return sum(len(f) - 2 for f in m.F)


if __name__ == "__main__":
    m = build_all()
    per = {}
    for f, p in zip(m.F, m.FP):
        per[p] = per.get(p, 0) + len(f) - 2
    print(per, "TOTAL", tri_count(m), "verts", len(m.V))
