"""Shared helpers for the arena lobby asset kit (headless bpy, Blender 5.x).

Units: 1 Blender unit = 1 Roblox stud.  +Z up, model fronts face -Y.
Every asset script imports this module, builds into its own collection,
renders inspection views, and saves a .blend.
"""
import bpy, bmesh, math, os, random
from mathutils import Vector, Matrix, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # assets/lobby
RENDERS = os.path.join(ROOT, "renders")
BLEND = os.path.join(ROOT, "blend")
FBX = os.path.join(ROOT, "fbx")
TEXTURES_DIR = os.path.join(ROOT, "textures")
FONT_BLACK = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
FONT_XBOLD = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"

# --------------------------------------------------------------------------- scene

def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _MATS.clear()


def coll(name, parent=None):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    p = parent or bpy.context.scene.collection
    if c.name not in [x.name for x in p.children]:
        p.children.link(c)
    return c


def _link(obj, c):
    (c or bpy.context.scene.collection).objects.link(obj)
    return obj


def mesh_obj(name, verts, faces, mat=None, c=None, smooth=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate()
    me.update()
    ob = bpy.data.objects.new(name, me)
    _link(ob, c)
    if mat:
        me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def from_bmesh(name, bm, mat=None, c=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.update()
    ob = bpy.data.objects.new(name, me)
    _link(ob, c)
    if mat:
        me.materials.append(mat)
    return ob


# Global edge treatment.  The references show crisp, planar forms with only a thin
# highlight edge - NOT pillowy rounded blocks.  Every bevel request is scaled down
# here, and small ones become single-segment chamfers.
BEVEL_SCALE = 0.35


def add_bevel(ob, width=0.08, segs=2, angle=35, harden=True):
    if width <= 0:
        return ob
    width *= BEVEL_SCALE
    if width < 0.04:
        segs = 1
    m = ob.modifiers.new("Bevel", "BEVEL")
    m.width = width
    m.segments = segs
    m.limit_method = "ANGLE"
    m.angle_limit = math.radians(angle)
    m.harden_normals = harden
    m.miter_outer = "MITER_ARC"
    for p in ob.data.polygons:
        p.use_smooth = True
    return ob


def box(name, size, loc=(0, 0, 0), mat=None, bevel=0.08, segs=2, c=None, rot=(0, 0, 0)):
    """Axis box; `loc` is the CENTER of the box."""
    sx, sy, sz = size
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    ob = from_bmesh(name, bm, mat, c)
    ob.location = loc
    ob.rotation_euler = rot
    add_bevel(ob, min(bevel, 0.45 * min(size)), segs)
    return ob


def cyl(name, r, h, loc=(0, 0, 0), mat=None, verts=32, bevel=0.05, segs=2, c=None, rot=(0, 0, 0), r2=None):
    """Cylinder/cone standing on z (loc = center)."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=verts,
                          radius1=r, radius2=r if r2 is None else r2, depth=h)
    ob = from_bmesh(name, bm, mat, c)
    ob.location = loc
    ob.rotation_euler = rot
    add_bevel(ob, min(bevel, 0.4 * h), segs)
    return ob


def ring(name, r_out, r_in, h, loc=(0, 0, 0), mat=None, verts=48, c=None, bevel=0.0):
    """Flat annulus (tube) standing on z, loc = center."""
    vs, fs = [], []
    for i in range(verts):
        a = 2 * math.pi * i / verts
        ca, sa = math.cos(a), math.sin(a)
        vs += [(r_out * ca, r_out * sa, -h / 2), (r_out * ca, r_out * sa, h / 2),
               (r_in * ca, r_in * sa, h / 2), (r_in * ca, r_in * sa, -h / 2)]
    for i in range(verts):
        j = (i + 1) % verts
        a, b = 4 * i, 4 * j
        for k in range(4):
            k2 = (k + 1) % 4
            fs.append((a + k, b + k, b + k2, a + k2))
    ob = mesh_obj(name, vs, fs, mat, c)
    ob.location = loc
    if bevel:
        add_bevel(ob, bevel, 2)
    return ob


def extrude_polygon(name, pts2d, depth, mat=None, c=None, plane="XZ", bevel=0.0, segs=2, center_depth=True):
    """Extrude a closed 2D outline (counter-clockwise) into a slab.
    plane XZ: outline in (x,z), extruded along +Y (front face at -depth/2)."""
    bm = bmesh.new()
    n = len(pts2d)
    off = -depth / 2 if center_depth else 0.0
    front = [bm.verts.new(_p3(p, off, plane)) for p in pts2d]
    back = [bm.verts.new(_p3(p, off + depth, plane)) for p in pts2d]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((front[j], front[i], back[i], back[j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # triangulate n-gons cleanly for concave outlines (beauty)
    ngons = [f for f in bm.faces if len(f.verts) > 4]
    if ngons:
        bmesh.ops.triangulate(bm, faces=ngons, quad_method="BEAUTY", ngon_method="EAR_CLIP")
    ob = from_bmesh(name, bm, mat, c)
    if bevel:
        add_bevel(ob, bevel, segs, angle=30)
    return ob


def _p3(p, d, plane):
    if plane == "XZ":
        return (p[0], d, p[1])
    if plane == "XY":
        return (p[0], p[1], d)
    if plane == "YZ":
        return (d, p[0], p[1])


def text_mesh(name, body, size=1.0, extrude=0.1, font=FONT_BLACK, mat=None, c=None,
              loc=(0, 0, 0), rot=(math.pi / 2, 0, 0), spacing=1.0, line_spacing=1.0, bevel=0.0):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.extrude = extrude
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.space_character = spacing
    cu.space_line = line_spacing
    cu.bevel_depth = bevel
    cu.resolution_u = 4
    ob = bpy.data.objects.new(name, cu)
    _link(ob, c)
    ob.location = loc
    ob.rotation_euler = rot
    if mat:
        cu.materials.append(mat)
    return to_mesh(ob)


def to_mesh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    new = bpy.data.objects.new(ob.name, me)
    for c in ob.users_collection:
        c.objects.link(new)
    new.matrix_world = ob.matrix_world
    name = ob.name
    bpy.data.objects.remove(ob)
    new.name = name
    return new


def parent_to(children, parent):
    for ch in children:
        mw = ch.matrix_world.copy()
        ch.parent = parent
        ch.matrix_world = mw


def empty(name, loc=(0, 0, 0), c=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "PLAIN_AXES"
    e.location = loc
    return _link(e, c)


def join(objs, name):
    """Apply modifiers and join into one mesh object (for export variants)."""
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    mats, mat_index = [], {}
    for ob in objs:
        if ob.type != "MESH":
            continue
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        me.transform(ob.matrix_world)
        remap = []
        for m in me.materials:
            if m.name not in mat_index:
                mat_index[m.name] = len(mats)
                mats.append(m)
            remap.append(mat_index[m.name])
        for p in me.polygons:
            if remap:
                p.material_index = remap[p.material_index]
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    return ob

# --------------------------------------------------------------------------- materials
_MATS = {}


def _new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links, m.node_tree.nodes["Principled BSDF"]


def flat(name, color, rough=0.5, metal=0.0, spec=0.5, coat=0.0):
    if name in _MATS:
        return _MATS[name]
    m, n, l, b = _new_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    b.inputs["Specular IOR Level"].default_value = spec
    b.inputs["Coat Weight"].default_value = coat
    m.diffuse_color = (*color, 1)
    _MATS[name] = m
    return m


def emissive(name, color, strength=6.0, base=None):
    """Glowing material.  `color` drives emission; base defaults to a pale version."""
    if name in _MATS:
        return _MATS[name]
    m, n, l, b = _new_mat(name)
    base = base or tuple(min(1, 0.55 + 0.45 * c) for c in color)
    b.inputs["Base Color"].default_value = (*base, 1)
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength
    b.inputs["Roughness"].default_value = 0.3
    m.diffuse_color = (*color, 1)
    m["roblox_neon"] = True
    _MATS[name] = m
    return m


def glass_emissive(name, color, strength=2.5, alpha=0.75):
    """Translucent glowing crystal / potion glass."""
    if name in _MATS:
        return _MATS[name]
    m, n, l, b = _new_mat(name)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Emission Color"].default_value = (*color, 1)
    b.inputs["Emission Strength"].default_value = strength
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Coat Weight"].default_value = 0.6
    b.inputs["Alpha"].default_value = alpha
    m.diffuse_color = (*color, 1)
    m["roblox_neon"] = True
    _MATS[name] = m
    return m


def marble(name="MAT_Marble", base=(0.86, 0.83, 0.90), tint=(0.76, 0.71, 0.84),
           vein=(0.58, 0.53, 0.66), scale=0.22, vein_width=0.016):
    """Stylised white/lavender marble: soft two-tone cloud + thin dark veins."""
    if name in _MATS:
        return _MATS[name]
    m, n, l, b = _new_mat(name)
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    # cloudy tint
    cloud = n.new("ShaderNodeTexNoise")
    cloud.inputs["Scale"].default_value = 1.6
    cloud.inputs["Detail"].default_value = 3
    l.new(mp.outputs["Vector"], cloud.inputs["Vector"])
    cr = n.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].position = 0.35
    cr.color_ramp.elements[0].color = (*base, 1)
    cr.color_ramp.elements[1].position = 0.75
    cr.color_ramp.elements[1].color = (*tint, 1)
    l.new(cloud.outputs["Fac"], cr.inputs["Fac"])
    # veins: distorted noise, take |v-0.5| narrow band
    vn = n.new("ShaderNodeTexNoise")
    vn.inputs["Scale"].default_value = 1.4
    vn.inputs["Detail"].default_value = 3
    vn.inputs["Distortion"].default_value = 0.4
    l.new(mp.outputs["Vector"], vn.inputs["Vector"])
    sub = n.new("ShaderNodeMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = 0.5
    l.new(vn.outputs["Fac"], sub.inputs[0])
    ab = n.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"
    l.new(sub.outputs[0], ab.inputs[0])
    vr = n.new("ShaderNodeValToRGB")
    vr.color_ramp.elements[0].position = 0.0
    vr.color_ramp.elements[0].color = (1, 1, 1, 1)
    vr.color_ramp.elements[1].position = vein_width
    vr.color_ramp.elements[1].color = (0, 0, 0, 1)
    l.new(ab.outputs[0], vr.inputs["Fac"])
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["B"].default_value = (*vein, 1)
    l.new(vr.outputs["Color"], mix.inputs["Factor"])
    l.new(cr.outputs["Color"], mix.inputs["A"])
    l.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.32
    b.inputs["Coat Weight"].default_value = 0.25
    m.diffuse_color = (*base, 1)
    m["roblox_material"] = "Marble"
    _MATS[name] = m
    return m


def varied(name, colors, rough=0.7, metal=0.0, attr="Random"):
    """Per-object colour variation (cobblestones, books, crates)."""
    if name in _MATS:
        return _MATS[name]
    m, n, l, b = _new_mat(name)
    oi = n.new("ShaderNodeObjectInfo")
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT" if len(colors) > 2 else "LINEAR"
    els = ramp.color_ramp.elements
    while len(els) < len(colors):
        els.new(0.5)
    for i, col in enumerate(colors):
        els[i].position = i / len(colors)
        els[i].color = (*col, 1)
    l.new(oi.outputs[attr], ramp.inputs["Fac"])
    l.new(ramp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    m.diffuse_color = (*colors[0], 1)
    _MATS[name] = m
    return m


WOOD_TILE = 6.0       # studs per wood-grain repeat (make_textures.wood_grain)


def wood(name="MAT_Wood", light=(0.62, 0.36, 0.17), dark=(0.42, 0.22, 0.09), scale=1.0, axis="Z"):
    """Stylised timber.  Every wood material shares ONE tileable grain texture (textures/wood_grain.png)
    at the same density; only the tint (dark -> light) differs per material.  Grain direction comes from
    per-object UVs laid along each plank's long axis (plank_uv, applied automatically in save_blend), so
    posts, beams, planks and crates all read uniformly.  `scale`/`axis` are kept for compatibility."""
    if name in _MATS:
        return _MATS[name]
    m, n, l, b = _new_mat(name)
    uvn = n.new("ShaderNodeUVMap")
    img = n.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(os.path.join(TEXTURES_DIR, "wood_grain.png"), check_existing=True)
    img.image.colorspace_settings.name = "Non-Color"
    l.new(uvn.outputs["UV"], img.inputs["Vector"])
    r = n.new("ShaderNodeValToRGB")
    r.color_ramp.elements[0].position = 0.3          # grain map spans ~0.3-0.7: stretch it to the tint range
    r.color_ramp.elements[0].color = (*dark, 1)
    r.color_ramp.elements[1].position = 0.7
    r.color_ramp.elements[1].color = (*light, 1)
    l.new(img.outputs["Color"], r.inputs["Fac"])
    l.new(r.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    m.diffuse_color = (*[(a + c) / 2 for a, c in zip(light, dark)], 1)
    m["roblox_material"] = "Wood"
    m["wood_uv"] = True
    _MATS[name] = m
    return m


def plank_uv(ob, tile=WOOD_TILE):
    """Grain-aligned UVs: on every face, U runs along the longer of the face's two in-plane object
    axes (so grain follows the plank), in studs / tile, with a per-object offset so neighbouring
    planks do not repeat the same streaks."""
    import hashlib
    me = ob.data
    if not me.vertices:
        return
    xs = [v.co for v in me.vertices]
    dims = [max(c[i] for c in xs) - min(c[i] for c in xs) for i in range(3)]
    h = hashlib.md5(ob.name.encode()).digest()
    ou, ov = h[0] / 255.0, h[1] / 255.0
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        a, b = [i for i in range(3) if i != ax]
        u_ax, v_ax = (a, b) if dims[a] >= dims[b] else (b, a)
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[u_ax] / tile + ou, lp.vert.co[v_ax] / tile + ov)
    bm.to_mesh(me)
    bm.free()


def apply_wood_uvs():
    for ob in bpy.data.objects:
        if ob.type == "MESH" and any(m and m.get("wood_uv") for m in ob.data.materials):
            plank_uv(ob)


def x_brace(name, w, h, bar, depth, mat, c):
    """ONE solid X brace (both planks merged) clipped exactly to a w x h frame opening, in the XZ plane,
    extruded `depth` along Y (centred).  No overlapping planks -> no z-fighting at the cross."""
    from shapely.geometry import Polygon, box as sbox
    from shapely.ops import unary_union

    def strip(p0, p1):
        d = (Vector(p1) - Vector(p0)).normalized()
        nrm = Vector((-d.y, d.x)) * (bar / 2)
        a, b = Vector(p0) - d * bar, Vector(p1) + d * bar
        return Polygon([tuple(a + nrm), tuple(b + nrm), tuple(b - nrm), tuple(a - nrm)])
    xs = unary_union([strip((-w / 2, -h / 2), (w / 2, h / 2)), strip((-w / 2, h / 2), (w / 2, -h / 2))])
    shape = xs.intersection(sbox(-w / 2, -h / 2, w / 2, h / 2))
    if shape.geom_type != "Polygon":
        shape = max(shape.geoms, key=lambda g: g.area)
    pts = [tuple(p) for p in list(shape.exterior.coords)[:-1]]
    return extrude_polygon(name, pts, depth, mat, c, bevel=0.02)


def stripes(name, c1, c2, width=1.0, axis=0, offset=0.0, rough=0.55):
    """Hard-edged stripes in object space along `axis` (0=X,1=Y,2=Z) - awning fabric."""
    if name in _MATS:
        return _MATS[name]
    m, n, l, b = _new_mat(name)
    tc = n.new("ShaderNodeTexCoord")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(tc.outputs["Object"], sep.inputs[0])
    add = n.new("ShaderNodeMath"); add.operation = "ADD"; add.inputs[1].default_value = offset
    l.new(sep.outputs[axis], add.inputs[0])
    div = n.new("ShaderNodeMath"); div.operation = "DIVIDE"; div.inputs[1].default_value = width
    l.new(add.outputs[0], div.inputs[0])
    mod = n.new("ShaderNodeMath"); mod.operation = "FLOORED_MODULO"; mod.inputs[1].default_value = 2.0
    l.new(div.outputs[0], mod.inputs[0])
    gt = n.new("ShaderNodeMath"); gt.operation = "GREATER_THAN"; gt.inputs[1].default_value = 1.0
    l.new(mod.outputs[0], gt.inputs[0])
    mix = n.new("ShaderNodeMix"); mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*c1, 1)
    mix.inputs["B"].default_value = (*c2, 1)
    l.new(gt.outputs[0], mix.inputs["Factor"])
    l.new(mix.outputs["Result"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Sheen Weight"].default_value = 0.3
    m.diffuse_color = (*c1, 1)
    _MATS[name] = m
    return m


# Shared palette -------------------------------------------------------------
def palette():
    return dict(
        marble=marble(),
        marble_dark=marble("MAT_MarbleShade", base=(0.80, 0.77, 0.88), tint=(0.72, 0.68, 0.84),
                           vein=(0.55, 0.51, 0.66)),
        gold=flat("MAT_Gold", (1.0, 0.62, 0.12), rough=0.3, metal=0.75),
        bronze=flat("MAT_Bronze", (0.46, 0.33, 0.21), rough=0.4, metal=0.6),
        navy=flat("MAT_NavyCloth", (0.02, 0.05, 0.28), rough=0.75),
        white=flat("MAT_WhiteEmblem", (0.95, 0.96, 1.0), rough=0.4),
        cyan=emissive("MAT_NeonCyan", (0.05, 0.75, 1.0), 3.2, base=(0.3, 0.9, 1.0)),
        cyan_soft=emissive("MAT_NeonCyanSoft", (0.2, 0.8, 1.0), 1.5),
        cobble=varied("MAT_Cobble", [(0.30, 0.30, 0.40), (0.25, 0.25, 0.35), (0.34, 0.33, 0.43),
                                     (0.28, 0.27, 0.38)], rough=0.8),
        grout=flat("MAT_Grout", (0.42, 0.36, 0.30), rough=0.95),
    )

# --------------------------------------------------------------------------- rendering

def setup_render(res=(1200, 1200), samples=48, transparent=False):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 6
    s.render.resolution_x, s.render.resolution_y = res
    s.render.resolution_percentage = 100
    s.render.film_transparent = transparent
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.view_settings.exposure = 0.0
    s.render.image_settings.file_format = "PNG"


def world_color(color=(0.82, 0.84, 0.88), strength=1.0, sky=False):
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    n, l = w.node_tree.nodes, w.node_tree.links
    bg = n["Background"]
    for x in list(n):
        if x.type not in ("BACKGROUND", "OUTPUT_WORLD"):
            n.remove(x)
    if sky:
        # simple vertical gradient: horizon pale, zenith blue (concept-art sky)
        tc = n.new("ShaderNodeTexCoord")
        sep = n.new("ShaderNodeSeparateXYZ")
        l.new(tc.outputs["Generated"], sep.inputs[0])
        r = n.new("ShaderNodeValToRGB")
        r.color_ramp.elements[0].position = 0.5
        r.color_ramp.elements[0].color = (0.50, 0.70, 1.0, 1)
        r.color_ramp.elements[1].position = 0.75
        r.color_ramp.elements[1].color = (0.10, 0.33, 0.92, 1)
        l.new(sep.outputs["Z"], r.inputs["Fac"])
        l.new(r.outputs["Color"], bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = (*color, 1)
    bg.inputs["Strength"].default_value = strength


def clear_rig():
    for ob in list(bpy.data.objects):
        if ob.name.startswith(("RIG_", "CAM_")):
            bpy.data.objects.remove(ob)


def sun(name, rot_deg, energy=3.0, color=(1, 0.97, 0.92), angle=8):
    d = bpy.data.lights.new(name, "SUN")
    d.energy = energy
    d.color = color
    d.angle = math.radians(angle)
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = [math.radians(a) for a in rot_deg]
    return o


def studio_lights():
    """Neutral inspection lighting: warm key sun, cool fill sun, bright grey world."""
    world_color((0.62, 0.64, 0.70), 0.75)
    sun("RIG_Key", (50, 0, -35), 2.4)
    sun("RIG_Fill", (65, 0, 140), 0.6, (0.85, 0.9, 1.0), 20)


def beauty_lights():
    world_color(sky=True, strength=0.8)
    sun("RIG_Key", (48, 0, -30), 2.6, (1.0, 0.95, 0.86), 6)
    sun("RIG_Fill", (70, 0, 150), 0.5, (0.75, 0.85, 1.0), 25)


def ground(size=200, color=(0.86, 0.86, 0.89), z=0.0):
    m = flat("MAT_InspectGround", color, rough=0.9)
    g = mesh_obj("RIG_Ground", [(-size, -size, z), (size, -size, z), (size, size, z), (-size, size, z)],
                 [(0, 1, 2, 3)], m)
    return g


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def camera(name, loc, target, lens=50.0, ortho=None):
    cd = bpy.data.cameras.new(name)
    if ortho:
        cd.type = "ORTHO"
        cd.ortho_scale = ortho
    else:
        cd.lens = lens
    cd.clip_end = 2000
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    look_at(o, target)
    return o


def render(cam, path, res=None):
    s = bpy.context.scene
    s.camera = cam
    if res:
        s.render.resolution_x, s.render.resolution_y = res
    s.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("RENDERED", path)
    return path


def bounds(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    mn = Vector((1e9, 1e9, 1e9)); mx = -mn
    for ob in objs:
        if ob.type != "MESH":
            continue
        for v in ob.bound_box:
            w = ob.matrix_world @ Vector(v)
            mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
    return mn, mx


def inspection_set(prefix, objs, outdir=RENDERS, res=900, samples=40, detail=None, three_q=(-1, -1.3, 0.7),
                   extra=()):
    """Front / right / rear ortho + 3/4 perspective (+ optional detail cams).
    `detail` = list of (label, cam_loc, target, lens)."""
    os.makedirs(outdir, exist_ok=True)
    setup_render((res, res), samples)
    mn, mx = bounds(objs)
    ctr = (mn + mx) / 2
    size = max(mx - mn) * 1.12
    far = size * 4
    out = []
    views = [("front", (0, -1, 0)), ("right", (1, 0, 0)), ("rear", (0, 1, 0)), ("left", (-1, 0, 0))]
    for label, d in views:
        c = camera(f"CAM_{label}", ctr + Vector(d) * far, ctr, ortho=size)
        out.append((label, render(c, os.path.join(outdir, f"{prefix}_{label}.png"))))
    tq = Vector(three_q).normalized()
    c = camera("CAM_3q", ctr + tq * size * 1.45, ctr, lens=45)
    out.append(("three_quarter", render(c, os.path.join(outdir, f"{prefix}_3q.png"))))
    for label, loc, tgt, lens in (detail or []):
        c = camera(f"CAM_{label}", loc, tgt, lens=lens)
        out.append((label, render(c, os.path.join(outdir, f"{prefix}_{label}.png"))))
    return out


def contact_sheet(items, out, cols=3, tile=600, title=None):
    """items = [(label, path)] -> labelled grid PNG (uses Pillow)."""
    from PIL import Image, ImageDraw, ImageFont
    rows = math.ceil(len(items) / cols)
    head = 60 if title else 0
    sheet = Image.new("RGB", (cols * tile, rows * (tile + 34) + head), (245, 245, 248))
    d = ImageDraw.Draw(sheet)
    try:
        f = ImageFont.truetype(FONT_XBOLD, 22)
        ft = ImageFont.truetype(FONT_BLACK, 32)
    except Exception:
        f = ft = ImageFont.load_default()
    if title:
        d.text((16, 12), title, fill=(30, 40, 90), font=ft)
    for i, (label, p) in enumerate(items):
        im = Image.open(p).convert("RGB")
        im.thumbnail((tile, tile))
        x = (i % cols) * tile; y = head + (i // cols) * (tile + 34)
        sheet.paste(im, (x + (tile - im.width) // 2, y + 34 + (tile - im.height) // 2))
        d.text((x + 10, y + 6), label.upper(), fill=(30, 40, 90), font=f)
    sheet.save(out)
    print("SHEET", out)
    return out


def save_blend(name):
    apply_wood_uvs()
    os.makedirs(BLEND, exist_ok=True)
    p = os.path.join(BLEND, name)
    bpy.ops.wm.save_as_mainfile(filepath=p, compress=True)
    print("SAVED", p)
    return p


# --------------------------------------------------------------------------- textured cobble floor
TEXTURES = os.path.join(ROOT, "textures")
COBBLE_TILE = 6.0          # studs per texture repeat (see make_textures.py)


def cobble_tex_material():
    """Image-textured cobblestone (albedo + normal), UV-mapped at COBBLE_TILE studs/repeat."""
    name = "MAT_CobbleTex"
    if name in _MATS:
        return _MATS[name]
    m, n, l, b = _new_mat(name)
    alb = n.new("ShaderNodeTexImage")
    alb.image = bpy.data.images.load(os.path.join(TEXTURES, "cobblestone_albedo.png"), check_existing=True)
    nrm = n.new("ShaderNodeTexImage")
    nrm.image = bpy.data.images.load(os.path.join(TEXTURES, "cobblestone_normal.png"), check_existing=True)
    nrm.image.colorspace_settings.name = "Non-Color"
    nm = n.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.8
    l.new(alb.outputs["Color"], b.inputs["Base Color"])
    l.new(nrm.outputs["Color"], nm.inputs["Color"])
    l.new(nm.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.8
    m.diffuse_color = (0.30, 0.30, 0.40, 1)
    m["roblox_texture"] = "cobblestone"
    _MATS[name] = m
    return m


def cobble_surface(name, x0, x1, y0, y1, top=0.0, thick=0.25, c=None, poly_holes=None):
    """Flat cobblestone floor slab (top at `top`) with world-aligned UVs (UV = worldXY / COBBLE_TILE),
    so neighbouring tiles continue the texture seamlessly."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(x1 - x0, y1 - y0, thick), verts=bm.verts)
    bmesh.ops.translate(bm, vec=((x0 + x1) / 2, (y0 + y1) / 2, top - thick / 2), verts=bm.verts)
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        ax = max(range(3), key=lambda i: abs(f.normal[i]))
        ui, vi = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co[ui] / COBBLE_TILE, lp.vert.co[vi] / COBBLE_TILE)
    ob = from_bmesh(name, bm, cobble_tex_material(), c)
    return ob


def tex_material(key, normal_strength=0.6, rough=0.55, fallback=(0.88, 0.86, 0.94)):
    """Image-textured material from textures/<key>_albedo.png + _normal.png (UV-mapped)."""
    name = f"MAT_Tex_{key}"
    if name in _MATS:
        return _MATS[name]
    m, n, l, b = _new_mat(name)
    alb = n.new("ShaderNodeTexImage")
    alb.image = bpy.data.images.load(os.path.join(TEXTURES, f"{key}_albedo.png"), check_existing=True)
    nrm = n.new("ShaderNodeTexImage")
    nrm.image = bpy.data.images.load(os.path.join(TEXTURES, f"{key}_normal.png"), check_existing=True)
    nrm.image.colorspace_settings.name = "Non-Color"
    nm = n.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = normal_strength
    l.new(alb.outputs["Color"], b.inputs["Base Color"])
    l.new(nrm.outputs["Color"], nm.inputs["Color"])
    l.new(nm.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    m.diffuse_color = (*fallback, 1)
    m["roblox_texture"] = key
    _MATS[name] = m
    return m


def world_box_uv(ob, tile):
    """Box-project UVs from WORLD coordinates (call after the object's final transform), so a
    tiling texture continues seamlessly across separate walls, towers and rotated pieces."""
    bpy.context.view_layer.update()
    mw = ob.matrix_world
    nmat = mw.to_3x3().inverted().transposed()
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        nw = nmat @ f.normal
        ax = max(range(3), key=lambda i: abs(nw[i]))
        ui, vi = [(1, 2), (0, 2), (0, 1)][ax]
        for lp in f.loops:
            w = mw @ lp.vert.co
            lp[uv].uv = (w[ui] / tile, w[vi] / tile)
    bm.to_mesh(ob.data)
    bm.free()
