"""ASSET 2 - Ability pedestals + physically modelled ability glyphs.

Primary reference: dedicated pedestal sheet (3 rows x 5: crystal, lightning,
shield, flame, wind spiral; row 1 = 3/4, row 2 = edge-on side, row 3 = alt 3/4).
Extra glyphs (emerald leaf crest, gold sunburst, purple eye-orb, white wings)
come from the right-hand ability row of the lobby screenshots.

One shared marble pedestal mesh (lathe) is instanced for every ability; the
neon rings and stem are per-ability colour variants.  Glyphs face -Y.
Run:  python build_02_pedestals.py [--no-render]
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
import lobbylib as L

SPACING = 6.0
TOP_Z = 2.2          # top face of the pedestal
GLYPH_BASE = TOP_Z + 0.32
GLYPH_SCALE = 1.2

# (name, neon colour)
ABILITIES = [
    ("Crystal", (0.10, 0.72, 1.00)),
    ("Lightning", (0.33, 0.10, 1.00)),
    ("Shield", (1.00, 0.62, 0.10)),
    ("Flame", (1.00, 0.20, 0.30)),
    ("Wind", (0.25, 0.65, 1.00)),
    ("Emerald", (0.20, 1.00, 0.35)),
    ("Sun", (1.00, 0.72, 0.18)),
    ("Orb", (0.85, 0.25, 1.00)),
    ("Wings", (0.70, 0.85, 1.00)),
    # ---- 10 additional abilities (same construction / scale / stem) ----
    ("Ice", (0.55, 0.90, 1.00)),
    ("Water", (0.05, 0.40, 1.00)),
    ("Earth", (0.85, 0.45, 0.12)),
    ("Poison", (0.55, 1.00, 0.10)),
    ("Moon", (0.70, 0.60, 1.00)),
    ("Star", (1.00, 0.85, 0.20)),
    ("Heart", (1.00, 0.30, 0.55)),
    ("Shadow", (0.45, 0.10, 0.75)),
    ("Speed", (0.20, 1.00, 0.85)),
    ("Sword", (0.80, 0.85, 1.00)),
    ("Gravity", (0.50, 0.20, 0.95)),
    ("Arrow", (0.95, 0.75, 0.35)),
    ("Vine", (0.30, 0.85, 0.20)),
    ("Sound", (0.95, 0.40, 0.85)),
    ("Time", (0.95, 0.80, 0.45)),
]

# pedestal lathe profile (r, z): plinth with neon groove, drum, overhanging top rim,
# inset neon groove in the top face.
PED_PROFILE = [
    (2.10, 0.00), (2.10, 0.32), (2.00, 0.32), (2.00, 0.24), (1.84, 0.24), (1.84, 0.32),
    (1.75, 0.32), (1.75, 1.90), (1.90, 1.93), (1.90, TOP_Z), (1.66, TOP_Z), (1.66, TOP_Z - 0.08),
    (1.44, TOP_Z - 0.08), (1.44, TOP_Z),
]


# ----------------------------------------------------------------------------- helpers
def lathe_mesh(name, prof, segs=48):
    bm = bmesh.new()
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        rings.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in prof])
    for i in range(segs):
        j = (i + 1) % segs
        for k in range(len(prof) - 1):
            bm.faces.new((rings[i][k], rings[j][k], rings[j][k + 1], rings[i][k + 1]))
    bm.faces.new([rings[i][0] for i in range(segs)][::-1])
    bm.faces.new([rings[i][-1] for i in range(segs)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def poly(name, pts, depth, mat, c, bevel=0.06, segs=2):
    return L.extrude_polygon(name, pts, depth, mat, c, plane="XZ", bevel=bevel, segs=segs)


def offset_poly(pts, d):
    """Miter offset of a closed polygon (positive d = outward for CCW)."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    sgn = 1 if area > 0 else -1
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e1 = (p1 - p0).normalized(); e2 = (p2 - p1).normalized()
        n1 = Vector((e1.y, -e1.x)) * sgn; n2 = Vector((e2.y, -e2.x)) * sgn
        m = (n1 + n2)
        if m.length < 1e-6:
            m = n1
        m.normalize()
        k = d / max(0.75, m.dot(n1))
        q = p1 + m * k
        out.append((q.x, q.y))
    return out


def scale_pts(pts, s, dx=0.0, dz=0.0):
    return [(x * s + dx, z * s + dz) for x, z in pts]


def crystal(name, r, h, mat, c, sides=6, squash=0.55, bot=0.18, shoulder=0.7):
    """Faceted crystal: pointed bottom, prism body, pointed top.  Flat shaded."""
    bm = bmesh.new()
    b = bm.verts.new((0, 0, 0))
    r1 = [bm.verts.new((r * math.cos(2 * math.pi * i / sides + math.pi / 2),
                        squash * r * math.sin(2 * math.pi * i / sides + math.pi / 2), bot * h)) for i in range(sides)]
    r2 = [bm.verts.new((0.92 * r * math.cos(2 * math.pi * i / sides + math.pi / 2),
                        0.92 * squash * r * math.sin(2 * math.pi * i / sides + math.pi / 2), shoulder * h))
          for i in range(sides)]
    t = bm.verts.new((0, 0, h))
    for i in range(sides):
        j = (i + 1) % sides
        bm.faces.new((b, r1[j], r1[i]))
        bm.faces.new((r1[i], r1[j], r2[j], r2[i]))
        bm.faces.new((r2[i], r2[j], t))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return L.from_bmesh(name, bm, mat, c)


def star_pts(rv, rh, rs, ri, n=4):
    """Compass star: long vertical (rv) / horizontal (rh) points, short diagonals rs, inner ri."""
    pts = []
    for k in range(4 * n):
        a = math.pi / 2 + k * 2 * math.pi / (4 * n)
        if k % 4 == 0:
            r = rv if (k // 4) % 2 == 0 else rh
        elif k % 4 == 2:
            r = rs
        else:
            r = ri
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def vring(name, r_out, r_in, depth, mat, c, verts=48):
    """Annulus standing vertically, facing -Y."""
    ob = L.ring(name, r_out, r_in, depth, (0, 0, 0), mat, verts, c)
    ob.rotation_euler = (math.pi / 2, 0, 0)
    L.add_bevel(ob, 0.04, 2, angle=30)
    return ob


def sphere(name, r, mat, c):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=14, radius=r)
    ob = L.from_bmesh(name, bm, mat, c)
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def place(objs, x, z, rot_y=0.0):
    for o in objs:
        o.location = (o.location.x + x, o.location.y, o.location.z + z)
        if rot_y:
            o.rotation_euler.y += rot_y


# ----------------------------------------------------------------------------- glyphs
# Each returns a list of objects positioned with their bottom at z=0, centred on x=0.

def g_crystal(c, col):
    m = L.emissive("MAT_Glyph_Crystal", (0.1, 0.65, 1.0), 1.1, base=(0.25, 0.78, 1.0))
    o = []
    spec = [(0.0, 0.0, 0.46, 2.4), (-0.42, -0.42, 0.30, 1.6), (0.42, 0.42, 0.30, 1.6),
            (-0.78, -0.9, 0.22, 1.1), (0.78, 0.9, 0.22, 1.1)]
    for i, (dx, tilt, r, h) in enumerate(spec):
        cr = crystal(f"PED_CrystalShard_{i}", r, h, m, c)
        cr.location = (dx * 0.75, 0.0, 0.12 if i else 0.0)
        cr.rotation_euler = (0, tilt, 0)
        o.append(cr)
    return o


BOLT = [(-0.18, 1.25), (0.78, 1.25), (0.22, 0.32), (0.72, 0.32), (-0.48, -1.25), (-0.04, -0.12), (-0.52, -0.12)]


def g_lightning(c, col):
    body = L.emissive("MAT_Glyph_LightningBody", (0.22, 0.05, 1.0), 0.55, base=(0.30, 0.10, 0.86))
    rim = L.emissive("MAT_Glyph_LightningRim", (0.55, 0.38, 1.0), 1.6, base=(0.70, 0.58, 1.0))
    inner = poly("PED_BoltBody", BOLT, 0.42, body, c, 0.07)
    outer = poly("PED_BoltNeonRim", offset_poly(BOLT, 0.09), 0.26, rim, c, 0.03)
    for ob in (inner, outer):
        ob.location.z = 1.25
    return [inner, outer]


SHIELD = [(-1.0, 1.12), (-0.5, 1.0), (0.0, 1.12), (0.5, 1.0), (1.0, 1.12), (0.98, 0.3), (0.78, -0.4),
          (0.42, -0.86), (0.0, -1.18)][::-1]


def _shield_pts():
    right = [(-1.0, 1.12), (-0.5, 1.0), (0.0, 1.12), (0.5, 1.0), (1.0, 1.12), (0.98, 0.3), (0.78, -0.4),
             (0.42, -0.86), (0.0, -1.18), (-0.42, -0.86), (-0.78, -0.4), (-0.98, 0.3)]
    return right


def g_shield(c, col):
    gold = L.flat("MAT_Glyph_ShieldGold", (1.0, 0.6, 0.1), rough=0.3, metal=0.7)
    face = L.emissive("MAT_Glyph_ShieldFace", (1.0, 0.62, 0.08), 0.5, base=(1.0, 0.72, 0.15))
    starm = L.emissive("MAT_Glyph_ShieldStar", (1.0, 0.92, 0.6), 2.2)
    s = _shield_pts()
    rim = poly("PED_ShieldRim", s, 0.42, gold, c, 0.08)
    inner = poly("PED_ShieldFace", offset_poly(s, -0.2), 0.56, face, c, 0.06)
    st = poly("PED_ShieldStar", star_pts(0.62, 0.42, 0.2, 0.1), 0.66, starm, c, 0.02)
    st.location.z = 0.12
    objs = [rim, inner, st]
    for ob in objs:
        ob.location.z += 1.18
    return objs


FLAME = [(0, 0), (0.45, 0.08), (0.75, 0.35), (0.86, 0.75), (0.8, 1.2), (0.68, 1.55), (0.74, 1.98),
         (0.46, 1.62), (0.34, 1.78), (0.24, 2.08), (0.04, 2.48), (-0.1, 2.02), (-0.24, 1.76), (-0.4, 1.86),
         (-0.62, 1.98), (-0.66, 1.5), (-0.82, 1.15), (-0.86, 0.75), (-0.76, 0.35), (-0.45, 0.08)]


def g_flame(c, col):
    red = L.emissive("MAT_Glyph_FlameRed", (1.0, 0.08, 0.02), 1.0, base=(0.9, 0.1, 0.03))
    org = L.emissive("MAT_Glyph_FlameOrange", (1.0, 0.38, 0.02), 1.4, base=(1.0, 0.42, 0.05))
    yel = L.emissive("MAT_Glyph_FlameYellow", (1.0, 0.8, 0.2), 1.8, base=(1.0, 0.85, 0.3))
    a = poly("PED_FlameOuter", FLAME, 0.5, red, c, 0.08)
    b = poly("PED_FlameMid", scale_pts(FLAME, 0.7, 0.02, 0.06), 0.66, org, c, 0.07)
    d = poly("PED_FlameCore", scale_pts(FLAME, 0.42, 0.02, 0.08), 0.8, yel, c, 0.06)
    return [a, b, d]


def _blade(phase, n=22):
    outer, inner = [], []
    for i in range(n + 1):
        t = i / n
        ang = phase + t * math.radians(205)
        ro = 0.3 + 0.95 * t
        w = 0.36 * math.sin(math.pi * min(1.0, t * 1.05)) ** 0.75 + 0.02
        outer.append((ro * math.cos(ang), ro * math.sin(ang)))
        inner.append(((ro - w) * math.cos(ang - 0.08), (ro - w) * math.sin(ang - 0.08)))
    return outer + inner[::-1][1:-1]


def g_wind(c, col):
    m = L.emissive("MAT_Glyph_Wind", (0.25, 0.6, 1.0), 0.5, base=(0.42, 0.70, 1.0))
    objs = []
    for k in range(4):
        b = poly(f"PED_WindBlade_{k}", _blade(k * math.pi / 2), 0.32, m, c, 0.05)
        objs.append(b)
    core = vring("PED_WindCore", 0.3, 0.12, 0.36, m, c, 24)
    objs.append(core)
    for ob in objs:
        ob.location.z += 1.25
    return objs


def _leaf(h, w, n=14):
    right, left = [], []
    for i in range(n + 1):
        s = i / n
        z = h * s
        x = w * math.sin(math.pi * s) ** 0.8 * (1 - 0.25 * s)
        right.append((x, z))
    pts = right + [(-x, z) for x, z in right[::-1][1:-1]]
    return pts


def g_emerald(c, col):
    m = L.emissive("MAT_Glyph_Emerald", (0.05, 0.85, 0.25), 1.0, base=(0.15, 0.85, 0.3))
    vein = L.emissive("MAT_Glyph_EmeraldVein", (0.6, 1.0, 0.5), 2.2)
    objs = []
    for i, (dx, tilt, h, w) in enumerate([(0, 0, 2.3, 0.62), (-0.25, -0.62, 1.5, 0.42), (0.25, 0.62, 1.5, 0.42)]):
        lf = poly(f"PED_EmeraldLeaf_{i}", _leaf(h, w), 0.34, m, c, 0.06)
        vn = L.box(f"PED_EmeraldVein_{i}", (0.08, 0.44, h * 0.75), (0, 0, h * 0.42), vein, 0.02, c=c)
        for ob in (lf, vn):
            ob.rotation_euler = (0, tilt, 0)
            ob.location.x += dx
        objs += [lf, vn]
    return objs


def g_sun(c, col):
    gold = L.flat("MAT_Glyph_SunGold", (1.0, 0.62, 0.12), rough=0.3, metal=0.7)
    glow = L.emissive("MAT_Glyph_SunCore", (1.0, 0.8, 0.3), 2.0)
    st = poly("PED_SunStar", star_pts(1.2, 1.2, 0.85, 0.36), 0.36, gold, c, 0.05)
    rg = vring("PED_SunRing", 0.82, 0.66, 0.28, gold, c)
    core = sphere("PED_SunCore", 0.3, glow, c)
    core.scale = (1, 0.55, 1)
    objs = [st, rg, core]
    for ob in objs:
        ob.location.z += 1.22
    return objs


def g_orb(c, col):
    ringm = L.emissive("MAT_Glyph_OrbRing", (0.7, 0.12, 1.0), 1.2, base=(0.65, 0.22, 0.95))
    eye = L.emissive("MAT_Glyph_OrbEye", (1.0, 0.4, 0.9), 1.6, base=(1.0, 0.5, 0.92))
    rg = vring("PED_OrbRing", 1.0, 0.72, 0.34, ringm, c)
    ball = sphere("PED_OrbEye", 0.4, eye, c)
    pupil = sphere("PED_OrbPupil", 0.16, L.flat("MAT_Glyph_OrbPupil", (0.25, 0.05, 0.4), 0.3), c)
    pupil.location.y = -0.32
    pupil.scale = (1, 0.5, 1)
    objs = [rg, ball, pupil]
    for ob in objs:
        ob.location.z += 1.05
    return objs


WING = [(0.12, 0.35), (0.5, 0.78), (1.0, 1.08), (1.48, 1.2), (1.28, 0.78), (1.12, 0.84), (1.0, 0.5),
        (0.86, 0.56), (0.74, 0.24), (0.6, 0.3), (0.5, -0.02), (0.36, 0.04), (0.26, -0.26), (0.12, -0.16)]


def g_wings(c, col):
    m = L.emissive("MAT_Glyph_Wings", (0.7, 0.82, 1.0), 0.45, base=(0.9, 0.93, 1.0))
    gem = L.emissive("MAT_Glyph_WingsGem", (0.1, 0.7, 1.0), 2.0)
    r = poly("PED_WingR", WING, 0.3, m, c, 0.05)
    lpts = [(-x, z) for x, z in WING][::-1]
    lw = poly("PED_WingL", lpts, 0.3, m, c, 0.05)
    g = poly("PED_WingsGem", [(0, 0.38), (0.2, 0), (0, -0.38), (-0.2, 0)], 0.4, gem, c, 0.03)
    g.location.z = 0.3
    objs = [r, lw, g]
    for ob in objs:
        ob.location.z += 0.55
    return objs


# ----------------------------------------------------------------------------- additional glyphs
def _rock(name, r, mat, c, seed, sq=0.62):
    import random as _r
    rnd = _r.Random(seed)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=r)
    for v in bm.verts:
        v.co *= rnd.uniform(0.84, 1.1)
    ob = L.from_bmesh(name, bm, mat, c)
    ob.scale = (1.0, sq, rnd.uniform(0.85, 1.0))
    for p in ob.data.polygons:
        p.use_smooth = False
    return ob


def g_ice(c, col):
    body = L.emissive("MAT_Glyph_IceBody", (0.25, 0.72, 1.0), 0.5, base=(0.4, 0.78, 1.0))
    core = L.emissive("MAT_Glyph_IceCore", (0.7, 0.95, 1.0), 0.8, base=(0.85, 0.97, 1.0))
    arm = [(-0.13, 0.0), (0.13, 0.0), (0.13, 1.08), (0.0, 1.26), (-0.13, 1.08)]
    barb = [(-0.08, 0.0), (0.08, 0.0), (0.08, 0.42), (0.0, 0.5), (-0.08, 0.42)]
    objs = []
    for k in range(6):
        th = k * math.pi / 3
        a = poly(f"PED_IceArm_{k}", arm, 0.3, body, c, 0.03)
        a.rotation_euler.y = th
        objs.append(a)
        for sgn in (-1, 1):
            b = poly(f"PED_IceBarb_{k}_{sgn}", barb, 0.26, body, c, 0.02)
            b.location = (0.66 * math.sin(th), 0, 0.66 * math.cos(th))
            b.rotation_euler.y = th + sgn * 0.85
            objs.append(b)
    hexp = [(0.38 * math.cos(math.pi / 6 + i * math.pi / 3), 0.38 * math.sin(math.pi / 6 + i * math.pi / 3))
            for i in range(6)]
    objs.append(poly("PED_IceGem", hexp, 0.46, core, c, 0.04))
    objs.append(poly("PED_IceGemInner", scale_pts(hexp, 0.55), 0.56, core, c, 0.02))
    for ob in objs:
        ob.location.z += 1.28
    return objs


def _teardrop(r=0.9, tip=2.45):
    cz = r
    d = tip - cz
    al = math.acos(r / d)
    a0, a1 = math.pi / 2 + al, math.pi / 2 - al + 2 * math.pi
    n = 26
    pts = [(r * math.cos(a0 + (a1 - a0) * i / n), cz + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    return pts + [(0.0, tip)]


def g_water(c, col):
    body = L.emissive("MAT_Glyph_WaterBody", (0.05, 0.35, 1.0), 0.6, base=(0.08, 0.38, 0.95))
    hi = L.emissive("MAT_Glyph_WaterHi", (0.4, 0.75, 1.0), 0.8, base=(0.55, 0.82, 1.0))
    drop = _teardrop()
    a = poly("PED_WaterDrop", drop, 0.5, body, c, 0.05)
    b = poly("PED_WaterInner", scale_pts(drop, 0.62, 0.0, 0.3), 0.62, hi, c, 0.03)
    shine = poly("PED_WaterShine", [(-0.5, 0.75), (-0.36, 0.72), (-0.22, 1.25), (-0.34, 1.32)], 0.7, hi, c, 0.01)
    objs = [a, b, shine]
    for i, (ro, ri) in enumerate(((0.95, 0.8), (1.3, 1.18))):
        rg = L.ring(f"PED_WaterSplash_{i}", ro, ri, 0.06, (0, 0, 0.04 + 0.05 * i), hi, 40, c)
        rg.scale = (1, 0.55, 1)
        objs.append(rg)
    for ob in objs[:3]:
        ob.location.z += 0.12
    return objs


def g_earth(c, col):
    rock = L.flat("MAT_Glyph_EarthRock", (0.42, 0.24, 0.10), rough=0.85)
    rock2 = L.flat("MAT_Glyph_EarthRockLight", (0.58, 0.36, 0.16), rough=0.85)
    seam = L.emissive("MAT_Glyph_EarthSeam", (1.0, 0.45, 0.05), 0.8, base=(1.0, 0.55, 0.12))
    big = _rock("PED_EarthRockBig", 0.85, rock, c, 1)
    big.location = (0, 0, 1.0)
    lft = _rock("PED_EarthRockL", 0.55, rock2, c, 2)
    lft.location = (-0.8, 0, 0.5)
    rgt = _rock("PED_EarthRockR", 0.6, rock2, c, 3)
    rgt.location = (0.82, 0, 0.55)
    chip = _rock("PED_EarthChip", 0.28, rock, c, 4)
    chip.location = (0.25, 0, 2.15)
    crack = [(-0.05, 1.7), (0.12, 1.42), (-0.1, 1.18), (0.14, 0.92), (-0.04, 0.6), (0.06, 0.6), (0.24, 0.92),
             (0.0, 1.18), (0.22, 1.42), (0.05, 1.7)]
    cr = poly("PED_EarthCrack", crack, 0.1, seam, c, 0.0)
    cr.location.y = -0.85 * 0.62 + 0.0
    return [big, lft, rgt, chip, cr]


def _flask():
    r, cz, nw = 0.78, 0.78, 0.19
    th = math.asin(nw / r)
    a0, a1 = math.pi / 2 + th, math.pi / 2 - th + 2 * math.pi
    n = 26
    body = [(r * math.cos(a0 + (a1 - a0) * i / n), cz + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    return body + [(nw, 1.75), (0.3, 1.82), (0.3, 1.98), (-0.3, 1.98), (-0.3, 1.82), (-nw, 1.75)]


def g_poison(c, col):
    glass = L.emissive("MAT_Glyph_PoisonGlass", (0.4, 0.9, 0.1), 0.35, base=(0.62, 0.95, 0.4))
    liquid = L.emissive("MAT_Glyph_PoisonLiquid", (0.45, 1.0, 0.05), 0.8, base=(0.5, 0.95, 0.1))
    cork = L.flat("MAT_Glyph_PoisonCork", (0.55, 0.36, 0.18), rough=0.8)
    a = poly("PED_PoisonFlask", _flask(), 0.42, glass, c, 0.04)
    r, n = 0.62, 24
    liq = [(r * math.cos(math.pi * (1 + i / n)), 0.78 + r * math.sin(math.pi * (1 + i / n))) for i in range(n + 1)]
    liq = liq[::-1] + [(0.6, 0.98), (0.2, 1.08), (-0.2, 0.94), (-0.6, 0.98)]
    b = poly("PED_PoisonLiquid", liq[::-1], 0.56, liquid, c, 0.03)
    k = L.box("PED_PoisonCork", (0.4, 0.34, 0.32), (0, 0, 2.12), cork, 0.03, c=c)
    objs = [a, b, k]
    for i, (x, z, rr) in enumerate(((0.12, 2.5, 0.13), (-0.16, 2.78, 0.1), (0.2, 3.0, 0.075),
                                    (-0.25, 0.65, 0.09), (0.22, 0.48, 0.07))):
        bb = sphere(f"PED_PoisonBubble_{i}", rr, liquid, c)
        bb.location = (x, -0.05 if z < 1.5 else 0.0, z)
        objs.append(bb)
    return objs


def _crescent():
    R, r, dx, dz = 1.18, 0.98, 0.52, 0.22
    n = 72
    outer = [(R * math.cos(2 * math.pi * i / n), R * math.sin(2 * math.pi * i / n)) for i in range(n)]
    ins = [(x - dx) ** 2 + (z - dz) ** 2 < r * r for x, z in outer]
    start = next(i for i in range(n) if ins[i] and not ins[(i + 1) % n])
    keep = []
    i = (start + 1) % n
    while not ins[i]:
        keep.append(outer[i])
        i = (i + 1) % n
    p0, p1 = Vector(keep[-1]), Vector(keep[0])
    a0 = math.atan2(p0.y - dz, p0.x - dx)
    a1 = math.atan2(p1.y - dz, p1.x - dx)
    # trace the inner (bite) arc the way that stays INSIDE the outer disc
    best = None
    for cand in (a1, a1 - 2 * math.pi, a1 + 2 * math.pi):
        am = (a0 + cand) / 2
        if math.hypot(dx + r * math.cos(am), dz + r * math.sin(am)) < R:
            if best is None or abs(cand - a0) < abs(best - a0):
                best = cand
    a1 = best
    inner = [(dx + r * math.cos(a0 + (a1 - a0) * t / 30), dz + r * math.sin(a0 + (a1 - a0) * t / 30))
             for t in range(1, 30)]
    return keep + inner


def _five_star(ro, ri, rot=math.pi / 2):
    return [((ro if k % 2 == 0 else ri) * math.cos(rot + k * math.pi / 5),
             (ro if k % 2 == 0 else ri) * math.sin(rot + k * math.pi / 5)) for k in range(10)]


def g_moon(c, col):
    body = L.emissive("MAT_Glyph_MoonBody", (0.45, 0.35, 1.0), 0.4, base=(0.5, 0.42, 0.95))
    hi = L.emissive("MAT_Glyph_MoonHi", (0.75, 0.68, 1.0), 0.6, base=(0.8, 0.75, 1.0))
    cres = _crescent()
    a = poly("PED_MoonBody", cres, 0.4, body, c, 0.04)
    b = poly("PED_MoonInner", scale_pts(cres, 0.7, -0.1, 0.0), 0.5, hi, c, 0.02)   # scaled (offset breaks at horns)
    st = poly("PED_MoonStar", _five_star(0.36, 0.15), 0.3, hi, c, 0.02)
    st.location = (0.62, 0, 0.78)
    objs = [a, b, st]
    for ob in objs:
        ob.location.z += 1.2
    return objs


def g_star(c, col):
    gold = L.flat("MAT_Glyph_StarGold", (1.0, 0.62, 0.1), rough=0.3, metal=0.7)
    face = L.emissive("MAT_Glyph_StarFace", (1.0, 0.82, 0.15), 0.7, base=(1.0, 0.86, 0.25))
    pts = _five_star(1.25, 0.55)
    a = poly("PED_StarRim", pts, 0.42, gold, c, 0.05)
    b = poly("PED_StarFace", offset_poly(pts, -0.18), 0.56, face, c, 0.03)
    objs = [a, b]
    for ob in objs:
        ob.location.z += 1.1
    return objs


def _heart(s=0.072, n=48):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        z = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * s, z * s))
    return pts[::-1]


def g_heart(c, col):
    body = L.emissive("MAT_Glyph_HeartBody", (1.0, 0.18, 0.4), 0.6, base=(0.95, 0.25, 0.45))
    hi = L.emissive("MAT_Glyph_HeartHi", (1.0, 0.38, 0.6), 0.7, base=(1.0, 0.48, 0.66))
    white = L.emissive("MAT_Glyph_HeartCross", (1.0, 1.0, 1.0), 0.6, base=(1.0, 1.0, 1.0))
    hp = _heart()
    a = poly("PED_HeartBody", hp, 0.44, body, c, 0.05)
    b = poly("PED_HeartInner", scale_pts(hp, 0.72, 0.0, 0.08), 0.56, hi, c, 0.03)  # scaled (offset breaks at cusp)
    w, l = 0.13, 0.36
    cross = [(-w, -l), (w, -l), (w, -w), (l, -w), (l, w), (w, w), (w, l), (-w, l), (-w, w), (-l, w), (-l, -w), (-w, -w)]
    x = poly("PED_HeartCross", cross, 0.66, white, c, 0.01)
    x.location.z = 0.1
    objs = [a, b, x]
    for ob in objs:
        ob.location.z += 1.22
    return objs


def g_shadow(c, col):
    dark = L.flat("MAT_Glyph_ShadowBody", (0.10, 0.03, 0.20), rough=0.5)
    rim = L.emissive("MAT_Glyph_ShadowRim", (0.55, 0.15, 1.0), 0.8, base=(0.6, 0.25, 1.0))
    core = L.emissive("MAT_Glyph_ShadowCore", (0.62, 0.25, 1.0), 0.7, base=(0.5, 0.2, 0.9))
    wisp = [(x - 0.42 * (z / 2.5) ** 2 + 0.12, z) for x, z in FLAME]
    a = poly("PED_ShadowBody", wisp, 0.46, dark, c, 0.04)
    b = poly("PED_ShadowRim", offset_poly(wisp, 0.1), 0.28, rim, c, 0.02)
    d = poly("PED_ShadowCore", scale_pts(wisp, 0.45, 0.05, 0.1), 0.6, core, c, 0.02)
    return [a, b, d]


CHEVRON = [(-1.0, 0.0), (0.0, 0.72), (1.0, 0.0), (1.0, -0.42), (0.0, 0.3), (-1.0, -0.42)]


def g_speed(c, col):
    body = L.emissive("MAT_Glyph_SpeedBody", (0.1, 0.9, 0.75), 0.6, base=(0.15, 0.85, 0.72))
    rim = L.emissive("MAT_Glyph_SpeedRim", (0.55, 1.0, 0.92), 0.8, base=(0.7, 1.0, 0.95))
    objs = []
    for i, (z, sc) in enumerate(((0.42, 0.82), (1.14, 0.92), (1.9, 1.0))):
        pts = scale_pts(CHEVRON, sc)
        objs.append(poly(f"PED_SpeedChevron_{i}", pts, 0.4, body, c, 0.03))
        objs.append(poly(f"PED_SpeedRim_{i}", offset_poly(pts, 0.08), 0.24, rim, c, 0.02))
        objs[-2].location.z = z
        objs[-1].location.z = z
    return objs


def g_sword(c, col):
    steel = L.flat("MAT_Glyph_SwordSteel", (0.78, 0.82, 0.92), rough=0.22, metal=0.85)
    fuller = L.emissive("MAT_Glyph_SwordFuller", (0.6, 0.8, 1.0), 0.6, base=(0.75, 0.86, 1.0))
    gold = L.flat("MAT_Glyph_SwordGold", (1.0, 0.62, 0.12), rough=0.3, metal=0.7)
    grip = L.flat("MAT_Glyph_SwordGrip", (0.08, 0.12, 0.38), rough=0.6)
    gem = L.emissive("MAT_Glyph_SwordGem", (0.15, 0.75, 1.0), 0.8, base=(0.3, 0.8, 1.0))
    blade = [(-0.28, 0.78), (0.28, 0.78), (0.28, 2.05), (0.0, 2.55), (-0.28, 2.05)]
    objs = [poly("PED_SwordBlade", blade, 0.24, steel, c, 0.03),
            poly("PED_SwordFuller", [(-0.05, 0.9), (0.05, 0.9), (0.05, 2.0), (-0.05, 2.0)], 0.22, fuller, c, 0.0),
            L.box("PED_SwordGuard", (1.45, 0.36, 0.24), (0, 0, 0.7), gold, 0.03, c=c),
            L.box("PED_SwordGrip", (0.16, 0.2, 0.5), (0, 0, 0.36), grip, 0.02, c=c)]
    pm = sphere("PED_SwordPommel", 0.13, gold, c)
    pm.location.z = 0.08
    g = poly("PED_SwordGem", [(0, 0.17), (0.12, 0), (0, -0.17), (-0.12, 0)], 0.42, gem, c, 0.02)
    g.location.z = 0.7
    return objs + [pm, g]



def _arc_band(cx, cz, r, w, a0, a1, n=24):
    out = [(cx + (r + w / 2) * math.cos(a0 + (a1 - a0) * i / n), cz + (r + w / 2) * math.sin(a0 + (a1 - a0) * i / n))
           for i in range(n + 1)]
    inn = [(cx + (r - w / 2) * math.cos(a0 + (a1 - a0) * i / n), cz + (r - w / 2) * math.sin(a0 + (a1 - a0) * i / n))
           for i in range(n + 1)]
    return out + inn[::-1]


def g_gravity(c, col):
    dark = L.flat("MAT_Glyph_GravityCore", (0.12, 0.05, 0.25), rough=0.35, metal=0.3)
    glow = L.emissive("MAT_Glyph_GravityRing", (0.5, 0.2, 0.95), 0.7, base=(0.55, 0.3, 0.95))
    hi = L.emissive("MAT_Glyph_GravityHalo", (0.7, 0.45, 1.0), 0.6, base=(0.7, 0.5, 1.0))
    core = sphere("PED_GravityCore", 0.6, dark, c)
    halo = vring("PED_GravityHalo", 0.7, 0.6, 0.12, hi, c, 40)
    objs = [core, halo]
    for i, (rx, ry) in enumerate(((1.15, 0.5), (1.15, -0.5))):
        rg = L.ring(f"PED_GravityOrbit_{i}", 1.18, 1.04, 0.1, (0, 0, 0), glow, 56, c)
        rg.rotation_euler = (rx, ry, 0)
        objs.append(rg)
    for ob in objs:
        ob.location.z += 1.25
    return objs


def g_arrow(c, col):
    wood = L.flat("MAT_Glyph_BowWood", (0.85, 0.5, 0.18), rough=0.5)
    goldm = L.flat("MAT_Glyph_BowGold", (1.0, 0.62, 0.12), rough=0.3, metal=0.7)
    string = L.emissive("MAT_Glyph_BowString", (1.0, 0.9, 0.7), 0.5, base=(1.0, 0.95, 0.85))
    steel = L.flat("MAT_Glyph_ArrowHead", (0.78, 0.82, 0.92), rough=0.25, metal=0.85)
    fl = L.emissive("MAT_Glyph_ArrowFletch", (0.95, 0.7, 0.3), 0.6, base=(1.0, 0.78, 0.4))
    dx = 0.65
    bow = poly("PED_BowLimb", _arc_band(0.4 + dx, 1.25, 1.3, 0.2, math.radians(110), math.radians(250)), 0.26,
               wood, c, 0.03)
    grip = L.box("PED_BowGrip", (0.26, 0.34, 0.5), (-0.9 + dx, 0, 1.25), goldm, 0.03, c=c)
    st = L.box("PED_BowString", (0.05, 0.06, 2.42), (-0.045 + dx, 0, 1.25), string, 0.0, c=c)
    shaft = L.box("PED_ArrowShaft", (1.15, 0.09, 0.09), (-0.6 + dx, 0, 1.25), wood, 0.0, c=c)
    head = poly("PED_ArrowHead", [(0, 0.2), (-0.38, 0), (0, -0.2)], 0.14, steel, c, 0.02)
    head.location = (-1.17 + dx, 0, 1.25)
    objs = [bow, grip, st, shaft, head]
    for sgn in (-1, 1):
        f = poly(f"PED_ArrowFletch_{sgn}", [(0, 0), (0.3, 0), (0.42, sgn * 0.24), (0.1, sgn * 0.2)][::sgn], 0.08,
                 fl, c, 0.0)
        f.location = (-0.1 + dx, 0, 1.25)
        objs.append(f)
    return objs


def _spiral_band(r0=0.22, r1=1.08, turns=1.55, w=0.2, n=60):
    out, inn = [], []
    total = turns * 2 * math.pi
    for i in range(n + 1):
        t = i / n
        a = math.pi / 2 + t * total
        r = r0 + (r1 - r0) * t
        ww = w * (0.55 + 0.45 * t)
        out.append(((r + ww / 2) * math.cos(a), (r + ww / 2) * math.sin(a)))
        inn.append(((r - ww / 2) * math.cos(a), (r - ww / 2) * math.sin(a)))
    return out + inn[::-1], total


def g_vine(c, col):
    vine = L.emissive("MAT_Glyph_Vine", (0.2, 0.7, 0.12), 0.4, base=(0.25, 0.65, 0.15))
    leafm = L.emissive("MAT_Glyph_VineLeaf", (0.35, 0.95, 0.2), 0.6, base=(0.4, 0.9, 0.25))
    thornm = L.flat("MAT_Glyph_VineThorn", (0.12, 0.35, 0.08), rough=0.6)
    band, total = _spiral_band()
    objs = [poly("PED_VineSpiral", band, 0.3, vine, c, 0.02)]
    for k in range(7):
        t = 0.25 + 0.75 * k / 6
        a = math.pi / 2 + t * total
        r = 0.22 + (1.08 - 0.22) * t + 0.1
        th = poly(f"PED_VineThorn_{k}", [(-0.07, 0), (0.07, 0), (0, 0.2)], 0.2, thornm, c, 0.0)
        th.location = (r * math.cos(a), 0, r * math.sin(a))
        th.rotation_euler.y = -(a - math.pi / 2)
        objs.append(th)
    for i, (x, z, rot) in enumerate(((0.75, 0.75, -0.9), (-0.85, 0.55, 0.8))):
        lf = poly(f"PED_VineLeaf_{i}", _leaf(0.8, 0.3), 0.22, leafm, c, 0.02)
        lf.location = (x, 0, z)
        lf.rotation_euler.y = rot
        objs.append(lf)
    for ob in objs:
        ob.location.z += 1.25
    return objs


def g_sound(c, col):
    wave = L.emissive("MAT_Glyph_SoundWave", (0.95, 0.35, 0.82), 0.7, base=(0.95, 0.45, 0.85))
    body = L.flat("MAT_Glyph_SoundBody", (0.55, 0.12, 0.45), rough=0.4, metal=0.2)
    spk = [(-1.2, 0.95), (-0.88, 0.95), (-0.45, 0.6), (-0.45, 1.9), (-0.88, 1.55), (-1.2, 1.55)]
    objs = [poly("PED_SoundSpeaker", spk, 0.4, body, c, 0.03),
            poly("PED_SoundSpeakerFace", offset_poly(spk, -0.1), 0.5, wave, c, 0.02)]
    for i, r in enumerate((0.42, 0.78, 1.14)):
        objs.append(poly(f"PED_SoundWave_{i}", _arc_band(-0.3, 1.25, r, 0.15, math.radians(-48), math.radians(48)),
                         0.3, wave, c, 0.02))
    for ob in objs:
        ob.location.x += 0.15
    return objs


def g_time(c, col):
    gold = L.flat("MAT_Glyph_TimeGold", (1.0, 0.62, 0.12), rough=0.3, metal=0.7)
    glass = L.glass_emissive("MAT_Glyph_TimeGlass", (0.95, 0.85, 0.55), 0.3, alpha=0.45)
    sand = L.emissive("MAT_Glyph_TimeSand", (1.0, 0.72, 0.25), 0.6, base=(1.0, 0.78, 0.35))

    def lathe_ob(name, prof, mat):
        me = lathe_mesh(name, prof, 32)
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        c.objects.link(ob)
        return ob
    bulbs = [(0.01, 0.22), (0.42, 0.24), (0.5, 0.55), (0.38, 0.95), (0.08, 1.25), (0.38, 1.55), (0.5, 1.95),
             (0.42, 2.26), (0.01, 2.28)]
    objs = [lathe_ob("PED_TimeGlass", bulbs, glass),
            lathe_ob("PED_TimeSandLow", [(0.01, 0.26), (0.4, 0.3), (0.44, 0.52), (0.01, 0.86)], sand),
            lathe_ob("PED_TimeSandHigh", [(0.01, 1.4), (0.24, 1.5), (0.36, 1.78), (0.3, 1.86), (0.01, 1.88)], sand),
            L.cyl("PED_TimeStream", 0.03, 0.5, (0, 0, 1.12), sand, 8, 0.0, c=c),
            L.box("PED_TimeTop", (1.35, 0.6, 0.2), (0, 0, 2.38), gold, 0.03, c=c),
            L.box("PED_TimeBottom", (1.35, 0.6, 0.2), (0, 0, 0.1), gold, 0.03, c=c)]
    for sx in (-1, 1):
        objs.append(L.cyl(f"PED_TimePost_{sx}", 0.07, 2.1, (sx * 0.58, 0, 1.24), gold, 12, 0.0, c=c))
    return objs


GLYPHS = dict(Crystal=g_crystal, Lightning=g_lightning, Shield=g_shield, Flame=g_flame, Wind=g_wind,
              Emerald=g_emerald, Sun=g_sun, Orb=g_orb, Wings=g_wings,
              Ice=g_ice, Water=g_water, Earth=g_earth, Poison=g_poison, Moon=g_moon, Star=g_star,
              Heart=g_heart, Shadow=g_shadow, Speed=g_speed, Sword=g_sword,
              Gravity=g_gravity, Arrow=g_arrow, Vine=g_vine, Sound=g_sound, Time=g_time)


# ----------------------------------------------------------------------------- build
def build(root):
    marble = L.marble("MAT_PedestalMarble", base=(0.62, 0.58, 0.64), tint=(0.52, 0.48, 0.57),
                      vein=(0.36, 0.32, 0.40), scale=0.7, vein_width=0.012)
    ped_mesh = lathe_mesh("PED_PedestalMesh", PED_PROFILE)
    ped_mesh.materials.append(marble)
    groups = {}
    for i, (name, col) in enumerate(ABILITIES):
        x = i * SPACING
        c = L.coll(f"PED_{name}", root)
        neon = L.emissive(f"MAT_PedNeon_{name}", col, 2.6, base=col)
        stemm = L.emissive(f"MAT_PedStem_{name}", col, 1.5, base=col)
        body = bpy.data.objects.new(f"PED_{name}_Pedestal", ped_mesh)
        c.objects.link(body)
        body.location = (x, 0, 0)
        L.add_bevel(body, 0.05, 2, angle=40)
        top = L.ring(f"PED_{name}_TopNeon", 1.65, 1.45, 0.1, (x, 0, TOP_Z - 0.04), neon, 64, c)
        bot = L.ring(f"PED_{name}_BaseNeon", 1.99, 1.85, 0.1, (x, 0, 0.29), neon, 64, c)
        lip = L.ring(f"PED_{name}_BaseNeonEdge", 2.13, 2.09, 0.07, (x, 0, 0.05), neon, 64, c)
        stem = L.cyl(f"PED_{name}_Stem", 0.05, GLYPH_BASE - TOP_Z + 0.2, (x, 0, (TOP_Z + GLYPH_BASE) / 2), stemm,
                     8, 0.0, c=c)
        g = GLYPHS[name](c, col)
        for ob in g:
            ob.location *= GLYPH_SCALE
            ob.scale = ob.scale * GLYPH_SCALE
        place(g, x, GLYPH_BASE)
        groups[name] = (c, [body, top, bot, lip, stem] + g)
    return groups


def set_visible(groups, only=None):
    for n, (c, _) in groups.items():
        c.hide_render = only is not None and n not in only


def main(do_render=True):
    L.reset()
    root = L.coll("ASSET_02_AbilityPedestals")
    groups = build(root)
    L.empty("PED_Origin", (0, 0, 0), root)
    L.save_blend("02_ability_pedestals.blend")
    if not do_render:
        return
    R = L.RENDERS
    L.studio_lights()
    L.ground(z=0.0)
    # 1) single-pedestal turnaround (Crystal) with others hidden
    set_visible(groups, ["Crystal"])
    items = L.inspection_set("pedestals_single", groups["Crystal"][1], res=600, samples=20,
                             three_q=(-0.55, -1.3, 0.55), detail=[
                                 ("detail_top_ring", (-2.4, -4.6, 4.2), (0, 0, 2.0), 50),
                                 ("detail_base_ring", (-3.2, -5.8, 1.2), (0, 0, 0.6), 50)])
    L.contact_sheet(items, os.path.join(R, "pedestals_single_sheet.png"), cols=4, tile=480,
                    title="ASSET 02 - ABILITY PEDESTAL (shared mesh) - Blender Cycles inspection")
    # 2) per-glyph 3/4 + edge-on side view (matches sheet rows 1 and 2)
    L.setup_render((400, 400), 16)
    items = []
    for i, (name, _) in enumerate(ABILITIES):
        x = i * SPACING
        set_visible(groups, [name])
        cam = L.camera(f"CAM_{name}_3q", (x - 3.0, -8.2, 5.4), (x, 0, 2.6), lens=50)
        items.append((f"{name} 3/4", L.render(cam, os.path.join(R, f"pedestals_{name.lower()}_3q.png"))))
        cam = L.camera(f"CAM_{name}_side", (x - 9.5, -0.9, 3.4), (x, 0, 2.6), lens=50)
        items.append((f"{name} side", L.render(cam, os.path.join(R, f"pedestals_{name.lower()}_side.png"))))
        cam = L.camera(f"CAM_{name}_back", (x + 3.0, 8.2, 5.0), (x, 0, 2.6), lens=50)
        items.append((f"{name} rear 3/4", L.render(cam, os.path.join(R, f"pedestals_{name.lower()}_rear.png"))))
    L.contact_sheet(items, os.path.join(R, "pedestals_glyphs_sheet.png"), cols=9, tile=300,
                    title="ASSET 02 - ABILITY GLYPHS: 3/4, edge-on side, rear 3/4 (Blender Cycles)")
    # 3) beauty row
    set_visible(groups, None)
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT":
            bpy.data.objects.remove(ob)
    L.beauty_lights()
    L.setup_render((1400, 700), 28)
    mid = (len(ABILITIES) - 1) * SPACING / 2
    cam = L.camera("CAM_beauty", (-8.0, -26.0, 9.0), (mid * 0.75, 0, 2.2), lens=32)
    L.render(cam, os.path.join(R, "pedestals_beauty_row.png"))
    cam = L.camera("CAM_beauty_front", (2 * SPACING, -34.0, 8.0), (2 * SPACING, 0, 2.4), lens=30)
    L.render(cam, os.path.join(R, "pedestals_beauty_five.png"))
    nx = (9 + 23) / 2 * SPACING
    cam = L.camera("CAM_beauty_new", (nx, -88.0, 14.0), (nx, 0, 2.6), lens=30)
    L.render(cam, os.path.join(R, "pedestals_beauty_new.png"))


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
