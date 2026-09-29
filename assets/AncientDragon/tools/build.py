"""Build the Ancient Dragon v2: rounded lofted forms + stud-texture atlas, rig, animate.

Run: python3.11 build.py      (Blender 4.2 as the `bpy` module)
Geometry is lofted along landmark paths measured from the reference sheet
(side view -> L/Z, front view -> X widths). See QUALITY_LOOP_REPORT.md.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from spec import *

ROOT = os.path.abspath(os.path.join(HERE, '..'))
TEX = os.path.join(ROOT, 'textures')
L0 = 15.0            # design L that maps to blender y=0
SCALE = 0.25         # design unit -> metres
rnd = random.Random(3)
C, G, CR, H, GL, T, D, B = 'charcoal', 'gold', 'cream', 'horn', 'glow', 'teal', 'dark', 'belly'


def P(X, L, Z):
    return Vector((X, L - L0, Z))


def PV(t):
    return P(*t)


# ------------------------------------------------------------------ mesh builder
class MB:
    def __init__(self):
        self.co, self.w, self.faces = [], [], []   # faces: (vidx, uvs, smooth)
        self.fkey, self.fpart, self.part, self.open, self.direct = [], [], 0, set(), set()
        self.skull_part, self.eyes = None, []

    def new_part(self, open_=False, direct=False):
        self.part += 1
        if open_:
            self.open.add(self.part)
        if direct:
            self.direct.add(self.part)

    def vert(self, p, bone):
        self.co.append(Vector(p))
        self.w.append(dict(bone) if isinstance(bone, dict) else {bone: 1.0})
        return len(self.co) - 1


mb = MB()


def face_basis(pts):
    n = Vector((0, 0, 0))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
    if n.length < 1e-9:
        n = Vector((0, 0, 1))
    n.normalize()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.85 else Vector((0, -1, 0))
    v = (up - n * up.dot(n)).normalized()
    u = v.cross(n).normalized()
    return n, u, v


def add_poly(vidx, key, smooth=False, uvs=None):
    pts = [mb.co[i] for i in vidx]
    if uvs is None:
        n, u, v = face_basis(pts)
        uvs = tile_uv_vox(pts, key, u, v)
    mb.faces.append((list(vidx), uvs, smooth)); mb.fkey.append(key); mb.fpart.append(mb.part)


def outward(ids, ref):
    """return ids ordered so the face normal points away from ref point."""
    pts = [mb.co[i] for i in ids]
    n, _, _ = face_basis(pts)
    c = sum(pts, Vector()) / len(pts)
    return ids if n.dot(c - ref) >= 0 else ids[::-1]


# ------------------------------------------------------------------ loft
def squircle(n, rx, rz, p=2.6, rot=None):
    rot = math.pi / n if rot is None else rot
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n + rot
        c, s = math.cos(a), math.sin(a)
        out.append((rx * math.copysign(abs(c) ** (2 / p), c), rz * math.copysign(abs(s) ** (2 / p), s)))
    return out


def loft(path, radii, weights, color_fn, n=8, p=2.6, smooth=True, up_hint=(0, 0, 1),
         cap0=True, cap1=True, tip1=False, tip0=False):
    """Loft rings along `path` (blender Vectors).  radii[i]=(rx, rz); weights[i]=bone dict;
    color_fn(seg, k, normal, centre) -> swatch key (seg = ring-pair index, -1/-2 = caps)."""
    mb.new_part()
    m = len(path)
    tans = []
    for i in range(m):
        a = path[max(i - 1, 0)]; b = path[min(i + 1, m - 1)]
        tans.append((b - a).normalized())
    up = Vector(up_hint)
    rings = []
    for i in range(m):
        t = tans[i]
        up = (up - t * up.dot(t))
        if up.length < 1e-4:
            up = Vector((0, -1, 0)) - t * t.y * -1
        up.normalize()
        sd = t.cross(up).normalized()
        rx, rz = radii[i]
        ring = [path[i] + sd * x + up * z for x, z in squircle(n, rx, rz, p)]
        rings.append([mb.vert(q, weights[i]) for q in ring])
    for i in range(m - 1):
        ctr = (path[i] + path[i + 1]) / 2
        for k in range(n):
            q = [rings[i][k], rings[i][(k + 1) % n], rings[i + 1][(k + 1) % n], rings[i + 1][k]]
            q = outward(q, ctr)
            pts = [mb.co[j] for j in q]
            nn, _, _ = face_basis(pts)
            add_poly(q, color_fn(i, k, nn, sum(pts, Vector()) / 4), smooth)
    if tip1:
        tv = mb.vert(path[-1] + tans[-1] * max(radii[-1]) * 1.6, weights[-1])
        for k in range(n):
            f = outward([rings[-1][k], rings[-1][(k + 1) % n], tv], path[-1] - tans[-1])
            add_poly(f, color_fn(-2, k, Vector((0, 0, 1)), mb.co[tv]), smooth)
    elif cap1:
        add_poly(outward(rings[-1][:], path[-1] - tans[-1]), color_fn(-2, 0, tans[-1], path[-1]), False)
    if tip0:
        tv = mb.vert(path[0] - tans[0] * max(radii[0]) * 1.6, weights[0])
        for k in range(n):
            f = outward([rings[0][k], rings[0][(k + 1) % n], tv], path[0] + tans[0])
            add_poly(f, color_fn(-1, k, Vector((0, 0, 1)), mb.co[tv]), smooth)
    elif cap0:
        add_poly(outward(rings[0][:], path[0] + tans[0]), color_fn(-1, 0, -tans[0], path[0]), False)
    return rings


def solid(key):
    return lambda s, k, nn, c: key


def tile_uv_vox(pts, key, u, v):
    """final-atlas tiling: whole VOX_CELL_U cubes inside the colour's swatch."""
    ox, oy = VOX_SWATCH[key][0] * SW, VOX_SWATCH[key][1] * SW
    cu = [p.dot(u) for p in pts]; cv = [p.dot(v) for p in pts]
    u0, v0 = min(cu), min(cv)
    eu, ev = (max(cu) - u0) / VOX_CELL_U, (max(cv) - v0) / VOX_CELL_U
    iu, iv = min(CELLS, max(1, round(eu))), min(CELLS, max(1, round(ev)))
    su, sv = iu / max(eu, 1e-6), iv / max(ev, 1e-6)
    offu = rnd.randint(0, CELLS - iu); offv = rnd.randint(0, CELLS - iv)
    return [((ox + MARGIN + (offu + (a - u0) / VOX_CELL_U * su) * CELL_PX) / ATLAS,
             1 - (oy + MARGIN + (offv + iv - (b - v0) / VOX_CELL_U * sv) * CELL_PX) / ATLAS) for a, b in zip(cu, cv)]


def horn(pts, r0, r1, key, bone, nseg=4, n=6, rib=0.08, tip=True):
    """smooth tapered horn/spike/claw made of slightly stepped segments (the reference's ribbed horns)."""
    path = [Vector(p) for p in resample([tuple(p) for p in pts], nseg + 1)]
    for k in range(nseg):
        ra = r0 + (r1 - r0) * k / nseg
        rb = r0 + (r1 - r0) * (k + 0.85) / nseg
        last = k == nseg - 1
        loft([path[k], path[k + 1]], [(ra * (1 + rib),) * 2, (rb,) * 2], [bone, bone], solid(key), n=n, p=2.0,
             smooth=True, cap0=k == 0, cap1=last and not tip, tip1=last and tip)


def cone(base, tip, r, key, bone, n=4, up=None):
    horn([base, tip], r, r * 0.45, key, bone, nseg=2, n=n)


def curved_cone(pts, r0, key, bone, n=4):
    horn(pts, r0, r0 * 0.35, key, bone, nseg=2, n=n)


def eyeball(c, axis, r, bone, seg=8, rings=5):
    """UV sphere looking along `axis`; planar UVs put the painted iris + slit pupil on the front."""
    c = Vector(c); ax = Vector(axis).normalized()
    up = Vector((0, 0, 1)); rt = up.cross(ax).normalized(); up = ax.cross(rt).normalized()
    ex, ey, ew, eh = EYE_REGION
    def uv(p):
        d = (p - c) / r
        return ((ex + (0.5 + d.dot(rt) * 0.5) * ew) / ATLAS, 1 - (ey + (0.5 - d.dot(up) * 0.5) * eh) / ATLAS)
    mb.new_part(direct=True)
    grid = []
    for i in range(1, rings):
        th = math.pi * i / rings
        grid.append([mb.vert(c + (ax * math.cos(th) + (rt * math.cos(2 * math.pi * j / seg) + up * math.sin(2 * math.pi * j / seg)) * math.sin(th)) * r, bone)
                     for j in range(seg)])
    front = mb.vert(c + ax * r, bone); back = mb.vert(c - ax * r, bone)
    def face(ids):
        ids = outward(ids, c)
        add_poly(ids, 'glow', True, [uv(mb.co[q]) for q in ids])
    for j in range(seg):
        k = (j + 1) % seg
        face([front, grid[0][j], grid[0][k]])
        face([back, grid[-1][k], grid[-1][j]])
        for i in range(rings - 2):
            face([grid[i][j], grid[i][k], grid[i + 1][k], grid[i + 1][j]])


PLATE_SHAPES = {
    'oct': [(2, 0), (6, 0), (8, 2), (8, 6), (6, 8), (2, 8), (0, 6), (0, 2)],
    'shield': [(0, 0), (7, 0), (7, 5), (3.5, 8), (0, 5)],
}


def art_plate(center, normal, up, name, cell, thick, bone, shape=None):
    """studded pixel-art plate (direct geometry): front face UV-locked to the painted art cells."""
    mb.new_part(direct=True)
    art = RUNE_ART[name]; H_ = len(art); W_ = len(art[0])
    n = Vector(normal).normalized(); u = Vector(up); u = (u - n * u.dot(n)).normalized()
    rt = u.cross(n).normalized(); c = Vector(center)
    poly = PLATE_SHAPES[shape] if shape else [(0, 0), (W_, 0), (W_, H_), (0, H_)]
    ox_, oy_ = RUNE_ORIGIN[name]
    pos = lambda x, y, off: c + rt * (x - W_ / 2) * cell + u * (H_ / 2 - y) * cell + n * off
    front = [mb.vert(pos(x, y, thick), bone) for x, y in poly]
    back = [mb.vert(pos(x, y, 0.0), bone) for x, y in poly]
    uvf = [((ox_ + x * CELL_PX) / ATLAS, 1 - (oy_ + y * CELL_PX) / ATLAS) for x, y in poly]
    ctr = c + n * thick * 0.5
    ids = outward(front[:], ctr)
    uvs = uvf if ids == front else uvf[::-1]
    mb.faces.append((ids, uvs, False)); mb.fkey.append('rune'); mb.fpart.append(mb.part)
    for ring in ():
        f = outward(ring[:], ctr); pts = [mb.co[i] for i in f]; nn, uu, vv = face_basis(pts)
        mb.faces.append((f, tile_uv_vox(pts, 'gold', uu, vv), False)); mb.fkey.append('gold'); mb.fpart.append(mb.part)
    m = len(poly)
    for i in range(m):
        j = (i + 1) % m
        f = outward([front[i], front[j], back[j], back[i]], ctr); pts = [mb.co[q] for q in f]
        nn, uu, vv = face_basis(pts)
        mb.faces.append((f, tile_uv_vox(pts, 'gold', uu, vv), False)); mb.fkey.append('gold'); mb.fpart.append(mb.part)


def blend(b0, b1, t):
    if b0 == b1 or t <= 0.0:
        return {b0: 1.0}
    if t >= 1.0:
        return {b1: 1.0}
    return {b0: 1.0 - t, b1: t}


def side_of(nn):
    return 'side' if abs(nn.x) > 0.7 else ('bottom' if nn.z < -0.55 else ('top' if nn.z > 0.55 else ('front' if nn.y < -0.6 else 'other')))


# ------------------------------------------------------------------ geometry
def build():
    # ================= neck + torso (one rounded loft) =================
    body = [  # L, Z, rx, rz, weights
        (5.9, 10.3, 1.35, 1.4, {'Neck2': 1}),
        (6.8, 9.0, 1.5, 1.6, blend('Neck2', 'Neck1', 0.5)),
        (7.8, 7.25, 1.55, 1.65, {'Neck1': 1}),
        (8.7, 6.5, 2.3, 2.35, blend('Neck1', 'Chest', 0.6)),
        (9.8, 5.9, 2.95, 2.8, {'Chest': 1}),
        (11.1, 5.75, 3.1, 2.9, blend('Chest', 'Spine', 0.5)),
        (12.5, 5.65, 3.0, 2.8, {'Spine': 1}),
        (13.9, 5.45, 2.9, 2.65, blend('Spine', 'Hips', 0.5)),
        (15.2, 5.25, 2.75, 2.5, {'Hips': 1}),
        (16.4, 4.75, 2.05, 2.05, blend('Hips', 'Tail1', 0.35)),
    ]

    def body_col(seg, k, nn, c):
        L = c.y + L0
        s = side_of(nn)
        if seg < 0:
            return C
        if s == 'bottom' or (L < 9.2 and (nn.y < -0.35 or nn.z < -0.2)):
            return CR if L < 9.2 else B
        if s == 'top' and seg in (4, 5, 7, 8):
            return G                                     # gold back armour plates
        return C
    loft([P(0, l, z) for l, z, *_ in body], [(rx, rz) for _, _, rx, rz, _ in body],
         [w for *_, w in body], body_col, n=16, p=2.3, cap1=True)

    # ================= tail: segments with gold bands, side runes =================
    tpath = [(16.4, 4.75, 2.05), (18.4, 4.05, 1.9), (20.5, 3.4, 1.75), (22.6, 2.95, 1.62), (24.7, 2.7, 1.5),
             (26.8, 2.65, 1.38), (28.9, 2.8, 1.25), (31.0, 3.1, 1.1), (33.0, 3.5, 0.95), (34.7, 3.95, 0.75)]
    tb = TAIL_BONES
    path, radii, wts, kinds = [], [], [], []
    for i in range(len(tpath) - 1):
        (l0, z0, r0), (l1, z1, r1) = tpath[i], tpath[i + 1]
        bn = 'Tail%d' % (i + 1)
        prev = 'Tail%d' % i if i > 0 else 'Hips'
        for t, rs, kind in ((0.0, 1.13, 'band'), (0.2, 1.13, 'step'), (0.24, 1.0, 'body')):
            l = l0 + (l1 - l0) * t; z = z0 + (z1 - z0) * t; r = r0 + (r1 - r0) * t
            path.append(P(0, l, z)); radii.append((r * rs, r * rs * 1.05)); kinds.append(kind)
            wts.append(blend(prev, bn, 0.5) if t == 0.0 else {bn: 1.0})
    l, z, r = tpath[-1]
    path.append(P(0, l, z)); radii.append((r, r)); wts.append({'Tail9': 1.0}); kinds.append('end')

    def tail_col(seg, k, nn, c):
        if seg < 0:
            return C
        kd = kinds[seg]
        if kd in ('band', 'step'):
            return G
        s = side_of(nn)
        if abs(nn.x) > 0.9:
            return C
        if s == 'bottom':
            return B
        return C
    loft(path, radii, wts, tail_col, n=10, p=2.4, cap0=True, cap1=True)
    # tail spikes (pairs, leaning back) and tip cluster
    for i in range(len(tpath) - 1):
        (l0, z0, r0), (l1, z1, r1) = tpath[i], tpath[i + 1]
        lc, zc, rc = (l0 + l1) / 2, (z0 + z1) / 2, (r0 + r1) / 2
        for s in (1, -1):
            cl = min(0.42, rc * 0.36)
            art_plate(P(s * (rc * 1.02 + 0.05), lc + 0.1, zc), (s, 0, 0), (0, 0, 1), 'tail', cl, 0.28, 'Tail%d' % (i + 1))
        hgt = max(1.1, 2.0 - i * 0.1)
        bn = 'Tail%d' % (i + 1)
        for s in (1, -1):
            if s == 1:
                cone(P(0, lc - 0.2, zc + rc * 0.8), P(0, lc + 0.9, zc + rc + hgt), 0.45 * max(rc, 0.9), H if i % 2 else G, bn)
    lt, zt, _ = tpath[-1]
    for dl, dz, dx in ((2.2, 0.2, 0.0), (1.6, 1.0, 0.55), (1.6, 1.0, -0.55)):
        cone(P(0, lt - 0.2, zt), P(dx, lt + dl, zt + dz), 0.36, H, 'Tail9')

    # ================= head: rounded skull with carved eye canals, ribbed horn crown =================
    hb, jb = 'Head', 'Jaw'
    skull = [(6.4, 9.0, 1.15, 1.2), (5.4, 9.05, 1.25, 1.25), (4.2, 8.9, 1.18, 1.1),
             (3.0, 8.6, 0.98, 0.92), (1.8, 8.35, 0.86, 0.78), (0.8, 8.25, 0.76, 0.62)]

    def skull_col(seg, k, nn, c):
        if seg < 0:
            return D
        if nn.z < -0.55:
            return CR
        if nn.z > 0.6 and c.y + L0 < 2.6:
            return 'slate'
        return C
    loft([P(0, l, z) for l, z, _, _ in skull], [(rx, rz) for _, _, rx, rz in skull], [hb] * len(skull),
         skull_col, n=12, p=2.8)
    mb.skull_part = mb.part

    def strip(pts, rx, rz, key, bone=hb, n=6):
        loft([P(*q) for q in pts], [(rx, rz)] * len(pts), [bone] * len(pts), solid(key), n=n, p=2.2)
    strip([(0, 1.5, 9.05), (0, 3.0, 9.48), (0, 4.4, 9.98), (0, 5.7, 10.25)], 0.3, 0.12, G)       # crest strip
    jaw = [(5.2, 7.35, 1.02, 0.5), (3.4, 7.1, 0.92, 0.45), (1.4, 6.95, 0.72, 0.38)]
    loft([P(0, l, z) for l, z, _, _ in jaw], [(rx, rz) for _, _, rx, rz in jaw], [jb] * 3,
         lambda s, k, nn, c: CR if nn.z > 0.5 else C, n=8, p=2.4)
    mb.eyes = []
    for s in (1, -1):
        strip([(s * 0.75, 2.8, 9.5), (s * 1.18, 3.8, 9.7), (s * 1.15, 5.0, 9.75)], 0.22, 0.17, G)   # brow ridge
        strip([(s * 1.1, 3.2, 8.45), (s * 1.2, 4.6, 8.5), (s * 1.18, 5.8, 8.65)], 0.12, 0.2, G)     # cheek band
        strip([(s * 1.1, 5.0, 8.05), (s * 1.12, 6.3, 8.15)], 0.14, 0.3, CR)                         # cheek plate
        strip([(s * 0.8, 1.15, 8.1), (s * 0.84, 1.75, 8.15)], 0.08, 0.12, GL)                      # snout glow slit
        strip([(s * 0.66, 1.0, 7.8), (s * 0.72, 2.3, 7.78), (s * 0.78, 3.6, 7.8)], 0.12, 0.16, CR)   # tooth row
        horn([P(s * 0.58, 1.1, 7.85), P(s * 0.6, 1.05, 6.9), P(s * 0.62, 0.95, 6.0)], 0.2, 0.06, H, hb, nseg=2)
        horn([P(s * 0.8, 2.5, 7.75), P(s * 0.82, 2.5, 7.1)], 0.13, 0.05, H, hb, nseg=1, n=5)
        # eye canal (carved in main) + eyeball with painted slit pupil
        axis = Vector((s * 0.94, -0.34, 0.0)).normalized()
        surf = P(s * 1.13, 3.95, 9.12)
        mb.eyes.append((mb.vert(surf, hb), mb.vert(surf + axis, hb)))
        eyeball(surf - axis * 0.2, axis, 0.3, hb)
        # great cream crescent horn: back, up, curling in at the tip
        horn([P(s * 0.85, 5.1, 9.8), P(s * 1.45, 5.9, 10.9), P(s * 1.95, 6.8, 11.9), P(s * 2.1, 7.8, 12.7),
              P(s * 1.95, 8.7, 13.5), P(s * 1.5, 9.3, 14.3)], 0.62, 0.12, H, hb, nseg=5, n=7)
        # gold crown horns behind the brow
        horn([P(s * 0.55, 4.6, 10.1), P(s * 0.8, 5.6, 11.0), P(s * 0.95, 6.8, 11.6), P(s * 1.0, 7.9, 12.2)],
             0.3, 0.07, G, hb, nseg=4)
        horn([P(s * 1.0, 5.6, 9.9), P(s * 1.45, 6.9, 10.35), P(s * 1.7, 8.2, 10.8), P(s * 1.8, 9.2, 11.4)],
             0.28, 0.06, G, hb, nseg=4)
        # lower cream horn swept straight back
        horn([P(s * 1.15, 5.9, 8.95), P(s * 1.65, 7.2, 9.1), P(s * 2.0, 8.6, 9.55), P(s * 2.15, 9.7, 10.3)],
             0.34, 0.07, H, hb, nseg=4)
        # gold cheek frill spikes
        horn([P(s * 1.25, 6.0, 8.3), P(s * 1.85, 7.1, 8.05), P(s * 2.25, 8.1, 8.4)], 0.24, 0.05, G, hb, nseg=3, n=5)
    horn([P(0, 4.9, 10.2), P(0, 5.35, 11.1), P(0, 5.9, 11.9)], 0.28, 0.06, G, hb, nseg=3, n=5)     # forehead crest

    # enlarge + lift the head cluster about the neck joint (reference head reads bigger)
    piv = P(0, 6.4, 8.6)
    for i, wd in enumerate(mb.w):
        if set(wd) <= {'Head', 'Jaw'}:
            mb.co[i] = piv + (mb.co[i] - piv) * 1.32 + Vector((0, -0.4, 2.2))

    # ================= neck / back spikes =================
    for l, z, bn, hgt in ((7.0, 9.35, 'Neck2', 1.1), (8.1, 8.8, 'Neck1', 1.3), (9.6, 8.3, 'Chest', 1.6),
                          (11.1, 8.15, 'Chest', 1.8), (12.6, 8.0, 'Spine', 1.7), (14.1, 7.7, 'Spine', 1.5),
                          (15.5, 7.4, 'Hips', 1.3)):
        cone(P(0, l, z - 0.2), P(0, l + 0.9, z + hgt), 0.55, G, bn)

    # ================= chest shield =================
    art_plate(P(0, 6.55, 3.7), (0, -1, 0), (0, 0, 1), 'chest', 0.5, 0.5, 'Chest', shape='shield')

    # ================= front legs =================
    def front_leg(s, sf):
        ua, fa, hd = 'UpperArm' + sf, 'Forearm' + sf, 'Hand' + sf
        art_plate(P(s * 4.2, 9.8, 5.4), (s, 0, 0), (0, 0, 1), 'disc', 0.52, 0.5, ua, shape='oct')
        pth = [P(s * 3.0, 9.9, 6.3), P(s * 3.35, 9.6, 4.6), P(s * 3.6, 9.2, 3.0), P(s * 3.75, 8.8, 2.0), P(s * 3.85, 8.5, 0.9)]
        rad = [(1.2, 1.5), (1.35, 1.45), (1.3, 1.3), (1.15, 1.15), (1.05, 1.05)]
        wt = [{ua: 1}, {ua: 1}, blend(ua, fa, 0.5), {fa: 1}, blend(fa, hd, 0.5)]
        loft(pth, rad, wt, lambda seg, k, nn, c: G if seg == 2 else C, n=10, p=2.3, up_hint=(0, -1, 0))
        # pauldron over the shoulder (gold)
        loft([P(s * 2.6, 11.0, 7.3), P(s * 3.2, 9.8, 7.5), P(s * 3.4, 8.6, 7.0)], [(1.0, 0.55), (1.15, 0.65), (0.9, 0.5)],
             [{ua: 1}] * 3, solid(G), n=8, p=2.4)
        # knee plate with rune (hex prism facing forward/out)
        art_plate(P(s * 4.25, 8.35, 2.5), (s * 0.55, -0.83, 0), (0, 0, 1), 'knee', 0.4, 0.35, fa)
        # foot + claws
        loft([P(s * 3.9, 9.2, 0.6), P(s * 3.95, 8.1, 0.62), P(s * 3.95, 6.9, 0.5)], [(1.2, 0.65), (1.35, 0.68), (1.2, 0.55)],
             [{hd: 1}] * 3, lambda seg, k, nn, c: G if nn.z > 0.6 else C, n=8, p=2.8)
        for dx in (-0.62, 0.0, 0.62):
            x = s * (3.95 + dx * 1.6)
            curved_cone([P(x, 6.9, 0.6), P(x, 6.0, 0.5), P(x * 1.0, 5.0, 0.1)], 0.28, H, hd, n=4)
        curved_cone([P(s * 3.95, 9.4, 0.6), P(s * 3.95, 9.8, 0.4), P(s * 3.95, 10.2, 0.08)], 0.2, H, hd, n=4)
    front_leg(1, '_L'); front_leg(-1, '_R')

    # ================= rear legs =================
    def rear_leg(s, sf):
        th, sh, ft = 'Thigh' + sf, 'Shin' + sf, 'Foot' + sf
        art_plate(P(s * 4.2, 14.6, 4.7), (s, 0, 0), (0, 0, 1), 'disc', 0.58, 0.5, th, shape='oct')
        pth = [P(s * 2.7, 14.9, 5.8), P(s * 3.1, 14.2, 4.1), P(s * 3.3, 13.5, 2.7), P(s * 3.4, 14.2, 1.7), P(s * 3.45, 14.8, 0.9)]
        rad = [(1.35, 1.7), (1.4, 1.55), (1.3, 1.3), (1.1, 1.1), (1.0, 1.0)]
        wt = [{th: 1}, {th: 1}, blend(th, sh, 0.5), {sh: 1}, blend(sh, ft, 0.5)]
        loft(pth, rad, wt, lambda seg, k, nn, c: G if seg == 2 else C, n=10, p=2.3, up_hint=(0, -1, 0))
        art_plate(P(s * 4.05, 12.8, 2.6), (s * 0.55, -0.83, 0), (0, 0, 1), 'knee', 0.4, 0.35, sh)
        loft([P(s * 3.45, 15.3, 0.6), P(s * 3.45, 14.1, 0.62), P(s * 3.45, 12.9, 0.5)], [(1.15, 0.65), (1.3, 0.68), (1.15, 0.55)],
             [{ft: 1}] * 3, lambda seg, k, nn, c: G if nn.z > 0.6 else C, n=8, p=2.8)
        for dx in (-0.6, 0.0, 0.6):
            x = s * (3.45 + dx * 1.6)
            curved_cone([P(x, 12.9, 0.6), P(x, 12.0, 0.5), P(x, 11.0, 0.1)], 0.28, H, ft, n=4)
    rear_leg(1, '_L'); rear_leg(-1, '_R')

    # ================= wings: ribbed gold spars + smooth-outline studded membrane =================
    def wing(s, sf):
        w1b, w2b = 'Wing1' + sf, 'Wing2' + sf
        nl = Vector(wing_plane_normal()); N = Vector((nl.x * s, nl.y, nl.z))
        X = lambda p: P(p[0] * s, p[1], p[2])
        def W3(a, b, off=0.0):
            q = wing_plane_pt(a, b); return X(q) + N * off
        horn([X(W_ROOT), X(W_WRIST)], 0.5, 0.45, G, w1b, nseg=2, tip=False)
        horn([X(p) for p in W_LEAD], 0.5, 0.3, G, w2b, nseg=5, tip=False)
        rim = []
        for k, p in enumerate(W_LEAD[:-1]):
            q2 = wing2d(p); rim.append(W3(q2[0], q2[1] + 0.4))
        horn(rim, 0.3, 0.2, C, w2b, nseg=3, n=5, tip=False)
        for i in range(3):
            horn([X(p) for p in spar_path(i, 5)], 0.36, 0.24, G, w2b, nseg=3, n=5, tip=False)
        for i in range(4):
            src = spar_path(i, 5) if i < 3 else W_LEAD
            p, q = X(src[-2]), X(src[-1]); d = (q - p).normalized()
            horn([q, q + d * 1.5], 0.26, 0.06, H, w2b, nseg=1, n=5)
        for i in range(3):
            q = X(scallop(i))
            horn([q + Vector((0, 0, 0.2)), q + Vector((0, 0.2, -0.9))], 0.17, 0.05, GL, w2b, nseg=1, n=4)
        a0, b0, NA, NB, c = wing_grid()
        outline = wing_outline_2d()[:-1]
        uvs = [((a - a0) / c * CELL_PX / ATLAS, 1 - (WING_ROW_Y + (NB - (b - b0) / c) * CELL_PX) / ATLAS) for a, b in outline]
        mb.new_part(direct=True)
        for off in (0.04, -0.04):
            ids = []
            for a, b in outline:
                wt = {w1b: 1.0} if a < 1.0 else ({w1b: 0.5, w2b: 0.5} if a < 3.0 else {w2b: 1.0})
                ids.append(mb.vert(W3(a, b, off), wt))
            uv = list(uvs)
            n_, _, _ = face_basis([mb.co[k] for k in ids])
            if (n_.dot(N) > 0) != (off > 0):
                ids = ids[::-1]; uv = uv[::-1]
            mb.faces.append((ids, uv, False)); mb.fkey.append('wing'); mb.fpart.append(mb.part)
    wing(1, '_L'); wing(-1, '_R')


# ------------------------------------------------------------------ armature
TAIL_PTS = [(16.4, 4.75), (18.4, 4.05), (20.5, 3.4), (22.6, 2.95), (24.7, 2.7), (26.8, 2.65), (28.9, 2.8),
            (31.0, 3.1), (33.0, 3.5), (36.4, 4.2)]
TAIL_BONES = ['Tail%d' % (i + 1) for i in range(9)]
BONES = {
    'Root': ((0, 15.0, 0.0), (0, 13.0, 0.0), None),
    'Hips': ((0, 15.8, 5.2), (0, 13.2, 5.5), 'Root'),
    'Spine': ((0, 13.2, 5.5), (0, 10.8, 5.75), 'Hips'),
    'Chest': ((0, 10.8, 5.75), (0, 8.4, 6.8), 'Spine'),
    'Neck1': ((0, 8.4, 6.8), (0, 7.2, 7.8), 'Chest'),
    'Neck2': ((0, 7.2, 7.8), (0, 6.0, 10.3), 'Neck1'),
    'Head': ((0, 6.0, 10.3), (0, 0.5, 10.6), 'Neck2'),
    'Jaw': ((0, 5.0, 9.4), (0, 1.0, 9.1), 'Head'),
}
for s, sf in ((1, '_L'), (-1, '_R')):
    BONES.update({
        'UpperArm' + sf: ((s * 3.0, 9.9, 6.3), (s * 3.6, 9.2, 3.0), 'Chest'),
        'Forearm' + sf: ((s * 3.6, 9.2, 3.0), (s * 3.85, 8.5, 0.9), 'UpperArm' + sf),
        'Hand' + sf: ((s * 3.85, 8.5, 0.9), (s * 3.95, 6.4, 0.5), 'Forearm' + sf),
        'Thigh' + sf: ((s * 2.7, 14.9, 5.8), (s * 3.3, 13.5, 2.7), 'Hips'),
        'Shin' + sf: ((s * 3.3, 13.5, 2.7), (s * 3.45, 14.8, 0.9), 'Thigh' + sf),
        'Foot' + sf: ((s * 3.45, 14.8, 0.9), (s * 3.45, 12.4, 0.5), 'Shin' + sf),
        'Wing1' + sf: ((s * W_ROOT[0], W_ROOT[1], W_ROOT[2]), (s * W_WRIST[0], W_WRIST[1], W_WRIST[2]), 'Chest'),
        'Wing2' + sf: ((s * W_WRIST[0], W_WRIST[1], W_WRIST[2]), (s * 7.5, 20.3, 12.9), 'Wing1' + sf),
    })
for i in range(9):
    BONES['Tail%d' % (i + 1)] = ((0, TAIL_PTS[i][0], TAIL_PTS[i][1]), (0, TAIL_PTS[i + 1][0], TAIL_PTS[i + 1][1]),
                                 'Hips' if i == 0 else 'Tail%d' % i)


LIFT = 1.4
NOLIFT = {'Tail%d' % i for i in range(3, 10)}


def lift_z(z):
    """stretch the legs: everything above the knees rises by LIFT, feet stay planted."""
    return z + LIFT * min(1.0, max(0.0, (z - 0.9) / 2.4))


LEG_SHIFT = 0.55
LEG_BONES = {'UpperArm', 'Forearm', 'Hand', 'Thigh', 'Shin', 'Foot'}


def is_leg(name):
    return name.rsplit('_', 1)[0] in LEG_BONES


def widen_legs():
    for i, wd in enumerate(mb.w):
        lw = sum(x for bn, x in wd.items() if is_leg(bn))
        if lw > 0 and abs(mb.co[i].x) > 0.3:
            mb.co[i].x += math.copysign(LEG_SHIFT * lw, mb.co[i].x)


def lift_all():
    for i, wd in enumerate(mb.w):
        if NOLIFT & set(wd):
            f = 1.0 - sum(w for bn, w in wd.items() if bn in NOLIFT)
            if f <= 0:
                continue
            mb.co[i].z = mb.co[i].z + (lift_z(mb.co[i].z) - mb.co[i].z) * f
        else:
            mb.co[i].z = lift_z(mb.co[i].z)


def carve_eye_canals():
    """boolean-cut an eye canal (elongated socket) into the skull at each eye marker."""
    fids = [i for i, p in enumerate(mb.fpart) if p == mb.skull_part]
    vids = sorted({q for i in fids for q in mb.faces[i][0]})
    vi = {v: k for k, v in enumerate(vids)}
    keys = sorted({mb.fkey[i] for i in fids} | {'dark'})
    me = bpy.data.meshes.new('skull')
    me.from_pydata([tuple(mb.co[v]) for v in vids], [], [[vi[q] for q in mb.faces[i][0]] for i in fids])
    for k in keys:
        me.materials.append(bpy.data.materials.get('k_' + k) or bpy.data.materials.new('k_' + k))
    for poly, i in zip(me.polygons, fids):
        poly.material_index = keys.index(mb.fkey[i])
    sk = bpy.data.objects.new('skull', me); bpy.context.scene.collection.objects.link(sk)
    cutters = []
    for m0, m1 in mb.eyes:
        c0 = mb.co[m0]; ax = mb.co[m1] - c0; hs = ax.length; ax.normalize()
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=1.0)
        cm = bpy.data.meshes.new('cut'); bm.to_mesh(cm); bm.free()
        cm.materials.append(bpy.data.materials['k_dark'])
        cu = bpy.data.objects.new('cut', cm); bpy.context.scene.collection.objects.link(cu)
        cu.location = c0 - ax * 0.12 * hs
        cu.rotation_mode = 'QUATERNION'; cu.rotation_quaternion = ax.to_track_quat('Z', 'Y')
        cu.scale = (0.36 * hs, 0.36 * hs, 0.55 * hs)
        mod = sk.modifiers.new('eye', 'BOOLEAN'); mod.operation = 'DIFFERENCE'; mod.solver = 'EXACT'
        mod.object = cu; mod.material_mode = 'TRANSFER'
        cutters.append(cu)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = sk.evaluated_get(dg); m = ev.to_mesh()
    mats = [ms.name[2:] for ms in m.materials]
    keep = [i for i, p in enumerate(mb.fpart) if p != mb.skull_part]
    mb.faces = [mb.faces[i] for i in keep]; mb.fkey = [mb.fkey[i] for i in keep]; mb.fpart = [mb.fpart[i] for i in keep]
    base = len(mb.co)
    for v in m.vertices:
        mb.vert(v.co.copy(), 'Head')
    for poly in m.polygons:
        ids = [base + q for q in poly.vertices]
        key = mats[poly.material_index] if poly.material_index < len(mats) else 'dark'
        add_poly(ids, key, True)
    carved = sum(1 for poly in m.polygons if mats[poly.material_index] == 'dark')
    print('EYE CANALS carved faces', carved)
    assert carved > 0, 'eye canal boolean produced no socket faces'
    ev.to_mesh_clear()
    for o in cutters + [sk]:
        bpy.data.objects.remove(o)


def compact():
    used = sorted({q for f in mb.faces for q in f[0]})
    idx = {v: k for k, v in enumerate(used)}
    mb.co = [mb.co[v] for v in used]; mb.w = [mb.w[v] for v in used]
    mb.faces = [([idx[q] for q in ids], uvs, sm) for ids, uvs, sm in mb.faces]


def make_armature():
    arm = bpy.data.armatures.new('DragonRig')
    ob = bpy.data.objects.new('DragonRig', arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (h, t, par) in BONES.items():
        eb = arm.edit_bones.new(name)
        lf = (lambda z: z) if name in NOLIFT else lift_z
        sx = (lambda x: x + math.copysign(LEG_SHIFT, x)) if is_leg(name) else (lambda x: x)
        eb.head = P(sx(h[0]), h[1], lf(h[2])); eb.tail = P(sx(t[0]), t[1], lf(t[2])); eb.roll = 0.0
    for name, (h, t, par) in BONES.items():
        if par:
            arm.edit_bones[name].parent = arm.edit_bones[par]
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


# ------------------------------------------------------------------ material
def make_material():
    m = bpy.data.materials.new('AncientDragon_Stud')
    m.use_nodes = True
    nt = m.node_tree; N = nt.nodes; Lk = nt.links
    bsdf = N['Principled BSDF']

    def img(fn, non_color=False):
        n = N.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(os.path.join(TEX, fn))
        if non_color:
            n.image.colorspace_settings.name = 'Non-Color'
        return n
    c = img('AncientDragon_Color_2048.png'); nm = img('AncientDragon_Normal_2048.png', True)
    em = img('AncientDragon_Emission_2048.png', True)
    Lk.new(c.outputs['Color'], bsdf.inputs['Base Color'])
    nmap = N.new('ShaderNodeNormalMap'); Lk.new(nm.outputs['Color'], nmap.inputs['Color'])
    Lk.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    mul = N.new('ShaderNodeMixRGB'); mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    Lk.new(c.outputs['Color'], mul.inputs[1]); Lk.new(em.outputs['Color'], mul.inputs[2])
    Lk.new(mul.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 2.5
    bsdf.inputs['Roughness'].default_value = 0.5
    return m


# ------------------------------------------------------------------ assemble
def assemble():
    me = bpy.data.meshes.new('AncientDragon')
    me.from_pydata([tuple(v) for v in mb.co], [], [f[0] for f in mb.faces])
    me.update()
    uvl = me.uv_layers.new(name='UVMap')
    for poly, (vids, uvs, sm) in zip(me.polygons, mb.faces):
        poly.use_smooth = sm
        for li, uv in zip(poly.loop_indices, uvs):
            uvl.data[li].uv = uv
    ob = bpy.data.objects.new('AncientDragon', me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(make_material())
    groups = {}
    for vi, wd in enumerate(mb.w):
        for bn, wt in wd.items():
            if bn not in groups:
                groups[bn] = ob.vertex_groups.new(name=bn)
            groups[bn].add([vi], wt, 'REPLACE')
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.to_mesh(me); bm.free()
    return ob


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build()
    widen_legs()
    lift_all()
    carve_eye_canals()
    compact()
    ob = assemble()
    rig = make_armature()
    missing = [g.name for g in ob.vertex_groups if g.name not in rig.data.bones]
    assert not missing, missing
    ob.parent = rig
    mod = ob.modifiers.new('Armature', 'ARMATURE'); mod.object = rig
    rig.scale = (SCALE,) * 3
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.select_all(action='DESELECT')
    rig.select_set(True); ob.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    tris = len(ob.data.polygons)
    print('TRIS', tris, 'VERTS', len(ob.data.vertices), 'BONES', len(rig.data.bones))
    assert tris < int(os.environ.get("TRI_LIMIT", 5000)), tris
    import animate
    animate.make_actions(rig)
    out = os.path.join(ROOT, 'AncientDragon.blend')
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('saved', out)


if __name__ == '__main__':
    main()
