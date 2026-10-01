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
import kitsune_fur as kf

P = PART_IDS

# ---- palette (sRGB), calibrated from k-means clusters of the reference sheet
PURPLE_DK = np.array([0.180, 0.100, 0.480])      # v22: brighter violet, sampled from the in-game model
PURPLE = np.array([0.330, 0.200, 0.670])
PURPLE_LT = np.array([0.550, 0.400, 0.840])
PURPLE_HEAD = np.array([0.400, 0.250, 0.740])
CYAN_DK = np.array([0.070, 0.560, 0.800])
CYAN = np.array([0.090, 0.870, 0.975])
CYAN_LT = np.array([0.470, 0.930, 0.985])
TIP_WHITE = np.array([0.880, 0.990, 1.000])
RED = np.array([0.820, 0.140, 0.230])
RED_DK = np.array([0.420, 0.040, 0.110])
ROPE_RED = np.array([0.880, 0.080, 0.130])
ROPE_LT = np.array([1.000, 0.300, 0.330])
RED_GEM = np.array([1.000, 0.090, 0.160])
EYE_RED = np.array([1.000, 0.060, 0.150])
EYE_IRIS = np.array([1.000, 0.120, 0.290])      # reference: hot pink-red iris
EYE_DEEP = np.array([0.620, 0.000, 0.100])
EYE_CORE = np.array([1.000, 0.400, 0.520])
EYELINER = np.array([0.055, 0.025, 0.130])

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


def soft_in(v, w=0.05):
    """Anti-aliased 'v < 1' (soft edge of relative width w)."""
    return smoothstep(1.0 + w * 0.5, 1.0 - w * 0.5, v)


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
    return 1.0 - smoothstep(0.93, 1.04, best)


def polyline_dist(px, py, pts):
    """Distance from points to an open polyline and the arc-length position of
    the nearest polyline point."""
    pts = np.asarray(pts, float)
    L = np.r_[0.0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    best = np.full(px.shape, 1e9)
    arc = np.zeros(px.shape)
    for i in range(len(pts) - 1):
        d, h = seg_dist(px, py, pts[i, 0], pts[i, 1], pts[i + 1, 0], pts[i + 1, 1])
        m = d < best
        best = np.where(m, d, best)
        arc = np.where(m, L[i] + h * (L[i + 1] - L[i]), arc)
    return best, arc


def eye_signed_dist(u, v, poly):
    """Signed metric distance to the (closed, star-shaped) eye outline: < 0 inside."""
    d, _ = polyline_dist(u, v, np.vstack([poly, poly[:1]]))
    psi = np.arctan2(poly[:, 1], poly[:, 0])
    r = np.hypot(poly[:, 0], poly[:, 1])
    o = np.argsort(psi)
    rr = np.interp(np.arctan2(v, u), psi[o], r[o], period=2 * np.pi)
    return np.where(np.hypot(u, v) < rr, -d, d)


def eye_scale(u, v, poly):
    """Almond-normalised radius: 0 at the eye centre, 1 on the outline."""
    psi = np.arctan2(poly[:, 1], poly[:, 0])
    r = np.hypot(poly[:, 0], poly[:, 1])
    o = np.argsort(psi)
    rr = np.interp(np.arctan2(v, u), psi[o], r[o], period=2 * np.pi)
    return np.hypot(u, v) / np.maximum(rr, 1e-9)


def tri_wave(x):
    """Triangle wave 0..1..0 with period 1."""
    return 1.0 - np.abs(2.0 * (x - np.floor(x)) - 1.0)


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

    X, Y, Z = s.P[:, 0], s.P[:, 1], s.P[:, 2]
    inv_p = {v: k for k, v in P.items()}
    t = s.t
    th = kf.mirror_th(np.array([inv_p[int(q)] for q in s.part]), X, s.th)     # exact left/right mirror
    nz = s.N[:, 2]
    phi = np.arccos(np.clip(np.cos(th), -1, 1))          # 0 dorsal .. pi ventral
    toplight = 0.88 + 0.16 * nz

    # ---------------------------------------------------------- body fur
    def fur(m, part, base=PURPLE, contrast=0.8, th_override=None):
        """Shading of the sculpted fur locks (same field as kitsune_sculpt):
        lit ridge toward each lock tip, dark crevice just past the tip."""
        f = kf.FUR[part]
        a, b = kf.fur_coords(part, t[m], th[m] if th_override is None else th_override)
        hh, ridge, v = kf.lock_field(a, b, f['ca'], f['cb'], f['seed'], **kf.lock_opts(part))
        sh = np.clip(0.35 + 0.55 * np.clip(hh, 0, 1) + 0.15 * ridge, 0, 1)
        sh = 1 - contrast * (1 - sh)
        c = lerp3(PURPLE_DK, base, 0.25 + 0.75 * sh)
        c = lerp3(c, PURPLE_LT, smoothstep(0.55, 0.95, hh * ridge) * 0.55 * contrast)
        crev = smoothstep(0.10, 0.0, v) * contrast
        c = lerp3(c, PURPLE_DK * 0.8, crev * 0.5)
        return c, np.clip(hh, 0, 1)

    # torso -----------------------------------------------------------------
    # metric loft coordinates: ps = 0 (rump) .. 1.25 (chest), pp = 0 (spine) .. 0.94 (belly)
    m = sel('torso')
    if m.any():
        c, h = fur(m, 'torso')
        ps, pp = t[m] * 1.45, phi[m] * 0.25       # ps: 0 rump .. 1.4 chest, pp: 0 spine .. 0.79 belly
        mk = np.zeros(m.sum())
        strokes = [   # clean lightning bolts (correction sheet side panels)
            ([(1.25, 0.50), (1.12, 0.40), (1.02, 0.44), (0.86, 0.34), (0.74, 0.38), (0.58, 0.30)], 0.032),  # flank bolt
            ([(1.22, 0.30), (1.15, 0.22), (1.20, 0.14)], 0.030),                                              # shoulder
            ([(0.36, 0.44), (0.28, 0.34), (0.33, 0.26), (0.25, 0.17)], 0.034),                                # haunch
        ]
        for i, (pts, w) in enumerate(strokes):
            mk = np.maximum(mk, stroke_mask(ps, pp, pts, w, w * 0.45, jag=0.1, seed=i))
        mk = np.maximum(mk, soft_in(np.abs(ps - 0.14) / 0.055 + np.abs(pp) / 0.04))    # rump diamond
        c = lerp3(c, CYAN, mk)
        col[m], hgt[m] = c * toplight[m][:, None], h
        emi[m] = mk
        reg[m] = REG_FUR

    # neck ------------------------------------------------------------------
    m = sel('neck')
    if m.any():
        c, h = fur(m, 'neck')
        hair = kf.neck_hair(t[m], np.cos(th[m]))
        c = lerp3(lerp3(PURPLE_HEAD, PURPLE, 0.35), c, hair)           # smooth top of the neck
        h = h * hair
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
        c, h = fur(m, 'head', base=PURPLE_HEAD, contrast=0.35)
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
        near = smoothstep(0.06, 0.045, np.abs(ww))
        # cyan nose pad (reference / in-game): an inverted rounded triangle on the
        # front of the snout tip -- crisp edge, lighter upper centre, deeper rim
        zr = z - ctx['nose_z']
        hw = 0.039 * np.clip((zr + 0.036) / 0.078, 0, 1) ** 0.50
        nose_in = (x / np.maximum(hw, 1e-4)) ** 2.4 + np.clip((zr - 0.030) / 0.016, 0, None) ** 2
        front_ = smoothstep(ctx['nose_y'] + 0.050, ctx['nose_y'] + 0.038, y)
        nose = smoothstep(1.06, 0.94, nose_in) * (zr > -0.036) * front_
        mk_nose = nose
        # bold forehead diamond + crest diamond (centred)
        topw = smoothstep(0.15, 0.35, nzh)
        mk = np.maximum(mk, soft_in(x / 0.040 + np.abs(y - (ey + 0.080)) / 0.075) * topw)
        mk = np.maximum(mk, soft_in(x / 0.022 + np.abs(y - (ey + 0.175)) / 0.036) * topw)
        # eye frame hugging the seated lens exactly (same outline): thin dark liner,
        # then a bold cyan band (thicker under the eye), pointed wing off the outer corner
        de = eye_signed_dist(u, vv, ctx['eye_poly'])
        s_up = vv / np.maximum(np.hypot(u, vv), 1e-9)
        band = 0.0100 + 0.0060 * smoothstep(0.1, -0.7, s_up)
        liner = smoothstep(0.0042, 0.0030, de) * near
        ring = smoothstep(0.0030, 0.0042, de) * smoothstep(0.0036 + band + 0.0008, 0.0036 + band - 0.0008, de)
        mk = np.maximum(mk, ring * near)
        mk = np.maximum(mk, stroke_mask(u, vv, [(0.056, 0.004), (0.125, 0.022)], 0.014, 0.005, seed=22) * near)
        # bold brow wedge above the eye, rising toward the ear (V toward the forehead)
        mk = np.maximum(mk, stroke_mask(u, vv, [(-0.065, 0.050), (0.025, 0.066), (0.120, 0.096)], 0.018, 0.007, seed=21)
                        * (np.abs(ww) < 0.08))
        # bold mask edge from under the inner eye corner down the muzzle toward the nose
        mk = np.maximum(mk, stroke_mask(u, vv, [(-0.052, -0.026), (-0.122, -0.052), (-0.190, -0.074)], 0.017, 0.007,
                                        seed=23) * (np.abs(ww) < 0.09) * (x > 0.025))
        mk = np.clip(mk, 0, 1) * (1 - liner)
        c = lerp3(c, CYAN, mk)
        c = lerp3(c, EYELINER, liner)
        nc = lerp3(CYAN, CYAN_LT, smoothstep(0.7, 0.1, nose_in) * smoothstep(-0.01, 0.025, zr) * 0.8)
        nc = lerp3(nc, CYAN_DK, smoothstep(0.70, 0.95, nose_in) * 0.6)
        c = lerp3(c, nc, mk_nose)
        mk = np.maximum(mk, mk_nose)
        col[m], hgt[m], emi[m] = c * toplight[m][:, None], h * 0.5, mk

    # ears ------------------------------------------------------------------
    # metric ear coordinates (ctx['ear'], measured on the final mesh; the right
    # ear is the exact mirror): a along the ear, c across it, outline distance
    m = sel('ear')
    if m.any():
        the = np.where(X[m] < 0, np.pi - th[m], th[m])
        c, h = fur(m, 'ear', base=PURPLE_HEAD, contrast=0.45, th_override=the)
        E = ctx['ear']
        Pm = s.P[m] * np.array([1, 1, 1])
        Pm[:, 0] = np.abs(Pm[:, 0])
        Nm = s.N[m].copy()
        Nm[:, 0] *= np.sign(X[m] + 1e-12)
        d = Pm - E['base']
        ea, ec = d @ E['ax'], d @ E['side']
        dist, arc = polyline_dist(ea, ec, E['outline'])
        front = smoothstep(0.15, -0.15, Nm @ E['back'])                # inner (forward-facing) side
        # rim with fur spikes pointing inward / down the ear, wider on the front
        # in-game ears: mostly cyan; a deep-navy pocket set toward the inner edge,
        # a thick cyan band on the outer side, a few bold notches on the inner side,
        # a jagged cyan fringe along the bottom and a solid cyan tip
        outer = smoothstep(E['c_mid'] - 0.01, E['c_mid'] + 0.01, ec)
        rim_w = np.where(front > 0.5, 0.018 + 0.020 * outer, 0.016)
        tip_w = smoothstep(E['a_tip'] - 0.090, E['a_tip'] - 0.040, ea) * 0.05
        rw_ = np.maximum(rim_w, tip_w)
        mk = smoothstep(rw_ + 0.0011, rw_ - 0.0011, dist)

        # inner ear: deep indigo with soft vertical strands
        strands = 0.5 + 0.5 * np.sin(ec / 0.011 + 1.5 * vnoise(ec * 40, ea * 8, 4))
        inner = front * smoothstep(0.0, 0.004, dist - rw_) * (1 - mk)
        # v22: inner ear keeps the body's purple (in-game look)
        cy_col = lerp3(CYAN, CYAN_LT, smoothstep(E['a_tip'] - 0.10, E['a_tip'], ea))
        c = lerp3(c, cy_col, mk)
        col[m], hgt[m], emi[m] = c, np.where(mk > 0.5, 0.3, h), mk

    # legs ------------------------------------------------------------------
    for part, L, tb, seed in (('leg_f', 0.80, 0.53, 5), ('leg_h', 0.90, 0.50, 6)):
        m = sel(part)
        if not m.any():
            continue
        c, h = fur(m, part)
        # cyan flames licking up into the purple (in-game legs): a few tall, curved,
        # pointed tongues of different heights leaning around the leg
        k = 4
        xf = th[m] * k / (2 * np.pi) + 0.9 * (tb - t[m]) + 0.15 * vnoise(th[m] * 2, t[m] * 3, seed)
        idx = np.floor(xf)
        ph = xf - idx
        tongue = (1 - np.abs(2 * ph - 1)) ** 2.4
        small = (1 - np.minimum(1, np.abs(2 * ((ph + 0.5) % 1.0) - 1) * 1.0)) ** 6      # little flame between
        flame_h = 0.13 + 0.09 * _hash2(idx, 3.0, seed)
        bound = tb + 0.04 - flame_h * tongue - 0.05 * small
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
            dia = np.maximum(dia, soft_in(np.abs(tt - tc) / 0.035 + da / 0.25))
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
        c = lerp3(c, PURPLE_DK, under.astype(float) * 0.05)
        tipc = sel('tuft_tip', 'tuft_cyan')[m]
        cy = smoothstep(0.50, 0.80, t[m]) * tipc
        c = lerp3(c, lerp3(CYAN, CYAN_LT, smoothstep(0.8, 1.0, t[m])), cy)
        col[m], hgt[m], emi[m] = c * (0.5 + 0.5 * toplight[m])[:, None], 0.3 + 0.5 * ridge, cy
        reg[m] = np.where(cy > 0.5, REG_CYAN, REG_FUR)
    m = sel('tuft_cheek')
    if m.any():
        # cheek ruff (reference close-ups): cyan flames licking down into purple
        # roots, serrated edges, streaked, bright white-cyan tips.
        # t: 0 root -> 1 tip ; w = sin(th): -1..1 across the flattened lock
        tt = t[m]
        w = np.sin(th[m])
        aw = np.abs(w)
        # clean, crisp bands (no noise): purple root -> deep-cyan base -> cyan
        # body with a light centre stripe and darker edges -> white-cyan tip
        # purple root -> cyan flame tongues licking toward the tip (like the legs)
        xf = th[m] * 3 / (2 * np.pi) + 0.4 * tt
        tongue = (1 - np.abs(2 * (xf - np.floor(xf)) - 1)) ** 2.2
        bound = 0.52 - 0.18 * tongue
        cy = smoothstep(bound - 0.015, bound + 0.015, tt)
        cc = lerp3(CYAN, CYAN, smoothstep(0.20, 0.34, tt))
        stripe = smoothstep(0.34, 0.27, aw) * smoothstep(0.30, 0.40, tt)
        cc = lerp3(cc, CYAN_LT, stripe * 0.85)
        cc = lerp3(cc, CYAN_DK, smoothstep(0.80, 0.86, aw) * 0.6)
        cc = lerp3(cc, TIP_WHITE, smoothstep(0.78, 0.92, tt))
        # root = exactly the cheek's own purple and lighting (the cheek is sculpted up
        # into the tuft, so there must be no colour / shading step at the join)
        cheek_col = lerp3(PURPLE_DK, PURPLE_HEAD, 0.90)
        c = lerp3(cheek_col, cc, cy)
        col[m] = c * lerp3(toplight[m][:, None] * np.ones(3), (0.80 + 0.20 * toplight[m])[:, None] * np.ones(3), cy)
        hgt[m] = np.where(cy > 0.5, 0.3 + 0.4 * (1 - aw), 0.20) * smoothstep(0.0, 0.25, tt)
        emi[m] = cy
        reg[m] = np.where(cy > 0.5, REG_CYAN, REG_FUR)
    m = sel('mane')
    if m.any():
        # nape mane: purple flame locks, dark roots, lighter ridge, lit tips
        tt, aw = t[m], np.abs(np.sin(th[m]))
        c = lerp3(PURPLE_DK, PURPLE, smoothstep(0.05, 0.35, tt))
        c = lerp3(c, PURPLE_LT, smoothstep(0.40, 0.0, aw) * smoothstep(0.25, 0.55, tt) * 0.6)
        c = lerp3(c, PURPLE_DK, smoothstep(0.78, 0.92, aw) * 0.5)
        c = lerp3(c, PURPLE_LT, smoothstep(0.80, 1.0, tt) * 0.5)
        col[m], hgt[m], emi[m], reg[m] = c * toplight[m][:, None], 0.3 + 0.4 * (1 - aw), 0.0, REG_FUR
    m = sel('ear_fur')
    if m.any():
        # sculpted ear fur: cyan locks, slightly deeper at the root, white-cyan tips
        tt, aw = t[m], np.abs(np.sin(th[m]))
        streak = 0.5 + 0.5 * np.sin(np.sin(th[m]) * 12 + tt * 3 + 1.2 * vnoise(th[m] * 2, tt * 6, 33))
        c = lerp3(CYAN_DK, CYAN, smoothstep(0.0, 0.35, tt))
        c = lerp3(c, CYAN_LT, smoothstep(0.50, 0.85, tt))
        c = lerp3(c, TIP_WHITE, smoothstep(0.84, 1.0, tt))
        c = lerp3(c, CYAN_DK, smoothstep(0.70, 0.95, aw) * 0.45)
        c = lerp3(c * 0.90, c, 0.40 + 0.60 * streak)
        col[m], hgt[m], emi[m], reg[m] = c, 0.3 + 0.4 * (1 - aw) * streak, 1.0, REG_CYAN
    m = sel('tail_tuft')
    if m.any():
        cy = smoothstep(0.35, 0.55, t[m])
        col[m] = lerp3(PURPLE, CYAN, cy)
        emi[m] = cy
        reg[m] = np.where(t[m] > 0.4, REG_CYAN, REG_FUR)

    # harness / ornaments ---------------------------------------------------
    m = sel('rope')
    if m.any():
        # stylised rope (reference): smooth glossy bright red with soft mottling and
        # a few long darker-red streaks winding slowly around it
        L, a = ctx['rope_len'][m], th[m]
        wind = 0.5 + 0.5 * np.sin(a + L / 0.16 * 2 * np.pi + 0.8 * vnoise(L * 9, a, 51))
        streak = smoothstep(0.80, 0.93, wind)
        mott = vnoise(L * 22, a * 1.6, 52)
        c = lerp3(ROPE_RED, ROPE_LT, smoothstep(0.55, 0.95, mott) * 0.35)
        c = lerp3(c, RED_DK, streak * 0.75 + smoothstep(0.35, 0.05, mott) * 0.25)
        col[m], hgt[m], rough[m], reg[m] = c, streak * 0.3, 0.82, REG_ROPE
    m = sel('knot')
    if m.any():
        tw = smoothstep(0.75, 0.92, 0.5 + 0.5 * np.sin(th[m] * 2 + t[m] * 7))
        col[m], hgt[m], rough[m], reg[m] = lerp3(ROPE_RED, RED_DK, tw * 0.7), tw * 0.3, 0.82, REG_ROPE
    m = sel('gem')
    if m.any():
        # t: 0 front pole -> 1 back pole ; painted highlight + rim darkening
        hi = smoothstep(0.16, 0.04, np.hypot(t[m] - 0.20, 0.10 * np.sin(th[m] - 2.3)))
        c = lerp3(np.array([0.92, 0.04, 0.10]), RED_DK, smoothstep(0.25, 0.75, t[m]) * 0.8)
        c = lerp3(c, np.array([1.0, 0.62, 0.66]), hi * 0.7)
        col[m], rough[m], emi[m], reg[m] = c, 0.45, 0.30, REG_ORN
    m = sel('frame')
    if m.any():
        col[m] = lerp3(RED_DK, RED, 0.5 + 0.5 * t[m])
        rough[m], reg[m] = 0.78, REG_ORN
    m = sel('bead')
    if m.any():
        hi = smoothstep(0.30, 0.10, t[m]) * (0.5 + 0.5 * np.cos(th[m] - 1.0))
        col[m] = lerp3(lerp3(RED, RED_DK, t[m] * 0.8), np.array([1.0, 0.6, 0.65]), hi * 0.6)
        rough[m], reg[m], emi[m] = 0.70, REG_ORN, 0.15
    m = sel('tassel')
    if m.any():
        st = 0.5 + 0.5 * np.cos(th[m] * 6)
        col[m] = lerp3(RED_DK, lerp3(RED, RED_GEM, 0.4), 0.45 + 0.55 * st)
        hgt[m], rough[m], reg[m] = st * 0.5, 0.85, REG_ORN
    m = sel('eye')
    if m.any():
        # exact eye-frame coordinates of the lens surface (u along the eye toward
        # the outer corner, v across / up); the right eye is the mirror image
        Pm = s.P[m].copy()
        Pm[:, 0] = np.abs(Pm[:, 0])
        de_ = Pm - ctx['eye_center']
        u, v = de_ @ ctx['eye_along'], de_ @ ctx['eye_acr']
        tt = eye_scale(u, v, ctx['eye_poly'])          # 0 centre -> 1 outline (-> 1.07 buried skirt)
        a = np.arctan2(v / 0.022, u / 0.056)
        # glowing pink-red iris (reference close-up): lighter upper half, deeper red
        # toward the lid line, faint radial fibres
        fib = 0.5 + 0.5 * np.sin(a * 23 + 2.0 * vnoise(a * 3, tt * 5, 17))
        c = lerp3(EYE_IRIS, EYE_CORE, smoothstep(-0.004, 0.016, v) * smoothstep(0.85, 0.3, tt) * 0.55)
        c = lerp3(c, EYE_DEEP, smoothstep(0.66, 0.93, tt) * (0.55 + 0.45 * smoothstep(0.004, -0.012, v)))
        c = lerp3(c * 0.88, c, 0.45 + 0.55 * fib)
        # pink-white catch-light (upper, toward the outer corner), dark lid-line rim
        glint = smoothstep(0.0070, 0.0042, np.hypot((u - 0.010) * 0.9, v - 0.008))
        c = lerp3(c, np.array([1.0, 0.93, 0.93]), glint)
        rim = smoothstep(0.93, 0.995, tt)
        c = lerp3(c, EYELINER, rim)
        col[m], rough[m], reg[m] = c, 0.22, REG_EYE
        emi[m] = np.clip((1.0 - rim) + glint, 0, 1)

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


def paint_all(tri_uv, tri_t, tri_th, tri_P, tri_N, tri_part, tri_face, tri_ropelen, n_faces, ctx, size=1024, ss=2,
              chunk=1_500_000):
    """Paint at size*ss (supersampled), in chunks, then box-filter down to size
    (coverage weighted) and dilate: smooth, anti-aliased texture edges."""
    attrs = {'t': tri_t, 'th': tri_th, 'P': tri_P, 'N': tri_N, 'part': tri_part.astype(float),
             'face': tri_face.astype(float), 'rl': tri_ropelen}
    HS = size * ss
    rr, cc, A = rasterize(tri_uv, attrs, HS)
    n = len(rr)
    col = np.zeros((n, 3)); emi = np.zeros(n); rough = np.zeros(n); hgt = np.zeros(n)
    reg = np.zeros(n, dtype=np.int32)
    faces = np.rint(A['face']).astype(int)
    for s0 in range(0, n, chunk):
        sl = slice(s0, min(n, s0 + chunk))
        Nn = A['N'][sl] / np.maximum(np.linalg.norm(A['N'][sl], axis=1, keepdims=True), 1e-9)
        S = Samples(A['t'][sl], A['th'][sl], A['P'][sl], Nn, np.rint(A['part'][sl]).astype(int), faces[sl])
        c2 = dict(ctx)
        c2['rope_len'] = A['rl'][sl]
        col[sl], emi[sl], rough[sl], hgt[sl], reg[sl] = paint_samples(S, c2)
    img = np.zeros((HS, HS, 3)); em = np.zeros((HS, HS)); ro = np.zeros((HS, HS)); hh = np.zeros((HS, HS))
    filled = np.zeros((HS, HS), bool)
    img[rr, cc] = col; em[rr, cc] = emi; ro[rr, cc] = rough; hh[rr, cc] = hgt
    filled[rr, cc] = True
    nrm_hi = height_to_normal(hh, filled, strength=2.5 * ss) - 0.5

    def down(a):
        """coverage-weighted ss x ss box filter"""
        f = filled.astype(float)
        if a.ndim == 3:
            num = (a * f[..., None]).reshape(size, ss, size, ss, a.shape[2]).sum((1, 3))
        else:
            num = (a * f).reshape(size, ss, size, ss).sum((1, 3))
        den = f.reshape(size, ss, size, ss).sum((1, 3))
        out = num / np.maximum(den, 1e-9)[..., None] if a.ndim == 3 else num / np.maximum(den, 1e-9)
        return out, den > 0
    img, filled_lo = down(img)
    em, _ = down(em)
    ro, _ = down(ro)
    nrm, _ = down(nrm_hi)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-9)
    nrm = nrm * 0.5 + 0.5
    ro[~filled_lo] = 0.85
    img = dilate(img, filled_lo); em = dilate(em, filled_lo); ro = dilate(ro, filled_lo)
    nrm = dilate(nrm, filled_lo)
    face_reg = np.zeros(n_faces, dtype=np.int32)
    votes = np.zeros((n_faces, 6))
    np.add.at(votes, (faces, reg), 1)
    has = votes.sum(1) > 0
    face_reg[has] = votes[has].argmax(1)
    return img, em, ro, nrm, face_reg, has
