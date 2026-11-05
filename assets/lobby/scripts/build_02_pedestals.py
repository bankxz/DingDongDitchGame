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


GLYPHS = dict(Crystal=g_crystal, Lightning=g_lightning, Shield=g_shield, Flame=g_flame, Wind=g_wind,
              Emerald=g_emerald, Sun=g_sun, Orb=g_orb, Wings=g_wings)


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
    L.setup_render((480, 480), 20)
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
    L.contact_sheet(items, os.path.join(R, "pedestals_glyphs_sheet.png"), cols=6, tile=400,
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


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
