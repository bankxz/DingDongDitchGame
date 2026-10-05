"""Verdant Qilin Guardian - stud-style Roblox model, fully procedural.
Run:  python3 build.py            (needs `pip install bpy==4.2.0 pillow numpy`)
Writes out/VerdantQilin.blend.  Z up, model faces -Y, its left side is +X, 1 unit = 1 stud.
"""
import bpy, sys, os, math, random
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
import stud_kit as K
import anim_kit as A
from mathutils import Vector as _V, Matrix

def V(*a):
    return _V((0, 0, 0)) if not a else (_V(a[0]) if len(a) == 1 else _V(a))

K.init(os.path.join(HERE, 'textures', 'atlas_regions.json'), stud=0.3)
BODY = K.MeshAcc('Qilin_Body')
GLOW = BODY          # single mesh: glow comes from the emissive texture, not a second part
W = K.W
rnd = random.Random(7)
Z = V((0, 0, 1)); Y = V((0, 1, 0)); X = V((1, 0, 0))


# ------------------------------------------------------------------ weights
def interp_w(stops, v):
    """stops [(value, bone)] ascending -> blended weight dict."""
    if v <= stops[0][0]: return {stops[0][1]: 1.0}
    if v >= stops[-1][0]: return {stops[-1][1]: 1.0}
    for (a, ba), (b, bb) in zip(stops, stops[1:]):
        if a <= v <= b:
            t = (v - a) / (b - a)
            return W(ba, bb, t) if ba != bb else {ba: 1.0}
SPINE = [(-6.8, 'Chest'), (-4.2, 'Torso'), (-2.0, 'Pelvis')]
NECK = [(4.9, 'Chest'), (5.8, 'Neck1'), (6.6, 'Neck2'), (7.4, 'Head')]
def wpos(p):
    p = V(p)
    if p.y < -6.0 and p.z > 5.0: return interp_w(NECK, p.z)
    if p.y > -0.9: return W('Tail1')
    return interp_w(SPINE, p.y)


# ------------------------------------------------------------------ solids
def solid(acc, pts, faces, slot, wt, slots=None):
    """Convex solid; faces are vertex-index lists, wound outward automatically."""
    ids = [acc.add_v(p, wt if isinstance(wt, dict) else wt(p)) for p in pts]
    cen = sum((V(p) for p in pts), V()) / len(pts)
    for fi, f in enumerate(faces):
        P = [V(pts[i]) for i in f]
        n = V()
        for i in range(len(P)): n += P[i].cross(P[(i + 1) % len(P)])
        fc = sum(P, V()) / len(P)
        idx = [ids[i] for i in f]
        if n.dot(fc - cen) < 0: idx = idx[::-1]
        acc.face(idx, (slots or {}).get(fi, slot))

BOXF = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]

def frustum(acc, p0, p1, w0, w1, slot, wt, h0=None, h1=None, up=None, caps=(True, True), slots=None):
    """Rectangular frustum p0->p1; w = width along 'side', h = depth along 'up'."""
    p0, p1 = V(p0), V(p1); T = (p1 - p0).normalized()
    s, u = K.frame(T, V(up) if up is not None else Z)
    h0 = h0 if h0 is not None else w0; h1 = h1 if h1 is not None else w1
    pts = []
    for p, w, h in ((p0, w0, h0), (p1, w1, h1)):
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts.append(p + s * (a * w / 2) + u * (b * h / 2))
    fs = [BOXF[2], BOXF[3], BOXF[4], BOXF[5]] + ([BOXF[0]] if caps[0] else []) + ([BOXF[1]] if caps[1] else [])
    solid(acc, pts, fs, slot, wt, slots)


LEAF_UV = {'b': (128, 252), 'R': (252, 143), 't': (128, 4), 'L': (4, 143), 'c': (128, 120)}   # px in the 256 leaf swatch
LEAF_FLAT = (6, 6)                                                                             # plain colour outside the kite

def leaf(acc, base, d, length, width, wt, slot, n=None, closed=True, ridge=0.28, widest=0.45,
         droop=0.06, slot_b=None, wmin=0.0):
    """Broad faceted kite leaf. Top = 4 ridge facets textured from the leaf swatch (studs + glowing rim,
    see Emissive.png); optional 2-tri back."""
    if slot == 'glowLeaf': slot = 'limeBright'
    d = V(d).normalized(); base = V(base); width = max(width, length * wmin)
    n = V(n) if n is not None else Z
    n = n - d * n.dot(d)
    if n.length < 1e-4: n = Z - d * Z.dot(d)
    if n.length < 1e-4: n = X - d * X.dot(d)
    n = n.normalized(); r = d.cross(n).normalized()
    wp = wt if isinstance(wt, dict) else wt(base)
    b = acc.add_v(base, wp)
    L = acc.add_v(base + d * length * widest - r * width / 2 - n * width * 0.04, wp)
    R = acc.add_v(base + d * length * widest + r * width / 2 - n * width * 0.04, wp)
    t = acc.add_v(base + d * length - n * droop * length, wp)
    c = acc.add_v(base + d * length * (widest + 0.08) + n * width * ridge, wp)
    uv = lambda k: K._uv_rect(slot, *LEAF_UV[k])
    acc.face([b, R, c], slot, [uv('b'), uv('R'), uv('c')]); acc.face([R, t, c], slot, [uv('R'), uv('t'), uv('c')])
    acc.face([t, L, c], slot, [uv('t'), uv('L'), uv('c')]); acc.face([L, b, c], slot, [uv('L'), uv('b'), uv('c')])
    if closed:
        f = K._uv_rect(slot, *LEAF_FLAT)
        acc.face([b, L, t], slot, [f, f, f]); acc.face([b, t, R], slot, [f, f, f])


LEAF_SLOTS = ['limeBright', 'lime', 'mid', 'dark', 'deep']
def pick_slot(lit, bias=0.0):
    """lit 0..1 (1 = brightest). Returns a leaf slot name."""
    x = min(1, max(0, lit + bias + rnd.uniform(-.22, .22)))
    return LEAF_SLOTS[min(4, int((1 - x) * 5))]


# ------------------------------------------------------------------ rig (defined first, weights refer to it)
LEGS = {  # name: (hip, knee, ankle, hoof-tip) world points
    'FL': [V((1.8, -6.6, 3.2)), V((1.95, -7.4, 1.9)), V((2.05, -7.6, 0.95)), V((2.05, -7.9, 0.0))],
    'BL': [V((1.5, -1.9, 3.0)), V((1.7, -1.0, 1.55)), V((1.85, -1.3, 0.8)), V((1.85, -1.35, 0.0))],
}
for k, s in (('FR', 'FL'), ('BR', 'BL')):
    LEGS[k] = [V((-p.x, p.y, p.z)) for p in LEGS[s]]
LEGBONES = {'FL': ('FrontUpper.L', 'FrontLower.L', 'FrontFoot.L'), 'FR': ('FrontUpper.R', 'FrontLower.R', 'FrontFoot.R'),
            'BL': ('HindUpper.L', 'HindLower.L', 'HindFoot.L'), 'BR': ('HindUpper.R', 'HindLower.R', 'HindFoot.R')}

BONES = {
    'Root': (V((0, 0, 0)), V((0, 0, 0.8)), None),
    'Torso': (V((0, -3.8, 4.2)), V((0, -3.8, 5.0)), 'Root'),
    'Pelvis': (V((0, -3.8, 4.2)), V((0, -1.0, 4.4)), 'Torso'),
    'Chest': (V((0, -3.8, 4.2)), V((0, -6.6, 4.5)), 'Torso'),
    'Neck1': (V((0, -6.6, 4.6)), V((0, -7.1, 5.8)), 'Chest'),
    'Neck2': (V((0, -7.1, 5.8)), V((0, -7.5, 6.6)), 'Neck1'),
    'Head': (V((0, -7.5, 6.6)), V((0, -7.8, 7.8)), 'Neck2'),
    'Tail1': (V((0, -0.9, 4.8)), V((0, 0.5, 5.1)), 'Pelvis'),
    'Tail2': (V((0, 0.5, 5.1)), V((0, 1.4, 4.95)), 'Tail1'),
    'Tail3': (V((0, 1.4, 4.95)), V((0, 2.4, 4.1)), 'Tail2'),
    'Tail4': (V((0, 2.4, 4.1)), V((0, 3.4, 2.7)), 'Tail3'),
}
for k, (up, lo, ft) in LEGBONES.items():
    h, kn, an, hf = LEGS[k]
    par = 'Chest' if k[0] == 'F' else 'Pelvis'
    BONES[up] = (h, kn, par); BONES[lo] = (kn, an, up); BONES[ft] = (an, hf, lo)


# ------------------------------------------------------------------ body
def torso():
    rings = [
        dict(c=(0, -7.7, 4.05), rx=1.35, ry=1.45, w=W('Chest')),
        dict(c=(0, -6.2, 4.1), rx=1.7, ry=1.45, w=W('Chest')),
        dict(c=(0, -4.6, 4.25), rx=1.7, ry=1.25, w=W('Chest', 'Torso', .5)),
        dict(c=(0, -3.0, 4.3), rx=1.6, ry=1.15, w=W('Torso', 'Pelvis', .5)),
        dict(c=(0, -1.6, 4.15), rx=1.35, ry=1.1, w=W('Pelvis')),
        dict(c=(0, -0.6, 4.1), rx=1.1, ry=1.0, w=W('Pelvis')),
    ]
    for r in rings: r['T'] = (0, 1, 0)
    K.loft(BODY, rings, 8, lambda n, c, i: 'creamB' if n.z < -0.45 else 'olive', cap0='olive', cap1='olive')


def hips():
    for sx in (1, -1):
        prof = [(-2.55, 2.25), (-1.3, 2.2), (-0.95, 2.7), (-0.95, 4.6), (-1.35, 5.0), (-2.4, 5.0), (-2.75, 4.65), (-2.75, 2.7)]
        x0, x1 = 0.75 * sx, 1.95 * sx
        pts = [V((x, y, z)) for x in (x0, x1) for y, z in prof]
        n = len(prof)
        faces = [list(range(n)), list(range(n, 2 * n))] + [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
        solid(BODY, pts, faces, 'olive', W('Pelvis'))
        # brown thigh joint under the slab
        frustum(BODY, V((1.4 * sx, -1.9, 3.3)), V((1.5 * sx, -1.4, 2.2)), 1.1, 0.95, 'brown', W('Pelvis'), h0=1.3, h1=1.0, up=Y)


def neck():
    rings = [
        dict(c=(0, -6.3, 4.8), rx=1.05, ry=1.0, w=W('Chest', 'Neck1', .3), T=(0, -.5, 1)),
        dict(c=(0, -7.0, 5.7), rx=0.95, ry=0.85, w=W('Neck1'), T=(0, -.5, 1)),
        dict(c=(0, -7.5, 6.5), rx=0.9, ry=0.8, w=W('Neck2'), T=(0, -.3, 1)),
        dict(c=(0, -7.7, 7.0), rx=0.9, ry=0.75, w=W('Head'), T=(0, -.3, 1)),
    ]
    K.loft(BODY, rings, 8, lambda n, c, i: 'cream' if n.y < -0.25 else 'olive', cap0='olive', cap1='olive')


HEAD = V((0, -7.8, 6.95)); PITCH = math.radians(14)
RX = Matrix.Rotation(PITCH, 3, 'X')
def hp(p): return HEAD + RX @ V(p)
def hn(n): return RX @ V(n)
WH = W('Head')

def head():
    M = RX
    def hb(c, size, slot, taper=1.0, slots=None):
        K.box(BODY, hp(c), size, slot, WH, M, taper, slots)
    hb((0, 0.0, 0.1), (1.95, 1.5, 1.55), 'olive')                                # skull
    K_f = lambda p0, p1, w0, w1, h0, h1, slot: frustum(BODY, hp(p0), hp(p1), w0, w1, slot, WH, h0=h0, h1=h1, up=hn((0, 0, 1)))
    K_f((0, -0.7, -0.05), (0, -1.45, -0.18), 1.45, 0.85, 1.0, 0.7, 'olive')       # tapering snout
    hb((0, -0.5, 0.62), (2.05, 0.55, 0.38), 'olive')                              # brow ridge
    hb((0, -1.0, -0.62), (1.5, 0.95, 0.55), 'creamB', slots={1: 'olive'})      # cream lower muzzle/jaw
    hb((0, -1.6, -0.22), (0.58, 0.3, 0.4), 'nose')                             # nose
    K.solid_spike(BODY, hp((0, -1.3, -0.95)), hn((0, -0.2, -1)), 0.6, 0.45, WH, 'cream')   # chin fang
    for s in (1, -1):
        hb((s * 0.82, -0.7, -0.62), (0.5, 0.6, 0.5), 'cream')                    # cheek/mouth-corner block
        hb((s * 0.5, 0.4, 0.95), (0.7, 0.7, 0.45), 'brownD')                     # antler mount
        K.eye_lens(GLOW, hp((s * 0.74, -0.8, 0.26)), hn((s * 0.55, -1, 0.15)), hn((s * 0.2, 0, 1)), hn((s * -1, -0.3, 0)), WH, scale=1.35, dome=0.12)


def gem():
    c = V((0, -8.25, 3.95))
    K.gem_plate(GLOW, c, V((0, -1, 0.1)), Z, 0.7, 1.0, 0.35, W('Chest'))
    frustum(BODY, V(0, -7.6, 3.3), V(0, -8.0, 2.6), 1.6, 0.5, 'creamB', W('Chest'), h0=0.7, h1=0.6, up=Y)


# ------------------------------------------------------------------ antlers
def antler():
    def chain(pts, widths, wt=WH, slot='cream'):
        for i in range(len(pts) - 1):
            frustum(BODY, pts[i], pts[i + 1], widths[i], widths[i + 1], slot, wt,
                    up=Z if abs((pts[i + 1] - pts[i]).normalized().z) < .9 else Y, caps=(i == 0, True))
    for s in (1, -1):
        m = lambda x, y, z: V((s * x, y, z))
        # lateral beam: out and up from the head
        chain([m(0.45, -7.7, 8.0), m(1.1, -7.8, 8.55), m(1.8, -7.9, 8.95), m(2.5, -8.0, 9.3)], [0.76, 0.68, 0.62, 0.48])
        chain([m(1.8, -7.9, 8.95), m(2.0, -8.1, 9.7), m(2.35, -8.2, 10.4)], [0.52, 0.4, 0.21])      # tine up-front
        chain([m(2.5, -8.0, 9.3), m(2.95, -8.0, 10.0), m(3.15, -8.0, 10.5)], [0.48, 0.34, 0.17])      # outer tip tine
        # rear sweeping beam
        chain([m(1.0, -7.6, 8.4), m(1.3, -6.7, 8.95), m(1.45, -5.7, 9.4), m(1.35, -4.6, 9.95)], [0.67, 0.59, 0.5, 0.34])
        chain([m(1.3, -6.7, 8.95), m(1.4, -6.8, 9.7), m(1.5, -6.7, 10.3)], [0.48, 0.37, 0.17])
        chain([m(1.45, -5.7, 9.4), m(1.55, -5.7, 10.1), m(1.65, -5.6, 10.7)], [0.44, 0.33, 0.15])
        chain([m(0.8, -7.9, 8.2), m(0.75, -8.5, 8.8), m(0.7, -8.95, 9.1)], [0.48, 0.34, 0.15])        # brow tine
        chain([m(0.5, -7.6, 8.1), m(0.4, -7.4, 9.0), m(0.35, -7.2, 9.7)], [0.48, 0.34, 0.13])         # inner crown tine
        frustum(BODY, m(2.5, -8.0, 9.3), m(3.2, -8.1, 9.45), 0.2, 0.16, 'brownD', WH, up=Y)
        pass


# ------------------------------------------------------------------ legs
def legs():
    for k, (hip, kn, an, hf) in LEGS.items():
        up, lo, ft = LEGBONES[k]; sx = 1 if k[1] == 'L' else -1; front = k[0] == 'F'
        wU, wL, wF = W(up), W(lo), W(ft)
        blend_knee = K.blend(wU, wL); blend_ank = K.blend(wL, wF)
        frustum(BODY, hip + V(0, 0, 0.1), kn, 1.5 if front else 1.4, 1.15, 'brown', wU, h0=1.9, h1=1.4, up=Y, caps=(False, False))
        frustum(BODY, kn + V(0, 0, 0.3), kn - V(0, 0, 0.3), 1.3, 1.3, 'brownD', blend_knee, h0=1.6, h1=1.6, up=Y)
        frustum(BODY, kn, an, 1.15, 1.0, 'brown', wL, h0=1.45, h1=1.25, up=Y, caps=(False, False))
        frustum(BODY, an + V(0, 0, 0.45), an - V(0, 0, 0.15), 1.2, 1.2, 'brownD', blend_ank, h0=1.5, h1=1.5, up=Y)
        for dx in (-0.4, 0.4):               # two cream hooves, splayed toes
            base = hf + V(dx * 1.0, -0.1, 0.0)
            solid(BODY, [base + V(-0.34, -0.9, 0), base + V(0.34, -0.9, 0), base + V(0.34, 0.6, 0), base + V(-0.34, 0.6, 0),
                         base + V(-0.26, -0.3, 1.0), base + V(0.26, -0.3, 1.0), base + V(0.26, 0.5, 1.0), base + V(-0.26, 0.5, 1.0)],
                  BOXF, 'cream', wF)
        if front:
            frustum(BODY, V(sx * 1.85, -6.65, 4.0), V(sx * 1.85, -6.7, 2.8), 1.45, 1.3, 'brown', W('Chest'), h0=1.9, h1=1.7, up=Y)


# ------------------------------------------------------------------ foliage
def mane(): pass


def body_leaves(): pass


def tail():
    wt = lambda p: W('Tail2') if p.y < 1.0 else interp_w([(1.0, 'Tail2'), (2.4, 'Tail3'), (3.4, 'Tail4')], p.y)
    frustum(BODY, V(0, -0.9, 4.7), V(0, 0.5, 5.1), 0.95, 0.75, 'olive', W('Tail1'), h0=0.95, h1=0.75, caps=(False, False))
    frustum(BODY, V(0, 0.5, 5.1), V(0, 1.4, 4.95), 0.75, 0.6, 'brown', W('Tail2'), caps=(False, True))


# ------------------------------------------------------------------ build all
def build_geometry():
    torso(); hips(); neck(); head(); gem(); antler(); legs(); tail()
    import ref_leaves; ref_leaves.place(globals())
    print('tris total', BODY.tris())


def build_scene(out_blend):
    import bpy
    K.new_scene()
    tex = os.path.join(HERE, 'textures')
    matb = K.make_material('QilinBody', os.path.join(tex, 'Color.png'), os.path.join(tex, 'Normal.png'),
                           emissive_png=os.path.join(tex, 'Emissive.png'), emission=0.7)
    body = K.build_object(BODY, matb)
    arm = K.build_armature('VerdantQilin', BONES, [body])
    import anim_clips
    anim_clips.make(arm, LEGBONES)
    os.makedirs(os.path.dirname(out_blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    tris = sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in (body,))
    print('final tris', tris)


if __name__ == '__main__':
    sys.path.insert(0, HERE)
    build_geometry()
    build_scene(os.path.join(HERE, 'out', 'VerdantQilin.blend'))
