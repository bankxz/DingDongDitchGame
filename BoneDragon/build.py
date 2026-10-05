"""Bone Dragon - stud-style Roblox model.  Run:  python3 build.py   (needs: pip install bpy==4.2.0 pillow numpy)

Z up, model faces -Y, its left side is +X, 1 unit = 1 stud.  Writes textures/, BoneDragon.blend.
Stud source: dudeax/Roblox-HD-Studs (MIT) - 3 tiles vendored in tools/studs.
"""
import sys, os, math, json, random, subprocess
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import bpy
import stud_kit as K
import anim_kit as A
from mathutils import Vector as V, Matrix

TEX = os.path.join(HERE, 'textures'); STUD = 0.4
subprocess.check_call([sys.executable, os.path.join(HERE, 'tools/make_stud_atlas.py'), os.path.join(HERE, 'tools/studs'),
                       os.path.join(HERE, 'atlas_config.json'), TEX])
K.init(os.path.join(TEX, 'atlas_regions.json'), stud=STUD)
BODY = K.MeshAcc('BoneDragon_Body'); GLOW = K.MeshAcc('BoneDragon_Glow', glow=True)
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)


# ------------------------------------------------------------------ helpers
def fix(acc, s):
    """Wind a freshly added primitive outward (mirrored builds flip handedness)."""
    fs = acc.f[s:]
    if not fs: return
    ec = Counter()
    for idx, _, _ in fs:
        for i in range(len(idx)): ec[frozenset((idx[i], idx[(i + 1) % len(idx)]))] += 1
    closed = all(c == 2 for c in ec.values())
    pts = [acc.v[i] for f in fs for i in f[0]]; cen = sum(pts, V()) / len(pts)
    if closed:
        vol = 0.0
        for idx, _, _ in fs:
            vs = [acc.v[i] for i in idx]
            for i in range(1, len(vs) - 1): vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6
        neg = vol < 0
    else:
        inward = 0
        for idx, _, _ in fs:
            vs = [acc.v[i] for i in idx]; n = (vs[1] - vs[0]).cross(vs[2] - vs[0]); fc = sum(vs, V()) / len(vs)
            if n.dot(fc - cen) < 0: inward += 1
        neg = inward > len(fs) / 2
    if neg:
        for j in range(s, len(acc.f)):
            idx, slot, uvs = acc.f[j]; acc.f[j] = (idx[::-1], slot, uvs[::-1] if uvs else None)


def prim(fn, acc, *a, **k):
    s = len(acc.f); r = fn(acc, *a, **k); fix(acc, s); return r


def M3(right, fwd, up):
    return Matrix(((right.x, fwd.x, up.x), (right.y, fwd.y, up.y), (right.z, fwd.z, up.z)))


def obox(acc, c, size, ydir, slot, wt, up=Z, taper=1.0, slots=None):
    """Box with local +Y along ydir."""
    f = V(ydir).normalized(); u = V(up)
    if abs(f.dot(u.normalized())) > .95: u = V(X)
    r = f.cross(u).normalized(); u = r.cross(f).normalized()
    prim(K.box, acc, c, size, slot, wt, M=M3(r, f, u), taper=taper, slots=slots)


def seg(acc, p0, p1, r0, r1, slot, w0, w1=None, n=4, cap=True, flat=1.0):
    p0, p1 = V(p0), V(p1); T = p1 - p0
    rings = [{'c': p0, 'rx': r0, 'ry': r0 * flat, 'w': w0, 'T': T}, {'c': p1, 'rx': r1, 'ry': r1 * flat, 'w': w1 or w0, 'T': T}]
    prim(K.loft, acc, rings, n, lambda nn, c, i: slot, cap0=slot if cap else None, cap1=slot if cap else None, rot=math.pi / n)


def spike(acc, base, d, length, width, w, slot='bone'):
    prim(K.solid_spike, acc, V(base), V(d), length, width, w, slot)


def tongue(base, d, side, h, w, bend, wt, off=0.0):
    """Curved flame tongue (3 tris, emitted twice for two-sided view) in the plane spanned by d and side."""
    base, d, side = V(base), V(d).normalized(), V(side).normalized(); nrm = d.cross(side).normalized() * off
    P = {'a': base - side * w * .5, 'b': base + side * w * .5, 'm1': base + d * h * .42 - side * w * .62 + side * bend * .3,
         'm2': base + d * h * .5 + side * w * .45 + side * bend * .4, 't': base + d * h + side * bend}
    uv = {'a': (0.05, 0), 'b': (.95, 0), 'm1': (0, .42), 'm2': (1, .46), 't': (.5, 1)}
    x0, y0, sw, sh = K.ATLAS['slots']['flame']; S_ = K.ATLAS['size']
    U = lambda k: ((x0 + 3 + uv[k][0] * (sw - 6)) / S_, 1 - (y0 + 3 + (1 - uv[k][1]) * (sh - 6)) / S_)
    for tri in (('a', 'b', 'm2'), ('a', 'm2', 'm1'), ('m1', 'm2', 't')):
        for sgn in (1, -1):
            ids = [GLOW.add_v(P[k] + nrm * sgn * .5 + nrm * 0 , wt) for k in tri]
            GLOW.face(ids if sgn > 0 else ids[::-1], 'flame', [U(k) for k in tri] if sgn > 0 else [U(k) for k in tri][::-1])


def flame(base, d, h, width, wt, seed=0, n=3, spread=.5, side=X):
    """Fan of curved flame tongues (alternating between two crossing planes), tallest in the middle."""
    rnd = random.Random(seed); d = V(d).normalized(); s = V(side).normalized(); u = s.cross(d).normalized()
    for i in range(n):
        a = (i / (n - 1) - .5) * 2 if n > 1 else 0
        dd = (d + s * a * spread + u * rnd.uniform(-.2, .2)).normalized()
        sd = s if i % 2 == 0 else (s * .35 + u).normalized()
        hh = h * (1 - .35 * abs(a)) * rnd.uniform(.9, 1.1)
        tongue(V(base) + s * a * h * .1, dd, sd, hh, max(width * 2.4, hh * .42), hh * rnd.uniform(.08, .2) * (1 if a >= 0 else -1), wt, off=.012 * (i + 1))


def claw(acc, base, fwd, length, drop, w, h, wt, slot='claw'):
    """Chunky triangular claw: from base runs forward (fwd) and curves down by drop to a blunt tip."""
    f = V(fwd).normalized(); p0 = V(base); p1 = p0 + f * length * .55 - V(Z) * drop * .15; p2 = p0 + f * length - V(Z) * drop
    rings = [{'c': p0, 'rx': w / 2, 'ry': h / 2, 'w': wt, 'T': f}, {'c': p1, 'rx': w * .4, 'ry': h * .42, 'w': wt, 'T': (p2 - p0)},
             {'c': p2, 'rx': w * .09, 'ry': h * .09, 'w': wt, 'T': (p2 - p1)}]
    prim(K.loft, acc, rings, 4, lambda n, c, i: slot, cap0=slot, cap1=slot, rot=math.pi / 4)


def catmull(P, k=6):
    P = [V(p) for p in P]; out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for j in range(k):
            t = j / k
            out.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1]); return out


def mx(p, s):  # mirror point in x
    p = V(p); return V((p.x * s, p.y, p.z))


# ---------------------------------------------------------------- skeleton
SK = {}
def B(name, head, tail, parent=None): SK[name] = (V(head), V(tail), parent)

B('Root', (0, 0, 0), (0, 0, .6))
B('Torso', (0, 1.4, 3.0), (0, -.8, 3.2), 'Root')
B('Chest', (0, -.8, 3.2), (0, -1.9, 3.6), 'Torso')
B('Neck1', (0, -1.9, 3.6), (0, -2.05, 4.3), 'Chest')
B('Neck2', (0, -2.05, 4.3), (0, -2.2, 4.85), 'Neck1')
B('Head', (0, -2.2, 4.7), (0, -4.2, 5.3), 'Neck2')
B('Jaw', (0, -2.6, 4.5), (0, -4.7, 3.9), 'Head')
TAILP = [(0, 1.4, 3.0), (0, 2.2, 2.85), (0, 3.2, 2.35), (0, 4.3, 1.6), (0, 5.2, 1.7), (0, 5.85, 2.3)]
for i in range(5): B(f'Tail{i + 1}', TAILP[i], TAILP[i + 1], 'Torso' if i == 0 else f'Tail{i}')
LEGS = {  # name: (hip, knee, ankle, toe, parent)
    'Front': ((1.35, -1.6, 3.3), (2.1, -1.2, 2.0), (2.2, -1.6, 1.0), (2.2, -2.5, .25), 'Chest'),
    'Hind':  ((1.4, 1.3, 2.95), (1.8, .65, 1.65), (1.95, 1.5, .95), (1.95, .75, .25), 'Torso'),
}
for nm, (h, k, a, t, par) in LEGS.items():
    for sg, sx in ((1, 'L'), (-1, 'R')):
        B(f'{nm}Upper.{sx}', mx(h, sg), mx(k, sg), par); B(f'{nm}Lower.{sx}', mx(k, sg), mx(a, sg), f'{nm}Upper.{sx}')
        B(f'{nm}Foot.{sx}', mx(a, sg), mx(t, sg), f'{nm}Lower.{sx}')
WS, WE, WW = (1.1, -.8, 4.6), (3.2, .7, 5.8), (4.15, 1.15, 8.7)
FING = {1: ((5.8, 4.0, 7.4), (6.1, 5.4, 4.5)), 2: ((4.8, 3.5, 6.5), (4.7, 4.6, 3.8)), 3: ((3.9, 2.2, 6.0), (3.0, 3.0, 3.3))}
for sg, sx in ((1, 'L'), (-1, 'R')):
    B(f'WingUpper.{sx}', mx(WS, sg), mx(WE, sg), 'Chest'); B(f'WingFore.{sx}', mx(WE, sg), mx(WW, sg), f'WingUpper.{sx}')
    for i, (j, t) in FING.items():
        B(f'Finger{i}a.{sx}', mx(WW, sg), mx(j, sg), f'WingFore.{sx}'); B(f'Finger{i}b.{sx}', mx(j, sg), mx(t, sg), f'Finger{i}a.{sx}')

# -------------------------------------------------------------- skull / head
H, JW = {'Head': 1.0}, {'Jaw': 1.0}
EYE_OUT = [(-.38, .12), (-.1, .27), (.2, .21), (.4, .0), (.3, -.21), (0, -.3), (-.28, -.2)]


def omat(xdir, ydir):
    x = V(xdir).normalized(); y = (V(ydir) - x * V(ydir).dot(x)).normalized(); return M3(x, y, x.cross(y))


def plate(acc, c, size, xdir, ydir, slot, wt, taper=1.0):
    prim(K.box, acc, c, size, slot, wt, M=omat(xdir, ydir), taper=taper)


def stations(acc, stn, wt, slot_fn, cap0=None, cap1=None):
    """Loft through hand-shaped cross-sections: y, top, (x,z) upper, mid, lower, bottom -> 8 ring points (x-mirrored)."""
    ids = []
    for y, top, ur, mr, lr, bot in stn:
        pts = [(0, top), ur, mr, lr, (0, bot), (-lr[0], lr[1]), (-mr[0], mr[1]), (-ur[0], ur[1])]
        ids.append([acc.add_v((x, y, z), wt) for x, z in pts])
    s0 = len(acc.f)
    for i in range(len(stn) - 1):
        for k in range(8):
            acc.face([ids[i][k], ids[i + 1][k], ids[i + 1][(k + 1) % 8], ids[i][(k + 1) % 8]], slot_fn(i, k))
    for row, slot in ((ids[0], cap0), (ids[-1], cap1)):
        if slot:
            ci = acc.add_v(sum((acc.v[j] for j in row), V()) / 8, wt)
            for k in range(8): acc.face([row[k], row[(k + 1) % 8], ci], slot)
    fix(acc, s0)
    return ids


# ---- cranium rebuilt from measured landmarks (reference front/left grids): 12-point rings along 10 stations
SK_Y = [-1.5, -1.9, -2.3, -2.8, -3.3, -3.8, -4.2, -4.6, -4.95, -5.3]
SK_T = [6.0, 6.3, 6.75, 7.0, 7.0, 6.85, 6.5, 6.05, 5.65, 5.45]      # top (centre ridge) z
SK_B = [5.0, 4.8, 4.7, 4.65, 4.55, 4.55, 4.55, 4.55, 4.6, 4.6]    # palate z
SK_W = [.7, 1.0, 1.15, 1.25, 1.25, 1.12, .9, .68, .58, .52]          # half width: nose bridge / snout flank tapers so the eyes face forward
# denser stations around the eyes carry the carved socket (pocket depth D per station)
import numpy as _np0
SK2_Y = [-1.5, -1.9, -2.3, -2.8, -3.3, -3.55, -3.8, -4.05, -4.3, -4.55, -4.95, -5.3]
SK2_D = [0, 0, 0, 0, 0, 0, .08, .24, .3, .22, 0, 0]
_ip = lambda arr: [float(_np0.interp(y, SK_Y[::-1], arr[::-1])) for y in SK2_Y]
SK2_T, SK2_B, SK2_W = _ip(SK_T), _ip(SK_B), _ip(SK_W)
SOCKET_FRAC = .445       # socket centre, as a fraction of skull height below the top ridge


def skull_ring(y, T, B, W, D):
    h = T - B
    # half ring: top, forehead shoulder, brow side, UPPER RIM, socket FLOOR (recessed), LOWER RIM (cheek bone), jaw side, palate edge, palate
    half = [(0, T), (.3 * W, T - .02 * h), (.7 * W, T - .2 * h), (.86 * W + .25 * D, T - .32 * h), (W - D, T - SOCKET_FRAC * h),
            (.9 * W + .2 * D, T - .57 * h), (.88 * W, T - .72 * h), (.52 * W, B + .06 * h), (0, B)]
    pts = half + [(-x, z) for x, z in reversed(half[1:-1])]
    if y < -5.2:   # nose end: bottom pushed forward so the end face slopes (faces forward + up) and can carry the nostrils
        return [(x, y - .38 * (T - z) / (T - B), z) for x, z in pts]
    return [(x, y, z) for x, z in pts]


def build_skull():
    ids = [[BODY.add_v(pt, H) for pt in skull_ring(*r)] for r in zip(SK2_Y, SK2_T, SK2_B, SK2_W, SK2_D)]
    s0 = len(BODY.f); n = 16
    for i in range(len(ids) - 1):
        d = (SK2_D[i] + SK2_D[i + 1]) / 2
        for k in range(n):
            if k in (7, 8): slot = 'dark'                           # palate
            elif k in (6, 9) and i > 3: slot = 'boneD'
            elif k in (3, 4, 11, 12) and d > .1: slot = 'socket'   # inside of the eye socket (warm dark brown)
            else: slot = 'bone'
            BODY.face([ids[i][k], ids[i + 1][k], ids[i + 1][(k + 1) % n], ids[i][(k + 1) % n]], slot)
    row = ids[0]; ci = BODY.add_v(sum((BODY.v[j] for j in row), V()) / n, H)
    for k in range(n): BODY.face([row[k], row[(k + 1) % n], ci], 'bone')
    fix(BODY, s0)
    return ids


_ids = build_skull()


def nose_with_nostrils(ring, depth=.3):
    """Sloped nose end face with two real teardrop nostril holes (tips pointing down toward the centre), each leading into a dark pocket."""
    from mathutils.geometry import tessellate_polygon
    outer = [BODY.v[j] for j in ring]
    vt = max(outer, key=lambda v: v.z); vb = min(outer, key=lambda v: v.z)
    t = (vt - vb).normalized(); nrm = t.cross(V(X)).normalized()
    if nrm.y > 0: nrm = -nrm
    P = lambda x, z: vb + t * ((z - vb.z) / t.z) + V((x, 0, 0))
    TEAR = [(-.08, -.25), (.09, -.1), (.13, .1), (-.01, .25), (-.12, .08)]
    holes = []; hole_ids = []; pockets = []
    for sg in (1, -1):
        q = [P(sg * (.3 + u + .28 * dz), 5.04 + dz) for u, dz in TEAR]; c = sum(q, V()) / len(q)
        holes.append(q); hole_ids.append([BODY.add_v(pt, H) for pt in q])
        pockets.append((hole_ids[-1], [BODY.add_v(c + (pt - c) * .5 - nrm * depth, H) for pt in q]))
    allids = list(ring) + hole_ids[0] + hole_ids[1]
    for a, b, c_ in tessellate_polygon([outer, holes[0], holes[1]]):
        f = [allids[a], allids[b], allids[c_]]; vs = [BODY.v[i] for i in f]
        if (vs[1] - vs[0]).cross(vs[2] - vs[0]).dot(nrm) < 0: f = f[::-1]
        BODY.face(f, 'bone')
    for outer_q, inner_q in pockets:
        n_ = len(outer_q)
        faces = [[outer_q[i], outer_q[(i + 1) % n_], inner_q[(i + 1) % n_], inner_q[i]] for i in range(n_)] + [inner_q[::-1]]
        cp = sum((BODY.v[i] for i in outer_q + inner_q), V()) / (2 * n_)
        for f in faces:
            vs = [BODY.v[i] for i in f]; nn = (vs[1] - vs[0]).cross(vs[2] - vs[0]); fc = sum(vs, V()) / len(vs)
            BODY.face(f if nn.dot(fc - cp) < 0 else f[::-1], 'dark')


nose_with_nostrils(_ids[-1])


def leaf_plate(acc, A, B, width, thick, wt, slot='bone', sink=.08):
    """Tapered leaf-shaped plate from A to B (pointed ends, widest ~35% along), sunk into the skull."""
    A, B = V(A), V(B); d = B - A; L = d.length; d.normalize()
    w = d.cross(V(Z)).normalized(); n = w.cross(d).normalized()
    prof = [(0, 0), (.3, .5), (.68, .42), (1, 0), (.68, -.42), (.3, -.5)]
    top = [acc.add_v(A + d * L * f + w * width * o + n * (thick / 2 - sink), wt) for f, o in prof]
    bot = [acc.add_v(A + d * L * f + w * width * o - n * (thick / 2 + sink), wt) for f, o in prof]
    s0 = len(acc.f)
    for i in range(1, 5):
        acc.face([top[0], top[i], top[i + 1]], slot); acc.face([bot[0], bot[i + 1], bot[i]], slot)
    for i in range(6):
        j = (i + 1) % 6; acc.face([bot[i], bot[j], top[j], top[i]], slot)
    fix(acc, s0)


for sg in (1, -1):
    leaf_plate(BODY, (sg * .4, -4.75, 6.4), (sg * 1.25, -3.5, 6.9), .55, .38, H, sink=.14)     # thick bevelled brow block right on the eye
    leaf_plate(BODY, (sg * .8, -4.45, 5.0), (sg * 1.25, -2.9, 5.3), .55, .36, H, sink=.14)   # cheek plate under the eye
    spike(BODY, (sg * 1.05, -2.95, 5.95), (sg * .75, .55, .35), .95, .8, H)                  # ear flare
    # low jagged crest along the cranium: small shards stepping back
    for i, (cy, cz, ln) in enumerate(((-3.45, 6.75, .5), (-3.1, 6.9, .6), (-2.75, 6.85, .6), (-2.4, 6.6, .5))):
        spike(BODY, (sg * (.42 + .08 * i), cy, cz - .2), (sg * .3, .3, 1), ln + .2, .5, H)
    spike(BODY, (sg * 1.15, -2.7, 6.4), (sg * .8, .2, .55), .8, .6, H)                       # outer crown shard
    spike(BODY, (sg * .9, -2.1, 5.95), (sg * .2, 1, .1), .6, .5, H)                          # rear skull spike
spike(BODY, (0, -2.95, 6.75), (0, .25, 1), .8, .8, H)                                      # central crown spike
# lower jaw
JR = [(-4.8, 3.87, .45, .3), (-3.7, 4.03, .85, .4), (-2.7, 4.19, 1.2, .5)]
rings = [{'c': (0, y, cz), 'rx': rx, 'ry': rz, 'w': JW, 'T': (0, -1, 0)} for y, cz, rx, rz in JR]
prim(K.loft, BODY, rings, 8, lambda n, c, i: 'dark' if n.z > .5 else ('boneD' if n.z < -.4 else 'bone'), cap0='bone', cap1='bone')
plate(BODY, (0, -3.75, 4.38), (1.1, 1.9, .5), (1, 0, 0), (0, -1, 0), 'dark', H)   # dark mouth interior between palate and jaw
# ---- teeth: many short, wide-based triangular fangs along the real skull / jaw edges (reference), dark mouth behind
import numpy as _np
def _tab(ys, vals, y): return float(_np.interp(y, ys[::-1], vals[::-1]))
def fang(acc, base, d, length, wy, wx, wt, slot='tooth'):
    d = V(d).normalized(); b = V(base)
    q = [acc.add_v(b + V((sx * wx / 2, sy * wy / 2, 0)), wt) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    tip = acc.add_v(b + d * length, wt); s0 = len(acc.f)
    for k in range(4): acc.face([q[k], q[(k + 1) % 4], tip], slot)
    fix(acc, s0)
for sg in (1, -1):
    for i, y in enumerate(_np.linspace(-5.05, -3.2, 9)):
        W_ = _tab(SK_Y, SK_W, y); T_ = _tab(SK_Y, SK_T, y); B_ = _tab(SK_Y, SK_B, y); zb = B_ + .06 * (T_ - B_) - .04
        fang(BODY, (sg * .5 * W_, y, zb), (sg * .1, 0, -1), .36 if i == 0 else (.26 if i % 2 else .3), .27, .14, H)
    for i, y in enumerate(_np.linspace(-4.65, -2.95, 7)):
        rx_ = _tab([r[0] for r in JR], [r[2] for r in JR], y); cz_ = _tab([r[0] for r in JR], [r[1] for r in JR], y); rz_ = _tab([r[0] for r in JR], [r[3] for r in JR], y)
        fang(JBODY if False else BODY, (sg * .5 * rx_, y, cz_ + .92 * rz_ - .05), (sg * -.1, 0, 1), .3 if i == 0 else .22, .25, .13, JW)
for sg in (1, -1):
    _y = -4.25
    _fl = lambda yy: float(_np0.interp(yy, SK_Y[::-1], SK_W[::-1])) - float(_np0.interp(yy, SK2_Y[::-1], SK2_D[::-1]))   # socket floor half-width x(y)
    _T = float(_np0.interp(_y, SK_Y[::-1], SK_T[::-1])); _B = float(_np0.interp(_y, SK_Y[::-1], SK_B[::-1]))
    _dxdy = (_fl(_y + .12) - _fl(_y - .12)) / .24
    _n = V((sg * 1.0, -_dxdy, .05)).normalized()                                  # outward normal of the sloped socket floor (faces forward-out)
    _c = V((sg * _fl(_y), _y, _T - SOCKET_FRAC * (_T - _B))) + _n * .06       # seated flush on the floor
    prim(K.eye_lens, GLOW, _c, _n, (0, 0, 1), (0, -1, 0), H, outline=EYE_OUT, scale=1.1, dome=.08)
# horns: loft with explicit gradient UVs (brown-orange base -> charcoal tip)
for sg in (1, -1):
    path = [(1.0, -2.4, 6.2), (1.3, -1.95, 7.4), (1.6, -1.4, 8.2), (1.75, -.8, 8.85), (1.7, -.3, 9.25)]
    R = [.66, .56, .42, .26, .02]; HR = [{'c': mx(p, sg), 'rx': r, 'ry': r * .82, 'w': H} for p, r in zip(path, R)]
    cs = [V(r['c']) for r in HR]; ids = []
    for i, r in enumerate(HR):
        T = cs[min(i + 1, 4)] - cs[max(i - 1, 0)]; s, u = K.frame(T, V((0, -1, 0)))
        ids.append([BODY.add_v(cs[i] + s * r['rx'] * math.cos(math.pi / 5 + 2 * math.pi * k / 5) + u * r['ry'] * math.sin(math.pi / 5 + 2 * math.pi * k / 5), H) for k in range(5)])
    s0 = len(BODY.f)
    x0, y0, w0, h0 = K.ATLAS['slots']['horn']; S_ = K.ATLAS['size']
    vv = lambda t: ((x0 + w0 / 2) / S_, 1 - (y0 + 4 + t * (h0 - 8)) / S_)
    for i in range(4):
        for k in range(5):
            q = [ids[i][k], ids[i + 1][k], ids[i + 1][(k + 1) % 5], ids[i][(k + 1) % 5]]
            BODY.face(q, 'horn', [vv(i / 4), vv((i + 1) / 4), vv((i + 1) / 4), vv(i / 4)])
    ci = BODY.add_v(sum((BODY.v[j] for j in ids[0]), V()) / 5, H)
    for k in range(5): BODY.face([ids[0][k], ids[0][(k + 1) % 5], ci], 'horn', [vv(0)] * 3)
    fix(BODY, s0)


# ------------------------------------------------------------------- neck
NECK = [((0, -1.85, 3.5), .95, .85, {'Chest': 1}), ((0, -1.9, 3.8), .72, .66, {'Chest': 1}), ((0, -1.98, 4.1), .95, .82, K.W('Chest', 'Neck1', .5)),
        ((0, -2.05, 4.38), .72, .66, {'Neck1': 1}), ((0, -2.12, 4.65), .9, .8, {'Neck1': 1}), ((0, -2.2, 4.9), .7, .64, K.W('Neck1', 'Neck2', .6)),
        ((0, -2.25, 5.1), .66, .6, {'Neck2': 1})]
rings = [{'c': c, 'rx': rx, 'ry': ry, 'w': w} for c, rx, ry, w in NECK]
prim(K.loft, BODY, rings, 8, lambda n, c, i: 'dark', cap0='dark', cap1='dark')
for sg in (1, -1):   # slanted cervical bones along the lower neck sides
    seg(BODY, (sg * .85, -1.55, 3.0), (sg * .78, -2.45, 4.35), .17, .13, 'bone', K.W('Chest', 'Neck1', .5), {'Neck1': 1}, n=4)
    plate(BODY, (sg * .8, -2.35, 5.0), (.55, .8, .5), (sg, 0, 0), (0, -1, .3), 'bone', {'Neck2': 1})
for z, w in ((4.05, K.W('Chest', 'Neck1', .5)), (4.6, {'Neck1': 1})):
    spike(BODY, (0, -1.55, z), (0, .9, .55), .6, .42, w)

# ---------------------------------------------------------------- torso
# dark dorsal barrel (rounded dark scale plates along the back); the ember core shows between the ribs
BAR = [((0, -1.85, 3.9), .8, .75, {'Chest': 1}), ((0, -1.1, 4.1), 1.0, .8, {'Chest': 1}), ((0, -.2, 4.0), 1.05, .8, K.W('Chest', 'Torso', .5)),
       ((0, .7, 3.75), .95, .75, {'Torso': 1}), ((0, 1.5, 3.4), .72, .6, {'Torso': 1})]
rings = [{'c': c, 'rx': rx, 'ry': rz, 'w': w} for c, rx, rz, w in BAR]
prim(K.loft, BODY, rings, 8, lambda n, c, i: 'dark', cap0='dark', cap1='dark')
# belly: dark barrel underside
rings = [{'c': (0, y, z), 'rx': rx, 'ry': .45, 'w': w} for y, z, rx, w in
         ((-2.0, 2.45, .65, {'Chest': 1}), (-1.0, 2.2, 1.0, {'Chest': 1}), (.1, 2.2, 1.0, K.W('Chest', 'Torso', .5)), (1.1, 2.45, .75, {'Torso': 1}))]
prim(K.loft, BODY, rings, 8, lambda n, c, i: 'dark', cap0='dark', cap1='dark')
for sg in (1, -1): plate(BODY, (sg * .95, 1.2, 3.15), (.7, 1.2, .9), (sg, 0, 0), (0, -1, -.1), 'bone', {'Torso': 1})   # pelvis blocks
# ribs: broad curved bands bowing backward, tops tucked under the dark spine barrel
RIBS = [(-2.0, .85, .75, 2.8, .2), (-1.3, 1.3, 1.15, 3.1, .38), (-.55, 1.48, 1.28, 3.25, .4), (.2, 1.45, 1.25, 3.25, .4), (.95, 1.2, 1.05, 3.15, .32)]
for j, (y, a, b, zc, wd) in enumerate(RIBS):
    for sg in (1, -1):
        rr = []
        for k, th in enumerate((24, 56, 90, 124, 158)):
            t = math.radians(th)
            rr.append({'c': (sg * a * math.sin(t), y + .72 * math.sin(t) * (1 if j > 0 else .6), zc + b * math.cos(t)), 'rx': wd, 'ry': .16,
                       'w': {'Chest': 1} if y < .4 else K.W('Chest', 'Torso', .6)})
        prim(K.loft, BODY, rr, 4, lambda n, c, i: 'bone', cap0='bone', cap1='bone', rot=math.pi / 4)
# ember core inside the cage (glow mesh)
rings = [{'c': (0, y, z), 'rx': rx, 'ry': rz, 'w': w} for y, z, rx, rz, w in
         ((-1.95, 2.95, .6, .55, {'Chest': 1}), (-1.1, 3.1, 1.1, .95, {'Chest': 1}), (.1, 3.1, 1.15, .95, K.W('Chest', 'Torso', .6)), (1.0, 3.0, .85, .75, {'Torso': 1}))]
prim(K.loft, GLOW, rings, 8, lambda n, c, i: 'ember', cap0='dark', cap1='dark')
prim(K.gem_plate, GLOW, (0, -2.2, 3.0), (0, -1, .15), (0, 0, 1), .34, .5, .2, {'Chest': 1}, slot='gem')
obox(BODY, (0, -2.15, 2.15), (.6, .45, .7), (0, -1, -.5), 'dark', {'Chest': 1}, taper=.45)
# dorsal flames (glow) + bone plates
for i, (y, z) in enumerate(((-1.6, 4.45), (-1.0, 4.75), (-.4, 4.65), (.25, 4.45), (.85, 4.2), (1.35, 3.85))):
    w = {'Chest': 1} if y < -.4 else K.W('Chest', 'Torso', .5) if y < .3 else {'Torso': 1}
    flame((0, y, z), (0, .55, 1), .8 if i in (1, 2) else .6, .2, w, seed=i, n=3, spread=.4)
flame((.65, -1.3, 4.4), (.6, .55, 1), 1.2, .22, {'Chest': 1}, seed=21, n=3, spread=.5, side=(0, 1, 0))
flame((-.65, -1.3, 4.4), (-.6, .55, 1), 1.1, .22, {'Chest': 1}, seed=22, n=3, spread=.5, side=(0, 1, 0))


# ------------------------------------------------------------------- tail
P = catmull(TAILP, 12)   # 61 points
def tail_w(u):  # u in [0,5]
    k = min(int(u), 4); s = u - k; return K.W(f'Tail{k + 1}', f'Tail{min(k + 2, 5)}', s * s * (3 - 2 * s)) if k < 4 else {'Tail5': 1}
NB = 12; rings = []; bandcol = []
for b in range(NB):
    u0 = b / NB * 5; u1 = (b + .55) / NB * 5; f = 1 - b / NB
    r = (.6 * f + .16) * (1.0 if b % 2 == 0 else .88)
    for u, rr in ((u0, r), (u1, r)):
        p = P[min(int(u * 12 + .5), len(P) - 1)]
        rings.append({'c': p, 'rx': rr, 'ry': rr * .9, 'w': tail_w(u)})
    bandcol.append(b)
prim(K.loft, BODY, rings, 6, lambda n, c, i: ('dark' if (i // 2) % 2 == 0 else 'bone') if i % 2 == 0 else 'dark',
     cap0='dark', cap1='dark', rot=math.pi / 6)
for b in range(1, NB - 2, 1):
    u = (b + .3) / NB * 5; p = P[min(int(u * 12 + .5), len(P) - 1)]; f = 1 - b / NB
    spike(BODY, p + V((0, 0, .1)), (0, .3, 1), .55 * f + .3, .38 * f + .2, tail_w(u))
tip = P[-1]
prim(K.solid_spike, BODY, tip - V((0, .15, .02)), V((0, .75, .55)), .85, .42, {'Tail5': 1}, 'dark')
flame(tip + V((0, .45, .35)), (0, .55, .9), 2.3, .34, {'Tail5': 1}, seed=40, n=5, spread=.55, side=(1, 0, 0))
flame(tip + V((0, .55, .25)), (0, 1, .35), 1.7, .3, {'Tail5': 1}, seed=41, n=3, spread=.5, side=(0, 0, 1))

# ------------------------------------------------------------------- legs
def foot(sg, ank, parent, size=1.0):
    w = {parent: 1}; ax, ay, az = ank
    plate(BODY, (sg * ax, ay - .35, .32), (1.2 * size, 1.1 * size, .55), (sg, 0, 0), (0, -1, -.05), 'boneD', w, taper=.9)
    for dx, yaw in ((-.46, -.18), (0, 0), (.46, .18)):
        x = sg * (ax + dx * size)
        obox(BODY, (x, ay - .95 * size, .3), (.46 * size, .55, .44), (sg * yaw, -1, 0), 'dark', w)
        claw(BODY, (x, ay - 1.15 * size, .3), (sg * yaw * 1.4, -1, 0), .62 * size, .27, .4 * size, .36, w)


for sg in (1, -1):
    sx = 'L' if sg > 0 else 'R'
    # front leg
    h, k, a, t, _ = LEGS['Front']; h, k, a, t = (mx(p, sg) for p in (h, k, a, t))
    U, Lo, Fo = {f'FrontUpper.{sx}': 1}, {f'FrontLower.{sx}': 1}, {f'FrontFoot.{sx}': 1}
    seg(BODY, (sg * 1.15, -.7, 4.75), (sg * 1.5, -1.75, 3.15), .3, .42, 'bone', {'Chest': 1}, n=6)             # scapula from the wing root
    plate(BODY, (sg * 1.75, -1.75, 2.95), (.8, .95, .85), (sg, 0, 0), (0, -1, -.15), 'bone', U, taper=.8)          # humerus head
    seg(BODY, h + V((0, 0, -.1)), k, .78, .6, 'bone', U, n=6, flat=.85)
    obox(BODY, k, (.82, .82, .82), (0, 1, 0), 'dark', U)
    seg(BODY, k, a, .62, .48, 'bone', Lo, n=6, flat=.8)
    plate(BODY, a + V((0, -.05, .05)), (.8, .85, .65), (sg, 0, 0), (0, -1, -.2), 'bone', Fo)
    foot(sg, (2.2, -1.65, 0), f'FrontFoot.{sx}', 1.12)
    # hind leg
    h, k, a, t, _ = LEGS['Hind']; h, k, a, t = (mx(p, sg) for p in (h, k, a, t))
    U, Lo, Fo = {f'HindUpper.{sx}': 1}, {f'HindLower.{sx}': 1}, {f'HindFoot.{sx}': 1}
    seg(BODY, h, k, 1.05, .66, 'bone', U, n=6, flat=.8)
    obox(BODY, k, (.9, .9, .9), (0, 1, 0), 'dark', U)
    seg(BODY, k, a, .62, .48, 'bone', Lo, n=6, flat=.8)
    plate(BODY, a + V((0, .1, 0)), (.85, .9, .65), (sg, 0, 0), (0, -1, -.2), 'bone', Fo)
    foot(sg, (1.95, 1.3, 0), f'HindFoot.{sx}', 1.18)

# ------------------------------------------------------------------- wings
WINGPTS = {}
def wing(sg):
    sx = 'L' if sg > 0 else 'R'; p = lambda q: mx(q, sg)
    w = lambda n: {f'{n}.{sx}': 1}
    seg(BODY, p(WS), p(WE), .26, .22, 'bone', w('WingUpper'), n=6)
    seg(BODY, p(WE), p(WW), .22, .18, 'bone', w('WingFore'), n=6)
    obox(BODY, p(WS), (.55, .55, .55), (1, 0, 0), 'bone', w('WingUpper'))
    obox(BODY, p(WE), (.5, .5, .5), (1, 0, 0), 'bone', w('WingFore'))
    obox(BODY, p(WW), (.6, .6, .6), (1, 0, 0), 'bone', w('WingFore'))
    spike(BODY, p(WE) + V((0, -.1, -.1)), (sg * .1, -.5, -1), .6, .4, w('WingFore'))
    for i, (j, t) in FING.items():
        seg(BODY, p(WW), p(j), .15, .13, 'bone', w(f'Finger{i}a'), n=4)
        seg(BODY, p(j), p(t), .13, .08, 'bone', w(f'Finger{i}b'), n=4)
        obox(BODY, p(j), (.3, .3, .3), (0, 1, 0), 'bone', w(f'Finger{i}a'))
        spike(BODY, V(p(t)) - (V(p(t)) - V(p(j))).normalized() * .12, (V(p(t)) - V(p(j))).normalized(), .67, .24, w(f'Finger{i}b'))
    flame(p(WW) + V((0, 0, .2)), (0, 0, 1), 1.35, .3, w('WingFore'), seed=30 + sg, n=3, spread=.55, side=(0, 1, 0))
    flame(p(WW) + V((0, .05, .15)), (0, .3, 1), 1.0, .28, w('WingFore'), seed=33 + sg, n=3, spread=.6, side=(1, 0, 0))
    # membrane
    Wp, T1, T2, T3 = (V(WW),) + tuple(V(FING[i][1]) for i in (1, 2, 3))
    J1, J2, J3 = (V(FING[i][0]) for i in (1, 2, 3))
    sc = lambda a, b, t: (a + b) / 2 * (1 - t) + V(WW) * t
    s1, s2, s3 = sc(T1, T2, .24), sc(T2, T3, .24), sc(T3, V((1.1, 1.5, 3.9)), .3)
    Bp, Sp, Ep = V((1.1, 1.5, 3.9)), V(WS), V(WE)
    poly = {'W': V(WW), 'J1': J1, 'T1': T1, 's1': s1, 'J2': J2, 'T2': T2, 's2': s2, 'J3': J3, 'T3': T3, 's3': s3, 'B': Bp, 'S': Sp, 'E': Ep}
    tris = [('W', 'J1', 'T1'), ('W', 'T1', 's1'), ('W', 's1', 'J2'), ('J2', 's1', 'T2'), ('W', 'J2', 'J3'), ('J3', 'T2', 's2'), ('J2', 'T2', 'J3'),
            ('W', 'J3', 'E'), ('J3', 's2', 'T3'), ('E', 'J3', 'T3'), ('E', 'T3', 's3'), ('E', 's3', 'B'), ('E', 'B', 'S')]
    WINGPTS['poly'] = {k: v for k, v in poly.items()}
    return poly, tris, sx


# plane basis for the membrane (shared by both wings; the right wing is the mirror image)
_poly, _tris, _ = wing(1); wing(-1)
_n = ((_poly['T1'] - _poly['W']).cross(_poly['T3'] - _poly['W'])).normalized()
_e1 = (_poly['T2'] - _poly['W']); _e1 = (_e1 - _n * _e1.dot(_n)).normalized(); _e2 = _n.cross(_e1)
def planar(p):
    d = V(p) - _poly['W']; return d.dot(_e1), d.dot(_e2)
_pts2 = {k: planar(v) for k, v in _poly.items()}
_umin = min(p[0] for p in _pts2.values()); _vmax = max(p[1] for p in _pts2.values())
PX_PER_UNIT = 32 / STUD
for p in _pts2.values():
    assert (p[0] - _umin) * PX_PER_UNIT < 630 and (_vmax - p[1]) * PX_PER_UNIT < 630, 'wing does not fit swatch'
def wing_uv(k):
    u, v = _pts2[k]; return K._uv_rect('wingS', 4 + (u - _umin) * PX_PER_UNIT, 4 + (_vmax - v) * PX_PER_UNIT)
for sg in (1, -1):
    sx = 'L' if sg > 0 else 'R'; bones = {'W': 'WingFore', 'J1': 'Finger1a', 'T1': 'Finger1b', 'J2': 'Finger2a', 'T2': 'Finger2b',
                                          'J3': 'Finger3a', 'T3': 'Finger3b', 'E': 'WingFore', 'S': 'WingUpper', 'B': 'Chest', 's1': 'Finger2a',
                                          's2': 'Finger3a', 's3': 'Chest'}
    for tri in _tris:
        for side in (1, -1):
            pts = [mx(_poly[k], sg) + V((0, 0, .02 * side)) for k in tri]
            wt = [{(bones[k] + '.' + sx) if bones[k] != 'Chest' else 'Chest': 1} for k in tri]
            ids = [BODY.add_v(p, w) for p, w in zip(pts, wt)]
            uv = [wing_uv(k) for k in tri]
            if side > 0: BODY.face(ids, 'wingS', uv)
            else: BODY.face(ids[::-1], 'wingS', uv[::-1])
        # orient the pair: front face normal should point +Z-ish / consistent; two-sided so either way is visible
PIVOT = V((0, -2.2, 5.2)); PITCH = 0.0
def pitch_pt(p):
    d = V(p) - PIVOT; c, sn = math.cos(PITCH), math.sin(PITCH)
    return PIVOT + V((d.x, d.y * c - d.z * sn, d.y * sn + d.z * c))
for acc in (BODY, GLOW):
    for i, wt in enumerate(acc.w):
        if wt.get('Head', 0) + wt.get('Jaw', 0) > .5: acc.v[i] = pitch_pt(acc.v[i])
for nm in ('Head', 'Jaw'):
    h, t, par = SK[nm]; SK[nm] = (pitch_pt(h), pitch_pt(t), par)
print('tris body', BODY.tris(), 'glow', GLOW.tris(), 'total', BODY.tris() + GLOW.tris())

# ---------------------------------------------------------- texture overlays
def paint_overlays():
    img = np.asarray(Image.open(os.path.join(TEX, 'Color.png')).convert('RGB')).astype(np.float32) / 255
    hexc = lambda h: np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255
    lerp = lambda a, b, t: a + (b - a) * np.clip(t, 0, 1)[..., None]
    # --- wing membrane: dark crimson, glowing orange->yellow trailing edge, studs from the white stud region
    x, y, w, h = K.ATLAS['slots']['wingS']; shade = img[y:y + h, x:x + w].copy()          # white * stud shade
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    uu = (xx - 4) / PX_PER_UNIT + _umin; vv = _vmax - (yy - 4) / PX_PER_UNIT
    edge = [_pts2[k] for k in ('T1', 's1', 'T2', 's2', 'T3', 's3')]
    dist = np.full((h, w), 99.0, np.float32)
    for (a, b) in zip(edge, edge[1:]):
        a = np.array(a); b = np.array(b); ab = b - a
        t = np.clip(((uu - a[0]) * ab[0] + (vv - a[1]) * ab[1]) / (ab @ ab), 0, 1)
        dist = np.minimum(dist, np.hypot(uu - (a[0] + t * ab[0]), vv - (a[1] + t * ab[1])))
    tipd = np.full((h, w), 99.0, np.float32)
    for k in ('T1', 'T2', 'T3'): tipd = np.minimum(tipd, np.hypot(uu - _pts2[k][0], vv - _pts2[k][1]))
    # dark band beside the leading bones (distance from W-J1-T1 / E-W)
    base = hexc('#4f1a1c'); mid = hexc('#8c2a1c'); hot = hexc('#ff7a14'); yel = hexc('#ffd44a')
    c = np.broadcast_to(base, (h, w, 3)).copy()
    gl = 1 - np.clip(dist / 1.6, 0, 1); c = lerp(c, np.broadcast_to(mid, (h, w, 3)), gl ** 1.4 * 1.2)
    c = lerp(c, np.broadcast_to(hot, (h, w, 3)), (1 - np.clip(dist / .55, 0, 1)) ** 1.3)
    c = lerp(c, np.broadcast_to(yel, (h, w, 3)), (1 - np.clip(tipd / .55, 0, 1)) ** 1.5 * .9 + (1 - np.clip(dist / .12, 0, 1)) * .5)
    lead = np.full((h, w), 99.0, np.float32)   # darker brown strip along the arm bones
    for ka, kb in (('E', 'W'), ('W', 'J1'), ('S', 'E')):
        a = np.array(_pts2[ka]); b = np.array(_pts2[kb]); ab = b - a
        t = np.clip(((uu - a[0]) * ab[0] + (vv - a[1]) * ab[1]) / (ab @ ab), 0, 1)
        lead = np.minimum(lead, np.hypot(uu - (a[0] + t * ab[0]), vv - (a[1] + t * ab[1])))
    c = lerp(c, np.broadcast_to(hexc('#2c1614'), (h, w, 3)), (1 - np.clip(lead / .7, 0, 1)) * .75)
    glowmask = np.clip(gl * 1.4, 0, 1)[..., None]
    img[y:y + h, x:x + w] = np.clip(c * (1 - glowmask * .6 + glowmask * .6 * np.clip(shade * .55 + .45, 0, 1.2)) * np.clip(shade * .5 + .5, 0, 1.1), 0, 1)
    # --- flame swatch: base deep orange -> tip bright yellow, facet-edge lines (same UV layout as stud_kit.shard)
    def paint_rect(name, fn):
        X0, Y0, W_, H_ = K.ATLAS['slots'][name]; im = Image.new('RGB', (W_, H_)); fn(ImageDraw.Draw(im), W_, H_, im)
        img[Y0:Y0 + H_, X0:X0 + W_] = np.asarray(im).astype(np.float32) / 255
    def flame_fn(d, w_, h_, im):
        a, b = (0xd8, 0x30, 0x08), (0xff, 0xe2, 0x6a)
        for j in range(h_):
            t = 1 - j / (h_ - 1)
            for i in range(w_):
                cc = tuple(int(a[k] + (b[k] - a[k]) * t ** .9) for k in range(3))
                d.point((i, j), fill=cc)
        P_ = lambda u, v: (u * (w_ - 1), (1 - v) * (h_ - 1))
        edges = [((0, 0), (.5, 1)), ((1, 0), (.5, 1)), ((0, .32), (.5, 1)), ((1, .32), (.5, 1)), ((.2, 0), (0, .32)), ((.8, 0), (1, .32)),
                 ((0, .32), (1, .32)), ((0, 0), (1, 0))]
        halo = im.copy(); hd = ImageDraw.Draw(halo)
        for p, q in edges: hd.line([P_(*p), P_(*q)], fill=(0xff, 0x90, 0x20), width=9)
        im.paste(Image.blend(im, halo.filter(ImageFilter.GaussianBlur(3)), .6))
        d = ImageDraw.Draw(im)
        for p, q in edges: d.line([P_(*p), P_(*q)], fill=(0xff, 0xc8, 0x50), width=2)
    def flame_core(d, w_, h_, im):
        for j in range(h_):
            v = 1 - j / (h_ - 1)
            for i in range(w_):
                u = i / (w_ - 1); core = max(0.0, 1 - abs(2 * u - 1)) ** 1.3 * (1 - v ** 1.6)
                edge = (0xd8, 0x3a, 0x08); mid = (0xff, 0x8a, 0x1a); hot = (0xff, 0xe2, 0x70)
                t = min(1.0, core * 1.25 + (1 - v) * .1)
                c0 = tuple(a + (b - a) * min(1, t * 2) for a, b in zip(edge, mid)); c1 = tuple(a + (b - a) * max(0, t * 2 - 1) for a, b in zip(c0, hot))
                d.point((i, j), fill=tuple(int(x) for x in c1))
    paint_rect('flame', flame_core)
    def eye_fn(d, w_, h_, im):
        im.paste((0x2a, 0x10, 0x06), [0, 0, w_, h_])
        cx, cy = w_ * .5, h_ * .5
        for k in range(40, 0, -1):          # pre-squashed: the lens is ~2.3x wider than tall
            t = k / 40; rx, ry = w_ * .45 * t, h_ * .47 * t
            col = tuple(int(a + (b - a) * (1 - t)) for a, b in zip((0xe0, 0x58, 0x08), (0xff, 0xb0, 0x28)))
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=col)
        for k in range(24, 0, -1):
            t = k / 24; rx, ry = w_ * .2 * t, h_ * .34 * t
            col = tuple(int(a + (b - a) * (1 - t)) for a, b in zip((0xff, 0xb4, 0x30), (0xff, 0xf2, 0xa0)))
            d.ellipse([cx - rx, cy - ry + h_ * .03, cx + rx, cy + ry + h_ * .03], fill=col)
    paint_rect('eye', eye_fn)
    def horn_fn(d, w_, h_, im):
        stops = [(0, (0xa8, 0x5a, 0x26)), (.3, (0xd0, 0x80, 0x34)), (.52, (0x5a, 0x40, 0x30)), (.7, (0x34, 0x2a, 0x26)), (1, (0x1e, 0x1a, 0x1a))]
        for j in range(h_):
            t = (j - 4) / (h_ - 8); t = min(max(t, 0), 1)
            for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
                if t0 <= t <= t1:
                    u = (t - t0) / (t1 - t0); d.line([(0, j), (w_, j)], fill=tuple(int(a + (b - a) * u) for a, b in zip(c0, c1)))
    paint_rect('horn', horn_fn)
    def ember_fn(d, w_, h_, im):
        for j in range(h_):
            t = 1 - j / (h_ - 1); d.line([(0, j), (w_, j)], fill=tuple(int(a + (b - a) * t) for a, b in zip((0x9a, 0x28, 0x08), (0xff, 0xb4, 0x30))))
    paint_rect('ember', ember_fn)
    def gem_fn(d, w_, h_, im):
        im.paste((0xff, 0xa8, 0x20), [0, 0, w_, h_]); c_ = (w_ / 2, h_ / 2)
        for (a, b), s in zip([((0, 0), (w_, 0)), ((w_, 0), (w_, h_)), ((w_, h_), (0, h_)), ((0, h_), (0, 0))],
                             [(0xff, 0xf0, 0x90), (0xff, 0xc8, 0x40), (0xe8, 0x68, 0x10), (0xff, 0xd8, 0x60)]):
            d.polygon([a, b, c_], fill=s)
        d.line([(0, 0), (w_, h_)], fill=(0xff, 0xfa, 0xd0), width=2); d.line([(w_, 0), (0, h_)], fill=(0xff, 0xfa, 0xd0), width=2)
    paint_rect('gem', gem_fn)
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(os.path.join(TEX, 'Color.png'))


paint_overlays()

# ------------------------------------------------------------------- scene
K.new_scene()
mb = K.make_material('BoneDragonBody', os.path.join(TEX, 'Color.png'), os.path.join(TEX, 'Normal.png'))
mg = K.make_material('BoneDragonGlow', os.path.join(TEX, 'Color.png'), glow=True, emission=1.4)
body = K.build_object(BODY, mb); glow = K.build_object(GLOW, mg)
arm = K.build_armature('BoneDragon', SK, [body, glow])
A.bind(arm)
print('bones', len(SK))

# --------------------------------------------------------------- animation
LEGMAP = {'FL': ('FrontUpper.L', 'FrontLower.L', 'FrontFoot.L', .0), 'HR': ('HindUpper.R', 'HindLower.R', 'HindFoot.R', .0),
          'FR': ('FrontUpper.R', 'FrontLower.R', 'FrontFoot.R', .5), 'HL': ('HindUpper.L', 'HindLower.L', 'HindFoot.L', .5)}
TAILB = [f'Tail{i}' for i in range(1, 6)]
WINGB = [('WingUpper', 0), ('WingFore', .08)] + [(f'Finger{i}{s}', .14 + .04 * (s == 'b')) for i in (1, 2, 3) for s in 'ab']
S_ = A.S


def wings(f, n, amp_up, amp_fore, amp_fin, ph=0.0):
    for sg, sx in ((1, 'L'), (-1, 'R')):
        A.set_rot(f'WingUpper.{sx}', (Y, -sg * amp_up * S_(f, n, ph)))
        A.set_rot(f'WingFore.{sx}', (Y, -sg * amp_fore * S_(f, n, ph - .08)))
        for i in (1, 2, 3):
            A.set_rot(f'Finger{i}a.{sx}', (Y, -sg * amp_fin * S_(f, n, ph - .14)), (X, 2 * S_(f, n, ph - .14)))
            A.set_rot(f'Finger{i}b.{sx}', (Y, -sg * amp_fin * 1.3 * S_(f, n, ph - .2)))


def tail(f, n, amp, ph=0.0, vert=0.0):
    for i, b in enumerate(TAILB):
        A.set_rot(b, (Z, amp * S_(f, n, ph - .1 * i)), (X, vert * S_(f, n, ph - .1 * i - .25)))


def idle(f, n):
    pb = arm.pose.bones
    pb['Torso'].location = A.world_loc('Torso', (0, 0, .05 * S_(f, n, 0)))
    A.set_rot('Torso', (X, .8 * S_(f, n, .1)))
    A.set_rot('Chest', (X, 1.6 * S_(f, n, 0)))
    A.set_rot('Neck1', (Z, 3 * S_(f, n, .15)), (X, -1 * S_(f, n, .1)))
    A.set_rot('Neck2', (Z, 4 * S_(f, n, .2)), (X, 1.5 * S_(f, n, .1)))
    A.set_rot('Head', (Z, 5 * S_(f, n, .25)), (X, 2 * S_(f, n, .0)))
    A.set_rot('Jaw', (X, 3.5 + 3.5 * S_(f, n, .3)))
    tail(f, n, 7, .0, 2)
    wings(f, n, 3, 4, 5, 0.05)


def walk(f, n):
    pb = arm.pose.bones
    for leg, (up, lo, ft, ph) in LEGMAP.items():
        p = (f / n + ph) % 1; dy, dz = A.foot_offset(p, stride=1.5, lift=.55, duty=.62)
        pb['IK_' + leg].location = A.world_loc('IK_' + leg, (0, dy, dz))
    bob = .09 * math.cos(4 * math.pi * f / n)
    pb['Torso'].location = A.world_loc('Torso', (0, 0, bob))
    A.set_rot('Torso', (Y, 2.5 * S_(f, n, 0)), (Z, 3 * S_(f, n, .25)))
    A.set_rot('Chest', (Z, -4 * S_(f, n, .25)), (Y, -2 * S_(f, n, 0)))
    A.set_rot('Neck1', (Z, 3 * S_(f, n, .5)), (X, 1.5 * S_(f, n, .15)))
    A.set_rot('Neck2', (Z, 3 * S_(f, n, .5)), (X, 1.5 * S_(f, n, .2)))
    A.set_rot('Head', (Z, 2 * S_(f, n, .5)), (X, 2 * S_(f, n, .25)))
    A.set_rot('Jaw', (X, 4 + 2 * S_(f, n, .1)))
    tail(f, n, 11, .0, 3)
    wings(f, n, 2.5, 3.5, 4.5, .1)


A.add_leg_ik(LEGMAP, root='Root')
clips = [('Idle', 90, idle, False), ('Walk', 40, walk, False)]
A.bake_clips(clips, LEGMAP, step={'Idle': 2})
bpy.context.scene.frame_start, bpy.context.scene.frame_end = 0, 90
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, 'BoneDragon.blend'))
print('saved')
