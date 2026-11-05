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


def _is_neon(ob):
    return any(m and m.get("roblox_neon") for m in ob.data.materials)


def _short(name):
    """Object name without its asset prefix (MKT_, GATE_, MP_DUELS_ ...)."""
    t = name.split("_")
    if t[0] == "MP" and len(t) > 2:
        t = t[2:]
    elif len(t) > 1:
        t = t[1:]
    return "_".join(t)


def _group_name(ob):
    c = ob.users_collection[0].name if ob.users_collection else "Misc"
    return c.split("_")[-1] if "_" in c else c


def _item_name(objs, group):
    shorts = sorted(_short(o.name) for o in objs)
    pre = os.path.commonprefix(shorts).rstrip("_-.0123456789") if len(shorts) > 1 else shorts[0]
    if len(pre) < 3:
        toks = {s_.split("_")[0].rstrip("0123456789") for s_ in shorts}
        # a cluster of many different part kinds is the group's main body (Canopy, Counter, Structure...)
        pre = group if len(toks) > 2 else sorted(toks)[0]
    return pre.replace(".", "")


def _clusters(objs, gap=0.05):
    """Connected components of objects whose world bounding boxes touch -> one physical item each."""
    boxes = []
    for o in objs:
        cs = [o.matrix_world @ Vector(c) for c in o.bound_box]
        boxes.append((Vector([min(c[i] for c in cs) for i in range(3)]) - Vector((gap,) * 3),
                      Vector([max(c[i] for c in cs) for i in range(3)]) + Vector((gap,) * 3)))
    parent = list(range(len(objs)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            (a0, a1), (b0, b1) = boxes[i], boxes[j]
            if all(a0[k] <= b1[k] and b0[k] <= a1[k] for k in range(3)):
                parent[find(i)] = find(j)
    out = {}
    for i, o in enumerate(objs):
        out.setdefault(find(i), []).append(o)
    return sorted(out.values(), key=lambda cl: _short(cl[0].name))


def _mesh_bms(ob, dg, mirror):
    """Evaluated, world-space bmesh per material slot: [(matkey, bm, tris)]."""
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    me.transform(ob.matrix_world)
    if mirror:                      # mirrored variant (Roblox cannot use negative scale)
        me.transform(MIRROR_X)
        me.flip_normals()
    mats = list(me.materials) or [None]
    res = []
    for mi, m in enumerate(mats):
        bm = bmesh.new()
        bm.from_mesh(me)
        if len(mats) > 1:
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index != mi], context="FACES")
        if bm.faces:
            res.append((m.name if m else "MAT_Default", bm, sum(len(f.verts) - 2 for f in bm.faces)))
        else:
            bm.free()
    bpy.data.meshes.remove(me)
    return res


def _emit(name, key, bms, parent):
    me = bpy.data.meshes.new(name)
    acc = bmesh.new()
    for bm in bms:
        tmp = bpy.data.meshes.new("tmp"); bm.to_mesh(tmp); bm.free()
        acc.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    bmesh.ops.remove_doubles(acc, verts=acc.verts, dist=1e-5)
    if not mat_has_texture(key):
        box_uv(acc)              # textured materials keep their authored world-aligned UVs
    tris = sum(len(f.verts) - 2 for f in acc.faces)
    acc.to_mesh(me); acc.free()
    mat = bpy.data.materials.get(key)
    if mat:
        me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    return ob, tris


def merge_by_material(unit, objs, mirror=False):
    """Editable Roblox hierarchy for one unit:
         <Group>  (empty -> Model; from the Blender sub-collection: Structure, Canopy, Crates ...)
           <Group>_<Item>  (empty -> Model; one physical thing = objects whose boxes touch)
             <Material>__<Item>      merged MeshPart per material
             <Material>__<Piece>     every NEON / glowing piece as its OWN MeshPart
       Part names start with the material key so LobbyAssetStyler can style any part by name."""
    dg = bpy.context.evaluated_depsgraph_get()
    meshes = [o for o in objs if o.type in ("MESH", "CURVE", "FONT") and not o.hide_render]
    by_group = {}
    for o in meshes:
        by_group.setdefault(_group_name(o), []).append(o)
    out, info = [], []
    used = set()

    def uniq(n):
        base, k = n, 2
        while n in used:
            n = f"{base}{k}"; k += 1
        used.add(n)
        return n
    for group, gobs in sorted(by_group.items()):
        gname = uniq(group)
        g_empty = bpy.data.objects.new(gname, None)
        bpy.context.scene.collection.objects.link(g_empty)
        out.append(g_empty)
        clusters = _clusters(gobs)
        for cl in clusters:
            if len(clusters) == 1:              # one item: parts sit directly in the group model
                item, iname, i_empty = group, gname, g_empty
            else:
                item = _item_name(cl, group)
                iname = uniq(f"{group}_Main" if item == group else f"{group}_{item}")
                i_empty = bpy.data.objects.new(iname, None)
                bpy.context.scene.collection.objects.link(i_empty)
                i_empty.parent = g_empty
                out.append(i_empty)
            buckets = {}
            for o in cl:
                for key, bm, t in _mesh_bms(o, dg, mirror):
                    if _is_neon(o):           # neon pieces stay individual
                        pn = uniq(f"{key.replace('MAT_', '')}__{_short(o.name)}")
                        ob, tris = _emit(pn, key, [bm], i_empty)
                        out.append(ob)
                        info.append({"part": pn, "material": key, "tris": tris, "group": gname, "item": iname,
                                     "neon": True})
                    else:
                        buckets.setdefault(key, []).append((bm, t))
            for key, parts in sorted(buckets.items()):
                chunks, cur, cur_t = [], [], 0
                for bm, t in parts:
                    if cur and cur_t + t > TRI_LIMIT:
                        chunks.append(cur); cur, cur_t = [], 0
                    cur.append(bm); cur_t += t
                if cur:
                    chunks.append(cur)
                for ci, ch in enumerate(chunks):
                    pn = uniq(f"{key.replace('MAT_', '')}__{item}" + (f"_p{ci + 1}" if len(chunks) > 1 else ""))
                    ob, tris = _emit(pn, key, ch, i_empty)
                    out.append(ob)
                    info.append({"part": pn, "material": key, "tris": tris, "group": gname, "item": iname})
    for d in info:
        m = bpy.data.materials.get(d["material"])
        d["roblox"] = roblox_props(m) if m else {"Material": "SmoothPlastic"}
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
            if ob.type == "MESH":
                ob.data.transform(__import__("mathutils").Matrix.Translation(-origin))
        bpy.ops.object.select_all(action="DESELECT")
        for ob in new:
            ob.select_set(True)
        path = os.path.join(L.FBX, f"{unit}.fbx")
        os.makedirs(L.FBX, exist_ok=True)
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH", "EMPTY"},
                                 apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL",
                                 axis_forward="-Z", axis_up="Y", use_mesh_modifiers=False,
                                 mesh_smooth_type="FACE", add_leaf_bones=False, bake_anim=False,
                                 path_mode="STRIP")
        size = mx - mn
        results[unit] = {"fbx": os.path.relpath(path, L.ROOT), "size_studs": [round(v, 3) for v in size],
                         "parts": info, "tris_total": sum(i["tris"] for i in info)}
        nparts = sum(1 for o in new if o.type == "MESH")
        nitems = sum(1 for o in new if o.type == "EMPTY" and o.parent)
        print(f"EXPORT {unit}: {nparts} parts in {nitems} items, {results[unit]['tris_total']} tris, size {tuple(round(v, 2) for v in size)}")
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
    mats = {}
    for u in manifest.values():
        for p in u["parts"]:
            mats[p["material"].replace("MAT_", "")] = p["roblox"]
    tex_keys = sorted({r["Texture"] for r in mats.values() if "Texture" in r})
    L_ = ["--!strict", "-- GENERATED by assets/lobby/scripts/export_roblox.py - do not edit by hand.",
          "-- Imported model layout (3D Importer keeps the FBX hierarchy):",
          "--   <Model>  >  <Group> (Structure, Canopy, Crates ...)  >  <Group>_<Item> (one crate, one lantern ...)",
          "--     >  MeshParts named  <Material>__<Item>  or, for every glowing piece,  <Material>__<Piece>",
          "-- Usage (Studio command bar, after importing):",
          "--   require(game.ReplicatedStorage.Shared.LobbyAssetStyler).styleAll(workspace)",
          "-- Every neon part gets the CollectionService tag \"LobbyNeon\" and attribute Neon = true.", "",
          "type PartSpec = { Material: string, Color: { number }, Reflectance: number?, Transparency: number?, Texture: string? }",
          "",
          "-- Upload textures/<name>_albedo.png and _normal.png and paste the rbxassetid:// ids here.",
          "-- While empty, textured parts fall back to a plain Slate material.",
          "local TEXTURES: { [string]: { ColorMap: string, NormalMap: string } } = {",
          *[f'\t{k} = {{ ColorMap = "", NormalMap = "" }},' for k in tex_keys],
          "}",
          "local TEXTURE_FALLBACK_COLOR = Color3.fromRGB(110, 112, 140)", "",
          "-- material key (prefix of every part name) -> Roblox appearance",
          "local MATERIALS: { [string]: PartSpec } = {"]
    for key, r in sorted(mats.items()):
        extra = ""
        if "Texture" in r:
            extra += f', Texture = "{r["Texture"]}"'
        if "Reflectance" in r:
            extra += f", Reflectance = {r['Reflectance']}"
        if "Transparency" in r:
            extra += f", Transparency = {r['Transparency']}"
        col = ", ".join(str(v) for v in r["Color"])
        L_.append(f'\t["{key}"] = {{ Material = "{r["Material"]}", Color = {{ {col} }}{extra} }},')
    L_ += ["}", "", "-- model name -> size in studs (used to undo any importer unit conversion)",
           "local UNITS: { [string]: { size: { number } } } = {"]
    for unit, u in sorted(manifest.items()):
        L_.append(f'\t["{unit}"] = {{ size = {{ {", ".join(str(v) for v in u["size_studs"])} }} }},')
    L_ += ["}", "",
           "local CollectionService = game:GetService(\"CollectionService\")",
           "local LobbyAssetStyler = {}", "",
           "local function materialKey(name: string): string",
           "\tlocal base = name:gsub(\"%.%d+$\", \"\")",
           "\treturn base:match(\"^(.-)__\") or base",
           "end", "",
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
           "\tif spec.Material == \"Neon\" or spec.Material == \"Glass\" then",
           "\t\tpart.CastShadow = false",
           "\t\tpart.CanCollide = false",
           "\t\tpart:SetAttribute(\"Neon\", true)",
           "\t\tCollectionService:AddTag(part, \"LobbyNeon\")",
           "\tend",
           "end", "",
           "function LobbyAssetStyler.style(model: Model)",
           "\tfor _, d in model:GetDescendants() do",
           "\t\tif d:IsA(\"BasePart\") then",
           "\t\t\tlocal spec = MATERIALS[materialKey(d.Name)]",
           "\t\t\tif spec then",
           "\t\t\t\tapplyPart(d, spec)",
           "\t\t\tend",
           "\t\tend",
           "\tend",
           "\tlocal unit = UNITS[model.Name]",
           "\tif unit then  -- rescale to the Blender size (1 Blender unit = 1 stud)",
           "\t\tlocal _, extents = model:GetBoundingBox()",
           "\t\tlocal want = math.max(unit.size[1], unit.size[2], unit.size[3])",
           "\t\tlocal have = math.max(extents.X, extents.Y, extents.Z)",
           "\t\tif have > 0 and math.abs(have - want) / want > 0.02 then",
           "\t\t\tmodel:ScaleTo(model:GetScale() * want / have)",
           "\t\tend",
           "\tend",
           "end", "",
           "function LobbyAssetStyler.styleAll(container: Instance)",
           "\tfor _, m in container:GetDescendants() do",
           "\t\tif m:IsA(\"Model\") and UNITS[m.Name] then",
           "\t\t\tLobbyAssetStyler.style(m)",
           "\t\tend",
           "\tend",
           "end", "",
           "LobbyAssetStyler.MATERIALS = MATERIALS",
           "LobbyAssetStyler.UNITS = UNITS",
           "return LobbyAssetStyler", ""]
    os.makedirs(os.path.dirname(LUAU_OUT), exist_ok=True)
    with open(LUAU_OUT, "w") as fh:
        fh.write("\n".join(L_))
    print("LUAU", LUAU_OUT)


if __name__ == "__main__":
    main()
