"""Lobby map assembly - single source of truth for the Roblox layout.

Plan coordinates (Blender): +X right, +Y toward the arena gate, +Z up, 1 unit = 1 stud,
deck top at z = 0.  Roblox conversion (FBX -Z forward / Y up):  (x, y, z) -> (x, z, -y).

This script
  1. appends every kit asset from blend/*.blend as collection instances,
  2. places them by the layout below (same rule the Luau assembler uses: each unit is
     positioned by its axis-aligned bounding-box bottom-centre B: rotate about B, move B to target),
  3. builds the island deck / underside as plain boxes and cylinders (Roblox Parts in Studio),
  4. renders preview views (spawn view, aerial, plan, plaza) to renders/lobby_*.png,
  5. writes src/shared/LobbyLayout.luau (data only) for src/shared/LobbyAssembler.luau.

Layout (from the aerial / spawn-view references):
  spawn plaza at the south (origin) -> 7 cobble road tiles north -> arena gate.
  Arches (column + half arch, mirrored pair) every 16 studs spanning the road; ability
  pedestals between the arch columns facing the spawn diagonally; shops on an east terrace,
  an overlook terrace with planters/lanterns to the west; marble balustrade around the
  whole island (module grid: every straight edge is 12 + 10n studs long so the kit fits
  exactly); EVENTS banner hanging under the first arch.
Run: python lobby_layout.py [--no-render]
"""
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Matrix
import lobbylib as L

# ------------------------------------------------------------------ named dimensions (studs)
DECK_TOP = 0.0
DECK_THICK = 2.5
PLAZA_R = 15.6                  # spawn plaza outer curb radius (asset 06)
PLAZA_LIFT = 0.2                # plaza base top sits 0.05 above the deck
RING_SCALE = 15.1 / 16.0        # curved balustrade module is built at R=16; sits on the plaza curb (R 15.1)
ROAD_TILE = 16.0
N_ROAD = 5
ROAD_Y0 = PLAZA_R
ROAD_Y1 = ROAD_Y0 + N_ROAD * ROAD_TILE      # 127.6 - gate steps start here
ROAD_LIFT = 0.06                # cobble surface 0.06 above deck (no coplanar faces)
ARCH_HALF_SPAN = 15.0           # column centre -> crown (arch module CROWN.x - COL_X)
ARCH_LOCAL_Y = 0.9              # arch plane offset inside the arch module (COL_Y)
ARCH_Y = [22.0 + 16.0 * k for k in range(5)]
PED_X = 10.5
ISLAND_HALF = 31.0              # balustrade line of the main deck
TERRACE_OUT = 43.0
TERRACE_Y0, TERRACE_Y1 = 42.0, 84.0
NORTH_Y = 116.0             # (31,84)->(31,116) = 32 = 12 + 2*10
EDGE_OVERHANG = 1.2             # deck extends past the balustrade line
MODE_PORTAL_Y = (53.0, 73.0)    # DUELS / PRACTICE portal centres on the west terrace
PORTAL_BACK_TO_PLANE = 3.5      # mode portal: bbox back (plinth back) -> portal plane (asset 07 local y=0)
PORTAL_TRIGGER_CZ = 6.0
# background castle islands: (x, y, z bottom, yaw, scale) - far enough to read as sky dressing
CASTLES = [(-115.0, 35.0, -22.0, 25.0, 1.0), (125.0, 95.0, -6.0, -35.0, 0.8), (-92.0, 107.0, 24.0, 35.0, 0.6),
           (105.0, -45.0, -30.0, -120.0, 0.7), (92.0, 107.0, 33.0, -35.0, 0.6), (-60.0, -95.0, -40.0, 150.0, 0.55)]

ROOT_BLEND = L.BLEND
UNIT_SOURCES = {
    "Lobby_ArchSpan": ("01_marble_arch.blend", ["ARCH_Column", "ARCH_Arch", "ARCH_Banner"]),
    "Lobby_MarketShop": ("03_market_shop.blend", ["ASSET_03_MarketShop"]),
    "Lobby_CraftShop": ("04_craft_shop.blend", ["ASSET_04_CraftShop"]),
    "Lobby_ArenaGate": ("05_arena_gate.blend", ["ASSET_05_ArenaGate"]),
}
for g in ("Crystal", "Lightning", "Shield", "Flame", "Wind", "Emerald", "Sun", "Orb", "Wings"):
    UNIT_SOURCES[f"Lobby_PED_{g}"] = ("02_ability_pedestals.blend", [f"PED_{g}"])
UNIT_SOURCES["Lobby_PORTAL_Duels"] = ("07_mode_portals.blend", ["MP_Duels"])
UNIT_SOURCES["Lobby_PORTAL_Practice"] = ("07_mode_portals.blend", ["MP_Practice"])
if os.path.exists(os.path.join(L.BLEND, "08_floating_castle.blend")):
    UNIT_SOURCES["Lobby_FloatingCastle"] = ("08_floating_castle.blend", ["ASSET_08_FloatingCastle"])
for p in ("BalustradeStraight", "BalustradeCorner", "BalustradeCurved", "LanternPost", "PlanterLong",
          "PlanterSquare", "EventsBanner", "StarBanner", "RoadCobble", "SpawnPlaza", "StonePost"):
    UNIT_SOURCES[f"Lobby_PROP_{p}"] = ("06_props.blend", [f"PROP_{p}"])

PLACEMENTS = []      # dicts for the Luau layout
TRIGGERS = []        # invisible teleport zones (Studio Parts; gameplay scripts hook these)
PARTS = []           # island deck / underside primitives
_SRC = {}            # unit -> (collection, B0 local bottom-centre)


# ------------------------------------------------------------------ kit loading
def load_units():
    by_file = {}
    for unit, (f, colls) in UNIT_SOURCES.items():
        by_file.setdefault(f, set()).update(colls)
    loaded = {}
    for f, names in by_file.items():
        with bpy.data.libraries.load(os.path.join(ROOT_BLEND, f), link=False) as (src, dst):
            dst.collections = [n for n in names if n in src.collections]
        for c in dst.collections:
            loaded[(f, c.name.split(".")[0])] = c
    kit = L.coll("KIT_Sources")
    for unit, (f, colls) in UNIT_SOURCES.items():
        u = bpy.data.collections.new(f"UNIT_{unit}")
        kit.children.link(u)
        for n in colls:
            u.children.link(loaded[(f, n)])
        bpy.context.view_layer.update()
        objs = [o for o in u.all_objects if o.type == "MESH"]
        mn, mx = L.bounds(objs)
        b0 = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
        u.instance_offset = b0
        _SRC[unit] = (u, b0, mx - mn)
    # sources stay out of the render
    bpy.context.view_layer.layer_collection.children["KIT_Sources"].exclude = True


# ------------------------------------------------------------------ placement API
LOBBY = None


def _emit(unit, zone, T_lin, target, yaw, scale, stretch, mirror):
    roblox_unit = "Lobby_ArchSpanMirrored" if (mirror and unit == "Lobby_ArchSpan") else unit
    PLACEMENTS.append({"unit": roblox_unit, "zone": zone, "target": [round(v, 4) for v in target],
                       "yaw": round(yaw, 4), "scale": round(scale, 5),
                       "stretch": [round(v, 5) for v in stretch]})


def place_T(unit, zone, loc, yaw_deg=0.0, scale=1.0, stretch=(1, 1, 1), mirror=False):
    """Place a unit by its authored local frame: world = T(local),
    T = Translate(loc) * RotZ(yaw) * Scale(scale * stretch * mirror)."""
    coll, b0, _ = _SRC[unit]
    yaw = math.radians(yaw_deg)
    S = Matrix.Diagonal((scale * stretch[0] * (-1 if mirror else 1), scale * stretch[1], scale * stretch[2], 1))
    T = Matrix.Translation(loc) @ Matrix.Rotation(yaw, 4, "Z") @ S
    target = T @ b0
    _instance(unit, zone, T @ Matrix.Translation(b0))
    _emit(unit, zone, T, target, yaw_deg, scale, stretch, mirror)
    return target


def place_B(unit, zone, target, yaw_deg=0.0, scale=1.0):
    """Place a unit so its bounding-box bottom-centre lands on `target` (rotated about it)."""
    coll, b0, _ = _SRC[unit]
    E = Matrix.Translation(target) @ Matrix.Rotation(math.radians(yaw_deg), 4, "Z") @ Matrix.Scale(scale, 4)
    _instance(unit, zone, E)
    _emit(unit, zone, E, Vector(target), yaw_deg, scale, (1, 1, 1), False)


def _instance(unit, zone, E):
    coll = _SRC[unit][0]
    zc = L.coll(f"LOBBY_{zone}", LOBBY)
    e = bpy.data.objects.new(f"{unit}_{len(PLACEMENTS):03d}", None)
    e.instance_type = "COLLECTION"
    e.instance_collection = coll
    zc.objects.link(e)
    e.matrix_world = E


def part(name, zone, center, size, material, color, shape="Block"):
    """Island geometry -> Roblox Part.  For shape='Cylinder', size = (2r, 2r, height), vertical axis."""
    PARTS.append({"name": name, "zone": zone, "shape": shape, "center": [round(v, 4) for v in center],
                  "size": [round(v, 4) for v in size], "material": material, "color": [round(c, 4) for c in color]})


# ------------------------------------------------------------------ the layout
GOLD = (1.0, 0.78, 0.30)
DECK = (0.90, 0.88, 0.96)
ROCK1 = (0.70, 0.66, 0.80)
ROCK2 = (0.58, 0.54, 0.70)
ROCK3 = (0.46, 0.43, 0.60)


def corner_yaw(d1, d2):
    for yaw in (0, 90, 180, 270):
        c, s = round(math.cos(math.radians(yaw))), round(math.sin(math.radians(yaw)))
        ax, ay = (c, s), (-s, c)          # where local +X and +Y end up
        if {ax, ay} == {tuple(d1), tuple(d2)}:
            return yaw
    raise ValueError((d1, d2))


def corner(p, d1, d2, zone="Balustrade"):
    place_T("Lobby_PROP_BalustradeCorner", zone, (p[0], p[1], DECK_TOP), corner_yaw(d1, d2))


def edge(a, b, zone="Balustrade"):
    """Straight modules between two corner posts (each corner contributes a 6-stud run)."""
    a, b = Vector((*a, 0)), Vector((*b, 0))
    d = (b - a).normalized()
    E = (b - a).length
    n = round((E - 12) / 10)
    if n <= 0:
        assert abs(E - 12) < 1e-6, f"edge {E} cannot be closed by corner runs"
        return
    f = (E - 12) / (10 * n)
    yaw = math.degrees(math.atan2(d.y, d.x))
    for k in range(n):
        s = 6 + 0.95 * f + 10 * f * k
        p = a + d * s
        place_T("Lobby_PROP_BalustradeStraight", zone, (p.x, p.y, DECK_TOP), yaw, stretch=(f, 1, 1))


def build_layout():
    # ---------------- island deck (main + terraces + plaza disc) and stepped underside
    oh = EDGE_OVERHANG
    y0, y1 = -oh, NORTH_Y + oh
    zc = DECK_TOP - DECK_THICK / 2
    part("Deck_Main", "Island", (0, (y0 + y1) / 2, zc), (2 * (ISLAND_HALF + oh), y1 - y0, DECK_THICK), "Marble", DECK)
    part("Deck_GoldBand", "Island", (0, (y0 + y1) / 2, DECK_TOP - 0.9),
         (2 * (ISLAND_HALF + oh) + 0.24, y1 - y0 + 0.24, 0.35), "SmoothPlastic", GOLD)
    part("Deck_Plaza", "Island", (0, 0, zc), (2 * (PLAZA_R + 0.4), 2 * (PLAZA_R + 0.4), DECK_THICK), "Marble", DECK,
         "Cylinder")
    part("Deck_PlazaGold", "Island", (0, 0, DECK_TOP - 0.9), (2 * (PLAZA_R + 0.52), 2 * (PLAZA_R + 0.52), 0.35),
         "SmoothPlastic", GOLD, "Cylinder")
    for side in (-1, 1):
        xa, xb = side * (ISLAND_HALF + oh), side * (TERRACE_OUT + oh)   # abut the main deck: no coplanar overlap
        cx, w = (xa + xb) / 2, abs(xb - xa)
        ty0, ty1 = TERRACE_Y0 - oh, TERRACE_Y1 + oh
        part(f"Deck_Terrace{'E' if side > 0 else 'W'}", "Island", (cx, (ty0 + ty1) / 2, zc), (w, ty1 - ty0, DECK_THICK),
             "Marble", DECK)
        part(f"Deck_TerraceGold{'E' if side > 0 else 'W'}", "Island", (cx + side * 0.12, (ty0 + ty1) / 2, DECK_TOP - 0.9),
             (w + 0.24, ty1 - ty0 + 0.24, 0.35), "SmoothPlastic", GOLD)
        part(f"Under_Terrace{'E' if side > 0 else 'W'}", "Island", (cx - side * 2, (ty0 + ty1) / 2, -DECK_THICK - 2.5),
             (w - 4, ty1 - ty0 - 4, 5.0), "Slate", ROCK1)
    # stepped floating-island underside (blocky, as in the aerial/rear references)
    layers = [(2.0, 5.0, ROCK1), (6.0, 6.0, ROCK2), (12.0, 7.0, ROCK3), (19.0, 6.0, ROCK3)]
    z = DECK_TOP - DECK_THICK
    for i, (inset, h, col) in enumerate(layers):
        w = 2 * (ISLAND_HALF + oh - inset)
        ln = (y1 - y0) - 2 * inset
        if w > 4 and ln > 4:
            part(f"Under_Main_{i}", "Island", (0, (y0 + y1) / 2, z - h / 2), (w, ln, h), "Slate", col)
        r = PLAZA_R + 0.4 - inset * 0.8
        if r > 3:
            part(f"Under_Plaza_{i}", "Island", (0, 0, z - h / 2), (2 * r, 2 * r, h), "Slate", col, "Cylinder")
        z -= h

    # ---------------- spawn plaza + ring balustrade on its curb (south half)
    place_T("Lobby_PROP_SpawnPlaza", "Plaza", (0, 0, PLAZA_LIFT))
    curb_top = PLAZA_LIFT + 0.155
    R = 16.0 * RING_SCALE
    for k in range(6):
        phi = math.radians(195 + 30 * k)
        place_T("Lobby_PROP_BalustradeCurved", "Balustrade", (R * math.cos(phi), R * math.sin(phi), curb_top),
                math.degrees(phi) - 90, scale=RING_SCALE)
    # shoulders: straight module whose post closes the ring, run out to the island corner
    f = (ISLAND_HALF - 6 - R) / 9.05
    place_T("Lobby_PROP_BalustradeStraight", "Balustrade", (R, 0, DECK_TOP), 0, stretch=(f, 1, 1))
    place_T("Lobby_PROP_BalustradeStraight", "Balustrade", (-R, 0, DECK_TOP), 180, stretch=(f, 1, 1))

    # ---------------- perimeter balustrade (right side, mirrored for the left)
    for sx in (1, -1):
        X = lambda x: sx * x
        pts = [(X(ISLAND_HALF), 0), (X(ISLAND_HALF), TERRACE_Y0), (X(TERRACE_OUT), TERRACE_Y0),
               (X(TERRACE_OUT), TERRACE_Y1), (X(ISLAND_HALF), TERRACE_Y1), (X(ISLAND_HALF), NORTH_Y)]
        dirs = [((-sx, 0), (0, 1)), ((0, -1), (sx, 0)), ((-sx, 0), (0, 1)), ((0, -1), (-sx, 0)), ((sx, 0), (0, 1)),
                ((0, -1), (-sx, 0))]
        for p, (d1, d2) in zip(pts, dirs):
            corner(p, d1, d2)
        for a, b in zip(pts[:-1], pts[1:]):
            edge(a, b)
    edge((ISLAND_HALF, NORTH_Y), (-ISLAND_HALF, NORTH_Y))

    # ---------------- road + gate
    for i in range(N_ROAD):
        place_T("Lobby_PROP_RoadCobble", "Road", (0, ROAD_Y0 + ROAD_TILE * (i + 0.5), ROAD_LIFT))
    gate_depth = _SRC["Lobby_ArenaGate"][2].y
    place_B("Lobby_ArenaGate", "ArenaGate", (0, ROAD_Y1 + gate_depth / 2, DECK_TOP))

    # ---------------- arches (column + half arch; mirrored copy on the east side)
    for y in ARCH_Y:
        place_T("Lobby_ArchSpan", "Arches", (-ARCH_HALF_SPAN, y, DECK_TOP))
        place_T("Lobby_ArchSpan", "Arches", (ARCH_HALF_SPAN, y, DECK_TOP), mirror=True)
    arch0 = ARCH_Y[0] + ARCH_LOCAL_Y
    place_T("Lobby_PROP_EventsBanner", "Arches", (0, arch0, 14.1))

    # ---------------- ability pedestals between the arch columns, glyphs angled toward the spawn
    west = ["Wind", "Crystal", "Lightning", "Shield", "Flame"]
    east = ["Emerald", "Sun", "Orb", "Wings"]
    slots = [ARCH_Y[k] + ARCH_LOCAL_Y + off for k in range(3) for off in (5.5, 10.5)]
    for name, y in zip(west, slots):
        place_B(f"Lobby_PED_{name}", "Abilities", (-PED_X, y, DECK_TOP), 45)
    for name, y in zip(east, slots):
        place_B(f"Lobby_PED_{name}", "Abilities", (PED_X, y, DECK_TOP), -45)

    # ---------------- east terrace: shops facing the road
    mk = _SRC["Lobby_MarketShop"][2]
    cr = _SRC["Lobby_CraftShop"][2]
    back = TERRACE_OUT - 1.4
    place_B("Lobby_MarketShop", "Shops", (back - mk.y / 2, TERRACE_Y0 + 2.0 + mk.x / 2, DECK_TOP), -90)
    place_B("Lobby_CraftShop", "Shops", (back - cr.y / 2, TERRACE_Y1 - 2.4 - cr.x / 2, DECK_TOP), -90)
    place_B("Lobby_PROP_LanternPost", "Shops", (ISLAND_HALF + 2.5, (TERRACE_Y0 + TERRACE_Y1) / 2 - 0.5, DECK_TOP))

    # ---------------- west terrace: game-mode portals (DUELS, PRACTICE) facing the road, opposite the shops
    back = -(TERRACE_OUT - 1.4)
    for mode, yc in (("Duels", MODE_PORTAL_Y[0]), ("Practice", MODE_PORTAL_Y[1])):
        unit = f"Lobby_PORTAL_{mode}"
        size = _SRC[unit][2]
        cx = back + size.y / 2                       # rotated 90 deg: local depth runs along world X
        place_B(unit, "ModePortals", (cx, yc, DECK_TOP), 90)
        # portal plane sits PORTAL_PLANE_OFFSET behind the bbox centre (local +Y -> world -X)
        px = cx - (size.y / 2 - PORTAL_BACK_TO_PLANE)
        TRIGGERS.append({"name": f"{mode}TeleportZone", "mode": mode,
                         "center": [round(px + 0.4, 3), yc, round(PORTAL_TRIGGER_CZ, 3)],
                         "size": [2.4, 7.0, 5.6]})
    place_B("Lobby_PROP_LanternPost", "ModePortals", (back + 3.5, sum(MODE_PORTAL_Y) / 2, DECK_TOP))

    # ---------------- background floating castle islands (asset 08), if built
    if "Lobby_FloatingCastle" in _SRC:
        for x, y, z, yaw, sc in CASTLES:
            place_B("Lobby_FloatingCastle", "Sky", (x, y, z), yaw, sc)

    # ---------------- lantern posts flanking the road ends, planters on the plaza shoulders
    for sx in (-1, 1):
        place_B("Lobby_PROP_LanternPost", "Road", (sx * PED_X, 14.0, DECK_TOP))
        place_B("Lobby_PROP_LanternPost", "Road", (sx * PED_X, ROAD_Y1 - 4.6, DECK_TOP))
        place_B("Lobby_PROP_PlanterLong", "Plaza", (sx * 23.0, 6.0, DECK_TOP))


SPAWN = (0.0, 0.0, PLAZA_LIFT + 0.25)
RIGS = [(0.0, 3.0), (-PED_X - 3.0, 31.0), (ISLAND_HALF + 1.5, 56.0), (0.0, ROAD_Y1 - 2.0)]


# ------------------------------------------------------------------ preview geometry for Parts
def build_parts_preview():
    c = L.coll("LOBBY_Island", LOBBY)
    deck = L.marble("MAT_DeckMarble", base=(0.90, 0.88, 0.96), tint=(0.80, 0.76, 0.90), vein=(0.6, 0.56, 0.72))
    mats = {"Marble": deck}
    for p in PARTS:
        col = tuple(p["color"])
        if p["material"] == "Marble":
            m = deck
        else:
            m = L.flat(f"MAT_Part_{p['material']}_{col}", col, rough=0.8 if p["material"] == "Slate" else 0.35,
                       metal=0.7 if p["material"] == "SmoothPlastic" else 0.0)
        cx, cy, cz = p["center"]
        sx, sy, sz = p["size"]
        if p["shape"] == "Cylinder":
            L.cyl(p["name"], sx / 2, sz, (cx, cy, cz), m, 72, 0.0, c=c)
        else:
            L.box(p["name"], (sx, sy, sz), (cx, cy, cz), m, 0.0, c=c)


def build_triggers_preview():
    """Teleport zones as wireframe boxes (visible in the .blend viewport, not rendered)."""
    c = L.coll("LOBBY_TeleportZones", LOBBY)
    for t in TRIGGERS:
        ob = L.box(t["name"], tuple(t["size"]), tuple(t["center"]), None, 0.0, c=c)
        ob.display_type = "WIRE"
        ob.hide_render = True


def build_rigs_preview():
    c = L.coll("LOBBY_ScaleRigs", LOBBY)
    skin = L.flat("MAT_RigSkin", (0.95, 0.8, 0.55), rough=0.6)
    body = L.flat("MAT_RigBody", (0.12, 0.12, 0.16), rough=0.6)
    for i, (x, y) in enumerate(RIGS):
        z = 0.2 if math.hypot(x, y) < PLAZA_R else 0.0
        L.box(f"RIG_Legs_{i}", (1.9, 1.0, 2.0), (x, y, z + 1.0), body, 0.05, c=c)
        L.box(f"RIG_Torso_{i}", (2.0, 1.0, 2.0), (x, y, z + 3.0), body, 0.05, c=c)
        L.box(f"RIG_Head_{i}", (1.2, 1.2, 1.0), (x, y, z + 4.5), skin, 0.15, c=c)


# ------------------------------------------------------------------ Luau emission
def rbx(v):
    return [round(v[0], 3), round(v[2], 3), round(-v[1], 3)]


def write_luau():
    out = os.path.join(os.path.dirname(L.ROOT), "..", "src", "shared", "LobbyLayout.luau")
    out = os.path.normpath(out)
    lines = ["--!strict",
             "-- GENERATED by assets/lobby/scripts/lobby_layout.py - edit the Python layout, not this file.",
             "-- Roblox coordinates relative to the lobby origin (deck top = 0). Units: studs.",
             "-- target = world position of the unit's bounding-box bottom-centre after rotation.",
             "-- stretch = per-axis scale in the unit's own (unrotated) frame, Roblox axes (X, Y up, Z).", "",
             "export type Placement = { unit: string, zone: string, target: { number }, yaw: number, scale: number, stretch: { number } }",
             "export type PartSpec = { name: string, zone: string, shape: string, center: { number }, size: { number }, material: string, color: { number } }",
             "", "local placements: { Placement } = {"]
    for p in PLACEMENTS:
        t = rbx(p["target"])
        st = [p["stretch"][0], p["stretch"][2], p["stretch"][1]]
        lines.append(f'\t{{ unit = "{p["unit"]}", zone = "{p["zone"]}", target = {{ {t[0]}, {t[1]}, {t[2]} }}, '
                     f'yaw = {p["yaw"]}, scale = {p["scale"]}, stretch = {{ {st[0]}, {st[1]}, {st[2]} }} }},')
    lines += ["}", "", "local parts: { PartSpec } = {"]
    for p in PARTS:
        c = rbx(p["center"])
        sx, sy, sz = p["size"]
        size = [sx, sz, sy]
        col = ", ".join(str(v) for v in p["color"])
        lines.append(f'\t{{ name = "{p["name"]}", zone = "{p["zone"]}", shape = "{p["shape"]}", '
                     f'center = {{ {c[0]}, {c[1]}, {c[2]} }}, size = {{ {size[0]}, {size[1]}, {size[2]} }}, '
                     f'material = "{p["material"]}", color = {{ {col} }} }},')
    sp = rbx(SPAWN)
    rigs = ", ".join("{ %s, %s, %s }" % tuple(rbx((x, y, 0.2 if math.hypot(x, y) < PLAZA_R else 0.0)))
                     for x, y in RIGS)
    lines += ["}", "",
              "return {",
              "\tplacements = placements,",
              "\tparts = parts,",
              f"\tspawn = {{ {sp[0]}, {sp[1]}, {sp[2]} }},",
              f"\tscaleRigs = {{ {rigs} }},",
              "\t-- invisible, non-colliding teleport zones in front of each mode portal (hook TeleportService here)",
              "\ttriggers = {",
              *[f'\t\t{{ name = "{t["name"]}", mode = "{t["mode"]}", center = {{ {", ".join(str(v) for v in rbx(t["center"]))} }}, '
                f'size = {{ {t["size"][0]}, {t["size"][2]}, {t["size"][1]} }} }},' for t in TRIGGERS],
              "\t},",
              f"\tunitCount = {len(PLACEMENTS)},",
              "}", ""]
    with open(out, "w") as fh:
        fh.write("\n".join(lines))
    print("LUAU", out, len(PLACEMENTS), "placements", len(PARTS), "parts")
    with open(os.path.join(L.ROOT, "fbx", "lobby_layout.json"), "w") as fh:
        json.dump({"placements": PLACEMENTS, "parts": PARTS, "spawn": SPAWN, "rigs": RIGS, "triggers": TRIGGERS}, fh, indent=1)


# ------------------------------------------------------------------ preview renders
def render_previews():
    L.beauty_lights()
    quick = "--quick" in sys.argv
    L.setup_render((1600, 900), 10 if quick else 40)
    s = bpy.context.scene
    s.render.resolution_percentage = 40 if quick else 100
    s.view_settings.exposure = -0.3
    views = [
        ("lobby_spawn_view", L.camera("CAM_spawn", (0, -11.0, 9.0), (0, 60, 7.0), lens=20), (1600, 900)),
        ("lobby_abilities_view", L.camera("CAM_abil", (-2.0, 17.0, 6.0), (-13.0, 48.0, 2.5), lens=24), (1600, 900)),
        ("lobby_modes_view", L.camera("CAM_modes", (-6.0, 63.0, 8.0), (-38.0, 63.0, 6.5), lens=22), (1600, 900)),
        ("lobby_shops_view", L.camera("CAM_shops", (24.0, 30.0, 8.0), (37.0, 64.0, 4.0), lens=24), (1600, 900)),
        ("lobby_plaza_view", L.camera("CAM_plaza", (-13.0, -12.0, 10.0), (12.0, 55.0, 4.0), lens=18), (1600, 900)),
        ("lobby_aerial_view", L.camera("CAM_aerial", (-95.0, -45.0, 85.0), (6.0, 70.0, 0.0), lens=26), (1600, 900)),
        ("lobby_rear_view", L.camera("CAM_rear", (0.0, 178.0, 70.0), (0.0, 40.0, 0.0), lens=24), (1600, 900)),
    ]
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--views=")), None)
    out = []
    for name, cam, res in views:
        path = os.path.join(L.RENDERS, f"{name}.png")
        if only is None or name.replace("lobby_", "").replace("_view", "") in only or not os.path.exists(path):
            L.render(cam, path, res)
        out.append((name.replace("lobby_", "").replace("_", " "), path))
    plan = L.camera("CAM_plan", (0, 70, 400), (0, 70, 0), ortho=170)
    plan.rotation_euler = (0, 0, 0)
    pp = os.path.join(L.RENDERS, "lobby_plan_view.png")
    if only is None or "plan" in only:
        L.render(plan, pp, (1100, 1100))
    out.append(("plan (top ortho)", pp))
    L.contact_sheet(out, os.path.join(L.RENDERS, "lobby_assembly_sheet.png"), cols=2, tile=800,
                    title="ASSEMBLED LOBBY MAP - Blender Cycles renders")


def main(do_render=True):
    global LOBBY
    L.reset()
    LOBBY = L.coll("LOBBY")
    load_units()
    build_layout()
    build_parts_preview()
    build_rigs_preview()
    build_triggers_preview()
    write_luau()
    L.save_blend("lobby_assembled.blend")
    if do_render:
        render_previews()


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
