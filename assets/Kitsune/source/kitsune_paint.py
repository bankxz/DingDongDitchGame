"""
Procedural texture painter for the kitsune.

Rasterises every mesh triangle into UV space, interpolates the per-corner loft
parameters (t, th), rest positions and normals, and evaluates hand-designed
colour rules that reproduce the reference sheet:
  * dark indigo/purple fur painted as chunky pointed clumps
  * cyan lightning / flame markings (body, chest, face mask, tails)
  * cyan lower legs with a jagged fur boundary, bright paws and claws
  * tails: purple base -> jagged boundary -> cyan -> white-cyan tip
  * red rope with twist stripes, red gem / beads / tassels, glowing red eyes

Outputs (numpy, H x W):  color (sRGB 0..1, RGB), emissive mask, roughness,
height (for the normal map) and a per-face region label used for material
slot assignment.
"""
import math
import numpy as np
from kitsune_geo import PART_IDS

P = PART_IDS

# ---- palette (sRGB), calibrated from k-means clusters of the reference sheet
PURPLE_DK = np.array([0.105, 0.070, 0.330])
PURPLE = np.array([0.215, 0.150, 0.570])
PURPLE_LT = np.array([0.345, 0.270, 0.780])
PURPLE_HEAD = np.array([0.255, 0.170, 0.620])
CYAN_DK = np.array([0.070, 0.560, 0.800])
CYAN = np.array([0.090, 0.870, 0.975])
CYAN_LT = np.array([0.470, 0.930, 0.985])
TIP_WHITE = np.array([0.880, 0.990, 1.000])
RED = np.array([0.820, 0.140, 0.230])
RED_DK = np.array([0.420, 0.040, 0.110])
RED_GEM = np.array([1.000, 0.090, 0.160])
EYE_RED = np.array([1.000, 0.060, 0.150])

REG_FUR, REG_CYAN, REG_TIP, REG_ROPE, REG_ORN, REG_EYE = range(6)


# --------------------------------------------------------------- noise utils
def _hash2(ix, iy, seed=0.0):
    return np.modf(np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453)[0] % 1.0


def vnoise(x, y, seed=0.0):
    ix, iy = np.floor(x), np.floor(y)
    fx, fy = x - ix, y - iy
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = _hash2(ix, iy, seed)
    b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed)
    d = _hash2(ix + 1, iy + 1, seed)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def fbm(x, y, seed=0.0):
    return 0.6 * vnoise(x, y, seed) + 0.3 * vnoise(x * 2.1, y * 2.1, seed + 3) + 0.1 * vnoise(x * 4.3, y * 4.3, seed + 7)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy + 1e-12
    h = np.clip(((px - ax) * dx + (py - ay) * dy) / L2, 0, 1)
    return np.hypot(px - ax - h * dx, py - ay - h * dy), h


def stroke_mask(px, py, pts, w0, w1, jag=0.0, seed=0.0):
    """Tapered polyline stroke (lightning / flame). Returns 0..1 coverage."""
    L = [0.0]
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L.append(L[-1] + math.hypot(bx - ax, by - ay))
    tot = L[-1]
    best = np.full(px.shape, 1e9)
    for i, ((ax, ay), (bx, by)) in enumerate(zip(pts, pts[1:])):
        d, h = seg_dist(px, py, ax, ay, bx, by)
        s = (L[i] + h * (L[i + 1] - L[i])) / tot
        w = w0 + (w1 - w0) * s
        w = w * (1.0 - 0.9 * s ** 3)             # pointed end
        if jag:
            w = w * (1.0 + jag * (vnoise(px * 60, py * 60, seed) - 0.5))
        best = np.minimum(best, d / np.maximum(w, 1e-5))
    return 1.0 - smoothstep(0.85, 1.05, best)


def fur_clumps(a, b, ca, cb, seed=0.0):
    """Painted-fur pattern: long soft strands along the flow (a) with a few
    darker jagged clump separations.  Returns (shade 0..1, height 0..1, gap 0..1)."""
    # strands: noise stretched along the flow direction
    st = fbm(b / (cb * 0.28), a / (ca * 1.6), seed)
    # clump lobes: broad bands across the flow with jagged, flame-like fronts
    lobe_v = a / ca + 0.9 * fbm(b / (cb * 0.9), a / (ca * 3.0), seed + 5)
    v = lobe_v - np.floor(lobe_v)
    shade = np.clip(0.30 + 0.50 * st + 0.35 * (1 - v) ** 1.5, 0, 1)
    height = np.clip(0.45 * st + 0.55 * (1 - v), 0, 1)
    gap = smoothstep(0.90, 1.0, v) * 0.8
    return shade, height, gap


def lerp3(c0, c1, f):
    f = np.asarray(f)[..., None]
    return c0 * (1 - f) + c1 * f


# ------------------------------------------------------------------ painter
class Samples:
    """Bundle of interpolated attributes at texel centres."""

    def __init__(self, t, th, pos, nrm, part, face):
        self.t, self.th, self.P, self.N, self.part, self.face = t, th, pos, nrm, part, face


def paint_samples(s, ctx):
    n = len(s.t)
    col = np.zeros((n, 3))
    emi = np.zeros(n)
    rough = np.full(n, 0.85)
    hgt = np.zeros(n)
    reg = np.zeros(n, dtype=np.int32)

    def sel(*names):
        return np.isin(s.part, [P[k] for k in names])

    t, th = s.t, s.th
    X, Y, Z = s.P[:, 0], s.P[:, 1], s.P[:, 2]
    nz = s.N[:, 2]
    phi = np.arccos(np.clip(np.cos(th), -1, 1))          # 0 dorsal .. pi ventral
    toplight = 0.88 + 0.16 * nz

    # ---------------------------------------------------------- body fur
    def fur(m, L, R, flow_sign, base=PURPLE, seed=0.0, ca=0.16, cb=0.12, contrast=0.7):
        a = flow_sign * t[m] * L
        b = th[m] * R
        sh, h, gap = fur_clumps(a, b, ca, cb, seed)
        sh = 1 - contrast * (1 - sh)
        c = lerp3(PURPLE_DK, base, 0.30 + 0.70 * sh)
        c = lerp3(c, PURPLE_LT, np.clip(sh - 0.7, 0, 1) * 1.3)
        c = lerp3(c, PURPLE_DK * 0.8, gap * 0.35 * contrast)
        return c, h

    # torso -----------------------------------------------------------------
    # metric loft coordinates: ps = 0 (rump) .. 1.25 (chest), pp = 0 (spine) .. 0.94 (belly)
    m = sel('torso')
    if m.any():
        c, h = fur(m, 1.45, 0.25, -1, seed=1, ca=0.22, cb=0.17)
        ps, pp = t[m] * 1.45, phi[m] * 0.25       # ps: 0 rump .. 1.4 chest, pp: 0 spine .. 0.79 belly
        mk = np.zeros(m.sum())
        strokes = [   # clean lightning bolts (correction sheet side panels)
            ([(1.25, 0.50), (1.12, 0.40), (1.02, 0.44), (0.86, 0.34), (0.74, 0.38), (0.58, 0.30)], 0.032),  # flank bolt
            ([(1.22, 0.30), (1.15, 0.22), (1.20, 0.14)], 0.030),                                              # shoulder
            ([(0.36, 0.44), (0.28, 0.34), (0.33, 0.26), (0.25, 0.17)], 0.034),                                # haunch
        ]
        for i, (pts, w) in enumerate(strokes):
            mk = np.maximum(mk, stroke_mask(ps, pp, pts, w, w * 0.45, jag=0.1, seed=i))
        mk = np.maximum(mk, ((np.abs(ps - 0.14) / 0.055 + np.abs(pp) / 0.04) < 1).astype(float))    # rump diamond
        c = lerp3(c, CYAN, mk)
        col[m], hgt[m] = c * toplight[m][:, None], h
        emi[m] = mk
        reg[m] = REG_FUR

    # neck ------------------------------------------------------------------
    m = sel('neck')
    if m.any():
        c, h = fur(m, 0.45, 0.24, -1, seed=2, ca=0.17, cb=0.14)
        ps, pp = t[m] * 0.45, phi[m] * 0.24
        mk = np.zeros(m.sum())
        for i, (pts, w) in enumerate([
                ([(0.02, 0.70), (0.09, 0.64), (0.16, 0.71), (0.24, 0.65), (0.32, 0.71)], 0.034),   # chest bolt
                ([(0.04, 0.55), (0.11, 0.49), (0.18, 0.56), (0.26, 0.50)], 0.028),
                ([(0.10, 0.36), (0.17, 0.30), (0.24, 0.37)], 0.026)]):
            mk = np.maximum(mk, stroke_mask(ps, pp, pts, w, w * 0.5, jag=0.15, seed=10 + i))
        c = lerp3(c, CYAN, mk)
        col[m], hgt[m], emi[m] = c * toplight[m][:, None], h, mk

    # head ------------------------------------------------------------------
    # face mask designed relative to the eye centre E (reference close-ups)
    m = sel('head')
    if m.any():
        c, h = fur(m, 0.55, 0.16, -1, base=PURPLE_HEAD, seed=3, ca=0.14, cb=0.10, contrast=0.15)
        x, y, z = np.abs(X[m]), Y[m], Z[m]
        nzh = s.N[m, 2]
        E = ctx['eye_center']
        ex, ey, ez = abs(E[0]), E[1], E[2]
        mk = np.zeros(m.sum())
        top = nzh > 0.25
        # eye-local frame (mirrored to the left side): u toward the back/up along the
        # slanted eye, v across it (up), w out of the surface
        A, C, Nn = ctx['eye_along'], ctx['eye_acr'], ctx['eye_n']
        d = np.stack([x - ex, y - ey, z - ez], 1)
        u = d @ A
        vv = d @ C
        ww = d @ Nn
        near = np.abs(ww) < 0.05
        # cyan nose tip
        mk = np.maximum(mk, smoothstep(0.968, 0.978, t[m]))
        # forehead diamond + small crest diamond (centred)
        mk = np.maximum(mk, ((x / 0.026 + np.abs(y - (ey + 0.075)) / 0.055) < 1) & top)
        mk = np.maximum(mk, ((x / 0.016 + np.abs(y - (ey + 0.165)) / 0.028) < 1) & top)
        # sharp eye outline following the slanted lens, open-ended streak off the outer corner
        e = (u / 0.064) ** 2 + ((vv + 0.004) / 0.030) ** 2
        mk = np.maximum(mk, ((e > 1.05) & (e < 1.55) & near).astype(float))
        mk = np.maximum(mk, stroke_mask(u, vv, [(0.062, 0.006), (0.12, 0.022), (0.18, 0.040)], 0.011, 0.004, seed=22) * near)
        # brow slash parallel above the eye, rising toward the ear
        mk = np.maximum(mk, stroke_mask(u, vv, [(-0.050, 0.050), (0.040, 0.066), (0.130, 0.092)], 0.011, 0.004, seed=21)
                        * (np.abs(ww) < 0.07))
        # mask line from under the inner corner down the snout toward the nose
        mk = np.maximum(mk, stroke_mask(u, vv, [(-0.050, -0.030), (-0.120, -0.052), (-0.200, -0.070)], 0.010, 0.004,
                                        seed=23) * (np.abs(ww) < 0.08) * (x > 0.025))
        # cheek line under the eye into the cheek ruff
        mk = np.maximum(mk, stroke_mask(u, vv, [(0.000, -0.045), (0.070, -0.062), (0.140, -0.058)], 0.009, 0.004,
                                        seed=24) * (np.abs(ww) < 0.08))
        mk = np.clip(mk, 0, 1)
        c = lerp3(c, CYAN, mk)
        col[m], hgt[m], emi[m] = c * toplight[m][:, None], h * 0.5, mk

    # ears ------------------------------------------------------------------
    m = sel('ear')
    if m.any():
        c, h = fur(m, 0.3, 0.05, -1, base=PURPLE_HEAD, seed=4, ca=0.08, cb=0.05, contrast=0.5)
        edge = np.abs(np.sin(th[m]))
        front = np.cos(th[m]) < -0.2
        rim = smoothstep(0.84, 0.92, edge + 0.08 * (vnoise(t[m] * 25, th[m] * 3, 3) - 0.5))
        tip = smoothstep(0.80, 0.86, t[m])
        inner = front & (edge < 0.55) & (t[m] > 0.15)
        c = lerp3(c, PURPLE_DK * 0.8, inner.astype(float) * 0.8)
        streak = inner & (np.abs(np.sin(th[m] * 3)) > 0.8) & (t[m] < 0.6)
        mk = np.clip(np.maximum(rim, tip), 0, 1)
        c = lerp3(c, CYAN, mk)
        col[m], hgt[m], emi[m] = c, h, mk

    # legs ------------------------------------------------------------------
    for part, L, tb, seed in (('leg_f', 0.80, 0.53, 5), ('leg_h', 0.90, 0.50, 6)):
        m = sel(part)
        if not m.any():
            continue
        c, h = fur(m, L, 0.07, 1, seed=seed, ca=0.12, cb=0.08)
        k = 7
        saw = 1 - np.abs(2 * (((th[m] * k / (2 * np.pi)) + 0.25 * vnoise(th[m] * 2, t[m] * 3, seed)) % 1.0) - 1)
        bound = tb - 0.10 * saw ** 2.5
        cy = smoothstep(bound - 0.006, bound + 0.006, t[m])
        grad = smoothstep(tb, 1.0, t[m])
        cc = lerp3(CYAN, CYAN_LT, grad * 0.6)
        # cyan fur strands in the lower leg
        sh2, h2, gap2 = fur_clumps(t[m] * L, th[m] * 0.07, 0.10, 0.07, seed + 9)
        cc = lerp3(cc * 0.88, cc, sh2)
        c = lerp3(c, cc, cy)
        col[m], hgt[m], emi[m] = c, np.where(cy > 0.5, h2 * 0.6, h), cy
        reg[m] = np.where(cy > 0.5, REG_CYAN, REG_FUR)

    # paws / claws ------------------------------------------------------------
    m = sel('paw')
    if m.any():
        sh, h, gap = fur_clumps(t[m] * 0.15, th[m] * 0.05, 0.05, 0.03, 12)
        c = lerp3(CYAN_DK, CYAN, 0.6 + 0.4 * sh)
        c = lerp3(c, CYAN_LT, smoothstep(0.6, 1.0, t[m]) * 0.7)
        col[m], hgt[m], emi[m], reg[m] = c, h * 0.5, 1.0, REG_CYAN
    m = sel('claw')
    if m.any():
        col[m] = lerp3(CYAN_LT, TIP_WHITE, t[m])
        emi[m], reg[m], rough[m] = 1.0, REG_CYAN, 0.4

    # tails -----------------------------------------------------------------
    m = sel('tail')
    if m.any():
        tt, a = t[m], th[m]
        sh, h, gap = fur_clumps(tt * 1.35, a * 0.2, 0.24, 0.17, 13)
        sh = 1 - 0.65 * (1 - sh)
        base = lerp3(PURPLE_DK, PURPLE, 0.30 + 0.70 * sh)
        base = lerp3(base, PURPLE_LT, np.clip(sh - 0.7, 0, 1) * 1.3)
        base = lerp3(base, PURPLE_DK * 0.7, gap * 0.6)
        # jagged purple -> cyan boundary (flames pointing to the tail base)
        k = 5
        saw = 1 - np.abs(2 * (((a * k / (2 * np.pi)) + 0.35 * vnoise(a * 1.5, tt * 4, 7)) % 1.0) - 1)
        bound = 0.70 - 0.20 * saw ** 2.2
        cy = smoothstep(bound - 0.008, bound + 0.008, tt)
        grad = smoothstep(0.62, 0.97, tt)
        streak = 0.5 + 0.5 * np.sin(a * 7 + tt * 9 + 2 * vnoise(a * 3, tt * 6, 9))
        cc = lerp3(CYAN, CYAN_LT, smoothstep(0.35, 0.75, grad))
        cc = lerp3(cc, TIP_WHITE, smoothstep(0.72, 1.0, grad))
        cc = lerp3(cc * 0.90, cc, streak * 0.6 + 0.4)
        # small cyan diamonds on the broad faces of the purple part
        dia = np.zeros(m.sum())
        for tc, ac in ((0.46, 0.0), (0.46, np.pi)):
            da = np.abs(((a - ac + np.pi) % (2 * np.pi)) - np.pi)
            dia = np.maximum(dia, ((np.abs(tt - tc) / 0.035 + da / 0.25) < 1).astype(float))
        base = lerp3(base, CYAN, dia * (1 - cy))
        c = lerp3(base, cc, cy)
        col[m], hgt[m] = c, np.where(cy > 0.5, h * 0.5, h)
        emi[m] = np.maximum(cy, dia)
        reg[m] = np.where(cy > 0.5, np.where(tt > 0.80, REG_TIP, REG_CYAN), REG_FUR)

    # fur clumps ------------------------------------------------------------
    # leaf clumps: t = 0 root .. 1 tip; th ~1.57 on the top ridge, 0 / 3.14 at the edges
    m = sel('tuft', 'spike', 'tuft_tip', 'tuft_cyan')
    if m.any():
        ridge = np.clip(np.sin(np.clip(th[m], 0, np.pi)), 0, 1)
        under = th[m] > np.pi + 0.2
        c = lerp3(PURPLE_DK, PURPLE, 0.55 + 0.35 * ridge + 0.1 * t[m])
        c = lerp3(c, PURPLE_LT, smoothstep(0.45, 1.0, ridge) * smoothstep(0.15, 0.7, t[m]) * 0.6)
        c = lerp3(c, PURPLE_DK, under.astype(float) * 0.35)
        tipc = sel('tuft_tip', 'tuft_cyan')[m]
        cy = smoothstep(0.50, 0.80, t[m]) * tipc
        c = lerp3(c, lerp3(CYAN, CYAN_LT, smoothstep(0.8, 1.0, t[m])), cy)
        col[m], hgt[m], emi[m] = c * (0.5 + 0.5 * toplight[m])[:, None], 0.3 + 0.5 * ridge, cy
        reg[m] = np.where(cy > 0.5, REG_CYAN, REG_FUR)
    m = sel('tail_tuft')
    if m.any():
        cy = smoothstep(0.35, 0.55, t[m])
        col[m] = lerp3(PURPLE, CYAN, cy)
        emi[m] = cy
        reg[m] = np.where(t[m] > 0.4, REG_CYAN, REG_FUR)

    # harness / ornaments ---------------------------------------------------
    m = sel('rope')
    if m.any():
        twist = 0.5 + 0.5 * np.sin(th[m] + ctx['rope_len'][m] / 0.018 * 2 * np.pi)
        c = lerp3(RED_DK, RED, 0.45 + 0.55 * twist)
        col[m], hgt[m], rough[m], reg[m] = c, twist * 0.6, 0.6, REG_ROPE
    m = sel('knot')
    if m.any():
        tw = 0.5 + 0.5 * np.sin(th[m] * 2 + t[m] * 9)
        col[m], hgt[m], rough[m], reg[m] = lerp3(RED_DK, RED, 0.4 + 0.5 * tw), tw * 0.5, 0.6, REG_ROPE
    m = sel('gem')
    if m.any():
        # t: 0 front pole -> 1 back pole ; painted highlight + rim darkening
        hi = smoothstep(0.16, 0.04, np.hypot(t[m] - 0.20, 0.10 * np.sin(th[m] - 2.3)))
        c = lerp3(np.array([0.92, 0.04, 0.10]), RED_DK, smoothstep(0.25, 0.75, t[m]) * 0.8)
        c = lerp3(c, np.array([1.0, 0.62, 0.66]), hi * 0.7)
        col[m], rough[m], emi[m], reg[m] = c, 0.15, 0.30, REG_ORN
    m = sel('frame')
    if m.any():
        col[m] = lerp3(RED_DK, RED, 0.5 + 0.5 * t[m])
        rough[m], reg[m] = 0.45, REG_ORN
    m = sel('bead')
    if m.any():
        hi = smoothstep(0.30, 0.10, t[m]) * (0.5 + 0.5 * np.cos(th[m] - 1.0))
        col[m] = lerp3(lerp3(RED, RED_DK, t[m] * 0.8), np.array([1.0, 0.6, 0.65]), hi * 0.6)
        rough[m], reg[m], emi[m] = 0.3, REG_ORN, 0.15
    m = sel('tassel')
    if m.any():
        st = 0.5 + 0.5 * np.cos(th[m] * 6)
        col[m] = lerp3(RED_DK, lerp3(RED, RED_GEM, 0.4), 0.45 + 0.55 * st)
        hgt[m], rough[m], reg[m] = st * 0.5, 0.7, REG_ORN
    m = sel('eye')
    if m.any():
        # t: 1 rim -> 0 centre
        c = lerp3(np.array([1.0, 0.45, 0.50]), EYE_RED, smoothstep(0.05, 0.45, t[m]))
        c = lerp3(c, np.array([0.55, 0.0, 0.06]), smoothstep(0.82, 1.0, t[m]) * 0.7)
        col[m], emi[m], rough[m], reg[m] = c, 1.0, 0.2, REG_EYE

    emi = np.clip(emi, 0, 1)
    # slot-classification: fur faces that are mostly cyan move to the cyan slot
    reg = np.where((reg == REG_FUR) & (emi > 0.5), REG_CYAN, reg)
    return np.clip(col, 0, 1), emi, rough, hgt, reg


# ---------------------------------------------------------------- raster
def rasterize(tri_uv, attrs, size):
    """tri_uv: (T,3,2).  attrs: dict name -> (T,3,k) or (T,) per-triangle.
    Returns pixel indices and interpolated attributes."""
    W = H = size
    pix_r, pix_c, out = [], [], {k: [] for k in attrs}
    uvp = tri_uv * np.array([W, H])
    for ti in range(len(tri_uv)):
        (x0, y0), (x1, y1), (x2, y2) = uvp[ti]
        xmin, xmax = int(math.floor(min(x0, x1, x2))) - 1, int(math.ceil(max(x0, x1, x2))) + 1
        ymin, ymax = int(math.floor(min(y0, y1, y2))) - 1, int(math.ceil(max(y0, y1, y2))) + 1
        xmin, ymin = max(xmin, 0), max(ymin, 0)
        xmax, ymax = min(xmax, W - 1), min(ymax, H - 1)
        if xmax < xmin or ymax < ymin:
            continue
        xs, ys = np.meshgrid(np.arange(xmin, xmax + 1) + 0.5, np.arange(ymin, ymax + 1) + 0.5)
        xs, ys = xs.ravel(), ys.ravel()
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        l0 = ((y1 - y2) * (xs - x2) + (x2 - x1) * (ys - y2)) / den
        l1 = ((y2 - y0) * (xs - x2) + (x0 - x2) * (ys - y2)) / den
        l2 = 1 - l0 - l1
        # conservative: accept texels within ~0.7px of the triangle
        area2 = abs(den)
        e = 0.7 * max(math.hypot(x1 - x0, y1 - y0), math.hypot(x2 - x1, y2 - y1), math.hypot(x0 - x2, y0 - y2)) / area2
        tol = min(e, 0.5)
        ok = (l0 >= -tol) & (l1 >= -tol) & (l2 >= -tol)
        if not ok.any():
            continue
        L = np.stack([l0[ok], l1[ok], l2[ok]], 1)
        L = np.clip(L, 0, None)
        L /= L.sum(1, keepdims=True)
        # image row 0 = top = v 1
        pix_c.append(xs[ok].astype(int))
        pix_r.append((H - 1 - ys[ok].astype(int)))
        for k, arr in attrs.items():
            a = arr[ti]
            if a.ndim == 0 or (a.ndim == 1 and arr.ndim == 1):
                out[k].append(np.full(ok.sum(), a))
            elif a.ndim == 1:
                out[k].append(L @ a)
            else:
                out[k].append(L @ a)
    rr = np.concatenate(pix_r)
    cc = np.concatenate(pix_c)
    return rr, cc, {k: np.concatenate(v) for k, v in out.items()}


def dilate(img, filled, iters=12):
    img = img.copy()
    filled = filled.copy()
    H, W = filled.shape
    for _ in range(iters):
        acc = np.zeros_like(img, dtype=float)
        cnt = np.zeros((H, W))
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            sh = np.roll(np.roll(filled, dr, 0), dc, 1)
            si = np.roll(np.roll(img, dr, 0), dc, 1)
            acc += si * (sh[..., None] if img.ndim == 3 else sh)
            cnt += sh
        new = (~filled) & (cnt > 0)
        if not new.any():
            break
        if img.ndim == 3:
            img[new] = acc[new] / cnt[new][:, None]
        else:
            img[new] = acc[new] / cnt[new]
        filled = filled | new
    return img


def height_to_normal(h, filled, strength=2.5):
    hs = h.copy()
    gy, gx = np.gradient(hs)
    # row axis points down (-v); OpenGL normal maps: green = +v
    nx = -gx * strength
    ny = gy * strength
    nz = np.ones_like(hs)
    n = np.stack([nx, ny, nz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    n[~filled] = (0, 0, 1)
    return n * 0.5 + 0.5


def paint_all(tri_uv, tri_t, tri_th, tri_P, tri_N, tri_part, tri_face, tri_ropelen, n_faces, ctx, size=1024):
    attrs = {'t': tri_t, 'th': tri_th, 'P': tri_P, 'N': tri_N, 'part': tri_part.astype(float),
             'face': tri_face.astype(float), 'rl': tri_ropelen}
    rr, cc, A = rasterize(tri_uv, attrs, size)
    Nn = A['N'] / np.maximum(np.linalg.norm(A['N'], axis=1, keepdims=True), 1e-9)
    S = Samples(A['t'], A['th'], A['P'], Nn, np.rint(A['part']).astype(int), np.rint(A['face']).astype(int))
    ctx = dict(ctx)
    ctx['rope_len'] = A['rl']
    col, emi, rough, hgt, reg = paint_samples(S, ctx)
    H = W = size
    img = np.zeros((H, W, 3)); em = np.zeros((H, W)); ro = np.full((H, W), 0.85); hh = np.zeros((H, W))
    filled = np.zeros((H, W), bool)
    img[rr, cc] = col; em[rr, cc] = emi; ro[rr, cc] = rough; hh[rr, cc] = hgt
    filled[rr, cc] = True
    nrm = height_to_normal(hh, filled)
    img = dilate(img, filled); em = dilate(em, filled); ro = dilate(ro, filled)
    nrm = dilate(nrm, filled)
    # per-face region by majority vote of its texels
    face_reg = np.zeros(n_faces, dtype=np.int32)
    votes = np.zeros((n_faces, 6))
    np.add.at(votes, (S.face, reg), 1)
    has = votes.sum(1) > 0
    face_reg[has] = votes[has].argmax(1)
    return img, em, ro, nrm, face_reg, has
