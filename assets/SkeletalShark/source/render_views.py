"""Render the reference-sheet views of SkeletalShark.blend (beauty + flat silhouettes).

    python render_views.py <blend> <out_dir> [pose_action frame]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

blend, out = sys.argv[1], sys.argv[2]
action_name = sys.argv[3] if len(sys.argv) > 3 else None
frame = int(sys.argv[4]) if len(sys.argv) > 4 else 1
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
scene = bpy.context.scene
arm = bpy.data.objects["SkeletalSharkRig"]
if action_name:
    arm.animation_data.action = bpy.data.actions[action_name]
    scene.frame_set(frame)

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = int(os.environ.get("SAMPLES", 48))
scene.cycles.use_denoising = True
scene.render.resolution_x = 1000
scene.render.resolution_y = 600
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "Medium High Contrast"

world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.012, 0.014, 0.022, 1)
bg.inputs["Strength"].default_value = 1.0

# floor to catch the soft shadow like the reference sheet
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, -0.02))
floor = bpy.context.active_object
fm = bpy.data.materials.new("Floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.014, 0.016, 0.024, 1)
fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
floor.data.materials.append(fm)


def light(name, kind, loc, energy, size, color=(1, 1, 1), target=(0, 0, 1.6)):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.size = size
    else:
        ld.angle = math.radians(size)
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    lo.location = loc
    d = Vector(target) - Vector(loc)
    lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return lo


light("Key", "SUN", (8, -10, 12), 3.6, 8, (1.0, 0.95, 0.88))
light("Fill", "AREA", (-12, -6, 6), 1400, 10, (0.75, 0.82, 1.0))
light("Rim", "AREA", (4, 14, 8), 700, 8, (0.7, 0.8, 1.0))
light("Top", "AREA", (0, 0, 14), 500, 14)

CENTER = Vector((0, 0, 1.75))
VIEWS = {
    # name: (direction from centre, ortho?, scale/lens, up_roll)
    "left": (Vector((1, 0, 0.0)), True, 15.6),
    "right": (Vector((-1, 0, 0.0)), True, 15.6),
    # the sheet's front/back views are perspective shots from slightly above
    "front": (Vector((0, -1, 0.30)), False, 40),
    "back": (Vector((0, 1, 0.45)), False, 40),
    "top": (Vector((0, 0, 1)), True, 15.6),
    "three_quarter": (Vector((0.75, -0.75, 0.32)), False, 50),
}
cam_data = bpy.data.cameras.new("Cam")
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def place(view):
    d, ortho, s = VIEWS[view]
    d = d.normalized()
    cam.location = CENTER + d * 40
    if view == "top":
        cam.rotation_euler = (0, 0, math.radians(90))
    else:
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam_data.type = "ORTHO" if ortho else "PERSP"
    cam_data.clip_end = 200
    if ortho:
        cam_data.ortho_scale = s
    else:
        cam.location = CENTER + d * (26 if view == "three_quarter" else 20)
        cam_data.lens = s


only = os.environ.get("VIEWS")
views = only.split(",") if only else list(VIEWS)
for v in views:
    place(v)
    scene.render.filepath = os.path.join(out, f"{v}.png")
    bpy.ops.render.render(write_still=True)

# flat silhouettes / label masks for the fit loop
if os.environ.get("SIL", "1") == "1":
    floor.hide_render = True
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = True
    bg.inputs["Color"].default_value = (0, 0, 0, 1)
    scene.cycles.samples = 4
    scene.cycles.use_denoising = False
    scene.view_settings.look = "None"
    mat = bpy.data.materials["M_SkeletalShark"]
    nt = mat.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    tex = [n for n in nt.nodes if n.type == "TEX_IMAGE" and "Color" in n.image.name][0]
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs[0], nt.nodes["Material Output"].inputs["Surface"])
    for v in ("left", "front", "top", "back"):
        place(v)
        scene.render.filepath = os.path.join(out, f"flat_{v}.png")
        bpy.ops.render.render(write_still=True)
print("RENDER_DONE")
