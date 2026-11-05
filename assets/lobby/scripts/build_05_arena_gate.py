"""ASSET 5 - Arena entrance gate / facade.

Primary reference: dedicated ARENA ENTRANCE FACADE prop concept sheet
(front view + left/right angle views + modular hex portal / steps / sign /
leaderboards).  Measurements were taken from the sheet's FRONT VIEW at
~0.0506 stud/px (facade ~1185 px wide -> ~59 studs) with the centre line at
x=1022 px and the ground at y=460 px.

Coordinates: x across, -Y = front (toward spawn), +Z up, ground z=0,
front face of the main wall at y=0.
Run:  python build_05_arena_gate.py [--no-render]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
import lobbylib as L

random.seed(5)

# ---------------------------------------------------------------- dimensions (studs)
PLINTH_X = 29.6
PLINTH_Z = (1.6, 3.3)                 # lower course top, upper course top
WALL_X = 26.0
WALL_Y = (0.0, 4.4)
WALL_TOP = 13.6
COPING_TOP = 14.3
MERLON_TOP = 16.0
TOWER_X, TOWER_W, TOWER_TOP = 26.9, 5.2, 16.2
PILLAR_X, PILLAR_W, PILLAR_TOP = 11.7, 2.9, 18.4
FLANK_X, FLANK_W = 9.4, 1.8
CENTER_X, CENTER_TOP, GABLE_PEAK = 10.6, 18.6, 21.6
SIGN_W, SIGN_Z = 20.8, (14.45, 18.2)
PORTAL_W, PORTAL_H, PORTAL_CZ = 16.4, 12.6, 7.7
PORTAL_TOP_HALF = 4.5                 # half-length of the flat top/bottom edges
PORTAL_FRAME_T = 1.45
PORTAL_Y = (-1.9, 1.0)
STEP_H, STEP_D, N_STEPS = 0.75, 1.3, 4
BOARD_X, BOARD_CZ, BOARD_W, BOARD_H = 19.2, 8.7, 10.4, 9.6


# ---------------------------------------------------------------- helpers
def blocks(name, x0, x1, z0, z1, y0, y1, mat, c, bw=3.2, bh=1.55, gap=0.12, jitter=0.05, skip=None, seed=0):
    """Course of individually bevelled ashlar blocks (one mesh object).
    Front face at y0, back at y1.  `skip(xc, zc)` -> True drops a block."""
    rnd = random.Random(seed)
    bm = bmesh.new()
    rows = max(1, round((z1 - z0) / bh))
    h = (z1 - z0) / rows
    for r in range(rows):
        zc = z0 + h * (r + 0.5)
        x = x0 - (bw * 0.5 if r % 2 else 0.0)
        while x < x1 - 0.05:
            w = bw * rnd.uniform(0.8, 1.15)
            xa, xb = max(x, x0), min(x + w, x1)
            if xb - xa > 0.4 and not (skip and skip((xa + xb) / 2, zc)):
                dy = rnd.uniform(-jitter, jitter)
                m = Matrix.Translation(((xa + xb) / 2, (y0 + y1) / 2 + dy, zc)) @ \
                    Matrix.Diagonal((xb - xa - gap, y1 - y0, h - gap, 1))
                bmesh.ops.create_cube(bm, size=1.0, matrix=m)
            x += w
    ob = L.from_bmesh(name, bm, mat, c)
    L.add_bevel(ob, 0.09, 2, angle=40)
    return ob


def crystal(name, r, h_top, h_bot, loc, mat, c, sides=6, shoulder=0.38, rot=0.0):
    """Faceted elongated bipyramid (cyan crystal finial)."""
    bm = bmesh.new()
    ring0, ring1 = [], []
    for i in range(sides):
        a = 2 * math.pi * i / sides + rot
        ring0.append(bm.verts.new((r * math.cos(a), r * math.sin(a), 0)))
        ring1.append(bm.verts.new((r * 0.92 * math.cos(a), r * 0.92 * math.sin(a), h_top * shoulder)))
    top = bm.verts.new((0, 0, h_top))
    bot = bm.verts.new((0, 0, -h_bot))
    for i in range(sides):
        j = (i + 1) % sides
        bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
        bm.faces.new((ring1[i], ring1[j], top))
        bm.faces.new((ring0[j], ring0[i], bot))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.from_bmesh(name, bm, mat, c)
    ob.location = loc
    return ob


def offset_convex(pts, d):
    """Inset a CCW convex polygon by distance d (edge-line intersection)."""
    n = len(pts)
    lines = []
    for i in range(n):
        a, b = Vector(pts[i]), Vector(pts[(i + 1) % n])
        e = (b - a).normalized()
        nrm = Vector((-e.y, e.x))                    # inward for CCW
        lines.append((a + nrm * d, e))
    out = []
    for i in range(n):
        p1, d1 = lines[i - 1]
        p2, d2 = lines[i]
        den = d1.x * d2.y - d1.y * d2.x
        t = ((p2.x - p1.x) * d2.y - (p2.y - p1.y) * d2.x) / den
        out.append(tuple(p1 + d1 * t))
    return out


def frame_prism(name, outer, inner, y0, y1, mat, c, bevel=0.08, cx=0.0, cz=0.0):
    """Polygon ring (outer minus inner, same vertex count) extruded y0..y1."""
    bm = bmesh.new()
    of = [bm.verts.new((cx + x, y0, cz + z)) for x, z in outer]
    ob_ = [bm.verts.new((cx + x, y1, cz + z)) for x, z in outer]
    inf = [bm.verts.new((cx + x, y0, cz + z)) for x, z in inner]
    inb = [bm.verts.new((cx + x, y1, cz + z)) for x, z in inner]
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((of[i], of[j], inf[j], inf[i]))
        bm.faces.new((ob_[j], ob_[i], inb[i], inb[j]))
        bm.faces.new((of[j], of[i], ob_[i], ob_[j]))
        bm.faces.new((inf[i], inf[j], inb[j], inb[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.from_bmesh(name, bm, mat, c)
    if bevel:
        L.add_bevel(ob, bevel, 2, angle=30)
    return ob


def hexagon(w, h, top_half):
    """Flat top/bottom hexagon, points left/right, CCW in (x,z)."""
    return [(w / 2, 0), (top_half, h / 2), (-top_half, h / 2), (-w / 2, 0), (-top_half, -h / 2), (top_half, -h / 2)]


def rect(w, h, chamfer=0.0):
    if not chamfer:
        return [(w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2), (-w / 2, -h / 2)]
    c = chamfer
    return [(w / 2, -h / 2 + c), (w / 2, h / 2 - c), (w / 2 - c, h / 2), (-w / 2 + c, h / 2), (-w / 2, h / 2 - c),
            (-w / 2, -h / 2 + c), (-w / 2 + c, -h / 2), (w / 2 - c, -h / 2)]


def inside(poly, x, z):
    """Point-in-convex-polygon (CCW)."""
    n = len(poly)
    for i in range(n):
        ax, az = poly[i]; bx, bz = poly[(i + 1) % n]
        if (bx - ax) * (z - az) - (bz - az) * (x - ax) < 0:
            return False
    return True


def diamond(r):
    return [(r, 0), (0, r), (-r, 0), (0, -r)]


def star_points(r_v, r_h, r_s, r_in):
    pts = []
    for k in range(16):
        a = math.pi / 2 - k * math.pi / 8
        r = (r_v if k % 8 == 0 else r_h) if k % 4 == 0 else (r_s if k % 4 == 2 else r_in)
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts[::-1]


def portal_material():
    """Swirling energy surface: polar-coordinate spiral bands + noise, emissive."""
    name = "MAT_PortalSwirl"
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    n, l = m.node_tree.nodes, m.node_tree.links
    b = n["Principled BSDF"]
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    at = n.new("ShaderNodeMath"); at.operation = "ARCTAN2"
    l.new(sep.outputs["Z"], at.inputs[0]); l.new(sep.outputs["X"], at.inputs[1])
    ang = n.new("ShaderNodeMath"); ang.operation = "MULTIPLY"; ang.inputs[1].default_value = 3.0 / (2 * math.pi)
    l.new(at.outputs[0], ang.inputs[0])
    vl = n.new("ShaderNodeVectorMath"); vl.operation = "LENGTH"
    l.new(tc.outputs["Object"], vl.inputs[0])
    rad = n.new("ShaderNodeMath"); rad.operation = "MULTIPLY"; rad.inputs[1].default_value = 0.42
    l.new(vl.outputs["Value"], rad.inputs[0])
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 0.6; nz.inputs["Detail"].default_value = 3
    l.new(tc.outputs["Object"], nz.inputs["Vector"])
    nzm = n.new("ShaderNodeMath"); nzm.operation = "MULTIPLY"; nzm.inputs[1].default_value = 0.5
    l.new(nz.outputs["Fac"], nzm.inputs[0])
    s1 = n.new("ShaderNodeMath"); s1.operation = "ADD"
    l.new(ang.outputs[0], s1.inputs[0]); l.new(rad.outputs[0], s1.inputs[1])
    s2 = n.new("ShaderNodeMath"); s2.operation = "ADD"
    l.new(s1.outputs[0], s2.inputs[0]); l.new(nzm.outputs[0], s2.inputs[1])
    fr = n.new("ShaderNodeMath"); fr.operation = "FRACT"
    l.new(s2.outputs[0], fr.inputs[0])
    ramp = n.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position = 0.0; e[0].color = (0.01, 0.22, 0.75, 1)
    e[1].position = 0.55; e[1].color = (0.15, 0.75, 1.0, 1)
    e3 = e.new(0.8); e3.color = (0.75, 0.97, 1.0, 1)
    e4 = e.new(0.9); e4.color = (0.12, 0.6, 1.0, 1)
    l.new(fr.outputs[0], ramp.inputs["Fac"])
    # brighter core
    core = n.new("ShaderNodeMapRange")
    core.inputs["From Min"].default_value = 0.0; core.inputs["From Max"].default_value = 5.5
    core.inputs["To Min"].default_value = 1.0; core.inputs["To Max"].default_value = 0.0
    l.new(vl.outputs["Value"], core.inputs["Value"])
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["B"].default_value = (0.55, 0.92, 1.0, 1)
    l.new(core.outputs["Result"], mix.inputs["Factor"])
    l.new(ramp.outputs["Color"], mix.inputs["A"])
    l.new(mix.outputs["Result"], b.inputs["Base Color"])
    l.new(mix.outputs["Result"], b.inputs["Emission Color"])
    b.inputs["Emission Strength"].default_value = 1.5
    b.inputs["Roughness"].default_value = 0.2
    m.diffuse_color = (0.15, 0.75, 1.0, 1)
    m["roblox_neon"] = True
    return m


# ---------------------------------------------------------------- build
def build(P, root):
    C = {k: L.coll(f"GATE_{k}", root) for k in
         ("Wall", "Towers", "Pillars", "Portal", "Steps", "Signage", "Leaderboards", "Crystals", "Trim", "Banners")}
    # gate stone is a deeper lavender-grey than the arch marble on the facade sheet
    M = L.marble("MAT_GateStone", base=(0.74, 0.70, 0.86), tint=(0.64, 0.60, 0.80), vein=(0.50, 0.46, 0.62))
    MD = L.marble("MAT_GateStoneJoint", base=(0.50, 0.47, 0.62), tint=(0.44, 0.41, 0.56), vein=(0.36, 0.33, 0.46))
    G, NAVY, CY = P["gold"], P["navy"], P["cyan"]
    white = P["white"]
    crys = L.emissive("MAT_GateCrystal", (0.04, 0.55, 1.0), 1.6, base=(0.15, 0.68, 1.0))
    silver = L.flat("MAT_Silver", (0.82, 0.84, 0.9), rough=0.25, metal=0.85)
    copper = L.flat("MAT_CrownBronze", (0.85, 0.45, 0.2), rough=0.3, metal=0.75)
    bar = L.emissive("MAT_BoardBar", (0.35, 0.55, 1.0), 0.6, base=(0.5, 0.65, 1.0))
    portal_mat = portal_material()
    objs = []
    add = objs.append

    # ---------------- plinth (two stepped courses, full width)
    add(L.box("GATE_PlinthLower", (2 * PLINTH_X, 6.4, PLINTH_Z[0]), (0, 1.9, PLINTH_Z[0] / 2), MD, 0.14, c=C["Wall"]))
    add(L.box("GATE_PlinthUpper", (2 * PLINTH_X - 0.8, 5.8, PLINTH_Z[1] - PLINTH_Z[0]),
              (0, 2.0, (PLINTH_Z[0] + PLINTH_Z[1]) / 2), M, 0.12, c=C["Wall"]))
    # front facing blocks on the upper plinth course (block joints read on the base)
    add(blocks("GATE_PlinthBlocks", -PLINTH_X + 0.45, PLINTH_X - 0.45, PLINTH_Z[0], PLINTH_Z[1], -0.95, -0.85, M,
               C["Wall"], bw=3.4, bh=1.7, seed=1, skip=lambda x, z: abs(x) < 9.9))
    # diamond inlays along the lower course, gold diamond plaques under the inner pillars
    for x in (-25.4, -21.2, -17.0, -6.0, 6.0, 17.0, 21.2, 25.4):
        if abs(x) < 10.2:
            continue
        d = L.extrude_polygon(f"GATE_PlinthDiamond_{x:+.0f}", diamond(0.55), 0.18, MD, C["Trim"], bevel=0.04)
        d.location = (x, -1.2, PLINTH_Z[0] / 2 + 0.05)
        add(d)
    for s in (-1, 1):
        fr = frame_prism(f"GATE_GoldPlaque_{s:+d}", diamond(1.0), diamond(0.62), -1.45, -1.05, G, C["Trim"], 0.04,
                         cx=s * PILLAR_X, cz=1.85)
        add(fr)
        ctr = L.extrude_polygon(f"GATE_GoldPlaqueCore_{s:+d}", diamond(0.62), 0.3, NAVY, C["Trim"])
        ctr.location = (s * PILLAR_X, -1.15, 1.85)
        add(ctr)
        gem = crystal(f"GATE_GoldPlaqueGem_{s:+d}", 0.3, 0.32, 0.32, (s * PILLAR_X, -1.42, 1.85), crys, C["Trim"],
                      sides=4)
        gem.rotation_euler = (math.pi / 2, 0, 0)
        add(gem)

    # ---------------- main wall (core + ashlar facing front and back)
    core_top = WALL_TOP
    add(L.box("GATE_WallCore", (2 * WALL_X, WALL_Y[1] - WALL_Y[0], core_top - PLINTH_Z[1]),
              (0, sum(WALL_Y) / 2, (PLINTH_Z[1] + core_top) / 2), MD, 0.05, c=C["Wall"]))
    add(blocks("GATE_WallBlocksFront", -WALL_X, WALL_X, PLINTH_Z[1], core_top, -0.35, 0.02, M, C["Wall"], seed=2,
               skip=lambda x, z: abs(x) < CENTER_X - 0.2))
    add(blocks("GATE_WallBlocksBack", -WALL_X, WALL_X, PLINTH_Z[1], core_top, WALL_Y[1] - 0.02, WALL_Y[1] + 0.35, M,
               C["Wall"], seed=3))
    add(L.box("GATE_Coping", (2 * WALL_X + 0.4, 5.6, COPING_TOP - core_top), (0, 2.2, (core_top + COPING_TOP) / 2), M,
              0.12, c=C["Wall"]))
    # crenellations (merlons) along the wall top, outside the raised centre
    mw, step = 2.2, 3.6
    x = -WALL_X + 1.4
    k = 0
    while x < WALL_X - 1.0:
        if abs(x) > CENTER_X + 1.4 and abs(x) < TOWER_X - TOWER_W / 2 - 0.9:
            add(L.box(f"GATE_Merlon_{k:02d}", (mw, 4.9, MERLON_TOP - COPING_TOP),
                      (x, 2.2, (COPING_TOP + MERLON_TOP) / 2), M, 0.1, c=C["Wall"]))
            k += 1
        x += step

    # ---------------- outer end towers
    for s in (-1, 1):
        tx = s * TOWER_X
        tag = "L" if s < 0 else "R"
        add(L.box(f"GATE_Tower{tag}_Base", (TOWER_W + 0.9, 7.6, PLINTH_Z[1] + 0.6),
                  (tx, 1.9, (PLINTH_Z[1] + 0.6) / 2), M, 0.14, c=C["Towers"]))
        add(L.box(f"GATE_Tower{tag}_Body", (TOWER_W, 6.6, TOWER_TOP - PLINTH_Z[1]),
                  (tx, 1.9, (PLINTH_Z[1] + TOWER_TOP) / 2), MD, 0.06, c=C["Towers"]))
        add(blocks(f"GATE_Tower{tag}_Blocks", tx - TOWER_W / 2 - 0.05, tx + TOWER_W / 2 + 0.05, PLINTH_Z[1] + 0.6,
                   TOWER_TOP, -1.75, -1.4, M, C["Towers"], bw=2.4, bh=1.5, seed=10 + s,
                   skip=lambda x, z, tx=tx: abs(x - tx) < 0.75 and 5.6 < z < 13.4))
        side = blocks(f"GATE_Tower{tag}_BlocksSide", 0.0, 6.5, PLINTH_Z[1] + 0.6, TOWER_TOP, -0.35, 0.0, M,
                      C["Towers"], bw=2.4, bh=1.5, seed=20 + s)
        side.rotation_euler = (0, 0, s * math.pi / 2)
        side.location = (tx + s * (TOWER_W / 2 + 0.02), 5.1 if s < 0 else -1.4, 0)
        add(side)
        add(L.box(f"GATE_Tower{tag}_Cap", (TOWER_W + 0.7, 7.3, 0.7), (tx, 1.9, TOWER_TOP + 0.35), M, 0.12,
                  c=C["Towers"]))
        for qx in (-1, 1):
            for qy in (-1, 1):
                add(L.box(f"GATE_Tower{tag}_Merlon_{qx:+d}{qy:+d}", (1.5, 1.5, 1.2),
                          (tx + qx * (TOWER_W / 2 - 0.55), 1.9 + qy * 2.75, TOWER_TOP + 0.7 + 0.6), M, 0.1,
                          c=C["Towers"]))
        add(L.box(f"GATE_Tower{tag}_CrystalSeat", (1.9, 1.9, 0.9), (tx, 1.9, TOWER_TOP + 1.15), G, 0.1,
                  c=C["Crystals"]))
        add(crystal(f"GATE_Tower{tag}_Crystal", 0.95, 3.1, 0.6, (tx, 1.9, TOWER_TOP + 2.1), crys, C["Crystals"]))
        # gold band + inset neon slot on the front face
        add(L.box(f"GATE_Tower{tag}_GoldBand", (TOWER_W + 0.25, 0.3, 0.5), (tx, -1.82, 5.1), G, 0.06, c=C["Trim"]))
        for e in (-1, 1):
            add(L.box(f"GATE_Tower{tag}_SlotRail_{e:+d}", (0.35, 0.5, 7.9), (tx + e * 0.62, -1.62, 9.5), M, 0.06,
                      c=C["Towers"]))
        add(L.box(f"GATE_Tower{tag}_Neon", (0.55, 0.3, 7.5), (tx, -1.45, 9.5), CY, 0.04, c=C["Trim"]))

    # ---------------- inner pillars (flank the centre, crystals on top, banners)
    for s in (-1, 1):
        px = s * PILLAR_X
        tag = "L" if s < 0 else "R"
        add(L.box(f"GATE_Pillar{tag}_Base", (PILLAR_W + 0.8, 7.0, 1.0), (px, 1.6, PLINTH_Z[1] + 0.5), M, 0.12,
                  c=C["Pillars"]))
        add(L.box(f"GATE_Pillar{tag}_Shaft", (PILLAR_W, 6.4, PILLAR_TOP - PLINTH_Z[1]),
                  (px, 1.6, (PLINTH_Z[1] + PILLAR_TOP) / 2), M, 0.1, c=C["Pillars"]))
        add(L.box(f"GATE_Pillar{tag}_Cap", (PILLAR_W + 0.6, 7.0, 0.6), (px, 1.6, PILLAR_TOP + 0.3), M, 0.1,
                  c=C["Pillars"]))
        add(L.box(f"GATE_Pillar{tag}_CrystalSeat", (1.8, 1.8, 0.6), (px, 1.0, PILLAR_TOP + 0.9), G, 0.08,
                  c=C["Crystals"]))
        add(crystal(f"GATE_Pillar{tag}_Crystal", 1.0, 3.3, 0.6, (px, 1.0, PILLAR_TOP + 1.8), crys, C["Crystals"]))
        for z in (12.85, 13.4):
            add(L.box(f"GATE_Pillar{tag}_GoldBand_{z}", (PILLAR_W + 0.18, 6.55, 0.22), (px, 1.6, z), G, 0.05,
                      c=C["Trim"]))
        for e in (-1, 1):
            add(L.box(f"GATE_Pillar{tag}_SlotRail_{e:+d}", (0.3, 0.4, 4.4), (px + e * 0.52, -1.75, 15.9), M, 0.05,
                      c=C["Pillars"]))
        add(L.box(f"GATE_Pillar{tag}_Neon", (0.45, 0.3, 4.2), (px, -1.62, 15.9), CY, 0.04, c=C["Trim"]))
        # banner (navy, gold edge, white star) hanging on the front face
        add_banner(f"GATE_Pillar{tag}_Banner", px, -1.95, 12.55, 2.3, 5.4, 0.9, P, C["Banners"], add)
        # small crystal on a gold bracket below the banner
        add(L.box(f"GATE_Pillar{tag}_LowBracket", (0.9, 0.6, 0.35), (px, -1.95, 4.15), G, 0.06, c=C["Crystals"]))
        add(crystal(f"GATE_Pillar{tag}_LowCrystal", 0.45, 1.5, 0.3, (px, -2.0, 4.4), crys, C["Crystals"]))

    # ---------------- portal-flanking columns + raised centre with gable
    for s in (-1, 1):
        fx = s * FLANK_X
        tag = "L" if s < 0 else "R"
        add(L.box(f"GATE_Flank{tag}_Shaft", (FLANK_W, 5.2, WALL_TOP - PLINTH_Z[1]),
                  (fx, 1.4, (PLINTH_Z[1] + WALL_TOP) / 2), M, 0.08, c=C["Pillars"]))
        add(L.box(f"GATE_Flank{tag}_Capital", (FLANK_W + 0.5, 5.6, 0.6), (fx, 1.4, WALL_TOP - 0.3), M, 0.08,
                  c=C["Pillars"]))
        add(L.box(f"GATE_Flank{tag}_Plinth", (FLANK_W + 0.5, 5.6, 0.7), (fx, 1.4, PLINTH_Z[1] + 0.35), M, 0.08,
                  c=C["Pillars"]))
    add(L.box("GATE_CentreCore", (2 * CENTER_X, WALL_Y[1] - WALL_Y[0] + 0.2, CENTER_TOP - PLINTH_Z[1]),
              (0, sum(WALL_Y) / 2 + 0.1, (PLINTH_Z[1] + CENTER_TOP) / 2), MD, 0.05, c=C["Wall"]))
    hole = hexagon(PORTAL_W - 0.6, PORTAL_H - 0.6, PORTAL_TOP_HALF - 0.2)
    add(blocks("GATE_CentreBlocksFront", -CENTER_X, CENTER_X, PLINTH_Z[1], CENTER_TOP, -0.45, -0.1, M, C["Wall"],
               bw=2.6, bh=1.5, seed=4, skip=lambda x, z: inside(hole, x, z - PORTAL_CZ)))
    add(blocks("GATE_CentreBlocksBack", -CENTER_X, CENTER_X, PLINTH_Z[1], CENTER_TOP, WALL_Y[1] + 0.3,
               WALL_Y[1] + 0.65, M, C["Wall"], bw=2.6, bh=1.5, seed=5))
    gable = [(CENTER_X + 0.3, 0), (0, GABLE_PEAK - CENTER_TOP), (-CENTER_X - 0.3, 0)]
    g = L.extrude_polygon("GATE_Gable", gable, 5.4, M, C["Wall"], bevel=0.1)
    g.location = (0, 2.2, CENTER_TOP)
    add(g)
    add(L.box("GATE_GableLedge", (2 * CENTER_X + 0.9, 6.0, 0.45), (0, 2.2, CENTER_TOP + 0.05), M, 0.1, c=C["Wall"]))
    slope = math.atan2(GABLE_PEAK - CENTER_TOP, CENTER_X + 0.3)
    hyp = math.hypot(GABLE_PEAK - CENTER_TOP, CENTER_X + 0.3)
    for s in (-1, 1):
        cp = L.box(f"GATE_GableCoping_{s:+d}", (hyp + 0.8, 6.0, 0.6),
                   (s * (CENTER_X + 0.3) / 2, 2.2, CENTER_TOP + (GABLE_PEAK - CENTER_TOP) / 2 + 0.3), M, 0.1,
                   c=C["Wall"], rot=(0, s * slope, 0))
        add(cp)
        # small cyan diamond studs on the gable face
        st = crystal(f"GATE_GableStud_{s:+d}", 0.42, 0.42, 0.42, (s * 3.2, -0.62, CENTER_TOP + 0.95), crys,
                     C["Crystals"], sides=4)
        st.rotation_euler = (math.pi / 2, 0, 0)
        add(st)
    # roof ornament: marble diamond frame + gold rim + big cyan crystal at the apex
    oz = GABLE_PEAK - 0.2
    add(frame_prism("GATE_OrnamentFrame", diamond(2.35), diamond(1.45), -1.1, 0.9, M, C["Wall"], 0.08, cz=oz))
    add(frame_prism("GATE_OrnamentGold", diamond(1.5), diamond(1.25), -1.2, 0.6, G, C["Trim"], 0.03, cz=oz))
    gem = crystal("GATE_OrnamentCrystal", 1.25, 0.75, 0.75, (0, -0.4, oz), crys, C["Crystals"], sides=4)
    gem.rotation_euler = (math.pi / 2, 0, 0)
    add(gem)

    # ---------------- ENTER THE ARENA sign
    sz0, sz1 = SIGN_Z
    sh = sz1 - sz0
    scz = (sz0 + sz1) / 2
    sg = L.extrude_polygon("GATE_SignGoldFrame", rect(SIGN_W, sh, 0.55), 0.45, G, C["Signage"], bevel=0.06)
    sg.location = (0, -2.05, scz)
    add(sg)
    vpt = L.extrude_polygon("GATE_SignPoint", [(0.95, 0), (0, -0.85), (-0.95, 0)][::-1], 0.45, G, C["Signage"],
                            bevel=0.04)
    vpt.location = (0, -2.05, sz0 + 0.02)
    add(vpt)
    nv = L.extrude_polygon("GATE_SignPanel", rect(SIGN_W - 0.7, sh - 0.7, 0.4), 0.6, NAVY, C["Signage"], bevel=0.03)
    nv.location = (0, -2.05, scz)
    add(nv)
    txt = L.text_mesh("GATE_SignText", "ENTER THE ARENA", size=2.55, extrude=0.08, mat=white, c=C["Signage"],
                      loc=(0, -2.42, scz + 0.05), spacing=1.02)
    add(txt)
    for s in (-1, 1):
        add(L.box(f"GATE_SignBracket_{s:+d}", (0.6, 1.8, 0.6), (s * 6.0, -1.0, sz1 - 0.6), G, 0.06, c=C["Signage"]))

    # ---------------- hex portal (marble frame, inner lip, neon ring, energy surface)
    hx = hexagon(PORTAL_W, PORTAL_H, PORTAL_TOP_HALF)
    in1 = offset_convex(hx, PORTAL_FRAME_T)
    in2 = offset_convex(in1, 0.45)
    in3 = offset_convex(in2, 0.42)
    add(frame_prism("GATE_PortalFrame", hx, in1, PORTAL_Y[0], PORTAL_Y[1], M, C["Portal"], 0.14, cz=PORTAL_CZ))
    add(frame_prism("GATE_PortalLip", in1, in2, PORTAL_Y[0] + 0.45, PORTAL_Y[1], MD, C["Portal"], 0.06,
                    cz=PORTAL_CZ))
    add(frame_prism("GATE_PortalNeon", in2, in3, PORTAL_Y[0] + 0.55, PORTAL_Y[1] - 0.2, CY, C["Portal"], 0.04,
                    cz=PORTAL_CZ))
    # outer gold-less marble chamfer ring (thin stepped edge seen on the sheet)
    add(frame_prism("GATE_PortalOuterStep", offset_convex(hx, -0.35), hx, PORTAL_Y[0] + 0.5, PORTAL_Y[1], MD,
                    C["Portal"], 0.06, cz=PORTAL_CZ))
    surf = L.extrude_polygon("GATE_PortalSurface", in3, 0.2, portal_mat, C["Portal"])
    surf.location = (0, 0.1, PORTAL_CZ)
    add(surf)
    # crystal sconces beside the portal (gold kite plaque + crystal)
    kite = [(0, -1.0), (0.6, 0.15), (0, 0.85), (-0.6, 0.15)]
    for s in (-1, 1):
        kp = L.extrude_polygon(f"GATE_Sconce_{s:+d}", kite, 0.3, G, C["Trim"], bevel=0.04)
        kp.location = (s * 7.55, -0.6, 11.4)
        add(kp)
        sc = crystal(f"GATE_SconceCrystal_{s:+d}", 0.32, 1.05, 0.3, (s * 7.55, -0.85, 11.35), crys, C["Crystals"])
        add(sc)

    # ---------------- entrance steps with cyan riser strips
    top_front = -2.6
    for k in range(N_STEPS):
        ztop = STEP_H * (k + 1)
        yf = top_front - STEP_D * (N_STEPS - 1 - k)
        hw = 9.9 - 0.45 * k
        add(L.box(f"GATE_Step_{k}", (2 * hw, 1.2 - yf, STEP_H), (0, (yf + 1.2) / 2, ztop - STEP_H / 2), M, 0.1,
                  c=C["Steps"]))
        add(L.box(f"GATE_StepNeon_{k}", (2 * hw - 0.9, 0.12, 0.16), (0, yf - 0.03, ztop - 0.27), CY, 0.02,
                  c=C["Steps"]))
    for s in (-1, 1):
        add(L.box(f"GATE_StepCheek_{s:+d}", (1.2, 5.6, 1.4), (s * 10.6, -2.4, PLINTH_Z[0] + 0.0), M, 0.12,
                  c=C["Steps"]))
        add(crystal(f"GATE_StepCrystal_{s:+d}", 0.42, 1.6, 0.3, (s * 10.6, -2.6, PLINTH_Z[0] + 0.8), crys,
                    C["Crystals"]))

    # ---------------- leaderboards
    for s, title in ((-1, "MOST KILLS"), (1, "TOP TIME")):
        bx = s * BOARD_X
        tag = "MostKills" if s < 0 else "TopTime"
        outer = rect(BOARD_W, BOARD_H, 0.6)
        add(frame_prism(f"GATE_Board{tag}_Frame", outer, offset_convex(outer, 0.75), -0.95, 0.05, M,
                        C["Leaderboards"], 0.1, cx=bx, cz=BOARD_CZ))
        g_out = offset_convex(outer, 0.62)
        add(frame_prism(f"GATE_Board{tag}_GoldTrim", g_out, offset_convex(g_out, 0.22), -1.02, -0.3, G,
                        C["Leaderboards"], 0.03, cx=bx, cz=BOARD_CZ))
        pnl = L.extrude_polygon(f"GATE_Board{tag}_Panel", offset_convex(outer, 0.8), 0.3, NAVY, C["Leaderboards"])
        pnl.location = (bx, -0.55, BOARD_CZ)
        add(pnl)
        add(L.text_mesh(f"GATE_Board{tag}_Title", title, size=1.35, extrude=0.06, mat=white, c=C["Leaderboards"],
                        loc=(bx, -0.74, BOARD_CZ + 3.0)))
        add(L.box(f"GATE_Board{tag}_Underline", (BOARD_W - 2.6, 0.08, 0.1), (bx, -0.73, BOARD_CZ + 2.05), bar, 0.0,
                  c=C["Leaderboards"]))
        for r, (cm, zz) in enumerate(((G, 0.9), (silver, -1.25), (copper, -3.3))):
            cr = L.extrude_polygon(f"GATE_Board{tag}_Crown_{r}", crown_outline(), 0.3, cm, C["Leaderboards"],
                                   bevel=0.03)
            cr.location = (bx - 3.35, -0.85, BOARD_CZ + zz - 0.5)
            cr.scale = (1.05, 1, 1.05)
            add(cr)
            for jx, jz in ((-0.95, 1.05), (0.0, 1.15), (0.95, 1.05)):
                bmj = bmesh.new()
                bmesh.ops.create_uvsphere(bmj, u_segments=10, v_segments=6, radius=0.14)
                j = L.from_bmesh(f"GATE_Board{tag}_CrownJewel_{r}_{jx:+.0f}", bmj, cm, C["Leaderboards"])
                j.location = (bx - 3.35 + jx * 1.05, -0.85, BOARD_CZ + zz - 0.5 + jz * 1.05)
                add(j)
            add(L.box(f"GATE_Board{tag}_Bar_{r}", (5.6, 0.1, 0.42), (bx + 0.9, -0.74, BOARD_CZ + zz + 0.1), bar, 0.04,
                      c=C["Leaderboards"]))
            add(L.box(f"GATE_Board{tag}_BarThin_{r}", (3.6, 0.1, 0.2), (bx - 0.1, -0.74, BOARD_CZ + zz - 0.55), bar,
                      0.02, c=C["Leaderboards"]))
    return objs


def crown_outline():
    return [(-0.8, 0), (0.8, 0), (0.8, 0.32), (0.95, 1.05), (0.45, 0.55), (0, 1.15), (-0.45, 0.55), (-0.95, 1.05),
            (-0.8, 0.32)]


def add_banner(name, x, y, top, w, h1, pd, P, c, add):
    outline = [(-w / 2, 0), (w / 2, 0), (w / 2, -h1), (0, -h1 - pd), (-w / 2, -h1)]
    i = 0.16
    inner = [(-w / 2 + i, -0.1), (w / 2 - i, -0.1), (w / 2 - i, -h1 + 0.06), (0, -h1 - pd + 0.32),
             (-w / 2 + i, -h1 + 0.06)]
    t = L.extrude_polygon(f"{name}Trim", outline, 0.1, P["gold"], c, bevel=0.03)
    cl = L.extrude_polygon(f"{name}Cloth", inner, 0.16, P["navy"], c, bevel=0.02)
    for ob in (t, cl):
        ob.location = (x, y, top)
    st = L.extrude_polygon(f"{name}Star", star_points(1.15, 0.85, 0.42, 0.18), 0.05, P["white"], c,
                           center_depth=False)
    st.location = (x, y - 0.125, top - h1 * 0.45)
    gm = L.extrude_polygon(f"{name}Gem", [(0, 0.26), (0.17, 0), (0, -0.26), (-0.17, 0)], 0.05, P["cyan_soft"], c,
                           center_depth=False)
    gm.location = (x, y - 0.155, top - h1 * 0.45)
    rod = L.cyl(f"{name}Rod", 0.1, w + 0.7, (x, y, top + 0.1), P["gold"], 12, 0.02, c=c, rot=(0, math.pi / 2, 0))
    for o in (t, cl, st, gm, rod):
        add(o)
    for sx in (-1, 1):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=12, v_segments=8, radius=0.18)
        f = L.from_bmesh(f"{name}Finial_{sx:+d}", bm, P["gold"], c)
        f.location = (x + sx * (w / 2 + 0.45), y, top + 0.1)
        add(f)


def reference_match(objs):
    L.clear_rig()
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT" or ob.name == "RIG_Ground":
            bpy.data.objects.remove(ob)
    L.beauty_lights()
    L.ground(color=(0.80, 0.78, 0.86), z=0.0)
    L.setup_render((1000, 640), 32)
    out = []
    c = L.camera("CAM_refmatch_front", (0, -95, 11.5), (0, 0, 10.5), lens=50)
    out.append(("refmatch_front_view", L.render(c, os.path.join(L.RENDERS, "gate_refmatch_front.png"))))
    c = L.camera("CAM_refmatch_left", (-52, -66, 13), (-1.0, 0, 9.5), lens=40)
    out.append(("refmatch_angle_left", L.render(c, os.path.join(L.RENDERS, "gate_refmatch_angle_left.png"))))
    c = L.camera("CAM_refmatch_right", (52, -66, 13), (1.0, 0, 9.5), lens=40)
    out.append(("refmatch_angle_right", L.render(c, os.path.join(L.RENDERS, "gate_refmatch_angle_right.png"))))
    return out


def main(do_render=True):
    L.reset()
    P = L.palette()
    root = L.coll("ASSET_05_ArenaGate")
    objs = build(P, root)
    L.empty("GATE_Origin", (0, 0, 0), root)
    L.save_blend("05_arena_gate.blend")
    if not do_render:
        return
    L.studio_lights()
    L.ground(z=0.0)
    items = L.inspection_set("gate", objs, res=800, samples=28, three_q=(-0.8, -1.25, 0.45), detail=[
        ("detail_portal_sign", (6.0, -26.0, 12.0), (0.0, 0.0, 11.5), 42),
        ("detail_leaderboard", (-15.0, -15.0, 9.5), (-19.2, -0.8, 8.7), 45),
        ("detail_pillar_crystal", (-6.0, -12.0, 19.0), (-11.7, 0.0, 18.0), 40),
    ])
    items += reference_match(objs)
    L.contact_sheet(items, os.path.join(L.RENDERS, "gate_inspection_sheet.png"), cols=4, tile=520,
                    title="ASSET 05 - ARENA ENTRANCE GATE (Blender Cycles renders)")


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
