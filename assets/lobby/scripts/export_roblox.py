"""Roblox export: .blend asset kit -> FBX per model + manifest + Luau styler.

For each export unit (an asset, or one prop of the props kit):
  * every mesh is evaluated (modifiers applied) and transformed to world space
  * meshes are merged per material  ->  one MeshPart per material in Studio,
    named  <Unit>__<MaterialKey>  (split into _p2, _p3 ... above TRI_LIMIT)
  * box-projected UVs (8 studs per tile) are written so Roblox surface
    materials (Marble, Wood, Slate, Fabric...) tile at a stable density
  * FBX written to assets/lobby/fbx/<Unit>.fbx
A manifest (fbx/roblox_manifest.json) and a Luau module
(src/shared/LobbyAssetStyler.luau) are generated: after importing an FBX with
the 3D Importer, LobbyAssetStyler.style(model, unitName) applies Material /
Color / Reflectance / Transparency and rescales the model to the size it had in
Blender (1 Blender unit = 1 stud), whatever unit conversion the importer used.

Run:  python export_roblox.py            (all blends in assets/lobby/blend)
"""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
import lobbylib as L

TRI_LIMIT = 18000
UV_TILE = 8.0
REPO = os.path.dirname(os.path.dirname(L.ROOT))
LUAU_OUT = os.path.join(REPO, "src", "shared", "LobbyAssetStyler.luau")


def roblox_props(mat):
    """Map a Blender material to Roblox MeshPart properties."""
    n = mat.name.lower()
    col = list(mat.diffuse_color[:3])
    if mat.get("roblox_neon") or "neon" in n or "glow" in n:
        d = {"Material": "Neon"}
        if "glass" in n or "potion" in n or "crystal" in n:
            d = {"Material": "Glass", "Transparency": 0.15}
    elif "marble" in n:
        d = {"Material": "Marble"}
    elif "gold" in n or "brass" in n:
        d = {"Material": "SmoothPlastic", "Reflectance": 0.2}
    elif "bronze" in n or "iron" in n or "metal" in n or "anvil" in n:
        d = {"Material": "Metal"}
    elif "wood" in n or "plank" in n or "crate" in n:
        d = {"Material": "Wood"}
    elif "cobble" in n or "stone" in n:
        d = {"Material": "Slate"}
    elif "cloth" in n or "canopy" in n or "awning" in n or "banner" in n or "fabric" in n or "red" in n:
        d = {"Material": "Fabric"}
    elif "glass" in n:
        d = {"Material": "Glass", "Transparency": 0.3}
    else:
        d = {"Material": "SmoothPlastic"}
    d["Color"] = [round(c, 4) for c in linear_to_srgb(col)]
    if mat.get("roblox_texture"):
        # image-textured surface: SurfaceAppearance (ColorMap + NormalMap) once the PNGs are uploaded
        d["Texture"] = mat["roblox_texture"]
        d["Color"] = [1.0, 1.0, 1.0]
    return d


def linear_to_srgb(c):
    return [12.92 * x if x <= 0.0031308 else 1.055 * (x ** (1 / 2.4)) - 0.055 for x in c]


def mat_has_texture(key):
    m = bpy.data.materials.get(key)
    return bool(m and m.get("roblox_texture"))


def box_uv(bm):
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        n = f.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        u_i, v_i = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            co = lp.vert.co
            lp[uv].uv = (co[u_i] / UV_TILE, co[v_i] / UV_TILE)


MIRROR_X = __import__("mathutils").Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0))


def merge_by_material(unit, objs, mirror=False):
    """Return list of new export objects for this unit."""
    dg = bpy.context.evaluated_depsgraph_get()
    groups = {}   # matname -> list[(mesh, tris)]
    for ob in objs:
        if ob.type not in ("MESH", "CURVE", "FONT") or ob.hide_render:
            continue
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        me.transform(ob.matrix_world)
        if mirror:                      # mirrored variant (Roblox cannot use negative scale)
            me.transform(MIRROR_X)
            me.flip_normals()
        mats = list(me.materials) or [None]
        # split multi-material meshes per material index
        for mi, m in enumerate(mats):
            key = m.name if m else "MAT_Default"
            bm = bmesh.new()
            bm.from_mesh(me)
            if len(mats) > 1:
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != mi], context="FACES")
            if not bm.faces:
                bm.free(); continue
            tris = sum(len(f.verts) - 2 for f in bm.faces)
            groups.setdefault(key, []).append((bm, tris))
        bpy.data.meshes.remove(me)
    out, info = [], []
    for key, parts in sorted(groups.items()):
        chunks, cur, cur_t = [], [], 0
        for bm, t in parts:
            if cur and cur_t + t > TRI_LIMIT:
                chunks.append(cur); cur, cur_t = [], 0
            cur.append(bm); cur_t += t
        if cur:
            chunks.append(cur)
        short = key.replace("MAT_", "")
        for ci, ch in enumerate(chunks):
            name = f"{unit}__{short}" + (f"_p{ci + 1}" if len(chunks) > 1 else "")
            me = bpy.data.meshes.new(name)
            acc = bmesh.new()
            for bm in ch:
                tmp = bpy.data.meshes.new("tmp"); bm.to_mesh(tmp); bm.free()
                acc.from_mesh(tmp); bpy.data.meshes.remove(tmp)
            bmesh.ops.remove_doubles(acc, verts=acc.verts, dist=1e-5)
            if not (mat_has_texture(key)):
                box_uv(acc)          # textured materials keep their authored world-aligned UVs
            tris = sum(len(f.verts) - 2 for f in acc.faces)
            acc.to_mesh(me); acc.free()
            mat = bpy.data.materials.get(key)
            if mat:
                me.materials.append(mat)
            ob = bpy.data.objects.new(name, me)
            bpy.context.scene.collection.objects.link(ob)
            out.append(ob)
            info.append({"part": name, "material": key, "tris": tris,
                         "roblox": roblox_props(mat) if mat else {"Material": "SmoothPlastic"}})
    return out, info


def export_units(blend, units_fn):
    bpy.ops.wm.open_mainfile(filepath=blend)
    results = {}
    for entry in units_fn():
        unit, objs = entry[0], entry[1]
        mirror = len(entry) > 2 and entry[2]
        mn, mx = L.bounds(objs)
        if mirror:
            mn, mx = Vector((-mx.x, mn.y, mn.z)), Vector((-mn.x, mx.y, mx.z))
        # origin: centre of footprint, floor at the lowest point
        origin = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
        new, info = merge_by_material(unit, objs, mirror)
        for ob in new:
            ob.data.transform(__import__("mathutils").Matrix.Translation(-origin))
        bpy.ops.object.select_all(action="DESELECT")
        for ob in new:
            ob.select_set(True)
        path = os.path.join(L.FBX, f"{unit}.fbx")
        os.makedirs(L.FBX, exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"},
                                 apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
                                 axis_forward="-Z", axis_up="Y", use_mesh_modifiers=False,
                                 mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False,
                                 path_mode="STRIP")
        size = mx - mn
        results[unit] = {"fbx": os.path.relpath(path, L.ROOT), "size_studs": [round(v, 3) for v in size],
                         "parts": info, "tris_total": sum(i["tris"] for i in info)}
        print(f"EXPORT {unit}: {len(new)} parts, {results[unit]['tris_total']} tris, size {tuple(round(v, 2) for v in size)}")
        for ob in new:
            bpy.data.objects.remove(ob)
    return results


def asset_units(coll_name, unit):
    def f():
        c = bpy.data.collections[coll_name]
        objs = [o for o in c.all_objects if not o.name.startswith(("RIG_", "CAM_", "REF_"))]
        return [(unit, objs)]
    return f


def props_units():
    root = bpy.data.collections["ASSET_06_Props"]
    return [(f"Lobby_{c.name}", list(c.all_objects)) for c in root.children]


def main():
    manifest = {}
    plan = [
        ("01_marble_arch.blend", asset_units, "ASSET_01_MarbleArch", "Lobby_MarbleArch"),
        ("01_marble_arch.blend", None, "ARCH_SPAN", None),
        ("02_ability_pedestals.blend", None, "ASSET_02_AbilityPedestals", "Lobby_AbilityPedestals"),
        ("03_market_shop.blend", asset_units, "ASSET_03_MarketShop", "Lobby_MarketShop"),
        ("04_craft_shop.blend", asset_units, "ASSET_04_CraftShop", "Lobby_CraftShop"),
        ("05_arena_gate.blend", asset_units, "ASSET_05_ArenaGate", "Lobby_ArenaGate"),
        ("06_props.blend", None, "ASSET_06_Props", None),
        ("07_mode_portals.blend", None, "ASSET_07_ModePortals", None),
        ("08_floating_castle.blend", asset_units, "ASSET_08_FloatingCastle", "Lobby_FloatingCastle"),
    ]
    for blend, fn, coll, unit in plan:
        path = os.path.join(L.BLEND, blend)
        if not os.path.exists(path):
            print("SKIP (missing)", blend)
            continue
        if coll == "ARCH_SPAN":
            manifest.update(export_units(path, arch_span_units))
        elif blend.startswith("07"):
            manifest.update(export_units(path, mode_portal_units))
        elif blend.startswith("06"):
            manifest.update(export_units(path, props_units))
        elif blend.startswith("02"):
            manifest.update(export_units(path, pedestal_units))
        else:
            manifest.update(export_units(path, fn(coll, unit)))
    with open(os.path.join(L.FBX, "roblox_manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    write_luau(manifest)


ARCH_SPAN_COLLS = ("ARCH_Column", "ARCH_Arch", "ARCH_Banner")


def arch_span_units():
    """Lobby arch: column + half arch + banner only (no floor slab / railing), plus a mirrored copy
    for the opposite side of the road."""
    objs = [o for n in ARCH_SPAN_COLLS for o in bpy.data.collections[n].all_objects]
    return [("Lobby_ArchSpan", objs), ("Lobby_ArchSpanMirrored", objs, True)]


def mode_portal_units():
    root = bpy.data.collections["ASSET_07_ModePortals"]
    return [(f"Lobby_PORTAL_{c.name.replace('MP_', '')}", list(c.all_objects)) for c in root.children]


def pedestal_units():
    """Each top-level child collection of the pedestal asset = one variant model;
    fall back to the whole asset if it has no children."""
    root = bpy.data.collections["ASSET_02_AbilityPedestals"]
    kids = [c for c in root.children if len(c.all_objects)]
    if not kids:
        return [("Lobby_AbilityPedestals", list(root.all_objects))]
    return [(f"Lobby_{c.name}", list(c.all_objects)) for c in kids]


def write_luau(manifest):
    lines = ["--!strict", "-- GENERATED by assets/lobby/scripts/export_roblox.py - do not edit by hand.",
             "-- Usage (Studio command bar, after importing an FBX with the 3D Importer):",
             "--   require(game.ReplicatedStorage.Shared.LobbyAssetStyler).style(workspace.Lobby_MarbleArch)",
             "-- or style every imported lobby model:  ...LobbyAssetStyler.styleAll(workspace)", "",
             "type PartSpec = { Material: string, Color: { number }, Reflectance: number?, Transparency: number?, Texture: string? }",
             "",
             "-- Upload textures/<name>_albedo.png and _normal.png (Asset Manager / Creator Hub) and paste the",
             "-- rbxassetid:// ids here. While empty, textured parts fall back to a plain Slate material.",
             "local TEXTURES: { [string]: { ColorMap: string, NormalMap: string } } = {",
             "\tcobblestone = { ColorMap = \"\", NormalMap = \"\" },",
             "}",
             "local TEXTURE_FALLBACK_COLOR = Color3.fromRGB(110, 112, 140)",
             "type UnitSpec = { size: { number }, parts: { [string]: PartSpec } }", "",
             "local UNITS: { [string]: UnitSpec } = {"]
    for unit, u in sorted(manifest.items()):
        lines.append(f'\t["{unit}"] = {{')
        lines.append(f"\t\tsize = {{ {', '.join(str(v) for v in u['size_studs'])} }},")
        lines.append("\t\tparts = {")
        for p in u["parts"]:
            r = p["roblox"]
            extra = ""
            if "Texture" in r:
                extra += f', Texture = "{r["Texture"]}"'
            if "Reflectance" in r:
                extra += f", Reflectance = {r['Reflectance']}"
            if "Transparency" in r:
                extra += f", Transparency = {r['Transparency']}"
            col = ", ".join(str(v) for v in r["Color"])
            lines.append(f'\t\t\t["{p["part"]}"] = {{ Material = "{r["Material"]}", Color = {{ {col} }}{extra} }},')
        lines.append("\t\t},")
        lines.append("\t},")
    lines += ["}", "",
              "local LobbyAssetStyler = {}", "",
              "local function applyPart(part: BasePart, spec: PartSpec)",
              "\tpart.Material = (Enum.Material :: any)[spec.Material]",
              "\tpart.Color = Color3.new(spec.Color[1], spec.Color[2], spec.Color[3])",
              "\tpart.Reflectance = spec.Reflectance or 0",
              "\tpart.Transparency = spec.Transparency or 0",
              "\tpart.Anchored = true",
              "\tif spec.Texture then",
              "\t\tlocal tex = TEXTURES[spec.Texture]",
              "\t\tif tex and tex.ColorMap ~= \"\" then",
              "\t\t\tlocal sa = part:FindFirstChildOfClass(\"SurfaceAppearance\") or Instance.new(\"SurfaceAppearance\")",
              "\t\t\tsa.ColorMap = tex.ColorMap",
              "\t\t\tsa.NormalMap = tex.NormalMap",
              "\t\t\tsa.Parent = part",
              "\t\telse",
              "\t\t\tpart.Material = Enum.Material.Slate",
              "\t\t\tpart.Color = TEXTURE_FALLBACK_COLOR",
              "\t\tend",
              "\tend",
              "\tif spec.Material == \"Neon\" then",
              "\t\tpart.CastShadow = false",
              "\tend",
              "end", "",
              "function LobbyAssetStyler.style(model: Model, unitName: string?)",
              "\tlocal name = unitName or model.Name",
              "\tlocal unit = UNITS[name]",
              "\tassert(unit, \"LobbyAssetStyler: unknown unit \" .. name)",
              "\tfor _, d in model:GetDescendants() do",
              "\t\tif d:IsA(\"BasePart\") then",
              "\t\t\tlocal key = d.Name:gsub(\"%.%d+$\", \"\")",
              "\t\t\tlocal spec = unit.parts[key]",
              "\t\t\tif spec then",
              "\t\t\t\tapplyPart(d, spec)",
              "\t\t\tend",
              "\t\tend",
              "\tend",
              "\t-- Rescale so the model matches its Blender size (1 Blender unit = 1 stud).",
              "\tlocal _, extents = model:GetBoundingBox()",
              "\tlocal want = math.max(unit.size[1], unit.size[2], unit.size[3])",
              "\tlocal have = math.max(extents.X, extents.Y, extents.Z)",
              "\tif have > 0 and math.abs(have - want) / want > 0.02 then",
              "\t\tmodel:ScaleTo(model:GetScale() * want / have)",
              "\tend",
              "end", "",
              "function LobbyAssetStyler.styleAll(container: Instance)",
              "\tfor _, m in container:GetDescendants() do",
              "\t\tif m:IsA(\"Model\") and UNITS[m.Name] then",
              "\t\t\tLobbyAssetStyler.style(m)",
              "\t\tend",
              "\tend",
              "end", "",
              "LobbyAssetStyler.UNITS = UNITS",
              "return LobbyAssetStyler", ""]
    os.makedirs(os.path.dirname(LUAU_OUT), exist_ok=True)
    with open(LUAU_OUT, "w") as fh:
        fh.write("\n".join(lines))
    print("LUAU", LUAU_OUT)


if __name__ == "__main__":
    main()
