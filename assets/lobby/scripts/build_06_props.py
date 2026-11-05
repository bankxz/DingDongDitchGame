"""ASSET 6 - Secondary lobby props (modular kit).

Sources: lobby screenshots (1.webp main view, 3.webp spawn-plaza view, 2/4 sheets)
+ arch turnaround for the stone-post finial.  No vegetation is modelled
(planters are empty with a soil top).

Props (each in its own collection, origin at its own floor centre):
  PROP_BalustradeStraight, PROP_BalustradeCorner, PROP_BalustradeCurved,
  PROP_LanternPost, PROP_PlanterLong, PROP_PlanterSquare, PROP_EventsBanner,
  PROP_StarBanner, PROP_RoadCobble (textured cobble surface + gold edging + cyan strips + chevrons),
  PROP_FloorMarble, PROP_SpawnPlaza (circular floor + neon star), PROP_StepsCurved,
  PROP_StonePost, PROP_GoldTrim, PROP_NeonEdgeStrip
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
import lobbylib as L

random.seed(6)
P = None
SKIP_EXISTING = "--skip-existing" in sys.argv


def lathe(name, prof, segs, mat, c, loc, rot=(0, 0, 0)):
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
    ob = L.from_bmesh(name, bm, mat, c)
    ob.location = loc
    ob.rotation_euler = rot
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def sphere(name, r, loc, mat, c, seg=16):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=max(6, seg // 2), radius=r)
    ob = L.from_bmesh(name, bm, mat, c)
    ob.location = loc
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def arc_block(name, r0, r1, z0, z1, a0, a1, mat, c, segs=12, bevel=0.06):
    """Annular sector solid (curved steps, curved rails, plaza rings)."""
    bm = bmesh.new()
    rows = []
    for s in range(segs + 1):
        a = a0 + (a1 - a0) * s / segs
        ca, sa = math.cos(a), math.sin(a)
        rows.append([bm.verts.new((r * ca, r * sa, z)) for r, z in ((r0, z0), (r1, z0), (r1, z1), (r0, z1))])
    for s in range(segs):
        for k in range(4):
            k2 = (k + 1) % 4
            bm.faces.new((rows[s][k], rows[s][k2], rows[s + 1][k2], rows[s + 1][k]))
    bm.faces.new(rows[0][::-1])
    bm.faces.new(rows[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.from_bmesh(name, bm, mat, c)
    L.add_bevel(ob, bevel, 2, angle=30)
    return ob


def star_poly(n_long, r_long, r_short, r_in, rot=math.pi / 2):
    """2*n_long-point star: long points, short diagonals, inner notches."""
    pts = []
    k_tot = n_long * 4
    for k in range(k_tot):
        a = rot + 2 * math.pi * k / k_tot
        r = r_long if k % 4 == 0 else (r_short if k % 4 == 2 else r_in)
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


# ============================================================ balustrade
BAL_PROF = [(0.34, 0.0), (0.34, 0.14), (0.22, 0.24), (0.2, 0.5), (0.32, 0.95), (0.36, 1.15), (0.3, 1.4),
            (0.18, 1.7), (0.22, 1.82), (0.34, 1.9), (0.34, 2.02)]
RAIL_H = 3.4


def bal_post(name, x, y, c, w=1.9, h=4.1):
    M = P["marble"]
    o = [L.box(f"{name}_Plinth", (w + 0.35, w + 0.35, 0.55), (x, y, 0.275), M, 0.08, c=c),
         L.box(f"{name}_Body", (w, w, h - 0.95), (x, y, 0.55 + (h - 0.95) / 2), M, 0.09, c=c),
         L.box(f"{name}_GoldBand", (w + 0.12, w + 0.12, 0.18), (x, y, h - 0.4 - 0.09 + 0.0), P["gold"], 0.03, c=c),
         L.box(f"{name}_Cap", (w + 0.4, w + 0.4, 0.4), (x, y, h - 0.2), M, 0.1, c=c),
         L.cyl(f"{name}_CapDome", w * 0.36, 0.35, (x, y, h + 0.175), M, 4, 0.06, c=c, r2=w * 0.22,
               rot=(0, 0, math.pi / 4))]
    return o


def bal_run(name, p0, p1, c, n=None):
    """Straight run between two points (post faces), marble balusters."""
    M = P["marble"]
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    ln = d.length
    ang = math.atan2(d.y, d.x)
    mid = (p0 + p1) / 2
    n = n or max(1, int(ln / 0.95))
    o = [L.box(f"{name}_Bottom", (ln, 1.05, 0.55), (mid.x, mid.y, 0.275), M, 0.08, c=c, rot=(0, 0, ang)),
         L.box(f"{name}_Hand", (ln, 1.0, 0.5), (mid.x, mid.y, RAIL_H - 0.25), M, 0.14, c=c, rot=(0, 0, ang)),
         L.box(f"{name}_HandGold", (ln, 1.02, 0.1), (mid.x, mid.y, RAIL_H - 0.55), P["gold"], 0.02, c=c,
               rot=(0, 0, ang))]
    for k in range(n):
        t = (k + 0.5) / n
        p = p0 + d * t
        o.append(lathe(f"{name}_Bal_{k}", BAL_PROF, 12, M, c, (p.x, p.y, 0.55)))
    return o


def prop_balustrade_straight(c):
    # module: post at x=0 + run to x=10 (next module supplies the next post)
    o = bal_post("PROP_BalS_Post", 0, 0, c)
    o += bal_run("PROP_BalS_Run", (0.95, 0), (10 - 0.95, 0), c, 8)
    return o


def prop_balustrade_corner(c):
    o = bal_post("PROP_BalC_Post", 0, 0, c, w=2.3, h=4.4)
    o += bal_run("PROP_BalC_RunX", (1.15, 0), (6.0, 0), c, 5)
    o += bal_run("PROP_BalC_RunY", (0, 1.15), (0, 6.0), c, 5)
    return o


def prop_balustrade_curved(c, R=16.0, span=30):
    """Curved run for the spawn plaza: post at a0 + run to a1 (centre of curvature at origin offset)."""
    M = P["marble"]
    a0, a1 = math.radians(-span / 2), math.radians(span / 2)
    o = []
    px, py = R * math.cos(a0), R * math.sin(a0)
    o += bal_post("PROP_BalCurve_Post", px, py, c)
    ga = 1.0 / R
    o.append(arc_block("PROP_BalCurve_Bottom", R - 0.52, R + 0.52, 0, 0.55, a0 + ga, a1 - ga, M, c, 10))
    o.append(arc_block("PROP_BalCurve_Hand", R - 0.5, R + 0.5, RAIL_H - 0.5, RAIL_H, a0 + ga, a1 - ga, M, c, 10, 0.12))
    o.append(arc_block("PROP_BalCurve_HandGold", R - 0.51, R + 0.51, RAIL_H - 0.6, RAIL_H - 0.5, a0 + ga, a1 - ga,
                       P["gold"], c, 10, 0.02))
    n = 7
    for k in range(n):
        a = a0 + ga + (a1 - a0 - 2 * ga) * (k + 0.5) / n
        o.append(lathe(f"PROP_BalCurve_Bal_{k}", BAL_PROF, 12, M, c, (R * math.cos(a), R * math.sin(a), 0.55)))
    for ob in o:   # recentre on the arc midpoint, then turn so the run follows +X like the straight module
        x, y = ob.location.x - R, ob.location.y
        ob.location.x, ob.location.y = -y, x
        ob.rotation_euler.z += math.pi / 2
    return o


# ============================================================ lantern post
def prop_lantern_post(c):
    M = P["marble"]
    iron = L.flat("MAT_LanternIron", (0.13, 0.15, 0.22), rough=0.45, metal=0.6)
    glass = L.glass_emissive("MAT_LanternGlassCyan", (0.35, 0.9, 1.0), 3.0, alpha=0.9)
    glow = L.emissive("MAT_NeonCyan", (0.05, 0.75, 1.0), 3.2)
    o = [L.box("PROP_Lantern_Plinth", (2.3, 2.3, 0.6), (0, 0, 0.3), M, 0.1, c=c),
         L.box("PROP_Lantern_Body", (1.75, 1.75, 2.9), (0, 0, 0.6 + 1.45), M, 0.09, c=c),
         L.box("PROP_Lantern_GoldBand", (1.95, 1.95, 0.22), (0, 0, 3.4), P["gold"], 0.04, c=c),
         L.box("PROP_Lantern_Cap", (2.2, 2.2, 0.38), (0, 0, 3.7), M, 0.1, c=c),
         L.box("PROP_Lantern_IronBase", (1.55, 1.55, 0.25), (0, 0, 4.0), iron, 0.05, c=c),
         L.box("PROP_Lantern_Glass", (1.18, 1.18, 1.85), (0, 0, 4.13 + 0.925), glass, 0.04, c=c),
         L.box("PROP_Lantern_IronTop", (1.6, 1.6, 0.22), (0, 0, 6.11), iron, 0.05, c=c)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(L.box(f"PROP_Lantern_Frame_{sx}{sy}", (0.18, 0.18, 1.95), (sx * 0.62, sy * 0.62, 5.05), iron,
                           0.03, c=c))
    # mid muntin bars + star glyph on each pane
    for i, (nx, ny) in enumerate(((0, -1), (1, 0), (0, 1), (-1, 0))):
        ang = math.atan2(ny, nx) + math.pi / 2
        o.append(L.box(f"PROP_Lantern_Muntin_{i}", (1.2, 0.08, 0.1), (nx * 0.6, ny * 0.6, 5.05), iron, 0.0, c=c,
                       rot=(0, 0, ang)))
        st = L.extrude_polygon(f"PROP_Lantern_Star_{i}", star_poly(4, 0.42, 0.2, 0.1), 0.05, glow, c,
                               center_depth=True)
        st.location = (nx * 0.61, ny * 0.61, 5.05)
        st.rotation_euler = (0, 0, ang)
        o.append(st)
    o.append(L.cyl("PROP_Lantern_Roof", 1.18, 0.75, (0, 0, 6.6), iron, 4, 0.04, c=c, r2=0.12,
                   rot=(0, 0, math.pi / 4)))
    o.append(sphere("PROP_Lantern_Knob", 0.2, (0, 0, 7.1), P["gold"], c, 12))
    pl = bpy.data.lights.new("PROP_Lantern_Light", "POINT")
    pl.energy = 60; pl.color = (0.4, 0.9, 1.0); pl.shadow_soft_size = 0.5
    lo = bpy.data.objects.new("PROP_Lantern_Light", pl); c.objects.link(lo); lo.location = (0, 0, 5.05)
    return o


# ============================================================ planters (no plants)
def planter(prefix, sx, sy, c):
    M = P["marble"]
    soil = L.flat("MAT_Soil", (0.22, 0.14, 0.09), rough=1.0)
    h = 1.8
    o = [L.box(f"{prefix}_Foot", (sx + 0.3, sy + 0.3, 0.35), (0, 0, 0.175), M, 0.08, c=c),
         L.box(f"{prefix}_Body", (sx, sy, h - 0.7), (0, 0, 0.35 + (h - 0.7) / 2), M, 0.1, c=c),
         L.box(f"{prefix}_GoldBand", (sx + 0.08, sy + 0.08, 0.14), (0, 0, h - 0.42), P["gold"], 0.02, c=c)]
    t = 0.38
    for i, (w, d, x, y) in enumerate(((sx + 0.35, t, 0, -(sy + 0.35) / 2 + t / 2),
                                       (sx + 0.35, t, 0, (sy + 0.35) / 2 - t / 2),
                                       (t, sy + 0.35 - 2 * t, -(sx + 0.35) / 2 + t / 2, 0),
                                       (t, sy + 0.35 - 2 * t, (sx + 0.35) / 2 - t / 2, 0))):
        o.append(L.box(f"{prefix}_Rim_{i}", (w, d, 0.35), (x, y, h - 0.175), M, 0.08, c=c))
    o.append(L.box(f"{prefix}_Soil", (sx + 0.35 - 2 * t + 0.02, sy + 0.35 - 2 * t + 0.02, 0.3), (0, 0, h - 0.3),
                   soil, 0.0, c=c))
    return o


# ============================================================ banners
def prop_events_banner(c):
    red = L.flat("MAT_EventsRed", (0.42, 0.03, 0.07), rough=0.65)
    cream = L.flat("MAT_EventsText", (1.0, 0.93, 0.78), rough=0.4)
    G = P["gold"]
    W, H, notch = 14.0, 3.6, 1.2
    out = [(-W / 2, H / 2), (W / 2, H / 2), (W / 2 - notch, 0), (W / 2, -H / 2), (-W / 2, -H / 2),
           (-W / 2 + notch, 0)]
    i = 0.22
    inn = [(-W / 2 + 0.3, H / 2 - i), (W / 2 - 0.3, H / 2 - i), (W / 2 - notch - 0.2, 0), (W / 2 - 0.3, -H / 2 + i),
           (-W / 2 + 0.3, -H / 2 + i), (-W / 2 + notch + 0.2, 0)]
    trim = L.extrude_polygon("PROP_Events_Trim", out[::-1], 0.14, G, c, bevel=0.03)
    cloth = L.extrude_polygon("PROP_Events_Cloth", inn[::-1], 0.22, red, c, bevel=0.03)
    txt = L.text_mesh("PROP_Events_Text", "EVENTS", size=2.0, extrude=0.06, mat=cream, c=c,
                      loc=(0, -0.17, -0.05), spacing=1.05)
    txt_b = L.text_mesh("PROP_Events_TextBack", "EVENTS", size=2.0, extrude=0.06, mat=cream, c=c,
                        loc=(0, 0.17, -0.05), rot=(math.pi / 2, 0, math.pi), spacing=1.05)
    o = [trim, cloth, txt, txt_b]
    # laurel sprigs: curved stem + paired leaves, both sides, front and back
    for side in (-1, 1):
        for face, fy in (("F", -0.16), ("B", 0.16)):
            cx = side * 4.85
            for k in range(6):
                t = k / 5
                a = math.radians(-70 + 120 * t)
                px = cx + side * 0.75 * math.cos(a) - side * 0.2
                pz = 0.95 * math.sin(a) - 0.1
                for lr in (-1, 1):
                    leaf = sphere(f"PROP_Events_Leaf_{face}{side}_{k}_{lr}", 0.25, (px, fy, pz), G, c, 10)
                    leaf.scale = (0.45, 0.25, 1.0)
                    leaf.rotation_euler = (0, side * (a + lr * 0.55) - math.pi / 2 * side, 0)
                    leaf.location.x += side * lr * 0.13
                    o.append(leaf)
            o.append(L.box(f"PROP_Events_Stem_{face}{side}", (0.08, 0.06, 1.6), (cx + side * 0.5, fy, -0.05), G, 0.0,
                           c=c, rot=(0, side * 0.35, 0)))
    # rod, finials and suspension chains
    rod_z = H / 2 + 0.45
    o.append(L.cyl("PROP_Events_Rod", 0.14, W + 0.8, (0, 0, rod_z), G, 16, 0.03, c=c, rot=(0, math.pi / 2, 0)))
    for s in (-1, 1):
        o.append(sphere(f"PROP_Events_Finial_{s}", 0.3, (s * (W / 2 + 0.55), 0, rod_z), G, c))
        for k in range(4):  # rings attaching cloth to rod
            o.append(L.ring(f"PROP_Events_Clip_{s}_{k}", 0.24, 0.15, 0.1, (s * (1.5 + k * 1.7), 0, rod_z - 0.2), G,
                            c=c))
            o[-1].rotation_euler = (math.pi / 2, 0, 0)
        # suspension chain up to the arches (links)
        for k in range(10):
            lk = L.ring(f"PROP_Events_Chain_{s}_{k}", 0.2, 0.12, 0.08,
                        (s * (W / 2 - 0.4 + k * 0.32), 0, rod_z + 0.4 + k * 0.5), G, verts=12, c=c)
            lk.rotation_euler = (math.pi / 2, 0, math.pi / 2 * (k % 2)) if k % 2 else (0, math.pi / 2, 0)
            lk.scale = (1.0, 1.6, 1.0) if k % 2 == 0 else (1.6, 1.0, 1.0)
            o.append(lk)
    # gentle cloth sag: lean the banner a few degrees like the reference drape
    return o


def prop_star_banner(c):
    """Stand-alone navy star banner + wall bracket (same design as the arch banner)."""
    G = P["gold"]
    w, h1, pd = 2.8, 6.3, 1.15
    outline = [(-w / 2, 0), (w / 2, 0), (w / 2, -h1), (0, -h1 - pd), (-w / 2, -h1)]
    i = 0.17
    inner = [(-w / 2 + i, -0.12), (w / 2 - i, -0.12), (w / 2 - i, -h1 + 0.07), (0, -h1 - pd + 0.36),
             (-w / 2 + i, -h1 + 0.07)]
    top = 8.0
    o = [L.extrude_polygon("PROP_StarBanner_Trim", outline, 0.1, G, c, bevel=0.03),
         L.extrude_polygon("PROP_StarBanner_Cloth", inner, 0.16, P["navy"], c, bevel=0.02)]
    for ob in o:
        ob.location = (0, 0, top)
    sp = star_poly(4, 1.8, 0.55, 0.24)
    # 4 long + 4 short points; shorten the horizontal long points (compass star on the sheet)
    sp = [(x * (1.15 / 1.8) if abs(y) < 0.3 and abs(x) > 1.0 else x, y) for x, y in sp]
    for face, y, rz in (("Front", -0.125, 0), ("Back", 0.125, math.pi)):
        st = L.extrude_polygon(f"PROP_StarBanner_Star{face}", sp, 0.05, P["white"], c, center_depth=False)
        st.location = (0, y, top - 0.12 - h1 * 0.47); st.rotation_euler = (0, 0, rz)
        gm = L.extrude_polygon(f"PROP_StarBanner_Gem{face}", [(0, 0.38), (0.24, 0), (0, -0.38), (-0.24, 0)], 0.05,
                               P["cyan_soft"], c, center_depth=False)
        gm.location = (0, y * 1.25, top - 0.12 - h1 * 0.47); gm.rotation_euler = (0, 0, rz)
        o += [st, gm]
    rod_z = top + 0.12
    o.append(L.cyl("PROP_StarBanner_Rod", 0.11, w + 0.9, (0, 0, rod_z), G, 16, 0.02, c=c, rot=(0, math.pi / 2, 0)))
    for s in (-1, 1):
        o.append(sphere(f"PROP_StarBanner_Finial_{s}", 0.22, (s * (w / 2 + 0.57), 0, rod_z), G, c))
        o.append(L.box(f"PROP_StarBanner_Bracket_{s}", (0.18, 0.55, 0.18), (s * 0.9, 0.3, rod_z), G, 0.03, c=c))
    o.append(L.box("PROP_StarBanner_WallPlate", (2.4, 0.1, 0.4), (0, 0.6, rod_z), G, 0.03, c=c))
    return o


# ============================================================ floors
def prop_road(c):
    """12 x 16 stud road tile (textured cobblestone surface), running toward +Y, two inlaid neon chevrons."""
    W, Lg = 12.0, 16.0
    G = P["gold"]
    o = [L.box("PROP_Road_Bed", (W + 2.0, Lg, 0.8), (0, 0, -0.5), P["marble_dark"], 0.0, c=c),
         L.cobble_surface("PROP_Road_CobbleFloor", -W / 2 + 0.05, W / 2 - 0.05, -Lg / 2, Lg / 2, top=0.0, thick=0.3,
                          c=c)]
    for s in (-1, 1):
        o.append(L.box(f"PROP_Road_GoldEdge_{s}", (0.3, Lg, 0.3), (s * (W / 2 + 0.85), 0, -0.13), G, 0.04, c=c))
        o.append(L.box(f"PROP_Road_Neon_{s}", (0.4, Lg, 0.22), (s * (W / 2 + 0.4), 0, -0.13), P["cyan"], 0.03, c=c))
        o.append(L.box(f"PROP_Road_GoldInner_{s}", (0.22, Lg, 0.3), (s * (W / 2 + 0.05), 0, -0.13), G, 0.04, c=c))
    chevs = []
    for k, yc in enumerate((-4.0, 3.5)):
        cw, th, hh = 7.0, 1.7, 3.0    # width, arm thickness, height of the V (bold, as in the lobby shots)
        poly = [(-cw / 2, yc - hh / 2), (0, yc + hh / 2), (cw / 2, yc - hh / 2), (cw / 2 - th, yc - hh / 2),
                (0, yc + hh / 2 - th * 1.35), (-cw / 2 + th, yc - hh / 2)]
        chevs.append(poly)
        ch = L.extrude_polygon(f"PROP_Road_Chevron_{k}", poly, 0.14, P["cyan"], c, plane="XY", bevel=0.03)
        ch.location.z = -0.04          # neon inlay, 0.03 proud of the textured cobbles
        o.append(ch)
    return o


def prop_floor_marble(c, n=4, t=4.0):
    light = P["marble"]
    lav = L.marble("MAT_MarbleLavender", base=(0.78, 0.72, 0.90), tint=(0.70, 0.64, 0.86), vein=(0.56, 0.5, 0.7))
    o = [L.box("PROP_FloorM_Bed", (n * t, n * t, 0.5), (0, 0, -0.45), P["grout"], 0.0, c=c)]
    for i in range(n):
        for j in range(n):
            m = light if (i + j) % 2 == 0 else lav
            o.append(L.box(f"PROP_FloorM_Tile_{i}{j}", (t - 0.1, t - 0.1, 0.3),
                           ((i - (n - 1) / 2) * t, (j - (n - 1) / 2) * t, -0.15), m, 0.05, c=c))
    return o


def prop_spawn_plaza(c):
    M = P["marble"]
    lav = L.marble("MAT_MarbleLavender", base=(0.78, 0.72, 0.90), tint=(0.70, 0.64, 0.86), vein=(0.56, 0.5, 0.7))
    G = P["gold"]
    o = [L.cyl("PROP_Plaza_Base", 15.6, 1.2, (0, 0, -0.75), P["marble_dark"], 96, 0.12, c=c)]
    o.append(L.ring("PROP_Plaza_OuterCurb", 15.6, 14.6, 0.35, (0, 0, -0.02), M, 96, c=c, bevel=0.06))
    o.append(L.ring("PROP_Plaza_GoldOuter", 14.6, 14.2, 0.3, (0, 0, -0.1), G, 96, c=c))
    # lavender tile band, 24 x 2 sectors
    seg = 24
    for ring_i, (r0, r1) in enumerate(((10.6, 12.4), (12.45, 14.2))):
        for k in range(seg):
            a0 = 2 * math.pi * k / seg + (math.pi / seg if ring_i else 0)
            a1 = a0 + 2 * math.pi / seg - 0.006
            o.append(arc_block(f"PROP_Plaza_Tile_{ring_i}_{k:02d}", r0 + 0.03, r1 - 0.03, -0.3, -0.05, a0, a1,
                               lav if (k + ring_i) % 2 else M, c, 4, 0.04))
    o.append(L.ring("PROP_Plaza_GoldInner", 10.6, 10.3, 0.3, (0, 0, -0.1), G, 96, c=c))
    o.append(L.ring("PROP_Plaza_NeonRing", 10.3, 9.6, 0.24, (0, 0, -0.14), P["cyan"], 96, c=c))
    o.append(L.cyl("PROP_Plaza_InnerDisc", 9.6, 0.28, (0, 0, -0.19), lav, 96, 0.03, c=c))
    # eight-point neon star: neon base polygon + lighter inset top so only an outline glows
    outer = star_poly(4, 8.6, 5.6, 2.9)
    inner = star_poly(4, 7.6, 4.9, 2.45)
    st = L.extrude_polygon("PROP_Plaza_StarNeon", outer, 0.12, P["cyan"], c, plane="XY")
    st.location.z = -0.07
    fill = L.marble("MAT_MarbleStarFill", base=(0.82, 0.86, 0.98), tint=(0.74, 0.80, 0.96), vein=(0.6, 0.62, 0.8))
    sf = L.extrude_polygon("PROP_Plaza_StarFill", inner, 0.12, fill, c, plane="XY")
    sf.location.z = -0.06
    o += [st, sf]
    return o


def prop_steps_curved(c, R=15.6, span=60, n=3):
    M = P["marble"]
    o = []
    a0, a1 = math.radians(-span / 2), math.radians(span / 2)
    rise, run = 0.55, 1.3
    for k in range(n):
        r0 = R + k * run
        top = -k * rise
        o.append(arc_block(f"PROP_Steps_Tread_{k}", r0 - 0.2, r0 + run, top - rise - 0.6, top, a0, a1, M, c, 16, 0.08))
        o.append(arc_block(f"PROP_Steps_Neon_{k}", r0 + run + 0.0, r0 + run + 0.08, top - rise + 0.12, top - 0.12,
                           a0 + 0.01, a1 - 0.01, P["cyan"], c, 16, 0.0))
    for ob in o:
        ob.location.x -= R
        ob.location.z += n * rise
    return o


def prop_stone_post(c):
    """Decorative stone post with bronze lantern finial (arch-sheet design)."""
    M = P["marble"]
    o = [L.box("PROP_StonePost_Body", (1.9, 1.9, 3.25), (0, 0, 1.625), M, 0.1, c=c),
         L.box("PROP_StonePost_Cap", (2.2, 2.2, 0.35), (0, 0, 3.425), M, 0.08, c=c),
         L.box("PROP_StonePost_FinialBase", (1.0, 1.0, 0.22), (0, 0, 3.71), P["bronze"], 0.04, c=c),
         L.box("PROP_StonePost_FinialBody", (0.62, 0.62, 0.5), (0, 0, 4.07), P["gold"], 0.05, c=c),
         L.cyl("PROP_StonePost_FinialRoof", 0.72, 0.5, (0, 0, 4.57), P["gold"], 4, 0.03, c=c, r2=0.08,
               rot=(0, 0, math.pi / 4)),
         L.cyl("PROP_StonePost_FinialKnob", 0.13, 0.22, (0, 0, 4.9), P["gold"], 8, 0.04, c=c)]
    return o


def prop_gold_trim(c):
    G = P["gold"]
    o = [L.box("PROP_GoldTrim_Straight", (8.0, 0.35, 0.3), (0, 0, 0.15), G, 0.05, c=c),
         L.box("PROP_GoldTrim_CornerA", (2.0, 0.35, 0.3), (5.0, 0.825, 0.15), G, 0.05, c=c),
         L.box("PROP_GoldTrim_CornerB", (0.35, 2.0, 0.3), (5.825, 0, 0.15), G, 0.05, c=c),
         L.box("PROP_GoldTrim_Band", (8.0, 0.12, 0.6), (0, 1.8, 0.3), G, 0.03, c=c)]
    pl = L.extrude_polygon("PROP_GoldTrim_Diamond", [(0, 0.6), (0.6, 0), (0, -0.6), (-0.6, 0)], 0.15, G, c, bevel=0.03)
    pl.location = (-6.0, 0, 0.8)
    o.append(pl)
    return o


def prop_neon_strip(c):
    M = P["marble"]
    return [L.box("PROP_NeonStrip_ChannelL", (8.0, 0.4, 0.4), (0, -0.45, -0.2), M, 0.05, c=c),
            L.box("PROP_NeonStrip_ChannelR", (8.0, 0.4, 0.4), (0, 0.45, -0.2), M, 0.05, c=c),
            L.box("PROP_NeonStrip_Bed", (8.0, 0.5, 0.2), (0, 0, -0.3), M, 0.0, c=c),
            L.box("PROP_NeonStrip_Light", (8.0, 0.46, 0.18), (0, 0, -0.12), P["cyan"], 0.03, c=c)]


PROPS = [
    ("BalustradeStraight", prop_balustrade_straight),
    ("BalustradeCorner", prop_balustrade_corner),
    ("BalustradeCurved", prop_balustrade_curved),
    ("LanternPost", prop_lantern_post),
    ("PlanterLong", lambda c: planter("PROP_PlanterLong", 4.6, 2.4, c)),
    ("PlanterSquare", lambda c: planter("PROP_PlanterSq", 3.2, 3.2, c)),
    ("EventsBanner", prop_events_banner),
    ("StarBanner", prop_star_banner),
    ("RoadCobble", prop_road),
    ("FloorMarble", prop_floor_marble),
    ("SpawnPlaza", prop_spawn_plaza),
    ("StepsCurved", prop_steps_curved),
    ("StonePost", prop_stone_post),
    ("GoldTrim", prop_gold_trim),
    ("NeonEdgeStrip", prop_neon_strip),
]


def main(do_render=True, only=None):
    global P
    L.reset()
    P = L.palette()
    root = L.coll("ASSET_06_Props")
    built = {}
    for name, fn in PROPS:
        c = L.coll(f"PROP_{name}", root)
        built[name] = (c, [o for o in fn(c) if o is not None])
        print("built", name, len(built[name][1]))
    L.save_blend("06_props.blend")
    if not do_render:
        return
    L.studio_lights()
    gnd = L.ground(z=-1.36)
    L.setup_render((700, 700), 28)
    items = []
    for name, (c, objs) in built.items():
        if only and name not in only:
            continue
        for oc, _ in built.values():
            oc.hide_render = oc is not c
        mn, mx = L.bounds(objs)
        ctr = (mn + mx) / 2
        size = max(mx - mn) * 1.15
        gnd.location.z = mn.z + 1.36 - 0.01
        pf = os.path.join(L.RENDERS, f"props_{name}_front.png")
        p3 = os.path.join(L.RENDERS, f"props_{name}_3q.png")
        if not (SKIP_EXISTING and os.path.exists(pf)):
            cf = L.camera(f"CAM_{name}_front", ctr + Vector((0, -1, 0)) * size * 4, ctr, ortho=size)
            L.render(cf, pf)
        items.append((f"{name} front", pf))
        if not (SKIP_EXISTING and os.path.exists(p3)):
            d = Vector((-0.8, -1.25, 0.75)).normalized()
            c3 = L.camera(f"CAM_{name}_3q", ctr + d * size * 1.5, ctr, lens=45)
            L.render(c3, p3)
        items.append((f"{name} 3/4", p3))
    half = len(items) // 2 + (len(items) // 2) % 2
    L.contact_sheet(items[:half], os.path.join(L.RENDERS, "props_inspection_sheet_A.png"), cols=4, tile=440,
                    title="ASSET 06 - SECONDARY PROPS (A)  Blender Cycles inspection renders")
    L.contact_sheet(items[half:], os.path.join(L.RENDERS, "props_inspection_sheet_B.png"), cols=4, tile=440,
                    title="ASSET 06 - SECONDARY PROPS (B)  Blender Cycles inspection renders")


if __name__ == "__main__":
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    main("--no-render" not in sys.argv, set(only[0].split(",")) if only else None)
