"""Build the Ancient Dragon (low-poly boxes + stud-texture atlas), rig, animate, export.

Run: python3.11 build.py      (Blender 4.2 as the `bpy` module)
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Quaternion
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from spec import *

ROOT = os.path.abspath(os.path.join(HERE, '..'))
TEX = os.path.join(ROOT, 'textures')
L0 = 15.0            # design L that maps to blender y=0
SCALE = 0.25         # design unit -> metres
rnd = random.Random(3)

def P(X, L, Z):
    return Vector((X, L - L0, Z))

# ------------------------------------------------------------------ mesh builder
class MB:
    def __init__(self):
        self.co, self.w, self.faces = [], [], []   # faces: (vidx list, uv list)
    def vert(self, p, bone):
        self.co.append(Vector(p)); self.w.append(bone if isinstance(bone, dict) else {bone: 1.0})
        return len(self.co) - 1

mb = MB()

def face_basis(pts):
    n = Vector((0, 0, 0))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
    n.normalize()
    up = Vector((0, 0, 1)) if abs(n.z) < 0.85 else Vector((0, -1, 0))
    v = (up - n * up.dot(n)).normalized()
    u = v.cross(n).normalized()
    return n, u, v

def label_of(n, side):
    ax = max(range(3), key=lambda i: abs(n[i]))
    lab = [('right', 'left'), ('front', 'back'), ('bottom', 'top')][ax][n[ax] > 0]
    if ax == 0 and side != 0:
        return lab, ('out' if (n.x > 0) == (side > 0) else 'in')
    return lab, None

def tile_uv(pts, key, u, v):
    ox, oy = SWATCH[key][0] * SW, SWATCH[key][1] * SW
    cu = [p.dot(u) for p in pts]; cv = [p.dot(v) for p in pts]
    u0, v0 = min(cu), min(cv)
    eu, ev = (max(cu) - u0) / CELL_U, (max(cv) - v0) / CELL_U
    s = min(1.0, (CELLS - 0.01) / max(eu, ev, 1e-6))
    eu, ev = eu * s, ev * s
    offu = rnd.randint(0, max(0, int(CELLS - math.ceil(eu))))
    offv = rnd.randint(0, max(0, int(CELLS - math.ceil(ev))))
    uv = []
    for a, b in zip(cu, cv):
        px = ox + MARGIN + (offu + (a - u0) / CELL_U * s) * CELL_PX
        py = oy + MARGIN + (offv + ev - (b - v0) / CELL_U * s) * CELL_PX
        uv.append((px / ATLAS, 1 - py / ATLAS))
    return uv

def decal_uv(pts, key, u, v):
    ox, oy = SWATCH[key][0] * SW, SWATCH[key][1] * SW
    cu = [p.dot(u) for p in pts]; cv = [p.dot(v) for p in pts]
    u0, v0, u1, v1 = min(cu), min(cv), max(cu), max(cv)
    uv = []
    for a, b in zip(cu, cv):
        px = ox + MARGIN + (a - u0) / max(u1 - u0, 1e-6) * (SW - 2 * MARGIN)
        py = oy + MARGIN + (1 - (b - v0) / max(v1 - v0, 1e-6)) * (SW - 2 * MARGIN)
        uv.append((px / ATLAS, 1 - py / ATLAS))
    return uv

def add_poly(vidx, key, over=None, side=0, uvs=None):
    pts = [mb.co[i] for i in vidx]
    n, u, v = face_basis(pts)
    if uvs is None:
        lab, io = label_of(n, side)
        k = key
        if over:
            k = over.get(lab, over.get(io, key) if io else key)
        uvs = decal_uv(pts, k, u, v) if k.startswith('rune') else tile_uv(pts, k, u, v)
    mb.faces.append((list(vidx), uvs))

def hexa(c8, key, bone, over=None):
    """8 corners: [b0,b1,b2,b3 (start ring), t0..t3 (end ring)] rings in same winding."""
    ctr = sum(c8, Vector()) / 8
    side = 0 if abs(ctr.x) < 0.3 else (1 if ctr.x > 0 else -1)
    ids = [mb.vert(p, bone) for p in c8]
    quads = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    for q in quads:
        pts = [c8[i] for i in q]
        n, _, _ = face_basis(pts)
        fc = sum(pts, Vector()) / 4
        if n.dot(fc - ctr) < 0:
            q = q[::-1]
        add_poly([ids[i] for i in q], key, over, side)

def beam(p0, p1, w, h, key, bone, up=None, taper=1.0, taper_h=None, over=None, w1=None, h1=None):
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0).normalized()
    up = Vector(up) if up is not None else (Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((0, -1, 0)))
    sd = ax.cross(up).normalized(); upv = sd.cross(ax).normalized()
    w1 = w * taper if w1 is None else w1
    h1 = h * (taper if taper_h is None else taper_h) if h1 is None else h1
    ring = lambda p, ww, hh: [p + sd * sx * ww / 2 + upv * sy * hh / 2 for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    hexa(ring(p0, w, h) + ring(p1, w1, h1), key, bone, over)

def block(x0, x1, l0, l1, z0, z1, key, bone, over=None, top_scale=(1, 1)):
    """Axis-aligned block in design coords; top face optionally scaled (x, l)."""
    cx, cl = (x0 + x1) / 2, (l0 + l1) / 2
    hx, hl = (x1 - x0) / 2, (l1 - l0) / 2
    b = [P(cx + sx * hx, cl + sl * hl, z0) for sx, sl in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    t = [P(cx + sx * hx * top_scale[0], cl + sl * hl * top_scale[1], z1) for sx, sl in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    hexa(b + t, key, bone, over)

def mirror(bone):
    return bone.replace('.L', '.R')

def sym(fn, *a, **k):
    """call fn(side=+1,bone suffix .L) and mirrored (side=-1, .R)."""
    fn(1, '.L', *a, **k); fn(-1, '.R', *a, **k)

def prism(center, axis, radius, thick, n, key, bone, cap_key=None, rot=0.0):
    axis = Vector(axis).normalized(); c = Vector(center)
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((0, 1, 0))
    e1 = (ref - axis * ref.dot(axis)).normalized(); e2 = axis.cross(e1)
    ring = lambda off: [c + axis * off + (e1 * math.cos(2 * math.pi * i / n + rot) + e2 * math.sin(2 * math.pi * i / n + rot)) * radius for i in range(n)]
    a, b = ring(thick / 2), ring(-thick / 2)
    ia = [mb.vert(p, bone) for p in a]; ib = [mb.vert(p, bone) for p in b]
    side = 1 if c.x > 0 else -1
    # caps
    for ids, sgn in ((ia, 1), (ib, -1)):
        pts = [mb.co[i] for i in ids]
        nn, _, _ = face_basis(pts)
        if nn.dot(axis * sgn) < 0:
            ids = ids[::-1]
        add_poly(ids, cap_key if (cap_key and sgn > 0) else key, None, side)
    for i in range(n):
        j = (i + 1) % n
        q = [ia[i], ia[j], ib[j], ib[i]]
        pts = [mb.co[x] for x in q]; nn, _, _ = face_basis(pts)
        if nn.dot(sum(pts, Vector()) / 4 - c) < 0:
            q = q[::-1]
        add_poly(q, key, None, side)

# ------------------------------------------------------------------ wing frame
WR = (3.0, 11.0, 7.8)          # design coords of wing root (left side)
A_DIR = Vector((0.47, 0.88, -0.05)).normalized()
B_DIR = Vector((0.0, -0.1, 0.995)).normalized()
N_DIR = A_DIR.cross(B_DIR).normalized()

def wing_pt(a, b, side, off=0.0):
    d = Vector(WR) + A_DIR * a + B_DIR * b + N_DIR * off
    return P(d.x * side, d.y, d.z)

def wing_n(side):
    return Vector((N_DIR.x * side, N_DIR.y, N_DIR.z))

# ------------------------------------------------------------------ geometry
def build():
    C, G, CR, H, GL, T, D, B = 'charcoal', 'gold', 'cream', 'horn', 'glow', 'teal', 'dark', 'belly'

    # ---------------- head ----------------
    hb = 'Head'
    block(-1.25, 1.25, 2.4, 5.4, 7.7, 9.8, C, hb)                                   # skull
    block(-1.0, 1.0, 0.6, 2.6, 7.35, 8.9, C, hb, top_scale=(0.95, 1.0))              # snout
    block(-0.9, 0.9, 0.9, 2.4, 8.9, 9.25, D, hb)                                     # snout top
    block(-0.45, 0.45, 0.9, 5.0, 9.2, 9.75, G, hb)                                   # nose ridge (gold)
    beam(P(0, 4.3, 9.6), P(0, 5.0, 12.4), 0.7, 0.8, G, hb, taper=0.3)                # central crest horn
    block(-0.8, 0.8, 0.5, 1.2, 7.8, 8.7, D, hb)                                      # nostril front
    block(-0.95, 0.95, 1.1, 4.6, 6.8, 7.4, CR, 'Jaw')                                # lower jaw
    block(-1.15, 1.15, 3.2, 5.2, 6.7, 7.7, C, 'Jaw')                                 # jaw hinge
    for s in (1, -1):
        block(s * 0.35 - 0.2, s * 0.35 + 0.2, 1.3, 1.7, 7.4, 7.5, CR, hb)            # filler teeth base
        beam(P(s * 0.62, 1.05, 7.5), P(s * 0.62, 1.05, 5.9), 0.42, 0.42, H, 'Jaw', taper=0.25)  # big fangs
        beam(P(s * 0.85, 2.2, 7.45), P(s * 0.85, 2.2, 6.9), 0.28, 0.28, H, hb, taper=0.3)    # side teeth
        beam(P(s * 0.85, 3.1, 7.45), P(s * 0.85, 3.1, 7.0), 0.26, 0.26, H, hb, taper=0.3)
        block(min(s * 1.05, s * 1.38), max(s * 1.05, s * 1.38), 3.9, 5.7, 8.3, 8.85, G, hb)  # gold cheek armour
        block(min(s * 0.9, s * 1.2), max(s * 0.9, s * 1.2), 0.9, 2.6, 8.9, 9.3, G, hb)  # snout side stripe
        block(min(s * 1.2, s * 1.45), max(s * 1.2, s * 1.45), 2.8, 3.9, 8.85, 9.35, GL, hb)  # eye glow
        block(min(s * 1.25, s * 1.47), max(s * 1.25, s * 1.47), 3.9, 5.2, 8.95, 9.2, GL, hb)  # glow streak
        block(min(s * 0.5, s * 1.35), max(s * 0.5, s * 1.35), 2.6, 4.2, 9.75, 10.15, G, hb)  # brow
        block(min(s * 0.95, s * 1.3), max(s * 0.95, s * 1.3), 1.0, 2.2, 8.05, 8.4, GL, hb)  # snout glow slit
        # great horns (cream), sweeping back/up
        hp = [P(s * 1.0, 4.6, 9.6), P(s * 1.9, 5.6, 11.0), P(s * 2.4, 6.8, 12.2), P(s * 2.2, 8.0, 13.0), P(s * 1.6, 9.2, 13.4)]
        ws = [1.0, 0.85, 0.65, 0.45, 0.2]
        for i in range(4):
            beam(hp[i], hp[i + 1], ws[i], ws[i], H, hb, w1=ws[i + 1], h1=ws[i + 1])
        # secondary horns (gold base -> cream)
        sp = [P(s * 1.3, 5.2, 8.6), P(s * 2.3, 6.6, 9.4), P(s * 2.8, 7.9, 10.5)]
        beam(sp[0], sp[1], 0.7, 0.7, G, hb, w1=0.5, h1=0.5)
        beam(sp[1], sp[2], 0.5, 0.5, H, hb, w1=0.12, h1=0.12)
        # third horn pair sweeping straight back
        mp = [P(s * 1.2, 5.3, 9.2), P(s * 1.9, 6.9, 9.9), P(s * 2.2, 8.3, 10.9)]
        beam(mp[0], mp[1], 0.75, 0.75, H, hb, w1=0.55, h1=0.55)
        beam(mp[1], mp[2], 0.55, 0.55, H, hb, w1=0.12, h1=0.12)
        # small back-of-head frill spikes
        beam(P(s * 0.8, 5.3, 9.3), P(s * 1.4, 6.6, 10.4), 0.5, 0.5, G, hb, taper=0.25)
        beam(P(s * 1.2, 4.9, 8.2), P(s * 2.0, 6.2, 8.0), 0.45, 0.45, G, hb, taper=0.25)

    # enlarge the head cluster ~15% about the neck joint (reference head reads larger)
    piv = P(0, 5.6, 8.4)
    for i, wd in enumerate(mb.w):
        if set(wd) <= {'Head', 'Jaw'}:
            mb.co[i] = piv + (mb.co[i] - piv) * 1.15

    # ---------------- neck ----------------
    block(-1.35, 1.35, 4.9, 7.0, 7.0, 9.4, C, 'Neck2', over={'front': CR, 'bottom': CR})
    block(-1.6, 1.6, 6.1, 8.4, 6.4, 8.8, C, 'Neck1', over={'front': CR, 'bottom': CR})
    block(-1.25, 1.25, 4.6, 6.9, 5.7, 7.2, CR, 'Neck2')                               # throat plates
    block(-1.5, 1.5, 5.6, 8.2, 4.9, 6.6, CR, 'Neck1')
    block(-1.5, 1.5, 6.5, 7.2, 4.0, 6.6, B, 'Chest')
    for l, z, bn in ((5.6, 9.2, 'Neck2'), (7.0, 8.6, 'Neck1')):
        beam(P(0, l, z), P(0, l + 0.9, z + 1.3), 0.6, 0.8, G, bn, taper=0.2)
        sym(lambda s, sf: block(min(s * 1.1, s * 1.5), max(s * 1.1, s * 1.5), l - 0.6, l + 0.6, z - 2.2, z - 0.4, G, bn))

    # ---------------- torso ----------------
    block(-2.5, 2.5, 7.3, 11.0, 3.2, 8.1, C, 'Chest', over={'bottom': B, 'front': CR})
    block(-2.55, 2.55, 10.8, 14.2, 3.1, 7.7, C, 'Spine', over={'bottom': B})
    block(-2.15, 2.15, 13.9, 16.8, 3.5, 7.1, C, 'Hips', over={'bottom': B})
    block(-1.6, 1.6, 7.6, 16.2, 2.95, 3.45, B, 'Spine')                               # belly plates
    # chest shield plate (gold w/ rune), tapered to a point at the bottom
    beam(P(0, 5.35, 5.6), P(0, 5.35, 2.4), 3.6, 0.7, G, 'Chest', up=(0, -1, 0), taper=0.62, taper_h=1.0,
         over={'front': 'rune_chest'})
    beam(P(0, 5.35, 2.42), P(0, 5.35, 1.4), 2.25, 0.7, G, 'Chest', up=(0, -1, 0), taper=0.15, taper_h=1.0)  # shield point
    block(-1.7, 1.7, 5.6, 7.4, 2.6, 5.0, C, 'Chest', over={'front': B})                 # chest filler behind shield
    # gold pauldrons / back armour
    for s in (1, -1):
        block(min(s * 0.9, s * 2.6), max(s * 0.9, s * 2.6), 7.9, 10.4, 7.6, 8.6, G, 'Chest')
        block(min(s * 1.0, s * 2.5), max(s * 1.0, s * 2.5), 11.3, 13.6, 7.3, 8.1, G, 'Spine')
        block(min(s * 1.0, s * 2.3), max(s * 1.0, s * 2.3), 14.4, 16.4, 6.8, 7.6, G, 'Hips')
    # dorsal spikes
    for l, z, bn, hgt in ((8.3, 8.6, 'Chest', 1.4), (9.8, 8.6, 'Chest', 1.6), (11.6, 8.1, 'Spine', 1.7),
                          (13.1, 8.1, 'Spine', 1.5), (14.7, 7.6, 'Hips', 1.4), (16.0, 7.6, 'Hips', 1.2)):
        beam(P(0, l, z - 0.1), P(0, l + 0.8, z + hgt), 0.75, 0.9, G, bn, taper=0.2)
        sym(lambda s, sf: beam(P(s * 1.4, l + 0.2, z - 0.1), P(s * 1.9, l + 0.9, z + hgt * 0.7), 0.55, 0.6, H, bn, taper=0.2))

    # ---------------- front legs ----------------
    def front_leg(s, sf):
        ua, fa, hd = 'UpperArm' + sf, 'Forearm' + sf, 'Hand' + sf
        prism(P(s * 4.0, 9.1, 5.3), (s, 0, 0), 2.1, 0.8, 8, G, ua, cap_key='rune_disc', rot=math.pi / 8)
        beam(P(s * 3.1, 9.1, 6.0), P(s * 3.5, 8.4, 2.4), 2.1, 2.3, C, ua)
        block(min(s * 2.4, s * 4.5), max(s * 2.4, s * 4.5), 8.0, 10.4, 6.6, 7.7, G, ua, top_scale=(0.85, 0.85))  # pauldron
        block(min(s * 2.4, s * 4.3), max(s * 2.4, s * 4.3), 13.6, 15.8, 6.2, 7.1, G, 'Thigh' + sf, top_scale=(0.85, 0.85))
        block(min(s * 2.7, s * 4.5), max(s * 2.7, s * 4.5), 7.1, 8.9, 1.7, 3.5, G, fa, over={'front': 'rune_knee', 'out': 'rune_knee'})
        beam(P(s * 3.5, 8.3, 2.6), P(s * 3.75, 7.6, 0.8), 1.9, 1.9, C, fa)
        block(min(s * 2.65, s * 4.85), max(s * 2.65, s * 4.85), 5.9, 8.3, 0.0, 1.1, C, hd)
        block(min(s * 2.8, s * 4.7), max(s * 2.8, s * 4.7), 6.2, 8.0, 1.1, 1.55, G, hd)
        for dx in (-0.75, -0.25, 0.25, 0.75):
            x = s * (3.75 + dx)
            beam(P(x, 6.3, 0.6), P(x, 4.9, 0.02), 0.48, 0.7, H, hd, taper=0.3)
        beam(P(s * 3.75, 8.2, 0.5), P(s * 3.75, 8.9, 0.05), 0.4, 0.5, H, hd, taper=0.3)   # dew claw
    sym(front_leg)

    # ---------------- rear legs ----------------
    def rear_leg(s, sf):
        th, sh, ft = 'Thigh' + sf, 'Shin' + sf, 'Foot' + sf
        prism(P(s * 3.85, 14.6, 4.5), (s, 0, 0), 2.3, 0.8, 8, G, th, cap_key='rune_disc', rot=math.pi / 8)
        beam(P(s * 2.9, 14.4, 5.0), P(s * 3.2, 13.6, 2.2), 2.2, 2.4, C, th)
        block(min(s * 2.3, s * 4.1), max(s * 2.3, s * 4.1), 12.7, 14.1, 1.4, 3.1, G, sh, over={'front': 'rune_knee', 'out': 'rune_knee'})
        beam(P(s * 3.2, 13.6, 2.4), P(s * 3.2, 14.2, 0.8), 1.9, 1.9, C, sh)
        block(min(s * 2.1, s * 4.3), max(s * 2.1, s * 4.3), 12.5, 14.8, 0.0, 1.1, C, ft)
        block(min(s * 2.4, s * 3.8), max(s * 2.4, s * 3.8), 13.0, 14.5, 1.0, 1.3, G, ft)
        for dx in (-0.6, 0.0, 0.6):
            x = s * (3.1 + dx)
            beam(P(x, 12.8, 0.6), P(x, 11.5, 0.02), 0.48, 0.7, H, ft, taper=0.3)
    sym(rear_leg)

    # ---------------- tail ----------------
    tp = [(16.4, 4.3, 2.4, 2.8), (18.4, 3.5, 2.3, 2.6), (20.5, 2.9, 2.2, 2.4), (22.6, 2.5, 2.05, 2.2),
          (24.7, 2.3, 1.9, 2.0), (26.8, 2.3, 1.75, 1.85), (28.9, 2.45, 1.6, 1.7), (31.0, 2.75, 1.45, 1.55),
          (33.0, 3.15, 1.25, 1.4), (34.6, 3.6, 1.0, 1.15)]
    for i in range(len(tp) - 1):
        (l0, z0, w0, h0), (l1, z1, w1, h1) = tp[i], tp[i + 1]
        bn = 'Tail%d' % (i + 1)
        beam(P(0, l0, z0), P(0, l1, z1), w0, h0, C, bn, w1=w1, h1=h1,
             over={'left': 'rune_tail', 'right': 'rune_tail', 'bottom': B})
        # gold band at joint
        lm, zm = l0, z0
        beam(P(0, lm - 0.2, zm), P(0, lm + 0.25, zm), w0 * 1.12, h0 * 1.12, G, bn)
        # pair of spikes (cream/horn) leaning back
        lc, zc, hc = (l0 + l1) / 2, (z0 + z1) / 2 + (h0 + h1) / 4, (h0 + h1) / 2
        sz = max(1.1, 1.9 - i * 0.08)
        for s in (1, -1):
            beam(P(s * w0 * 0.22, lc - 0.4, zc - 0.1), P(s * w0 * 0.55, lc + 0.7, zc + sz), 0.7, 0.8, H if i % 2 else G, bn, taper=0.15)
    lt, zt = tp[-1][0], tp[-1][1]
    for dl, dz, dx in ((1.8, 0.1, 0.0), (1.3, 0.8, 0.35), (1.3, 0.8, -0.35), (1.2, -0.5, 0.0)):
        beam(P(0, lt - 0.2, zt), P(dx, lt + dl, zt + dz), 0.7, 0.7, H, 'Tail9', taper=0.2)

    # ---------------- wings ----------------
    def wing(s, sf):
        w1b, w2b = 'Wing1' + sf, 'Wing2' + sf
        n = wing_n(s)
        # arm (shoulder -> wrist)
        beam(wing_pt(-0.6, -0.3, s), wing_pt(*WRIST, s), 1.1, 1.0, G, w1b, up=n)
        beam(wing_pt(-0.4, 0.6, s, 0.0), wing_pt(WRIST[0] - 0.3, WRIST[1] + 0.3, s), 0.6, 1.2, D, w1b, up=n)
        # leading edge: gold with charcoal outer rim
        for p, q in zip(LEADING, LEADING[1:]):
            beam(wing_pt(*p, s), wing_pt(*q, s), 0.85, 0.75, G, w2b, up=n)
            dp = (Vector(q) - Vector(p)).normalized(); nrm = Vector((-dp.y, dp.x)) * 0.6
            beam(wing_pt(p[0] + nrm.x, p[1] + nrm.y, s), wing_pt(q[0] + nrm.x, q[1] + nrm.y, s), 0.45, 0.5, C, w2b, up=n)
        beam(wing_pt(*LEADING[-1], s), wing_pt(LEADING[-1][0] + 0.4, LEADING[-1][1] - 1.6, s), 0.55, 0.55, H, w2b, up=n, taper=0.2)
        # spars
        for sp in SPARS:
            for p, q in zip(sp, sp[1:]):
                beam(wing_pt(*p, s), wing_pt(*q, s), 0.7, 0.6, G, w2b, up=n)
            p, q = Vector(sp[-2]), Vector(sp[-1]); d = (q - p).normalized() * 1.3
            beam(wing_pt(*q, s), wing_pt(q.x + d.x, q.y + d.y, s), 0.5, 0.5, H, w2b, up=n, taper=0.2)
        # glowing drips under scallops
        ol = membrane_outline()
        for k in (len(LEADING) + 1, len(LEADING) + 3, len(LEADING) + 5):
            a, b = ol[k]
            beam(wing_pt(a, b + 0.3, s), wing_pt(a + 0.2, b - 0.9, s), 0.35, 0.25, GL, w2b, up=n, taper=0.2)
        # membrane: extruded polygon with wing-region UVs
        th = 0.08
        wx, wy, ww, wh = WING_REGION
        S = ww / (WING_A1 - WING_A0)
        uvf = lambda a, b: ((wx + (a - WING_A0) * S) / ATLAS, 1 - (wy + (WING_B1 - b) * S) / ATLAS)
        top, bot = [], []
        for a, b in ol:
            wt = {w1b: 1.0} if a < 0.8 else ({w1b: 0.5, w2b: 0.5} if a < 2.5 else {w2b: 1.0})
            top.append(mb.vert(wing_pt(a, b, s, th), wt)); bot.append(mb.vert(wing_pt(a, b, s, -th), wt))
        uv = [uvf(a, b) for a, b in ol]
        # orient caps so they face +/- n
        pts = [mb.co[i] for i in top]; nn, _, _ = face_basis(pts)
        if nn.dot(n) > 0:
            add_poly(top, T, uvs=uv); add_poly(bot[::-1], T, uvs=uv[::-1])
        else:
            add_poly(top[::-1], T, uvs=uv[::-1]); add_poly(bot, T, uvs=uv)
    sym(wing)

# ------------------------------------------------------------------ armature
BONES = {
    # name: (head, tail, parent)  in design coords
    'Root': ((0, 15.0, 0.0), (0, 13.0, 0.0), None),
    'Hips': ((0, 15.5, 5.3), (0, 13.0, 5.5), 'Root'),
    'Spine': ((0, 13.0, 5.5), (0, 10.5, 5.8), 'Hips'),
    'Chest': ((0, 10.5, 5.8), (0, 7.6, 6.6), 'Spine'),
    'Neck1': ((0, 7.6, 6.6), (0, 6.2, 7.9), 'Chest'),
    'Neck2': ((0, 6.2, 7.9), (0, 5.0, 8.7), 'Neck1'),
    'Head': ((0, 5.0, 8.7), (0, 1.0, 8.5), 'Neck2'),
    'Jaw': ((0, 4.4, 7.2), (0, 1.0, 6.9), 'Head'),
}
for s, sf in ((1, '.L'), (-1, '.R')):
    BONES.update({
        'UpperArm' + sf: ((s * 2.8, 9.1, 5.6), (s * 3.3, 8.4, 2.5), 'Chest'),
        'Forearm' + sf: ((s * 3.3, 8.4, 2.5), (s * 3.7, 7.6, 0.9), 'UpperArm' + sf),
        'Hand' + sf: ((s * 3.7, 7.6, 0.9), (s * 3.75, 5.6, 0.5), 'Forearm' + sf),
        'Thigh' + sf: ((s * 2.6, 14.6, 4.8), (s * 3.0, 13.6, 2.3), 'Hips'),
        'Shin' + sf: ((s * 3.0, 13.6, 2.3), (s * 3.1, 14.2, 0.9), 'Thigh' + sf),
        'Foot' + sf: ((s * 3.1, 14.2, 0.9), (s * 3.1, 11.8, 0.4), 'Shin' + sf),
    })
TAILP = [(16.4, 4.3), (18.4, 3.5), (20.5, 2.9), (22.6, 2.5), (24.7, 2.3), (26.8, 2.3), (28.9, 2.45),
         (31.0, 2.75), (33.0, 3.15), (35.6, 3.6)]
for i in range(9):
    BONES['Tail%d' % (i + 1)] = ((0,) + TAILP[i][:1] + TAILP[i][1:], (0,) + TAILP[i + 1][:1] + TAILP[i + 1][1:],
                                 'Hips' if i == 0 else 'Tail%d' % i)

def wing_bones():
    for s, sf in ((1, '.L'), (-1, '.R')):
        def d(a, b):
            v = wing_pt(a, b, s); return (v.x, v.y + L0, v.z)
        BONES['Wing1' + sf] = (d(-0.6, -0.3), d(*WRIST), 'Chest')
        BONES['Wing2' + sf] = (d(*WRIST), d(12.0, 1.0), 'Wing1' + sf)
wing_bones()

def make_armature():
    arm = bpy.data.armatures.new('DragonRig')
    ob = bpy.data.objects.new('DragonRig', arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (h, t, par) in BONES.items():
        eb = arm.edit_bones.new(name)
        eb.head = P(*h); eb.tail = P(*t)
        eb.roll = 0.0
    for name, (h, t, par) in BONES.items():
        if par:
            eb = arm.edit_bones[name]; eb.parent = arm.edit_bones[par]
            eb.use_connect = False
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
        n.interpolation = 'Closest' if False else 'Linear'
        if non_color: n.image.colorspace_settings.name = 'Non-Color'
        return n
    c = img('AncientDragon_Color_2048.png'); nm = img('AncientDragon_Normal_2048.png', True); em = img('AncientDragon_Emission_2048.png', True)
    Lk.new(c.outputs['Color'], bsdf.inputs['Base Color'])
    nmap = N.new('ShaderNodeNormalMap'); Lk.new(nm.outputs['Color'], nmap.inputs['Color']); Lk.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    mul = N.new('ShaderNodeMixRGB'); mul.blend_type = 'MULTIPLY'; mul.inputs[0].default_value = 1.0
    Lk.new(c.outputs['Color'], mul.inputs[1]); Lk.new(em.outputs['Color'], mul.inputs[2])
    Lk.new(mul.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 2.5
    bsdf.inputs['Roughness'].default_value = 0.55
    return m

# ------------------------------------------------------------------ assemble
def assemble():
    me = bpy.data.meshes.new('AncientDragon')
    me.from_pydata([tuple(v) for v in mb.co], [], [f[0] for f in mb.faces])
    me.update()
    uvl = me.uv_layers.new(name='UVMap')
    for poly, (vids, uvs) in zip(me.polygons, mb.faces):
        for li, uv in zip(poly.loop_indices, uvs):
            uvl.data[li].uv = uv
    ob = bpy.data.objects.new('AncientDragon', me)
    bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(make_material())
    # weights
    groups = {}
    for vi, wd in enumerate(mb.w):
        for bn, wt in wd.items():
            if bn not in groups:
                groups[bn] = ob.vertex_groups.new(name=bn)
            groups[bn].add([vi], wt, 'REPLACE')
    # triangulate (Roblox imports triangles; keeps shading predictable)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method='BEAUTY', ngon_method='BEAUTY')
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = False
    return ob

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    build()
    ob = assemble()
    rig = make_armature()
    for bone in rig.data.bones:          # Roblox-friendly names (no dots)
        bone.name = bone.name.replace('.L', '_L').replace('.R', '_R')
    for g in ob.vertex_groups:
        g.name = g.name.replace('.L', '_L').replace('.R', '_R')
    missing = [g.name for g in ob.vertex_groups if g.name not in rig.data.bones]
    assert not missing, missing
    ob.parent = rig
    mod = ob.modifiers.new('Armature', 'ARMATURE'); mod.object = rig
    # scale to metres and apply
    for o in (rig, ob):
        o.select_set(True)
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
