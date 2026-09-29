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


def tile_uv(pts, key, u, v):
    """map a face into its colour swatch; extents snapped to whole stud cells."""
    ox, oy = SWATCH[key][0] * SW, SWATCH[key][1] * SW
    cu = [p.dot(u) for p in pts]; cv = [p.dot(v) for p in pts]
    u0, v0 = min(cu), min(cv)
    eu, ev = (max(cu) - u0) / CELL_U, (max(cv) - v0) / CELL_U
    iu, iv = min(CELLS, max(1, round(eu))), min(CELLS, max(1, round(ev)))
    su, sv = iu / max(eu, 1e-6), iv / max(ev, 1e-6)
    offu = rnd.randint(0, CELLS - iu); offv = rnd.randint(0, CELLS - iv)
    uv = []
    for a, b in zip(cu, cv):
        px = ox + MARGIN + (offu + (a - u0) / CELL_U * su) * CELL_PX
        py = oy + MARGIN + (offv + iv - (b - v0) / CELL_U * sv) * CELL_PX
        uv.append((px / ATLAS, 1 - py / ATLAS))
    return uv


def decal_uv(pts, key, u, v):
    ox, oy = SWATCH[key][0] * SW, SWATCH[key][1] * SW
    cu = [p.dot(u) for p in pts]; cv = [p.dot(v) for p in pts]
    u0, v0, u1, v1 = min(cu), min(cv), max(cu), max(cv)
    return [((ox + MARGIN + (a - u0) / max(u1 - u0, 1e-6) * (SW - 2 * MARGIN)) / ATLAS,
             1 - (oy + MARGIN + (1 - (b - v0) / max(v1 - v0, 1e-6)) * (SW - 2 * MARGIN)) / ATLAS)
            for a, b in zip(cu, cv)]


def add_poly(vidx, key, smooth=False, uvs=None, decal_pts=None):
    pts = [mb.co[i] for i in vidx]
    if uvs is None:
        n, u, v = face_basis(pts)
        if key.startswith('rune'):
            uvs = decal_uv(pts, key, u, v)
        else:
            uvs = tile_uv(pts, key, u, v)
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


def cone_smooth(base, tip, r, key, bone, n=4, up=None):
    """pointed spike/claw (n-sided pyramid), flat shaded."""
    mb.new_part()
    base, tip = Vector(base), Vector(tip)
    ax = (tip - base).normalized()
    upv = Vector(up) if up is not None else (Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((0, -1, 0)))
    sd = ax.cross(upv).normalized(); upv = sd.cross(ax).normalized()
    ids = [mb.vert(base + (sd * math.cos(2 * math.pi * k / n + math.pi / n) + upv * math.sin(2 * math.pi * k / n + math.pi / n)) * r, bone)
           for k in range(n)]
    tv = mb.vert(tip, bone)
    ctr = base + (tip - base) * 0.3
    for k in range(n):
        add_poly(outward([ids[k], ids[(k + 1) % n], tv], ctr), key)
    add_poly(outward(ids[:], tip), key)


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


def vblock(p0, p1, w, h, key, bone, up=None, taper=1.0, skip_start=False):
    """cube-style block between p0 and p1 (final-atlas UVs, flat shaded, not voxelized)."""
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0).normalized()
    upv = Vector(up) if up is not None else (Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((0, -1, 0)))
    sd = ax.cross(upv).normalized(); upv = sd.cross(ax).normalized()
    ring = lambda p, sc: [p + sd * sx * w / 2 * sc + upv * sy * h / 2 * sc for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    c8 = ring(p0, 1.0) + ring(p1, taper)
    ids = [mb.vert(q, bone) for q in c8]
    ctr = (p0 + p1) / 2
    for q in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        if skip_start and q == (0, 1, 2, 3):
            continue
        f = outward([ids[i] for i in q], ctr)
        pts = [mb.co[i] for i in f]
        n, u, v = face_basis(pts)
        mb.faces.append((f, tile_uv_vox(pts, key, u, v), False)); mb.fkey.append(key); mb.fpart.append(mb.part)


def cube_chain(pts, w0, w1, key, bone, seg=1.0):
    """stepped chain of studded cubes along a curve, tapering w0 -> w1 (reference horn/spike style)."""
    mb.new_part(direct=True)
    pts = [Vector(p) for p in pts]
    L = sum((q - p).length for p, q in zip(pts, pts[1:]))
    n = max(1, min(6, int(round(L / seg))))
    tp = [tuple(p) for p in pts]
    rs = [Vector(p) for p in resample(tp, n + 1)] if len(pts) > 2 else [pts[0].lerp(pts[1], k / n) for k in range(n + 1)]
    for k in range(n):
        t = k / max(1, n)
        w = w0 + (w1 - w0) * t
        last = k == n - 1
        vblock(rs[k], rs[k + 1], w, w, key, bone, taper=0.55 if last else 0.92, skip_start=True)


def cone(base, tip, r, key, bone, n=4, up=None):
    cube_chain([base, tip], max(0.36, 2.2 * r), max(0.25, 1.1 * r), key, bone)


def curved_cone(pts, r0, key, bone, n=4):
    cube_chain(pts, max(0.36, 2.0 * r0), max(0.22, 0.6 * r0), key, bone)


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


def curved_cone_smooth(pts, r0, key, bone, n=4):
    """multi-segment tapered horn/claw along pts, radius r0 -> 0."""
    path = [Vector(p) for p in pts]
    m = len(path)
    radii = [(r0 * (1 - i / (m - 1)) + 0.04,) * 2 for i in range(m)]
    loft(path[:-1], radii[:-1], [bone] * (m - 1), solid(key), n=n, p=2.0, smooth=False, tip1=False, cap1=False)
    # tip fan
    rings_start = len(mb.co) - (m - 1) * n
    last = list(range(rings_start + (m - 2) * n, rings_start + (m - 1) * n))
    tv = mb.vert(path[-1], bone)
    for k in range(n):
        add_poly(outward([last[k], last[(k + 1) % n], tv], path[-2]), key)


def prism(center, axis, radius, thick, n, key, bone, cap_key=None, rot=0.0):
    mb.new_part()
    axis = Vector(axis).normalized(); c = Vector(center)
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((0, 1, 0))
    e1 = (ref - axis * ref.dot(axis)).normalized(); e2 = axis.cross(e1)
    ring = lambda off: [c + axis * off + (e1 * math.cos(2 * math.pi * i / n + rot) + e2 * math.sin(2 * math.pi * i / n + rot)) * radius for i in range(n)]
    ia = [mb.vert(q, bone) for q in ring(thick / 2)]; ib = [mb.vert(q, bone) for q in ring(-thick / 2)]
    add_poly(outward(ia[:], c), cap_key or key)
    add_poly(outward(ib[:], c), key)
    for i in range(n):
        j = (i + 1) % n
        add_poly(outward([ia[i], ia[j], ib[j], ib[i]], c), key)


def extrude_poly(pts2d, frame_o, ex, ez, depth_dir, depth, key, bone, front_key=None):
    """flat polygon (x,z in a local frame) extruded along depth_dir."""
    mb.new_part()
    o = Vector(frame_o); ex = Vector(ex); ez = Vector(ez); dd = Vector(depth_dir)
    f = [mb.vert(o + ex * x + ez * z, bone) for x, z in pts2d]
    b = [mb.vert(o + ex * x + ez * z + dd * depth, bone) for x, z in pts2d]
    ctr = o + dd * depth / 2 + ex * (sum(x for x, _ in pts2d) / len(pts2d)) + ez * (sum(z for _, z in pts2d) / len(pts2d))
    add_poly(outward(f[:], ctr), front_key or key)
    add_poly(outward(b[:], ctr), key)
    n = len(pts2d)
    for i in range(n):
        j = (i + 1) % n
        add_poly(outward([f[i], f[j], b[j], b[i]], ctr), key)


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
         [w for *_, w in body], body_col, n=12, p=2.4, cap1=True)

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
    loft(path, radii, wts, tail_col, n=8, p=2.8, cap0=True, cap1=True)
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

    # ================= head: studded blocks + stepped horn crown (built directly, not voxelized) =================
    hb, jb = 'Head', 'Jaw'
    mb.new_part(direct=True)

    def blk(x0, x1, l0, l1, z0, z1, key, bone=hb):
        vblock(P((x0 + x1) / 2, (l0 + l1) / 2, z0), P((x0 + x1) / 2, (l0 + l1) / 2, z1), x1 - x0, l1 - l0, key, bone)

    def sblk(x0, x1, l0, l1, z0, z1, key, bone=hb):
        for s in (1, -1):
            blk(min(s * x0, s * x1), max(s * x0, s * x1), l0, l1, z0, z1, key, bone)
    SL = 'slate'
    # skull: blunt dark snout tip -> mid head -> rear skull
    blk(-0.85, 0.85, 0.7, 3.0, 7.75, 8.95, D)             # snout
    blk(-0.75, 0.75, 1.0, 3.2, 8.95, 9.35, SL)            # snout top plate
    blk(-0.55, 0.55, 0.55, 1.1, 8.3, 9.05, D)             # nose tip
    blk(-1.1, 1.1, 2.8, 4.8, 7.7, 9.8, C)                 # mid head
    blk(-1.2, 1.2, 4.6, 6.4, 7.8, 10.1, C)                # rear skull
    # gold brow, crest strip and cheek band
    sblk(0.55, 1.28, 3.0, 4.7, 9.6, 10.1, G)
    blk(-0.38, 0.38, 1.6, 3.4, 9.3, 9.7, G)
    blk(-0.4, 0.4, 3.3, 5.9, 9.75, 10.35, G)
    sblk(1.05, 1.35, 3.3, 5.6, 8.35, 8.85, G)
    sblk(1.05, 1.4, 4.9, 6.3, 7.85, 8.4, CR)              # cream cheek plate
    sblk(0.8, 0.98, 2.1, 2.8, 8.25, 8.7, 'teal')          # teal accent cube on the snout side
    sblk(1.05, 1.2, 2.9, 3.5, 8.9, 9.3, SL)
    # glowing eyes + glow slit low on the snout
    sblk(1.08, 1.32, 3.55, 4.35, 9.1, 9.5, GL)
    sblk(0.83, 0.95, 1.25, 1.6, 7.8, 8.55, GL)
    # cream tooth line under the upper jaw
    sblk(0.55, 0.95, 1.0, 3.6, 7.35, 7.78, CR)
    # lower jaw (small, dark) with cream inner teeth
    blk(-0.8, 0.8, 1.5, 4.8, 6.75, 7.35, C, jb)
    sblk(0.45, 0.78, 1.6, 3.0, 7.35, 7.6, CR, jb)
    # big fangs hanging at the front + side teeth
    for s in (1, -1):
        cube_chain([P(s * 0.58, 1.1, 7.75), P(s * 0.6, 1.05, 6.8), P(s * 0.62, 1.0, 5.8)], 0.42, 0.24, H, hb, seg=0.7)
        cube_chain([P(s * 0.82, 2.6, 7.6), P(s * 0.84, 2.6, 6.95)], 0.3, 0.2, H, hb, seg=0.7)
        # crown: big cream crescent horn sweeping back then curling up
        cube_chain([P(s * 1.0, 5.3, 9.9), P(s * 1.6, 6.4, 10.5), P(s * 2.1, 7.6, 11.1), P(s * 2.3, 8.8, 11.8),
                    P(s * 2.1, 9.8, 12.8), P(s * 1.7, 10.4, 13.8)], 0.85, 0.3, H, hb, seg=1.05)
        # two gold horns above it
        cube_chain([P(s * 0.65, 4.9, 10.2), P(s * 0.95, 6.2, 10.8), P(s * 1.1, 7.5, 11.2), P(s * 1.15, 8.6, 11.7)],
                   0.6, 0.25, G, hb, seg=1.35)
        cube_chain([P(s * 0.95, 5.8, 10.0), P(s * 1.4, 7.2, 10.3), P(s * 1.65, 8.5, 10.7), P(s * 1.7, 9.5, 11.2)],
                   0.55, 0.22, G, hb, seg=1.35)
        # lower cream horn pointing straight back
        cube_chain([P(s * 1.15, 5.9, 8.95), P(s * 1.65, 7.2, 9.1), P(s * 2.05, 8.6, 9.6), P(s * 2.2, 9.7, 10.4)],
                   0.62, 0.24, H, hb, seg=1.35)
        # gold cheek frill
        cube_chain([P(s * 1.3, 6.0, 8.2), P(s * 1.95, 7.2, 7.95), P(s * 2.35, 8.2, 8.4)], 0.5, 0.22, G, hb, seg=0.8)
    # tall gold forehead crest (front view)
    cube_chain([P(0, 4.9, 10.2), P(0, 5.4, 11.1), P(0, 5.9, 11.8)], 0.55, 0.28, G, hb, seg=0.8)

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
        loft(pth, rad, wt, lambda seg, k, nn, c: G if seg == 2 else C, n=8, p=2.6, up_hint=(0, -1, 0))
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
        loft(pth, rad, wt, lambda seg, k, nn, c: G if seg == 2 else C, n=8, p=2.6, up_hint=(0, -1, 0))
        art_plate(P(s * 4.05, 12.8, 2.6), (s * 0.55, -0.83, 0), (0, 0, 1), 'knee', 0.4, 0.35, sh)
        loft([P(s * 3.45, 15.3, 0.6), P(s * 3.45, 14.1, 0.62), P(s * 3.45, 12.9, 0.5)], [(1.15, 0.65), (1.3, 0.68), (1.15, 0.55)],
             [{ft: 1}] * 3, lambda seg, k, nn, c: G if nn.z > 0.6 else C, n=8, p=2.8)
        for dx in (-0.6, 0.0, 0.6):
            x = s * (3.45 + dx * 1.6)
            curved_cone([P(x, 12.9, 0.6), P(x, 12.0, 0.5), P(x, 11.0, 0.1)], 0.28, H, ft, n=4)
    rear_leg(1, '_L'); rear_leg(-1, '_R')

    # ================= wings: stepped studded membrane + gold cube-chain spars =================
    def wing(s, sf):
        w1b, w2b = 'Wing1' + sf, 'Wing2' + sf
        nl = Vector(wing_plane_normal()); N = Vector((nl.x * s, nl.y, nl.z))
        def W3(a, b, off=0.0):
            q = wing_plane_pt(a, b); return P(q[0] * s, q[1], q[2]) + N * off
        def proj(p):
            return wing2d(p)
        def chain(pts2d, w, h, key, bone, seg=1.7, stagger=0.0, off=0.0, taper_last=None):
            poly = resample(pts2d, max(2, int(round(sum(math.dist(p, q) for p, q in zip(pts2d, pts2d[1:])) / seg)) + 1))
            for k, (p, q) in enumerate(zip(poly, poly[1:])):
                d = Vector((q[0] - p[0], q[1] - p[1])).normalized(); perp = Vector((-d.y, d.x))
                sh = perp * (stagger if k % 2 else -stagger)
                a0, b0 = p[0] + sh.x - d.x * 0.1, p[1] + sh.y - d.y * 0.1
                a1, b1 = q[0] + sh.x + d.x * 0.1, q[1] + sh.y + d.y * 0.1
                tp = taper_last if (taper_last and k == len(poly) - 2) else 1.0
                vblock(W3(a0, b0, off), W3(a1, b1, off), w, h, key, bone, up=N, taper=tp)
        root2 = proj(W_ROOT); wr2 = proj(W_WRIST)
        mb.new_part(direct=True)
        chain([root2, wr2], 1.0, 0.9, G, w1b, seg=3.0)
        lead2 = [proj(p) for p in W_LEAD]
        chain(lead2, 1.0, 0.85, G, w2b, seg=3.0, stagger=0.08)
        ridge = []
        for k, p in enumerate(lead2):
            q = lead2[min(k + 1, len(lead2) - 1)]; o = lead2[max(k - 1, 0)]
            d = Vector((q[0] - o[0], q[1] - o[1])).normalized(); perp = Vector((-d.y, d.x))
            if perp.y < 0: perp = -perp
            ridge.append((p[0] + perp.x * 0.75, p[1] + perp.y * 0.75))
        chain(ridge[:-1], 0.6, 0.7, C, w2b, seg=4.5)
        tips2 = [proj(p) for p in W_TIPS]
        for i in range(3):
            sp = [proj(p) for p in spar_path(i, 7)]
            chain(sp, 0.75, 0.7, G, w2b, seg=2.3, stagger=0.1)
        # stepped cream claws at every tip (two cube tiers)
        for i in range(4):
            src = [proj(p) for p in (spar_path(i, 7) if i < 3 else W_LEAD)]
            p, q = Vector(src[-2]), Vector(src[-1]); d = (q - p).normalized()
            t1 = q + d * 0.9; t2 = t1 + d * 0.9
            vblock(W3(*q), W3(*t2), 0.6, 0.6, H, w2b, up=N, taper=0.45)
        # glowing drips below the scallops
        for i in range(3):
            q = proj(scallop(i))
            vblock(W3(q[0], q[1] + 0.1), W3(q[0] + 0.1, q[1] - 0.9), 0.35, 0.3, GL, w2b, up=N, taper=0.5)
        # membrane rows (stepped outline), double sided, UVs into the painted row
        a0, b0, NA, NB, c = wing_grid()
        cells = wing_cells()
        for j in range(NB):
            i = 0
            while i < NA:
                if (i, j) not in cells:
                    i += 1; continue
                i1 = i
                while (i1 + 1, j) in cells:
                    i1 += 1
                aa, ab = a0 + i * c, a0 + (i1 + 1) * c
                ba, bb = b0 + j * c, b0 + (j + 1) * c
                px0, px1 = i * CELL_PX, (i1 + 1) * CELL_PX
                py0, py1 = WING_ROW_Y + (NB - 1 - j) * CELL_PX, WING_ROW_Y + (NB - j) * CELL_PX
                uv = [(px0 / ATLAS, 1 - py1 / ATLAS), (px1 / ATLAS, 1 - py1 / ATLAS),
                      (px1 / ATLAS, 1 - py0 / ATLAS), (px0 / ATLAS, 1 - py0 / ATLAS)]
                corners = [(aa, ba), (ab, ba), (ab, bb), (aa, bb)]
                for off in (0.04, -0.04):
                    ids = []
                    for ca, cb in corners:
                        wt = {w1b: 1.0} if ca < 1.0 else ({w1b: 0.5, w2b: 0.5} if ca < 3.0 else {w2b: 1.0})
                        ids.append(mb.vert(W3(ca, cb, off), wt))
                    uvs = list(uv)
                    n_, _, _ = face_basis([mb.co[k] for k in ids])
                    if (n_.dot(N) > 0) != (off > 0):
                        ids = ids[::-1]; uvs = uvs[::-1]
                    mb.faces.append((ids, uvs, False)); mb.fkey.append('wing'); mb.fpart.append(mb.part)
                i = i1 + 1
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
    import voxel
    keep = [i for i, p in enumerate(mb.fpart) if p not in mb.direct]
    vco, vw, vfaces, info = voxel.voxelize(mb.co, [mb.faces[i] for i in keep], [mb.fkey[i] for i in keep],
                                           [mb.fpart[i] for i in keep], mb.open, mb.w)
    remap = {}
    for i, p in enumerate(mb.fpart):
        if p in mb.direct:
            ids, uvs, sm = mb.faces[i]
            nid = []
            for q in ids:
                if q not in remap:
                    vco.append(mb.co[q]); vw.append(mb.w[q]); remap[q] = len(vco) - 1
                nid.append(remap[q])
            vfaces.append((nid, uvs, False))
    print('VOXELS grid', info[:3], 'filled', info[3], 'quads', len(vfaces))
    mb.co, mb.w, mb.faces = vco, vw, vfaces
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
