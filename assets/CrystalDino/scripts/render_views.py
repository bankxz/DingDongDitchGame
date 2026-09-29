"""Render validation views of CrystalDino.blend and build reference comparison sheets.

python3 render_views.py OUTDIR [REF_DIR] [action frame ...]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "previews")
REF = sys.argv[2] if len(sys.argv) > 2 else None
VIEWS = os.environ.get("VIEWS", "hero,left,right,front,back,top,fronthead,sidehead").split(",")
ACTION = os.environ.get("ACTION", "")
FRAMES = [int(f) for f in os.environ.get("FRAMES", "1").split(",")]
RES = int(os.environ.get("RES", "640"))
SAMPLES = int(os.environ.get("SAMPLES", "24"))
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "CrystalDino.blend"))
scene = bpy.context.scene
arm = bpy.data.objects["CrystalDino_Rig"]
if ACTION:
    arm.animation_data.action = bpy.data.actions[ACTION]
else:
    arm.animation_data.action = None
    for b in arm.pose.bones:
        b.location = (0, 0, 0)
        b.rotation_quaternion = (1, 0, 0, 0)
arm.hide_render = True

# world: blue sky like the reference sheet
world = bpy.data.worlds.new("Sky")
scene.world = world
world.use_nodes = True
nt = world.node_tree
bg = nt.nodes["Background"]
sky = nt.nodes.new("ShaderNodeTexSky")
sky.sky_type = "HOSEK_WILKIE"
sky.sun_direction = Vector((0.3, -0.5, 0.8)).normalized()
sky.turbidity = 2.5
nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.0

# ground: grey-blue grid floor
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
g = bpy.context.active_object
gm = bpy.data.materials.new("Ground")
gm.use_nodes = True
gnt = gm.node_tree
gb = gnt.nodes["Principled BSDF"]
bt = gnt.nodes.new("ShaderNodeTexBrick")
bt.inputs["Scale"].default_value = 0.25
bt.inputs["Mortar Size"].default_value = 0.01
bt.offset = 0.0
bt.inputs["Color1"].default_value = (0.09, 0.1, 0.15, 1)
bt.inputs["Color2"].default_value = (0.1, 0.105, 0.155, 1)
bt.inputs["Mortar"].default_value = (0.06, 0.065, 0.1, 1)
gnt.links.new(bt.outputs["Color"], gb.inputs["Base Color"])
gb.inputs["Roughness"].default_value = 0.6
g.data.materials.append(gm)

sun = bpy.data.lights.new("Sun", "SUN")
sun.energy = 4.5
sun.angle = math.radians(8)
so = bpy.data.objects.new("Sun", sun)
scene.collection.objects.link(so)
so.rotation_euler = (math.radians(45), 0, math.radians(35))
fill = bpy.data.lights.new("Fill", "SUN")
fill.energy = 0.9
fo = bpy.data.objects.new("Fill", fill)
scene.collection.objects.link(fo)
fo.rotation_euler = (math.radians(60), 0, math.radians(150))

scene.render.engine = "CYCLES"
scene.cycles.samples = SAMPLES
scene.cycles.use_denoising = True
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"

cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

CENTER = Vector((0, 0.5, 5.5))
VIEWDEF = {  # name: (location, target, lens, aspect)
    "hero": (Vector((33, -13, 6.0)), Vector((0, 3.5, 6.0)), 23, (2.1, 1)),
    "left": (Vector((40, -6, 8)), Vector((0, 2.0, 6)), 40, (1.51, 1)),
    "right": (Vector((-40, -6, 8)), Vector((0, 2.0, 6)), 40, (1.51, 1)),
    "front": (Vector((0, -30, 7.5)), Vector((0, 0, 6.3)), 38, (0.86, 1)),
    "back": (Vector((0, 42, 12)), Vector((0, 0, 6.3)), 40, (0.81, 1)),
    "top": (Vector((0, 0.5, 60)), Vector((0, 0.5, 0)), 45, (0.61, 1)),
    "fronthead": (Vector((0, -30, 10.5)), Vector((0, -10, 9.6)), 62, (0.65, 1)),
    "mouthclose": (Vector((6.5, -21.0, 9.5)), Vector((0.0, -11.5, 8.6)), 55, (1.0, 1)),
    "browside": (Vector((14.0, -11.0, 12.5)), Vector((0.0, -10.5, 11.5)), 60, (1.0, 1)),
    "eyegraze": (Vector((3.2, -20.0, 11.2)), Vector((2.0, -10.2, 10.95)), 70, (1.0, 1)),
    "eyeclose": (Vector((8.5, -16.0, 12.2)), Vector((2.0, -10.2, 10.95)), 70, (1.0, 1)),
    "sidehead": (Vector((-17, -16, 11)), Vector((0, -10, 9.8)), 55, (0.7, 1)),
}


def look(obj, target):
    d = target - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


for frame in FRAMES:
    scene.frame_set(frame)
    for v in VIEWS:
        loc, tgt, lens, asp = VIEWDEF[v]
        cam.location = loc
        look(cam, tgt)
        cam_data.lens = lens
        if v == "top":
            cam.rotation_euler = (0, 0, 0)
        a = asp[0] / asp[1]
        if a >= 1:
            scene.render.resolution_x, scene.render.resolution_y = RES, int(RES / a)
        else:
            scene.render.resolution_x, scene.render.resolution_y = int(RES * a), RES
        tag = ("%s_%s_f%03d" % (ACTION, v, frame)) if ACTION else v
        scene.render.filepath = os.path.join(OUT, tag + ".png")
        bpy.ops.render.render(write_still=True)
        print("rendered", tag)

if REF:
    from PIL import Image
    for v in VIEWS:
        rp = os.path.join(REF, v + ".png")
        mp = os.path.join(OUT, v + ".png")
        if not (os.path.exists(rp) and os.path.exists(mp)):
            continue
        a, b = Image.open(rp).convert("RGB"), Image.open(mp).convert("RGB")
        h = 480
        a = a.resize((int(a.width * h / a.height), h))
        b = b.resize((int(b.width * h / b.height), h))
        c = Image.new("RGB", (a.width + b.width + 8, h), (255, 255, 255))
        c.paste(a, (0, 0))
        c.paste(b, (a.width + 8, 0))
        c.save(os.path.join(OUT, "cmp_" + v + ".png"))
