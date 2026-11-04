"""ASSET 1 - White marble arch module (half-arch + column + banner + railing + floor slab).

Primary reference: dedicated arch turnaround (3 views on sky background).
Layout of module A (left view of the sheet):
  * column at x=0 on the back line (y=+0.9), arch springs from its top and
    curves toward +X, ending at its crown at x=15 (mirror plane - two modules
    mirrored about x=15 form the full arch)
  * banner on the front (-Y) face of the column, overhanging its +X edge
  * bronze balustrade on a marble curb from the column to an end post (+X);
    short rail + post on the -X side
  * cobblestone floor in front, cyan neon strip along the front edge.
Run:  python build_01_arch.py [--no-render]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
import lobbylib as L

random.seed(11)

# ---------------------------------------------------------------- dimensions (studs)
COL_X, COL_Y = 0.0, 0.9
SHAFT_W = 4.2
BASE_TIERS = [(5.6, 0.0, 1.3), (5.0, 1.3, 2.4), (4.6, 2.4, 2.7)]   # (width, z0, z1)
SHAFT_Z = (2.7, 15.0)
CAP_TIERS = [(4.5, 15.0, 15.3), (5.8, 15.3, 16.4), (5.0, 16.4, 17.9)]
IMPOST_TOP = 17.9
ARCH_T, ARCH_D = 2.3, 3.1           # radial thickness, depth (Y)
GROOVE_W, GROOVE_D = 1.15, 0.32     # intrados neon channel
CROWN = Vector((15.0, 24.6))        # centreline end (x, z), horizontal tangent
SPRING = Vector((0.6, IMPOST_TOP + ARCH_T / 2 + 0.25))
SLAB_X = (-6.0, 15.0)
SLAB_Y = (-6.4, 3.6)
RAIL_Y = COL_Y
POST_R_X = 11.0
POST_L_X = -4.9
POST_W, POST_H = 1.9, 3.6
RAIL_TOP = 3.15


def lathe(name, prof, segs, mat, c, loc):
    """Spin an (r, z) profile around Z."""
    bm = bmesh.new()
    rings = []
    for i in range(segs):
        a = 2 * math.pi * i / segs + math.pi / segs
        rings.append([bm.verts.new((r * math.cos(a), r * math.sin(a), z)) for r, z in prof])
    for i in range(segs):
        j = (i + 1) % segs
        for k in range(len(prof) - 1):
            bm.faces.new((rings[i][k], rings[j][k], rings[j][k + 1], rings[i][k + 1]))
    bot = bm.faces.new([rings[i][0] for i in range(segs)][::-1])
    top = bm.faces.new([rings[i][-1] for i in range(segs)])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ob = L.from_bmesh(name, bm, mat, c)
    ob.location = loc
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def arch_sweep(name, profile, mat, c, a0, a1, steps=56, cap=True):
    """Sweep a closed (radial, depth) profile along the circular centreline.
    Angles measured from +Z toward -X, around centre O (crown at angle 0)."""
    R = arch_radius()
    O = Vector((CROWN.x, CROWN.y - R))
    bm = bmesh.new()
    rings = []
    for s in range(steps + 1):
        a = a0 + (a1 - a0) * s / steps
        nrm = Vector((-math.sin(a), math.cos(a)))          # radial outward (x,z)
        pc = O + nrm * R
        ring = []
        for rr, yy in profile:
            p = pc + nrm * rr
            ring.append(bm.verts.new((p.x, COL_Y + yy, p.y)))
        rings.append(ring)
    n = len(profile)
    for s in range(steps):
        for k in range(n):
            k2 = (k + 1) % n
            bm.faces.new((rings[s][k], rings[s][k2], rings[s + 1][k2], rings[s + 1][k]))
    if cap:
        bm.faces.new(rings[0])
        bm.faces.new(rings[-1][::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def arch_radius():
    dx = CROWN.x - SPRING.x
    dz = CROWN.y - SPRING.y
    return (dx * dx + dz * dz) / (2 * dz)


def clip_bottom(bm, z):
    """Cut the swept arch flat at the impost top so it sits on the column."""
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, z), plane_no=(0, 0, 1), clear_inner=True)
    cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    bmesh.ops.holes_fill(bm, edges=cut_edges, sides=0)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="EAR_CLIP")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def star_points(r_long_v, r_long_h, r_short, r_in):
    pts = []
    for k in range(16):
        a = math.pi / 2 - k * math.pi / 8
        if k % 4 == 0:
            r = r_long_v if k % 8 == 0 else r_long_h
        elif k % 4 == 2:
            r = r_short
        else:
            r = r_in
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts[::-1]


def build(P, root):
    C = {k: L.coll(f"ARCH_{k}", root) for k in ("Column", "Arch", "Banner", "Balustrade", "Floor")}
    objs = []
    M = P["marble"]

    # ---------------- column
    for i, (w, z0, z1) in enumerate(BASE_TIERS):
        objs.append(L.box(f"ARCH_ColBase_{i}", (w, w, z1 - z0), (COL_X, COL_Y, (z0 + z1) / 2), M, 0.12, c=C["Column"]))
    objs.append(L.box("ARCH_ColShaft", (SHAFT_W, SHAFT_W, SHAFT_Z[1] - SHAFT_Z[0]),
                      (COL_X, COL_Y, sum(SHAFT_Z) / 2), M, 0.1, c=C["Column"]))
    for i, (w, z0, z1) in enumerate(CAP_TIERS):
        objs.append(L.box(f"ARCH_ColCapital_{i}", (w, w, z1 - z0), (COL_X, COL_Y, (z0 + z1) / 2), M,
                          0.14 if i == 1 else 0.1, c=C["Column"]))

    # ---------------- arch (intrados channel profile, closed loop)
    T, D, g, gd = ARCH_T, ARCH_D, GROOVE_W, GROOVE_D
    prof = [(T / 2, -D / 2), (T / 2, D / 2), (-T / 2, D / 2), (-T / 2, g / 2), (-T / 2 + gd, g / 2),
            (-T / 2 + gd, -g / 2), (-T / 2, -g / 2), (-T / 2, -D / 2)][::-1]
    R = arch_radius()
    a_start = math.asin((CROWN.x - SPRING.x) / R) + 0.22     # overshoot then clip flat
    bm = arch_sweep("ARCH_Arch", prof, M, C["Arch"], a_start, 0.0)
    clip_bottom(bm, IMPOST_TOP)
    arch = L.from_bmesh("ARCH_Arch", bm, M, C["Arch"])
    L.add_bevel(arch, 0.1, 2, angle=40)
    objs.append(arch)
    # neon insert inside the channel (slightly recessed from the intrados plane)
    sprof = [(-T / 2 + gd - 0.01, -g / 2 + 0.06), (-T / 2 + gd - 0.01, g / 2 - 0.06),
             (-T / 2 + 0.1, g / 2 - 0.06), (-T / 2 + 0.1, -g / 2 + 0.06)][::-1]
    bm = arch_sweep("ARCH_ArchNeon", sprof, P["cyan"], C["Arch"], a_start, 0.03, steps=56)
    clip_bottom(bm, IMPOST_TOP + 0.05)
    objs.append(L.from_bmesh("ARCH_ArchNeon", bm, P["cyan"], C["Arch"]))
    # corbel lip under the crown end (visible notch at the arch tip on the sheet)
    objs.append(L.box("ARCH_CrownCorbel", (1.3, D + 0.1, 0.5),
                      (CROWN.x - 0.65, COL_Y, CROWN.y - T / 2 - 0.2), M, 0.08, c=C["Arch"]))

    # ---------------- banner
    face_y = COL_Y - SHAFT_W / 2
    by = face_y - 0.42
    bx = COL_X + 1.7
    rod_z = 13.9
    w, h1, pd = 2.8, 6.3, 1.15
    outline = [(-w / 2, 0), (w / 2, 0), (w / 2, -h1), (0, -h1 - pd), (-w / 2, -h1)]
    i = 0.17
    inner = [(-w / 2 + i, -0.12), (w / 2 - i, -0.12), (w / 2 - i, -h1 + 0.07), (0, -h1 - pd + 0.36),
             (-w / 2 + i, -h1 + 0.07)]
    gold_b = L.extrude_polygon("ARCH_BannerTrim", outline, 0.1, P["gold"], C["Banner"], bevel=0.03)
    navy = L.extrude_polygon("ARCH_BannerCloth", inner, 0.16, P["navy"], C["Banner"], bevel=0.02)
    star_f = L.extrude_polygon("ARCH_BannerStarFront", star_points(1.8, 1.15, 0.55, 0.24), 0.05,
                               P["white"], C["Banner"], center_depth=False)
    star_b = L.extrude_polygon("ARCH_BannerStarBack", star_points(1.8, 1.15, 0.55, 0.24), 0.05,
                               P["white"], C["Banner"], center_depth=False)
    gem_pts = [(0, 0.38), (0.24, 0), (0, -0.38), (-0.24, 0)]
    gem_f = L.extrude_polygon("ARCH_BannerGemFront", gem_pts, 0.05, P["cyan_soft"], C["Banner"], center_depth=False)
    gem_b = L.extrude_polygon("ARCH_BannerGemBack", gem_pts, 0.05, P["cyan_soft"], C["Banner"], center_depth=False)
    top = rod_z - 0.12
    star_z = top - h1 * 0.47
    for ob in (gold_b, navy):
        ob.location = (bx, by, top)
    star_f.location = (bx, by - 0.08 - 0.045, star_z)   # front face, extrudes toward +y into cloth
    gem_f.location = (bx, by - 0.08 - 0.075, star_z)
    star_b.location = (bx, by + 0.08 + 0.045, star_z); star_b.rotation_euler = (0, 0, math.pi)
    gem_b.location = (bx, by + 0.08 + 0.075, star_z); gem_b.rotation_euler = (0, 0, math.pi)
    objs += [gold_b, navy, star_f, star_b, gem_f, gem_b]
    rod = L.cyl("ARCH_BannerRod", 0.11, w + 0.9, (bx, by, rod_z), P["gold"], 16, 0.02, c=C["Banner"],
                rot=(0, math.pi / 2, 0))
    objs.append(rod)
    for s in (-1, 1):
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=10, radius=0.22)
        f = L.from_bmesh(f"ARCH_BannerFinial_{'L' if s < 0 else 'R'}", bm, P["gold"], C["Banner"])
        f.location = (bx + s * (w / 2 + 0.45 + 0.12), by, rod_z)
        for p in f.data.polygons: p.use_smooth = True
        objs.append(f)
    # wall bracket from column face to rod (two small arms)
    for xo in (-0.9, 0.0):
        objs.append(L.box(f"ARCH_BannerBracket_{xo}", (0.18, face_y - by + 0.05, 0.18),
                          (bx + xo, (face_y + by) / 2, rod_z), P["gold"], 0.03, c=C["Banner"]))

    # ---------------- balustrade
    def post(name, x):
        o = [L.box(f"{name}_Body", (POST_W, POST_W, POST_H - 0.35), (x, RAIL_Y, (POST_H - 0.35) / 2), M, 0.1,
                   c=C["Balustrade"]),
             L.box(f"{name}_Cap", (POST_W + 0.3, POST_W + 0.3, 0.35), (x, RAIL_Y, POST_H - 0.175), M, 0.08,
                   c=C["Balustrade"]),
             L.box(f"{name}_FinialBase", (1.0, 1.0, 0.22), (x, RAIL_Y, POST_H + 0.11), P["bronze"], 0.04,
                   c=C["Balustrade"]),
             L.box(f"{name}_FinialBody", (0.62, 0.62, 0.5), (x, RAIL_Y, POST_H + 0.47), P["gold"], 0.05,
                   c=C["Balustrade"])]
        roof = L.cyl(f"{name}_FinialRoof", 0.72, 0.5, (x, RAIL_Y, POST_H + 0.97), P["gold"], 4, 0.03,
                     c=C["Balustrade"], r2=0.08, rot=(0, 0, math.pi / 4))
        knob = L.cyl(f"{name}_FinialKnob", 0.13, 0.22, (x, RAIL_Y, POST_H + 1.3), P["gold"], 8, 0.04,
                     c=C["Balustrade"])
        return o + [roof, knob]

    objs += post("ARCH_PostR", POST_R_X)
    objs += post("ARCH_PostL", POST_L_X)
    bal_prof = [(0.2, 0.0), (0.2, 0.12), (0.12, 0.2), (0.1, 0.45), (0.19, 0.78), (0.22, 0.95), (0.18, 1.12),
                (0.1, 1.38), (0.13, 1.5), (0.2, 1.56), (0.2, 1.7)]

    def rail_run(name, x0, x1, n_bal):
        o = []
        length = x1 - x0
        xm = (x0 + x1) / 2
        o.append(L.box(f"{name}_Curb", (length, 1.15, 0.8), (xm, RAIL_Y, 0.4), M, 0.1, c=C["Balustrade"]))
        o.append(L.box(f"{name}_BottomRail", (length, 0.6, 0.25), (xm, RAIL_Y, 0.925), P["bronze"], 0.05,
                       c=C["Balustrade"]))
        o.append(L.box(f"{name}_TopRail", (length, 0.62, 0.38), (xm, RAIL_Y, RAIL_TOP - 0.19), P["bronze"], 0.12,
                       c=C["Balustrade"]))
        for k in range(n_bal):
            x = x0 + length * (k + 1) / (n_bal + 1)
            o.append(lathe(f"{name}_Baluster_{k}", bal_prof, 10, P["bronze"], C["Balustrade"], (x, RAIL_Y, 1.05)))
        return o

    col_edge = BASE_TIERS[0][0] / 2
    objs += rail_run("ARCH_RailR", COL_X + col_edge, POST_R_X - POST_W / 2, 5)
    objs += rail_run("ARCH_RailL", POST_L_X + POST_W / 2, COL_X - col_edge, 1)

    # ---------------- floor slab
    sx0, sx1 = SLAB_X; sy0, sy1 = SLAB_Y
    bord = 0.6
    objs.append(L.box("ARCH_SlabBase", (sx1 - sx0, sy1 - sy0, 1.2), ((sx0 + sx1) / 2, (sy0 + sy1) / 2, -0.7), M,
                      0.14, c=C["Floor"]))
    top_z, th = 0.08, 0.3
    strip_y0, strip_y1 = sy0 + 0.65, sy0 + 1.0
    cob_y0, cob_y1 = strip_y1 + 0.08, RAIL_Y - 0.62
    def deck(name, x0, x1, y0, y1):
        return L.box(name, (x1 - x0, y1 - y0, th), ((x0 + x1) / 2, (y0 + y1) / 2, top_z - th / 2), M, 0.08,
                     c=C["Floor"])
    objs.append(deck("ARCH_BorderFront", sx0, sx1, sy0, strip_y0))
    objs.append(deck("ARCH_BorderStrip", sx0, sx1, strip_y1, strip_y1 + 0.08))
    objs.append(deck("ARCH_BorderLeft", sx0, sx0 + bord, strip_y1, sy1))
    objs.append(deck("ARCH_BorderRight", sx1 - bord, sx1, strip_y1, sy1))
    objs.append(deck("ARCH_DeckBack", sx0 + bord, sx1 - bord, cob_y1, sy1))
    # neon strip in its channel
    objs.append(L.box("ARCH_FloorNeon", (sx1 - sx0 - 0.2, strip_y1 - strip_y0 - 0.06, 0.12),
                      ((sx0 + sx1) / 2, (strip_y0 + strip_y1) / 2, top_z - 0.1), P["cyan"], 0.02, c=C["Floor"]))
    # grout bed
    objs.append(L.box("ARCH_Grout", (sx1 - sx0 - 2 * bord, cob_y1 - cob_y0 + 0.02, 0.1),
                      ((sx0 + sx1) / 2, (cob_y0 + cob_y1) / 2, top_z - 0.24), P["grout"], 0.0, c=C["Floor"]))
    # cobblestones (running bond setts, gently irregular)
    cx0, cx1 = sx0 + bord + 0.05, sx1 - bord - 0.05
    row_h, gap = 0.95, 0.09
    y = cob_y0
    r = 0
    footprint = BASE_TIERS[0][0] / 2 + 0.08
    stones = []
    while y + row_h <= cob_y1 + 0.01:
        x = cx0 - (0.75 if r % 2 else 0.0)
        while x < cx1 - 0.2:
            ln = random.uniform(1.3, 1.75)
            xa, xb = max(x, cx0), min(x + ln, cx1)
            if xb - xa > 0.35:
                xc, yc = (xa + xb) / 2, y + row_h / 2
                if not (abs(xc - COL_X) < footprint + (xb - xa) / 2 and yc > COL_Y - footprint - row_h / 2):
                    s = L.box(f"ARCH_Cobble_{len(stones):03d}",
                              (xb - xa - gap, row_h - gap, 0.26 + random.uniform(-0.03, 0.03)),
                              (xc + random.uniform(-0.03, 0.03), yc + random.uniform(-0.03, 0.03),
                               top_z - 0.13 + random.uniform(-0.03, 0.02)),
                              P["cobble"], 0.07, c=C["Floor"], rot=(0, 0, random.uniform(-0.03, 0.03)))
                    stones.append(s)
            x += ln
        y += row_h
        r += 1
    objs += stones
    print("cobbles", len(stones))
    return objs


def reference_match(objs):
    """Re-light with the concept-art sky and render from the turnaround's LEFT-view camera."""
    L.clear_rig()
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT":
            bpy.data.objects.remove(ob)
    L.beauty_lights()
    L.setup_render((1000, 1000), 48)
    c = L.camera("CAM_refmatch_left", (-13.0, -33.0, 7.5), (5.5, 0.0, 12.5), lens=33)
    a = L.render(c, os.path.join(L.RENDERS, "arch_refmatch_leftview.png"))
    c = L.camera("CAM_refmatch_side", (-38.0, -4.5, 9.0), (4.0, -1.0, 12.0), lens=40)
    b = L.render(c, os.path.join(L.RENDERS, "arch_refmatch_sideview.png"))
    return [("refmatch_left_view", a), ("refmatch_side_view", b)]


def main(do_render=True):
    L.reset()
    P = L.palette()
    root = L.coll("ASSET_01_MarbleArch")
    objs = build(P, root)
    origin = L.empty("ARCH_Origin", (0, 0, 0), root)
    L.save_blend("01_marble_arch.blend")
    if not do_render:
        return
    # inspection renders (neutral)
    L.studio_lights()
    L.ground(z=-1.31)
    items = L.inspection_set("arch", objs, res=900, samples=40, three_q=(-0.75, -1.2, 0.55), detail=[
        ("detail_capital_banner", (5.5, -14.0, 13.5), (1.6, 0.0, 14.5), 50),
        ("detail_railing_floor", (8.0, -11.0, 4.5), (6.0, 0.0, 1.0), 40),
        ("detail_crown_neon", (11.0, -9.0, 15.0), (12.5, COL_Y, 22.5), 45),
    ])
    items += reference_match(objs)
    L.contact_sheet(items, os.path.join(L.RENDERS, "arch_inspection_sheet.png"), cols=4, tile=520,
                    title="ASSET 01 - MARBLE ARCH MODULE (Blender Cycles inspection renders)")


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
