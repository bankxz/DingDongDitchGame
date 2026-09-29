"""Animation QA contact sheet: renders N frames of every action (3/4 + top views).

    python anim_sheet.py <blend> <out_dir>
"""
import math
import os
import sys

import bpy
from mathutils import Vector

blend, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
arm = bpy.data.objects["SkeletalSharkRig"]
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 8
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = 420, 260
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.35, 0.37, 0.42, 1)
sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
sun.data.energy = 3.5
sun.rotation_euler = (math.radians(40), 0, math.radians(30))
scene.collection.objects.link(sun)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.collection.objects.link(cam)
scene.camera = cam
CENTER = Vector((0, 0, 1.8))
VIEWS = {"q": Vector((0.8, -0.7, 0.45)), "top": Vector((0.001, 0, 1))}

from PIL import Image  # noqa: E402

rows = []
for act in bpy.data.actions:
    arm.animation_data.action = act
    f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
    n = 8
    frames = [round(f0 + (f1 - f0) * k / n) for k in range(n)]
    for vname, d in VIEWS.items():
        tiles = []
        for f in frames:
            scene.frame_set(f)
            cam.location = CENTER + d.normalized() * 22
            cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
            cam.data.lens = 40
            p = os.path.join(out, f"{act.name}_{vname}_{f:03d}.png")
            scene.render.filepath = p
            bpy.ops.render.render(write_still=True)
            tiles.append(Image.open(p).convert("RGB"))
        row = Image.new("RGB", (420 * n, 260 + 24), (20, 20, 26))
        for k, t in enumerate(tiles):
            row.paste(t, (420 * k, 24))
        from PIL import ImageDraw
        ImageDraw.Draw(row).text((6, 5), f"{act.name}  view={vname}  frames={frames}", fill=(255, 255, 255))
        rows.append(row)
sheet = Image.new("RGB", (rows[0].width, sum(r.height for r in rows)))
y = 0
for r in rows:
    sheet.paste(r, (0, y))
    y += r.height
sheet.save(os.path.join(out, "animation_contact_sheet.png"))
print("SHEET_DONE")
