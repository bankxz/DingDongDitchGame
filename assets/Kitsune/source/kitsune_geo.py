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
def bezier(p0, p1, p2, p3, t):
    a = 1 - t
    return a**3 * p0 + 3 * a * a * t * p1 + 3 * a * t * t * p2 + t**3 * p3


TAIL_BASE = v3(0, 0.60, 0.88)
# (name, fan angle deg seen from behind: 90 = up, 0 = creature left (+X)), back factor, length, max radius
TAIL_SPECS = [
    ('Tail1', 90.0, 0.72, 1.25, 0.27),     # top centre
    ('Tail2', 46.0, 0.72, 1.36, 0.28),     # upper left
    ('Tail3', 134.0, 0.72, 1.36, 0.28),    # upper right
    ('Tail4', 8.0, 0.68, 1.40, 0.28),      # mid left
    ('Tail5', 172.0, 0.68, 1.40, 0.28),    # mid right
    ('Tail6', -30.0, 0.85, 1.28, 0.27),    # lower left
    ('Tail7', 210.0, 0.85, 1.28, 0.27),    # lower right
    ('Tail8', -90.0, 0.95, 0.86, 0.25),    # hangs down over the rump
]
TAIL_T = [0.0, 0.07, 0.16, 0.27, 0.39, 0.51, 0.62, 0.72, 0.81, 0.89, 0.95]


def tail_curve(spec):
    name, phi, back, L, rmax = spec
    ph = math.radians(phi)
    fan = v3(math.cos(ph), 0.0, math.sin(ph))
    d = norm(back * v3(0, 1, 0) + fan)
    # tips curl up / outward like flames
    if abs(phi - 90) < 1 or abs(phi + 90) < 1:
        curl = v3(0, 0.25, 0.0) if phi > 0 else v3(0, 0.35, 0.10)
    else:
        tang = v3(-math.sin(ph), 0, math.cos(ph)) * (1 if math.cos(ph) > 0 else -1)
        curl = tang * 0.9 + v3(0, 0.15, 0)
    p0 = TAIL_BASE - d * 0.02
    p1 = TAIL_BASE + norm(v3(0, 1.0, 0.55)) * 0.28 * L + fan * 0.08 * L
    p2 = TAIL_BASE + d * 0.72 * L
    p3 = TAIL_BASE + d * L + curl * 0.16 * L
    return (p0, p1, p2, p3), fan, d


def tail_radius(t, rmax):
    if t <= 0.56:
        return rmax * (0.30 + 0.70 * math.sin(0.5 * math.pi * t / 0.56) ** 0.7)
    return rmax * max(((1.0 - t) / 0.44), 0.0) ** 0.85


def tail_bone_points(spec):
    ctrl, fan, d = tail_curve(spec)
    return [bezier(*ctrl, t) for t in (0.0, 0.33, 0.66, 1.0)]


# joint positions shared by geometry and rig -------------------------------
FRONT_LEG = [v3(0.12, -0.20, 0.88), v3(0.135, -0.11, 0.52), v3(0.13, -0.15, 0.15), v3(0.13, -0.16, 0.075)]
HIND_LEG = [v3(0.12, 0.50, 0.84), v3(0.14, 0.34, 0.54), v3(0.135, 0.62, 0.26), v3(0.13, 0.58, 0.075)]
FRONT_PAW = [v3(0.13, -0.09, 0.065), v3(0.13, -0.175, 0.06), v3(0.13, -0.265, 0.045)]
HIND_PAW = [v3(0.13, 0.65, 0.065), v3(0.13, 0.565, 0.06), v3(0.13, 0.475, 0.045)]
EAR_BASE = v3(0.095, -0.41, 1.45)
EAR_TIP = v3(0.19, -0.37, 1.78)
TASSEL_TOP = v3(0.235, -0.02, 0.93)


def mx(p, sx):
    return v3(p[0] * sx, p[1], p[2])


def build_kitsune():
    md = MeshData()
    X = v3(1, 0, 0)

    # ------------------------------------------------------------------ torso
    ty = [0.66, 0.60, 0.50, 0.36, 0.20, 0.05, -0.08, -0.19, -0.27]
    tz = [0.86, 0.855, 0.84, 0.83, 0.835, 0.835, 0.845, 0.85, 0.85]
    trw = [0.12, 0.175, 0.205, 0.180, 0.190, 0.215, 0.228, 0.212, 0.160]
    trt = [0.09, 0.115, 0.125, 0.110, 0.130, 0.165, 0.180, 0.175, 0.140]
    trb = [0.11, 0.180, 0.235, 0.195, 0.225, 0.270, 0.290, 0.265, 0.185]
    torso = Loft([v3(0, y, z) for y, z in zip(ty, tz)], trw, trt, trb, X, 16)
    torso_j = [(0.0, 'Hips'), (0.30, 'Hips'), (0.52, 'Spine'), (0.70, 'Spine'), (0.86, 'Chest'), (1.0, 'Chest')]

    def torso_w(i, t, p):
        w = blend_chain(t, torso_j)
        # shoulder / haunch skin follows the upper leg a little
        for leg, bone in ((FRONT_LEG, 'FrontLegUpper'), (HIND_LEG, 'HindLegUpper')):
            sx = 1 if p[0] >= 0 else -1
            d = np.linalg.norm((p - mx(leg[0], sx)) * v3(0.6, 1, 1))
            if p[2] < leg[0][2] - 0.02 and d < 0.28 and abs(p[0]) > 0.06:
                f = 0.45 * (1 - d / 0.28)
                w = {k: v * (1 - f) for k, v in w.items()}
                nm = bone + ('_L' if sx > 0 else '_R')
                w[nm] = w.get(nm, 0) + f
        return w
    torso.build(md, 'torso', torso_w, cap_start=v3(0, 0.72, 0.86), cap_end=v3(0, -0.305, 0.85))

    # ------------------------------------------------------------------- neck
    neck_c = [v3(0, -0.16, 0.90), v3(0, -0.25, 1.03), v3(0, -0.31, 1.17), v3(0, -0.35, 1.30), v3(0, -0.37, 1.38)]
    neck = Loft(neck_c, [0.160, 0.150, 0.132, 0.112, 0.098], [0.165, 0.150, 0.130, 0.110, 0.098],
                [0.20, 0.18, 0.145, 0.118, 0.098], X, 12)
    neck_j = [(0.0, 'Chest'), (0.25, 'Neck1'), (0.6, 'Neck2'), (0.95, 'Head')]
    neck.build(md, 'neck', lambda i, t, p: blend_chain(t, neck_j))

    # ------------------------------------------------------------------- head
    hc = [v3(0, -0.345, 1.395), v3(0, -0.405, 1.405), v3(0, -0.48, 1.395), v3(0, -0.555, 1.35),
          v3(0, -0.625, 1.305), v3(0, -0.69, 1.27), v3(0, -0.745, 1.245)]
    hrw = [0.095, 0.155, 0.168, 0.135, 0.084, 0.058, 0.040]
    hrt = [0.085, 0.108, 0.104, 0.078, 0.056, 0.044, 0.033]
    hrb = [0.085, 0.118, 0.118, 0.094, 0.068, 0.052, 0.037]
    head = Loft(hc, hrw, hrt, hrb, X, 12)
    head.build(md, 'head', lambda i, t, p: {'Head': 1.0} if i > 0 else {'Head': 0.8, 'Neck2': 0.2},
               cap_start=v3(0, -0.30, 1.40), cap_end=v3(0, -0.785, 1.233))

    # ------------------------------------------------------------------- eyes
    for sx in (1, -1):
        p, n, T = head.point(0.50, sx * math.radians(52), 0.0)
        side = norm(np.cross(n, v3(0, 0, 1)))
        upv = norm(np.cross(side, n))
        isl = md.new_island('eye')
        first = len(md.faces)
        rim = []
        for k in range(8):
            a = TAU * k / 8
            q = p + n * 0.004 + side * math.cos(a) * 0.028 + upv * math.sin(a) * 0.013 + upv * math.cos(a) * 0.006 * sx
            rim.append(md.add_vert(q, {'Head': 1.0}))
        cvt = md.add_vert(p + n * 0.012, {'Head': 1.0})
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
        pts = [base - ax * 0.03, base + (tip - base) * 0.35, base + (tip - base) * 0.72]
        ref = norm(v3(sx * 1.0, 0.35, 0))       # broad axis turned slightly outward
        ear = Loft(pts, [0.098, 0.074, 0.036], [0.036, 0.030, 0.015], [0.036, 0.026, 0.013], ref, 6)
        nm = 'Ear' + ('_L' if sx > 0 else '_R')
        ear.build(md, 'ear', lambda i, t, p, nm=nm: {'Head': 0.6, nm: 0.4} if i == 0 else {nm: 1.0},
                  cap_end=tip)

    # ------------------------------------------------------------------- legs
    for sx in (1, -1):
        S = '_L' if sx > 0 else '_R'
        # front leg
        fl = [mx(p, sx) for p in FRONT_LEG]
        pts = [fl[0], fl[0] * 0.5 + fl[1] * 0.5, fl[1], fl[1] * 0.55 + fl[2] * 0.45, fl[2], fl[3]]
        lf = Loft(pts, [0.118, 0.110, 0.076, 0.062, 0.054, 0.054], [0.130, 0.120, 0.080, 0.064, 0.056, 0.060],
                  [0.130, 0.120, 0.080, 0.064, 0.056, 0.060], X, 8)
        jf = [(0.0, 'FrontLegUpper' + S), (0.42, 'FrontLegUpper' + S), (0.52, 'FrontLegLower' + S),
              (0.86, 'FrontLegLower' + S), (0.96, 'FrontPaw' + S)]
        lf.build(md, 'leg_f', lambda i, t, p, jf=jf: blend_chain(t, jf))
        # hind leg
        hl = [mx(p, sx) for p in HIND_LEG]
        pts = [hl[0], hl[0] * 0.45 + hl[1] * 0.55, hl[1], hl[1] * 0.5 + hl[2] * 0.5, hl[2], hl[2] * 0.5 + hl[3] * 0.5, hl[3]]
        lh = Loft(pts, [0.140, 0.145, 0.095, 0.070, 0.058, 0.054, 0.054], [0.160, 0.170, 0.105, 0.078, 0.060, 0.056, 0.060],
                  [0.160, 0.170, 0.105, 0.078, 0.060, 0.056, 0.060], X, 8)
        jh = [(0.0, 'HindLegUpper' + S), (0.33, 'HindLegUpper' + S), (0.42, 'HindLegLower' + S),
              (0.66, 'HindLegLower' + S), (0.74, 'HindFoot' + S), (0.93, 'HindFoot' + S), (1.0, 'HindPaw' + S)]
        lh.build(md, 'leg_h', lambda i, t, p, jh=jh: blend_chain(t, jh))
        # paws (heel -> toes)
        for pawpts, bone, lower in ((FRONT_PAW, 'FrontPaw' + S, 'FrontPaw' + S), (HIND_PAW, 'HindPaw' + S, 'HindFoot' + S)):
            pp = [mx(p, sx) for p in pawpts]
            paw = Loft(pp, [0.055, 0.076, 0.072], [0.048, 0.054, 0.036], [0.034, 0.036, 0.026], X, 8)
            paw.build(md, 'paw', lambda i, t, p, b=bone, lo=lower: {b: 1.0} if i else {b: 0.6, lo: 0.4},
                      cap_start=pp[0] + norm(pp[0] - pp[1]) * 0.03 + v3(0, 0, 0.005),
                      cap_end=pp[2] + v3(0, -0.028, -0.008))
            # claws
            for cx in (-0.045, -0.015, 0.015, 0.045):
                b = pp[2] + v3(cx, 0.0, -0.012)
                build_cone(md, 'claw', b + v3(0, 0.014, 0.004), b + v3(cx * 0.2, -0.065, -0.032), 0.013, 3, {bone: 1.0})

    # ------------------------------------------------------------------ tails
    tails = []
    for spec in TAIL_SPECS:
        ctrl, fan, d = tail_curve(spec)
        name, phi, back, L, rmax = spec
        cs = [bezier(*ctrl, t) for t in TAIL_T]
        tip = bezier(*ctrl, 1.0)
        tang = norm(v3(-math.sin(math.radians(phi)), 0, math.cos(math.radians(phi))))
        rw = [tail_radius(t, rmax) for t in TAIL_T]
        rt = [r * 0.72 for r in rw]
        loft = Loft(cs, rw, rt, rt, tang, 8,
                    bulge=lambda i, th: 0.10 * math.cos(3 * th) * (1 if 2 < i < 9 else 0))
        jt = [(0.0, 'TailBase'), (0.08, name + '_1'), (0.28, name + '_1'), (0.40, name + '_2'),
              (0.62, name + '_2'), (0.74, name + '_3')]
        loft.build(md, 'tail', lambda i, t, p, jt=jt: blend_chain(t, jt), cap_end=tip, t_range=(0.0, 0.97))
        tails.append((spec, loft, jt))

    # ------------------------------------------------------------ fur clumps
    def clump_on(loft, s, th, part, L, W, flow, wfn, lift=0.5, sink=0.02, thick=0.45):
        p, n, T = loft.point(s, th)
        build_clump(md, part, p, n, flow(p, n, T), L, W, wfn(s, p), lift=lift, sink=sink, thick=thick)

    back_flow = lambda p, n, T: v3(0, 1, -0.25)
    down_back = lambda p, n, T: v3(0, 0.6, -1)
    neck_down = lambda p, n, T: -T + v3(0, 0.35, 0)
    tw = lambda s, p: torso_w(0, s, p)
    nw = lambda s, p: blend_chain(s, neck_j)
    hw = lambda s, p: {'Head': 1.0}

    # neck mane - big layered clumps flowing down / back
    for s, L in ((0.90, 0.20), (0.68, 0.23), (0.46, 0.24), (0.24, 0.22)):
        for deg in (0, 45, -45, 95, -95):
            clump_on(neck, s, math.radians(deg + (12 if s in (0.68, 0.24) else 0)), 'tuft',
                     L * (0.85 if abs(deg) > 60 else 1), 0.12, neck_down, nw, lift=0.55)
    # chest ruff (front / ventral side of neck, flows down)
    for s, L in ((0.10, 0.17), (0.32, 0.17), (0.54, 0.15)):
        for deg in (180, 145, -145):
            clump_on(neck, s, math.radians(deg), 'tuft', L * 1.15, 0.12, lambda p, n, T: v3(0, 0.1, -1), nw, lift=0.35)
    # head crest and cheek tufts
    for deg in (0, 40, -40):
        clump_on(head, 0.10, math.radians(deg), 'tuft', 0.16, 0.09, back_flow, hw, lift=0.55)
    for sx in (1, -1):
        for s, deg, L in ((0.32, 100, 0.19), (0.24, 128, 0.16), (0.42, 118, 0.13)):
            clump_on(head, s, sx * math.radians(deg), 'tuft_cyan', L, 0.075,
                     lambda p, n, T, sx=sx: v3(sx * 0.9, 0.9, -0.1), hw, lift=0.25)
    # shoulders, elbows, flanks, haunches, belly fringe
    for sx in (1, -1):
        S = '_L' if sx > 0 else '_R'
        for s, deg, L in ((0.84, 62, 0.19), (0.76, 95, 0.19), (0.64, 75, 0.17), (0.52, 100, 0.15), (0.30, 75, 0.16),
                          (0.18, 100, 0.18), (0.08, 70, 0.15), (0.55, 140, 0.15), (0.40, 145, 0.14), (0.70, 150, 0.15),
                          (0.88, 120, 0.17), (0.46, 40, 0.13), (0.20, 35, 0.13)):
            clump_on(torso, s, sx * math.radians(deg), 'tuft', L, 0.11, down_back, tw, lift=0.42)
        # elbow tuft on the back of the front leg; hock tuft
        e = mx(FRONT_LEG[1], sx) + v3(0, 0.045, 0.02)
        build_clump(md, 'tuft', e, v3(0, 1, 0.2), v3(0, 0.6, -1), 0.13, 0.07,
                    {'FrontLegUpper' + S: 0.5, 'FrontLegLower' + S: 0.5}, lift=0.3)
        h = mx(HIND_LEG[0], sx) * 0.4 + mx(HIND_LEG[1], sx) * 0.6 + v3(sx * 0.02, 0.07, 0)
        build_clump(md, 'tuft', h, v3(0, 1, 0.1), v3(0, 0.5, -1), 0.14, 0.08, {'HindLegUpper' + S: 1.0}, lift=0.3)
        # jagged fur at the purple / cyan boundary of each leg (spikes pointing down)
        for leg, t_b, bone in ((FRONT_LEG, 0.62, 'FrontLegLower' + S), (HIND_LEG, 0.62, 'HindLegLower' + S)):
            a, b = mx(leg[1], sx), mx(leg[2], sx)
            c = a + (b - a) * t_b
            for ang in (0, 120, 240):
                dirn = v3(math.sin(math.radians(ang)) * sx, math.cos(math.radians(ang)), 0)
                build_clump(md, 'tuft', c + dirn * 0.045, dirn, norm(b - a), 0.09, 0.05, {bone: 1.0}, lift=0.3)
    # dorsal spikes (two tall ones behind the harness + smaller ridge)
    for s, L, W in ((0.42, 0.30, 0.10), (0.62, 0.26, 0.10), (0.26, 0.15, 0.08), (0.78, 0.15, 0.08)):
        p, n, T = torso.point(s, 0.0)
        build_clump(md, 'spike', p, v3(0, 0, 1), v3(0, 1.0, 0.0), L, W, torso_w(0, s, p), lift=1.05, thick=0.35)
    # tail edge clumps (jagged purple -> cyan boundary)
    for spec, loft, jt in tails:
        for s, deg in ((0.50, 90), (0.50, -90), (0.40, 0)):
            p, n, T = loft.point(s, math.radians(deg))
            build_clump(md, 'tail_tuft', p, n, T, 0.13, 0.07, blend_chain(s * 0.97, jt), lift=0.30)

    # ---------------------------------------------------------------- harness
    rope_r = 0.020
    # collar around the neck base
    coll = [neck.point(0.22, TAU * k / 12, rope_r * 1.4)[0] for k in range(12)]
    build_tube(md, 'rope', coll, rope_r, 5, lambda i, t, p: {'Neck1': 0.5, 'Chest': 0.5}, closed=True)
    # girth rope behind the front legs
    girth = [torso.point(0.66, TAU * k / 14, rope_r * 1.2)[0] for k in range(14)]
    build_tube(md, 'rope', girth, rope_r, 5, lambda i, t, p: torso_w(0, 0.66, p), closed=True)
    # two big loops rising over the shoulders (ring around the head seen from the front)
    loops = [(v3(0, -0.14, 1.16), 0.34, 0.40, 0.022, v3(1, 0, 0), norm(v3(0, 0.75, 1.0))),
             (v3(0.0, -0.04, 1.12), 0.31, 0.36, 0.020, norm(v3(1, 0.18, 0)), norm(v3(0, 1.25, 1.0)))]
    for c, rx, ru, rr, Xa, Uax in loops:
        pts = [c + Xa * rx * math.cos(TAU * k / 16) + Uax * ru * math.sin(TAU * k / 16) for k in range(16)]
        build_tube(md, 'rope', pts, rr, 5, lambda i, t, p: {'Chest': 1.0}, closed=True)
    # back strands from collar to girth (tear-drop seen from above)
    for sx in (1, -1):
        a = neck.point(0.22, sx * math.radians(40), rope_r * 1.4)[0]
        pts = [a]
        for s in (0.80, 0.74, 0.68):
            pts.append(torso.point(s, sx * math.radians(18 + (0.80 - s) * 80), rope_r * 1.2)[0])
        build_tube(md, 'rope', pts, rope_r * 0.9, 5, lambda i, t, p: {'Chest': 1.0})
    # chest strands collar -> gem
    gem_p, gem_n, _ = neck.point(0.06, math.pi, 0.055)
    gem_p = gem_p + v3(0, 0, -0.03)
    for sx in (1, -1):
        a = neck.point(0.22, sx * math.radians(125), rope_r * 1.4)[0]
        m = neck.point(0.10, sx * math.radians(155), rope_r * 1.6)[0]
        build_tube(md, 'rope', [a, m, gem_p + v3(sx * 0.03, -0.01, 0.07)], rope_r * 0.9, 5,
                   lambda i, t, p: {'Neck1': 0.4, 'Chest': 0.6})
    # knots
    for p, w in ((neck.point(0.22, 0.0, rope_r * 2.2)[0], {'Neck1': 0.5, 'Chest': 0.5}),
                 (torso.point(0.66, 0.0, rope_r * 2.0)[0], {'Chest': 1.0}),
                 (torso.point(0.74, 0.0, rope_r * 2.0)[0], {'Chest': 1.0})):
        build_sphere(md, 'knot', p, (0.045, 0.038, 0.030), 6, 4, w)
    # chest ornament: diamond frame + gem + dangling beads
    fwd = norm(gem_n * v3(1, 1, 0.3))
    fr_up = v3(0, 0, 1)
    fr_side = v3(1, 0, 0)
    isl = md.new_island('frame')
    first = len(md.faces)
    outline = [(0, 0.125), (0.09, 0.015), (0, -0.095), (-0.09, 0.015)]
    frw = {'Chest': 0.7, 'Neck1': 0.3}
    front = [md.add_vert(gem_p + fr_side * x + fr_up * y - fwd * 0.004, frw) for x, y in outline]
    back = [md.add_vert(gem_p + fr_side * x * 0.9 + fr_up * y * 0.9 - fwd * 0.03, frw) for x, y in outline]
    ctr = md.add_vert(gem_p + fwd * 0.012, frw)
    for k in range(4):
        k2 = (k + 1) % 4
        md.add_face([front[k], front[k2], ctr], [(0.5 + outline[k][0] * 3, 0.5 + outline[k][1] * 3),
                                                 (0.5 + outline[k2][0] * 3, 0.5 + outline[k2][1] * 3), (0.5, 0.5)],
                    [(1, k), (1, k2), (0, 0)], 'frame', isl)
        md.add_face([back[k], back[k2], front[k2], front[k]], [(k / 4, 0), ((k + 1) / 4, 0), ((k + 1) / 4, .2), (k / 4, .2)],
                    [(1, k), (1, k2), (1, k2), (1, k)], 'frame', isl)
    md.orient_piece(first, gem_p - fwd * 0.05)
    build_sphere(md, 'gem', gem_p + fwd * 0.022, (0.052, 0.052, 0.050), 8, 5, frw, axis_up=fwd, axis_side=fr_side)
    for sx in (1, -1):
        bp = gem_p + fr_side * sx * 0.06 + fr_up * -0.05 - fwd * 0.01
        build_tube(md, 'rope', [gem_p + fr_side * sx * 0.06 + fr_up * 0.0, bp], 0.006, 4, lambda i, t, p: frw)
        build_sphere(md, 'bead', bp + v3(0, 0, -0.012), (0.016, 0.016, 0.016), 6, 4, frw)
        build_cone(md, 'tassel', bp + v3(0, 0, -0.03), bp + v3(0, 0, -0.09), 0.014, 5, frw)

    # side tassels (string, 2 beads, tassel)
    for sx in (1, -1):
        S = '_L' if sx > 0 else '_R'
        top = mx(TASSEL_TOP, sx)
        tw_ = {'Tassel' + S: 1.0}
        pts = [top + v3(-sx * 0.03, 0, 0.02), top, top + v3(0, 0, -0.12)]
        build_tube(md, 'rope', pts, 0.008, 4, lambda i, t, p, S=S: {'Chest': 1.0} if i == 0 else {'Tassel' + S: 1.0})
        build_sphere(md, 'bead', top + v3(0, 0, -0.15), (0.030, 0.030, 0.032), 6, 4, tw_)
        build_sphere(md, 'bead', top + v3(0, 0, -0.245), (0.028, 0.028, 0.030), 6, 4, tw_)
        build_tube(md, 'rope', [top + v3(0, 0, -0.18), top + v3(0, 0, -0.215)], 0.007, 4, lambda i, t, p: tw_)
        build_sphere(md, 'tassel', top + v3(0, 0, -0.29), (0.022, 0.022, 0.018), 6, 3, tw_)
        tq = [top + v3(0, 0, -0.29), top + v3(0, 0, -0.34), top + v3(0, 0, -0.43)]
        build_tube(md, 'tassel', tq, 0.024, 6, lambda i, t, p: tw_, radii=[0.022, 0.026, 0.028], cap_ends=True)

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
