"""Render the reference-matching views of LavaScorpion.blend for validation.
usage: python3 render_views.py OUTDIR [action] [frame]"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "validation")
ACTION = sys.argv[2] if len(sys.argv) > 2 else ""
FRAMES = [int(f) for f in sys.argv[3].split(",")] if len(sys.argv) > 3 else [1]
VIEWS = sys.argv[4].split(",") if len(sys.argv) > 4 else None
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "..", "LavaScorpion.blend"))
sc = bpy.context.scene
arm = bpy.data.objects["LavaScorpion"]
if ACTION:
    arm.animation_data_create()
    arm.animation_data.action = bpy.data.actions[ACTION]
    if hasattr(arm.animation_data, "action_slot") and arm.animation_data.action.slots:
        arm.animation_data.action_slot = arm.animation_data.action.slots[0]

# world / floor / lights -- dark studio like the reference sheet
w = bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.018, 0.018, 0.021, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
floor = bpy.context.active_object
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
fm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.45
floor.data.materials.append(fm)


def light(name, loc, energy, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.size, ld.color = energy, size, color
    o = bpy.data.objects.new(name, ld)
    sc.collection.objects.link(o)
    o.location = loc
    d = Vector((0, 0, 0.8)) - Vector(loc)
    o.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


light("key", (3, -5, 7), 800, 5, (1, 0.93, 0.88))
light("fill", (-6, -2, 3), 250, 6, (0.8, 0.85, 1.0))
light("rim", (0, 7, 6), 500, 5)

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = int(os.environ.get("SAMPLES", "40"))
sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"

cam_d = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_d)
sc.collection.objects.link(cam)
sc.camera = cam
from bpy_extras.object_utils import world_to_camera_view

# glare / bloom (the reference sheet renders glow with bloom; Roblox: Lighting.Bloom)
try:
    try:
        sc.use_nodes = True
    except Exception:
        pass
    ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree")
    sc.compositing_node_group = ng
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    gl = ng.nodes.new("CompositorNodeGlare")
    out = ng.nodes.new("NodeGroupOutput")
    for inp in gl.inputs:
        if inp.name == "Type":
            inp.default_value = "Bloom"
        elif inp.name == "Threshold":
            inp.default_value = 0.6
        elif inp.name == "Strength":
            inp.default_value = 0.9
        elif inp.name == "Size":
            inp.default_value = 0.7
        elif inp.name == "Quality":
            inp.default_value = "High"
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"])
    ng.links.new(gl.outputs["Image"], out.inputs[0])
    print("GLARE inputs", [(i.name, getattr(i, "default_value", None)) for i in gl.inputs])
except Exception as e:  # compositor API differs between versions; bloom is optional
    print("glare skipped", e)

mesh = bpy.data.objects["GEO-LavaScorpion"]
deps = bpy.context.evaluated_depsgraph_get()
target = Vector((0, -0.2, 1.1))
# (direction from target to camera, resolution, lens, fill fraction) matched to each reference panel
views = {
    "persp": ((0.62, -0.62, 0.48), (560, 440), 45, 0.93),
    "front": ((0, -1, 0.2), (400, 440), 45, 0.97),
    "back": ((0, 1, 0.32), (488, 440), 45, 0.9),
    "left": ((-1, 0.0, 0.16), (480, 300), 45, 0.9),   # reference "LEFT SIDE": head on the right of the image
    "right": ((1, 0.0, 0.16), (468, 300), 45, 0.9),
    "top": ((0, 0, 1), (500, 300), 45, 0.9),
}


def fit(dirv, fill):
    """move the camera along dirv until the evaluated mesh fills `fill` of the frame."""
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    pts = [ev.matrix_world @ v.co for v in list(ev.data.vertices)[::3]]
    ctr = sum(pts, Vector()) / len(pts)
    ctr = Vector(((max(p.x for p in pts) + min(p.x for p in pts)) / 2, (max(p.y for p in pts) + min(p.y for p in pts)) / 2,
                  (max(p.z for p in pts) + min(p.z for p in pts)) / 2))
    dist = 12.0
    for _ in range(4):
        cam.location = ctr + dirv * dist
        bpy.context.view_layer.update()
        pp = [world_to_camera_view(sc, cam, p) for p in pts]
        ext = max(max(q.x for q in pp) - min(q.x for q in pp), max(q.y for q in pp) - min(q.y for q in pp))
        dist *= ext / fill
    cam.location = ctr + dirv * dist
    bpy.context.view_layer.update()
    pp = [world_to_camera_view(sc, cam, p) for p in pts]
    # recentre the projected bbox via lens shift
    cam_d.shift_x = 0
    cam_d.shift_y = 0
    bpy.context.view_layer.update()
    pp = [world_to_camera_view(sc, cam, p) for p in pts]
    cx = (max(q.x for q in pp) + min(q.x for q in pp)) / 2 - 0.5
    cy = (max(q.y for q in pp) + min(q.y for q in pp)) / 2 - 0.5
    ar = sc.render.resolution_x / sc.render.resolution_y
    cam_d.shift_x = cx * (1 if ar >= 1 else ar)
    cam_d.shift_y = cy * (1 / ar if ar >= 1 else 1)


for f in FRAMES:
    sc.frame_set(f)
    for name, (dv, res, lens, fill) in views.items():
        if VIEWS and name not in VIEWS:
            continue
        sc.render.resolution_x, sc.render.resolution_y = res
        cam_d.lens = lens
        dirv = Vector(dv).normalized()
        if name == "top":
            cam.rotation_euler = (0, 0, math.radians(90))  # head (-Y) to the image left
        else:
            cam.rotation_euler = dirv.to_track_quat("Z", "Y").to_euler()
        fit(dirv, fill)
        sc.render.filepath = os.path.join(OUT, f"{name}{'_' + ACTION + '_' + str(f) if ACTION else ''}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", sc.render.filepath)
