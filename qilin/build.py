"""Verdant Qilin Guardian (Grass Boss) - stud-style procedural build.

    python3 tools/make_atlas.py <Roblox-HD-Studs> atlas_config.json textures
    python3 build.py            # -> out/Qilin.blend, Qilin.glb, Qilin.fbx

Z up, the creature faces -Y, its left is +X, 1 unit = 1 stud.
Everything is leaves + blocks: olive barrel/head/thighs, brown legs, cream hooves/antlers/belly,
hundreds of faceted leaf plates. Glowing parts (gem, eyes, neon leaves) live in their own
mesh (Qilin_Glow) and are driven by the Emissive.png atlas.
"""
import bpy, sys, os, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import stud_kit as K
from mathutils import Vector as V, Matrix

OUT = os.path.join(HERE, 'out'); os.makedirs(OUT, exist_ok=True)
K.init(os.path.join(HERE, 'textures', 'atlas_regions.json'), stud=0.45)
BODY, GLOW = K.MeshAcc('Qilin_Body'), K.MeshAcc('Qilin_Glow', glow=True)
R = {'Root': 1.0}
REC = []   # (first face idx, centre, up) of every body leaf, recoloured from the reference after layout
rnd = random.Random(7)
SIDES = (1, -1)


# ----------------------------------------------------------------------------- leaf
def leaf(base, d, up, L, Wd, slot=None, glow=False, thick=0.28, curl=0.0, bottom=True):
    """Faceted leaf plate (8 tris): base -> widest at 38% -> pointed tip, ridge on top.
    d = growth direction, up = which way the top face looks. Glow leaves use the leaf-shaped
    glowleaf swatch with explicit UVs (neon rim + tip) and live in the glow mesh."""
    d = V(d).normalized(); up = V(up); Wd *= 1.3
    s = d.cross(up)
    if s.length < .2: s = d.cross(V((0, 0, 1)) if abs(d.z) < .9 else V((1, 0, 0)))
    s.normalize(); u = s.cross(d).normalized()
    base = V(base); base.x *= .9; k = min(1.0, max(0.0, (base.z - 1.2) / 3.0)); base.z += .9 * k * k * (3 - 2 * k); h = Wd * thick
    b = base
    l = base + d * (.38 * L) - s * (Wd / 2); r = base + d * (.38 * L) + s * (Wd / 2)
    T = base + d * L + u * (curl * L)
    m1 = base + d * (.30 * L) + u * h; m2 = base + d * (.62 * L) + u * (h * .8 + curl * L * .3)
    acc = GLOW if glow else BODY
    slot = 'glowleaf' if glow else slot
    ids = {k: acc.add_v(p, R) for k, p in dict(b=b, l=l, r=r, T=T, m1=m1, m2=m2).items()}
    tris = [('b', 'r', 'm1'), ('b', 'm1', 'l'), ('r', 'm2', 'm1'), ('m1', 'm2', 'l'), ('r', 'T', 'm2'), ('m2', 'T', 'l'),
            ('b', 'l', 'r'), ('l', 'T', 'r')][:8 if bottom else 6]
    UVm = dict(b=(.5, 0), l=(0, .38), r=(1, .38), T=(.5, 1), m1=(.5, .28), m2=(.5, .62))
    x0, y0, w, hh = K.ATLAS['slots']['glowleaf']; S = K.ATLAS['size']
    uv = lambda k: ((x0 + 3 + UVm[k][0] * (w - 6)) / S, 1 - (y0 + 3 + (1 - UVm[k][1]) * (hh - 6)) / S)
    if not glow: REC.append((len(acc.f), (b + T) / 2, up, len(tris)))
    for t in tris:
        acc.face([ids[k] for k in t], slot, [uv(k) for k in t] if glow else None)


def pick(outer, bias=0.0):
    """Leaf swatch by exposure: inner = deep green, outer = lime."""
    x = outer + bias + rnd.uniform(-.28, .28)
    if x < .12: return 'leafX'
    if x < .3: return 'leafD'
    if x < .58: return 'leafM'
    return 'leafL'


def unit(*a): return V(a).normalized()


# --------------------------------------------------------------------- body blocks
def torso():
    """Barrel measured from the side view: chest at y=-6, rump y=4.5, back z~7.8, belly rising toward the rear."""
    rings = [dict(c=(0, y, cz), rx=rx, ry=ry, w=R) for y, rx, ry, cz in
             [(-6.1, 1.3, 1.5, 5.7), (-5.5, 2.1, 2.3, 5.9), (-4.0, 2.7, 2.5, 6.0), (-1.5, 2.6, 1.8, 6.3),
              (1.0, 2.6, 1.6, 6.4), (3.4, 2.5, 1.7, 6.3), (4.5, 1.9, 1.5, 6.3)]]
    K.loft(BODY, rings, 8, lambda n, c, i: 'cream' if n.z < -.5 else 'olive', cap0='olive', cap1='olive')
    for sd in SIDES:   # big octagonal haunch slab (y 1.9..4.4, z 3.9..7.5)
        rs = [dict(c=(sd * x, 3.15, 5.7), rx=rx, ry=ry, w=R, T=(sd, 0, 0), up=(0, 1, 0))
              for x, rx, ry in [(1.4, 1.1, 1.5), (1.7, 1.45, 2.0), (2.85, 1.45, 2.0), (3.1, 1.15, 1.6)]]
        K.loft(BODY, rs, 8, lambda n, c, i: 'olive', cap0='olive', cap1='olive')
        rs = [dict(c=(sd * x, -3.7, 5.9), rx=rx, ry=ry, w=R, T=(sd, 0, 0), up=(0, 1, 0))      # shoulder mass
              for x, rx, ry in [(1.5, 1.3, 1.6), (1.8, 1.6, 2.1), (2.8, 1.6, 2.1), (3.05, 1.2, 1.7)]]
        K.loft(BODY, rs, 8, lambda n, c, i: 'olive', cap0='olive', cap1='olive')


def leg(x, pts, hs, hoof_y):
    """pts: [(y, z)] joints top->bottom (angled), hs: half-sizes (across x, along y)."""
    rings = [dict(c=(x, y, z), rx=hx, ry=hy, w=R, T=(0, 0, -1), up=(0, 1, 0)) for (y, z), (hx, hy) in zip(pts, hs)]
    K.loft(BODY, rings, 8, lambda n, c, i: 'brown', cap0='brown', cap1='brown')
    K.box(BODY, (x, hoof_y + .1, 1.0), (1.8, 1.6, 1.0), 'brown', R, taper=.9)
    for dx in (-.55, .55):
        K.box(BODY, (x + dx * 1.2, hoof_y - .35, .55), (1.2, 2.2, 1.1), 'cream', R, taper=.75)


def belly():
    K.box(BODY, (0, -0.3, 4.55), (4.2, 6.2, .45), 'cream', R, taper=.9)


def legs():
    for sd in SIDES:
        leg(sd * 2.5, [(-3.9, 5.4), (-4.8, 3.6), (-5.8, 2.0), (-6.4, 1.2)], [(1.15, 1.2), (1.05, 1.05), (.9, .9), (1.0, 1.0)], -6.5)
        leg(sd * 2.4, [(3.2, 5.2), (5.2, 3.5), (5.1, 2.0), (5.0, 1.2)], [(1.15, 1.3), (1.0, 1.0), (.85, .85), (.95, .95)], 4.95)


def neck_head():
    rings = [dict(c=c, rx=rx, ry=ry, w=R) for c, rx, ry in
             [((0, -4.6, 6.0), 1.5, .9), ((0, -5.3, 7.4), 1.15, .95), ((0, -5.5, 9.0), 1.0, .95), ((0, -5.6, 10.2), .95, .9)]]
    K.loft(BODY, rings, 8, lambda n, c, i: 'cream' if n.y < -.15 else 'olive', cap0='olive', cap1='olive')
    P = V((0, -5.95, 10.9)); M = Matrix.Rotation(math.radians(8), 3, 'X')
    hb = lambda off, size, slot, taper=1.0, slots=None: K.box(BODY, P + M @ V(off), size, slot, R, M, taper, slots)
    hb((0, .1, 0), (3.0, 2.4, 2.5), 'olive')                        # skull
    mz = M @ V((0, 0, 1)); mt = M @ V((0, -1, 0))
    rings = [dict(c=P + M @ V((0, y, z)), rx=hw, ry=hh, w=R, T=mt, up=mz)
             for y, z, hw, hh in [(-.6, -.2, 1.45, 1.3), (-1.5, -.45, 1.15, 1.15), (-2.3, -.55, .85, .9), (-2.75, -.55, .55, .65)]]
    K.loft(BODY, rings, 8, lambda n, c, i: 'cream' if n.z < -.3 else 'olive', cap0='olive', cap1='nose')    # tapered muzzle
    K.solid_spike(BODY, P + M @ V((0, -2.0, -1.0)), (0, -.35, -1), 1.5, 1.5, R, 'cream')                      # chin point
    for sd in SIDES:
        c = P + M @ V((sd * 1.2, -1.17, .05)); n = M @ V((sd * .35, -.94, 0))
        K.eye_lens(GLOW, c + n * .03, n, M @ V((0, 0, 1)), M @ V((-sd, -.1, .12)), R, scale=1.35)
    K.gem_plate(GLOW, (0, -6.45, 6.4), (0, -1, 0), (0, 0, 1), .9, 1.4, .6, R)    # chest emerald


ANTLER = [  # (points (x,y,z), half-size start, half-size end) - measured from the front + side panels
    ([(0.6, -6.6, 11.8), (1.4, -5.9, 12.7), (2.4, -4.9, 13.4), (3.4, -3.9, 14.0), (4.0, -2.4, 14.4), (4.6, -1.0, 15.2)], .5, .22),
    ([(1.8, -5.5, 13.2), (1.85, -5.4, 14.5), (1.9, -5.4, 15.7)], .36, .13),
    ([(0.9, -6.2, 12.3), (1.0, -5.9, 13.2), (1.05, -5.7, 14.2)], .34, .13),
    ([(3.5, -3.4, 14.0), (4.2, -3.2, 14.9), (4.8, -3.0, 15.8)], .3, .12),
    ([(1.6, -5.4, 12.9), (2.6, -4.6, 12.8), (3.7, -4.0, 12.6)], .3, .12),
]


def antlers():
    for sd in SIDES:
        for pts, h0, h1 in ANTLER:
            rings = []
            for i, p in enumerate(pts):
                t = i / (len(pts) - 1); hsz = (h0 + (h1 - h0) * t) * 1.414
                rings.append(dict(c=(sd * p[0], p[1], p[2]), rx=hsz, ry=hsz, w=R))
            K.loft(BODY, rings, 4, lambda n, c, i: 'cream', cap0='cream', cap1='cream', rot=math.pi / 4)


# -------------------------------------------------------------------------- leaves
def sphere_pts(n, c, r):
    """Fibonacci sphere -> (point, outward unit normal-ish) on an ellipsoid with radii r."""
    out = []
    for i in range(n):
        z = 1 - 2 * (i + .5) / n; rr = math.sqrt(1 - z * z); a = i * 2.399963
        d = V((rr * math.cos(a), rr * math.sin(a), z))
        p = V(c) + V((d.x * r[0], d.y * r[1], d.z * r[2]))
        nrm = V((d.x / r[0], d.y / r[1], d.z / r[2])).normalized()
        out.append((p, nrm))
    return out


def mane():
    """Dense layered rows of mid-size leaves down the neck (head -> withers), each row a ring around the neck axis."""
    c0, c1 = V((0, -5.2, 11.3)), V((0, -1.6, 7.9)); ax = (c1 - c0).normalized()
    rows = 17
    for i in range(rows):
        t = i / (rows - 1); c = c0.lerp(c1, t); rx = 1.3 + .9 * t; rz = 1.5 + .8 * t
        n = 10 if i < 4 else 12
        for k in range(n):
            th = (k + .5 * (i % 2)) / n * 2 * math.pi
            rad = V((math.sin(th) * rx, 0, math.cos(th) * rz)); nrm = V((math.sin(th) / rx, .15, math.cos(th) / rz)).normalized()
            if nrm.z < -.55 or (i < 2 and nrm.z < -.1): continue
            p = c + rad
            if p.y < -6.0 and abs(p.x) < 1.8 and p.z < 12.4: continue
            d = (ax * .9 + nrm * (.4 + .2 * (1 - t))).normalized()
            L = rnd.uniform(1.9, 2.8) * (.9 + .25 * t)
            outer = .5 + .45 * (nrm.z > .3) + rnd.uniform(-.2, .2) - .1 * t
            leaf(p - nrm * .2, d, nrm, L, L * .5, slot=pick(outer), glow=(rnd.random() < .1), bottom=False)


def crown_and_face():
    base = V((0, -6.0, 11.7))
    leaf(base, (0, .12, 1), (0, -1, .1), 3.1, 1.5, 'leafL')
    for sd in SIDES:
        leaf(base + V((sd * .55, .05, -.1)), (sd * .3, .2, 1), (sd * .4, -1, .1), 2.4, 1.15, 'leafM')
        leaf(base + V((sd * 1.05, .2, -.35)), (sd * .65, .25, 1), (sd * .5, -1, .1), 2.0, 1.0, 'leafL')
        leaf(base + V((sd * 1.5, .35, -.7)), (sd * .9, .3, .7), (sd * .3, -1, .3), 1.9, .9, 'leafD')
        leaf(base + V((sd * .3, 1.0, -.25)), (sd * .15, .55, 1), (0, 0, 1), 2.3, 1.1, 'leafM')
        leaf(base + V((sd * 1.0, 1.4, -.5)), (sd * .5, .6, .9), (0, 0, 1), 2.0, 1.0, 'leafD')
        # brow leaves over the eyes
        leaf((sd * .7, -7.25, 11.55), (sd * .85, -.1, .35), (sd * .2, -.6, .8), 1.5, .7, 'leafD')
        leaf((sd * 1.1, -6.9, 11.7), (sd * 1.0, .1, .5), (0, -.3, 1), 1.9, .85, 'leafM')
        # cheek flares
        for k, (yy, zz, L, sl) in enumerate([(-5.6, 10.3, 2.3, 'leafL'), (-5.2, 10.0, 2.4, 'leafM'), (-4.9, 10.6, 2.5, 'leafL'),
                                              (-5.4, 11.2, 2.1, 'leafM'), (-4.8, 9.5, 2.4, 'leafD')]):
            leaf((sd * 1.35, yy, zz), (sd * 1.0, .45, .15 - .12 * k), (sd * .2, 0, 1), L, L * .42, sl, glow=(k == 0 or k == 3))
        # glowing leaf at antler tip + behind shoulders
        leaf((sd * 3.7, -3.4, 14.2), (sd * .5, .7, .35), (0, 0, 1), 1.2, .55, glow=True)
        leaf((sd * 2.8, -3.6, 9.4), (sd * .15, .15, 1), (sd * 1, 0, 0), 1.3, .55, glow=True)


def face_frame():
    for k in range(12):
        a = k / 12 * 2 * math.pi; rad = V((math.sin(a), 0, math.cos(a)))
        if rad.z < .25: continue
        p = V((rad.x * 1.75, -5.7, 10.9 + rad.z * 1.45))
        leaf(p, rad * .75 + V((0, .75, 0)), rad + V((0, -.6, 0)), rnd.uniform(1.7, 2.3), 1.0, pick(.55 + .2 * (k % 2)), glow=(k % 5 == 0))


def head_halo():
    for sd in SIDES:
        for k, (yy, zz, L, sl) in enumerate([(-4.4, 12.4, 2.8, 'leafL'), (-4.0, 11.4, 3.0, 'leafM'), (-4.2, 10.4, 2.8, 'leafL'), (-3.6, 12.2, 2.6, 'leafL'),
                                              (-3.2, 11.0, 3.0, 'leafM'), (-4.6, 9.4, 2.4, 'leafD'), (-3.4, 9.6, 2.8, 'leafL'), (-3.0, 12.4, 2.5, 'leafM')]):
            leaf((sd * 1.6, yy, zz - .9), (sd * 1.0, .75, .12 + .08 * (k % 3)), (sd * 1, 0, .4), L, L * .45, sl, glow=(k == 3))


def throat():
    for k in range(12):
        a = k / 12 * 2 * math.pi; z = 7.6 + (k % 3) * .9
        rad = V((math.sin(a), math.cos(a) * .6, 0)); c = V((0, -5.8, z))
        leaf(c + rad * .9, rad * .5 + V((0, .7, -.3)), rad + V((0, 0, .6)), 2.3, 1.1, pick(.25 + .3 * (k % 2)))


def chest_flower():
    c = V((0, -6.1, 5.4))
    for ring, (cnt, r0, L, W, glow) in enumerate([(14, 1.0, 2.0, .85, False), (12, .7, 1.3, .6, True)]):
        for i in range(cnt):
            a = (i + (.5 if ring else 0)) / cnt * 2 * math.pi
            rad = V((math.sin(a), 0, math.cos(a)))
            if rad.z < -.5: continue
            ll = L * (1.25 if rad.z > .5 else (.85 if rad.z < -.4 else 1.0))
            leaf(c + rad * r0 + V((0, -.1 - ring * .1, 0)), rad + V((0, -.45, 0)), (0, -1, .1), ll, W * ll / L * 1.1,
                 pick(.7 + .2 * ring), glow=glow and rnd.random() < .6)
    # outer fan of larger leaves below the shoulder/neck
    for sd in SIDES:
        for k in range(5):
            leaf((sd * (.8 + .5 * k), -5.2 + .25 * k, 7.0 - .35 * k), (sd * (.6 + .15 * k), -.5 + .15 * k, .4 - .3 * k), (0, -1, .5),
                 2.0, .95, pick(.6))


def shoulder_wings():
    """Big flat shoulder plates (measured: ~3.5-4 long, ~2 wide) lying over the barrel, light on top, dark behind."""
    for sd in SIDES:
        for row, z in enumerate([7.7, 6.8, 5.9]):
            for j in range(3):
                y = -4.4 + j * 1.25 + row * .35 + rnd.uniform(-.2, .2)
                L = rnd.uniform(3.0, 3.8) - .2 * row
                tilt = rnd.uniform(-.45, .1)
                leaf((sd * 3.45, y, z), (sd * (.3 + .2 * rnd.random()), .7, tilt), (sd * 1, 0, .3 + .4 * rnd.random()), L, L * .52,
                     'leafL' if (j + row) % 3 else 'leafM', thick=.2, curl=.08)
        for j in range(6):   # dark flank leaves behind the plates
            y = -2.0 + j * .6; z = 5.8 - (j % 3) * .6
            leaf((sd * 3.3, y, z), (sd * .2, .6, -.7), (sd * 1, 0, .4), rnd.uniform(2.0, 2.7), 1.2, 'leafD' if j % 2 else 'leafX')
        for j in range(4):   # lifted crest leaves
            leaf((sd * (1.3 + .25 * j), -4.0 + 1.0 * j, 7.4), (sd * .5, .7, .5), (sd * .3, 0, 1), 2.2, 1.0, pick(.8), glow=(j == 1))


def back_ridge():
    for i, y in enumerate([-3.2 + k * .8 for k in range(11)]):
        for sd in (-1, 1):
            if i % 2 and sd > 0: continue
            L = rnd.uniform(1.4, 1.9)
            leaf((sd * .55, y, 7.2), (sd * .3, .8, .35), (sd * .3, 0, 1), L, L * .45, pick(.6), glow=(i % 4 == 0 and sd > 0))
        leaf((0, y + .3, 7.25), (0, .8, .4), (0, 0, 1), 1.5, .7, 'leafL' if i % 2 else 'leafM')


def tail():
    rings = [dict(c=c, rx=rx, ry=ry, w=R) for c, rx, ry in
             [((0, 4.2, 7.3), .62, .5), ((0, 5.2, 7.5), .55, .48), ((0, 6.2, 7.4), .5, .44), ((0, 7.0, 7.1), .42, .38)]]
    K.loft(BODY, rings, 8, lambda n, c, i: 'bark' if i > 0 else 'olive', cap0='olive', cap1='bark')
    ax = unit(0, .9, -.4); anchor = V((0, 7.0, 5.6))
    for i in range(64):
        radial = V((rnd.uniform(-1, 1), rnd.uniform(-.4, .4), rnd.uniform(-1, 1)))
        radial -= ax * radial.dot(ax); radial.normalize()
        d = (ax + radial * rnd.uniform(.35, 1.1)).normalized()
        L = rnd.uniform(3.8, 6.0) * (1.0 - .25 * abs(radial.x))
        p = anchor + V((rnd.uniform(-.4, .4), rnd.uniform(-.8, .6), rnd.uniform(-.4, .3)))
        leaf(p, d, radial + V((0, 0, .5)), L, L * .5, pick(.35 + .5 * rnd.random()), glow=(rnd.random() < .08))
    for i in range(9):   # hanging centre cluster (reaches low in the back view)
        d = unit(rnd.uniform(-.25, .25), .35, -1)
        leaf(anchor + V((rnd.uniform(-.4, .4), rnd.uniform(.3, 1.4), -.2)), d, (rnd.uniform(-1, 1), -1, .2), rnd.uniform(4.2, 5.8), 1.7, pick(.35 + .5 * rnd.random()), glow=(i % 5 == 0))
    for i in range(6):   # upward-flicking leaves on the tuft
        d = unit(rnd.uniform(-.6, .6), .55, .45 + rnd.random() * .3)
        leaf(anchor + V((rnd.uniform(-.3, .3), rnd.uniform(-.8, .2), .2)), d, (0, 0, 1), rnd.uniform(2.0, 3.0), 1.1, pick(.7), glow=rnd.random() < .3)


def leg_leaves():
    specs = [(-6.5, True), (4.95, False)]
    for sd in SIDES:
        for y, front in specs:
            x = sd * (3.1 if front else 3.0)
            yy = y - (.2 if front else 0)
            leaf((x + sd * .35, yy - .2, 1.0), (sd * .12, -.15 if front else .1, 1), (sd, 0, .2), 2.9, 1.3, 'leafL', thick=.2)
            leaf((x + sd * .85, yy + .2, 1.0), (sd * .5, .1, 1), (sd, 0, .3), 2.0, .95, 'leafM')
            leaf((x - sd * .35, yy - .6, .9), (-sd * .2, -.3, 1), (-sd, 0, .3), 1.7, .8, 'leafD')
            leaf((x + sd * .5, yy + .7, 1.0), (sd * .3, .6, .9), (sd, 0, .3), 1.5, .7, 'leafL', glow=False)
        for dy, zz in ((-4.9, 3.5), (-4.3, 4.1), (3.7, 3.4)):    # shin leaves
            leaf((sd * 3.05, dy, zz), (sd * .3, .35, .7), (sd, 0, .3), 1.6, .7, 'leafM')
    # inner leg leaves visible in the front view
    for sd in SIDES:
        leaf((sd * 1.75, -5.3, 1.0), (-sd * .2, -.1, 1), (-sd, 0, .3), 1.8, .8, 'leafM')


def recolor_from_reference():
    """Leaf colour field transferred from the reference views: every body leaf looks up the reference
    pixel at its projected position (views registered by silhouette bbox) and takes the matching shade."""
    import numpy as np
    from PIL import Image
    ref = np.asarray(Image.open(os.path.join(HERE, 'ref', 'ref.png')).convert('RGB')).astype(float)
    crops = {'front': (765, 62, 1098, 458), 'back': (1132, 62, 1436, 458), 'left': (765, 505, 1090, 758), 'right': (1115, 505, 1440, 758)}
    pts = [v for a in (BODY, GLOW) for v in a.v]
    lo = V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))); hi = V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    info = {}
    for n, (x0, y0, x1, y1) in crops.items():
        a = ref[y0:y1, x0:x1]; bg = np.median(np.concatenate([a[:6].reshape(-1, 3), a[-6:].reshape(-1, 3)]), 0)
        m = np.linalg.norm(a - bg, axis=2) > 38; ys, xs = np.where(m)
        info[n] = (a, xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    def sample(view, p):
        a, bx0, by0, bx1, by1 = info[view]
        h = {'front': p.x, 'back': -p.x, 'left': p.y, 'right': -p.y}[view]
        hl, hh = {'front': (lo.x, hi.x), 'back': (-hi.x, -lo.x), 'left': (lo.y, hi.y), 'right': (-hi.y, -lo.y)}[view]
        u = (h - hl) / (hh - hl); v = (hi.z - p.z) / (hi.z - lo.z)
        px = int(bx0 + u * (bx1 - bx0)); py = int(by0 + v * (by1 - by0))
        px = min(max(px, 3), a.shape[1] - 4); py = min(max(py, 3), a.shape[0] - 4)
        return a[py - 2:py + 3, px - 2:px + 3].reshape(-1, 3).mean(0) / 255
    changed = 0
    for first, c, up, nt in REC:
        if abs(up.x) > abs(up.y) * .8: view = 'left' if up.x > 0 else 'right'
        else: view = 'front' if up.y < 0 else 'back'
        rgb = sample(view, c); mx, mn = rgb.max(), rgb.min()
        if not (rgb[1] >= rgb[0] and rgb[1] >= rgb[2] and mx - mn > .12): continue      # not leaf green (bg / cream / brown)
        lum = .3 * rgb[0] + .59 * rgb[1] + .11 * rgb[2]
        slot = 'leafX' if lum < .2 else 'leafD' if lum < .3 else 'leafM' if lum < .43 else 'leafL'
        for i in range(first, first + nt):
            idx, _, uvs = BODY.f[i]; BODY.f[i] = (idx, slot, uvs)
        changed += 1
    print('recoloured leaves from reference:', changed, 'of', len(REC))


def build():
    torso(); belly(); legs(); neck_head(); antlers()
    mane(); head_halo(); face_frame(); throat(); crown_and_face(); chest_flower(); shoulder_wings(); back_ridge(); tail(); leg_leaves()
    recolor_from_reference()
    print('tris body', BODY.tris(), 'glow', GLOW.tris(), 'total', BODY.tris() + GLOW.tris())


def material():
    import bpy
    m = bpy.data.materials.new('QilinStud'); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    ld = lambda f, cs=None: (lambda t: (setattr(t, 'image', bpy.data.images.load(os.path.join(HERE, 'textures', f), check_existing=True)), t)[1])(nt.nodes.new('ShaderNodeTexImage'))
    c = ld('Color.png'); e = ld('Emissive.png'); nm = ld('Normal.png'); nm.image.colorspace_settings.name = 'Non-Color'
    e.image.colorspace_settings.name = 'sRGB'
    nt.links.new(c.outputs['Color'], b.inputs['Base Color'])
    add = nt.nodes.new('ShaderNodeVectorMath'); add.operation = 'ADD'
    sc_ = nt.nodes.new('ShaderNodeVectorMath'); sc_.operation = 'SCALE'; sc_.inputs['Scale'].default_value = .2
    nt.links.new(c.outputs['Color'], sc_.inputs[0]); nt.links.new(e.outputs['Color'], add.inputs[0]); nt.links.new(sc_.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = 1.0
    n = nt.nodes.new('ShaderNodeNormalMap'); n.inputs['Strength'].default_value = .8
    nt.links.new(nm.outputs['Color'], n.inputs['Color']); nt.links.new(n.outputs['Normal'], b.inputs['Normal'])
    b.inputs['Roughness'].default_value = .5
    return m


if __name__ == '__main__':
    import bpy
    build()
    K.new_scene(); mat = material()
    body = K.build_object(BODY, mat); glow = K.build_object(GLOW, mat)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'Qilin.blend'))
    print('saved')
