"""Re-texture the Hellhound in the Lava Scorpion style (geometry, rig and weights are untouched).

usage: python3 retexture.py [path/to/Hellhound_Model.fbx]

Every face is classified by the colour region it used in the original atlas, then re-UV'd onto one
cell of the lava atlas (make_textures.py):
  grey stone  -> charcoal rock with Roblox studs + lava seams/cracks   (R / D / R**C cells)
  red-orange  -> magma rock (deep red, studs, glowing seams)            (M cells)
  flame tones -> studded hot tones deep red -> hot yellow               (T1..T4)
  cream       -> hot-yellow claws / teeth / horns                       (TOOTH)
  white / red -> glowing eyes / pupils                                  (EYE / EYE2)
  deep red    -> glowing maw                                             (MAW)
  charcoal / black -> plain dark rock                                   (D cells)
Thin bevel strips and corner triangles become ember edges (EMB / EMB2) so the lava shows along block edges.
The stud count per face = round(face size / STUD), clamped 1..3, so studs stay a constant size.
"""
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "Hellhound_Model_original.fbx")
ATLAS = json.load(open(os.path.join(HERE, "atlas_regions.json")))
TEX = os.path.join(ROOT, "textures")
STUD = 0.32      # world size of one stud (model units)
STRIP = 0.06     # faces thinner than this are bevel strips
PAD = 2 / 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=SRC)
ob = bpy.data.objects["HellhoundMesh"]
me = ob.data
uv = me.uv_layers.active.data


def region(u, v):
    """Which colour region of the ORIGINAL atlas a UV point lies in."""
    x, y = u * 1024, (1 - v) * 1024
    if y < 512:
        if x < 512:
            return "stone"
        if y < 256:
            return "redorange"
        return "charcoal" if x < 768 else "deepred"
    row, col = (0 if y < 768 else 1), int(x // 256)
    return ["cream", "yellow", "orange", "orangered", "redorange2", "white", "red", "black"][row * 4 + col]


FLAT = {"cream": "TOOTH", "yellow": "T4", "orange": "T3", "orangered": "T2", "redorange2": "T1",
        "white": "EYE", "red": "EYE2", "deepred": "MAW", "black": "D11"}


def cell_for(reg, nu, nv, strip, top):
    nu, nv = max(1, min(3, nu)), max(1, min(3, nv))
    if reg == "stone":
        if strip:
            return "EMB"
        if top and (nu, nv) in ((2, 2), (3, 3), (3, 2), (2, 3)):
            return {(2, 2): "R22C", (3, 3): "R33C"}.get((nu, nv), "R32C")
        return f"R{nu}{nv}" if min(nu, nv) >= 2 else f"D{nu}{nv}"
    if reg == "redorange":
        return "EMB2" if strip else f"M{nu}{nv}"
    if reg == "charcoal":
        return "EMB" if strip else f"D{nu}{nv}"
    return FLAT[reg]


# classify every face from its ORIGINAL uv before overwriting
plan = []
counts = {}
for p in me.polygons:
    li = list(p.loop_indices)
    u = sum(uv[l].uv.x for l in li) / len(li)
    v = sum(uv[l].uv.y for l in li) / len(li)
    reg = region(u, v)
    co = [me.vertices[me.loops[l].vertex_index].co for l in li]
    edges = [(co[(k + 1) % len(co)] - co[k]).length for k in range(len(co))]
    if len(co) == 4:
        su, sv = (edges[0] + edges[2]) / 2, (edges[1] + edges[3]) / 2
        strip = min(su, sv) < STRIP
    else:
        su = sv = max(edges)
        strip = max(edges) < 0.12  # bevel corner triangle
    top = p.normal.z > 0.7
    cell = cell_for(reg, round(su / STUD), round(sv / STUD), strip, top)
    plan.append((p.index, cell, len(co)))
    counts[cell] = counts.get(cell, 0) + 1

# write the new UVs: each face fills its cell
QUAD = [(0, 0), (1, 0), (1, 1), (0, 1)]
TRI = [(0, 0), (1, 0), (0.5, 1)]
for pi, cell, n in plan:
    u0, v0, u1, v1 = ATLAS[cell]
    corners = QUAD if n == 4 else TRI
    for k, l in enumerate(me.polygons[pi].loop_indices):
        a, b = corners[k] if k < len(corners) else (0.5, 0.5)
        uv[l].uv = (u0 + PAD + a * (u1 - u0 - 2 * PAD), v0 + PAD + b * (v1 - v0 - 2 * PAD))

# lava material (Principled BSDF only -> exports cleanly)
old = ob.material_slots[0].material
mat = bpy.data.materials.new("MAT-LavaHellhound")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]


def teximg(fname, cs, y):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(os.path.join(TEX, fname))
    n.image.colorspace_settings.name = cs
    n.location = (-600, y)
    return n


tc = teximg("LavaHellhound_Color.png", "sRGB", 300)
te = teximg("LavaHellhound_Emission.png", "sRGB", 0)
tn = teximg("LavaHellhound_Normal.png", "Non-Color", -300)
nm = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(tc.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(te.outputs["Color"], bsdf.inputs["Emission Color"])
bsdf.inputs["Emission Strength"].default_value = 1.2
nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
bsdf.inputs["Roughness"].default_value = 0.75
bsdf.inputs["Specular IOR Level"].default_value = 0.12
ob.material_slots[0].material = mat
if old and old.users == 0:
    bpy.data.materials.remove(old)
for img in list(bpy.data.images):
    if img.name == "Hellhound_Atlas" and img.users == 0:
        bpy.data.images.remove(img)

tris = sum(len(p.vertices) - 2 for p in me.polygons)
print("RETEX faces", len(me.polygons), "tris", tris, "cells", dict(sorted(counts.items())))
out = os.path.join(ROOT, "LavaHellhound.blend")
bpy.ops.wm.save_as_mainfile(filepath=out, relative_remap=True)
print("saved", out)
