"""
Kitsune geometry builder (pure numpy, no bpy).

Builds the whole creature as one low-poly mesh from parametric lofts, fur
clumps, rope tubes and small ornaments.  Every face carries:
  * a part id (used by the texture painter and material-slot assignment)
  * an island id (one UV island per loft / clump / rope)
  * per-corner UVs (pre-pack, roughly proportional to world size)
  * per-corner loft parameters  t (0..1 along the part) and th (angle around)
Every vertex carries skin weights {bone_name: weight}.

Coordinate system (Blender): Z up, the creature faces -Y, its left side is +X.
Units: "shoulder height = 1.0".  build_kitsune.py multiplies by WORLD_SCALE.
"""
import math
import numpy as np

TAU = 2.0 * math.pi

PART_IDS = {
    'torso': 0, 'neck': 1, 'head': 2, 'ear': 3, 'leg_f': 4, 'leg_h': 5,
    'paw': 6, 'claw': 7, 'tail': 8, 'tuft': 9, 'tuft_cyan': 10, 'spike': 11,
    'tail_tuft': 12, 'rope': 13, 'knot': 14, 'gem': 15, 'frame': 16,
    'bead': 17, 'tassel': 18, 'eye': 19, 'tuft_tip': 20, 'tuft_cheek': 21, 'ear_fur': 22, 'mane': 23,
}


def v3(x, y, z):
    return np.array([x, y, z], dtype=float)


def norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def mirror_w(w, sx):
    """Map *_L bone names to *_R for mirrored (sx < 0) parts."""
    if sx > 0:
        return dict(w)
    return {(k[:-2] + '_R' if k.endswith('_L') else k): v for k, v in w.items()}


def blend_chain(s, joints):
    """joints: list of (s_position, bone).  Linear blend between neighbours."""
    if s <= joints[0][0]:
        return {joints[0][1]: 1.0}
    for (s0, b0), (s1, b1) in zip(joints, joints[1:]):
        if s <= s1:
            f = (s - s0) / max(s1 - s0, 1e-9)
            if b0 == b1:
                return {b0: 1.0}
            return {b0: 1.0 - f, b1: f}
    return {joints[-1][1]: 1.0}


class MeshData:
    def __init__(self):
        self.verts = []        # np.array(3)
        self.weights = []      # dict per vertex
        self.faces = []        # list of vertex index lists
        self.face_uv = []      # list of [(u,v)...]
        self.face_at = []      # list of [(t,th)...]
        self.face_part = []
        self.face_island = []
        self.island_parts = {}
        self._island = -1
        self.hug = []          # accessory pieces to seat onto the sculpted surface

    # ------------------------------------------------------------------ basics
    def new_island(self, part):
        self._island += 1
        self.island_parts[self._island] = part
        return self._island

    def add_vert(self, p, w):
        self.verts.append(np.asarray(p, dtype=float))
        self.weights.append(dict(w))
        return len(self.verts) - 1

    def add_face(self, vids, uvs, ats, part, island):
        self.faces.append(list(vids))
        self.face_uv.append(list(uvs))
        self.face_at.append(list(ats))
        self.face_part.append(PART_IDS[part])
        self.face_island.append(island)

    def orient_piece(self, first_face, inside_point=None):
        """Flip every face of a piece (faces[first_face:]) so normals point
        away from inside_point (defaults to the piece's vertex centroid)."""
        idx = range(first_face, len(self.faces))
        vids = sorted({v for i in idx for v in self.faces[i]})
        c = np.mean([self.verts[v] for v in vids], axis=0) if inside_point is None else inside_point
        score = 0.0
        for i in idx:
            pts = [self.verts[v] for v in self.faces[i]]
            n = np.zeros(3)
            for a, b in zip(pts, pts[1:] + pts[:1]):
                n += np.cross(a, b)
            fc = np.mean(pts, axis=0)
            score += np.dot(n, fc - c)
        if score < 0:
            for i in idx:
                self.faces[i].reverse()
                self.face_uv[i].reverse()
                self.face_at[i].reverse()

    def tri_count(self):
        return sum(len(f) - 2 for f in self.faces)


# ---------------------------------------------------------------------- lofts
class Loft:
    """Generalised cylinder through ring centres with elliptical sections.

    th = 0 is the 'up' side of the ring (dorsal for the torso), th = pi/2 the
    'side' axis.  Ring vertex k sits at th = pi + TAU*k/n so the UV seam runs
    along the underside (least visible).
    """

    def __init__(self, centers, rw, rt, rb, ref, n, sx=1.0, bulge=None):
        self.c = [np.asarray(c, float) for c in centers]
        self.rw, self.rt, self.rb = list(rw), list(rt), list(rb)
        self.n = n
        self.bulge = bulge
        R = len(self.c)
        self.T, self.side, self.up = [], [], []
        for i in range(R):
            a = self.c[max(i - 1, 0)]
            b = self.c[min(i + 1, R - 1)]
            T = norm(b - a)
            r = np.asarray(ref(i) if callable(ref) else ref, float)
            s = norm(r - np.dot(r, T) * T)
            u = norm(np.cross(T, s))
            if sx < 0:            # keep 'up' consistent on mirrored parts
                pass
            self.T.append(T)
            self.side.append(s)
            self.up.append(u)
        # arc length
        L = [0.0]
        for a, b in zip(self.c, self.c[1:]):
            L.append(L[-1] + np.linalg.norm(b - a))
        self.arc = np.array(L)
        self.length = L[-1]

    def ring_point(self, i, th):
        rv = self.rt[i] if math.cos(th) >= 0 else self.rb[i]
        m = 1.0 + (self.bulge(i, th) if self.bulge else 0.0)
        return (self.c[i] + self.side[i] * self.rw[i] * math.sin(th) * m
                + self.up[i] * rv * math.cos(th) * m)

    def _interp(self, s):
        x = s * (len(self.c) - 1)
        i = int(min(max(math.floor(x), 0), len(self.c) - 2))
        f = x - i
        return i, f

    def point(self, s, th, offset=0.0):
        """Surface point + outward normal at loft param s (0..1), angle th."""
        i, f = self._interp(s)
        lerp = lambda a, b: a * (1 - f) + b * f
        c = lerp(self.c[i], self.c[i + 1])
        side = norm(lerp(self.side[i], self.side[i + 1]))
        up = norm(lerp(self.up[i], self.up[i + 1]))
        T = norm(lerp(self.T[i], self.T[i + 1]))
        rw = lerp(self.rw[i], self.rw[i + 1])
        rv = lerp(self.rt[i], self.rt[i + 1]) if math.cos(th) >= 0 else lerp(self.rb[i], self.rb[i + 1])
        p = c + side * rw * math.sin(th) + up * rv * math.cos(th)
        nrm = norm(side * math.sin(th) / max(rw, 1e-6) + up * math.cos(th) / max(rv, 1e-6))
        return p + nrm * offset, nrm, T

    def build(self, md, part, weight_fn, cap_start=None, cap_end=None, t_range=(0.0, 1.0), cap_end_t=None):
        """cap_start / cap_end: None (open) or a pole position.  cap_end_t: loft t
        of the end pole (defaults to the last ring's t)."""
        isl = md.new_island(part)
        first = len(md.faces)
        n, R = self.n, len(self.c)
        t0, t1 = t_range
        tt = [t0 + (t1 - t0) * a / max(self.length, 1e-9) for a in self.arc]
        circ = np.mean([math.pi * (self.rw[i] + 0.5 * (self.rt[i] + self.rb[i])) for i in range(R)])
        rings = []
        for i in range(R):
            ring = []
            for k in range(n):
                th = math.pi + TAU * k / n
                p = self.ring_point(i, th)
                ring.append(md.add_vert(p, weight_fn(i, tt[i], p)))
            rings.append(ring)
        uvs = lambda i, k: (circ * k / n, self.arc[i])
        ths = lambda k: math.pi + TAU * k / n
        for i in range(R - 1):
            for k in range(n):
                k2 = k + 1
                vids = [rings[i][k], rings[i][k2 % n], rings[i + 1][k2 % n], rings[i + 1][k]]
                md.add_face(vids,
                            [uvs(i, k), uvs(i, k2), uvs(i + 1, k2), uvs(i + 1, k)],
                            [(tt[i], ths(k)), (tt[i], ths(k2)), (tt[i + 1], ths(k2)), (tt[i + 1], ths(k))],
                            part, isl)
        for cap, i, sgn, tcap in ((cap_start, 0, -1, t0), (cap_end, R - 1, 1, t1 if cap_end_t is None else cap_end_t)):
            if cap is None:
                continue
            capv = md.add_vert(cap, weight_fn(i, tcap, np.asarray(cap)))
            dv = np.linalg.norm(np.asarray(cap) - self.c[i]) * sgn
            for k in range(n):
                k2 = k + 1
                md.add_face([rings[i][k], rings[i][k2 % n], capv],
                            [uvs(i, k), uvs(i, k2), (circ * (k + 0.5) / n, self.arc[i] + dv)],
                            [(tt[i], ths(k)), (tt[i], ths(k2)), (tcap, ths(k + 0.5))],
                            part, isl)
        md.orient_piece(first)
        return rings


def build_tube(md, part, pts, radius, n, weight_fn, closed=False, radii=None, cap_ends=False, ref=None):
    """Rope / string tube through pts."""
    pts = [np.asarray(p, float) for p in pts]
    P = len(pts)
    v_start = len(md.verts)
    isl = md.new_island(part)
    first = len(md.faces)
    Ts = []
    for i in range(P):
        if closed:
            a, b = pts[(i - 1) % P], pts[(i + 1) % P]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, P - 1)]
        Ts.append(norm(b - a))
    # parallel transport frames
    r0 = np.asarray(ref if ref is not None else v3(0, 0, 1), float)
    if abs(np.dot(r0, Ts[0])) > 0.9:
        r0 = v3(1, 0, 0)
    side = norm(r0 - np.dot(r0, Ts[0]) * Ts[0])
    sides = []
    for i in range(P):
        side = norm(side - np.dot(side, Ts[i]) * Ts[i])
        sides.append(side)
    L = [0.0]
    for i in range(1, P):
        L.append(L[-1] + np.linalg.norm(pts[i] - pts[i - 1]))
    if closed:
        L.append(L[-1] + np.linalg.norm(pts[0] - pts[-1]))
    tot = L[-1]
    rings = []
    for i in range(P):
        s, T = sides[i], Ts[i]
        u = np.cross(T, s)
        r = radii[i] if radii is not None else radius
        ring = []
        for k in range(n):
            a = TAU * k / n
            p = pts[i] + (s * math.cos(a) + u * math.sin(a)) * r
            ring.append(md.add_vert(p, weight_fn(i, L[i] / tot, p)))
        rings.append(ring)
    circ = TAU * radius
    segs = P if closed else P - 1
    for i in range(segs):
        j = (i + 1) % P
        vi, vj = L[i], L[i + 1]
        for k in range(n):
            k2 = k + 1
            md.add_face([rings[i][k], rings[i][k2 % n], rings[j][k2 % n], rings[j][k]],
                        [(circ * k / n, vi), (circ * k2 / n, vi), (circ * k2 / n, vj), (circ * k / n, vj)],
                        [(vi / tot, TAU * k / n), (vi / tot, TAU * k2 / n), (vj / tot, TAU * k2 / n), (vj / tot, TAU * k / n)],
                        part, isl)
    if cap_ends and not closed:
        for i, sgn in ((0, -1), (P - 1, 1)):
            c = md.add_vert(pts[i] + Ts[i] * sgn * radius * 0.6, weight_fn(i, L[i] / tot, pts[i]))
            for k in range(n):
                k2 = k + 1
                md.add_face([rings[i][k], rings[i][k2 % n], c],
                            [(circ * k / n, L[i]), (circ * k2 / n, L[i]), (circ * (k + .5) / n, L[i] + sgn * radius)],
                            [(L[i] / tot, TAU * k / n), (L[i] / tot, TAU * k2 / n), (L[i] / tot, 0.0)], part, isl)
    # orient: outward from local ring centres (works for any tube shape)
    score = 0.0
    for fi in range(first, len(md.faces)):
        vs = [md.verts[v] for v in md.faces[fi]]
        nrm = np.cross(vs[1] - vs[0], vs[2] - vs[0])
        fc = np.mean(vs, axis=0)
        near = min(pts, key=lambda q: np.linalg.norm(q - fc))
        score += np.dot(nrm, fc - near)
    if score < 0:
        for fi in range(first, len(md.faces)):
            md.faces[fi].reverse(); md.face_uv[fi].reverse(); md.face_at[fi].reverse()
    return dict(rings=rings, pts=pts, v0=v_start, v1=len(md.verts), radius=radius, closed=closed)


def build_sphere(md, part, center, radii, seg, rings, weight, axis_up=None, axis_side=None):
    """Low-poly ellipsoid (UV sphere) with poles along axis_up."""
    c = np.asarray(center, float)
    up = norm(np.asarray(axis_up if axis_up is not None else v3(0, 0, 1), float))
    sd = np.asarray(axis_side if axis_side is not None else v3(1, 0, 0), float)
    sd = norm(sd - np.dot(sd, up) * up)
    fw = np.cross(up, sd)
    rx, ry, rz = radii
    isl = md.new_island(part)
    first = len(md.faces)
    top = md.add_vert(c + up * rz, weight)
    bot = md.add_vert(c - up * rz, weight)
    grid = []
    for j in range(1, rings):
        phi = math.pi * j / rings
        row = []
        for k in range(seg):
            a = TAU * k / seg
            p = c + up * rz * math.cos(phi) + (sd * rx * math.cos(a) + fw * ry * math.sin(a)) * math.sin(phi)
            row.append(md.add_vert(p, weight))
        grid.append(row)
    uv = lambda j, k: (k / seg, 1 - j / rings)
    at = lambda j, k: (j / rings, TAU * k / seg)
    for k in range(seg):
        k2 = k + 1
        md.add_face([top, grid[0][k], grid[0][k2 % seg]], [(k / seg + .5 / seg, 1), uv(1, k), uv(1, k2)],
                    [(0, TAU * k / seg), at(1, k), at(1, k2)], part, isl)
        md.add_face([bot, grid[-1][k2 % seg], grid[-1][k]], [(k / seg + .5 / seg, 0), uv(rings - 1, k2), uv(rings - 1, k)],
                    [(1, TAU * k / seg), at(rings - 1, k2), at(rings - 1, k)], part, isl)
        for j in range(rings - 2):
            md.add_face([grid[j][k], grid[j + 1][k], grid[j + 1][k2 % seg], grid[j][k2 % seg]],
                        [uv(j + 1, k), uv(j + 2, k), uv(j + 2, k2), uv(j + 1, k2)],
                        [at(j + 1, k), at(j + 2, k), at(j + 2, k2), at(j + 1, k2)], part, isl)
    md.orient_piece(first, c)


def build_clump(md, part, root, nrm, flow, length, width, weight, lift=0.45, thick=0.45, sink=0.02, bend=0.0):
    """Chunky fur clump: 4-sided spike with its base sunk into the host."""
    nrm = norm(nrm)
    flow = norm(flow - np.dot(flow, nrm) * nrm)
    side = norm(np.cross(flow, nrm))
    base = root - nrm * sink - flow * width * 0.3
    apex = root + flow * length * math.cos(lift) + nrm * length * math.sin(lift)
    mid = root + flow * length * 0.5 * math.cos(lift) + nrm * (length * 0.5 * math.sin(lift) + width * thick * 0.6 + bend)
    b = [base + side * width * 0.5,
         base + nrm * (width * thick + sink),
         base - side * width * 0.5,
         base - nrm * width * 0.25]
    isl = md.new_island(part)
    first = len(md.faces)
    vb = [md.add_vert(p, weight) for p in b]
    vm = md.add_vert(mid, weight)
    va = md.add_vert(apex, weight)
    # upper faces go through the raised mid point (ridge) for a chunkier read
    us = [0.0, 0.3, 0.6, 0.8, 1.0]
    md.add_face([vb[0], vb[1], vm], [(0, 0), (.3, 0), (.2, .5)], [(0, 0), (0, 1.6), (.5, 1.2)], part, isl)
    md.add_face([vb[1], vb[2], vm], [(.3, 0), (.6, 0), (.4, .5)], [(0, 1.6), (0, 3.1), (.5, 2.0)], part, isl)
    md.add_face([vb[0], vm, va], [(0, 0), (.2, .5), (.3, 1)], [(0, 0), (.5, 1.2), (1, 1.6)], part, isl)
    md.add_face([vm, vb[2], va], [(.4, .5), (.6, 0), (.3, 1)], [(.5, 2.0), (0, 3.1), (1, 1.6)], part, isl)
    md.add_face([vb[2], vb[3], va], [(.6, 0), (.8, 0), (.7, 1)], [(0, 3.1), (0, 4.7), (1, 4.7)], part, isl)
    md.add_face([vb[3], vb[0], va], [(.8, 0), (1.0, 0), (.9, 1)], [(0, 4.7), (0, 6.28), (1, 4.7)], part, isl)
    md.orient_piece(first, root - nrm * width)


def build_cone(md, part, base_c, tip, radius, n, weight, ref=None):
    base_c, tip = np.asarray(base_c, float), np.asarray(tip, float)
    ax = norm(tip - base_c)
    r0 = np.asarray(ref if ref is not None else v3(0, 0, 1), float)
    if abs(np.dot(r0, ax)) > 0.9:
        r0 = v3(1, 0, 0)
    s = norm(r0 - np.dot(r0, ax) * ax)
    u = np.cross(ax, s)
    isl = md.new_island(part)
    first = len(md.faces)
    ring = [md.add_vert(base_c + (s * math.cos(TAU * k / n) + u * math.sin(TAU * k / n)) * radius, weight) for k in range(n)]
    tv = md.add_vert(tip, weight)
    for k in range(n):
        k2 = (k + 1) % n
        md.add_face([ring[k], ring[k2], tv], [(k / n, 0), ((k + 1) / n, 0), ((k + .5) / n, 1)],
                    [(0, TAU * k / n), (0, TAU * (k + 1) / n), (1, TAU * (k + .5) / n)], part, isl)
    md.orient_piece(first, base_c)


# ==================================================================== creature
# v2: every dimension below is measured from the reference sheet
# (side view = heights / lengths, front + back views = widths, top view = fan
# spread).  Unit = shoulder (withers) height.  See reference_manifest.json.
def bezier(p0, p1, p2, p3, t):
    a = 1 - t
    return a**3 * p0 + 3 * a * a * t * p1 + 3 * a * t * t * p2 + t**3 * p3


TAIL_BASE_DESIGN = v3(0, 0.55, 0.95)    # tail fan was fitted around this root (v2)
TAIL_BASE = v3(0, 0.62, 0.95)           # v15: fan follows the shorter, perked-up rump (shape unchanged)
# (name, tip position, max radius, bow)  -- tips measured from side/front/back views
TAIL_SPECS = [
    ('Tail1', v3(0.00, 1.18, 1.50), 0.28, 0.20),    # top centre
    ('Tail2', v3(0.66, 1.58, 1.36), 0.30, 0.22),    # upper left
    ('Tail3', v3(-0.66, 1.58, 1.36), 0.30, 0.22),   # upper right
    ('Tail4', v3(1.05, 1.55, 0.98), 0.31, 0.22),    # mid left
    ('Tail5', v3(-1.05, 1.55, 0.98), 0.31, 0.22),   # mid right
    ('Tail6', v3(1.00, 1.48, 0.20), 0.32, 0.20),    # lower left
    ('Tail7', v3(-1.00, 1.48, 0.20), 0.32, 0.20),   # lower right
    ('Tail8', v3(0.00, 1.10, 0.16), 0.33, 0.10),    # hangs down over the rump
]
# silhouette-fit tunables (solved by fit_silhouettes.py --optimize against the sheet)
TAIL_TUNE = dict(lat=1.08, back=1.05, dz_top=0.10, dz_mid=-0.20, dz_low=-0.15, rs=0.96)


def tuned_specs():
    T = TAIL_TUNE
    out = []
    for name, tip, rmax, bow in TAIL_SPECS:
        tip = tip.copy()
        tip[0] *= T['lat']
        tip[1] = TAIL_BASE_DESIGN[1] + (tip[1] - TAIL_BASE_DESIGN[1]) * T['back']
        grp = 'top' if name in ('Tail1', 'Tail2', 'Tail3') else ('mid' if name in ('Tail4', 'Tail5') else 'low')
        tip[2] += T['dz_' + grp]
        tip = TAIL_BASE + (tip - TAIL_BASE_DESIGN)
        out.append((name, tip, rmax * T['rs'], bow))
    return out


TAIL_T = [0.0, 0.07, 0.15, 0.25, 0.36, 0.47, 0.58, 0.68, 0.77, 0.85, 0.92, 0.97]


def tail_frame(spec):
    name, tip, rmax, bow = spec
    d = norm(tip - TAIL_BASE)
    broad = norm(np.cross(d, v3(0, 1, 0)))
    if np.linalg.norm(np.cross(d, v3(0, 1, 0))) < 1e-3:
        broad = v3(1, 0, 0)
    # 'lift' = the in-fan direction pointing away from the fan centre (flame hook)
    out = tip - TAIL_BASE
    out = norm(v3(out[0], 0, out[2] - 0.35)) if abs(out[0]) > 0.05 or out[2] > 0.5 else v3(0, 0, -1)
    return d, broad, out


def tail_curve(spec):
    name, tip, rmax, bow = spec
    d, broad, out = tail_frame(spec)
    L = np.linalg.norm(tip - TAIL_BASE)
    up = v3(0, 0, 1)
    # leaves the rump going back/up, bows away from the fan centre, tip hooks up
    p0 = TAIL_BASE - d * 0.04
    p1 = TAIL_BASE + norm(v3(0, 1.0, 0.45) * 0.6 + d) * 0.38 * L
    p2 = TAIL_BASE + d * 0.72 * L + out * bow * L - up * 0.10 * L * (1 if tip[2] > 0.6 else 0)
    p3 = tip
    return (p0, p1, p2, p3), broad, d


def tail_radius(t, rmax):
    # leaf / flame: slim root, full belly at ~48%, long pointed tip
    if t <= 0.48:
        return rmax * (0.22 + 0.78 * math.sin(0.5 * math.pi * t / 0.48) ** 0.9)
    return rmax * max(((1.0 - t) / 0.52), 0.0) ** 1.05


def tail_bone_points(spec):
    ctrl, broad, d = tail_curve(spec)
    return [bezier(*ctrl, t) for t in (0.0, 0.33, 0.66, 1.0)]




# ------------------------------------------------------------ v3 fur clump
def build_leaf_clump(md, part, root, nrm, flow, length, width, weight, lift=0.25, thick=0.5, sink=0.03, curl=0.35):
    """Sculpted, overlapping fur clump (10 tris): a thick pointed leaf lying on
    the host surface, lifting slightly and curling back toward it at the tip,
    so neighbouring clumps layer like shingles."""
    nrm = norm(nrm)
    flow = norm(flow - np.dot(flow, nrm) * nrm)
    side = norm(np.cross(flow, nrm))
    ca, sa = math.cos(lift), math.sin(lift)
    base = root - nrm * sink - flow * width * 0.25
    mid = root + flow * length * 0.45 * ca + nrm * length * 0.45 * sa
    apex = root + flow * length * ca + nrm * length * sa * (1 - curl)
    h = width * thick
    P = {
        'bL': base + side * width * 0.5, 'bR': base - side * width * 0.5,
        'bT': base + nrm * (h + sink), 'bB': base - nrm * h * 0.4,
        'mL': mid + side * width * 0.42, 'mR': mid - side * width * 0.42,
        'mT': mid + nrm * h * 0.7, 'A': apex,
    }
    isl = md.new_island(part)
    first = len(md.faces)
    V = {k: md.add_vert(p, weight) for k, p in P.items()}
    # (vertex keys, uvs, t along clump, u across)
    quads = [
        (('bL', 'bT', 'mT', 'mL'), ((0, 0), (.5, 0), (.5, .45), (0.05, .45))),
        (('bT', 'bR', 'mR', 'mT'), ((.5, 0), (1, 0), (.95, .45), (.5, .45))),
        (('bR', 'bB', 'A', 'mR'), ((0, 0), (.5, 0), (.5, 1), (.05, .45))),
        (('bB', 'bL', 'mL', 'A'), ((.5, 0), (1, 0), (.95, .45), (.5, 1))),
    ]
    tris = [(('mL', 'mT', 'A'), ((0.05, .45), (.5, .45), (.5, 1))),
            (('mT', 'mR', 'A'), ((.5, .45), (.95, .45), (.5, 1)))]
    tpar = {'bL': 0, 'bR': 0, 'bT': 0, 'bB': 0, 'mL': .45, 'mR': .45, 'mT': .45, 'A': 1}
    upar = {'bL': 0.0, 'bR': 3.14, 'bT': 1.57, 'bB': 4.71, 'mL': 0.3, 'mR': 2.8, 'mT': 1.57, 'A': 1.57}
    for keys, uvs in quads + tris:
        md.add_face([V[k] for k in keys], list(uvs), [(tpar[k], upar[k]) for k in keys], part, isl)
    md.orient_piece(first, root - nrm * width)


def build_flame_lock(md, part, root, d, skin_n, length, width, thick, weight, n=8, curl_k=0.18, curl_dir=None):
    """Closed, flattened flame-shaped fur lock (pointed leaf) growing from root
    along d.  It lies roughly parallel to the skin (flattened along the skin
    normal) and its tip curls further back.  Loft params: t 0 root -> 1 tip,
    th = 0 / pi on the two broad faces, +-pi/2 on the edges."""
    d = norm(d)
    flat = norm(skin_n - np.dot(skin_n, d) * d)           # thickness axis
    wax = norm(np.cross(d, flat))                         # width axis
    back = v3(0, 1, 0) if curl_dir is None else np.asarray(curl_dir, float)
    curl = norm(back - np.dot(back, d) * d) * curl_k * length
    fs = [0.0, 0.14, 0.30, 0.46, 0.62, 0.77, 0.89]
    centers = [root + d * length * f + curl * f * f for f in fs]
    rw = [width * k for k in (0.85, 1.0, 0.92, 0.72, 0.48, 0.27, 0.11)]       # broad base, flame taper
    rt = [thick * k for k in (1.0, 1.0, 0.92, 0.80, 0.64, 0.50, 0.38)]
    loft = Loft(centers, rw, rt, rt, wax, n)
    tip = root + d * length + curl
    loft.build(md, part, lambda i, t, p: dict(weight), cap_start=root - d * 0.012, cap_end=tip,
               t_range=(0.0, 0.89), cap_end_t=1.0)
    return loft


def ear_clip(poly):
    """Triangulate a simple 2D polygon (CCW) by ear clipping -> index triples."""
    P = [np.asarray(p, float) for p in poly]
    idx = list(range(len(P)))
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    out = []
    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = P[i0], P[i1], P[i2]
            if cross(a, b, c) <= 1e-12:
                continue
            inside = False
            for j in idx:
                if j in (i0, i1, i2):
                    continue
                q = P[j]
                if cross(a, b, q) >= 0 and cross(b, c, q) >= 0 and cross(c, a, q) >= 0:
                    inside = True
                    break
            if not inside:
                out.append((i0, i1, i2))
                idx.pop(k)
                break
    out.append(tuple(idx))
    return out


def build_slab(md, part, outline, origin, ax_u, ax_v, thick, weight):
    """Closed flat slab from a 2D outline (u along ax_u, v along ax_v), thickness
    along ax_u x ax_v.  Loft-style params for the painter: t = u / max(u),
    th = across position (sin(th) = v / max|v| on the faces, +-1 on the walls)."""
    ol = [np.asarray(p, float) for p in outline]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ol, ol[1:] + ol[:1]))
    if area < 0:
        ol = ol[::-1]
    nrm = norm(np.cross(ax_u, ax_v))
    umax = max(p[0] for p in ol)
    vmax = max(abs(p[1]) for p in ol)
    isl = md.new_island(part)
    first = len(md.faces)
    top, bot = [], []
    for u, v in ol:
        base = origin + ax_u * u + ax_v * v
        taper = 1.0 - 0.55 * max(0.0, u / umax) ** 1.5           # thinner toward the tips
        top.append(md.add_vert(base + nrm * thick * taper, weight))
        bot.append(md.add_vert(base - nrm * thick * taper, weight))
    tpar = lambda p: max(0.0, p[0]) / umax
    ang = lambda p: math.asin(max(-1.0, min(1.0, p[1] / vmax))) * 0.95
    uv = lambda p, f: (p[0] + 0.0, p[1] + (0.0 if f == 0 else 2.2 * vmax))
    for i0, i1, i2 in ear_clip(ol):
        tri = (ol[i0], ol[i1], ol[i2])
        md.add_face([top[i0], top[i1], top[i2]], [uv(q, 0) for q in tri], [(tpar(q), ang(q)) for q in tri], part, isl)
        md.add_face([bot[i2], bot[i1], bot[i0]], [uv(q, 1) for q in tri[::-1]],
                    [(tpar(q), math.pi - ang(q)) for q in tri[::-1]], part, isl)
    n = len(ol)
    L = 0.0
    for i in range(n):
        j = (i + 1) % n
        seg = np.linalg.norm(ol[j] - ol[i])
        w = math.copysign(math.pi / 2, (ol[i][1] + ol[j][1]) or 1.0)
        md.add_face([top[i], bot[i], bot[j], top[j]],
                    [(L, 4.5 * vmax), (L, 4.5 * vmax + 2 * thick), (L + seg, 4.5 * vmax + 2 * thick), (L + seg, 4.5 * vmax)],
                    [(tpar(ol[i]), w), (tpar(ol[i]), w), (tpar(ol[j]), w), (tpar(ol[j]), w)], part, isl)
        L += seg
    md.orient_piece(first)


def catmull_loop(pts, n_per):
    pts = [np.asarray(p, float) for p in pts]
    N = len(pts)
    out = []
    for i in range(N):
        p0, p1, p2, p3 = pts[(i - 1) % N], pts[i], pts[(i + 1) % N], pts[(i + 2) % N]
        for k in range(n_per):
            t = k / n_per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    return out


def catmull_open(pts, n_per):
    pts = [np.asarray(p, float) for p in pts]
    ext = [2 * pts[0] - pts[1]] + pts + [2 * pts[-1] - pts[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(n_per):
            t = k / n_per
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(pts[-1])
    return out


# ------------------------------------------------ v7 anatomy (sculpt pipeline)
# Organic parts (torso, neck, head, ears, legs, toe-paws) are built as CLOSED
# forms and later fused by a voxel remesh, smoothed, fur-sculpted and decimated
# (kitsune_sculpt.py).  Accessories (tails, harness, ornaments) stay separate.
# Unit: withers height = 1.0.  Creature faces -Y, left = +X.
FRONT_LEG = [v3(0.23, -0.30, 0.82), v3(0.26, -0.27, 0.46), v3(0.275, -0.33, 0.13), v3(0.28, -0.345, 0.09)]
HIND_LEG = [v3(0.22, 0.56, 0.84), v3(0.265, 0.45, 0.53), v3(0.28, 0.74, 0.24), v3(0.28, 0.71, 0.09)]
FRONT_PAW_C = v3(0.285, -0.385, 0.060)          # pad centre
HIND_PAW_C = v3(0.285, 0.665, 0.060)
HEAD_LIFT = v3(0.0, 0.05, 0.06)            # v19: head sits higher / further back on a more upright neck
EAR_BASE = v3(0.135, -0.66, 1.485) + HEAD_LIFT
EAR_TIP = v3(0.335, -0.655, 1.690) + HEAD_LIFT         # v17: short, pointed, splayed ~45 deg (in-game ears)
KNOT = v3(0.0, 0.14, 1.03)
TASSEL_TOP = v3(0.33, 0.14, 0.84)

# torso key profile (y, top z, bottom z, half width): rump now ends ~0.2 behind the hip joint
TORSO_KEYS = np.array([
    [0.68, 0.965, 0.66, 0.25], [0.58, 0.99, 0.58, 0.30], [0.46, 0.99, 0.55, 0.31], [0.34, 0.975, 0.53, 0.30],
    [0.22, 0.96, 0.51, 0.305], [0.08, 0.975, 0.47, 0.33], [-0.08, 1.00, 0.44, 0.355], [-0.24, 1.005, 0.425, 0.365],
    [-0.38, 0.995, 0.435, 0.355], [-0.50, 0.955, 0.485, 0.32], [-0.58, 0.885, 0.565, 0.24]])
TORSO_Y = list(np.linspace(TORSO_KEYS[0, 0], TORSO_KEYS[-1, 0], 18))
HEAD_KEYS_TB = np.array([   # y, top z, bottom z, half width  (domed skull, stop, short thick fox muzzle, wedge face)
    [-0.58, 1.44, 1.23, 0.155], [-0.64, 1.48, 1.21, 0.215], [-0.71, 1.475, 1.20, 0.235], [-0.77, 1.44, 1.18, 0.210],
    [-0.82, 1.378, 1.158, 0.140], [-0.87, 1.345, 1.142, 0.112], [-0.92, 1.320, 1.136, 0.098], [-0.97, 1.296, 1.136, 0.085],
    [-1.01, 1.276, 1.141, 0.071], [-1.045, 1.256, 1.151, 0.053]])
HEAD_KEYS_TB = HEAD_KEYS_TB + np.array([[HEAD_LIFT[1], HEAD_LIFT[2], HEAD_LIFT[2], 0.0]])
HEAD_KEYS_TB[:5, 1] += [0.030, 0.050, 0.055, 0.045, 0.020]     # v22: taller forehead / skull dome
HEAD_KEYS = np.c_[HEAD_KEYS_TB[:, 0], (HEAD_KEYS_TB[:, 1] + HEAD_KEYS_TB[:, 2]) / 2, HEAD_KEYS_TB[:, 3],
                  (HEAD_KEYS_TB[:, 1] - HEAD_KEYS_TB[:, 2]) / 2 * 0.92, (HEAD_KEYS_TB[:, 1] - HEAD_KEYS_TB[:, 2]) / 2 * 1.08]
EYE_S, EYE_TH = 0.38, math.radians(40)
# cheek ruff (reference head close-ups): a fan of curved flame locks growing ON the
# cheek, beside and below the eye (temple under the ear -> cheek -> jaw), flaring
# sideways and a little back so they frame the face in the front view.  Broad
# bases fuse into the cheek; the tips separate into sharp tongues.
# (head s, head th deg, direction weights (out along the skin normal, back, up),
#  length, half width)
CHEEK_LOCKS = [   # (head s, th deg, direction (out, back, up), length, half width, half thickness,
                  #  curl amount, curl direction (back, up))
    (0.345, 98, (1.00, 0.22, 0.10), 0.150, 0.092, 0.036, 0.60, (0.15, 1.0)),   # BIG tuft on the cheek below the eye
    (0.345, 114, (1.00, 0.30, -0.40), 0.085, 0.028, 0.016, 0.20, (0.5, 0.5)),  # small spikes stepping down
    (0.34, 126, (0.95, 0.35, -0.58), 0.070, 0.024, 0.014, 0.20, (0.5, 0.5)),   # the cheek
    (0.33, 137, (0.85, 0.40, -0.75), 0.055, 0.020, 0.013, 0.20, (0.5, 0.5)),
]
# in-game cheek tuft outline (u along the tuft from the root, v across), unit = 0.19
CHEEK_TUFT_OUTLINE = [   # a small fan of thin sharp spikes (in-game cheek tuft)
    (0.00, -0.15), (0.35, -0.21), (0.78, -0.30), (0.45, -0.17), (0.92, -0.16), (0.50, -0.06),
    (1.00, -0.01), (0.52, 0.06), (0.94, 0.14), (0.48, 0.17), (0.78, 0.27), (0.35, 0.20), (0.00, 0.15),
]
# nape mane: (loft, s, th deg, direction weights (out, back, up), length, half width)
MANE_LOCKS = []                                # v18: the top of the neck stays smooth
# halo harness loop: centre, radius, backward tilt (deg), half arc (deg from the top)
HALO_C, HALO_R, HALO_TILT, HALO_SPAN = v3(0.0, -0.25, 1.31), 0.48, 46.0, 128.0
# sculpted cyan ear fur (in-game ears): a bold lock curling inward at the inner
# base and one small spike on the inner edge; the outer edge stays clean.  Left ear, in the ear frame:
# (a along the ear, c across (+ outer edge), lift off the front face, direction
#  (across, along, forward), length, half width, half thickness)
EAR_FUR = []                                   # v23: clean ears (the inner-base locks read as shards)


def mx(p, sx):
    return v3(p[0] * sx, p[1], p[2])


def torso_s(y):
    """torso loft parameter (0 rear .. 1 front) for a world Y position."""
    return float(np.interp(-y, [-t for t in TORSO_Y], np.linspace(0, 1, len(TORSO_Y))))


def smooth_rows(keys, n):
    """Resample a key table (first column = y, descending) with Catmull-Rom."""
    ys = keys[:, 0]
    out_y = np.linspace(ys[0], ys[-1], n)
    cols = []
    for c in range(1, keys.shape[1]):
        pts = [np.array([ys[i], keys[i, c]]) for i in range(len(ys))]
        dense = catmull_open(pts, 12)
        dy = np.array([p[0] for p in dense]); dv = np.array([p[1] for p in dense])
        order = np.argsort(-dy)
        cols.append(np.interp(-out_y, -dy[order], dv[order]))
    return out_y, cols


def eye_frame(head, sx):
    """Analytic eye centre / normal / slanted long axis on the source head."""
    p, n, T = head.point(EYE_S, sx * EYE_TH, 0.0)
    ref_ax = v3(sx * 0.75, 0.55, 0.75)          # outer corner out, back and up -> inner corner low (aggressive)
    along = norm(ref_ax - np.dot(ref_ax, n) * n)
    acr = np.cross(n, along)
    acr = norm(acr) * (1 if acr[2] > 0 else -1)
    return p, n, along, acr


def build_kitsune():
    """Returns (md_body, md_acc, info).  md_body holds the closed organic forms
    that get fused + sculpted; md_acc holds tails, harness and ornaments."""
    md = MeshData()          # organic body
    ma = MeshData()          # accessories
    X = v3(1, 0, 0)

    # ------------------------------------------------------------------ torso
    ty, (top, bot, hw) = smooth_rows(TORSO_KEYS, 18)
    tz = (top + bot) / 2
    tr = (top - bot) / 2
    torso = Loft([v3(0, y, z) for y, z in zip(ty, tz)], hw, tr, tr, X, 24)
    torso_j = [(0.0, 'Hips'), (0.26, 'Hips'), (0.48, 'Spine'), (0.62, 'Spine'), (0.80, 'Chest'), (1.0, 'Chest')]

    def torso_w(i, t, p):
        w = blend_chain(t, torso_j)
        for leg, bone in ((FRONT_LEG, 'FrontLegUpper'), (HIND_LEG, 'HindLegUpper')):
            sx = 1 if p[0] >= 0 else -1
            d = np.linalg.norm((p - mx(leg[0], sx)) * v3(0.6, 1, 1))
            if p[2] < leg[0][2] and d < 0.30 and abs(p[0]) > 0.09:
                f = 0.45 * (1 - d / 0.30)
                w = {k: v * (1 - f) for k, v in w.items()}
                nm = bone + ('_L' if sx > 0 else '_R')
                w[nm] = w.get(nm, 0) + f
        return w
    torso.build(md, 'torso', torso_w, cap_start=v3(0, 0.73, 0.83), cap_end=v3(0, -0.625, 0.73))

    # ------------------------------------------------------------------- neck
    # thick neck running INTO the back of the skull and under the jaw; the
    # remesh fuses it with the head into one continuous surface
    nkeys = [v3(0, -0.34, 0.83), v3(0, -0.43, 0.99), v3(0, -0.50, 1.14), v3(0, -0.57, 1.27), v3(0, -0.65, 1.36)]   # upright
    neck_c = catmull_open(nkeys, 3)
    nr = np.linspace(0, 1, len(neck_c))
    nrw = list(np.interp(nr, [0, 0.45, 1], [0.27, 0.18, 0.14]))     # v20: sleek neck
    nrt = list(np.interp(nr, [0, 0.45, 1], [0.22, 0.155, 0.13]))
    nrb = list(np.interp(nr, [0, 0.45, 1], [0.28, 0.17, 0.12]))
    neck = Loft(neck_c, nrw, nrt, nrb, X, 20)
    neck_j = [(0.0, 'Chest'), (0.30, 'Neck1'), (0.70, 'Neck2'), (1.0, 'Head')]
    neck.build(md, 'neck', lambda i, t, p: blend_chain(t, neck_j),
               cap_start=neck_c[0] - norm(neck_c[1] - neck_c[0]) * 0.05,
               cap_end=neck_c[-1] + norm(neck_c[-1] - neck_c[-2]) * 0.05)

    # ------------------------------------------------------------------- head
    hy, (hz, hrw, hrt, hrb) = smooth_rows(HEAD_KEYS, 16)
    head = Loft([v3(0, y, z) for y, z in zip(hy, hz)], hrw, hrt, hrb, X, 22)
    head.build(md, 'head', lambda i, t, p: {'Head': 1.0} if i > 0 else {'Head': 0.8, 'Neck2': 0.2},
               cap_start=v3(0, -0.54, 1.335) + HEAD_LIFT, cap_end=v3(0, -1.078, 1.205) + HEAD_LIFT)

    # ------------------------------------------------------------------- ears
    for sx in (1, -1):
        base, tip = mx(EAR_BASE, sx), mx(EAR_TIP, sx)
        ax = norm(tip - base)
        pts = [base - ax * 0.06, base + (tip - base) * 0.25, base + (tip - base) * 0.52, base + (tip - base) * 0.76]
        ref = norm(v3(sx * 1.0, 0.12, 0))
        ear = Loft(pts, [0.128, 0.108, 0.066, 0.024], [0.080, 0.066, 0.044, 0.022], [0.046, 0.040, 0.028, 0.014], ref, 10)
        nm = 'Ear' + ('_L' if sx > 0 else '_R')
        ear.build(md, 'ear', lambda i, t, p, nm=nm: {'Head': 0.6, nm: 0.4} if i == 0 else {nm: 1.0},
                  cap_start=base - ax * 0.10, cap_end=tip)
        # sculpted cyan fur (fused into the ear by the voxel remesh)
        M = v3(sx, 1, 1)
        eax = norm(EAR_TIP - EAR_BASE)
        eside = norm(norm(v3(1.0, 0.12, 0)) - np.dot(norm(v3(1.0, 0.12, 0)), eax) * eax)
        eback = np.cross(eax, eside)
        eback = eback if eback[1] > 0 else -eback
        for a, c, lift, (dc, da, df), L, w, th_ in EAR_FUR:
            root = EAR_BASE + eax * a + eside * c
            if lift:                                    # on the front face: root just under the surface
                root = root - eback * 0.030
                skin = -eback
            else:                                       # in the rim: flat in the ear plane, root inside the edge
                root = root - eside * np.sign(c) * 0.022 - eback * 0.010
                skin = eback
            d = norm(eside * dc + eax * da - eback * df)
            build_flame_lock(md, 'ear_fur', root * M, d * M, skin * M, L + 0.022, w, th_, {nm: 1.0}, n=6,
                             curl_k=0.10)

    # ------------------------------------------------------------ nape mane
    # spiky purple crest from the back of the skull down the top of the neck
    # (reference side views): flame locks sweeping back / up, fused by the remesh
    for loft_, s, thd, (o, b, u), L, w in MANE_LOCKS:
        src = head if loft_ == 'head' else neck
        for sx in ((1,) if thd == 0 else (1, -1)):
            p, n, _ = src.point(s, sx * math.radians(thd), 0.0)
            d = norm(n * o + v3(0, b, u))
            build_flame_lock(md, 'mane', p - n * 0.04, d, n, L + 0.04, w, 0.022,
                             {'Head': 1.0} if loft_ == 'head' else {'Neck2': 1.0}, curl_k=0.22)

    # ------------------------------------------------------------ cheek ruff
    # in-game cheek fur: one chunky sculpted cyan tuft per cheek, just behind the
    # eye, flaring out sideways with a long main point and smaller side points.
    # Solid flame-shaped volumes (kept out of the remesh so the points stay sharp)
    for sx in (1, -1):
        for s_, thd, (o, b, u), L, w, tk, ck, (cb, cu) in CHEEK_LOCKS:
            p, n, _ = head.point(s_, sx * math.radians(thd), 0.0)
            d = norm(n * o + v3(0, b, u))
            build_flame_lock(ma, 'tuft_cheek', p - n * 0.030, d, n, L + 0.030, w, tk, {'Head': 1.0}, n=6,
                             curl_k=ck, curl_dir=v3(0, cb, cu))

    # ------------------------------------------------------------------- legs + paws
    toe_tips = []
    for sx in (1, -1):
        S = '_L' if sx > 0 else '_R'
        fl = [mx(p, sx) for p in FRONT_LEG]
        pts = catmull_open([fl[0], fl[1], fl[2], fl[3]], 2)[:7]
        lf = Loft(pts, [0.130, 0.112, 0.088, 0.070, 0.062, 0.062, 0.064], [0.150, 0.125, 0.094, 0.074, 0.064, 0.064, 0.066],
                  [0.150, 0.125, 0.094, 0.074, 0.064, 0.064, 0.066], X, 12)
        jf = [(0.0, 'FrontLegUpper' + S), (0.42, 'FrontLegUpper' + S), (0.52, 'FrontLegLower' + S),
              (0.86, 'FrontLegLower' + S), (0.96, 'FrontPaw' + S)]
        lf.build(md, 'leg_f', lambda i, t, p, jf=jf: blend_chain(t, jf),
                 cap_start=pts[0] + v3(0, 0, 0.05), cap_end=pts[-1] + v3(0, 0, -0.03))
        hl = [mx(p, sx) for p in HIND_LEG]
        pts = catmull_open([hl[0], hl[1], hl[2], hl[3]], 2)[:7]
        lh = Loft(pts, [0.170, 0.142, 0.104, 0.078, 0.064, 0.062, 0.064], [0.195, 0.160, 0.112, 0.082, 0.066, 0.064, 0.066],
                  [0.195, 0.160, 0.112, 0.082, 0.066, 0.064, 0.066], X, 12)
        jh = [(0.0, 'HindLegUpper' + S), (0.33, 'HindLegUpper' + S), (0.42, 'HindLegLower' + S),
              (0.66, 'HindLegLower' + S), (0.74, 'HindFoot' + S), (0.93, 'HindFoot' + S), (1.0, 'HindPaw' + S)]
        lh.build(md, 'leg_h', lambda i, t, p, jh=jh: blend_chain(t, jh),
                 cap_start=pts[0] + v3(0, 0, 0.05), cap_end=pts[-1] + v3(0, 0, -0.03))
        # paws sculpted from a broad pad + four separate toes (the remesh fuses them,
        # leaving creases between the toes like the reference close-up)
        for pc, bone in ((FRONT_PAW_C, 'FrontPaw' + S), (HIND_PAW_C, 'HindPaw' + S)):
            c = mx(pc, sx)
            w = {bone: 1.0}
            build_sphere(md, 'paw', c + v3(0, 0.015, 0.002), (0.106, 0.112, 0.058), 12, 7, w)
            for cx, dy in ((-0.086, 0.020), (-0.030, 0.0), (0.030, 0.0), (0.086, 0.020)):
                tc = c + v3(cx, -0.100 + dy, -0.012)
                build_sphere(md, 'paw', tc, (0.038, 0.054, 0.044), 10, 6, w)
                toe_tips.append((tc + v3(cx * 0.12, -0.044, -0.002), bone, sx))
            # small heel pad behind the leg
            build_sphere(md, 'paw', c + v3(0, 0.085, -0.004), (0.050, 0.040, 0.040), 8, 5, w)

    # ------------------------------------------------------------------ tails (unchanged design)
    tails = []
    for spec in tuned_specs():
        ctrl, broad, d = tail_curve(spec)
        name, tip, rmax, bow = spec
        cs = [bezier(*ctrl, t) for t in TAIL_T]
        rw = [tail_radius(t, rmax) for t in TAIL_T]
        rt = [r * 0.66 for r in rw]
        loft = Loft(cs, rw, rt, rt, broad, 9,
                    bulge=lambda i, th: 0.07 * math.cos(3 * th) * (1 if 2 < i < 10 else 0))
        jt = [(0.0, 'TailBase'), (0.08, name + '_1'), (0.28, name + '_1'), (0.40, name + '_2'),
              (0.62, name + '_2'), (0.74, name + '_3')]
        loft.build(ma, 'tail', lambda i, t, p, jt=jt: blend_chain(t, jt), cap_end=tip, t_range=(0.0, 0.97))
        tails.append((spec, loft, jt))

    # ---------------------------------------------------------------- harness
    # Built on the source surfaces, then SEATED onto the sculpted fur after the
    # sculpt (kitsune_sculpt.hug_accessories): every rope ring / rigid group is
    # pulled to  surface + normal * (clearance + designed lift).
    rope_r = 0.025
    coll_s = 0.14
    coll = [neck.point(coll_s, TAU * k / 16, rope_r * 2.2 + 0.05)[0] for k in range(16)]
    tb = build_tube(ma, 'rope', coll, rope_r, 6, lambda i, t, p: {'Neck1': 0.5, 'Chest': 0.5}, closed=True)
    ma.hug.append(dict(kind='tube', tube=tb, lift=[0.0] * len(tb['rings'])))
    back_pt = lambda y, deg, off: torso.point(torso_s(y), math.radians(deg), off)[0]
    # shoulder ropes (reference harness overlay): from the collar sides back over
    # the shoulders to the knot on the back -- a V seen from above
    for sx in (1, -1):
        pts = catmull_open([neck.point(coll_s, sx * math.radians(60), rope_r * 2.2 + 0.05)[0],
                            back_pt(-0.25, sx * 30, 0.05), back_pt(-0.02, sx * 15, 0.05),
                            KNOT + v3(sx * 0.035, -0.03, 0.0)], 3)
        tb = build_tube(ma, 'rope', pts, rope_r, 6, lambda i, t, p: {'Chest': 1.0})
        ma.hug.append(dict(kind='tube', tube=tb, lift=[0.0] * len(tb['rings'])))
    # the big HALO loop (reference sheet + in-game views): a bundle of ropes forming
    # one large ring that stands behind the head, tilted back a little, circling the
    # head in the front view; both ends come down over the shoulders and continue
    # down the sides of the neck into the collar (reference harness overlay)
    C, R, tilt = HALO_C, HALO_R, math.radians(HALO_TILT)
    up_ = v3(0, math.sin(tilt), math.cos(tilt))                # ring "up" leans back
    side_ = v3(1, 0, 0)
    nrm_ = np.cross(side_, up_)                                 # ring plane normal
    for dr, dn in ((0.0, 0.0), (-0.035, 0.012), (-0.012, -0.035)):
        arc = []
        for k in range(25):
            ang = math.radians(-HALO_SPAN + 2 * HALO_SPAN * k / 24)
            arc.append(C + side_ * (R + dr) * math.sin(ang) + up_ * (R + dr) * math.cos(ang) + nrm_ * dn)
        ends = []
        for sx, end, prev in ((-1, arc[0], arc[1]), (1, arc[-1], arc[-2])):
            tng = norm(end - prev)
            tie = neck.point(coll_s, sx * math.radians(98), rope_r * 2.2 + 0.03)[0] + v3(0, 0, dn * 0.5)
            mid = end + tng * 0.07
            ext = catmull_open([end, mid, (mid + tie) / 2 + v3(sx * 0.02, 0, 0), tie], 2)[1:]
            ends.append(ext)
        pts = ends[0][::-1] + arc + ends[1]
        build_tube(ma, 'rope', pts, rope_r * 0.85, 6,
                   lambda i, t, p: {'Chest': 1.0} if p[2] < 1.15 else {'Neck1': 0.5, 'Chest': 0.5}, cap_ends=True)
    # wrapped ties where the halo meets the collar
    for sx in (1, -1):
        tie = neck.point(coll_s, sx * math.radians(98), rope_r * 2.2 + 0.03)[0]
        tv0 = len(ma.verts)
        build_sphere(ma, 'knot', tie, (0.040, 0.045, 0.040), 6, 3, {'Neck1': 0.5, 'Chest': 0.5})
        ma.hug.append(dict(kind='rigid', v0=tv0, v1=len(ma.verts), anchor=tie, clear=0.030))
    v0 = len(ma.verts)
    build_sphere(ma, 'knot', KNOT + v3(0, 0, 0.04), (0.060, 0.050, 0.040), 6, 3, {'Spine': 0.5, 'Chest': 0.5})
    ma.hug.append(dict(kind='rigid', v0=v0, v1=len(ma.verts), anchor=KNOT + v3(0, 0, 0.04), clear=0.030))
    ks = torso_s(KNOT[1])
    tassel_tops = {sx: torso.point(ks, sx * math.radians(82), rope_r * 1.4 + 0.05)[0] for sx in (1, -1)}
    for sx in (1, -1):
        pts = catmull_open([KNOT + v3(sx * 0.03, 0, 0.02),
                            torso.point(ks, sx * math.radians(45), rope_r * 1.4 + 0.03)[0],
                            torso.point(ks, sx * math.radians(78), rope_r * 1.4 + 0.03)[0]], 3)
        tb = build_tube(ma, 'rope', pts, rope_r * 0.85, 5, lambda i, t, p: {'Spine': 0.5, 'Chest': 0.5})
        ma.hug.append(dict(kind='tube', tube=tb, lift=[0.0] * len(tb['rings'])))
    # chest gem: raised onto the collar front / upper chest
    gv0 = len(ma.verts)
    gem_p, gem_n, _ = neck.point(0.13, math.pi, 0.09)
    gem_p = gem_p + v3(0, -0.01, -0.035)
    for sx in (1, -1):
        a = neck.point(coll_s, sx * math.radians(150), rope_r * 2.2 + 0.05)[0]
        build_tube(ma, 'rope', [a, gem_p + v3(sx * 0.07, -0.01, 0.09)], rope_r * 0.9, 5,
                   lambda i, t, p: {'Neck1': 0.4, 'Chest': 0.6})
    fwd = norm(gem_n * v3(1, 1, 0.25))
    fr_up, fr_side = v3(0, 0, 1), v3(1, 0, 0)
    isl = ma.new_island('frame')
    first = len(ma.faces)
    outline = [(0, 0.20), (0.14, 0.03), (0, -0.13), (-0.14, 0.03)]
    frw = {'Chest': 0.7, 'Neck1': 0.3}
    front_v = [ma.add_vert(gem_p + fr_side * x + fr_up * y - fwd * 0.004, frw) for x, y in outline]
    back_v = [ma.add_vert(gem_p + fr_side * x * 0.9 + fr_up * y * 0.9 - fwd * 0.04, frw) for x, y in outline]
    ctr = ma.add_vert(gem_p + fwd * 0.015, frw)
    for k in range(4):
        k2 = (k + 1) % 4
        ma.add_face([front_v[k], front_v[k2], ctr], [(0.5 + outline[k][0] * 3, 0.5 + outline[k][1] * 3),
                                                     (0.5 + outline[k2][0] * 3, 0.5 + outline[k2][1] * 3), (0.5, 0.5)],
                    [(1, k), (1, k2), (0, 0)], 'frame', isl)
        ma.add_face([back_v[k], back_v[k2], front_v[k2], front_v[k]], [(k / 4, 0), ((k + 1) / 4, 0), ((k + 1) / 4, .2), (k / 4, .2)],
                    [(1, k), (1, k2), (1, k2), (1, k)], 'frame', isl)
    ma.orient_piece(first, gem_p - fwd * 0.05)
    build_sphere(ma, 'gem', gem_p + fwd * 0.04, (0.082, 0.082, 0.072), 8, 5, frw, axis_up=fwd, axis_side=fr_side)
    for sx in (1, -1):
        bp = gem_p + fr_side * sx * 0.08 + fr_up * -0.07 - fwd * 0.01
        build_tube(ma, 'rope', [gem_p + fr_side * sx * 0.08, bp], 0.008, 4, lambda i, t, p: frw)
        build_sphere(ma, 'bead', bp + v3(0, 0, -0.016), (0.022, 0.022, 0.022), 6, 3, frw)
        build_cone(ma, 'tassel', bp + v3(0, 0, -0.04), bp + v3(0, 0, -0.12), 0.019, 5, frw)
    # the whole ornament moves as one piece so its back plate rests on the chest fur
    ma.hug.append(dict(kind='rigid', v0=gv0, v1=len(ma.verts), anchor=gem_p - fwd * 0.04, clear=0.004))
    for sx in (1, -1):
        S = '_L' if sx > 0 else '_R'
        top = tassel_tops[sx]
        tw_ = {'Tassel' + S: 1.0}
        tv0 = len(ma.verts)
        build_tube(ma, 'rope', [top + v3(0, 0, 0.01), top + v3(0, 0, -0.10)], 0.010, 4,
                   lambda i, t, p, S=S: {'Spine': 0.5, 'Chest': 0.5} if i == 0 else {'Tassel' + S: 1.0})
        build_sphere(ma, 'bead', top + v3(0, 0, -0.14), (0.040, 0.040, 0.043), 6, 3, tw_)
        build_sphere(ma, 'bead', top + v3(0, 0, -0.25), (0.038, 0.038, 0.040), 6, 3, tw_)
        build_tube(ma, 'rope', [top + v3(0, 0, -0.18), top + v3(0, 0, -0.21)], 0.009, 4, lambda i, t, p: tw_)
        build_sphere(ma, 'tassel', top + v3(0, 0, -0.31), (0.028, 0.028, 0.022), 6, 3, tw_)
        tq = [top + v3(0, 0, -0.31), top + v3(0, 0, -0.38), top + v3(0, 0, -0.52)]
        build_tube(ma, 'tassel', tq, 0.032, 6, lambda i, t, p: tw_, radii=[0.028, 0.034, 0.038], cap_ends=True)
        # tassel hangs plumb from where the side strand meets the flank
        ma.hug.append(dict(kind='rigid', v0=tv0, v1=len(ma.verts), anchor=top, clear=0.045, horizontal_only=True))

    info = dict(torso=torso, neck=neck, head=head, tails=tails, toe_tips=toe_tips, tassel_tops=tassel_tops,
                eye=(EYE_S, EYE_TH))
    return md, ma, info


def add_claws(ma, toe_tips):
    """Long, curved, pale claws growing from each toe (reference leg close-up)."""
    for tip, bone, sx in toe_tips:
        w = {bone: 1.0}
        isl = ma.new_island('claw')
        first = len(ma.faces)
        path = [tip + v3(0, 0.022, 0.014), tip + v3(0, -0.022, 0.006), tip + v3(0, -0.062, -0.018), tip + v3(0, -0.084, -0.054)]
        radii = [0.022, 0.017, 0.010]
        rings = []
        for i in range(3):
            T = norm(path[i + 1] - path[max(i - 1, 0)])
            s = norm(np.cross(T, v3(0, 0, 1))) if abs(T[2]) < 0.95 else v3(1, 0, 0)
            u = np.cross(s, T)
            rings.append([ma.add_vert(path[i] + (s * math.cos(TAU * k / 4 + 0.785) * 1.15 + u * math.sin(TAU * k / 4 + 0.785))
                                      * radii[i], w) for k in range(4)])
        tv = ma.add_vert(path[3], w)
        for i in range(2):
            for k in range(4):
                k2 = (k + 1) % 4
                ma.add_face([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]],
                            [(k / 4, i / 3), ((k + 1) / 4, i / 3), ((k + 1) / 4, (i + 1) / 3), (k / 4, (i + 1) / 3)],
                            [(i / 3, TAU * k / 4), (i / 3, TAU * k2 / 4), ((i + 1) / 3, TAU * k2 / 4), ((i + 1) / 3, TAU * k / 4)],
                            'claw', isl)
        for k in range(4):
            k2 = (k + 1) % 4
            ma.add_face([rings[2][k], rings[2][k2], tv], [(k / 4, 2 / 3), ((k + 1) / 4, 2 / 3), ((k + .5) / 4, 1)],
                        [(2 / 3, TAU * k / 4), (2 / 3, TAU * k2 / 4), (1, 0)], 'claw', isl)
        ma.orient_piece(first, tip + v3(0, 0.0, 0.02))


def combined(md, ma):
    """Unsculpted body + accessories in one MeshData (quick previews / fit checks)."""
    out = MeshData()
    for src in (md, ma):
        off = len(out.verts)
        out.verts += src.verts
        out.weights += src.weights
        out.faces += [[v + off for v in f] for f in src.faces]
        out.face_uv += src.face_uv
        out.face_at += src.face_at
        out.face_part += src.face_part
        out.face_island += src.face_island
    return out


if __name__ == '__main__':
    md, ma, info = build_kitsune()
    add_claws(ma, info['toe_tips'])
    print('body source tris', md.tri_count(), 'accessory tris', ma.tri_count())
