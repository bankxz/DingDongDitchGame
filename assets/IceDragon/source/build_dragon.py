"""Procedural build of the three-headed Ice Dragon for Roblox.

Run:  python3 build_dragon.py <assets/IceDragon dir>
Produces IceDragon.blend, IceDragon.fbx, IceDragon_Idle.fbx, IceDragon_Walk.fbx,
IceDragon.glb and a validation JSON.

Axes: Blender Z up, dragon faces -Y, dragon's left side is +X (bones *.L).
1 Blender unit = 1 Roblox stud.
"""
import bpy, math, json, os, sys, random
from mathutils import Vector, Matrix, Quaternion

ROOT = os.path.abspath(sys.argv[-1])
TEX = os.path.join(ROOT, 'textures')
ATLAS = json.load(open(os.path.join(TEX, 'atlas_regions.json')))
SLOTS = ATLAS['slots']; STUDDED = set(ATLAS['studded'])
ASIZE = ATLAS['size']; PXS = ATLAS['px_per_stud']
STUD = 0.45                                   # world size of one stud
random.seed(7)
V = Vector

# ----------------------------------------------------------------------------
# mesh accumulation
# ----------------------------------------------------------------------------
class MeshAcc:
    def __init__(self, name):
        self.name = name; self.v = []; self.w = []; self.f = []   # f: (idx, slot, uvs|None)

    def add_v(self, p, wt):
        self.v.append(V(p)); self.w.append(dict(wt)); return len(self.v) - 1

    def face(self, idx, slot, uvs=None):
        self.f.append((list(idx), slot, uvs))

    def tris(self):
        return sum(len(i) - 2 for i, _, _ in self.f)

BODY = MeshAcc('IceDragon_Body')
GLOW = MeshAcc('IceDragon_Ice')

def W(b, b2=None, t=0.0):
    if b2 is None or t <= 0.0: return {b: 1.0}
    if t >= 1.0: return {b2: 1.0}
    return {b: 1.0 - t, b2: t}

def frame(T, up=V((0, 0, 1))):
    T = T.normalized()
    if abs(T.dot(up)) > 0.95: up = V((0, 1, 0)) if abs(T.y) < 0.9 else V((1, 0, 0))
    s = T.cross(up).normalized(); u = s.cross(T).normalized()
    return s, u

def loft(acc, rings, n, color, cap0=None, cap1=None, rot=math.pi / 8):
    """rings: list of dict(c, T(optional), up(optional), rx, ry, w).
    color(face_normal, face_centre, ring_index) -> slot name."""
    cs = [V(r['c']) for r in rings]
    ids = []
    for i, r in enumerate(rings):
        T = r.get('T')
        if T is None:
            a = cs[max(i - 1, 0)]; b = cs[min(i + 1, len(cs) - 1)]; T = b - a
        s, u = frame(V(T), V(r.get('up', (0, 0, 1))))
        row = []
        for k in range(n):
            a = rot + 2 * math.pi * k / n
            p = cs[i] + s * (r['rx'] * math.cos(a)) + u * (r['ry'] * math.sin(a))
            row.append(acc.add_v(p, r['w']))
        ids.append(row)
    for i in range(len(rings) - 1):
        for k in range(n):
            q = [ids[i][k], ids[i + 1][k], ids[i + 1][(k + 1) % n], ids[i][(k + 1) % n]]
            P = [acc.v[j] for j in q]
            nrm = (P[2] - P[0]).cross(P[3] - P[1]).normalized()
            acc.face(q, color(nrm, sum(P, V()) / 4, i))
    def cap(row, flip, slot):
        P = [acc.v[j] for j in row]; c = sum(P, V()) / len(P)
        ci = acc.add_v(c, acc.w[row[0]])
        for k in range(n):
            tri = [row[k], row[(k + 1) % n], ci]
            if flip: tri.reverse()
            acc.face(tri, slot)
    if cap0: cap(ids[0], False, cap0)
    if cap1: cap(ids[-1], True, cap1)
    return ids

def poly_box(acc, corners, slot, wt, slots=None):
    """corners: 8 points (0-3 bottom ccw seen from above, 4-7 top)."""
    ids = [acc.add_v(p, wt) for p in corners]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for qi, q in enumerate(quads):
        acc.face([ids[j] for j in q], (slots or {}).get(qi, slot))

def box(acc, c, size, slot, wt, M=Matrix.Identity(3), taper=1.0, slots=None):
    c = V(c); sx, sy, sz = [v / 2 for v in size]
    pts = []
    for z, tp in ((-sz, 1.0), (sz, taper)):
        for x, y in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy)):
            pts.append(c + M @ V((x * tp, y * tp, z)))
    poly_box(acc, pts, slot, wt, slots)

def shard(acc, base, d, length, width, wt, twist=0.0, sides=4, simple=False):
    """Faceted ice crystal: base ring -> wider shoulder -> tip. Crystal-atlas UVs.
    simple=True gives a 4-tri pyramid for filler shards (tri budget)."""
    d = V(d).normalized(); base = V(base)
    s, u = frame(d); u = -u          # ring runs counter-clockwise around d => outward faces
    x, y, w, h = SLOTS['crystal']
    U = lambda uu, vv: ((x + 3 + uu * (w - 6)) / ASIZE, 1 - (y + 3 + (1 - vv) * (h - 6)) / ASIZE)
    if simple:
        row = [acc.add_v(base + (s * math.cos(twist + 2 * math.pi * k / sides) + u * math.sin(twist + 2 * math.pi * k / sides)) * width * 0.5, wt) for k in range(sides)]
        tip = acc.add_v(base + d * length, wt)
        for k in range(sides):
            acc.face([row[k], row[(k + 1) % sides], tip], 'crystal', [U(0, 0), U(1, 0), U(0.5, 1)])
        return
    rows = []
    for t, wf in ((0.0, 0.55), (0.32, 1.0)):
        row = []
        for k in range(sides):
            a = twist + 2 * math.pi * k / sides
            p = base + d * (length * t) + (s * math.cos(a) + u * math.sin(a)) * (width * 0.5 * wf)
            row.append(acc.add_v(p, wt))
        rows.append(row)
    tip = acc.add_v(base + d * length, wt)
    for k in range(sides):
        k2 = (k + 1) % sides
        acc.face([rows[0][k], rows[0][k2], rows[1][k2], rows[1][k]], 'crystal',
                 [U(0.2, 0), U(0.8, 0), U(1, 0.32), U(0, 0.32)])
        acc.face([rows[1][k], rows[1][k2], tip], 'crystal', [U(0, 0.32), U(1, 0.32), U(0.5, 1)])

def cluster(acc, base, d, spread, count, length, width, wt, seed=0, side=None, simple=True):
    """Fan of shards around direction d (like the reference's ice clumps)."""
    rnd = random.Random(seed); d = V(d).normalized(); s, u = frame(d)
    if side is not None: s = V(side).normalized(); u = s.cross(d).normalized()
    for i in range(count):
        a = (i / max(count - 1, 1) - 0.5) * 2 if count > 1 else 0.0
        dd = (d + s * (a * spread) + u * rnd.uniform(-0.25, 0.25) * spread).normalized()
        L = length * (1.0 - 0.35 * abs(a)) * rnd.uniform(0.85, 1.1)
        off = s * (a * width * 0.9) + u * rnd.uniform(-0.1, 0.1)
        shard(acc, V(base) + off, dd, L, width * rnd.uniform(0.8, 1.1), wt, twist=rnd.uniform(0, 1.5), simple=simple and abs(a) > 0.01)

def gem_plate(acc, c, n, up, w, h, t, wt, slot='gem'):
    """Diamond bipyramid gem facing normal n (glow mesh)."""
    c = V(c); n = V(n).normalized(); up = V(up).normalized(); s = up.cross(n).normalized(); up = n.cross(s)
    ring = [c + up * h, c + s * w, c - up * h, c - s * w]
    ids = [acc.add_v(p, wt) for p in ring]
    f = acc.add_v(c + n * t, wt); b = acc.add_v(c - n * t * 0.3, wt)
    x, y, ww, hh = SLOTS[slot]
    uvp = lambda px, py: ((x + px * ww) / ASIZE, 1 - (y + (1 - py) * hh) / ASIZE)
    uvr = [uvp(0.5, 1), uvp(0, 0.5), uvp(0.5, 0), uvp(1, 0.5)]
    for k in range(4):
        k2 = (k + 1) % 4
        acc.face([ids[k2], ids[k], f], slot, [uvr[k2], uvr[k], uvp(0.5, 0.5)])
        acc.face([ids[k], ids[k2], b], slot, [uvr[k], uvr[k2], uvp(0.5, 0.5)])

def gold_frame(acc, c, n, up, w, h, bw, depth, wt):
    """Diamond-shaped gold frame (chest / wing joints)."""
    c = V(c); n = V(n).normalized(); up = V(up).normalized(); s = up.cross(n).normalized(); up = n.cross(s)
    outer = [c + up * h, c + s * w, c - up * h, c - s * w]
    k = 1 - bw
    inner = [c + (p - c) * k for p in outer]
    rows = []
    for dz in (0.0, depth):
        rows.append([acc.add_v(p + n * dz, wt) for p in outer] + [acc.add_v(p + n * dz, wt) for p in inner])
    back, front = rows
    for i in range(4):
        j = (i + 1) % 4
        acc.face([front[i], front[j], front[4 + j], front[4 + i]][::-1], 'gold')    # front rim
        acc.face([back[i], back[j], front[j], front[i]], 'gold')                     # outer wall
        acc.face([front[4 + i], front[4 + j], back[4 + j], back[4 + i]], 'gold')     # inner wall

def gold_band(acc, c, T, rx, ry, height, wt, n=8):
    c = V(c); T = V(T).normalized()
    loft(acc, [dict(c=c - T * height / 2, T=T, rx=rx, ry=ry, w=wt),
               dict(c=c + T * height / 2, T=T, rx=rx, ry=ry, w=wt)], n, lambda *a: 'gold')

def square_joint(acc, glow, c, n, up, size, wt):
    """Gold square boss with a cyan gem, as on the wing joints."""
    n = V(n).normalized(); up = V(up).normalized()
    s = up.cross(n).normalized(); up = n.cross(s)
    M = Matrix((s, up, n)).transposed()
    box(acc, c, (size, size, size * 0.55), 'gold', wt, M, taper=0.8)
    gem_plate(glow, V(c) + n * size * 0.28, n, up, size * 0.26, size * 0.26, size * 0.12, wt)

def claw(acc, top, fwd, reach, drop, w, h, wt):
    """Chunky white claw (CLAW / FOOT DETAIL): chamfered-square section running forward
    off the toe, then bending straight down to a flat blunt tip on the ground."""
    fwd = V(fwd).normalized(); side = fwd.cross(V((0, 0, 1))).normalized(); up = V((0, 0, 1))
    def ring(c, a, b, n):
        k = 0.62                                     # chamfer: corners cut to 62 %
        pts = [(a, b * k), (a * k, b), (-a * k, b), (-a, b * k), (-a, -b * k), (-a * k, -b), (a * k, -b), (a, -b * k)]
        nn = n.cross(side).normalized()
        return [acc.add_v(c + side * x + nn * y, wt) for x, y in pts]
    p0 = V(top); p1 = p0 + fwd * reach * 0.8 - up * drop * 0.15; p2 = p0 + fwd * reach - up * drop
    r0 = ring(p0, w / 2, h / 2, fwd)
    r1 = ring(p1, w / 2 * 0.97, h / 2, (fwd - up).normalized())
    r2 = ring(p2, w / 2 * 0.88, h / 2 * 0.85, (-up + fwd * 0.1).normalized())
    for ra, rb in ((r0, r1), (r1, r2)):
        for i in range(8):
            acc.face([ra[i], ra[(i + 1) % 8], rb[(i + 1) % 8], rb[i]], 'tooth')
    acc.face(r2, 'tooth')                                               # flat blunt tip

def chevron(acc, c, fwd, w, h, t, wt):
    """Gold inverted-V trim on the front of a toe (apex up, facing forward)."""
    fwd = V(fwd).normalized(); side = fwd.cross(V((0, 0, 1))).normalized(); up = side.cross(fwd).normalized()
    th = 0.42 * h
    outline = [(-w / 2, 0), (0, h), (w / 2, 0), (w / 2 - th, 0), (0, h - th * 1.2), (-w / 2 + th, 0)]
    b = [acc.add_v(V(c) + side * x + up * y, wt) for x, y in outline]
    f = [acc.add_v(V(c) + side * x + up * y + fwd * t, wt) for x, y in outline]
    for tri in ((0, 1, 5), (1, 4, 5), (1, 2, 4), (2, 3, 4)):
        acc.face([f[i] for i in tri], 'gold'); acc.face([b[i] for i in tri][::-1], 'gold')
    for i in range(6):
        j = (i + 1) % 6
        acc.face([b[i], b[j], f[j], f[i]], 'gold')

def tooth(acc, base, d, length, width, wt, side):
    d = V(d).normalized(); side = V(side).normalized(); f = d.cross(side).normalized()
    a = acc.add_v(V(base) - side * width * 0.5, wt)
    b = acc.add_v(V(base) + side * width * 0.5, wt)
    c = acc.add_v(V(base) + f * width * 0.6, wt)
    t = acc.add_v(V(base) + d * length, wt)
    acc.face([a, b, t], 'tooth'); acc.face([b, c, t], 'tooth'); acc.face([c, a, t], 'tooth')

# ----------------------------------------------------------------------------
# skeleton definition (head, tail, parent) — also used for weighting
# ----------------------------------------------------------------------------
BONES = {}
def bone(name, head, tail, parent=None):
    BONES[name] = (V(head), V(tail), parent)

bone('Root', (0, 0, 0), (0, -1.5, 0))
bone('Torso', (0, 1.4, 4.3), (0, -1.6, 4.6), 'Root')
bone('Pelvis', (0, 1.4, 4.3), (0, 4.6, 4.1), 'Torso')
# tail chain
TAIL = [V((0, 4.6, 4.1)), V((0, 6.4, 3.3)), V((0, 8.0, 2.3)), V((0, 9.6, 1.5)), V((0, 11.0, 1.0)), V((0, 12.3, 0.75))]
for i in range(5):
    bone(f'Tail{i+1}', TAIL[i], TAIL[i + 1], 'Pelvis' if i == 0 else f'Tail{i}')

# necks + heads: (base, mid1, mid2, headbase, snout dir)
NECKS = {
    'C': [V((0, -1.2, 5.4)), V((0, -1.9, 6.8)), V((0, -2.2, 7.9)), V((0, -2.3, 8.8))],
    'L': [V((2.0, -1.2, 5.1)), V((2.5, -1.8, 6.5)), V((3.0, -2.2, 7.3)), V((3.7, -2.3, 7.7))],
    'R': [V((-2.0, -1.2, 5.1)), V((-2.5, -1.8, 6.5)), V((-3.0, -2.2, 7.3)), V((-3.7, -2.3, 7.7))],
}
HEADDIR = {'C': V((0, -1, 0.0)).normalized(), 'L': V((0.8, -1, 0.0)).normalized(), 'R': V((-0.8, -1, 0.0)).normalized()}
HS = 1.05                    # overall head scale (head ~2.2 studs wide, reference ratio to neck ~1.2)
HEADLEN = 2.8 * HS
JAW_OPEN = math.radians(38)
def head_frame(k):
    d = HEADDIR[k]; s_, u = frame(d)
    return d, s_, u
for k, pts in NECKS.items():
    for i in range(3):
        bone(f'Neck{k}{i+1}', pts[i], pts[i + 1], 'Torso' if i == 0 else f'Neck{k}{i}')
    d, s_, u = head_frame(k)
    bone(f'Head{k}', pts[3], pts[3] + d * HEADLEN, f'Neck{k}3')
    hinge = pts[3] + (d * 0.3 + u * -0.42) * HS
    jd = d * math.cos(JAW_OPEN) - u * math.sin(JAW_OPEN)
    bone(f'Jaw{k}', hinge, hinge + jd * 2.3 * HS, f'Head{k}')

def mirror(p, sgn): return V((p[0] * sgn, p[1], p[2]))

LEG_F = [V((2.5, -1.1, 4.3)), V((3.5, -0.8, 2.6)), V((3.8, -1.9, 1.15)), V((3.85, -2.7, 0.5))]
LEG_H = [V((2.2, 3.3, 3.9)), V((2.8, 2.0, 2.4)), V((2.6, 3.5, 1.1)), V((2.6, 2.8, 0.45))]
WING = [V((1.7, 0.7, 6.0)), V((3.3, 1.7, 10.4)), V((5.0, 6.1, 9.1)), V((6.6, 10.3, 3.1))]
for side, sg in (('L', 1), ('R', -1)):
    f = [mirror(p, sg) for p in LEG_F]
    bone(f'UpperArm.{side}', f[0], f[1], 'Torso')
    bone(f'Forearm.{side}', f[1], f[2], f'UpperArm.{side}')
    bone(f'Hand.{side}', f[2], f[3], f'Forearm.{side}')
    h = [mirror(p, sg) for p in LEG_H]
    bone(f'Thigh.{side}', h[0], h[1], 'Pelvis')
    bone(f'Shin.{side}', h[1], h[2], f'Thigh.{side}')
    bone(f'Foot.{side}', h[2], h[3], f'Shin.{side}')
    w = [mirror(p, sg) for p in WING]
    bone(f'Wing1.{side}', w[0], w[1], 'Torso')
    bone(f'Wing2.{side}', w[1], w[2], f'Wing1.{side}')
    bone(f'Wing3.{side}', w[2], w[3], f'Wing2.{side}')

# ----------------------------------------------------------------------------
# geometry
# ----------------------------------------------------------------------------
def c_torso(n, c, i):
    if n.z < -0.45: return 'white'
    if n.y < -0.6 and n.z < 0.55: return 'white'
    return 'navy'

# torso: chest (front) -> hips; necks and legs plug into it
TORSO = [(-2.35, 4.4, 1.4, 1.35), (-1.7, 4.4, 2.2, 1.95), (-0.5, 4.45, 2.7, 2.2), (1.0, 4.5, 2.6, 2.15),
         (2.5, 4.4, 2.5, 2.0), (3.9, 4.25, 2.3, 1.85), (4.9, 4.05, 1.5, 1.35)]
def torso_w(y):
    return W('Torso', 'Pelvis', (y - 0.6) / 1.8)
loft(BODY, [dict(c=(0, y, z), T=(0, 1, 0), rx=rx, ry=ry, w=torso_w(y)) for y, z, rx, ry in TORSO],
     8, c_torso, cap0='white')

# tail
def tail_w(i, t=0.0):
    names = ['Pelvis'] + [f'Tail{k}' for k in range(1, 6)]
    return W(names[i], names[min(i + 1, 5)], t)
TR = [(1.4, 1.25), (1.05, 0.95), (0.8, 0.72), (0.58, 0.52), (0.4, 0.36), (0.22, 0.2)]
rings = []
for i, p in enumerate(TAIL):
    rings.append(dict(c=p, rx=TR[i][0], ry=TR[i][1], w=tail_w(i, 0.0) if i == 0 else W(f'Tail{i}', f'Tail{min(i+1,5)}', 0.35 if i < 5 else 0)))
rings[0]['c'] = V((0, 4.4, 4.1))
loft(BODY, rings, 8, lambda n, c, i: 'white' if n.z < -0.35 else 'navy', cap1='navy')

# spine crystals: big central column + side shards (back view)
spine = [(-1.0, 1.0, 1.25), (0.1, 1.2, 1.55), (1.3, 1.3, 1.7), (2.6, 1.25, 1.55), (3.8, 1.0, 1.35)]
for y, s, L in spine:
    zc = [z for yy, z, rx, ry in TORSO]
    top = 4.45 + 2.15
    wt = torso_w(y)
    shard(GLOW, (0, y, top - 0.45), (0, 0.3, 1), L * 1.75, 0.95 * s, wt, twist=0.78)
    for sg in (1, -1):
        shard(GLOW, (0.55 * sg, y + 0.25, top - 0.55), (0.5 * sg, 0.3, 1), L * 1.15, 0.7 * s, wt, twist=0.3, simple=True)
for i in range(1, 5):
    p = TAIL[i]; r = TR[i][1]
    wt = W(f'Tail{i}')
    L = 1.75 - 0.2 * i
    shard(GLOW, p + V((0, 0, r * 0.6)), (0, 0.45, 1), L, 0.7 - 0.08 * i, wt, twist=0.78)
    for sg in (1, -1):
        shard(GLOW, p + V((0.3 * sg, 0.25, r * 0.5)), (0.7 * sg, 0.4, 0.8), L * 0.75, 0.5 - 0.05 * i, wt, twist=0.2, simple=True)
# tail tip fan
tip = TAIL[5]
for i in range(11):
    a = (i / 10 - 0.5) * 2.6
    d = V((math.sin(a), math.cos(a) * 0.9 + 0.35, 0.25 + 0.25 * math.cos(a)))
    shard(GLOW, tip + V((0, -0.45, 0.05)), d, 2.4 * (1 - 0.3 * abs(a) / 1.3), 0.6, W('Tail5'), twist=i * 0.7, simple=(i % 2 == 1))
for sg in (1, -1):
    shard(GLOW, tip + V((0, -0.3, 0.1)), (0.35 * sg, 0.7, 0.9), 1.9, 0.55, W('Tail5'))
gold_frame(BODY, TAIL[4] + V((0, -0.25, 0.42)), (0, 0.2, 1), (0, 1, 0), 0.26, 0.34, 0.35, 0.08, W('Tail4', 'Tail5', 0.5))
gem_plate(GLOW, TAIL[4] + V((0, -0.25, 0.46)), (0, 0.2, 1), (0, 1, 0), 0.16, 0.22, 0.08, W('Tail4', 'Tail5', 0.5))

# chest: gold-framed diamond gem + crystal skirt below
gold_frame(BODY, (0, -2.55, 4.3), (0, -1, 0.25), (0, 0.25, 1), 0.62, 0.95, 0.3, 0.14, W('Torso'))
gem_plate(GLOW, (0, -2.6, 4.3), (0, -1, 0.25), (0, 0.25, 1), 0.44, 0.7, 0.22, W('Torso'))
# ice-blue chest shield around the gem
loft(BODY, [dict(c=(0, -2.3, 4.35), T=(0, -1, 0.25), rx=1.05, ry=1.35, w=W('Torso')),
            dict(c=(0, -2.5, 4.35), T=(0, -1, 0.25), rx=0.9, ry=1.2, w=W('Torso'))],
     4, lambda *a: 'ice', cap1='ice', rot=0)
cluster(GLOW, (0, -2.0, 2.8), (0, -0.25, -1), 0.6, 5, 1.4, 0.5, W('Torso'), seed=3, side=(1, 0, 0))

# necks + heads
def neck_color(front):
    def f(n, c, i):
        return 'white' if n.dot(front) > 0.6 else 'navy'
    return f

def shard_tooth(base, dirv, length, width, wt):
    """Big white fang: 4-sided pyramid in the tooth swatch."""
    d = V(dirv).normalized(); s_, u_ = frame(d); u_ = -u_
    row = [BODY.add_v(V(base) + (s_ * math.cos(a) + u_ * math.sin(a)) * width * 0.5, wt)
           for a in (0.78, 0.78 + math.pi / 2, 0.78 + math.pi, 0.78 + 1.5 * math.pi)]
    tip = BODY.add_v(V(base) + d * length, wt)
    for i in range(4):
        BODY.face([row[i], row[(i + 1) % 4], tip], 'tooth')

def gold_spike(base, dirv, length, width, wt):
    g0 = len(BODY.f)
    shard(BODY, base, dirv, length, width, wt, twist=0.78, simple=True)
    BODY.f[g0:] = [(i, 'gold', None) for i, sl, uv in BODY.f[g0:]]

def build_head(k):
    """Blocky head per the HEAD / EYE DETAIL close-up: flat navy skull, blunt box snout,
    angry V brow over a glowing slit eye, white gum line with big fangs, white cheek
    blocks, white blocky lower jaw with red mouth, gold horns, ice mane."""
    base = NECKS[k][3]
    d, s, u = head_frame(k)
    R = Matrix((s, d, u)).transposed()                   # local (x side, y forward, z up)
    hw = W(f'Head{k}'); jw = W(f'Jaw{k}')
    P = lambda x, y, z: base + R @ (V((x, y, z)) * HS)
    def hbox(c, size, slot, rot=None, taper=1.0, slots=None):
        box(BODY, P(*c), [v * HS for v in size], slot, hw, R @ (rot or Matrix.Identity(3)), taper, slots)
    BOT, TOP, BACK, SIDE_P, FRONT, SIDE_N = range(6)
    # skull + snout (roof of mouth is red)
    hbox((0, 0.45, 0.26), (2.1, 1.6, 1.05), 'navy', taper=0.88, slots={BOT: 'red'})
    hbox((0, 2.0, 0.08), (1.66, 1.9, 0.74), 'navy', taper=0.9, slots={BOT: 'red'},
         rot=Matrix.Rotation(0.1, 3, 'X'))                                   # snout, nose tipped down
    hbox((0, 2.9, 0.1), (1.3, 0.3, 0.52), 'navy', taper=0.85)                 # blunt nose block
    hbox((0, 1.5, 0.52), (1.1, 1.3, 0.3), 'royal', taper=0.8)                 # lighter bridge plate
    # white gum line along the upper jaw edge
    hbox((0, 1.85, -0.34), (1.74, 2.3, 0.2), 'white', slots={BOT: 'red'})
    for sg in (1, -1):
        # angry V brow: outer end high, inner end low
        hbox((0.52 * sg, 0.98, 0.84), (0.98, 0.62, 0.38), 'navy', rot=Matrix.Rotation(-0.48 * sg, 3, 'Y'))
        hbox((0.9 * sg, 0.45, 0.72), (0.4, 0.8, 0.5), 'royal')                 # upper cheek plate
        # glowing slit eye tucked under the brow
        gem_plate(GLOW, P(0.6 * sg, 1.3, 0.6), d * 0.75 + s * sg * 0.65, u + s * 0.4 * sg, 0.36 * HS, 0.15 * HS, 0.08 * HS, hw, slot='eye')
        # white cheek blocks at the mouth corner (two stacked, as in the close-up)
        hbox((0.93 * sg, 0.35, -0.2), (0.42, 0.95, 0.9), 'white')
        hbox((0.86 * sg, 0.85, -0.55), (0.36, 0.6, 0.5), 'white')
        # nostrils
        hbox((0.33 * sg, 2.72, 0.42), (0.22, 0.22, 0.1), 'dark', rot=Matrix.Rotation(0.1, 3, 'X'))
        # gold horn spikes at the back of the skull
        gold_spike(P(0.72 * sg, -0.05, 0.9), R @ V((0.45 * sg, -0.75, 0.6)), 0.6 * HS, 0.3 * HS, hw)
        gold_spike(P(0.9 * sg, 0.35, 0.85), R @ V((0.8 * sg, -0.4, 0.6)), 0.4 * HS, 0.24 * HS, hw)
        # upper fangs hanging from the gum line (big pair at the front corners)
        for y, L, x in ((1.0, 0.42, 0.74), (1.5, 0.64, 0.74), (2.0, 0.46, 0.72), (2.55, 0.8, 0.66), (2.88, 0.4, 0.28)):
            shard_tooth(P(x * sg, y, -0.42), -u + d * 0.08, L * HS, 0.3 * HS, hw)
    if k == 'C':  # gold horn in the middle of the forehead
        gold_spike(P(0, 1.25, 0.95), R @ V((0, 0.35, 1)), 0.55 * HS, 0.26 * HS, hw)
    # mouth interior / tongue joining the jaws
    hbox((0, 0.85, -0.62), (1.4, 1.3, 0.55), 'red')
    # lower jaw: white block, red top, hinged open ~38 deg
    hinge = BONES[f'Jaw{k}'][0]
    jd = (BONES[f'Jaw{k}'][1] - hinge).normalized(); ju = s.cross(jd).normalized()
    RJ = Matrix((s, jd, ju)).transposed()
    J = lambda x, y, z: hinge + RJ @ (V((x, y, z)) * HS)
    box(BODY, J(0, 1.2, -0.12), [1.56 * HS, 2.55 * HS, 0.48 * HS], 'white', jw, RJ, 1.0, {TOP: 'red'})
    box(BODY, J(0, 1.35, -0.4), [1.1 * HS, 1.9 * HS, 0.22 * HS], 'white', jw, RJ, 0.9)          # chin block
    for sg in (1, -1):
        box(BODY, J(0.72 * sg, 1.2, 0.14), [0.16 * HS, 2.5 * HS, 0.12 * HS], 'white', jw, RJ)     # lower gum rim
        for y, L, x in ((0.6, 0.38, 0.66), (1.15, 0.48, 0.66), (1.75, 0.55, 0.62), (2.3, 0.42, 0.3)):
            shard_tooth(J(x * sg, y, 0.18), ju + jd * 0.05, L * HS, 0.28 * HS, jw)
    # chin icicle
    shard(GLOW, J(0, 1.7, -0.5), -ju + jd * 0.25, 1.0 * HS, 0.34 * HS, jw, twist=0.78)
    # ice mane: crystals erupting from the back of the skull, up and back
    for j in range(9):
        a = (j / 8 - 0.5) * 2
        dd = (u * 1.0 - d * 0.6 + s * a * 0.8).normalized()
        L = (2.3 - 0.8 * abs(a)) * (1.15 if k == 'C' else 1.0)
        shard(GLOW, P(a * 0.62, 0.1 - abs(a) * 0.15, 0.8 - abs(a) * 0.1), dd, L, 0.58, hw, twist=j * 0.6, simple=(j % 2 == 1))
    for sg in (1, -1):  # side spikes flaring back from the cheeks
        shard(GLOW, P(1.0 * sg, 0.1, 0.35), (s * sg - d * 0.6 + u * 0.35), 1.3, 0.42, hw, twist=0.4, simple=True)

for k, pts in NECKS.items():
    sgk = neck_side_sign = {'C': 0, 'L': 1, 'R': -1}[k]
    front = V((-0.55 * sgk, -1, -0.2)).normalized()    # white belly band faces forward/inward
    radii = [(1.1, 1.0), (1.0, 0.92), (0.95, 0.88), (0.9, 0.82)] if k != 'C' else [(1.2, 1.1), (1.05, 0.95), (0.95, 0.88), (0.9, 0.82)]
    rings = []
    for i, p in enumerate(pts):
        wt = W(f'Neck{k}{min(i+1,3)}') if i < 3 else W(f'Neck{k}3', f'Head{k}', 0.5)
        if 0 < i < 3: wt = W(f'Neck{k}{i}', f'Neck{k}{i+1}', 0.5)
        rings.append(dict(c=p, rx=radii[i][0], ry=radii[i][1], up=-front, w=wt))
    rings[0]['c'] = pts[0] + (pts[0] - pts[1]).normalized() * 0.6
    loft(BODY, rings, 8, neck_color(front))
    # crystals down the back of the neck
    for i in range(3):
        a, b = pts[i], pts[i + 1]
        m = a.lerp(b, 0.5); T = (b - a).normalized()
        back = (-front - T * (-front).dot(T)).normalized()
        wt = W(f'Neck{k}{i+1}')
        shard(GLOW, m + back * 0.7, (back + V((0, 0, 0.6))).normalized(), 1.5 + 0.1 * i, 0.62, wt, twist=0.78)
        for sg in (1, -1):
            side = T.cross(back).normalized()
            shard(GLOW, m + back * 0.55 + side * 0.5 * sg, (back + side * 0.7 * sg + V((0, 0, 0.4))).normalized(), 1.2, 0.5, wt, simple=True)
    build_head(k)

# legs
def leg(chain, bones, radii, sg, front):
    rings = []
    for i, p in enumerate(chain[:3]):
        wt = W(bones[0]) if i == 0 else W(bones[i - 1], bones[i], 0.5)
        rings.append(dict(c=p, rx=radii[i][0], ry=radii[i][1], w=wt))
    rings.insert(1, dict(c=chain[0].lerp(chain[1], 0.5), rx=radii[0][0] * 1.05, ry=radii[0][1] * 1.05, w=W(bones[0])))
    rings.append(dict(c=chain[2].lerp(chain[3], 0.4) + V((0, 0, 0.1)), rx=radii[2][0], ry=radii[2][1], w=W(bones[2])))
    for r in rings: r['up'] = (0, -1, 0)
    loft(BODY, rings, 8, lambda n, c, i: 'royal' if (n.y < -0.7 and i == 3) else 'navy', cap0='navy')
    # paw
    fw = W(bones[2]); f = chain[3]
    pw = 2.3 if front else 2.0
    pl = 1.9 if front else 1.7
    box(BODY, f + V((0, 0.15, 0.05)), (pw, pl, 1.1), 'navy', fw, taper=0.72)         # stud-covered foot dome
    n = 4
    for j in range(n):
        x = (j / (n - 1) - 0.5) * pw * 0.76
        # navy toe block, gold chevron on top, chunky white claw out the front
        box(BODY, V((f.x + x, f.y - 0.72, 0.42)), (0.5, 0.62, 0.84), 'navy', fw, taper=0.9)
        chevron(BODY, V((f.x + x, f.y - 0.72, 0.86)), (0, -1, 0.9), 0.5, 0.36, 0.1, fw)
        cf = V((0, -1, 0.9)).normalized(); cup = cf.cross(V((0, 0, 1))).normalized().cross(cf)
        shard(GLOW, V((f.x + x, f.y - 0.72, 0.86)) + cup * 0.36 + cf * 0.05, cup + cf * 0.4, 0.3, 0.2, fw, twist=0.78, simple=True)
        claw(BODY, V((f.x + x, f.y - 0.98, 0.55)), (x * 0.08, -1, 0), 0.62, 0.66, 0.46, 0.5, fw)
    gold_band(BODY, chain[2], chain[3] - chain[2] + V((0, 0, 0.5)), radii[2][0] * 1.12, radii[2][1] * 1.12, 0.22, W(bones[1], bones[2], 0.5))

for side, sg in (('L', 1), ('R', -1)):
    f = [mirror(p, sg) for p in LEG_F]
    leg(f, [f'UpperArm.{side}', f'Forearm.{side}', f'Hand.{side}'], [(1.45, 1.5), (1.05, 1.05), (0.85, 0.85)], sg, True)
    out = V((sg, 0, 0))
    # shoulder: gold chevron armour + ice cluster
    gold_band(BODY, f[0].lerp(f[1], 0.3), f[1] - f[0], 1.6, 1.65, 0.3, W(f'UpperArm.{side}'))
    cluster(GLOW, f[0].lerp(f[1], 0.25) + out * 1.2, out + V((0, 0.3, 0.9)), 0.7, 5, 1.7, 0.55, W(f'UpperArm.{side}'), seed=11, side=(0, 1, 0))
    cluster(GLOW, f[1] + out * 0.8 + V((0, 0.5, 0)), out * 0.6 + V((0, 0.9, 0.3)), 0.6, 4, 1.4, 0.5, W(f'Forearm.{side}'), seed=12, side=(0, 0, 1))
    h = [mirror(p, sg) for p in LEG_H]
    leg(h, [f'Thigh.{side}', f'Shin.{side}', f'Foot.{side}'], [(1.6, 1.75), (0.9, 0.95), (0.75, 0.75)], sg, False)
    cluster(GLOW, h[0].lerp(h[1], 0.4) + out * 1.4 + V((0, 0.5, 0.3)), out * 0.8 + V((0, 0.6, 0.8)), 0.7, 5, 1.7, 0.55, W(f'Thigh.{side}'), seed=13, side=(0, 1, 0))
    gold_band(BODY, h[0].lerp(h[1], 0.62), h[1] - h[0], 1.45, 1.55, 0.24, W(f'Thigh.{side}'))
    # white belly/inner-leg panel where thigh meets body (side view)
    box(BODY, h[0].lerp(h[1], 0.35) + V((-0.45 * sg, -1.3, -0.2)), (0.8, 0.45, 1.5), 'white', W(f'Thigh.{side}'))

# wings
def wing(side, sg):
    w = [mirror(p, sg) for p in WING]
    b1, b2, b3 = (f'Wing{i}.{side}' for i in (1, 2, 3))
    mid3 = w[2].lerp(w[3], 0.45) + V((0.35 * sg, 0.3, 0.2))            # outer gold joint
    arm = [w[0], w[1], w[2], mid3, w[3]]
    wts = [W('Torso', b1, 0.7), W(b1, b2, 0.5), W(b2, b3, 0.5), W(b3), W(b3)]
    radii = [(0.62, 0.62), (0.55, 0.55), (0.45, 0.45), (0.36, 0.36), (0.16, 0.16)]
    loft(BODY, [dict(c=p, rx=r[0], ry=r[1], w=wt, up=(sg, 0, 0)) for p, r, wt in zip(arm, radii, wts)],
         6, lambda *a: 'navy', rot=0)
    # finger bone from the peak down to the membrane edge
    fend = mirror(V((4.3, 4.9, 5.6)), sg)
    loft(BODY, [dict(c=w[1], rx=0.25, ry=0.25, w=W(b1, b2, 0.5), up=(sg, 0, 0)),
                dict(c=fend, rx=0.16, ry=0.16, w=W(b1, b2, 0.3), up=(sg, 0, 0))], 6, lambda *a: 'navy', rot=0)
    root2 = mirror(V((1.9, 3.6, 5.5)), sg)
    sc1 = mirror(V((5.3, 8.1, 5.0)), sg)
    sc2 = mirror(V((3.2, 3.9, 5.2)), sg)
    # membrane (both faces), subdivided so studs keep a sensible size
    wm = {'s': W('Torso', b1, 0.4), 'p': W(b1, b2, 0.5), 'w': W(b2, b3, 0.5), 'm': W(b3), 't': W(b3),
          'sc1': W(b2, b3, 0.6), 'f': W(b1, b2, 0.3), 'sc2': W('Torso', b1, 0.5), 'r': W('Torso')}
    pts = {'s': w[0], 'p': w[1], 'w': w[2], 'm': mid3, 't': w[3], 'sc1': sc1, 'f': fend, 'sc2': sc2, 'r': root2}
    tris = [('p', 'w', 'f'), ('w', 'sc1', 'f'), ('w', 'm', 'sc1'), ('m', 't', 'sc1'), ('s', 'p', 'f'), ('s', 'f', 'sc2'), ('s', 'sc2', 'r')]
    off = V((0.04 * sg, 0, 0))
    def blend(a, b):
        out = {}
        for ww in (a, b):
            for kk, vv in ww.items(): out[kk] = out.get(kk, 0) + vv * 0.5
        return out
    for tri in tris:
        A, B, C = (pts[x] for x in tri); wa, wb, wc = (wm[x] for x in tri)
        AB, BC, CA = A.lerp(B, .5), B.lerp(C, .5), C.lerp(A, .5)
        wab, wbc, wca = blend(wa, wb), blend(wb, wc), blend(wc, wa)
        for q, qw in (((A, AB, CA), (wa, wab, wca)), ((AB, B, BC), (wab, wb, wbc)), ((CA, BC, C), (wca, wbc, wc)), ((AB, BC, CA), (wab, wbc, wca))):
            for face_sg in (1, -1):
                ids = [BODY.add_v(p + off * face_sg, ww) for p, ww in zip(q, qw)]
                if (face_sg * sg) < 0: ids.reverse()
                BODY.face(ids, 'ice')
    # gold square joints w/ cyan gems
    nrm = mirror(V((0.9, -0.2, 0.25)), sg)
    for p, wt, s_ in ((w[1], W(b1, b2, 0.5), 0.55), (w[2], W(b2, b3, 0.5), 0.5), (mid3, W(b3), 0.45), (w[0].lerp(w[1], 0.5), W(b1), 0.42)):
        square_joint(BODY, GLOW, p + nrm * 0.25, nrm, (0, 0, 1), s_, wt)
    square_joint(BODY, GLOW, fend + nrm * 0.12, nrm, (0, 0, 1), 0.3, wm['f'])
    shard(GLOW, fend - V((0, 0, 0.1)), (0, 0.15, -1), 0.9, 0.3, wm['f'], twist=0.78)
    # ice along the leading edge and at the tip
    for t in (0.2, 0.5, 0.8):
        p = w[1].lerp(w[2], t)
        cluster(GLOW, p + V((0, 0, 0.25)), V((0.3 * sg, -0.2, 1.0)), 0.5, 3, 1.4 - 0.3 * t, 0.5, W(b2), seed=int(t * 10) + 20 * sg, side=(0, 1, 0))
    for t in (0.3, 0.7):
        p = w[0].lerp(w[1], t)
        cluster(GLOW, p + V((0.3 * sg, -0.3, 0)), V((0.8 * sg, -0.5, 0.5)), 0.4, 2, 1.2, 0.45, W(b1), seed=30 + int(t * 10))
    for t in (0.25, 0.65):   # ice along the outer edge (front view)
        p = mid3.lerp(w[3], t) if t > 0.5 else w[2].lerp(mid3, t * 2)
        cluster(GLOW, p + V((0.25 * sg, 0, 0)), V((1.0 * sg, 0.5, 0.1)), 0.5, 3, 1.3, 0.48, W(b3), seed=40 + int(t * 10), side=(0, 0, 1))
    cluster(GLOW, w[3] + V((0, -0.1, 0.5)), V((0.15 * sg, 0.25, -1)), 0.35, 4, 2.2, 0.65, W(b3), seed=41, side=(0, 1, 0))
wing('L', 1); wing('R', -1)
for sg in (1, -1):
    cluster(GLOW, (1.5 * sg, -0.3, 6.2), (0.5 * sg, -0.2, 1), 0.6, 5, 1.6, 0.55, W('Torso'), seed=50, side=(0, 1, 0), simple=False)

# ----------------------------------------------------------------------------
# UVs
# ----------------------------------------------------------------------------
def slot_uv(slot, px, py):
    x, y, w, h = SLOTS[slot]
    return ((x + px) / ASIZE, 1 - (y + py) / ASIZE)

def stud_uvs(acc, idx, slot):
    P = [acc.v[i] for i in idx]
    n = V((0, 0, 0))
    for i in range(len(P)):
        n += P[i].cross(P[(i + 1) % len(P)])
    n = n.normalized() if n.length > 1e-9 else V((0, 0, 1))
    t = V((0, 0, 1)).cross(n)
    if t.length < 0.3: t = V((1, 0, 0)) - n * n.x
    t.normalize(); b = n.cross(t)
    cu = [p.dot(t) / STUD for p in P]; cv = [-p.dot(b) / STUD for p in P]
    x, y, w, h = SLOTS[slot]
    cap_u, cap_v = w / PXS - 0.3, h / PXS - 0.3
    su, sv = math.floor(min(cu)), math.floor(min(cv))
    eu, ev = max(cu) - su, max(cv) - sv
    k = min(1.0, cap_u / max(eu, 1e-6), cap_v / max(ev, 1e-6))
    return [slot_uv(slot, 4 + (u - su) * k * PXS * (1 if k == 1 else 1), 4 + (v - sv) * k * PXS) for u, v in zip(cu, cv)]

def flat_uvs(acc, idx, slot):
    P = [acc.v[i] for i in idx]
    x, y, w, h = SLOTS[slot]
    # simple planar map filling the slot
    n = (P[1] - P[0]).cross(P[2] - P[0]).normalized()
    t = V((0, 0, 1)).cross(n)
    if t.length < 0.3: t = V((1, 0, 0))
    t.normalize(); b = n.cross(t)
    cu = [p.dot(t) for p in P]; cv = [-p.dot(b) for p in P]
    mu, mv = min(cu), min(cv); eu = max(max(cu) - mu, 1e-6); ev = max(max(cv) - mv, 1e-6)
    return [slot_uv(slot, 4 + (u - mu) / eu * (w - 8), 4 + (v - mv) / ev * (h - 8)) for u, v in zip(cu, cv)]

# ----------------------------------------------------------------------------
# Blender objects
# ----------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'; scene.unit_settings.scale_length = 1.0

col_img = bpy.data.images.load(os.path.join(TEX, 'IceDragon_Color.png'))
nrm_img = bpy.data.images.load(os.path.join(TEX, 'IceDragon_Normal.png'))
nrm_img.colorspace_settings.name = 'Non-Color'

def make_mat(name, glow):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = col_img; t.interpolation = 'Closest' if False else 'Linear'
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = 0.45 if not glow else 0.15
    if glow:
        nt.links.new(t.outputs['Color'], b.inputs['Emission Color'])
        b.inputs['Emission Strength'].default_value = 1.4
    else:
        nt_ = nt.nodes.new('ShaderNodeTexImage'); nt_.image = nrm_img
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 0.8
        nt.links.new(nt_.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    return m

MAT_BODY = make_mat('IceDragon_Body', False)
MAT_ICE = make_mat('IceDragon_Ice', True)

def build_obj(acc, mat):
    me = bpy.data.meshes.new(acc.name)
    me.from_pydata([tuple(v) for v in acc.v], [], [f[0] for f in acc.f])
    me.update()
    uvl = me.uv_layers.new(name='UVMap')
    for poly, (idx, slot, uvs) in zip(me.polygons, acc.f):
        if uvs is None:
            uvs = stud_uvs(acc, idx, slot) if slot in STUDDED else flat_uvs(acc, idx, slot)
        for li, uv in zip(poly.loop_indices, uvs):
            uvl.data[li].uv = uv
        poly.use_smooth = False
    me.materials.append(mat)
    ob = bpy.data.objects.new(acc.name, me)
    scene.collection.objects.link(ob)
    groups = {}
    for vi, wt in enumerate(acc.w):
        for bn, val in wt.items():
            if val <= 0: continue
            if bn not in groups: groups[bn] = ob.vertex_groups.new(name=bn)
            groups[bn].add([vi], val, 'REPLACE')
    return ob

ob_body = build_obj(BODY, MAT_BODY)
ob_ice = build_obj(GLOW, MAT_ICE)
for ob in (ob_body, ob_ice):
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=0.0001)
    bpy.ops.object.mode_set(mode='OBJECT'); ob.select_set(False)

# armature
arm_data = bpy.data.armatures.new('IceDragonRig')
arm = bpy.data.objects.new('IceDragon', arm_data)
scene.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
for name, (h, t, p) in BONES.items():
    eb = arm_data.edit_bones.new(name); eb.head = h; eb.tail = t
    eb.roll = 0.0
for name, (h, t, p) in BONES.items():
    if p:
        eb = arm_data.edit_bones[name]; eb.parent = arm_data.edit_bones[p]
        eb.use_connect = False
bpy.ops.object.mode_set(mode='OBJECT')
for ob in (ob_body, ob_ice):
    ob.parent = arm
    md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm

tri_total = BODY.tris() + GLOW.tris()
print('TRIS body', BODY.tris(), 'ice', GLOW.tris(), 'total', tri_total)
json.dump({'tris_body': BODY.tris(), 'tris_ice': GLOW.tris(), 'tris_total': tri_total, 'bones': len(BONES)},
          open(os.path.join(ROOT, 'source', 'build_stats.json'), 'w'), indent=1)

# ----------------------------------------------------------------------------
# animation
# ----------------------------------------------------------------------------
exec(open(os.path.join(ROOT, 'source', 'animate_dragon.py')).read())

bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'IceDragon.blend'))
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, 'IceDragon.blend'))
print('saved blend')
