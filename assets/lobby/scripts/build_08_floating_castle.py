"""ASSET 8 - Floating castle island (background asset).

Primary reference: images/5.webp (floating castle island, 3/4 from front-left, slightly above).
Secondary: the small background castles in lobby images 1-4 (same design, read for silhouette only).

Measured from the reference (island top edge ~1300 px wide -> ~62 studs, ~0.046 stud/px):
  keep ~10.6 wide x ~19 tall body + ~6 stud stepped blue pyramid roof; outer towers ~6.7 wide,
  ~12.5 tall + roof; inner towers ~7 / ~5.5 wide; front curtain wall ~10 tall with the arched
  glowing entrance right of the keep; 5-step stair down to the grass; waterfall at the front-left edge.
Vegetation (trees, bushes, flowers, grass blades) is deliberately NOT modelled - the ground is a
flat chunky grass-coloured slab only.

Coordinates: island centre at origin, grass top z=0, front = -Y.
Run:  python build_08_floating_castle.py [--no-render]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
import lobbylib as L
from build_05_arena_gate import crystal, frame_prism
from build_01_arch import star_points

random.seed(8)

# ------------------------------------------------------------------ named dimensions (studs)
CELL = 4.0                    # voxel cell of the island
ISLAND_RX, ISLAND_RY = 31.0, 21.0
GRASS_T = 1.2
SEG_H = 4.0                   # underside block course height
PLAT = (-22.6, 23.6, -7.5, 12.5)   # castle platform x0,x1,y0,y1 (hugs the castle footprint)
PLAT_TOP = 2.0
WALL_Y = (-4.0, -1.0)
WALL_X = (-11.0, 16.0)
WALL_TOP = PLAT_TOP + 10.0
DOOR_X, DOOR_W, DOOR_H = 7.0, 4.2, 6.6
KEEP = (0.0, 3.5, 11.0, 10.0, 19.0)          # cx, cy, w, d, height above platform
TOWERS = {                                   # cx, cy, w, height above platform
    "OuterL": (-18.6, 0.5, 6.6, 12.5),
    "InnerL": (-8.2, -3.0, 7.0, 14.0),
    "InnerR": (10.8, 2.0, 5.6, 15.5),
    "OuterR": (19.6, 0.5, 6.6, 12.5),
    "Back": (13.5, 9.5, 5.0, 18.0),
}
STEP_N, STEP_H, STEP_D, STAIR_W = 5, PLAT_TOP / 5, 1.1, 6.4

P = None
M = {}
TRIS = {"count": 0}


def mats():
    M["marble"] = P["marble"]
    M["stone_dark"] = P["marble_dark"]
    M["gold"] = P["gold"]
    M["navy"] = P["navy"]
    M["white"] = P["white"]
    M["roof"] = L.flat("MAT_RoofBlue", (0.05, 0.12, 0.58), rough=0.45)
    M["roof_hi"] = L.flat("MAT_RoofBlueLight", (0.08, 0.20, 0.78), rough=0.45)
    M["window"] = L.emissive("MAT_WindowCyan", (0.12, 0.75, 1.0), 2.2, base=(0.35, 0.85, 1.0))
    M["door"] = L.emissive("MAT_DoorWarm", (1.0, 0.68, 0.30), 1.4, base=(1.0, 0.80, 0.50))
    M["flag"] = L.flat("MAT_FlagRed", (0.80, 0.05, 0.08), rough=0.6)
    M["iron"] = L.flat("MAT_LanternIron", (0.13, 0.15, 0.22), rough=0.45, metal=0.6)
    M["glass"] = L.glass_emissive("MAT_LanternGlassCyan", (0.35, 0.9, 1.0), 2.5, alpha=0.9)
    M["crystal"] = L.emissive("MAT_CrystalCyan", (0.15, 0.85, 1.0), 1.6, base=(0.45, 0.9, 1.0))
    M["water"] = L.glass_emissive("MAT_Waterfall", (0.30, 0.82, 1.0), 1.0, alpha=0.78)
    M["foam"] = L.emissive("MAT_WaterFoam", (0.75, 0.95, 1.0), 1.2, base=(0.9, 0.98, 1.0))
    M["rock"] = L.flat("MAT_RockGrey", (0.50, 0.50, 0.56), rough=0.85)
    M["grass"] = L.flat("MAT_GrassTop", (0.30, 0.62, 0.16), rough=0.85)
    M["grass2"] = L.flat("MAT_GrassTopLight", (0.40, 0.72, 0.22), rough=0.85)
    for i, col in enumerate([(0.62, 0.58, 0.72), (0.55, 0.51, 0.66), (0.68, 0.64, 0.78), (0.48, 0.45, 0.60)]):
        M[f"stone{i}"] = L.flat(f"MAT_IslandStone{i}", col, rough=0.9)


def bx(name, size, loc, mat, c, bevel=0.1, rot=(0, 0, 0)):
    """Castle box with a 1-segment bevel (background asset triangle budget)."""
    ob = L.box(name, size, loc, mat, bevel, segs=1, c=c, rot=rot)
    return ob


def merged_boxes(name, boxes, mat_list, c, bevel=0.0):
    """boxes = [(center, size, mat_index)] -> one mesh object."""
    bm = bmesh.new()
    for ctr, size, mi in boxes:
        before = set(bm.faces)
        bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation(ctr) @ Matrix.Diagonal((*size, 1)))
        for f in set(bm.faces) - before:
            f.material_index = mi
    ob = L.from_bmesh(name, bm, None, c)
    for m in mat_list:
        ob.data.materials.append(m)
    if bevel:
        L.add_bevel(ob, bevel, 1, angle=40)
    return ob


# ------------------------------------------------------------------ island
def build_island(C):
    objs = []
    cells = []
    nx, ny = int(ISLAND_RX * 2 / CELL) + 2, int(ISLAND_RY * 2 / CELL) + 2
    for i in range(-nx // 2, nx // 2 + 1):
        for j in range(-ny // 2, ny // 2 + 1):
            x, y = (i + 0.5) * CELL, (j + 0.5) * CELL
            rn = math.hypot(x / ISLAND_RX, y / ISLAND_RY)
            if rn < 1.0 + random.uniform(-0.1, 0.06):
                cells.append((x, y, min(rn, 1.0)))
    in_plat = lambda x, y: PLAT[0] - 2 < x < PLAT[1] + 2 and PLAT[2] - 7 < y < PLAT[3] + 2
    grass, under = [], []
    tips = set(random.sample(range(len(cells)), 6))
    for k, (x, y, rn) in enumerate(cells):
        lift = 0.0 if in_plat(x, y) or rn > 0.85 else random.choice((0.0, 0.0, 0.0, 0.35))
        grass.append(((x, y, -GRASS_T / 2 + lift), (CELL + 0.02, CELL + 0.02, GRASS_T + 2 * lift),
                      0 if random.random() < 0.6 else 1))
        depth = 4.0 + 30.0 * (1.0 - rn) ** 1.5 * random.uniform(0.8, 1.2)
        if k in tips and rn < 0.6:
            depth += random.uniform(8, 14)
        z = -GRASS_T
        # solid full-width upper mass (reads as one block body, as in the reference)
        h0 = min(depth, 7.0 + 7.0 * (1.0 - rn))
        under.append(((x, y, z - h0 / 2), (CELL + 0.02, CELL + 0.02, h0), random.choice((0, 2))))
        z -= h0
        depth -= h0
        seg = 1
        while depth > 0.4:
            h = min(SEG_H, depth)
            inset = min(0.4 * seg, CELL * 0.35)
            w = CELL - 2 * inset
            mi = (seg + random.randint(0, 1)) % 4
            under.append(((x + random.uniform(-0.1, 0.1), y + random.uniform(-0.1, 0.1), z - h / 2), (w, w, h), mi))
            z -= h
            depth -= h
            seg += 1
    stone = [M[f"stone{i}"] for i in range(4)]
    objs.append(merged_boxes("FC_IslandGrass", grass, [M["grass"], M["grass2"]], C["Island"], bevel=0.14))
    objs.append(merged_boxes("FC_IslandUnderside", under, stone, C["Island"]))
    # loose floating cubes under the island
    for k in range(6):
        s = random.uniform(1.2, 2.8)
        objs.append(bx(f"FC_FloatCube_{k}", (s, s, s),
                       (random.uniform(-22, 22), random.uniform(-14, 10), random.uniform(-38, -24)),
                       stone[k % 4], C["Island"], 0.12,
                       rot=(random.uniform(-0.4, 0.4), random.uniform(-0.4, 0.4), random.uniform(0, 1.5))))
    return objs, cells


def build_waterfall(C, cells):
    objs = []
    xw = -20.0
    col = [c for c in cells if abs(c[0] - xw) < CELL / 2 + 0.1]
    edge = min(c[1] for c in col) - CELL / 2
    # stream channel across the grass to the lip
    objs.append(bx("FC_StreamBed", (3.4, 9.0, 0.3), (xw, edge + 4.4, 0.05), M["water"], C["Waterfall"], 0.05))
    # falling sheet: front + back layers of stepped translucent blocks (real thickness)
    zs = [0.2, -6, -13, -20, -28, -36]
    for k in range(len(zs) - 1):
        z0, z1 = zs[k], zs[k + 1]
        w = 3.2 + 0.25 * k
        objs.append(bx(f"FC_FallFront_{k}", (w, 0.9, z0 - z1), (xw, edge - 0.55 - 0.15 * k, (z0 + z1) / 2),
                       M["water"], C["Waterfall"], 0.08))
        objs.append(bx(f"FC_FallCore_{k}", (w * 0.55, 0.6, z0 - z1), (xw + 0.3, edge - 1.0 - 0.15 * k, (z0 + z1) / 2),
                       M["foam"], C["Waterfall"], 0.06))
    for k in range(5):
        s = random.uniform(0.5, 0.9)
        objs.append(bx(f"FC_Foam_{k}", (s, s, s), (xw + random.uniform(-1.5, 1.5), edge - 0.4, random.uniform(-0.3, 0.4)),
                       M["foam"], C["Waterfall"], 0.1))
    # grey rocks near the waterfall and scattered on the grass
    spots = [(-23.5, edge + 2.0, 1.6), (-17.0, edge + 1.5, 1.2), (-25.0, edge + 6.0, 1.3), (-16.5, edge + 5.0, 0.9),
             (21.0, -12.0, 1.4), (24.0, -8.0, 1.0), (-8.0, -15.0, 0.9)]
    for k, (x, y, s) in enumerate(spots):
        objs.append(bx(f"FC_Rock_{k}", (s * 1.4, s * 1.1, s), (x, y, s / 2 - 0.1), M["rock"], C["Waterfall"], 0.2,
                       rot=(0, 0, random.uniform(0, 1.2))))
    return objs


# ------------------------------------------------------------------ castle helpers
def arch_poly(w, h, seg=8):
    r = w / 2
    pts = [(r, 0.0), (r, h - r)]
    for i in range(1, seg):
        a = math.pi * i / seg
        pts.append((r * math.cos(a), h - r + r * math.sin(a)))
    pts += [(-r, h - r), (-r, 0.0)]
    return pts[::-1] if _area(pts) < 0 else pts


def _area(p):
    return sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))) / 2


def window(name, x, y, z, w, h, C, yaw=0.0):
    """Arched glowing window with a marble surround, on a face whose outward normal is -Y rotated by yaw."""
    objs = []
    fr = L.extrude_polygon(f"{name}_Frame", [(px * 1.0, pz) for px, pz in arch_poly(w + 0.7, h + 0.35)], 0.25,
                           M["marble"], C, bevel=0.04)
    gl = L.extrude_polygon(f"{name}_Glow", arch_poly(w, h), 0.32, M["window"], C)
    mull = L.box(f"{name}_Mullion", (0.18, 0.36, h - 0.2), (0, 0, (h - 0.2) / 2 + 0.1), M["marble"], 0.0, c=C)
    for ob, dz in ((fr, -0.17), (gl, 0.0), (mull, 0.0)):
        ob.location = Vector((x, y, z + dz)) + (Vector((0, 0, ob.location.z)) if ob is mull else Vector())
        ob.rotation_euler = (0, 0, yaw)
        objs.append(ob)
    return objs


def banner(name, x, y, top, w, h1, pd, C):
    outline = [(-w / 2, 0), (w / 2, 0), (w / 2, -h1), (0, -h1 - pd), (-w / 2, -h1)]
    i = 0.14
    inner = [(-w / 2 + i, -0.1), (w / 2 - i, -0.1), (w / 2 - i, -h1 + 0.06), (0, -h1 - pd + 0.3), (-w / 2 + i, -h1 + 0.06)]
    t = L.extrude_polygon(f"{name}_Trim", outline, 0.1, M["gold"], C, bevel=0.02)
    cl = L.extrude_polygon(f"{name}_Cloth", inner, 0.16, M["navy"], C)
    sc = w / 2.8
    st = L.extrude_polygon(f"{name}_Star", [(px * sc, pz * sc) for px, pz in star_points(1.8, 1.15, 0.55, 0.24)],
                           0.05, M["white"], C, center_depth=False)
    for ob in (t, cl):
        ob.location = (x, y, top)
    st.location = (x, y - 0.13, top - h1 * 0.45)
    rod = L.cyl(f"{name}_Rod", 0.08, w + 0.5, (x, y + 0.05, top + 0.08), M["gold"], 10, 0.0, c=C, rot=(0, math.pi / 2, 0))
    return [t, cl, st, rod]


def stepped_roof(name, cx, cy, z0, base, C, layers=5, lh=1.15, finial="crystal"):
    """Voxel-stepped pyramid roof (blue) with a gold eave band and a finial."""
    objs = [bx(f"{name}_Eave", (base + 0.3, base + 0.3, 0.3), (cx, cy, z0 + 0.15), M["gold"], C, 0.05)]
    z = z0 + 0.3
    for k in range(layers):
        s = base * (1.0 - k / (layers + 0.7))
        objs.append(bx(f"{name}_Layer_{k}", (s, s, lh), (cx, cy, z + lh / 2), M["roof"] if k % 2 == 0 else M["roof_hi"],
                       C, 0.12))
        z += lh
    s_top = base * (1.0 - layers / (layers + 0.7))
    objs.append(L.cyl(f"{name}_Cap", s_top * 0.5, 0.9, (cx, cy, z + 0.45), M["roof_hi"], 4, 0.05, c=C, r2=0.1,
                      rot=(0, 0, math.pi / 4)))
    z += 0.9
    if finial == "crystal":
        objs.append(crystal(f"{name}_Crystal", 0.45, 1.8, 0.5, (cx, cy, z + 0.4), M["crystal"], C))
    else:
        objs += flag(f"{name}_Flag", cx, cy, z, C)
    return objs


def flag(name, x, y, z, C, h=4.0):
    pole = L.cyl(f"{name}_Pole", 0.11, h, (x, y, z + h / 2), M["gold"], 8, 0.0, c=C)
    ball = L.cyl(f"{name}_Ball", 0.25, 0.4, (x, y, z + h + 0.15), M["gold"], 8, 0.08, c=C)
    pen = L.extrude_polygon(f"{name}_Pennant", [(0, 0), (2.6, 0.45), (2.0, 0.62), (2.7, 1.05), (0, 1.25)], 0.08,
                            M["flag"], C)
    pen.location = (x + 0.1, y, z + h - 1.5)
    return [pole, ball, pen]


def merlons(prefix, x0, x1, y0, y1, z, C, mw=1.0, mh=1.0, step=2.0, sides="NESW", depth=0.7):
    """Crenellation blocks on the rectangle edges at height z."""
    out = []
    def run(a0, a1, fixed, axis, tag):
        n = max(2, int((a1 - a0) / step) + 1)
        for k in range(n):
            a = a0 + (a1 - a0) * k / (n - 1)
            if axis == "x":
                out.append(bx(f"{prefix}_M{tag}{k}", (mw, depth, mh), (a, fixed, z + mh / 2), M["marble"], C, 0.08))
            else:
                out.append(bx(f"{prefix}_M{tag}{k}", (depth, mw, mh), (fixed, a, z + mh / 2), M["marble"], C, 0.08))
    if "S" in sides: run(x0 + mw / 2, x1 - mw / 2, y0 + depth / 2, "x", "S")
    if "N" in sides: run(x0 + mw / 2, x1 - mw / 2, y1 - depth / 2, "x", "N")
    if "W" in sides: run(y0 + mw / 2 + depth, y1 - mw / 2 - depth, x0 + depth / 2, "y", "W")
    if "E" in sides: run(y0 + mw / 2 + depth, y1 - mw / 2 - depth, x1 - depth / 2, "y", "E")
    return out


def tower(name, cx, cy, w, h, C, finial="crystal", windows=1):
    z0 = PLAT_TOP
    objs = [bx(f"{name}_Body", (w, w, h), (cx, cy, z0 + h / 2), M["marble"], C, 0.12),
            bx(f"{name}_Foot", (w + 0.5, w + 0.5, 0.9), (cx, cy, z0 + 0.45), M["stone_dark"], C, 0.1),
            bx(f"{name}_GoldBand", (w + 0.16, w + 0.16, 0.3), (cx, cy, z0 + h - 1.3), M["gold"], C, 0.04),
            bx(f"{name}_Corbel", (w + 0.7, w + 0.7, 0.7), (cx, cy, z0 + h + 0.35), M["marble"], C, 0.1)]
    half = (w + 0.7) / 2
    objs += merlons(name, cx - half, cx + half, cy - half, cy + half, z0 + h + 0.7, C, step=1.9)
    objs += stepped_roof(f"{name}_Roof", cx, cy, z0 + h + 1.4, w + 0.9, C, layers=5, lh=1.1, finial=finial)
    for k in range(windows):
        wz = z0 + h * (0.42 + 0.3 * k)
        objs += window(f"{name}_Win{k}", cx, cy - w / 2 - 0.05, wz, 1.3, 2.4, C)
    return objs


# ------------------------------------------------------------------ castle
def build_castle(C):
    objs = []
    x0, x1, y0, y1 = PLAT
    objs.append(bx("FC_Platform", (x1 - x0, y1 - y0, PLAT_TOP + 0.6), ((x0 + x1) / 2, (y0 + y1) / 2, (PLAT_TOP - 0.6) / 2),
                   M["stone_dark"], C["Castle"], 0.14))
    objs.append(bx("FC_PlatformGold", (x1 - x0 + 0.1, 0.12, 0.25), ((x0 + x1) / 2, y0 - 0.02, PLAT_TOP - 0.3), M["gold"],
                   C["Castle"], 0.02))
    # keep
    kx, ky, kw, kd, kh = KEEP
    z0 = PLAT_TOP
    objs += [bx("FC_Keep_Body", (kw, kd, kh), (kx, ky, z0 + kh / 2), M["marble"], C["Castle"], 0.12),
             bx("FC_Keep_GoldBand", (kw + 0.16, kd + 0.16, 0.35), (kx, ky, z0 + kh - 1.4), M["gold"], C["Castle"], 0.04),
             bx("FC_Keep_GoldBand2", (kw + 0.16, kd + 0.16, 0.3), (kx, ky, z0 + kh * 0.55), M["gold"], C["Castle"], 0.04),
             bx("FC_Keep_Corbel", (kw + 0.8, kd + 0.8, 0.8), (kx, ky, z0 + kh + 0.4), M["marble"], C["Castle"], 0.1)]
    objs += merlons("FC_Keep", kx - kw / 2 - 0.4, kx + kw / 2 + 0.4, ky - kd / 2 - 0.4, ky + kd / 2 + 0.4,
                    z0 + kh + 0.8, C["Castle"], mw=1.1, mh=1.1, step=2.1)
    objs += stepped_roof("FC_Keep_Roof", kx, ky, z0 + kh + 1.6, kw - 0.6, C["Castle"], layers=6, lh=1.2, finial="flag")
    for sx in (-1, 1):
        for sy in (-1, 1):
            objs.append(crystal(f"FC_Keep_CornerCrystal_{sx}{sy}", 0.4, 1.6, 0.4,
                                (kx + sx * (kw / 2 + 0.1), ky + sy * (kd / 2 + 0.1), z0 + kh + 2.2), M["crystal"], C["Castle"]))
    objs += banner("FC_Keep_Banner", kx, ky - kd / 2 - 0.12, z0 + kh - 2.0, 2.6, 4.6, 1.0, C["Castle"])
    for sx in (-1, 1):
        objs += window(f"FC_Keep_Win{sx}", kx + sx * 3.3, ky - kd / 2 - 0.05, z0 + kh - 6.4, 1.4, 2.8, C["Castle"])
    # towers
    for n, (cx, cy, w, h) in TOWERS.items():
        fin = "flag" if n in ("OuterL", "OuterR", "Back") else "crystal"
        objs += tower(f"FC_Tower{n}", cx, cy, w, h, C["Castle"], fin, windows=2 if h > 14 else 1)
    # curtain walls (front wall with arched glowing entrance, side links to outer towers)
    wy0, wy1 = WALL_Y
    wx0, wx1 = WALL_X
    wh = WALL_TOP - z0
    dl, dr = DOOR_X - DOOR_W / 2, DOOR_X + DOOR_W / 2
    objs += [bx("FC_Wall_Left", (dl - wx0, wy1 - wy0, wh), ((wx0 + dl) / 2, (wy0 + wy1) / 2, z0 + wh / 2), M["marble"],
                C["Castle"], 0.1),
             bx("FC_Wall_Right", (wx1 - dr, wy1 - wy0, wh), ((dr + wx1) / 2, (wy0 + wy1) / 2, z0 + wh / 2), M["marble"],
                C["Castle"], 0.1),
             bx("FC_Wall_OverDoor", (DOOR_W, wy1 - wy0, wh - DOOR_H), (DOOR_X, (wy0 + wy1) / 2, z0 + DOOR_H + (wh - DOOR_H) / 2),
                M["marble"], C["Castle"], 0.1),
             bx("FC_Wall_GoldBand", (wx1 - wx0, 0.14, 0.3), ((wx0 + wx1) / 2, wy0 - 0.05, WALL_TOP - 1.2), M["gold"],
                C["Castle"], 0.03)]
    objs += merlons("FC_Wall", wx0, wx1, wy0, wy1, WALL_TOP, C["Castle"], sides="S", step=2.2)
    for side, (a, b) in (("L", (TOWERS["OuterL"][0] + 3.3, TOWERS["InnerL"][0] - 3.5)),
                         ("R", (wx1, TOWERS["OuterR"][0] - 3.3))):
        objs.append(bx(f"FC_LinkWall{side}", (b - a, 3.0, 8.0), ((a + b) / 2, -0.5, z0 + 4.0), M["marble"], C["Castle"], 0.1))
        objs += merlons(f"FC_Link{side}", a, b, -2.0, 1.0, z0 + 8.0, C["Castle"], sides="S", step=2.0)
    # arched entrance: neon-cyan arch frame, recessed warm interior with small banners
    a_out, a_mid, a_in = arch_poly(DOOR_W + 1.3, DOOR_H + 0.65), arch_poly(DOOR_W + 0.4, DOOR_H + 0.2), \
        arch_poly(DOOR_W, DOOR_H)
    fr = frame_prism("FC_Door_Frame", a_out, a_mid, wy0 - 0.45, wy0 + 0.3, M["marble"], C["Castle"], 0.06,
                     cx=DOOR_X, cz=z0)
    neon = frame_prism("FC_Door_Neon", a_mid, a_in, wy0 - 0.35, wy0 + 0.3, M["window"], C["Castle"], 0.0,
                       cx=DOOR_X, cz=z0)
    inner = L.extrude_polygon("FC_Door_Interior", arch_poly(DOOR_W, DOOR_H), 0.4, M["door"], C["Castle"])
    inner.location = (DOOR_X, wy1 + 0.2, z0)
    objs += [fr, neon, inner]
    for k, dx in enumerate((-1.0, 1.0)):
        objs += banner(f"FC_Door_InnerBanner{k}", DOOR_X + dx, wy1 + 0.05, z0 + 4.8, 0.8, 1.8, 0.4, C["Castle"])
    # door passage side walls (so the recess reads as a corridor)
    for sx in (-1, 1):
        objs.append(bx(f"FC_Door_Jamb{sx}", (0.3, wy1 - wy0 + 0.4, DOOR_H), (DOOR_X + sx * (DOOR_W / 2 + 0.15),
                       (wy0 + wy1) / 2 + 0.2, z0 + DOOR_H / 2), M["stone_dark"], C["Castle"], 0.03))
    objs.append(bx("FC_Door_Floor", (DOOR_W, wy1 - wy0 + 0.4, 0.1), (DOOR_X, (wy0 + wy1) / 2 + 0.2, z0 + 0.05),
                   M["stone_dark"], C["Castle"], 0.0))
    # front-wall banners flanking the entrance, windows left of the keep
    objs += banner("FC_Wall_BannerL", DOOR_X - 4.2, wy0 - 0.12, WALL_TOP - 1.6, 1.9, 3.6, 0.8, C["Castle"])
    objs += banner("FC_Wall_BannerR", DOOR_X + 4.4, wy0 - 0.12, WALL_TOP - 1.6, 1.9, 3.6, 0.8, C["Castle"])
    for k, x in enumerate((-3.6, 0.6)):
        objs += window(f"FC_Wall_Win{k}", x, wy0 - 0.05, z0 + 2.6, 1.4, 3.0, C["Castle"])
    return objs


def build_stairs(C):
    objs = []
    y_top = PLAT[2]
    for k in range(STEP_N):
        top = PLAT_TOP - STEP_H * (k + 1)
        yf = y_top - STEP_D * (k + 1)
        objs.append(bx(f"FC_Step_{k}", (STAIR_W, STEP_D + 0.05, top + 0.6), (DOOR_X, yf + STEP_D / 2, (top - 0.6) / 2),
                       M["marble"], C["Stairs"], 0.08))
        objs.append(bx(f"FC_StepNeon_{k}", (STAIR_W - 0.6, 0.08, 0.14), (DOOR_X, yf - 0.02, top - 0.17), M["window"],
                       C["Stairs"], 0.0))
    y_bot = y_top - STEP_D * STEP_N
    for sx in (-1, 1):
        x = DOOR_X + sx * (STAIR_W / 2 + 0.6)
        objs.append(bx(f"FC_StairCheek_{sx}", (1.2, y_top - y_bot, 1.4), (x, (y_top + y_bot) / 2, 0.7), M["marble"],
                       C["Stairs"], 0.08))
        for tag, y, z in (("Top", y_top + 0.6, PLAT_TOP), ("Bot", y_bot + 0.6, 1.4)):
            objs += lantern(f"FC_Lantern{tag}_{sx}", x, y, z, C["Stairs"])
    return objs


def lantern(name, x, y, z, C):
    return [bx(f"{name}_Post", (1.1, 1.1, 1.8), (x, y, z + 0.9), M["marble"], C, 0.08),
            bx(f"{name}_Cap", (1.3, 1.3, 0.25), (x, y, z + 1.92), M["marble"], C, 0.05),
            bx(f"{name}_Glass", (0.75, 0.75, 1.1), (x, y, z + 2.6), M["glass"], C, 0.04),
            bx(f"{name}_Frame", (0.95, 0.95, 0.15), (x, y, z + 2.05), M["iron"], C, 0.02),
            L.cyl(f"{name}_Roof", 0.75, 0.5, (x, y, z + 3.4), M["iron"], 4, 0.03, c=C, r2=0.08, rot=(0, 0, math.pi / 4))]


def tri_count(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    t = 0
    for ob in objs:
        if ob.type != "MESH":
            continue
        me = ob.evaluated_get(dg).to_mesh()
        t += sum(len(p.vertices) - 2 for p in me.polygons)
        ob.evaluated_get(dg).to_mesh_clear()
    return t


def main(do_render=True):
    global P
    L.reset()
    P = L.palette()
    mats()
    root = L.coll("ASSET_08_FloatingCastle")
    C = {k: L.coll(f"FC_{k}", root) for k in ("Island", "Waterfall", "Castle", "Stairs")}
    objs, cells = build_island(C)
    objs += build_waterfall(C, cells)
    objs += build_castle(C)
    objs += build_stairs(C)
    mn, mx = L.bounds(objs)
    print("TRIS", tri_count(objs), "SIZE", tuple(round(v, 1) for v in (mx - mn)))
    L.save_blend("08_floating_castle.blend")
    if not do_render:
        return
    L.studio_lights()
    L.ground(z=mn.z - 3)
    items = L.inspection_set("castle", objs, res=800, samples=28, three_q=(-0.55, -1.3, 0.45), detail=[
        ("detail_entrance", (DOOR_X - 6, -26.0, 7.0), (DOOR_X - 1, -3.0, 5.0), 40),
        ("detail_waterfall", (-34.0, -38.0, -4.0), (-20.0, -16.0, -10.0), 40),
    ])
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT" or ob.name.startswith("RIG_"):
            bpy.data.objects.remove(ob)
    L.beauty_lights()
    L.setup_render((900, 506), 28)
    cam = L.camera("CAM_refmatch", (-60.0, -138.0, 36.0), (1.0, 0.0, -4.0), lens=40)
    items.append(("refmatch_3q (sky)", L.render(cam, os.path.join(L.RENDERS, "castle_refmatch.png"))))
    cam = L.camera("CAM_beauty", (70.0, -120.0, 6.0), (0.0, 0.0, -4.0), lens=38)
    items.append(("beauty_low_right (sky)", L.render(cam, os.path.join(L.RENDERS, "castle_beauty.png"))))
    L.contact_sheet(items, os.path.join(L.RENDERS, "castle_inspection_sheet.png"), cols=3, tile=560,
                    title="ASSET 08 - FLOATING CASTLE ISLAND (Blender Cycles renders)")


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
