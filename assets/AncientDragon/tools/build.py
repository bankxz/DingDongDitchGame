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
    mb.faces.append((list(vidx), uvs, smooth))


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


def cone(base, tip, r, key, bone, n=4, up=None):
    """pointed spike/claw (n-sided pyramid), flat shaded."""
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


def curved_cone(pts, r0, key, bone, n=4):
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
        (6.1, 9.45, 1.2, 1.3, {'Neck2': 1}),
        (6.9, 8.45, 1.35, 1.45, blend('Neck2', 'Neck1', 0.5)),
        (7.8, 7.25, 1.55, 1.65, {'Neck1': 1}),
        (8.7, 6.55, 1.95, 2.05, blend('Neck1', 'Chest', 0.6)),
        (9.8, 5.95, 2.35, 2.45, {'Chest': 1}),
        (11.1, 5.75, 2.5, 2.5, blend('Chest', 'Spine', 0.5)),
        (12.5, 5.65, 2.4, 2.4, {'Spine': 1}),
        (13.9, 5.45, 2.35, 2.3, blend('Spine', 'Hips', 0.5)),
        (15.2, 5.25, 2.3, 2.2, {'Hips': 1}),
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
         [w for *_, w in body], body_col, n=12, p=2.4, cap1=False)

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
            return 'rune_tail'
        if s == 'bottom':
            return B
        return C
    loft(path, radii, wts, tail_col, n=8, p=2.8, cap0=False, cap1=True)
    # tail spikes (pairs, leaning back) and tip cluster
    for i in range(len(tpath) - 1):
        (l0, z0, r0), (l1, z1, r1) = tpath[i], tpath[i + 1]
        lc, zc, rc = (l0 + l1) / 2, (z0 + z1) / 2, (r0 + r1) / 2
        hgt = max(1.1, 2.0 - i * 0.1)
        bn = 'Tail%d' % (i + 1)
        for s in (1, -1):
            cone(P(s * rc * 0.45, lc - 0.2, zc + rc * 0.85), P(s * rc * 0.9, lc + 0.9, zc + rc + hgt),
                 0.45 * max(rc, 0.9), H if i % 2 else G, bn)
    lt, zt, _ = tpath[-1]
    for dl, dz, dx in ((2.2, 0.2, 0.0), (1.6, 1.0, 0.45), (1.6, 1.0, -0.45), (1.5, -0.6, 0.0), (1.2, 0.3, 0.7), (1.2, 0.3, -0.7)):
        cone(P(0, lt - 0.2, zt), P(dx, lt + dl, zt + dz), 0.36, H, 'Tail9')

    # ================= head =================
    hb = 'Head'
    head = [(6.3, 8.75, 1.2, 1.3), (5.4, 8.95, 1.45, 1.45), (4.2, 8.85, 1.4, 1.3),
            (3.0, 8.55, 1.18, 1.08), (2.0, 8.3, 1.02, 0.92), (1.3, 8.15, 0.92, 0.82)]

    def head_col(seg, k, nn, c):
        s = side_of(nn)
        if seg == -2:
            return D
        if s == 'top' and seg <= 1:
            return G
        if s == 'bottom':
            return CR
        return C
    loft([P(0, l, z) for l, z, _, _ in head], [(rx, rz) for _, _, rx, rz in head], [hb] * len(head),
         head_col, n=8, p=2.6, up_hint=(0, 0, 1))
    jaw = [(5.2, 7.45, 1.05, 0.45), (3.4, 7.2, 0.95, 0.42), (1.3, 7.0, 0.72, 0.34)]
    loft([P(0, l, z) for l, z, _, _ in jaw], [(rx, rz) for _, _, rx, rz in jaw], ['Jaw'] * 3,
         lambda s, k, nn, c: CR if nn.z > 0.5 else C, n=8, p=2.6)
    for s in (1, -1):
        # fangs & teeth (cream)
        cone(P(s * 0.55, 1.25, 7.95), P(s * 0.6, 1.1, 5.8), 0.32, H, hb)
        cone(P(s * 0.8, 2.3, 7.75), P(s * 0.82, 2.25, 6.95), 0.17, H, hb)
        cone(P(s * 0.85, 3.2, 7.75), P(s * 0.86, 3.15, 7.15), 0.15, H, hb)
        cone(P(s * 0.5, 1.6, 7.2), P(s * 0.5, 1.65, 7.75), 0.14, H, 'Jaw')
        # gold brow ridge + cheek stripe, glowing eye and cheek slit
        loft([P(s * 0.95, 2.7, 9.35), P(s * 1.25, 4.0, 9.7), P(s * 1.2, 5.4, 9.85)], [(0.28, 0.2)] * 3, [hb] * 3,
             solid(G), n=4, p=2.0, smooth=False)
        loft([P(s * 1.08, 1.4, 8.25), P(s * 1.38, 3.6, 8.3), P(s * 1.42, 5.6, 8.5)], [(0.12, 0.2)] * 3, [hb] * 3,
             solid(G), n=4, p=2.0, smooth=False)
        loft([P(s * 1.28, 3.3, 9.05), P(s * 1.4, 4.5, 9.12)], [(0.1, 0.22)] * 2, [hb] * 2, solid(GL), n=4, p=2.0, smooth=False)
        loft([P(s * 1.36, 4.6, 9.05), P(s * 1.38, 5.6, 8.95)], [(0.06, 0.1)] * 2, [hb] * 2, solid(GL), n=4, p=2.0, smooth=False)
        # great crescent horns (cream)
        curved_cone([P(s * 0.85, 5.0, 9.6), P(s * 1.3, 5.5, 10.9), P(s * 1.8, 6.3, 11.7), P(s * 2.1, 7.2, 12.3),
                     P(s * 2.1, 8.2, 12.6), P(s * 1.95, 9.3, 12.35), P(s * 1.7, 10.2, 11.9)], 0.72, H, hb, n=6)
        # swept-back lower horn (cream)
        curved_cone([P(s * 1.15, 5.7, 8.7), P(s * 1.9, 6.9, 9.3), P(s * 2.5, 8.2, 10.1), P(s * 2.8, 9.4, 11.2)],
                    0.55, H, hb, n=6)
        # gold crown horns fanning back
        curved_cone([P(s * 0.6, 5.6, 9.9), P(s * 0.95, 6.5, 11.1), P(s * 1.1, 7.6, 11.9), P(s * 1.05, 8.4, 12.2)],
                    0.45, G, hb, n=4)
        curved_cone([P(s * 1.3, 5.9, 9.3), P(s * 2.2, 7.0, 10.4), P(s * 2.9, 7.9, 11.0)], 0.42, G, hb, n=4)
        curved_cone([P(s * 1.25, 6.1, 8.3), P(s * 2.1, 7.4, 8.3), P(s * 2.7, 8.3, 8.8)], 0.4, G, hb, n=4)
    cone(P(0, 4.6, 9.9), P(0, 5.4, 12.2), 0.34, G, hb)                                # central crest
    cone(P(0, 3.2, 9.4), P(0, 3.9, 10.4), 0.26, G, hb)

    # enlarge + lift the head cluster about the neck joint (reference head reads bigger)
    piv = P(0, 6.4, 8.6)
    for i, wd in enumerate(mb.w):
        if set(wd) <= {'Head', 'Jaw'}:
            mb.co[i] = piv + (mb.co[i] - piv) * 1.12 + Vector((0, -0.2, 1.5))

    # ================= neck / back spikes =================
    for l, z, bn, hgt in ((7.0, 9.35, 'Neck2', 1.1), (8.1, 8.8, 'Neck1', 1.3), (9.6, 8.3, 'Chest', 1.6),
                          (11.1, 8.15, 'Chest', 1.8), (12.6, 8.0, 'Spine', 1.7), (14.1, 7.7, 'Spine', 1.5),
                          (15.5, 7.4, 'Hips', 1.3)):
        cone(P(0, l, z - 0.2), P(0, l + 0.9, z + hgt), 0.55, G, bn)
        for s in (1, -1):
            cone(P(s * 1.2, l + 0.2, z - 0.5), P(s * 1.9, l + 1.0, z + hgt * 0.65), 0.42, H, bn)

    # ================= chest shield =================
    extrude_poly([(x * 0.85, 1.2 + z * 0.8) for x, z in SHIELD], P(0, 7.35, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0), 0.7, G, 'Chest', front_key='rune_chest')

    # ================= front legs =================
    def front_leg(s, sf):
        ua, fa, hd = 'UpperArm' + sf, 'Forearm' + sf, 'Hand' + sf
        prism(P(s * 4.45, 9.8, 5.4), (s, 0, 0), 1.85, 0.6, 12, G, ua, cap_key='rune_disc', rot=math.pi / 12)
        pth = [P(s * 3.0, 9.9, 6.3), P(s * 3.35, 9.6, 4.6), P(s * 3.6, 9.2, 3.0), P(s * 3.75, 8.8, 2.0), P(s * 3.85, 8.5, 0.9)]
        rad = [(1.2, 1.5), (1.35, 1.45), (1.3, 1.3), (1.15, 1.15), (1.05, 1.05)]
        wt = [{ua: 1}, {ua: 1}, blend(ua, fa, 0.5), {fa: 1}, blend(fa, hd, 0.5)]
        loft(pth, rad, wt, lambda seg, k, nn, c: G if seg == 2 else C, n=8, p=2.6, up_hint=(0, -1, 0))
        # pauldron over the shoulder (gold)
        loft([P(s * 2.6, 11.0, 7.3), P(s * 3.2, 9.8, 7.5), P(s * 3.4, 8.6, 7.0)], [(1.0, 0.55), (1.15, 0.65), (0.9, 0.5)],
             [{ua: 1}] * 3, solid(G), n=8, p=2.4)
        # knee plate with rune (hex prism facing forward/out)
        prism(P(s * 4.35, 8.6, 2.4), (s * 0.55, -0.83, 0), 0.95, 0.45, 6, G, fa, cap_key='rune_knee', rot=math.pi / 6)
        # foot + claws
        loft([P(s * 3.9, 9.2, 0.6), P(s * 3.95, 8.1, 0.62), P(s * 3.95, 6.9, 0.5)], [(1.2, 0.65), (1.35, 0.68), (1.2, 0.55)],
             [{hd: 1}] * 3, lambda seg, k, nn, c: G if nn.z > 0.6 else C, n=8, p=2.8)
        for dx in (-0.78, -0.26, 0.26, 0.78):
            x = s * (3.95 + dx * 1.2)
            curved_cone([P(x, 6.9, 0.6), P(x, 6.0, 0.55), P(x * 1.0, 5.1, 0.05)], 0.34, H, hd, n=4)
        curved_cone([P(s * 3.95, 9.4, 0.6), P(s * 3.95, 9.8, 0.4), P(s * 3.95, 10.2, 0.08)], 0.2, H, hd, n=4)
    front_leg(1, '_L'); front_leg(-1, '_R')

    # ================= rear legs =================
    def rear_leg(s, sf):
        th, sh, ft = 'Thigh' + sf, 'Shin' + sf, 'Foot' + sf
        prism(P(s * 4.4, 14.6, 4.8), (s, 0, 0), 2.0, 0.6, 12, G, th, cap_key='rune_disc', rot=math.pi / 12)
        pth = [P(s * 2.7, 14.9, 5.8), P(s * 3.1, 14.2, 4.1), P(s * 3.3, 13.5, 2.7), P(s * 3.4, 14.2, 1.7), P(s * 3.45, 14.8, 0.9)]
        rad = [(1.35, 1.7), (1.4, 1.55), (1.3, 1.3), (1.1, 1.1), (1.0, 1.0)]
        wt = [{th: 1}, {th: 1}, blend(th, sh, 0.5), {sh: 1}, blend(sh, ft, 0.5)]
        loft(pth, rad, wt, lambda seg, k, nn, c: G if seg == 2 else C, n=8, p=2.6, up_hint=(0, -1, 0))
        prism(P(s * 4.2, 13.0, 2.6), (s * 0.55, -0.83, 0), 0.9, 0.45, 6, G, sh, cap_key='rune_knee', rot=math.pi / 6)
        loft([P(s * 3.45, 15.3, 0.6), P(s * 3.45, 14.1, 0.62), P(s * 3.45, 12.9, 0.5)], [(1.15, 0.65), (1.3, 0.68), (1.15, 0.55)],
             [{ft: 1}] * 3, lambda seg, k, nn, c: G if nn.z > 0.6 else C, n=8, p=2.8)
        for dx in (-0.6, 0.0, 0.6):
            x = s * (3.45 + dx * 1.2)
            curved_cone([P(x, 12.9, 0.6), P(x, 12.0, 0.55), P(x, 11.1, 0.05)], 0.33, H, ft, n=4)
    rear_leg(1, '_L'); rear_leg(-1, '_R')

    # ================= wings =================
    def wing(s, sf):
        w1b, w2b = 'Wing1' + sf, 'Wing2' + sf
        X = lambda p: P(p[0] * s, p[1], p[2])
        # arm (shoulder -> wrist), gold
        loft([X(W_ROOT), X(lerp(W_ROOT, W_WRIST, 0.5)), X(W_WRIST)], [(0.55, 0.55), (0.5, 0.5), (0.5, 0.5)],
             [{w1b: 1}] * 3, solid(G), n=6, p=2.2)
        # leading edge: thick gold tube with a charcoal ridge on top
        lead = [X(p) for p in resample(W_LEAD, 9)]
        lr = [(0.55, 0.5)] * 8 + [(0.3, 0.3)]
        loft(lead, lr, [{w2b: 1}] * 9, solid(G), n=6, p=2.2)
        ridge = [q + Vector((0.12 * s, 0, 0.55)) for q in lead[:-1]]
        loft(ridge, [(0.28, 0.28)] * len(ridge), [{w2b: 1}] * len(ridge), solid(C), n=6, p=2.2)
        cone(lead[-1], lead[-1] + (lead[-1] - lead[-2]).normalized() * 1.7, 0.3, H, w2b)
        # three curved spars with cream claw tips
        for i in range(3):
            sp = [X(p) for p in spar_path(i, 5)]
            loft(sp, [(0.42, 0.38)] * 4 + [(0.3, 0.3)], [{w2b: 1}] * 5, solid(G), n=6, p=2.2)
            cone(sp[-1], sp[-1] + (sp[-1] - sp[-2]).normalized() * 1.4, 0.26, H, w2b)
        # glowing drips under the scallops
        for i in range(3):
            q = X(scallop(i))
            cone(q + Vector((0, 0, 0.25)), q + Vector((0, 0.2, -0.9)), 0.2, GL, w2b)
        # membrane: billowed strips between (edge/spar) pairs, double sided
        K = 6
        edges = [inner_edge(K + 1)] + [resample(spar_path(i, 9), K + 1) for i in range(3)] + [resample(W_LEAD, K + 1)]
        # the inner panel starts at the root (edge 0) but the spar at the wrist; others share the wrist
        nrm = Vector((0.84 * s, -0.41, -0.33)).normalized()
        for off, flip in ((0.05, False), (-0.05, True)):
            cache = {}

            def vid(pt3, wt):
                key = tuple(round(x, 4) for x in pt3)
                if key not in cache:
                    cache[key] = mb.vert(pt3, wt)
                return cache[key]
            for pi in range(4):
                A, Bp = edges[pi], edges[pi + 1]
                grid = []
                for j in range(K + 1):
                    a, b = A[j], Bp[j]
                    mid = scallop(pi - 1) if (j == K and pi >= 1) else lerp(a, b, 0.5)
                    t = j / K
                    bil = math.sin(math.pi * min(1.0, t * 1.1)) * 0.7
                    row = []
                    for c, (pt, bw) in enumerate(((a, 0.0), (mid, 1.0), (b, 0.0))):
                        wt = {w2b: 1.0}
                        if pi == 0 and c < 2 and j < 3:
                            wt = blend(w1b, w2b, j / 3 + (0.3 if c == 1 else 0.0))
                        v3 = X(pt) + nrm * (off + bil * bw)
                        row.append((vid(v3, wt), pt))
                    grid.append(row)
                for j in range(K):
                    for c in range(2):
                        q = [grid[j][c], grid[j][c + 1], grid[j + 1][c + 1], grid[j + 1][c]]
                        ids, uvs = [], []
                        for v, p in q:
                            if v not in ids:
                                ids.append(v); uvs.append(wing_uv(p))
                        if len(ids) < 3:
                            continue
                        pts = [mb.co[i] for i in ids]
                        n_, _, _ = face_basis(pts)
                        if n_.length < 0.5:
                            continue
                        if (n_.dot(nrm) > 0) == flip:
                            ids = ids[::-1]; uvs = uvs[::-1]
                        mb.faces.append((ids, uvs, True))
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
    'Neck2': ((0, 7.2, 7.8), (0, 6.2, 9.4), 'Neck1'),
    'Head': ((0, 6.2, 9.4), (0, 1.0, 9.6), 'Neck2'),
    'Jaw': ((0, 5.2, 8.6), (0, 1.3, 8.3), 'Head'),
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
        eb.head = P(h[0], h[1], lf(h[2])); eb.tail = P(t[0], t[1], lf(t[2])); eb.roll = 0.0
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
    lift_all()
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
    assert tris < 5000, tris
    import animate
    animate.make_actions(rig)
    out = os.path.join(ROOT, 'AncientDragon.blend')
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print('saved', out)


if __name__ == '__main__':
    main()
