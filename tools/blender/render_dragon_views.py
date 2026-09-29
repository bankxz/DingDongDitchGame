"""Render AncientDragon.blend from cameras matched to the reference sheet's panels.

python3 tools/blender/render_dragon_views.py <out_dir> [--action NAME] [--frame N] [--mask] [views...]
--mask renders alpha silhouettes (for IoU against the reference masks).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BLEND = os.path.join(ROOT, "assets", "models", "AncientDragon", "AncientDragon.blend")
args = sys.argv[1:]
out = args.pop(0) if args else "/tmp/dragon_views"
action, frame, mask, night = "", 1, False, False
views = []
while args:
    a = args.pop(0)
    if a == "--action":
        action = args.pop(0)
    elif a == "--frame":
        frame = int(args.pop(0))
    elif a == "--mask":
        mask = True
    elif a == "--night":
        night = True
    else:
        views.append(a)
os.makedirs(out, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
arm = bpy.data.objects.get("AncientDragon")
if arm and action:
    arm.animation_data.action = bpy.data.actions[action]
    try:
        arm.animation_data.action_slot = arm.animation_data.action_suggested_slots[0]
    except Exception:
        pass
sc.frame_set(frame)

w = bpy.data.worlds.new("SKY")
sc.world = w
w.use_nodes = True
nt = w.node_tree
bg = nt.nodes["Background"]
coord = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ")
ramp = nt.nodes.new("ShaderNodeValToRGB")
nt.links.new(coord.outputs["Window"], sep.inputs[0])
nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
ramp.color_ramp.elements[0].color = (0.62, 0.8, 0.97, 1)
ramp.color_ramp.elements[1].color = (0.12, 0.45, 0.9, 1)
nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
bg.inputs["Strength"].default_value = 1.4

bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 0, 0))
ground = bpy.context.active_object
gm = bpy.data.materials.new("GROUND")
gm.use_nodes = True
gb = gm.node_tree.nodes["Principled BSDF"]
gb.inputs["Base Color"].default_value = (0.035, 0.045, 0.085, 1)
gb.inputs["Roughness"].default_value = 0.35
ground.data.materials.append(gm)

sun = bpy.data.lights.new("sun", "SUN")
sun.energy = 4.5
sun.color = (1.0, 0.93, 0.82)
sun.angle = math.radians(10)
so = bpy.data.objects.new("sun", sun)
sc.collection.objects.link(so)
so.rotation_euler = (math.radians(45), math.radians(-15), math.radians(-40))
fill = bpy.data.lights.new("fill", "SUN")
fill.energy = 0.8
fo = bpy.data.objects.new("fill", fill)
sc.collection.objects.link(fo)
fo.rotation_euler = (math.radians(60), 0, math.radians(150))

if night:  # dusk lighting to show the emissive wings / runes / eyes
    bg.inputs["Strength"].default_value = 0.12
    sun.energy = 0.5
    fill.energy = 0.15
sc.render.engine = "CYCLES"
sc.cycles.samples = 4 if mask else 28
sc.cycles.use_denoising = not mask
sc.cycles.device = "CPU"
sc.render.resolution_x = 960
sc.render.resolution_y = 640
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
if mask:
    sc.render.film_transparent = True
    ground.hide_render = True

cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam

# name: (location, target, lens, resolution)  - matched to the reference panels
VIEWS = {
    "hero": ((11.0, -9.5, 3.4), (0.0, 3.8, 5.4), 22, (720, 488)),
    "front": ((0, -58, 3.2), (0, 2, 5.4), 80, (646, 406)),
    "back": ((0, 62, 5.5), (0, 2, 5.0), 72, (794, 406)),
    "left": ((60, 5.0, 3.0), (0, 5.0, 5.2), 82, (646, 280)),
    "right": ((-60, 5.0, 3.0), (0, 5.0, 5.2), 82, (794, 280)),
    "top": ((0, -30, 21), (0, 4.5, 5), 25, (646, 208)),
    "topdown": ((0, 4.0, 45), (0, 4.0, 0), 30, (600, 600)),
    "bottom": ((0, -24, -13), (0, 4.5, 4.5), 25, (794, 208)),
    "head_front": ((0, -17, 8.8), (0, -4.5, 8.6), 55, (400, 400)),
    "head_34": ((7, -12.5, 9.4), (0, -4.6, 8.4), 50, (400, 400)),
    "head_side": ((14, -4.5, 8.8), (0, -4.2, 8.6), 50, (400, 400)),
    "head_top": ((0, -4.0, 20), (0, -4.0, 8.0), 60, (400, 400)),
    "tail": ((10, 12, 4), (0, 12, 1.8), 45, (700, 300)),
    "claw": ((5, -9, 2.0), (2.6, -2.5, 0.6), 50, (500, 380)),
    "eye": ((5.5, -9.0, 8.6), (0.9, -5.3, 8.2), 60, (500, 380)),
    "mouth": ((3.2, -10.5, 6.6), (0.0, -5.6, 7.0), 45, (500, 380)),
    "mouth_front": ((0.0, -12.0, 6.9), (0.0, -5.8, 7.3), 50, (500, 380)),
    "arm": ((12, -3, 3.2), (2.6, -0.3, 2.4), 35, (500, 380)),
    "feet_under": ((1.5, -6.0, -6.0), (2.3, 1.5, 0.3), 32, (600, 420)),
    "spine": ((9, 16, 13), (0, 5, 4.5), 30, (600, 380)),
}
# The reference TOP/BOTTOM panels show the wings spread flat (flight pose) while FRONT/BACK/SIDE show them
# raised, so those two panels are rendered with the rig posing the wings flat (same mesh, rig-driven pose).
SPREAD_VIEWS = ("top", "bottom", "topdown")
OPEN_MOUTH_VIEWS = ("hero", "left", "right", "head_34", "head_side", "mouth")


def set_wing_spread(on):
    from mathutils import Matrix
    if not arm:
        return
    for sfx, s in (("_L", 1), ("_R", -1)):
        pb = arm.pose.bones["Wing1" + sfx]
        if on:
            h = pb.bone.head_local
            R = (Matrix.Rotation(math.radians(20 * s), 4, "Z") @ Matrix.Rotation(math.radians(50 * s), 4, "Y")
                 @ Matrix.Rotation(math.radians(70), 4, "X"))
            pb.matrix = Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ pb.bone.matrix_local
        else:
            pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


for name, (loc, tgt, lens, res) in VIEWS.items():
    if views and name not in views:
        continue
    set_wing_spread(name in SPREAD_VIEWS and not action)
    if arm and not action:
        # reference hero / side / 3-4 head panels show the mouth open: pose the jaw open (rig pose, not a remodel)
        from mathutils import Matrix
        pb = arm.pose.bones["Jaw"]
        if name in OPEN_MOUTH_VIEWS:
            h = pb.bone.head_local
            pb.matrix = (Matrix.Translation(h) @ Matrix.Rotation(math.radians(22), 4, "X") @ Matrix.Translation(-h)
                         @ pb.bone.matrix_local)
        else:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
    sc.render.resolution_x, sc.render.resolution_y = res
    cam.location = Vector(loc)
    d = Vector(tgt) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam_d.lens = lens
    if name in ("bottom", "feet_under"):
        ground.hide_render = True
    elif not mask:
        ground.hide_render = False
    sc.render.filepath = os.path.join(out, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name)
