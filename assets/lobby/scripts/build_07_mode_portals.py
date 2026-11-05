"""ASSET 07 - Game-mode teleport portals: DUELS and PRACTICE.

No dedicated reference exists for these, so they are built strictly from the arena
gate's established design language (asset 05) rather than invented: the same hex
portal construction (marble frame, darker lip, neon ring, swirling energy surface),
block-course marble plinth, neon-riser steps, neon-strip pillars with crystal finials,
gold-framed navy sign with white 3D lettering, and hanging banners.  Only the accent
colour and the medallion emblem change per mode so players can tell them apart:
  DUELS     red neon / swirl / crystals, crossed-swords medallion
  PRACTICE  yellow neon / swirl / crystals, bullseye-target medallion
Each portal is about 16 studs wide and 17 tall (a smaller sibling of the 16 x 12.6 arena
portal: these are side destinations, the arena stays the hero landmark).
Front faces -Y, centred on x = 0, floor at z = 0.
Run:  python build_07_mode_portals.py [--no-render]
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector
import lobbylib as L
import build_05_arena_gate as G
from build_01_arch import star_points

# ---------------------------------------------------------------- named dimensions
PLINTH_W, PLINTH_D = 16.0, 7.0
PLINTH_Z = (1.5, 2.4)                 # lower course top, upper course top
UPPER_W, UPPER_D = 13.6, 5.6
PORTAL_W, PORTAL_H, PORTAL_TOP_HALF = 10.0, 8.0, 2.8
PORTAL_Y = (-0.9, 0.9)
PORTAL_CZ = PLINTH_Z[1] + 0.35 + PORTAL_H / 2
PILLAR_X, PILLAR_W = 6.4, 1.9
PILLAR_TOP = 12.0
LINTEL_Z = (11.0, 12.2)
SIGN_W, SIGN_H, SIGN_CZ = 10.6, 2.5, 13.55
N_STEPS, STEP_H, STEP_D, STEP_W = 3, PLINTH_Z[1] / 3, 1.2, 8.0

MODES = {
    # DUELS = red
    "Duels": dict(neon=(1.0, 0.03, 0.03), crystal=(1.0, 0.06, 0.06), cloth=(0.30, 0.01, 0.02),
                  swirl=[(0.0, (0.30, 0.0, 0.0)), (0.55, (1.0, 0.05, 0.03)), (0.8, (1.0, 0.32, 0.25)),
                         (0.9, (0.85, 0.02, 0.02))], core=(1.0, 0.22, 0.15), text="DUELS", emblem="swords"),
    # PRACTICE = yellow (brighter / more saturated than the gold trim so the two stay distinct)
    "Practice": dict(neon=(1.0, 0.80, 0.0), crystal=(1.0, 0.85, 0.05), cloth=(0.62, 0.40, 0.0),
                     swirl=[(0.0, (0.40, 0.22, 0.0)), (0.55, (1.0, 0.78, 0.0)), (0.8, (1.0, 0.92, 0.35)),
                            (0.9, (0.95, 0.65, 0.0))], core=(1.0, 0.86, 0.25), text="PRACTICE", emblem="target"),
}


def swirl_material(mode, spec):
    m = G.portal_material()
    m.name = f"MAT_PortalSwirl{mode}"
    nodes = m.node_tree.nodes
    ramp = next(n for n in nodes if n.type == "VALTORGB")
    for el, (pos, col) in zip(ramp.color_ramp.elements, spec["swirl"]):
        el.position = pos
        el.color = (*col, 1)
    mix = next(n for n in nodes if n.type == "MIX")
    mix.inputs["B"].default_value = (*spec["core"], 1)
    m.diffuse_color = (*spec["swirl"][1][1], 1)
    nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.75
    return m


def sword_outline():
    """Stylised sword pointing +z in (x,z): blade, crossguard, grip, pommel (one closed outline)."""
    return [(0.0, 2.3), (0.22, 1.95), (0.22, 0.25), (0.75, 0.25), (0.75, 0.0), (0.14, 0.0), (0.14, -0.7),
            (0.26, -0.8), (0.26, -1.0), (-0.26, -1.0), (-0.26, -0.8), (-0.14, -0.7), (-0.14, 0.0), (-0.75, 0.0),
            (-0.75, 0.25), (-0.22, 0.25), (-0.22, 1.95)][::-1]


def build_portal(mode, spec, P, root, x_off=0.0):
    tag = mode.upper()
    C = {k: L.coll(f"MP_{mode}_{k}", root) for k in ("Plinth", "Portal", "Pillars", "Sign", "Steps", "Decor")}
    M, MD, G_ = P["marble"], P["marble_dark"], P["gold"]
    # moderate emission: stronger values clip the red/yellow channels to pink/white (seen in v1)
    neon = L.emissive(f"MAT_Neon{mode}", spec["neon"], 1.4, base=tuple(0.75 * c for c in spec["neon"]))
    cryst = L.emissive(f"MAT_Crystal{mode}", spec["crystal"], 0.55, base=tuple(0.8 * c for c in spec["crystal"]))
    cloth = L.flat(f"MAT_{mode}BannerCloth", spec["cloth"], rough=0.7)
    swirl = swirl_material(mode, spec)
    objs = []

    def add(o):
        o.location.x += x_off
        objs.append(o)
        return o

    # ---------------- plinth: two block courses (stone joints like the arena wall)
    y0, y1 = -PLINTH_D / 2, PLINTH_D / 2
    add(G.blocks(f"MP_{tag}_PlinthLow", -PLINTH_W / 2, PLINTH_W / 2, 0.0, PLINTH_Z[0], y0, y1, MD, C["Plinth"],
                 bw=2.6, bh=PLINTH_Z[0], seed=3))
    add(G.blocks(f"MP_{tag}_PlinthUp", -UPPER_W / 2, UPPER_W / 2, PLINTH_Z[0], PLINTH_Z[1], -UPPER_D / 2,
                 UPPER_D / 2, M, C["Plinth"], bw=2.2, bh=PLINTH_Z[1] - PLINTH_Z[0], seed=4))
    add(L.box(f"MP_{tag}_PlinthGold", (UPPER_W + 0.1, UPPER_D + 0.1, 0.16), (0, 0, PLINTH_Z[0] + 0.08), G_, 0.03,
              c=C["Plinth"]))
    for sx in (-1, 1):   # gold diamond plaques on the lower course front
        d = L.extrude_polygon(f"MP_{tag}_Plaque_{sx}", G.diamond(0.45), 0.12, G_, C["Plinth"], bevel=0.03)
        d.location = (sx * 5.6, y0 - 0.06, PLINTH_Z[0] / 2)
        add(d)

    # ---------------- steps with accent riser strips
    for k in range(N_STEPS):
        ztop = STEP_H * (k + 1)
        yf = y0 - STEP_D * (N_STEPS - 1 - k) - STEP_D
        depth = (-UPPER_D / 2 + 0.2) - yf
        add(L.box(f"MP_{tag}_Step_{k}", (STEP_W - 0.4 * k, depth, STEP_H), (0, yf + depth / 2, ztop - STEP_H / 2), M,
                  0.08, c=C["Steps"]))
        add(L.box(f"MP_{tag}_StepNeon_{k}", (STEP_W - 0.4 * k - 0.8, 0.08, STEP_H * 0.35),
                  (0, yf - 0.03, ztop - STEP_H * 0.55), neon, 0.0, c=C["Steps"]))

    # ---------------- hex portal (same construction as the arena gate)
    hx = G.hexagon(PORTAL_W, PORTAL_H, PORTAL_TOP_HALF)
    in1 = G.offset_convex(hx, 1.2)
    in2 = G.offset_convex(hx, 1.5)
    in3 = G.offset_convex(hx, 1.85)
    add(G.frame_prism(f"MP_{tag}_PortalFrame", hx, in1, PORTAL_Y[0], PORTAL_Y[1], M, C["Portal"], 0.12, cz=PORTAL_CZ))
    add(G.frame_prism(f"MP_{tag}_PortalLip", in1, in2, PORTAL_Y[0] + 0.35, PORTAL_Y[1], MD, C["Portal"], 0.05,
                      cz=PORTAL_CZ))
    add(G.frame_prism(f"MP_{tag}_PortalNeon", in2, in3, PORTAL_Y[0] + 0.45, PORTAL_Y[1] - 0.2, neon, C["Portal"], 0.03,
                      cz=PORTAL_CZ))
    add(G.frame_prism(f"MP_{tag}_PortalOuterStep", G.offset_convex(hx, -0.3), hx, PORTAL_Y[0] + 0.4, PORTAL_Y[1], MD,
                      C["Portal"], 0.05, cz=PORTAL_CZ))
    surf = L.extrude_polygon(f"MP_{tag}_PortalSurface", in3, 0.16, swirl, C["Portal"])
    surf.location = (0, 0.05, PORTAL_CZ)
    add(surf)
    # back plate so the portal reads from behind as well
    back = L.extrude_polygon(f"MP_{tag}_PortalBack", hx, 0.5, MD, C["Portal"], bevel=0.08)
    back.location = (0, PORTAL_Y[1] + 0.25, PORTAL_CZ)
    add(back)

    # ---------------- pillars: neon strip inset, gold bands, cap, crystal finial
    for sx in (-1, 1):
        px = sx * PILLAR_X
        h = PILLAR_TOP - PLINTH_Z[1]
        add(L.box(f"MP_{tag}_PillarBase_{sx}", (PILLAR_W + 0.5, PILLAR_W + 0.5, 0.6),
                  (px, 0, PLINTH_Z[1] + 0.3), M, 0.08, c=C["Pillars"]))
        # smooth marble shaft (the arena sheet's inner pillars are plain shafts, not block stacks)
        add(L.box(f"MP_{tag}_Pillar_{sx}", (PILLAR_W, PILLAR_W, PILLAR_TOP - PLINTH_Z[1] - 0.6),
                  (px, 0, (PLINTH_Z[1] + 0.6 + PILLAR_TOP) / 2), M, 0.08, c=C["Pillars"]))
        add(L.box(f"MP_{tag}_PillarNeon_{sx}", (0.36, 0.1, h - 3.0), (px, -PILLAR_W / 2 - 0.02, PLINTH_Z[1] + 1.6 +
                                                                     (h - 3.0) / 2), neon, 0.02, c=C["Pillars"]))
        for zb in (PLINTH_Z[1] + 1.05, PILLAR_TOP - 0.9):
            add(L.box(f"MP_{tag}_PillarGold_{sx}_{zb:.0f}", (PILLAR_W + 0.12, PILLAR_W + 0.12, 0.18), (px, 0, zb), G_,
                      0.03, c=C["Pillars"]))
        add(L.box(f"MP_{tag}_PillarCap_{sx}", (PILLAR_W + 0.55, PILLAR_W + 0.55, 0.55),
                  (px, 0, PILLAR_TOP + 0.27), M, 0.1, c=C["Pillars"]))
        add(L.box(f"MP_{tag}_CrystalSeat_{sx}", (0.9, 0.9, 0.3), (px, 0, PILLAR_TOP + 0.7), G_, 0.04, c=C["Pillars"]))
        add(G.crystal(f"MP_{tag}_Crystal_{sx}", 0.55, 1.9, 0.35, (px, 0, PILLAR_TOP + 1.2), cryst, C["Pillars"]))

    # ---------------- lintel + sign (gold chamfered frame, navy panel, white 3D text)
    # lintel ends inside the pillars (ending flush with their outer faces z-fought in v1)
    # smooth marble lintel beam, ending inside the pillars (no flush end faces)
    add(L.box(f"MP_{tag}_Lintel", (2 * PILLAR_X, 2.0, LINTEL_Z[1] - LINTEL_Z[0]),
              (0, 0, (LINTEL_Z[0] + LINTEL_Z[1]) / 2), M, 0.08, c=C["Sign"]))
    add(L.box(f"MP_{tag}_LintelGold", (2 * PILLAR_X - PILLAR_W + 0.2, 2.1, 0.14), (0, 0, LINTEL_Z[0] + 0.07), G_, 0.02,
              c=C["Sign"]))
    sy = -1.25
    frame = L.extrude_polygon(f"MP_{tag}_SignFrame", G.rect(SIGN_W, SIGN_H, 0.45), 0.3, G_, C["Sign"], bevel=0.05)
    frame.location = (0, sy + 0.1, SIGN_CZ)
    add(frame)
    panel = L.extrude_polygon(f"MP_{tag}_SignPanel", G.rect(SIGN_W - 0.5, SIGN_H - 0.5, 0.3), 0.36, P["navy"],
                              C["Sign"])
    panel.location = (0, sy + 0.1, SIGN_CZ)
    add(panel)
    add(L.box(f"MP_{tag}_SignBack", (SIGN_W - 0.6, 1.0, SIGN_H - 0.6), (0, sy + 0.75, SIGN_CZ), M, 0.06, c=C["Sign"]))
    size = 1.45 if len(spec["text"]) <= 5 else 1.22
    add(L.text_mesh(f"MP_{tag}_SignText", spec["text"], size=size, extrude=0.06, mat=P["white"], c=C["Sign"],
                    loc=(0, sy - 0.14, SIGN_CZ - 0.05), spacing=1.04))
    # notch pointer under the sign (as on ENTER THE ARENA)
    tri = L.extrude_polygon(f"MP_{tag}_SignPointer", [(-0.45, 0), (0.45, 0), (0, -0.45)], 0.25, G_, C["Sign"])
    tri.location = (0, sy + 0.05, SIGN_CZ - SIGN_H / 2 + 0.02)
    add(tri)

    # ---------------- medallion emblem on top of the sign
    mz = SIGN_CZ + SIGN_H / 2 + 1.25
    disc = L.cyl(f"MP_{tag}_Medallion", 1.3, 0.35, (0, sy + 0.25, mz), G_, 32, 0.06, c=C["Sign"],
                 rot=(math.pi / 2, 0, 0))
    add(disc)
    add(L.cyl(f"MP_{tag}_MedallionFace", 1.05, 0.12, (0, sy + 0.02, mz), P["navy"], 32, 0.02, c=C["Sign"],
              rot=(math.pi / 2, 0, 0)))
    if spec["emblem"] == "swords":
        for i, a in enumerate((-math.pi / 4, math.pi / 4)):
            sw = L.extrude_polygon(f"MP_{tag}_Sword_{i}", [(x * 0.42, z * 0.42) for x, z in sword_outline()], 0.08,
                                   neon, C["Sign"])
            sw.location = (0, sy - 0.1, mz)
            sw.rotation_euler = (0, a, 0)
            add(sw)
    else:
        for i, (ro, ri) in enumerate(((0.85, 0.62), (0.42, 0.22))):
            r = L.ring(f"MP_{tag}_TargetRing_{i}", ro, ri, 0.1, (0, sy - 0.07, mz), neon, 32, c=C["Sign"])
            r.rotation_euler = (math.pi / 2, 0, 0)
            add(r)
        add(L.cyl(f"MP_{tag}_TargetDot", 0.1, 0.1, (0, sy - 0.07, mz), neon, 16, 0.0, c=C["Sign"],
                  rot=(math.pi / 2, 0, 0)))
    # ---------------- mode banners hanging on the pillar fronts (arch-banner construction, mode cloth)
    for sxx in (-1, 1):
        bx, by, top = sxx * PILLAR_X, -PILLAR_W / 2 - 0.35, 10.3
        w, h1, pd = 1.6, 3.6, 0.7
        outline = [(-w / 2, 0), (w / 2, 0), (w / 2, -h1), (0, -h1 - pd), (-w / 2, -h1)]
        inner = [(-w / 2 + 0.12, -0.1), (w / 2 - 0.12, -0.1), (w / 2 - 0.12, -h1 + 0.05), (0, -h1 - pd + 0.25),
                 (-w / 2 + 0.12, -h1 + 0.05)]
        t = L.extrude_polygon(f"MP_{tag}_BannerTrim_{sxx}", outline, 0.08, G_, C["Decor"], bevel=0.02)
        cl = L.extrude_polygon(f"MP_{tag}_BannerCloth_{sxx}", inner, 0.13, cloth, C["Decor"])
        st = L.extrude_polygon(f"MP_{tag}_BannerStar_{sxx}", star_points(0.95, 0.62, 0.3, 0.13), 0.04, P["white"],
                               C["Decor"], center_depth=False)
        for o in (t, cl):
            o.location = (bx, by, top)
        st.location = (bx, by - 0.1, top - h1 * 0.47)
        rod = L.cyl(f"MP_{tag}_BannerRod_{sxx}", 0.08, w + 0.5, (bx, by, top + 0.1), G_, 12, 0.02, c=C["Decor"],
                    rot=(0, math.pi / 2, 0))
        for o in (t, cl, st, rod):
            add(o)
    return objs


def main(do_render=True):
    L.reset()
    P = L.palette()
    root = L.coll("ASSET_07_ModePortals")
    built = {}
    for i, (mode, spec) in enumerate(MODES.items()):
        c = L.coll(f"MP_{mode}", root)
        built[mode] = build_portal(mode, spec, P, c, x_off=0.0)
        # nest the per-part collections under the mode collection
        for sub in list(root.children):
            if sub.name.startswith(f"MP_{mode}_"):
                root.children.unlink(sub)
                c.children.link(sub)
    L.save_blend("07_mode_portals.blend")
    if not do_render:
        return
    L.studio_lights()
    gnd = L.ground(z=-0.01)
    roots = {m: bpy.data.collections[f"MP_{m}"] for m in MODES}
    sheet = []
    for mode, objs in built.items():
        for m, c in roots.items():
            c.hide_render = m != mode
        items = L.inspection_set(f"portal_{mode.lower()}", objs, res=800, samples=28, three_q=(-0.8, -1.3, 0.5),
                                 detail=[("detail_sign", (3.0, -12.0, 14.0), (0.0, -1.2, 13.8), 50)])
        sheet += [(f"{mode} {a}", p) for a, p in items if a in ("front", "right", "rear", "three_quarter",
                                                                 "detail_sign")]
    # beauty pair (both portals side by side, sky lighting)
    for c in roots.values():
        c.hide_render = False
    for ob in roots["Practice"].all_objects:
        ob.location.x += 20.0
    for ob in list(bpy.data.objects):
        if ob.type == "LIGHT":
            bpy.data.objects.remove(ob)
    L.beauty_lights()
    L.setup_render((1400, 800), 36)
    cam = L.camera("CAM_beauty", (-6.0, -34.0, 9.0), (10.0, 0.0, 7.0), lens=32)
    sheet.append(("beauty both", L.render(cam, os.path.join(L.RENDERS, "portals_beauty.png"))))
    L.contact_sheet(sheet, os.path.join(L.RENDERS, "portals_inspection_sheet.png"), cols=5, tile=420,
                    title="ASSET 07 - MODE PORTALS (DUELS / PRACTICE)  Blender Cycles renders")


if __name__ == "__main__":
    main("--no-render" not in sys.argv)
