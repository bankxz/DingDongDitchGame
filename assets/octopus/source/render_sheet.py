"""Render the six reference-sheet views of Octopus.blend and a side-by-side vs the reference.

python3 render_sheet.py [reference.png] [out_dir] [action] [frame]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
REF = sys.argv[1] if len(sys.argv) > 1 else None
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "previews")
ACTION = sys.argv[3] if len(sys.argv) > 3 else None
FRAME = int(sys.argv[4]) if len(sys.argv) > 4 else 1
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "Octopus.blend"))
sc = bpy.context.scene
rig = bpy.data.objects["OctopusRig"]
if ACTION:
    rig.animation_data.action = bpy.data.actions[ACTION]
    sc.frame_set(FRAME)
else:
    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = int(os.environ.get("SAMPLES", "24"))
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.render.resolution_x, sc.render.resolution_y = 520, 420

world = bpy.data.worlds.new("W")
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.028, 0.030, 0.040, 1)
bg.inputs[1].default_value = 1.0
sc.world = world


def area(name, loc, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    ld.color = color
    lo = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(lo)
    lo.location = loc
    d = Vector((0, 0, 3)) - Vector(loc)
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return lo


# studio rig that rotates with the camera (key upper-left, fill right, rim behind)
key = area("Key", (0, 0, 0), 2000, 9)
fill = area("Fill", (0, 0, 0), 380, 10, (0.85, 0.85, 1.0))
rim = area("Rim", (0, 0, 0), 2000, 8, (0.8, 0.7, 1.0))
top = area("Top", (0, 0, 16), 350, 12)

cam_d = bpy.data.cameras.new("Cam")
cam_d.lens = 50
cam = bpy.data.objects.new("Cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam

TARGET = Vector((0, 0.4, 3.4))
VIEWS = {  # name: (azimuth deg (0 = front, camera at -Y), elevation deg, distance)
    "front": (0, 8, 19),
    "back": (180, 8, 19),
    "three_quarter": (38, 14, 19),
    "left": (-90, 6, 19),
    "top": (0, 88, 21),
    "right": (90, 6, 19),
}


def place(obj, az, el, dist, tgt):
    a, e = math.radians(az), math.radians(el)
    obj.location = tgt + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
    obj.rotation_euler = (tgt - obj.location).to_track_quat("-Z", "Y").to_euler()


paths = {}
ONLY = os.environ.get("ONLY")
for name, (az, el, dist) in VIEWS.items():
    if ONLY and name not in ONLY.split(","):
        continue
    tgt = TARGET if name != "top" else Vector((0, 0.4, 2.5))
    place(cam, az, el, dist, tgt)
    place(key, az - 45, 45, 14, tgt)
    place(fill, az + 60, 15, 14, tgt)
    place(rim, az + 170, 35, 14, tgt)
    sc.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    paths[name] = sc.render.filepath
    print("RENDERED", name)

if ONLY:
    raise SystemExit(0)
# contact sheet in the reference layout (+ reference crops side by side)
from PIL import Image, ImageDraw  # noqa: E402

order = ["front", "back", "three_quarter", "left", "top", "right"]
W, H = 520, 420
sheet = Image.new("RGB", (W * 3, H * 2), (46, 48, 57))
for i, n in enumerate(order):
    im = Image.open(paths[n]).convert("RGB")
    sheet.paste(im, ((i % 3) * W, (i // 3) * H))
    ImageDraw.Draw(sheet).text(((i % 3) * W + 12, (i // 3) * H + 10), n.upper().replace("_", " "), fill=(220, 220, 230))
sheet.save(os.path.join(OUT, "sheet.png"))
if REF:
    ref = Image.open(REF).convert("RGB")
    crops = {"front": (10, 0, 490, 390), "back": (495, 0, 960, 390), "three_quarter": (950, 0, 1448, 400),
             "left": (10, 440, 490, 780), "top": (500, 440, 960, 780), "right": (950, 440, 1448, 780)}
    cmp_ = Image.new("RGB", (W * 2, H * 6), (46, 48, 57))
    for i, n in enumerate(order):
        c = ref.crop(crops[n])
        c.thumbnail((W, H))
        cmp_.paste(c, (0, i * H))
        cmp_.paste(Image.open(paths[n]).convert("RGB"), (W, i * H))
    cmp_.save(os.path.join(OUT, "compare.png"))
print("SHEET", os.path.join(OUT, "sheet.png"))
