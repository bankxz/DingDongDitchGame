"""ASSET 08 - Floating castle island (REMAKE from the dedicated castle turnaround sheet).

Primary reference: castle sheet (main 3/4, front/back/left/right ortho, top-view layout,
bottom-view underside, front-low / rear 3/4 / side 3/4, detail close-ups, modular parts,
palette, approx. dimensions ~160 w x 160 d x 120 h studs incl. island).  Image 5 is secondary.

Layout (top view): square castle on a raised paved platform in the middle of a rounded,
blocky voxel island.  Four corner towers with stepped blue pyramid roofs, crystal finials and
red pennants; crenellated curtain walls with gold bands; central square keep with a big blue
pyramid roof; front gatehouse with a glowing arched entrance flanked by two short turrets;
wide front stair with cyan risers and lantern posts; waterfall pouring off the front-left
edge; faceted polygonal boulder underside with floating rock chunks.
Style rules: crisp planar forms, masonry = flat walls with thin dark seams (no pillowy
cubes), NO vegetation (green top is a chunky ground slab only).  Front faces -Y.
Run:  python build_08_floating_castle.py [--no-render]
"""
import sys, os, math, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector, Matrix
import lobbylib as L
import build_05_arena_gate as G
from build_01_arch import star_points

# ---------------------------------------------------------------- named dimensions (studs)
ISLAND_R = 76.0                # mean island radius (sheet: ~160 wide incl. edge blocks)
CELL = 6.0                     # voxel ground cell
GRASS_T = 2.5
PLAT_HALF = 50.0               # raised paved platform (castle footprint)
PLAT_TOP = 5.0
TOWER_C = 40.0                 # corner tower centres at (+-40, +-40)
TOWER_W, TOWER_H = 15.0, 31.0
WALL_T, WALL_H = 4.0, 15.0
KEEP_W, KEEP_H = 28.0, 37.0
GATE_W, GATE_D, GATE_H = 20.0, 9.0, 21.0
GATE_Y = -TOWER_C              # gatehouse sits on the front curtain wall line
ARCH_W, ARCH_H = 9.0, 13.5
TURRET_X, TURRET_W, TURRET_H = 15.0, 8.0, 25.0
STEP_N, STEP_W = 7, 16.0
FALL_X, FALL_Y = -50.0, -58.0  # waterfall lip (front-left)

random.seed(808)
P = None
M = {}


def mats():
    M["marble"] = P["marble"]
    M["shade"] = P["marble_dark"]
    M["gold"] = P["gold"]
    M["navy"] = P["navy"]
    M["white"] = P["white"]
    M["roof"] = L.flat("MAT_RoofBlue", (0.03, 0.10, 0.62), rough=0.45)
    M["roof2"] = L.flat("MAT_RoofBlueDark", (0.02, 0.06, 0.45), rough=0.45)
    M["grass"] = L.flat("MAT_GroundGreen", (0.20, 0.58, 0.08), rough=0.85)
    M["grass2"] = L.flat("MAT_GroundGreenLight", (0.32, 0.70, 0.12), rough=0.85)
    M["rock"] = L.varied("MAT_IslandRock", [(0.40, 0.36, 0.55), (0.46, 0.42, 0.60), (0.36, 0.32, 0.50),
                                             (0.50, 0.46, 0.64)], rough=0.9)
    M["glass"] = L.emissive("MAT_WindowCyan", (0.15, 0.80, 1.0), 1.2, base=(0.35, 0.85, 1.0))
    M["neon"] = L.emissive("MAT_NeonCyan", (0.05, 0.75, 1.0), 3.2, base=(0.3, 0.9, 1.0))
    M["crystal"] = L.emissive("MAT_CastleCrystal", (0.10, 0.85, 1.0), 0.8, base=(0.35, 0.9, 1.0))
    M["warm"] = L.emissive("MAT_WarmInterior", (1.0, 0.55, 0.18), 1.6, base=(1.0, 0.75, 0.45))
    M["red"] = L.flat("MAT_PennantRed", (0.85, 0.04, 0.05), rough=0.6)
    M["water"] = L.glass_emissive("MAT_WaterfallCyan", (0.25, 0.85, 1.0), 1.1, alpha=0.85)
    M["iron"] = L.flat("MAT_LanternIron", (0.13, 0.15, 0.22), rough=0.45, metal=0.6)
    M["mortar"] = L.flat("MAT_CastleMortar", (0.66, 0.62, 0.76), rough=0.9)


def flat_blocks(name, x0, x1, z0, z1, y0, y1, c, mat=None, bw=4.0, bh=2.3, seed=0, skip=None):
    """Flat ashlar wall (arena-gate helper); bevel stripped - crisp, cheap distant asset."""
    ob = G.blocks(name, x0, x1, z0, z1, y0, y1, mat or M["marble"], c, bw=bw, bh=bh, seed=seed, skip=skip)
    ob.modifiers.clear()
    if len(ob.data.materials) > 1:      # subtle seams: the sheet's joints are light, not dark lines
        ob.data.materials[1] = M["mortar"]
    return ob


def box(name, size, loc, mat, c, rot=(0, 0, 0)):
    return L.box(name, size, loc, mat, 0.0, c=c, rot=rot)


# ---------------------------------------------------------------- island
def radius(a):
    return ISLAND_R + 5.0 * math.sin(3 * a + 1.0) + 3.0 * math.sin(5 * a + 2.3) + 2.0 * math.sin(7 * a + 0.4)


def inside(x, y, pad=0.0):
    return math.hypot(x, y) < radius(math.atan2(y, x)) - pad


def build_island(C):
    objs = []
    rnd = random.Random(3)
    cells = []
    n = int(ISLAND_R * 1.2 / CELL) + 1
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = (i + 0.5) * CELL, (j + 0.5) * CELL
            if inside(x, y):
                cells.append((x, y))
    cset = {(round(x / CELL - 0.5), round(y / CELL - 0.5)) for x, y in cells}

    def is_edge(x, y):
        i, j = round(x / CELL - 0.5), round(y / CELL - 0.5)
        return any((i + di, j + dj) not in cset for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)))

    bm_g, bm_g2, bm_r = bmesh.new(), bmesh.new(), bmesh.new()
    for x, y in cells:
        edge = is_edge(x, y)
        top = 0.0 + (rnd.choice((0.0, 0.0, 0.8, -0.8, 1.4)) if edge else 0.0)
        tgt = bm_g2 if rnd.random() < 0.3 else bm_g
        m = Matrix.Translation((x, y, top - GRASS_T / 2)) @ Matrix.Diagonal((CELL, CELL, GRASS_T, 1))
        bmesh.ops.create_cube(tgt, size=1.0, matrix=m)
        depth = rnd.uniform(8.0, 14.0) if edge else 10.0     # thick stepped rock band (sheet sides)
        zr0 = top - GRASS_T
        m = Matrix.Translation((x, y, zr0 - depth / 2)) @ Matrix.Diagonal((CELL, CELL, depth, 1))
        bmesh.ops.create_cube(bm_r, size=1.0, matrix=m)
    for bm in (bm_g, bm_g2):
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    objs.append(L.from_bmesh("FC_IslandGround", bm_g, M["grass"], C["Island"]))
    objs.append(L.from_bmesh("FC_IslandGroundLight", bm_g2, M["grass2"], C["Island"]))
    objs.append(L.from_bmesh("FC_IslandRockLayer", bm_r, M["rock"], C["Island"]))

    # faceted polygonal boulder underside (bottom view): rings of low-poly boulders tapering down
    k = 0
    rings = [(0.84, -14.0, 17, 25.0), (0.62, -21.0, 13, 25.0), (0.40, -28.0, 9, 23.0), (0.17, -35.0, 5, 21.0)]
    for frac, zc, count, size in rings:
        for q in range(count):
            a = 2 * math.pi * q / count + rnd.uniform(-0.2, 0.2) + frac
            r = frac * ISLAND_R * rnd.uniform(0.85, 1.05)
            k += 1
            objs.append(boulder(f"FC_Boulder_{k:02d}", (r * math.cos(a), r * math.sin(a), zc + rnd.uniform(-3, 3)),
                                size * rnd.uniform(0.8, 1.15), rnd, C["Island"]))
    objs.append(boulder("FC_Boulder_Tip", (4.0, -2.0, -43.0), 15.0, rnd, C["Island"]))
    # floating rock chunks below the island
    for q in range(10):
        a = rnd.uniform(0, 2 * math.pi)
        r = rnd.uniform(20, 70)
        objs.append(boulder(f"FC_Chunk_{q:02d}", (r * math.cos(a), r * math.sin(a), rnd.uniform(-62, -44)),
                            rnd.uniform(2.5, 5.0), rnd, C["Island"], subdiv=1))
    return objs


def boulder(name, loc, size, rnd, c, subdiv=1):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=size / 2)
    for v in bm.verts:            # break the symmetry: faceted, irregular rock
        v.co *= rnd.uniform(0.82, 1.12)
    ob = L.from_bmesh(name, bm, M["rock"], c)
    ob.location = loc
    ob.scale = (1.0, rnd.uniform(0.9, 1.15), rnd.uniform(0.85, 1.05))
    ob.rotation_euler = (rnd.uniform(0, 3), rnd.uniform(0, 3), rnd.uniform(0, 3))
    for p in ob.data.polygons:
        p.use_smooth = False
    return ob


# ---------------------------------------------------------------- castle details
def arch_poly(w, h, seg=6):
    """Round-headed arch outline (x, z), CCW, base at z=0."""
    r = w / 2
    pts = [(r, 0.0), (r, h - r)]
    for i in range(1, seg):
        a = math.pi * i / seg
        pts.append((r * math.cos(a), h - r + r * math.sin(a)))
    pts += [(-r, h - r), (-r, 0.0)]
    return pts


def window(name, x, y, z, w, h, c, yaw=0.0):
    """Arched cyan window: marble surround, glowing glass, white cross mullions."""
    o = []
    surround = G.frame_prism(f"{name}_Frame", arch_poly(w + 0.7, h + 0.35), arch_poly(w, h), -0.25, 0.15,
                             M["marble"], c, 0.0)
    glass = L.extrude_polygon(f"{name}_Glass", arch_poly(w, h), 0.12, M["glass"], c)
    glass.location.y = 0.08
    mv = box(f"{name}_MullionV", (0.16, 0.1, h - 0.2), (0, -0.02, h / 2), M["white"], c)
    mh = box(f"{name}_MullionH", (w, 0.1, 0.16), (0, -0.02, h * 0.55), M["white"], c)
    for ob in (surround, glass, mv, mh):
        ob.location = Matrix.Rotation(yaw, 3, "Z") @ Vector(ob.location) + Vector((x, y, z))
        ob.rotation_euler.z += yaw
        o.append(ob)
    return o


def banner(name, x, y, top, w, h1, pd, c, yaw=0.0):
    outline = [(-w / 2, 0), (w / 2, 0), (w / 2, -h1), (0, -h1 - pd), (-w / 2, -h1)]
    inner = [(-w / 2 + 0.25, -0.2), (w / 2 - 0.25, -0.2), (w / 2 - 0.25, -h1 + 0.1), (0, -h1 - pd + 0.45),
             (-w / 2 + 0.25, -h1 + 0.1)]
    t = L.extrude_polygon(f"{name}_Trim", outline, 0.14, M["gold"], c)
    cl = L.extrude_polygon(f"{name}_Cloth", inner, 0.22, M["navy"], c)
    st = L.extrude_polygon(f"{name}_Star", star_points(w * 0.42, w * 0.3, w * 0.14, w * 0.07), 0.06, M["white"], c,
                           center_depth=False)
    rod = L.cyl(f"{name}_Rod", 0.14, w + 0.8, (0, 0, 0.15), M["gold"], 10, 0.0, c=c, rot=(0, math.pi / 2, 0))
    o = []
    for ob, off in ((t, (0, 0, top)), (cl, (0, 0, top)), (st, (0, -0.17, top - h1 * 0.47)), (rod, (0, 0, top + 0.15))):
        ob.location = Matrix.Rotation(yaw, 3, "Z") @ Vector(off) + Vector((x, y, 0))
        ob.rotation_euler.z += yaw
        o.append(ob)
    return o


def stepped_roof(name, cx, cy, z0, base, c, layers=6, lh=2.3, top_w=2.0, pennant=True):
    """Voxel-stepped square pyramid roof + gold collar + crystal finial + red pennant."""
    o = []
    for k in range(layers):
        w = base - (base - top_w) * k / (layers - 1)
        o.append(box(f"{name}_Step{k}", (w, w, lh), (cx, cy, z0 + lh * (k + 0.5)), M["roof"] if k % 2 == 0 else
                     M["roof2"], c))
    zt = z0 + lh * layers
    o.append(box(f"{name}_Collar", (top_w + 0.6, top_w + 0.6, 0.5), (cx, cy, zt + 0.25), M["gold"], c))
    o.append(G.crystal(f"{name}_Crystal", base * 0.09, base * 0.30, base * 0.06, (cx, cy, zt + 0.5 + base * 0.06),
                       M["crystal"], c))
    if pennant:
        ph = base * 0.55
        pz = zt + 0.5
        px = cx + top_w * 0.15
        o.append(L.cyl(f"{name}_Pole", 0.16, ph, (px, cy, pz + ph / 2), M["gold"], 8, 0.0, c=c))
        o.append(L.cyl(f"{name}_PoleKnob", 0.32, 0.5, (px, cy, pz + ph + 0.2), M["gold"], 8, 0.0, c=c))
        fl = L.extrude_polygon(f"{name}_Pennant", [(0, 0), (0, -2.2), (4.6, -1.4), (3.4, -1.1), (4.6, -0.6)], 0.12,
                               M["red"], c)
        fl.location = (px + 0.1, cy, pz + ph)
        o.append(fl)
    return o


def crenellate(prefix, x0, x1, y, z, c, depth, along="X", mw=1.8, gap=1.4, mh=1.8):
    """Merlons along a wall top (flat, crisp)."""
    o = []
    L_ = (x1 - x0)
    n = max(1, int((L_ + gap) / (mw + gap)))
    step = L_ / n
    for k in range(n):
        p = x0 + step * (k + 0.5)
        loc = (p, y, z + mh / 2) if along == "X" else (y, p, z + mh / 2)
        size = (mw, depth, mh) if along == "X" else (depth, mw, mh)
        o.append(box(f"{prefix}_{k:02d}", size, loc, M["marble"], c))
    return o


def tower(name, cx, cy, w, h, c, roof_layers=6, windows=2, banners=False):
    """Square tower: flat ashlar body, gold bands, overhanging crenellated cap, stepped roof."""
    o = []
    z0 = PLAT_TOP
    o.append(box(f"{name}_Core", (w - 0.2, w - 0.2, h), (cx, cy, z0 + h / 2), M["shade"], c))
    o.append(flat_blocks(f"{name}_Body", cx - w / 2, cx + w / 2, z0, z0 + h, cy - w / 2, cy + w / 2, c,
                         bw=5.4, bh=3.4, seed=seed_of(name)))
    for zb in (z0 + h * 0.62, z0 + h - 1.6):
        o.append(box(f"{name}_Gold_{zb:.0f}", (w + 0.3, w + 0.3, 0.6), (cx, cy, zb), M["gold"], c))
    cap_w = w + 2.0
    o.append(box(f"{name}_Cap", (cap_w, cap_w, 1.6), (cx, cy, z0 + h + 0.8), M["marble"], c))
    zc = z0 + h + 1.6
    for s, (yy, ax) in enumerate(((cy - cap_w / 2 + 0.6, "X"), (cy + cap_w / 2 - 0.6, "X"))):
        o += crenellate(f"{name}_Merlon{s}", cx - cap_w / 2 + 0.6, cx + cap_w / 2 - 0.6, yy, zc, c, 1.2)
    for s, xx in enumerate((cx - cap_w / 2 + 0.6, cx + cap_w / 2 - 0.6)):
        o += crenellate(f"{name}_MerlonS{s}", cy - cap_w / 2 + 1.8, cy + cap_w / 2 - 1.8, xx, zc, c, 1.2, along="Y")
    o += stepped_roof(f"{name}_Roof", cx, cy, zc + 0.4, w * 0.95, c, layers=roof_layers)
    # windows on all four faces (front ones also on the lower level)
    for yaw, (dx, dy) in ((0.0, (0, -1)), (math.pi, (0, 1)), (math.pi / 2, (1, 0)), (-math.pi / 2, (-1, 0))):
        for lvl in range(windows):
            zw = z0 + h * (0.30 + 0.40 * lvl)
            o += window(f"{name}_Win_{int(math.degrees(yaw))}_{lvl}", cx + dx * (w / 2 + 0.05),
                        cy + dy * (w / 2 + 0.05), zw, 2.4, 4.6, c, yaw=yaw)
    if banners:
        o += banner(f"{name}_Banner", cx, cy - w / 2 - 0.4, z0 + h * 0.58, 3.2, 6.5, 1.4, c)
    return o


def wall(name, p0, p1, c):
    """Crenellated curtain wall between two end points (axis-aligned), gold band, coping."""
    o = []
    a, b = Vector(p0), Vector(p1)
    d = b - a
    ln = d.length
    mid = (a + b) / 2
    along_x = abs(d.x) > abs(d.y)
    ob = flat_blocks(f"{name}_Blocks", -ln / 2, ln / 2, PLAT_TOP, PLAT_TOP + WALL_H, -WALL_T / 2, WALL_T / 2, c,
                     bw=6.0, bh=3.4, seed=seed_of(name))
    ob.location = (mid.x, mid.y, 0)
    if not along_x:
        ob.rotation_euler.z = math.pi / 2
    o.append(ob)
    size = (ln, WALL_T + 0.3, 0.6) if along_x else (WALL_T + 0.3, ln, 0.6)
    o.append(box(f"{name}_Gold", size, (mid.x, mid.y, PLAT_TOP + WALL_H - 2.2), M["gold"], c))
    size = (ln, WALL_T + 0.8, 0.9) if along_x else (WALL_T + 0.8, ln, 0.9)
    o.append(box(f"{name}_Coping", size, (mid.x, mid.y, PLAT_TOP + WALL_H + 0.45), M["marble"], c))
    zc = PLAT_TOP + WALL_H + 0.9
    for s in (-1, 1):
        if along_x:
            o += crenellate(f"{name}_Merlon{s}", mid.x - ln / 2, mid.x + ln / 2, mid.y + s * (WALL_T / 2), zc, c, 1.0)
        else:
            o += crenellate(f"{name}_Merlon{s}", mid.y - ln / 2, mid.y + ln / 2, mid.x + s * (WALL_T / 2), zc, c, 1.0,
                            along="Y")
    return o


def seed_of(name):
    return sum(map(ord, name)) % 997


def lantern(name, x, y, z, c):
    o = [box(f"{name}_Post", (1.4, 1.4, 3.2), (x, y, z + 1.6), M["marble"], c),
         box(f"{name}_Band", (1.55, 1.55, 0.3), (x, y, z + 2.6), M["gold"], c),
         box(f"{name}_Base", (1.5, 1.5, 0.3), (x, y, z + 3.35), M["iron"], c),
         box(f"{name}_Glass", (1.1, 1.1, 1.6), (x, y, z + 4.3), M["glass"], c),
         box(f"{name}_Top", (1.6, 1.6, 0.3), (x, y, z + 5.25), M["iron"], c),
         L.cyl(f"{name}_Roof", 1.15, 0.8, (x, y, z + 5.8), M["iron"], 4, 0.0, c=c, r2=0.1, rot=(0, 0, math.pi / 4))]
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(box(f"{name}_Bar{sx}{sy}", (0.16, 0.16, 1.7), (x + sx * 0.56, y + sy * 0.56, z + 4.3), M["iron"], c))
    return o


def slab_with_hole(name, outer, inner, y0, y1, mat, c):
    """Extrude an (x,z) outline with an inner hole along y (gatehouse with arched passage)."""
    bm = bmesh.new()
    vo = [bm.verts.new((x, y0, z)) for x, z in outer]
    vi = [bm.verts.new((x, y0, z)) for x, z in inner]
    edges = [bm.edges.new((vo[i], vo[(i + 1) % len(vo)])) for i in range(len(vo))]
    edges += [bm.edges.new((vi[i], vi[(i + 1) % len(vi)])) for i in range(len(vi))]
    bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=edges)
    faces = list(bm.faces)
    ext = bmesh.ops.extrude_face_region(bm, geom=faces)
    verts = [v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0, y1 - y0, 0), verts=verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return L.from_bmesh(name, bm, mat, c)


def build_castle(C):
    o = []
    c = C["Castle"]
    # raised paved platform with flat ashlar sides
    o.append(box("FC_Platform", (2 * PLAT_HALF, 2 * PLAT_HALF, PLAT_TOP + 0.5), (0, 0, PLAT_TOP / 2 - 0.25),
                 M["shade"], C["Platform"]))
    o.append(box("FC_PlatformPaving", (2 * PLAT_HALF - 0.6, 2 * PLAT_HALF - 0.6, 0.2), (0, 0, PLAT_TOP + 0.1),
                 M["marble"], C["Platform"]))
    for s, (yy, rot) in enumerate(((-PLAT_HALF, 0.0), (PLAT_HALF, 0.0))):
        sk = (lambda x, z: abs(x) < STEP_W / 2 + 1.5) if yy < 0 else None
        ob = flat_blocks(f"FC_PlatformSide{s}", -PLAT_HALF, PLAT_HALF, 0.0, PLAT_TOP - 0.05, yy - 0.4, yy + 0.4,
                         C["Platform"], bw=6.0, bh=2.5, seed=40 + s, skip=sk)
        o.append(ob)
    for s, xx in enumerate((-PLAT_HALF, PLAT_HALF)):
        ob = flat_blocks(f"FC_PlatformSideX{s}", -PLAT_HALF, PLAT_HALF, 0.0, PLAT_TOP - 0.05, -0.4, 0.4, C["Platform"],
                         bw=6.0, bh=2.5, seed=50 + s)
        ob.rotation_euler.z = math.pi / 2
        ob.location.x = xx
        o.append(ob)
    o.append(box("FC_PlatformGold", (2 * PLAT_HALF + 1.0, 2 * PLAT_HALF + 1.0, 0.45), (0, 0, PLAT_TOP - 0.25),
                 M["gold"], C["Platform"]))

    # corner towers (front two carry banners like the sheet's main view)
    T = TOWER_C
    for name, (x, y) in {"FL": (-T, -T), "FR": (T, -T), "BL": (-T, T), "BR": (T, T)}.items():
        o += tower(f"FC_Tower{name}", x, y, TOWER_W, TOWER_H, c, roof_layers=6, windows=2, banners=(y < 0))
    # curtain walls (front wall is split by the gatehouse)
    h = TOWER_W / 2
    for name, a, b in (("Back", (-T + h, T), (T - h, T)), ("Left", (-T, -T + h), (-T, T - h)),
                       ("Right", (T, -T + h), (T, T - h)), ("FrontL", (-T + h, -T), (-GATE_W / 2, -T)),
                       ("FrontR", (GATE_W / 2, -T), (T - h, -T))):
        o += wall(f"FC_Wall{name}", a, b, c)
    # windows along the curtain walls (outer faces)
    for xx in (-27.0, -18.0, 18.0, 27.0, -9.0, 0.0, 9.0):
        o += window(f"FC_WallWinB_{xx:+.0f}", xx, T + WALL_T / 2 + 0.05, PLAT_TOP + 6.0, 2.2, 4.2, c, yaw=math.pi)
    for yy in (-22.0, -8.0, 8.0, 22.0):
        o += window(f"FC_WallWinL_{yy:+.0f}", -T - WALL_T / 2 - 0.05, yy, PLAT_TOP + 6.0, 2.2, 4.2, c, yaw=-math.pi / 2)
        o += window(f"FC_WallWinR_{yy:+.0f}", T + WALL_T / 2 + 0.05, yy, PLAT_TOP + 6.0, 2.2, 4.2, c, yaw=math.pi / 2)
    for xx in (-27.0, 27.0):
        o += window(f"FC_WallWinF_{xx:+.0f}", xx, -T - WALL_T / 2 - 0.05, PLAT_TOP + 6.0, 2.2, 4.2, c)

    # central keep
    o += tower("FC_Keep", 0.0, 4.0, KEEP_W, KEEP_H, c, roof_layers=7, windows=2, banners=False)
    o += banner("FC_KeepBanner", 0.0, 4.0 - KEEP_W / 2 - 0.4, PLAT_TOP + KEEP_H * 0.80, 5.0, 9.0, 2.0, c)

    # gatehouse: solid body with an arched passage, flat ashlar face, glowing arch lining, warm interior
    gy0, gy1 = GATE_Y - GATE_D / 2 - 1.0, GATE_Y + GATE_D / 2
    outer = [(GATE_W / 2, 0.0), (GATE_W / 2, GATE_H), (-GATE_W / 2, GATE_H), (-GATE_W / 2, 0.0)]
    inner = arch_poly(ARCH_W, ARCH_H)
    inner = [(x, max(z, 0.05)) for x, z in inner][::-1]
    body = slab_with_hole("FC_GateBody", outer, inner, gy0 + 0.4, gy1, M["shade"], c)
    body.location.z = PLAT_TOP
    o.append(body)
    face = flat_blocks("FC_GateFace", -GATE_W / 2, GATE_W / 2, PLAT_TOP, PLAT_TOP + GATE_H, gy0, gy0 + 0.45, c,
                       bw=4.6, bh=3.0, seed=77,
                       skip=lambda x, z: abs(x) < ARCH_W / 2 + 0.9 and (z - PLAT_TOP) < ARCH_H + 0.9)
    o.append(face)
    ring = G.frame_prism("FC_GateArchRing", arch_poly(ARCH_W + 2.4, ARCH_H + 1.2), arch_poly(ARCH_W, ARCH_H),
                         gy0 - 0.35, gy0 + 1.6, M["marble"], c, 0.0, cz=PLAT_TOP)
    o.append(ring)
    neon = G.frame_prism("FC_GateArchNeon", arch_poly(ARCH_W + 0.7, ARCH_H + 0.35), arch_poly(ARCH_W, ARCH_H),
                         gy0 - 0.45, gy0 + 0.2, M["neon"], c, 0.0, cz=PLAT_TOP)
    o.append(neon)
    o.append(box("FC_GateInterior", (ARCH_W + 0.4, 0.4, ARCH_H + 0.5), (0, gy1 - 0.3, PLAT_TOP + ARCH_H / 2),
                 M["warm"], c))
    for s in (-1, 1):
        o += banner(f"FC_GateInBanner{s}", s * 2.4, gy1 - 0.8, PLAT_TOP + ARCH_H * 0.75, 1.3, 2.6, 0.6, c)
        o += banner(f"FC_GateBanner{s}", s * (ARCH_W / 2 + 3.4), gy0 - 0.3, PLAT_TOP + GATE_H - 3.0, 3.0, 7.0, 1.4, c)
    o.append(box("FC_GateGold", (GATE_W + 0.4, GATE_D + 1.4, 0.6), (0, GATE_Y - 0.5, PLAT_TOP + GATE_H - 1.2),
                 M["gold"], c))
    o.append(box("FC_GateCap", (GATE_W + 1.6, GATE_D + 2.6, 1.4), (0, GATE_Y - 0.5, PLAT_TOP + GATE_H + 0.7),
                 M["marble"], c))
    o += crenellate("FC_GateMerlonF", -GATE_W / 2, GATE_W / 2, gy0 - 0.7, PLAT_TOP + GATE_H + 1.4, c, 1.2)
    # turrets flanking the gatehouse (shorter, smaller roofs - front ortho)
    for s in (-1, 1):
        o += tower(f"FC_Turret{'L' if s < 0 else 'R'}", s * TURRET_X, GATE_Y - 1.0, TURRET_W, TURRET_H, c,
                   roof_layers=5, windows=1)
    return o


def build_stairs(C):
    o = []
    c = C["Stairs"]
    rise = PLAT_TOP / STEP_N
    run = 1.8
    y_top = -PLAT_HALF
    for k in range(STEP_N):
        ztop = PLAT_TOP - rise * k
        y_front = y_top - run * (k + 1)
        o.append(box(f"FC_Step_{k}", (STEP_W, run * (k + 1) + 0.6, rise), (0, y_top - (run * (k + 1)) / 2 + 0.3,
                                                                             ztop - rise / 2), M["marble"], c))
        o.append(box(f"FC_StepNeon_{k}", (STEP_W - 1.6, 0.12, rise * 0.4), (0, y_front - 0.05, ztop - rise * 0.55),
                     M["neon"], c))
    # stair cheek walls + lanterns (bottom and top, both sides)
    yb = y_top - run * STEP_N
    for s in (-1, 1):
        x = s * (STEP_W / 2 + 0.95)          # inner face 0.05 outside the step ends (no coplanar faces)
        o.append(box(f"FC_StairCheek{s}", (1.8, run * STEP_N, PLAT_TOP), (x, y_top - run * STEP_N / 2, PLAT_TOP / 2 - 0.4),
                     M["marble"], c))
        o += lantern(f"FC_LanternLow{s}", x, yb + 1.0, 0.0, c)
        o += lantern(f"FC_LanternTop{s}", x, y_top - 1.0, PLAT_TOP, c)
    return o


def build_waterfall(C):
    """Pool/stream on the front-left ground running to the edge, then a blocky stepped fall."""
    o = []
    c = C["Waterfall"]
    a = math.atan2(FALL_Y, FALL_X)
    r_edge = radius(a) + 4.5            # past the blocky edge cells
    ex, ey = r_edge * math.cos(a), r_edge * math.sin(a)
    sx, sy = -PLAT_HALF + 4.0, -PLAT_HALF + 4.0
    d = Vector((ex - sx, ey - sy))
    ang = math.atan2(d.y, d.x)
    o.append(box("FC_Stream", (d.length + 2.0, 9.0, 0.5), ((sx + ex) / 2, (sy + ey) / 2, 0.1), M["water"], c,
                 rot=(0, 0, ang)))
    # falling sheet: three stepped slabs, widest at the bottom (blocky, as on the sheet's waterfall edge)
    n = Vector((math.cos(ang), math.sin(ang), 0))
    for k, (w, z0, z1, t, out) in enumerate(((9.0, -2.0, -26.0, 2.0, 0.9), (10.0, -26.0, -54.0, 2.2, 1.6),
                                             (11.0, -54.0, -72.0, 2.4, 2.3))):
        p = Vector((ex, ey, 0)) + n * out
        o.append(box(f"FC_Fall_{k}", (t, w, z0 - z1), (p.x, p.y, (z0 + z1) / 2), M["water"], c, rot=(0, 0, ang)))
    o.append(box("FC_FallLip", (2.2, 9.6, 1.0), (ex + n.x * 0.6, ey + n.y * 0.6, -0.4), M["water"], c, rot=(0, 0, ang)))
    return o


def tri_count(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    t = 0
    for ob in objs:
        if ob.type == "MESH":
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
    C = {k: L.coll(f"FC_{k}", root) for k in ("Island", "Platform", "Castle", "Stairs", "Waterfall")}
    objs = build_island(C) + build_castle(C) + build_stairs(C) + build_waterfall(C)
    mn, mx = L.bounds(objs)
    print("TRIS", tri_count(objs), "SIZE", tuple(round(v, 1) for v in (mx - mn)), "MINZ", round(mn.z, 1),
          "MAXZ", round(mx.z, 1))
    L.save_blend("08_floating_castle.blend")
    if not do_render:
        return
    L.studio_lights()
    L.ground(z=mn.z - 0.5)
    items = L.inspection_set("castle", objs, res=800, samples=24, three_q=(-0.75, -1.25, 0.6))
    ctr = (mn + mx) / 2
    cam = L.camera("CAM_top", (ctr.x, ctr.y, 400), (ctr.x, ctr.y, 0), ortho=max(mx.x - mn.x, mx.y - mn.y) * 1.08)
    cam.rotation_euler = (0, 0, 0)
    items.append(("top (layout)", L.render(cam, os.path.join(L.RENDERS, "castle_top.png"))))
    for ob in list(bpy.data.objects):
        if ob.name.startswith("RIG_Ground"):
            bpy.data.objects.remove(ob)
    cam = L.camera("CAM_bottom", (ctr.x + 0.01, ctr.y, -400), (ctr.x, ctr.y, 0), ortho=max(mx.x - mn.x, mx.y - mn.y) * 1.08)
    items.append(("bottom (underside)", L.render(cam, os.path.join(L.RENDERS, "castle_bottom.png"))))
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT":
            bpy.data.objects.remove(ob)
    L.beauty_lights()
    L.setup_render((900, 600), 28)
    cam = L.camera("CAM_refmatch", (-150.0, -235.0, 95.0), (0.0, 0.0, 6.0), lens=40)
    items.append(("refmatch main 3/4 (sky)", L.render(cam, os.path.join(L.RENDERS, "castle_refmatch.png"))))
    cam = L.camera("CAM_beauty", (0.0, -300.0, 20.0), (0.0, 0.0, 12.0), lens=42)
    items.append(("refmatch front (sky)", L.render(cam, os.path.join(L.RENDERS, "castle_beauty.png"))))
    L.contact_sheet(items, os.path.join(L.RENDERS, "castle_inspection_sheet.png"), cols=3, tile=560,
                    title="ASSET 08 - FLOATING CASTLE ISLAND (remake from castle sheet)  Blender Cycles renders")


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
