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
    'bead': 17, 'tassel': 18, 'eye': 19,
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

    def build(self, md, part, weight_fn, cap_start=None, cap_end=None, t_range=(0.0, 1.0)):
        """cap_start / cap_end: None (open) or a pole position."""
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
        for cap, i, sgn, tcap in ((cap_start, 0, -1, t0), (cap_end, R - 1, 1, t1)):
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


TAIL_BASE = v3(0, 0.55, 0.95)
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
        tip[1] = TAIL_BASE[1] + (tip[1] - TAIL_BASE[1]) * T['back']
        grp = 'top' if name in ('Tail1', 'Tail2', 'Tail3') else ('mid' if name in ('Tail4', 'Tail5') else 'low')
        tip[2] += T['dz_' + grp]
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


# joint positions shared by geometry and rig (left side; mirrored for right)
FRONT_LEG = [v3(0.30, -0.33, 0.78), v3(0.35, -0.36, 0.43), v3(0.37, -0.44, 0.13), v3(0.37, -0.46, 0.085)]
HIND_LEG = [v3(0.28, 0.40, 0.84), v3(0.34, 0.28, 0.54), v3(0.36, 0.50, 0.24), v3(0.36, 0.44, 0.085)]
FRONT_PAW = [v3(0.37, -0.40, 0.075), v3(0.375, -0.50, 0.07), v3(0.38, -0.62, 0.05)]
HIND_PAW = [v3(0.36, 0.50, 0.075), v3(0.365, 0.40, 0.07), v3(0.37, 0.28, 0.05)]
EAR_BASE = v3(0.16, -0.60, 1.38)
EAR_TIP = v3(0.31, -0.62, 1.72)
TASSEL_TOP = v3(0.41, 0.08, 0.93)
TORSO_Y = [0.60, 0.52, 0.38, 0.22, 0.05, -0.12, -0.28, -0.42, -0.52]


def mx(p, sx):
    return v3(p[0] * sx, p[1], p[2])


def torso_s(y):
    """torso loft parameter (0 rear .. 1 front) for a world Y position."""
    return float(np.interp(-y, [-t for t in TORSO_Y], np.linspace(0, 1, len(TORSO_Y))))


def build_kitsune():
    md = MeshData()
    X = v3(1, 0, 0)

    # ------------------------------------------------------------------ torso
    tz = [0.84, 0.785, 0.76, 0.755, 0.745, 0.73, 0.72, 0.725, 0.75]
    trw = [0.22, 0.33, 0.32, 0.31, 0.35, 0.38, 0.40, 0.36, 0.27]
    trt = [0.12, 0.205, 0.24, 0.245, 0.255, 0.27, 0.27, 0.235, 0.17]
    trb = [0.14, 0.205, 0.24, 0.245, 0.26, 0.28, 0.28, 0.245, 0.17]
    torso = Loft([v3(0, y, z) for y, z in zip(TORSO_Y, tz)], trw, trt, trb, X, 16)
    torso_j = [(0.0, 'Hips'), (0.25, 'Hips'), (0.48, 'Spine'), (0.62, 'Spine'), (0.80, 'Chest'), (1.0, 'Chest')]

    def torso_w(i, t, p):
        w = blend_chain(t, torso_j)
        for leg, bone in ((FRONT_LEG, 'FrontLegUpper'), (HIND_LEG, 'HindLegUpper')):
            sx = 1 if p[0] >= 0 else -1
            d = np.linalg.norm((p - mx(leg[0], sx)) * v3(0.6, 1, 1))
            if p[2] < leg[0][2] and d < 0.32 and abs(p[0]) > 0.10:
                f = 0.45 * (1 - d / 0.32)
                w = {k: v * (1 - f) for k, v in w.items()}
                nm = bone + ('_L' if sx > 0 else '_R')
                w[nm] = w.get(nm, 0) + f
        return w
    torso.build(md, 'torso', torso_w, cap_start=v3(0, 0.67, 0.84), cap_end=v3(0, -0.585, 0.75))

    # ------------------------------------------------------------------- neck
    neck_c = [v3(0, -0.27, 0.84), v3(0, -0.40, 1.00), v3(0, -0.49, 1.13), v3(0, -0.54, 1.23)]
    neck = Loft(neck_c, [0.275, 0.245, 0.215, 0.18], [0.23, 0.20, 0.17, 0.14], [0.31, 0.27, 0.22, 0.16], X, 12)
    neck_j = [(0.0, 'Chest'), (0.30, 'Neck1'), (0.70, 'Neck2'), (1.0, 'Head')]
    neck.build(md, 'neck', lambda i, t, p: blend_chain(t, neck_j))

    # ------------------------------------------------------------------- head
    hc = [v3(0, -0.48, 1.285), v3(0, -0.55, 1.295), v3(0, -0.63, 1.275), v3(0, -0.71, 1.235),
          v3(0, -0.78, 1.18), v3(0, -0.85, 1.13), v3(0, -0.915, 1.11)]
    hrw = [0.18, 0.26, 0.285, 0.215, 0.130, 0.084, 0.056]
    hrt = [0.12, 0.125, 0.115, 0.090, 0.062, 0.042, 0.032]
    hrb = [0.13, 0.165, 0.165, 0.130, 0.095, 0.070, 0.047]
    head = Loft(hc, hrw, hrt, hrb, X, 12)
    head.build(md, 'head', lambda i, t, p: {'Head': 1.0} if i > 0 else {'Head': 0.8, 'Neck2': 0.2},
               cap_start=v3(0, -0.44, 1.285), cap_end=v3(0, -0.965, 1.105))

    # ------------------------------------------------------------------- eyes
    for sx in (1, -1):
        p, n, T = head.point(0.52, sx * math.radians(50), 0.0)
        side = norm(np.cross(n, v3(0, 0, 1)))
        upv = norm(np.cross(side, n))
        isl = md.new_island('eye')
        first = len(md.faces)
        rim = []
        for k in range(8):
            a = TAU * k / 8
            q = p + n * 0.004 + side * math.cos(a) * 0.047 + upv * math.sin(a) * 0.023 + upv * math.cos(a) * 0.011 * sx
            rim.append(md.add_vert(q, {'Head': 1.0}))
        cvt = md.add_vert(p + n * 0.014, {'Head': 1.0})
        for k in range(8):
            k2 = (k + 1) % 8
            a, b = TAU * k / 8, TAU * (k + 1) / 8
            md.add_face([rim[k], rim[k2], cvt], [(.5 + .5 * math.cos(a), .5 + .5 * math.sin(a)),
                                                 (.5 + .5 * math.cos(b), .5 + .5 * math.sin(b)), (.5, .5)],
                        [(1, a), (1, b), (0, 0)], 'eye', isl)
        md.orient_piece(first, p - n * 0.05)

    # ------------------------------------------------------------------- ears
    for sx in (1, -1):
        base, tip = mx(EAR_BASE, sx), mx(EAR_TIP, sx)
        ax = norm(tip - base)
        pts = [base - ax * 0.04, base + (tip - base) * 0.33, base + (tip - base) * 0.68]
        ref = norm(v3(sx * 1.0, 0.18, 0))      # broad side faces forward
        ear = Loft(pts, [0.150, 0.105, 0.052], [0.038, 0.030, 0.016], [0.030, 0.022, 0.012], ref, 6)
        nm = 'Ear' + ('_L' if sx > 0 else '_R')
        ear.build(md, 'ear', lambda i, t, p, nm=nm: {'Head': 0.6, nm: 0.4} if i == 0 else {nm: 1.0},
                  cap_end=tip)

    # ------------------------------------------------------------------- legs
    for sx in (1, -1):
        S = '_L' if sx > 0 else '_R'
        fl = [mx(p, sx) for p in FRONT_LEG]
        pts = [fl[0], fl[0] * 0.5 + fl[1] * 0.5, fl[1], fl[1] * 0.5 + fl[2] * 0.5, fl[2], fl[3]]
        lf = Loft(pts, [0.150, 0.140, 0.100, 0.080, 0.070, 0.066], [0.165, 0.150, 0.110, 0.085, 0.072, 0.070],
                  [0.165, 0.150, 0.110, 0.085, 0.072, 0.070], X, 8)
        jf = [(0.0, 'FrontLegUpper' + S), (0.42, 'FrontLegUpper' + S), (0.52, 'FrontLegLower' + S),
              (0.86, 'FrontLegLower' + S), (0.96, 'FrontPaw' + S)]
        lf.build(md, 'leg_f', lambda i, t, p, jf=jf: blend_chain(t, jf))
        hl = [mx(p, sx) for p in HIND_LEG]
        pts = [hl[0], hl[0] * 0.45 + hl[1] * 0.55, hl[1], hl[1] * 0.5 + hl[2] * 0.5, hl[2], hl[2] * 0.5 + hl[3] * 0.5, hl[3]]
        lh = Loft(pts, [0.175, 0.170, 0.115, 0.080, 0.064, 0.060, 0.062], [0.200, 0.190, 0.125, 0.085, 0.066, 0.062, 0.068],
                  [0.200, 0.190, 0.125, 0.085, 0.066, 0.062, 0.068], X, 8)
        jh = [(0.0, 'HindLegUpper' + S), (0.33, 'HindLegUpper' + S), (0.42, 'HindLegLower' + S),
              (0.66, 'HindLegLower' + S), (0.74, 'HindFoot' + S), (0.93, 'HindFoot' + S), (1.0, 'HindPaw' + S)]
        lh.build(md, 'leg_h', lambda i, t, p, jh=jh: blend_chain(t, jh))
        for pawpts, bone, lower in ((FRONT_PAW, 'FrontPaw' + S, 'FrontPaw' + S), (HIND_PAW, 'HindPaw' + S, 'HindFoot' + S)):
            pp = [mx(p, sx) for p in pawpts]
            paw = Loft(pp, [0.070, 0.090, 0.086], [0.062, 0.066, 0.042], [0.040, 0.042, 0.030], X, 8)
            paw.build(md, 'paw', lambda i, t, p, b=bone, lo=lower: {b: 1.0} if i else {b: 0.6, lo: 0.4},
                      cap_start=pp[0] + norm(pp[0] - pp[1]) * 0.035 + v3(0, 0, 0.005),
                      cap_end=pp[2] + v3(0, -0.035, -0.010))
            for cx in (-0.055, -0.019, 0.019, 0.055):
                b = pp[2] + v3(cx, 0.0, -0.012)
                build_cone(md, 'claw', b + v3(0, 0.018, 0.008), b + v3(cx * 0.2, -0.060, -0.034), 0.022, 4, {bone: 1.0})

    # ------------------------------------------------------------------ tails
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
        loft.build(md, 'tail', lambda i, t, p, jt=jt: blend_chain(t, jt), cap_end=tip, t_range=(0.0, 0.97))
        tails.append((spec, loft, jt))

    # ------------------------------------------------------------ fur clumps
    def clump_on(loft, s, th, part, L, W, flow, wfn, lift=0.5, sink=0.025, thick=0.45):
        p, n, T = loft.point(s, th)
        build_clump(md, part, p, n, flow(p, n, T), L, W, wfn(s, p), lift=lift, sink=sink, thick=thick)

    back_flow = lambda p, n, T: v3(0, 1, -0.2)
    down_back = lambda p, n, T: v3(0, 0.55, -1)
    neck_down = lambda p, n, T: -T + v3(0, 0.3, 0)
    tw = lambda s, p: torso_w(0, s, p)
    nw = lambda s, p: blend_chain(s, neck_j)
    hw = lambda s, p: {'Head': 1.0}

    # nape mane: layered spiky clumps flowing back over the withers
    for s, L in ((0.95, 0.22), (0.70, 0.26), (0.45, 0.27), (0.20, 0.25)):
        for deg in (0, 40, -40, 85, -85):
            clump_on(neck, s, math.radians(deg + (10 if s in (0.70, 0.20) else 0)), 'tuft',
                     L * (0.85 if abs(deg) > 60 else 1), 0.15, lambda p, n, T: -T + v3(0, 0.6, 0.15), nw, lift=0.6)
    # chest ruff (front of neck / chest, flows down)
    for s, L in ((0.10, 0.22), (0.35, 0.21), (0.60, 0.18)):
        for deg in (180, 140, -140):
            clump_on(neck, s, math.radians(deg), 'tuft', L, 0.15, lambda p, n, T: v3(0, 0.15, -1), nw, lift=0.35)
    # head crest between the ears and cyan cheek spikes
    for deg in (0, 35, -35):
        clump_on(head, 0.12, math.radians(deg), 'tuft', 0.17, 0.10, back_flow, hw, lift=0.6)
    for sx in (1, -1):
        for s, deg, L in ((0.30, 95, 0.22), (0.20, 120, 0.19), (0.42, 112, 0.15)):
            clump_on(head, s, sx * math.radians(deg), 'tuft_cyan', L, 0.085,
                     lambda p, n, T, sx=sx: v3(sx * 1.0, 0.8, -0.05), hw, lift=0.2)
    # torso: shoulders, flanks, haunches, belly fringe, back ridge
    for sx in (1, -1):
        S = '_L' if sx > 0 else '_R'
        for y, deg, L in ((-0.40, 70, 0.22), (-0.30, 100, 0.24), (-0.15, 80, 0.21), (0.0, 105, 0.20), (0.15, 75, 0.20),
                          (0.30, 100, 0.21), (0.45, 80, 0.21), (-0.36, 140, 0.20), (-0.18, 150, 0.19), (0.02, 150, 0.19),
                          (0.20, 148, 0.18), (-0.05, 40, 0.16), (0.32, 40, 0.16), (-0.25, 38, 0.16)):
            clump_on(torso, torso_s(y), sx * math.radians(deg), 'tuft', L, 0.17, down_back, tw, lift=0.42, thick=0.35)
        # elbow and thigh tufts
        e = mx(FRONT_LEG[1], sx) + v3(sx * 0.02, 0.08, 0.04)
        build_clump(md, 'tuft', e, v3(sx * 0.3, 1, 0.1), v3(0, 0.6, -1), 0.18, 0.10,
                    {'FrontLegUpper' + S: 0.5, 'FrontLegLower' + S: 0.5}, lift=0.3)
        h = mx(HIND_LEG[0], sx) * 0.4 + mx(HIND_LEG[1], sx) * 0.6 + v3(sx * 0.04, 0.12, 0)
        build_clump(md, 'tuft', h, v3(sx * 0.3, 1, 0.1), v3(0, 0.5, -1), 0.20, 0.11, {'HindLegUpper' + S: 1.0}, lift=0.3)
        # jagged purple fur spikes over the cyan lower legs (point down)
        for leg, t_b, bone, r in ((FRONT_LEG, 0.55, 'FrontLegLower' + S, 0.075), (HIND_LEG, 0.35, 'HindLegLower' + S, 0.09)):
            a, b = mx(leg[1], sx), mx(leg[2], sx)
            c = a + (b - a) * t_b
            for ang in (0, 90, 180, 270):
                dirn = v3(math.sin(math.radians(ang)) * sx, math.cos(math.radians(ang)), 0)
                build_clump(md, 'tuft', c + dirn * r * 0.8, dirn, norm(b - a), 0.13, 0.07, {bone: 1.0}, lift=0.25)
    # dorsal spikes (two tall ones between the harness loops + smaller ridge)
    for y, L, W in ((0.20, 0.26, 0.17), (0.34, 0.22, 0.16)):
        s = torso_s(y)
        p, n, T = torso.point(s, 0.0)
        build_clump(md, 'spike', p, v3(0, 0, 1), v3(0, 1.0, 0.0), L, W, torso_w(0, s, p), lift=0.95, thick=0.5)

    # ---------------------------------------------------------------- harness
    rope_r = 0.026
    # collar around the neck base (sits on the chest ruff)
    coll = [neck.point(0.18, TAU * k / 12, rope_r * 2.2)[0] for k in range(12)]
    build_tube(md, 'rope', coll, rope_r, 5, lambda i, t, p: {'Neck1': 0.5, 'Chest': 0.5}, closed=True)
    # girth rope around the barrel (the tassels hang from it)
    gs = torso_s(0.10)
    girth = [torso.point(gs, TAU * k / 14, rope_r * 1.6)[0] for k in range(14)]
    build_tube(md, 'rope', girth, rope_r, 5, lambda i, t, p: torso_w(0, gs, p), closed=True)
    # two big hoops: a ring around the head seen from the front, arching from
    # the neck base up over the withers and down onto the back seen from the side
    # two hoops lying along the back, leaning in so their tops meet above the
    # withers: side = open ellipse, front = ring of two arcs, top = tear-drop
    for sx in (1, -1):
        c = v3(sx * 0.21, -0.06, 1.20)
        a_ax = v3(sx * 0.10, 0.44, 0.02)
        b_ax = norm(v3(-sx * 0.52, 0.0, 0.86)) * 0.42
        pts = [c + a_ax * math.cos(TAU * k / 18) + b_ax * math.sin(TAU * k / 18) for k in range(18)]
        rr = 0.028
        build_tube(md, 'rope', pts, rr, 5, lambda i, t, p: {'Chest': 1.0}, closed=True)
    # back strands collar -> girth (tear-drop seen from above) with knots
    for sx in (1, -1):
        a = neck.point(0.18, sx * math.radians(35), rope_r * 2.2)[0]
        pts = [a]
        for y in (-0.22, -0.05):
            pts.append(torso.point(torso_s(y), sx * math.radians(28), rope_r * 1.6)[0])
        pts.append(torso.point(gs, sx * math.radians(12), rope_r * 1.6)[0])
        build_tube(md, 'rope', pts, rope_r * 0.9, 5, lambda i, t, p: {'Chest': 1.0})
    # chest strands collar -> gem
    gem_p, gem_n, _ = neck.point(0.02, math.pi, 0.05)
    gem_p = gem_p + v3(0, -0.02, -0.02)
    for sx in (1, -1):
        a = neck.point(0.18, sx * math.radians(120), rope_r * 2.2)[0]
        m = neck.point(0.08, sx * math.radians(150), rope_r * 2.4)[0]
        build_tube(md, 'rope', [a, m, gem_p + v3(sx * 0.05, -0.01, 0.07)], rope_r * 0.9, 5,
                   lambda i, t, p: {'Neck1': 0.4, 'Chest': 0.6})
    for p, w in ((neck.point(0.18, 0.0, rope_r * 3.0)[0], {'Neck1': 0.5, 'Chest': 0.5}),
                 (torso.point(gs, 0.0, rope_r * 2.6)[0], {'Spine': 0.5, 'Chest': 0.5}),
                 (torso.point(torso_s(-0.12), 0.0, rope_r * 2.6)[0], {'Chest': 1.0})):
        build_sphere(md, 'knot', p, (0.06, 0.05, 0.04), 6, 4, w)
    # chest ornament: diamond frame + big red gem + two small dangles
    fwd = norm(gem_n * v3(1, 1, 0.25))
    fr_up, fr_side = v3(0, 0, 1), v3(1, 0, 0)
    isl = md.new_island('frame')
    first = len(md.faces)
    outline = [(0, 0.21), (0.15, 0.03), (0, -0.14), (-0.15, 0.03)]
    frw = {'Chest': 0.7, 'Neck1': 0.3}
    front = [md.add_vert(gem_p + fr_side * x + fr_up * y - fwd * 0.004, frw) for x, y in outline]
    back = [md.add_vert(gem_p + fr_side * x * 0.9 + fr_up * y * 0.9 - fwd * 0.04, frw) for x, y in outline]
    ctr = md.add_vert(gem_p + fwd * 0.015, frw)
    for k in range(4):
        k2 = (k + 1) % 4
        md.add_face([front[k], front[k2], ctr], [(0.5 + outline[k][0] * 3, 0.5 + outline[k][1] * 3),
                                                 (0.5 + outline[k2][0] * 3, 0.5 + outline[k2][1] * 3), (0.5, 0.5)],
                    [(1, k), (1, k2), (0, 0)], 'frame', isl)
        md.add_face([back[k], back[k2], front[k2], front[k]], [(k / 4, 0), ((k + 1) / 4, 0), ((k + 1) / 4, .2), (k / 4, .2)],
                    [(1, k), (1, k2), (1, k2), (1, k)], 'frame', isl)
    md.orient_piece(first, gem_p - fwd * 0.05)
    build_sphere(md, 'gem', gem_p + fwd * 0.04, (0.088, 0.088, 0.075), 8, 5, frw, axis_up=fwd, axis_side=fr_side)
    for sx in (1, -1):
        bp = gem_p + fr_side * sx * 0.085 + fr_up * -0.07 - fwd * 0.01
        build_tube(md, 'rope', [gem_p + fr_side * sx * 0.085, bp], 0.008, 4, lambda i, t, p: frw)
        build_sphere(md, 'bead', bp + v3(0, 0, -0.016), (0.022, 0.022, 0.022), 6, 4, frw)
        build_cone(md, 'tassel', bp + v3(0, 0, -0.04), bp + v3(0, 0, -0.12), 0.019, 5, frw)

    # side tassels hanging from the girth rope: string, 2 beads, tassel
    for sx in (1, -1):
        S = '_L' if sx > 0 else '_R'
        top = mx(TASSEL_TOP, sx)
        tw_ = {'Tassel' + S: 1.0}
        pts = [top + v3(-sx * 0.04, 0, 0.03), top, top + v3(0, 0, -0.10)]
        build_tube(md, 'rope', pts, 0.010, 4, lambda i, t, p, S=S: {'Chest': 1.0} if i == 0 else {'Tassel' + S: 1.0})
        build_sphere(md, 'bead', top + v3(0, 0, -0.14), (0.042, 0.042, 0.045), 6, 4, tw_)
        build_sphere(md, 'bead', top + v3(0, 0, -0.26), (0.040, 0.040, 0.042), 6, 4, tw_)
        build_tube(md, 'rope', [top + v3(0, 0, -0.18), top + v3(0, 0, -0.22)], 0.009, 4, lambda i, t, p: tw_)
        build_sphere(md, 'tassel', top + v3(0, 0, -0.33), (0.030, 0.030, 0.024), 6, 3, tw_)
        tq = [top + v3(0, 0, -0.33), top + v3(0, 0, -0.40), top + v3(0, 0, -0.55)]
        build_tube(md, 'tassel', tq, 0.034, 6, lambda i, t, p: tw_, radii=[0.030, 0.036, 0.040], cap_ends=True)

    return md, dict(torso=torso, neck=neck, head=head, tails=tails)


if __name__ == '__main__':
    md, _ = build_kitsune()
    print('verts', len(md.verts), 'faces', len(md.faces), 'tris', md.tri_count())
    from collections import Counter
    inv = {v: k for k, v in PART_IDS.items()}
    cnt = Counter()
    for f, p in zip(md.faces, md.face_part):
        cnt[inv[p]] += len(f) - 2
    print(dict(cnt))
