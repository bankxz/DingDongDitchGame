"""ASSET 3 - Market shop stall.

Primary reference: dedicated MARKET SHOP turnaround (front / front 3/4 / side + detail crops).
Scale derived from the front view: ~0.027 stud per sheet pixel (overall height ~14 studs).
Layout: front faces -Y.  Four marble post bases, wooden posts (front short, back tall up to
the ridge beam), lean-to striped canopy sloping toward the front with hip side flaps, rolled
eave and scalloped valance, gold-framed maroon sign, X-braced counter, back plank wall with
two shelves, merchandise, potion row, lanterns, side crates.
Run:  python build_03_market_shop.py [--no-render]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
import lobbylib as L

random.seed(3)

# ---------------------------------------------------------------- dimensions (studs)
POST_X = 4.9            # post centre |x|
FRONT_Y, BACK_Y = -2.1, 2.1
BASE_TOP = 3.4
POST_W = 1.2
FRONT_POST_TOP = 9.6
RIDGE_Z = 13.5          # underside of ridge beam
RIDGE_Y = 2.3
RIDGE_HALF = 5.3        # canopy top edge half-width
EAVE_Y, EAVE_Z = -2.2, 10.75     # UPPER tier front edge (rolled), just above the sign
EAVE_HALF = 7.0
STRIPE = 1.4            # 10 stripes across the eave
# LOWER tier (sheet: a second, flatter striped awning projecting from under the upper one;
# every stripe curls over a rounded fold and hangs as a U-shaped tab)
LOW_Y0, LOW_Z0 = -1.9, 10.15
LOW_Y1, LOW_Z1 = -4.7, 9.0
FOLD_R = 0.34
TAB_H = 1.3
COUNTER_TOP = 3.7
SHELF_Z = 5.75
SHELF2_Z = 4.55
WALL_Y = 1.75
SIGN_Y = -4.1
SIGN_Z = 10.75
SIGN_W, SIGN_H = 8.0, 3.2


def mats():
    M = dict(L.palette())
    M["woodV"] = L.wood("MAT_WoodPost", light=(0.44, 0.20, 0.065), dark=(0.29, 0.12, 0.035), axis="Z")
    M["woodH"] = L.wood("MAT_WoodBeam", light=(0.44, 0.20, 0.065), dark=(0.29, 0.12, 0.035), axis="X")
    M["woodDark"] = L.wood("MAT_WoodBackWall", light=(0.30, 0.14, 0.05), dark=(0.19, 0.08, 0.03), axis="Z")
    M["woodPanel"] = L.wood("MAT_WoodPanel", light=(0.40, 0.18, 0.06), dark=(0.26, 0.11, 0.03), axis="Z")
    M["crate"] = L.wood("MAT_WoodCrate", light=(0.56, 0.30, 0.09), dark=(0.40, 0.19, 0.05), axis="X")
    M["crateV"] = L.wood("MAT_WoodCrateV", light=(0.56, 0.30, 0.09), dark=(0.40, 0.19, 0.05), axis="Z")
    M["red"] = L.flat("MAT_AwningRed", (0.72, 0.04, 0.17), rough=0.6)
    M["cream"] = L.flat("MAT_AwningWhite", (0.95, 0.92, 0.93), rough=0.6)
    M["maroon"] = L.flat("MAT_SignMaroon", (0.33, 0.03, 0.07), rough=0.55)
    M["signtext"] = L.flat("MAT_SignText", (1.0, 0.84, 0.48), rough=0.35, metal=0.3)
    M["iron"] = L.flat("MAT_LanternIron", (0.25, 0.17, 0.10), rough=0.5, metal=0.6)
    M["lampglow"] = L.emissive("MAT_LanternGlow", (1.0, 0.70, 0.25), 6.0, base=(1.0, 0.85, 0.5))
    M["crystal"] = L.glass_emissive("MAT_CrystalPurple", (0.30, 0.06, 1.0), 0.8, 1.0)
    M["paper"] = L.flat("MAT_Parchment", (0.93, 0.84, 0.64), rough=0.7)
    M["cork"] = L.flat("MAT_Cork", (0.62, 0.42, 0.24), rough=0.8)
    M["pages"] = L.flat("MAT_BookPages", (0.95, 0.90, 0.78), rough=0.8)
    for k, c in {"bookNavy": (0.07, 0.13, 0.42), "bookTeal": (0.08, 0.26, 0.34), "bookRed": (0.55, 0.06, 0.08),
                 "bookBlue": (0.12, 0.25, 0.55)}.items():
        M[k] = L.flat("MAT_" + k, c, rough=0.6)
    for k, c in {"pPurple": (0.40, 0.04, 1.0), "pBlue": (0.03, 0.18, 1.0), "pPink": (1.0, 0.10, 0.65),
                 "pCyan": (0.02, 0.85, 1.0), "pGreen": (0.20, 1.0, 0.08)}.items():
        M[k] = L.glass_emissive("MAT_Potion_" + k[1:], c, 0.9, 1.0)
    return M


# ---------------------------------------------------------------- helpers
def quad_slab(bm, pts, thick, normal_hint=None):
    """Make a solid from a planar 4-pt (or n-pt) polygon, thickened along its normal."""
    v = [Vector(p) for p in pts]
    n = (v[1] - v[0]).cross(v[-1] - v[0]).normalized()
    if normal_hint is not None and n.dot(Vector(normal_hint)) < 0:
        n = -n
    a = [bm.verts.new(p) for p in v]
    b = [bm.verts.new(p - n * thick) for p in v]
    fs = [bm.faces.new(a), bm.faces.new(b[::-1])]
    k = len(v)
    for i in range(k):
        j = (i + 1) % k
        fs.append(bm.faces.new((a[j], a[i], b[i], b[j])))
    return fs


def striped_obj(name, pieces, M, c, bevel=0.06):
    """pieces = [(pts, thick, mat_index, normal_hint)]; mat 0 = red, 1 = white."""
    bm = bmesh.new()
    for pts, th, mi, nh in pieces:
        for f in quad_slab(bm, pts, th, nh):
            f.material_index = mi
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.from_bmesh(name, bm, None, c)
    ob.data.materials.append(M["red"])
    ob.data.materials.append(M["cream"])
    L.add_bevel(ob, bevel, 2, angle=40)
    return ob


def ring_slab(name, outer, inner, depth, mat, c, y=0.0):
    """Frame between two matching XZ outlines, extruded along Y (centred at y)."""
    bm = bmesh.new()
    n = len(outer)
    fo = [bm.verts.new((p[0], y - depth / 2, p[1])) for p in outer]
    fi = [bm.verts.new((p[0], y - depth / 2, p[1])) for p in inner]
    bo = [bm.verts.new((p[0], y + depth / 2, p[1])) for p in outer]
    bi = [bm.verts.new((p[0], y + depth / 2, p[1])) for p in inner]
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((fo[i], fo[j], fi[j], fi[i]))
        bm.faces.new((bo[j], bo[i], bi[i], bi[j]))
        bm.faces.new((fo[j], fo[i], bo[i], bo[j]))
        bm.faces.new((fi[i], fi[j], bi[j], bi[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.from_bmesh(name, bm, mat, c)
    L.add_bevel(ob, 0.05, 2, angle=40)
    return ob


def notched_rect(w, h, notch):
    x, z, c = w / 2, h / 2, notch
    return [(-x + c, z), (x - c, z), (x - c, z - c), (x, z - c), (x, -z + c), (x - c, -z + c),
            (x - c, -z), (-x + c, -z), (-x + c, -z + c), (-x, -z + c), (-x, z - c), (-x + c, z - c)][::-1]


def offset_notched(w, h, notch, inset):
    return notched_rect(w - 2 * inset, h - 2 * inset, notch)


def sphere(name, r, loc, mat, c, scale=(1, 1, 1), segs=20, rings=12):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    ob = L.from_bmesh(name, bm, mat, c)
    ob.location = loc
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def beam_between(name, p0, p1, w, h, mat, c, bevel=0.06):
    """Rectangular beam from p0 to p1 (w across, h in the 'up' direction)."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    ob = L.box(name, (d.length, w, h), (p0 + p1) / 2, mat, bevel, c=c)
    ob.rotation_euler = d.to_track_quat("X", "Z").to_euler()
    return ob


def crystal_prism(bm, base, height, r, tilt, yaw):
    """Hexagonal prism with pointed tip, appended into bm."""
    mtx = Matrix.Translation(base) @ Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(tilt, 4, "Y")
    body = height * 0.68
    ring0 = [bm.verts.new(mtx @ Vector((r * math.cos(a), r * math.sin(a), 0)))
             for a in [i * math.pi / 3 for i in range(6)]]
    ring1 = [bm.verts.new(mtx @ Vector((r * math.cos(a), r * math.sin(a), body)))
             for a in [i * math.pi / 3 for i in range(6)]]
    tip = bm.verts.new(mtx @ Vector((0, 0, height)))
    bm.faces.new(ring0[::-1])
    for i in range(6):
        j = (i + 1) % 6
        bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
        bm.faces.new((ring1[i], ring1[j], tip))


def leaf_sprig(name, side, M, c, center, y):
    """Laurel sprig: curved stem + alternating leaves (flat extrusions in XZ)."""
    bm = bmesh.new()
    cx, cz = center
    pts = []
    for i in range(8):
        t = i / 7
        a = math.radians(-70 + 125 * t)
        px = cx + side * (0.55 * math.cos(a) - 0.2)
        pz = cz + 0.85 * math.sin(a) * 1.0
        pts.append((px, pz, a))
    def slab(poly, depth):
        f = [bm.verts.new((p[0], y - depth / 2, p[1])) for p in poly]
        b = [bm.verts.new((p[0], y + depth / 2, p[1])) for p in poly]
        bm.faces.new(f); bm.faces.new(b[::-1])
        for i in range(len(poly)):
            j = (i + 1) % len(poly)
            bm.faces.new((f[j], f[i], b[i], b[j]))
    for i, (px, pz, a) in enumerate(pts[1:], 1):
        for s in (-1, 1):
            if i == len(pts) - 1 and s == 1:
                continue
            ang = a + side * (math.pi / 2) + s * 0.75 * side
            ang = math.atan2(math.sin(a + math.pi / 2), side * math.cos(a + math.pi / 2)) + s * 0.6
            lx, lz = math.cos(ang), math.sin(ang)
            px2, pz2 = -lz, lx
            poly = []
            for k in range(10):
                tt = k / 10 * 2 * math.pi
                u = 0.5 * (1 - math.cos(tt))          # 0..1 along leaf
                rr = 0.11 * math.sin(tt)
                poly.append((px + lx * 0.38 * u + px2 * rr, pz + lz * 0.38 * u + pz2 * rr))
            slab(poly[::-1] if side < 0 else poly, 0.08)
    # stem
    for i in range(len(pts) - 1):
        (x0, z0, _), (x1, z1, _) = pts[i], pts[i + 1]
        d = Vector((x1 - x0, z1 - z0)); n = Vector((-d.y, d.x)).normalized() * 0.04
        slab([(x0 - n.x, z0 - n.y), (x1 - n.x, z1 - n.y), (x1 + n.x, z1 + n.y), (x0 + n.x, z0 + n.y)], 0.07)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return L.from_bmesh(name, bm, M["signtext"], c)


# ---------------------------------------------------------------- build
def build(M, root):
    C = {k: L.coll(f"MKT_{k}", root) for k in ("Structure", "Canopy", "Sign", "Counter", "Shelves",
                                               "Merchandise", "Lanterns", "Crates")}
    objs = []
    MB = M["marble"]

    # ---- marble post bases + posts
    for sx in (-1, 1):
        for py, tag in ((FRONT_Y, "F"), (BACK_Y, "B")):
            x = sx * POST_X
            n = f"MKT_Base{tag}{'L' if sx < 0 else 'R'}"
            objs.append(L.box(n + "_Foot", (2.15, 2.15, 0.55), (x, py, 0.275), MB, 0.1, c=C["Structure"]))
            objs.append(L.box(n + "_Body", (1.85, 1.85, 2.3), (x, py, 0.55 + 1.15), MB, 0.08, c=C["Structure"]))
            objs.append(L.box(n + "_Cap", (2.15, 2.15, 0.55), (x, py, BASE_TOP - 0.275), MB, 0.1, c=C["Structure"]))
            top = FRONT_POST_TOP if tag == "F" else RIDGE_Z
            objs.append(L.box(f"MKT_Post{tag}{'L' if sx < 0 else 'R'}", (POST_W, POST_W, top - BASE_TOP),
                              (x, py, (top + BASE_TOP) / 2), M["woodV"], 0.08, c=C["Structure"]))
    # ridge beam with end blocks
    objs.append(L.box("MKT_RidgeBeam", (2 * POST_X + 1.4, 1.1, 0.75), (0, RIDGE_Y - 0.1, RIDGE_Z + 0.37),
                      M["woodH"], 0.1, c=C["Structure"]))
    for sx in (-1, 1):
        objs.append(L.box(f"MKT_RidgeCap_{sx}", (0.9, 1.3, 1.0), (sx * (POST_X + 0.85), RIDGE_Y - 0.1, RIDGE_Z + 0.42),
                          M["woodV"], 0.1, c=C["Structure"]))
    # front header beam under eave, back top beam, side beams + braces
    objs.append(L.box("MKT_FrontHeader", (2 * POST_X + 1.0, 0.95, 0.75), (0, FRONT_Y, FRONT_POST_TOP - 0.55),
                      M["woodH"], 0.08, c=C["Structure"]))
    objs.append(L.box("MKT_BackHeader", (2 * POST_X, 0.9, 0.7), (0, BACK_Y, FRONT_POST_TOP - 0.55),
                      M["woodH"], 0.08, c=C["Structure"]))
    for sx in (-1, 1):
        x = sx * POST_X
        objs.append(beam_between(f"MKT_SideBeam_{sx}", (x, FRONT_Y, FRONT_POST_TOP - 0.55),
                                 (x, BACK_Y, FRONT_POST_TOP - 0.55), 0.85, 0.7, M["woodH"], C["Structure"]))
        # rafter brace parallel to the canopy slope (front post top -> back post high)
        objs.append(beam_between(f"MKT_Rafter_{sx}", (x, FRONT_Y, FRONT_POST_TOP - 0.1),
                                 (x, BACK_Y, RIDGE_Z - 0.6), 0.75, 0.55, M["woodH"], C["Structure"]))
        # knee braces (side view diagonals)
        objs.append(beam_between(f"MKT_KneeBack_{sx}", (x, BACK_Y - 0.4, FRONT_POST_TOP - 2.6),
                                 (x, BACK_Y - 2.0, FRONT_POST_TOP - 0.85), 0.55, 0.45, M["woodH"], C["Structure"]))
        objs.append(beam_between(f"MKT_KneeFront_{sx}", (x, FRONT_Y + 0.4, FRONT_POST_TOP - 2.6),
                                 (x, FRONT_Y + 2.0, FRONT_POST_TOP - 0.85), 0.55, 0.45, M["woodH"], C["Structure"]))
        # front knee braces toward the header (front view shows small corner brackets)
        objs.append(beam_between(f"MKT_FrontKnee_{sx}", (x - sx * 0.5, FRONT_Y - 0.05, FRONT_POST_TOP - 2.2),
                                 (x - sx * 1.7, FRONT_Y - 0.05, FRONT_POST_TOP - 0.85), 0.45, 0.4, M["woodH"],
                                 C["Structure"]))

    # ---- back plank wall (dark wood), full height behind shelves
    wx0, wx1 = -POST_X + POST_W / 2, POST_X - POST_W / 2
    n_pl = 10
    pw = (wx1 - wx0) / n_pl
    for i in range(n_pl):
        objs.append(L.box(f"MKT_BackPlank_{i}", (pw - 0.06, 0.3, RIDGE_Z - 0.3 - BASE_TOP + 3.0),
                          (wx0 + pw * (i + 0.5), BACK_Y + 0.1, (RIDGE_Z - 0.3 + BASE_TOP - 3.0) / 2),
                          M["woodDark"], 0.05, c=C["Structure"]))

    objs.append(L.box("MKT_BackBoard", (2 * POST_X, 0.2, RIDGE_Z - BASE_TOP), (0, BACK_Y + 0.32, (RIDGE_Z + BASE_TOP) / 2 - 1.5),
                      M["woodDark"], 0.03, c=C["Structure"]))

    # ---- canopy (lean-to with hip side flaps, rolled eave, scalloped valance)
    th = 0.24
    pieces = []
    n = int(round(2 * EAVE_HALF / STRIPE))
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        e0 = (-EAVE_HALF + 2 * EAVE_HALF * t0, EAVE_Y, EAVE_Z)
        e1 = (-EAVE_HALF + 2 * EAVE_HALF * t1, EAVE_Y, EAVE_Z)
        r0 = (-RIDGE_HALF + 2 * RIDGE_HALF * t0, RIDGE_Y, RIDGE_Z + 0.05)
        r1 = (-RIDGE_HALF + 2 * RIDGE_HALF * t1, RIDGE_Y, RIDGE_Z + 0.05)
        pieces.append(([e0, e1, r1, r0], th, i % 2, (0, -0.5, 1)))
    # hip side flaps: fan of 3 stripes from the ridge end down to the side eave
    for sx in (-1, 1):
        apex = Vector((sx * RIDGE_HALF, RIDGE_Y, RIDGE_Z + 0.05))
        p_front = Vector((sx * EAVE_HALF, EAVE_Y, EAVE_Z))
        p_back = Vector((sx * (EAVE_HALF - 0.4), RIDGE_Y, EAVE_Z + 0.6))
        k = 3
        for j in range(k):
            a = p_front.lerp(p_back, j / k)
            b = p_front.lerp(p_back, (j + 1) / k)
            pts = [a, b, apex] if sx > 0 else [b, a, apex]
            pieces.append(([tuple(p) for p in pts], th, (j + 1) % 2, (sx, 0, 1)))
    canopy = striped_obj("MKT_CanopyRoof", pieces, M, C["Canopy"])
    objs.append(canopy)
    # rolled eave (one cylinder segment per stripe)
    bm = bmesh.new()
    roll = []
    RR = 0.42                     # roll radius; the end segments stop RR short and get a rounded cap,
    for i in range(n):            # so the roll ends flush with the canopy corner (no flat stub disc)
        x0 = -EAVE_HALF + STRIPE * i
        x1 = x0 + STRIPE
        if i == 0:
            x0 += RR
        if i == n - 1:
            x1 -= RR
        col = M["red"] if i % 2 == 0 else M["cream"]
        seg = L.cyl(f"MKT_EaveRoll_{i}", RR, x1 - x0, ((x0 + x1) / 2, EAVE_Y - 0.1, EAVE_Z - 0.2),
                    col, 16, 0.0, c=C["Canopy"], rot=(0, math.pi / 2, 0))
        roll.append(seg)
    for sx, col in ((-1, M["red"]), (1, M["red"] if (n - 1) % 2 == 0 else M["cream"])):
        cap = sphere(f"MKT_EaveRollCap_{sx}", RR, (sx * (EAVE_HALF - RR), EAVE_Y - 0.1, EAVE_Z - 0.2), col,
                     C["Canopy"], segs=16, rings=8)
        roll.append(cap)
    objs += roll
    # ---- LOWER tier: striped slope, rounded fold at the front, U-shaped hanging tab per stripe
    low = []
    for k in range(n):
        x0 = -EAVE_HALF + STRIPE * k
        x1 = x0 + STRIPE
        low.append(([(x0, LOW_Y1, LOW_Z1), (x1, LOW_Y1, LOW_Z1), (x1, LOW_Y0, LOW_Z0), (x0, LOW_Y0, LOW_Z0)],
                     th, k % 2, (0, -0.3, 1)))
    objs.append(striped_obj("MKT_CanopyLower", low, M, C["Canopy"]))
    fold_c = (LOW_Y1 - 0.02, LOW_Z1 - FOLD_R + 0.02)          # fold axis just under the slope's front edge
    tab_y = fold_c[0] - FOLD_R + 0.15                          # tab front face flush with the fold front
    gap = 0.07
    for k in range(n):
        x0 = -EAVE_HALF + STRIPE * k
        x1 = x0 + STRIPE
        col = M["red"] if k % 2 == 0 else M["cream"]
        objs.append(L.cyl(f"MKT_LowerFold_{k}", FOLD_R, STRIPE - 0.002, ((x0 + x1) / 2, fold_c[0], fold_c[1]), col,
                          16, 0.0, c=C["Canopy"], rot=(0, math.pi / 2, 0)))
        # U tab: straight sides, semicircular bottom
        xa, xb = x0 + gap, x1 - gap
        r = (xb - xa) / 2
        xm = (xa + xb) / 2
        top = fold_c[1]
        zr = top - TAB_H + r
        outline = [(xa, top), (xb, top), (xb, zr)]
        for q in range(1, 10):
            a = -q * math.pi / 10
            outline.append((xm + r * math.cos(a), zr + r * math.sin(a)))
        outline.append((xa, zr))
        tab = L.extrude_polygon(f"MKT_LowerTab_{k}", outline[::-1], 0.3, col, C["Canopy"], bevel=0.04)
        tab.location = (0, tab_y, 0)
        objs.append(tab)

    # (no side valance: the market sheet's side view and awning close-up show scallops on the FRONT
    #  edge only; the earlier side tabs were an invented detail that looked like loose discs at the corner)

    # ---- sign: gold notched frame, maroon panel, 3D text, laurel sprigs
    outer = notched_rect(SIGN_W, SIGN_H, 0.38)
    inner = offset_notched(SIGN_W, SIGN_H, 0.30, 0.34)
    frame = ring_slab("MKT_SignFrame", outer, inner, 0.5, M["gold"], C["Sign"], y=SIGN_Y)
    frame.location = (0, 0, SIGN_Z)
    panel = L.extrude_polygon("MKT_SignPanel", inner, 0.34, M["maroon"], C["Sign"])
    panel.location = (0, SIGN_Y, SIGN_Z)
    inner_line = ring_slab("MKT_SignInnerLine", offset_notched(SIGN_W, SIGN_H, 0.26, 0.48),
                           offset_notched(SIGN_W, SIGN_H, 0.22, 0.56), 0.38, M["gold"], C["Sign"], y=SIGN_Y)
    inner_line.location = (0, 0, SIGN_Z)
    txt = L.text_mesh("MKT_SignText", "MARKET\nSHOP", size=1.32, extrude=0.06, mat=M["signtext"], c=C["Sign"],
                      loc=(0.15, SIGN_Y - 0.2, SIGN_Z - 0.05), line_spacing=0.78, bevel=0.015)
    objs += [frame, panel, inner_line, txt]
    for side in (-1, 1):
        objs.append(leaf_sprig(f"MKT_SignLaurel_{'L' if side < 0 else 'R'}", side, M, C["Sign"],
                               (side * 3.05, SIGN_Z - 0.15), SIGN_Y - 0.2))
    # hidden mounting struts from sign back to the canopy
    for sx in (-2.6, 2.6):
        objs.append(beam_between(f"MKT_SignStrut_{sx}", (sx, SIGN_Y + 0.25, SIGN_Z), (sx, EAVE_Y + 2.2, EAVE_Z + 1.3),
                                 0.3, 0.3, M["woodH"], C["Sign"]))

    # ---- counter
    cx0, cx1 = -POST_X + 0.95, POST_X - 0.95
    cy0, cy1 = -2.75, -1.1
    objs.append(L.box("MKT_CounterBody", (cx1 - cx0, cy1 - cy0 - 0.2, COUNTER_TOP - 0.35),
                      (0, (cy0 + cy1) / 2 + 0.1, (COUNTER_TOP - 0.35) / 2), M["woodPanel"], 0.04, c=C["Counter"]))
    objs.append(L.box("MKT_CounterTop", (cx1 - cx0 + 0.7, cy1 - cy0 + 0.35, 0.38),
                      (0, (cy0 + cy1) / 2 - 0.05, COUNTER_TOP - 0.19), M["woodH"], 0.1, c=C["Counter"]))
    fy = cy0 - 0.02
    frame_d = 0.3
    # frame rails/stiles on the front face
    objs.append(L.box("MKT_CounterRailTop", (cx1 - cx0, frame_d, 0.4), (0, fy, COUNTER_TOP - 0.6), M["woodH"], 0.06, c=C["Counter"]))
    objs.append(L.box("MKT_CounterRailBot", (cx1 - cx0, frame_d, 0.45), (0, fy, 0.25), M["woodH"], 0.06, c=C["Counter"]))
    for x in (cx0 + 0.2, 0.0, cx1 - 0.2):
        objs.append(L.box(f"MKT_CounterStile_{x:.1f}", (0.42, frame_d + 0.08, COUNTER_TOP - 0.4), (x, fy, (COUNTER_TOP - 0.4) / 2),
                          M["woodV"], 0.06, c=C["Counter"]))
    # vertical planks + X braces in each panel
    for (px0, px1) in ((cx0 + 0.41, -0.21), (0.21, cx1 - 0.41)):
        pz0, pz1 = 0.48, COUNTER_TOP - 0.8
        w, h = px1 - px0, pz1 - pz0
        for k in range(5):
            objs.append(L.box(f"MKT_PanelPlank_{px0:.1f}_{k}", (w / 5 - 0.05, 0.14, h),
                              (px0 + w / 5 * (k + 0.5), fy + 0.05, (pz0 + pz1) / 2), M["woodPanel"], 0.03, c=C["Counter"]))
        ang = math.atan2(h, w)
        diag = math.hypot(w, h) - 0.2
        for s in (-1, 1):
            # the second plank lies OVER the first (offset outward): equal depths z-fought -> black centres
            objs.append(L.box(f"MKT_PanelBrace_{px0:.1f}_{s}", (diag, 0.22, 0.34),
                              ((px0 + px1) / 2, fy - 0.1 - (0.12 if s > 0 else 0.0), (pz0 + pz1) / 2),
                              M["woodH"], 0.05, c=C["Counter"], rot=(0, s * ang, 0)))

    # ---- shelves (upper merchandise shelf + lower side shelf)
    for z, nm, x0, x1 in ((SHELF_Z, "Upper", wx0, wx1), (SHELF2_Z, "Lower", wx1 - 3.0, wx1)):
        objs.append(L.box(f"MKT_Shelf{nm}", (x1 - x0, 1.35, 0.25), ((x0 + x1) / 2, WALL_Y - 0.6, z), M["woodH"], 0.05,
                          c=C["Shelves"]))
        for x in (x0 + 0.4, x1 - 0.4):
            objs.append(beam_between(f"MKT_ShelfBracket_{nm}_{x:.1f}", (x, WALL_Y, z - 0.75), (x, WALL_Y - 1.0, z - 0.1),
                                     0.2, 0.2, M["woodV"], C["Shelves"]))
    stop = SHELF_Z + 0.125

    # crystal cluster (purple)
    bm = bmesh.new()
    base = Vector((-3.15, WALL_Y - 0.6, stop))
    crystal_prism(bm, base, 1.6, 0.26, 0.0, 0.3)
    for tilt, yaw, h, r, off in ((0.45, 0.0, 1.0, 0.2, (0.3, 0, 0)), (-0.5, 0.2, 1.05, 0.2, (-0.32, 0, 0)),
                                 (0.75, 0.3, 0.7, 0.15, (0.5, -0.1, 0)), (-0.8, -0.2, 0.65, 0.15, (-0.52, 0.05, 0)),
                                 (0.25, 1.6, 0.8, 0.17, (0.0, -0.25, 0))):
        crystal_prism(bm, base + Vector(off), h, r, tilt, yaw)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    objs.append(L.from_bmesh("MKT_CrystalCluster", bm, M["crystal"], C["Merchandise"]))
    objs.append(L.cyl("MKT_CrystalBase", 0.55, 0.12, (base.x, base.y, stop + 0.06), M["crystal"], 6, 0.03, c=C["Merchandise"]))

    # books
    bx = -2.25
    for i, (mk, h, t) in enumerate((("bookNavy", 1.45, 0.3), ("bookTeal", 1.35, 0.26), ("bookNavy", 1.5, 0.32),
                                     ("bookRed", 1.4, 0.3), ("bookRed", 1.3, 0.24))):
        objs.append(L.box(f"MKT_Book_{i}", (t, 0.95, h), (bx + t / 2, WALL_Y - 0.65, stop + h / 2), M[mk], 0.03,
                          c=C["Merchandise"]))
        objs.append(L.box(f"MKT_BookBand_{i}", (t + 0.02, 0.97, 0.08), (bx + t / 2, WALL_Y - 0.65, stop + h * 0.78),
                          M["gold"], 0.0, c=C["Merchandise"]))
        bx += t + 0.04
    # scroll (rolled parchment + rolled end detail)
    objs.append(L.cyl("MKT_Scroll", 0.24, 1.25, (0.55, WALL_Y - 0.85, stop + 0.24), M["paper"], 16, 0.04,
                      c=C["Merchandise"], rot=(0, math.pi / 2, 0.15)))
    objs.append(L.cyl("MKT_ScrollTie", 0.26, 0.12, (0.55, WALL_Y - 0.85, stop + 0.24), M["bookRed"], 16, 0.0,
                      c=C["Merchandise"], rot=(0, math.pi / 2, 0.15)))
    objs.append(L.cyl("MKT_Scroll2", 0.2, 1.0, (0.65, WALL_Y - 0.4, stop + 0.2), M["paper"], 16, 0.04,
                      c=C["Merchandise"], rot=(0, math.pi / 2, -0.1)))
    # treasure chest
    chx, chy = 2.75, WALL_Y - 0.65
    cw, cd, chh = 1.55, 0.95, 0.7
    objs.append(L.box("MKT_ChestBody", (cw, cd, chh), (chx, chy, stop + chh / 2), M["woodH"], 0.05, c=C["Merchandise"]))
    lid = L.cyl("MKT_ChestLid", cd / 2, cw, (chx, chy, stop + chh), M["woodH"], 16, 0.04, c=C["Merchandise"],
                rot=(0, math.pi / 2, 0))
    # keep only the top half of the lid
    bm = bmesh.new(); bm.from_mesh(lid.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(0, 0, 0), plane_no=(-1, 0, 0),
                           clear_inner=True)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary])
    bm.to_mesh(lid.data); bm.free()
    objs.append(lid)
    for x in (chx - cw / 2 + 0.2, chx + cw / 2 - 0.2):
        objs.append(L.box(f"MKT_ChestBand_{x:.1f}", (0.14, cd + 0.04, chh + 0.02), (x, chy, stop + chh / 2), M["gold"], 0.02,
                          c=C["Merchandise"]))
        band = L.ring(f"MKT_ChestLidBand_{x:.1f}", cd / 2 + 0.04, cd / 2 - 0.05, 0.14, (x, chy, stop + chh), M["gold"], 24,
                      c=C["Merchandise"])
        band.rotation_euler = (0, math.pi / 2, 0)
        objs.append(band)
    objs.append(L.box("MKT_ChestLatch", (0.32, 0.12, 0.38), (chx, chy - cd / 2 - 0.04, stop + chh - 0.02), M["gold"], 0.03,
                      c=C["Merchandise"]))
    # lower shelf books (right side, seen in 3/4 + side views)
    bx = wx1 - 2.6
    for i, (mk, h) in enumerate((("bookRed", 1.0), ("bookNavy", 1.1), ("bookRed", 0.95), ("bookBlue", 1.05))):
        objs.append(L.box(f"MKT_LowBook_{i}", (0.28, 0.8, h), (bx, WALL_Y - 0.6, SHELF2_Z + 0.125 + h / 2), M[mk], 0.03,
                          c=C["Merchandise"]))
        bx += 0.32

    # potions on the counter
    pz = COUNTER_TOP
    for i, (mk, x) in enumerate((("pPurple", -3.0), ("pBlue", -1.5), ("pPink", 0.0), ("pCyan", 1.5), ("pGreen", 2.95))):
        y = -2.05
        objs.append(sphere(f"MKT_Potion_{i}_Flask", 0.55, (x, y, pz + 0.52), M[mk], C["Merchandise"], (1, 1, 0.95)))
        objs.append(L.cyl(f"MKT_Potion_{i}_Neck", 0.2, 0.5, (x, y, pz + 1.15), M[mk], 16, 0.03, c=C["Merchandise"]))
        objs.append(L.cyl(f"MKT_Potion_{i}_Rim", 0.25, 0.1, (x, y, pz + 1.38), M[mk], 16, 0.03, c=C["Merchandise"]))
        objs.append(L.cyl(f"MKT_Potion_{i}_Cork", 0.18, 0.32, (x, y, pz + 1.55), M["cork"], 12, 0.05, c=C["Merchandise"]))

    # ---- lanterns (bracket from front post, hanging lamp)
    for sx in (-1, 1):
        x = sx * (POST_X + 0.75)
        y = FRONT_Y - 0.95
        tag = "L" if sx < 0 else "R"
        objs.append(beam_between(f"MKT_LanternArm_{tag}", (sx * POST_X, FRONT_Y - 0.55, 8.35), (x, y, 8.35), 0.18, 0.18,
                                 M["iron"], C["Lanterns"], 0.03))
        objs.append(L.cyl(f"MKT_LanternHook_{tag}", 0.05, 0.4, (x, y, 8.15), M["iron"], 8, 0.0, c=C["Lanterns"]))
        lc = 6.85
        objs.append(L.cyl(f"MKT_LanternRing_{tag}", 0.14, 0.12, (x, y, 7.95), M["gold"], 10, 0.02, c=C["Lanterns"]))
        objs.append(L.cyl(f"MKT_LanternRoof_{tag}", 0.95, 0.55, (x, y, 7.55), M["gold"], 4, 0.04, c=C["Lanterns"],
                          r2=0.18, rot=(0, 0, math.pi / 4)))
        objs.append(L.box(f"MKT_LanternTopPlate_{tag}", (1.3, 1.3, 0.16), (x, y, 7.22), M["gold"], 0.04, c=C["Lanterns"]))
        objs.append(L.box(f"MKT_LanternGlass_{tag}", (1.0, 1.0, 1.25), (x, y, lc), M["lampglow"], 0.05, c=C["Lanterns"]))
        for cx in (-0.5, 0.5):
            for cy in (-0.5, 0.5):
                objs.append(L.box(f"MKT_LanternBar_{tag}_{cx}_{cy}", (0.14, 0.14, 1.3), (x + cx, y + cy, lc), M["gold"], 0.02,
                                  c=C["Lanterns"]))
        objs.append(L.box(f"MKT_LanternBase_{tag}", (1.2, 1.2, 0.2), (x, y, lc - 0.72), M["gold"], 0.04, c=C["Lanterns"]))
        objs.append(L.cyl(f"MKT_LanternFoot_{tag}", 0.35, 0.2, (x, y, lc - 0.92), M["gold"], 4, 0.03, c=C["Lanterns"], r2=0.12,
                          rot=(math.pi, 0, math.pi / 4)))

    # ---- side crates
    def crate(name, center, size):
        x, y = center
        sx_, sy_, sz_ = size
        o = [L.box(name + "_Body", (sx_ - 0.1, sy_ - 0.1, sz_ - 0.1), (x, y, sz_ / 2), M["crate"], 0.04, c=C["Crates"])]
        e = 0.26
        # edge frame
        for zz in (e / 2, sz_ - e / 2):
            o.append(L.box(name + f"_RimX_{zz:.1f}a", (sx_, e, e), (x, y - sy_ / 2 + e / 2, zz), M["crate"], 0.04, c=C["Crates"]))
            o.append(L.box(name + f"_RimX_{zz:.1f}b", (sx_, e, e), (x, y + sy_ / 2 - e / 2, zz), M["crate"], 0.04, c=C["Crates"]))
            o.append(L.box(name + f"_RimY_{zz:.1f}a", (e, sy_, e), (x - sx_ / 2 + e / 2, y, zz), M["crate"], 0.04, c=C["Crates"]))
            o.append(L.box(name + f"_RimY_{zz:.1f}b", (e, sy_, e), (x + sx_ / 2 - e / 2, y, zz), M["crate"], 0.04, c=C["Crates"]))
        for cx in (-1, 1):
            for cy in (-1, 1):
                o.append(L.box(name + f"_Corner_{cx}{cy}", (e + 0.05, e + 0.05, sz_ + 0.02), (x + cx * (sx_ / 2 - e / 2), y + cy * (sy_ / 2 - e / 2), sz_ / 2),
                               M["crateV"], 0.04, c=C["Crates"]))
        # X braces on the four faces
        for face in ("-y", "+y", "-x", "+x"):
            w = (sx_ if "y" in face else sy_) - 2 * e
            h = sz_ - 2 * e
            ang = math.atan2(h, w)
            dl = math.hypot(w, h)
            for s in (-1, 1):
                if "y" in face:
                    out = 1 if face[0] == "+" else -1          # second plank lies over the first
                    yy = y + (sy_ / 2 + 0.02) * out + (0.07 * out if s > 0 else 0.0)
                    o.append(L.box(name + f"_Brace{face}{s}", (dl, 0.1, 0.22), (x, yy, sz_ / 2), M["crate"], 0.03, c=C["Crates"],
                                   rot=(0, s * ang, 0)))
                else:
                    out = 1 if face[0] == "+" else -1
                    xx = x + (sx_ / 2 + 0.02) * out + (0.07 * out if s > 0 else 0.0)
                    o.append(L.box(name + f"_Brace{face}{s}", (0.1, dl, 0.22), (xx, y, sz_ / 2), M["crate"], 0.03, c=C["Crates"],
                                   rot=(s * ang, 0, 0)))
        return o

    objs += crate("MKT_CrateL", (-6.95, -1.3), (2.2, 2.2, 2.5))
    objs += crate("MKT_CrateR", (7.0, -0.7), (2.5, 2.5, 2.7))
    objs += crate("MKT_CrateRBack", (6.75, 1.75), (2.0, 2.0, 2.0))
    return objs


def main(do_render=True):
    L.reset()
    M = mats()
    root = L.coll("ASSET_03_MarketShop")
    objs = build(M, root)
    L.empty("MKT_Origin", (0, 0, 0), root)
    L.save_blend("03_market_shop.blend")
    if not do_render:
        return
    L.studio_lights()
    L.ground(z=0.0)
    items = L.inspection_set("market", objs, res=800, samples=28, three_q=(0.75, -1.2, 0.45), detail=[
        ("detail_sign", (0.0, -15.0, 10.6), (0.0, SIGN_Y, 10.35), 55),
        ("detail_lantern", (-7.5, -10.0, 7.2), (-5.65, -3.05, 6.9), 60),
        ("detail_shelf", (0.5, -9.5, 7.0), (0.0, 1.0, 6.2), 40),
        ("detail_potions", (0.0, -8.5, 5.4), (0.0, -2.05, 4.3), 40),
    ])
    # beauty render at the sheet's front 3/4 angle with concept-art sky lighting
    L.clear_rig()
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT" or ob.name == "RIG_Ground":
            bpy.data.objects.remove(ob)
    L.beauty_lights()
    L.ground(color=(0.93, 0.90, 0.92), z=0.0)
    L.setup_render((960, 800), 32)
    c = L.camera("CAM_beauty_3q", (13.5, -24.0, 9.5), (0.6, 0.0, 6.6), lens=38)
    items.append(("beauty_front_3q", L.render(c, os.path.join(L.RENDERS, "market_beauty_3q.png"))))
    L.contact_sheet(items, os.path.join(L.RENDERS, "market_inspection_sheet.png"), cols=4, tile=480,
                    title="ASSET 03 - MARKET SHOP (Blender Cycles inspection renders)")


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
