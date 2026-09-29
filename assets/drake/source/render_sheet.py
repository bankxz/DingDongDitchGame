"""Render Drake.blend in the reference-sheet views + a side-by-side vs the reference.

python3 render_sheet.py [reference] [out_dir] [action] [frame]
Default action is RefPose (the sheet's pose). Env: SAMPLES, ONLY=front,left,...
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
REF = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "previews")
ACTION = sys.argv[3] if len(sys.argv) > 3 else "RefPose"
FRAME = int(sys.argv[4]) if len(sys.argv) > 4 else 1
os.makedirs(OUT, exist_ok=True)

# reference sheet crops (x0, y0, x1, y1) on the 1448x1086 sheet
CROPS = {"front": (10, 0, 400, 390), "back": (420, 0, 740, 390), "three_quarter": (740, 0, 1448, 395),
         "left": (0, 412, 740, 605), "right": (740, 412, 1448, 605), "top": (40, 628, 1420, 772)}

bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "Drake.blend"))
sc = bpy.context.scene
rig = bpy.data.objects["DrakeRig"]
rig.animation_data.action = bpy.data.actions[ACTION] if ACTION != "rest" else None
if ACTION == "rest":
    for pb in rig.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
sc.frame_set(FRAME)

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = int(os.environ.get("SAMPLES", "24"))
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("W")
world.use_nodes = True
# dark backdrop for camera rays, soft bright ambient for lighting
wn = world.node_tree
bg_cam = wn.nodes["Background"]
bg_cam.inputs[0].default_value = (0.022, 0.025, 0.036, 1)
bg_amb = wn.nodes.new("ShaderNodeBackground")
bg_amb.inputs[0].default_value = (0.8, 0.85, 1.0, 1)
bg_amb.inputs[1].default_value = 0.9
lp = wn.nodes.new("ShaderNodeLightPath")
mix = wn.nodes.new("ShaderNodeMixShader")
wn.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
wn.links.new(bg_amb.outputs[0], mix.inputs[1])
wn.links.new(bg_cam.outputs[0], mix.inputs[2])
wn.links.new(mix.outputs[0], wn.nodes["World Output"].inputs[0])
for m in bpy.data.materials:
    if m.use_nodes and "Principled BSDF" in m.node_tree.nodes:
        m.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.12
sc.world = world


def area(name, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.size, ld.color = energy, size, color
    lo = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(lo)
    return lo


key = area("Key", 3600, 14)
fill = area("Fill", 900, 16, (0.85, 0.9, 1.0))
rim = area("Rim", 1500, 12, (0.8, 0.9, 1.0))
cam_d = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam

# name: (azimuth (0 = camera at -Y/front), elevation, distance, target, ortho_scale or lens, res)
VIEWS = {
    "front": (0, 6, 17, (0, 1.0, 2.6), ("P", 50), (390, 390)),
    "back": (180, 8, 24, (0, 4, 2.8), ("P", 50), (320, 390)),
    "three_quarter": (62, 10, 36, (0, 8.5, 2.6), ("P", 45), (708, 395)),
    "left": (90, 2, 60, (0, 11.0, 2.8), ("O", 33), (740, 193)),
    "right": (-90, 2, 60, (0, 11.0, 2.8), ("O", 33), (708, 193)),
    "top": (90, 89.5, 60, (0, 11.0, 1.0), ("O", 33), (1380, 144)),
}


def place(o, az, el, dist, tgt):
    a, e = math.radians(az), math.radians(el)
    o.location = tgt + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    o.rotation_euler = (tgt - o.location).to_track_quat("-Z", "Y").to_euler()


if os.environ.get("NEON"):   # preview of Roblox Neon on the Drake_Spikes MeshPart
    sp = bpy.data.materials["Drake_Spikes"]
    sp.node_tree.nodes.clear()
    em = sp.node_tree.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0.02, 0.6, 0.95, 1)
    em.inputs["Strength"].default_value = 3.0
    out = sp.node_tree.nodes.new("ShaderNodeOutputMaterial")
    sp.node_tree.links.new(em.outputs[0], out.inputs[0])
ONLY = os.environ.get("ONLY")
paths = {}
for name, (az, el, dist, tgt, lensinfo, res) in VIEWS.items():
    if ONLY and name not in ONLY.split(","):
        continue
    tgt = Vector(tgt)
    kind, val = lensinfo
    cam_d.type = "ORTHO" if kind == "O" else "PERSP"
    if kind == "O":
        cam_d.ortho_scale = val
    else:
        cam_d.lens = val
    cam_d.clip_end = 500
    sc.render.resolution_x, sc.render.resolution_y = res
    place(cam, az, el, dist, tgt)
    place(key, az - 40, 50, 30, tgt)
    place(fill, az + 70, 15, 30, tgt)
    place(rim, az + 170, 40, 30, tgt)
    sc.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    paths[name] = sc.render.filepath
    print("RENDERED", name)
if ONLY:
    raise SystemExit(0)

from PIL import Image, ImageDraw  # noqa: E402

W = 1448
sheet = Image.new("RGB", (1448, 800), (40, 43, 55))
layout = {"front": (10, 0), "back": (420, 0), "three_quarter": (740, 0), "left": (0, 412), "right": (740, 412), "top": (40, 628)}
for n, (x, y) in layout.items():
    sheet.paste(Image.open(paths[n]).convert("RGB"), (x, y))
    ImageDraw.Draw(sheet).text((x + 10, y + 6), n.upper().replace("_", " "), fill=(220, 220, 230))
sheet.save(os.path.join(OUT, "sheet.png"))
if REF:
    ref = Image.open(REF).convert("RGB").crop((0, 0, 1448, 800))
    Image.fromarray(__import__("numpy").concatenate([__import__("numpy").asarray(ref), __import__("numpy").asarray(sheet)], 0)).save(os.path.join(OUT, "compare.png"))
print("SHEET", os.path.join(OUT, "sheet.png"))
