"""ASSET 4 - Craft shop stall.

Primary reference: dedicated CRAFT SHOP turnaround (front / front 3/4 / side).
Scale from the sheet's front view: ~0.0265 stud/px (540 px plinth -> 14.3 studs).
Structure (distinct from the market shop):
  * marble block plinth with tile seams, marble back wall + thick marble side
    piers built from stacked blocks (with a cornice band at counter height)
  * wooden frame: front posts, top beam, side beams on the pier faces, knee
    braces, gold diamond corner plates
  * blue tonal-striped hip-roof canopy, gold-trimmed crenellated valance,
    ridge beam with end blocks
  * blue CRAFT SHOP sign in a gold chamfered frame with bolts and 3D text
  * plank counter, wall shelves (books + scrolls), hanging hammer + pickaxe,
    glowing crystal cluster, anvil on a gold-trimmed block with a cyan rune,
    two potions, X-braced crate, two hanging lanterns.
Run:  python build_04_craft_shop.py [--no-render]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
import lobbylib as L

random.seed(4)

# ---------------------------------------------------------------- dimensions (studs)
PL_X = 7.15                     # plinth half width
PL_Y = (-5.2, 4.3)              # plinth depth range (front, back)
FLOOR = 1.0                     # plinth top
PIER_X = (5.2, 6.8)             # |x| range of side piers
PIER_Y = (-1.8, 4.0)
BACK_Y = (3.2, 4.0)             # back wall thickness range
WALL_TOP = 10.4
POST_X, POST_Y, POST_W = 6.0, -2.4, 0.8
BEAM_Z = (10.4, 11.0)
COUNTER_X, COUNTER_Y, COUNTER_TOP = 5.5, (-2.9, -1.1), 4.7
EAVE_Z, RIDGE_Z = 10.95, 13.9
CAN_X, CAN_Y = 7.4, (-3.7, 4.7)
RIDGE_X, RIDGE_Y = 4.6, 0.6


def lathe(name, prof, segs, mat, c, loc, smooth=True):
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
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.from_bmesh(name, bm, mat, c)
    ob.location = loc
    for p in ob.data.polygons:
        p.use_smooth = smooth
    return ob


def crystal(name, r, h, tip, mat, c, loc, rot=(0, 0, 0), sides=6):
    """Hexagonal prism with pointed tip, slightly narrower base."""
    bm = bmesh.new()
    bot = [bm.verts.new((0.8 * r * math.cos(2 * math.pi * i / sides), 0.8 * r * math.sin(2 * math.pi * i / sides), 0))
           for i in range(sides)]
    top = [bm.verts.new((r * math.cos(2 * math.pi * i / sides), r * math.sin(2 * math.pi * i / sides), h))
           for i in range(sides)]
    apex = bm.verts.new((0, 0, h + tip))
    bm.faces.new(bot[::-1])
    for i in range(sides):
        j = (i + 1) % sides
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
        bm.faces.new((top[i], top[j], apex))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.from_bmesh(name, bm, mat, c)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


def chamfer_rect(w, h, ch):
    x, y = w / 2, h / 2
    return [(-x + ch, -y), (x - ch, -y), (x, -y + ch), (x, y - ch), (x - ch, y), (-x + ch, y), (-x, y - ch), (-x, -y + ch)]


def crenel_outline(length, base, tab, tab_w=0.8, pitch=1.6):
    pts = [(0, 0), (length, 0), (length, -base)]
    n = int((length - 0.2) // pitch)
    start = (length - (n - 1) * pitch) / 2
    centers = [start + k * pitch for k in range(n)][::-1]
    for u in centers:
        pts += [(u + tab_w / 2, -base), (u + tab_w / 2, -tab), (u - tab_w / 2, -tab), (u - tab_w / 2, -base)]
    pts.append((0, -base))
    return pts


def build(P, root):
    C = {k: L.coll(f"CRF_{k}", root) for k in ("Masonry", "Frame", "Canopy", "Sign", "Counter", "Props", "Lanterns")}
    M = P["marble"]
    objs = []
    wood_frame = L.wood("MAT_WoodFrame", light=(0.62, 0.34, 0.13), dark=(0.45, 0.22, 0.08))
    wood_plank = L.wood("MAT_WoodPlank", light=(0.70, 0.42, 0.18), dark=(0.52, 0.29, 0.11), axis="Z")
    wood_crate = L.wood("MAT_WoodCrate", light=(0.92, 0.62, 0.26), dark=(0.78, 0.48, 0.18))
    iron = L.flat("MAT_Iron", (0.10, 0.11, 0.15), rough=0.35, metal=0.65)
    canvas = L.stripes("MAT_CanopyBlue", (0.06, 0.14, 0.62), (0.03, 0.08, 0.42), width=1.05, axis=0, offset=0.52)
    canvas_v = L.flat("MAT_CanopyBlueEdge", (0.06, 0.14, 0.62), rough=0.55)
    sign_blue = L.flat("MAT_SignBlue", (0.035, 0.075, 0.40), rough=0.45)
    paper = L.flat("MAT_Parchment", (0.93, 0.80, 0.58), rough=0.7)
    books = L.varied("MAT_Books", [(0.08, 0.16, 0.55), (0.30, 0.12, 0.55), (0.12, 0.22, 0.70), (0.45, 0.20, 0.65)],
                     rough=0.6)
    lamp = L.emissive("MAT_LanternGlow", (1.0, 0.55, 0.12), 1.6, base=(1.0, 0.72, 0.30))
    purple = L.emissive("MAT_CrystalPurple", (0.30, 0.06, 1.0), 0.7, base=(0.30, 0.10, 0.80))
    purple_glow = L.emissive("MAT_PurpleGlow", (0.45, 0.15, 1.0), 1.4, base=(0.5, 0.3, 1.0))
    pot_blue = L.emissive("MAT_PotionBlue", (0.05, 0.55, 1.0), 0.8, base=(0.15, 0.62, 1.0))
    pot_pink = L.emissive("MAT_PotionPink", (1.0, 0.18, 0.65), 0.8, base=(1.0, 0.35, 0.75))
    cork = L.flat("MAT_Cork", (0.62, 0.42, 0.24), rough=0.8)

    # ------------------------------------------------ plinth tiles (6 x 4)
    nx, ny = 6, 4
    tw, td = 2 * PL_X / nx, (PL_Y[1] - PL_Y[0]) / ny
    for i in range(nx):
        for j in range(ny):
            objs.append(L.box(f"CRF_PlinthTile_{i}{j}", (tw - 0.04, td - 0.04, FLOOR),
                              (-PL_X + tw * (i + 0.5), PL_Y[0] + td * (j + 0.5), FLOOR / 2), M, 0.1, c=C["Masonry"]))

    # ------------------------------------------------ back wall (staggered blocks)
    row_h = (WALL_TOP - FLOOR) / 6
    bw = 2.6
    for r in range(6):
        z0 = FLOOR + r * row_h
        x = -PIER_X[0] - (bw / 2 if r % 2 else 0)
        k = 0
        while x < PIER_X[0] - 0.01:
            xa, xb = max(x, -PIER_X[0]), min(x + bw, PIER_X[0])
            objs.append(L.box(f"CRF_BackWall_{r}_{k}", (xb - xa - 0.03, BACK_Y[1] - BACK_Y[0], row_h - 0.03),
                              ((xa + xb) / 2, sum(BACK_Y) / 2, z0 + row_h / 2), M, 0.07, c=C["Masonry"]))
            x += bw; k += 1

    # ------------------------------------------------ side piers (two blocks deep, staggered rows)
    pw = PIER_X[1] - PIER_X[0]
    for s in (-1, 1):
        px = s * sum(PIER_X) / 2
        for r in range(6):
            z0 = FLOOR + r * row_h
            split = PIER_Y[0] + (2.6 if r % 2 else 3.4)
            for k, (ya, yb) in enumerate(((PIER_Y[0], split), (split, PIER_Y[1]))):
                objs.append(L.box(f"CRF_Pier{'LR'[s > 0]}_{r}_{k}", (pw - 0.03, yb - ya - 0.03, row_h - 0.03),
                                  (px, (ya + yb) / 2, z0 + row_h / 2), M, 0.07, c=C["Masonry"]))
        # cornice band at counter height
        objs.append(L.box(f"CRF_PierBand{'LR'[s > 0]}", (pw + 0.3, PIER_Y[1] - PIER_Y[0] + 0.3, 0.35),
                          (px, sum(PIER_Y) / 2 - 0.0, COUNTER_TOP - 0.1), P["marble_dark"], 0.08, c=C["Masonry"]))

    # ------------------------------------------------ wooden frame
    for s in (-1, 1):
        t = "LR"[s > 0]
        objs.append(L.box(f"CRF_Post{t}", (POST_W, POST_W, BEAM_Z[0] - FLOOR),
                          (s * POST_X, POST_Y, (FLOOR + BEAM_Z[0]) / 2), wood_frame, 0.08, c=C["Frame"]))
        # side top beam over the pier
        objs.append(L.box(f"CRF_SideTopBeam{t}", (0.8, PL_Y[1] - POST_Y + 0.4 - 0.3, BEAM_Z[1] - BEAM_Z[0]),
                          (s * POST_X, (POST_Y - 0.4 + PL_Y[1] - 0.3) / 2, sum(BEAM_Z) / 2), wood_frame, 0.08,
                          c=C["Frame"]))
        # side mid beam on the pier outer face
        objs.append(L.box(f"CRF_SideMidBeam{t}", (0.55, PL_Y[1] - POST_Y + 0.1, 0.6),
                          (s * (PIER_X[1] - 0.12), (POST_Y - 0.4 + PL_Y[1] - 0.3) / 2, COUNTER_TOP + 0.45),
                          wood_frame, 0.07, c=C["Frame"]))
        # vertical post on the pier outer face + diagonal knee brace (side view)
        objs.append(L.box(f"CRF_SidePost{t}", (0.5, 0.7, BEAM_Z[0] - FLOOR),
                          (s * (PIER_X[1] + 0.1), 1.7, (FLOOR + BEAM_Z[0]) / 2), wood_frame, 0.07, c=C["Frame"]))
        a, b = Vector((POST_Y + 0.2, 9.9)), Vector((1.5, 6.6))
        d = b - a
        objs.append(L.box(f"CRF_SideBrace{t}", (0.45, d.length, 0.5),
                          (s * (PIER_X[1] + 0.12), (a.x + b.x) / 2, (a.y + b.y) / 2), wood_frame, 0.06, c=C["Frame"],
                          rot=(math.atan2(d.y, d.x), 0, 0)))
        # front knee braces under the top beam
        objs.append(L.box(f"CRF_FrontBrace{t}", (1.5, 0.45, 0.4),
                          (s * (POST_X - 0.75), POST_Y, BEAM_Z[0] - 0.55), wood_frame, 0.05, c=C["Frame"],
                          rot=(0, s * math.radians(40), 0)))
        # gold diamond plates (post outer face, side post / brace junction)
        for nm, loc, rot in ((f"CRF_GoldPlatePost{t}", (s * (POST_X + POST_W / 2 + 0.03), POST_Y, 7.0), (0, math.pi / 4, 0)),
                             (f"CRF_GoldPlateSide{t}", (s * (PIER_X[1] + 0.38), 1.7, 6.9), (math.pi / 4, 0, 0)),
                             (f"CRF_GoldPlateBeam{t}", (s * (PIER_X[1] + 0.38), 1.7, COUNTER_TOP + 0.45), (math.pi / 4, 0, 0))):
            sz = (0.08, 0.55, 0.55) if "Side" in nm or "Beam" in nm else (0.55, 0.08, 0.55)
            if "Post" in nm:
                sz = (0.08, 0.55, 0.55)
            objs.append(L.box(nm, sz, loc, P["gold"], 0.03, c=C["Frame"], rot=rot))
    objs.append(L.box("CRF_FrontTopBeam", (2 * POST_X + 0.9, 0.85, BEAM_Z[1] - BEAM_Z[0]),
                      (0, POST_Y, sum(BEAM_Z) / 2), wood_frame, 0.08, c=C["Frame"]))
    objs.append(L.box("CRF_BackTopBeam", (2 * POST_X + 0.9, 0.8, BEAM_Z[1] - BEAM_Z[0]),
                      (0, PL_Y[1] - 0.7, sum(BEAM_Z) / 2), wood_frame, 0.08, c=C["Frame"]))

    # ------------------------------------------------ canopy (hip roof shell)
    ze, zr = EAVE_Z, RIDGE_Z
    y0, y1 = CAN_Y
    v = [(-CAN_X, y0, ze), (CAN_X, y0, ze), (CAN_X, y1, ze), (-CAN_X, y1, ze),
         (-RIDGE_X, RIDGE_Y, zr), (RIDGE_X, RIDGE_Y, zr)]
    f = [(0, 1, 5, 4), (1, 2, 5), (2, 3, 4, 5), (3, 0, 4)]
    can = L.mesh_obj("CRF_Canopy", v, f, canvas, C["Canopy"])
    so = can.modifiers.new("Solidify", "SOLIDIFY"); so.thickness = 0.32; so.offset = -1
    L.add_bevel(can, 0.08, 2, angle=20)
    objs.append(can)
    # ridge beam + end blocks
    objs.append(L.box("CRF_RidgeBeam", (2 * RIDGE_X, 0.65, 0.6), (0, RIDGE_Y, zr + 0.22), wood_frame, 0.08,
                      c=C["Canopy"]))
    for s in (-1, 1):
        objs.append(L.box(f"CRF_RidgeEnd{'LR'[s > 0]}", (0.95, 0.95, 0.95), (s * RIDGE_X, RIDGE_Y, zr + 0.25),
                          wood_frame, 0.1, c=C["Canopy"]))
    # crenellated valance with gold border, around the four eave edges
    edges = [((-CAN_X, y0), 0.0, 2 * CAN_X), ((CAN_X, y0), math.pi / 2, y1 - y0),
             ((CAN_X, y1), math.pi, 2 * CAN_X), ((-CAN_X, y1), -math.pi / 2, y1 - y0)]
    for i, ((ex, ey), rz, ln) in enumerate(edges):
        g = L.extrude_polygon(f"CRF_ValanceGold_{i}", crenel_outline(ln, 0.55, 0.95), 0.14, P["gold"], C["Canopy"],
                              bevel=0.03)
        inner = [(px, py) for px, py in crenel_outline(ln - 0.0, 0.43, 0.83, tab_w=0.56)]
        inner = [(min(max(px, 0.12), ln - 0.12), min(py, -0.0) if py < 0 else -0.0) for px, py in inner]
        bl = L.extrude_polygon(f"CRF_ValanceBlue_{i}", inner, 0.2, canvas_v, C["Canopy"])
        for ob in (g, bl):
            ob.location = (ex, ey, ze + 0.02)
            ob.rotation_euler = (0, 0, rz)
        objs += [g, bl]
    # gold eave cap strip along the top of the valance
    for i, ((ex, ey), rz, ln) in enumerate(edges):
        cap = L.box(f"CRF_EaveCap_{i}", (ln + 0.1, 0.3, 0.16), (0, 0, 0), P["gold"], 0.04, c=C["Canopy"])
        dvec = Vector((math.cos(rz), math.sin(rz), 0))
        cap.location = Vector((ex, ey, ze + 0.06)) + dvec * (ln / 2)
        cap.rotation_euler = (0, 0, rz)
        objs.append(cap)

    # ------------------------------------------------ sign
    sz, sy = 11.85, CAN_Y[0] - 0.25
    gold_fr = L.extrude_polygon("CRF_SignFrame", chamfer_rect(8.2, 3.45, 0.45), 0.35, P["gold"], C["Sign"], bevel=0.06)
    panel = L.extrude_polygon("CRF_SignPanel", chamfer_rect(7.5, 2.8, 0.32), 0.45, sign_blue, C["Sign"], bevel=0.04)
    for ob in (gold_fr, panel):
        ob.location = (0, sy, sz)
    txt = L.text_mesh("CRF_SignText", "CRAFT\nSHOP", size=1.72, extrude=0.06, font=L.FONT_BLACK, mat=P["white"],
                      c=C["Sign"], loc=(0, sy - 0.27, sz - 0.08), line_spacing=0.78)
    objs += [gold_fr, panel, txt]
    for bx in (-3.75, 3.75):
        for bz in (-1.38, 1.38):
            objs.append(L.cyl(f"CRF_SignBolt_{bx}_{bz}", 0.13, 0.12, (bx, sy - 0.2, sz + bz), P["gold"], 10, 0.03,
                              c=C["Sign"], rot=(math.pi / 2, 0, 0)))
    # ------------------------------------------------ counter
    cy0, cy1 = COUNTER_Y
    ch = COUNTER_TOP - FLOOR - 0.3
    objs.append(L.box("CRF_CounterTop", (2 * COUNTER_X + 0.3, cy1 - cy0 + 0.35, 0.3),
                      (0, (cy0 + cy1) / 2 - 0.12, COUNTER_TOP - 0.15), wood_frame, 0.07, c=C["Counter"]))
    objs.append(L.box("CRF_CounterCore", (2 * COUNTER_X - 0.2, cy1 - cy0 - 0.3, ch),
                      (0, (cy0 + cy1) / 2 + 0.1, FLOOR + ch / 2), wood_plank, 0.05, c=C["Counter"]))
    objs.append(L.box("CRF_CounterBaseRail", (2 * COUNTER_X, 0.3, 0.45), (0, cy0 + 0.1, FLOOR + 0.225), wood_frame,
                      0.06, c=C["Counter"]))
    objs.append(L.box("CRF_CounterTopRail", (2 * COUNTER_X, 0.3, 0.4), (0, cy0 + 0.1, COUNTER_TOP - 0.5), wood_frame,
                      0.06, c=C["Counter"]))
    for s in (-1, 1):
        objs.append(L.box(f"CRF_CounterStile{'LR'[s > 0]}", (0.45, 0.32, ch), (s * (COUNTER_X - 0.225), cy0 + 0.1,
                                                                               FLOOR + ch / 2), wood_frame, 0.06,
                          c=C["Counter"]))
    n_pl = 12
    span = 2 * COUNTER_X - 0.9
    for k in range(n_pl):
        x = -span / 2 + span * (k + 0.5) / n_pl
        objs.append(L.box(f"CRF_CounterPlank_{k:02d}", (span / n_pl - 0.07, 0.12, ch - 0.85),
                          (x, cy0 + 0.17, FLOOR + 0.45 + (ch - 0.85) / 2), wood_plank, 0.03, c=C["Counter"]))

    # ------------------------------------------------ wall shelves, books, scrolls
    wy = BACK_Y[0]
    for k, zz in enumerate((8.35, 6.55)):
        objs.append(L.box(f"CRF_Shelf_{k}", (3.1, 0.85, 0.18), (-2.2, wy - 0.43, zz), wood_frame, 0.04, c=C["Props"]))
        for bx in (-3.4, -1.0):
            objs.append(L.box(f"CRF_ShelfBracket_{k}_{bx}", (0.18, 0.6, 0.45), (bx, wy - 0.3, zz - 0.3), wood_frame,
                              0.03, c=C["Props"]))
    x = -3.55
    for k, (w, h) in enumerate(((0.32, 1.25), (0.26, 1.1), (0.34, 1.32), (0.28, 1.15), (0.3, 1.2))):
        b = L.box(f"CRF_Book_{k}", (w, 0.62, h), (x + w / 2, wy - 0.42, 6.64 + h / 2), books, 0.03, c=C["Props"])
        objs.append(b)
        x += w + 0.03
    # lying book on lower shelf
    objs.append(L.box("CRF_BookFlat", (0.95, 0.65, 0.22), (-1.6, wy - 0.42, 6.75), books, 0.03, c=C["Props"]))
    # scroll pile on the upper shelf (pyramid of rolls lying along X)
    for k, (sx, dz) in enumerate(((-3.0, 0.0), (-2.1, 0.0), (-2.55, 0.46))):
        sc = L.cyl(f"CRF_Scroll_{k}", 0.25, 0.85, (sx, wy - 0.45, 8.69 + dz), paper, 14, 0.05, c=C["Props"],
                   rot=(0, math.pi / 2, 0))
        objs.append(sc)
    # hammer
    hx = 0.75
    objs.append(L.cyl("CRF_HammerPeg", 0.08, 0.5, (hx, wy - 0.25, 9.25), wood_frame, 8, 0.02, c=C["Props"],
                      rot=(math.pi / 2, 0, 0)))
    objs.append(L.cyl("CRF_HammerHandle", 0.11, 2.3, (hx, wy - 0.35, 7.55), wood_frame, 10, 0.03, c=C["Props"]))
    objs.append(L.box("CRF_HammerHead", (1.2, 0.48, 0.5), (hx, wy - 0.35, 8.82), iron, 0.06, c=C["Props"]))
    # pickaxe
    px_ = 2.65
    objs.append(L.cyl("CRF_PickHandle", 0.11, 2.4, (px_, wy - 0.35, 7.5), wood_frame, 10, 0.03, c=C["Props"]))
    R1, R2, cz = 1.35, 1.0, 8.75 - 1.15
    arc = []
    angs = [math.radians(a) for a in range(-55, 56, 10)]
    arc += [(R1 * math.sin(a), R1 * math.cos(a)) for a in angs]
    arc.append((1.2 * math.sin(math.radians(68)), 1.2 * math.cos(math.radians(68))))
    arc += [(R2 * math.sin(a), R2 * math.cos(a)) for a in reversed(angs)]
    arc.append((1.2 * math.sin(math.radians(-68)), 1.2 * math.cos(math.radians(-68))))
    pick = L.extrude_polygon("CRF_PickHead", arc[::-1], 0.3, iron, C["Props"], bevel=0.04)
    pick.location = (px_, wy - 0.35, cz)
    objs.append(pick)
    objs.append(L.cyl("CRF_PickPeg", 0.08, 0.5, (px_, wy - 0.25, 9.0), wood_frame, 8, 0.02, c=C["Props"],
                      rot=(math.pi / 2, 0, 0)))

    # ------------------------------------------------ counter props
    ty = (cy0 + cy1) / 2
    flask = [(0.0, 0.0), (0.28, 0.02), (0.40, 0.18), (0.43, 0.38), (0.36, 0.58), (0.2, 0.72), (0.13, 0.78),
             (0.13, 1.0), (0.17, 1.04), (0.0, 1.04)]
    for k, (fx, m) in enumerate(((-4.0, pot_blue), (-2.95, pot_pink))):
        objs.append(lathe(f"CRF_Potion_{k}", flask, 20, m, C["Props"], (fx, ty, COUNTER_TOP)))
        objs.append(L.cyl(f"CRF_PotionCork_{k}", 0.12, 0.22, (fx, ty, COUNTER_TOP + 1.12), cork, 10, 0.03,
                          c=C["Props"]))
    # crystal cluster on glowing base
    cx = -0.6
    objs.append(L.cyl("CRF_CrystalBase", 1.25, 0.18, (cx, ty, COUNTER_TOP + 0.09), P["marble_dark"], 32, 0.05,
                      c=C["Props"]))
    objs.append(L.ring("CRF_CrystalBaseGlow", 1.3, 1.05, 0.1, (cx, ty, COUNTER_TOP + 0.2), purple_glow, 40,
                       c=C["Props"]))
    for k, (dx, dy, r, h, tip, tilt, yaw) in enumerate((
            (0.0, 0.0, 0.42, 1.9, 0.75, 0.0, 0.0),
            (-0.6, -0.1, 0.3, 1.1, 0.5, -0.45, 0.0),
            (0.6, -0.05, 0.3, 1.2, 0.5, 0.45, 0.0),
            (-0.95, 0.15, 0.2, 0.6, 0.35, -0.75, 0.2),
            (0.95, 0.15, 0.2, 0.65, 0.35, 0.75, -0.2),
            (0.25, 0.45, 0.24, 0.9, 0.4, 0.25, 0.6))):
        objs.append(crystal(f"CRF_Crystal_{k}", r, h, tip, purple, C["Props"], (cx + dx, ty + dy, COUNTER_TOP + 0.15),
                            rot=(0, tilt, yaw)))
    # anvil on gold-trimmed block
    ax = 2.95
    objs.append(L.box("CRF_AnvilBlock", (2.5, 1.4, 0.6), (ax, ty, COUNTER_TOP + 0.3), wood_crate, 0.06, c=C["Props"]))
    for zz in (0.06, 0.54):
        objs.append(L.box(f"CRF_AnvilBlockTrim_{zz}", (2.58, 1.48, 0.12), (ax, ty, COUNTER_TOP + zz), P["gold"], 0.03,
                          c=C["Props"]))
    anvil_pts = [(-0.85, 0), (0.85, 0), (0.85, 0.2), (0.5, 0.35), (0.42, 0.72), (1.25, 0.82), (1.35, 1.25),
                 (-0.75, 1.25), (-1.65, 1.12), (-0.78, 0.92), (-0.42, 0.72), (-0.5, 0.35), (-0.85, 0.2)]
    anv = L.extrude_polygon("CRF_Anvil", anvil_pts, 0.95, iron, C["Props"], bevel=0.06)
    anv.location = (ax + 0.1, ty, COUNTER_TOP + 0.6)
    objs.append(anv)
    rune = [(0, 0.26), (0.26, 0), (0, -0.26), (-0.26, 0)]
    r1 = L.extrude_polygon("CRF_AnvilRune", rune, 0.05, P["cyan"], C["Props"], center_depth=False)
    r1.location = (ax + 0.1, ty - 0.5, COUNTER_TOP + 0.6 + 1.0)
    objs.append(r1)
    objs.append(L.ring("CRF_AnvilRuneRing", 0.38, 0.32, 0.05, (ax + 0.1, ty - 0.49, COUNTER_TOP + 1.6), P["cyan"], 24,
                       c=C["Props"]))
    objs[-1].rotation_euler = (math.pi / 2, 0, 0)

    # ------------------------------------------------ crate (X braced)
    cw, cd, chh = 3.1, 2.2, 2.9
    ccx, ccy = 4.55, PL_Y[0] + 0.15 + cd / 2
    ccz = FLOOR + chh / 2
    objs.append(L.box("CRF_CrateCore", (cw - 0.1, cd - 0.1, chh - 0.1), (ccx, ccy, ccz), wood_crate, 0.05,
                      c=C["Props"]))
    t = 0.32
    for sx in (-1, 1):
        for sy_ in (-1, 1):
            objs.append(L.box(f"CRF_CrateEdgeV_{sx}{sy_}", (t, t, chh), (ccx + sx * (cw / 2 - t / 2),
                                                                         ccy + sy_ * (cd / 2 - t / 2), ccz),
                              wood_frame, 0.05, c=C["Props"]))
    for sz_ in (-1, 1):
        for sy_ in (-1, 1):
            objs.append(L.box(f"CRF_CrateEdgeX_{sz_}{sy_}", (cw, t, t), (ccx, ccy + sy_ * (cd / 2 - t / 2),
                                                                         ccz + sz_ * (chh / 2 - t / 2)),
                              wood_frame, 0.05, c=C["Props"]))
        for sx in (-1, 1):
            objs.append(L.box(f"CRF_CrateEdgeY_{sz_}{sx}", (t, cd, t), (ccx + sx * (cw / 2 - t / 2), ccy,
                                                                        ccz + sz_ * (chh / 2 - t / 2)),
                              wood_frame, 0.05, c=C["Props"]))
    # X braces on front and both sides
    iw, ih = cw - 2 * t, chh - 2 * t
    ang = math.atan2(ih, iw)
    for s in (-1, 1):
        objs.append(L.box(f"CRF_CrateXFront_{s}", (math.hypot(iw, ih) - 0.55, 0.2, 0.3),
                          (ccx, ccy - cd / 2 + 0.02, ccz), wood_frame, 0.04, c=C["Props"], rot=(0, s * ang, 0)))
        objs.append(L.box(f"CRF_CrateXBack_{s}", (math.hypot(iw, ih) - 0.55, 0.2, 0.3),
                          (ccx, ccy + cd / 2 - 0.02, ccz), wood_frame, 0.04, c=C["Props"], rot=(0, s * ang, 0)))
    iwd = cd - 2 * t
    angd = math.atan2(ih, iwd)
    for sx in (-1, 1):
        for s in (-1, 1):
            objs.append(L.box(f"CRF_CrateXSide_{sx}{s}", (0.2, math.hypot(iwd, ih) - 0.55, 0.3),
                              (ccx + sx * (cw / 2 - 0.02), ccy, ccz), wood_frame, 0.04, c=C["Props"],
                              rot=(s * angd, 0, 0)))

    # ------------------------------------------------ lanterns on bracket arms
    for s in (-1, 1):
        t_ = "LR"[s > 0]
        lx, ly = s * POST_X, POST_Y - 1.05
        objs.append(L.box(f"CRF_LanternArm{t_}", (0.16, 1.0, 0.16), (lx, POST_Y - 0.85, 10.05), iron, 0.03,
                          c=C["Lanterns"]))
        objs.append(L.box(f"CRF_LanternArmBrace{t_}", (0.12, 0.7, 0.12), (lx, POST_Y - 0.6, 9.75), iron, 0.02,
                          c=C["Lanterns"], rot=(math.radians(-40), 0, 0)))
        objs.append(L.cyl(f"CRF_LanternHook{t_}", 0.05, 0.4, (lx, ly, 9.82), iron, 6, 0.0, c=C["Lanterns"]))
        z0 = 7.55
        objs.append(L.box(f"CRF_LanternBase{t_}", (1.0, 1.0, 0.22), (lx, ly, z0 + 0.11), P["gold"], 0.05,
                          c=C["Lanterns"]))
        objs.append(L.box(f"CRF_LanternGlass{t_}", (0.72, 0.72, 1.15), (lx, ly, z0 + 0.22 + 0.575), lamp, 0.03,
                          c=C["Lanterns"]))
        for cx_ in (-1, 1):
            for cy_ in (-1, 1):
                objs.append(L.box(f"CRF_LanternBar{t_}_{cx_}{cy_}", (0.14, 0.14, 1.2),
                                  (lx + cx_ * 0.38, ly + cy_ * 0.38, z0 + 0.82), P["gold"], 0.02, c=C["Lanterns"]))
        objs.append(L.box(f"CRF_LanternRim{t_}", (0.98, 0.98, 0.14), (lx, ly, z0 + 1.42), P["gold"], 0.03,
                          c=C["Lanterns"]))
        objs.append(L.cyl(f"CRF_LanternRoof{t_}", 0.78, 0.42, (lx, ly, z0 + 1.7), P["gold"], 4, 0.03,
                          c=C["Lanterns"], r2=0.12, rot=(0, 0, math.pi / 4)))
        objs.append(L.ring(f"CRF_LanternRing{t_}", 0.16, 0.09, 0.06, (lx, ly, z0 + 2.02), iron, 12, c=C["Lanterns"]))
        objs[-1].rotation_euler = (math.pi / 2, 0, 0)
    return objs


def main(do_render=True):
    L.reset()
    P = L.palette()
    root = L.coll("ASSET_04_CraftShop")
    objs = build(P, root)
    L.empty("CRF_Origin", (0, 0, 0), root)
    L.save_blend("04_craft_shop.blend")
    if not do_render:
        return
    L.studio_lights()
    L.ground(z=0.0)
    items = L.inspection_set("craft", objs, res=800, samples=28, three_q=(0.9, -1.35, 0.5), detail=[
        ("detail_sign_canopy", (6.0, -16.0, 13.5), (0.0, -3.0, 11.8), 45),
        ("detail_counter_props", (2.0, -12.5, 7.0), (0.0, -1.0, 6.2), 40),
    ])
    # beauty at the sheet's front 3/4 angle (camera front-right, slightly above)
    L.clear_rig()
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT":
            bpy.data.objects.remove(ob)
    L.beauty_lights()
    L.setup_render((900, 900), 32)
    c = L.camera("CAM_beauty_3q", (17.0, -27.0, 13.0), (0.6, 0.0, 6.6), lens=40)
    items.append(("beauty_front_3q", L.render(c, os.path.join(L.RENDERS, "craft_beauty_3q.png"))))
    L.contact_sheet(items, os.path.join(L.RENDERS, "craft_inspection_sheet.png"), cols=4, tile=480,
                    title="ASSET 04 - CRAFT SHOP (Blender Cycles inspection renders)")


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
