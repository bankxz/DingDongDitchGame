"""Render validation views of a Hellhound .blend or .fbx. usage: python3 render_hh.py INPUT OUTDIR [views] [action] [frames]"""
import math, os, sys
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
INP, OUT = sys.argv[1], sys.argv[2]
VIEWS = sys.argv[3].split(",") if len(sys.argv) > 3 and sys.argv[3] else None
ACTION = sys.argv[4] if len(sys.argv) > 4 else ""
FRAMES = [int(f) for f in sys.argv[5].split(",")] if len(sys.argv) > 5 else [1]
os.makedirs(OUT, exist_ok=True)
if INP.endswith(".blend"):
    bpy.ops.wm.open_mainfile(filepath=INP)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=INP)
sc = bpy.context.scene
mesh = [o for o in bpy.data.objects if o.type == "MESH"][0]
arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
if ACTION:
    arm.animation_data_create()
    act = bpy.data.actions[ACTION]
    arm.animation_data.action = act
    if hasattr(arm.animation_data, "action_slot") and act.slots:
        arm.animation_data.action_slot = act.slots[0]
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.018, 0.018, 0.021, 1)
bpy.ops.mesh.primitive_plane_add(size=400)
floor = bpy.context.active_object
fm = bpy.data.materials.new("floor"); fm.use_nodes = True
fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.03, 0.03, 0.035, 1)
floor.data.materials.append(fm)
ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
pts = [ev.matrix_world @ v.co for v in list(ev.data.vertices)[::4]]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
floor.location.z = lo.z
ctr = (lo + hi) / 2; size = (hi - lo).length
def light(name, d, energy, s):
    ld = bpy.data.lights.new(name, "AREA"); ld.energy, ld.size = energy * size * size / 40, s * size / 6
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o)
    o.location = ctr + Vector(d).normalized() * size * 1.3
    o.rotation_euler = (ctr - o.location).to_track_quat("-Z", "Y").to_euler()
light("key", (0.5, -0.8, 1.0), 800, 5); light("fill", (-1, -0.3, 0.4), 250, 6); light("rim", (0, 1, 0.8), 500, 5)
sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"
sc.cycles.samples = int(os.environ.get("SAMPLES", "32")); sc.cycles.use_denoising = True
sc.view_settings.view_transform = "Standard"
try:
    ng = bpy.data.node_groups.new("Comp", "CompositorNodeTree"); sc.compositing_node_group = ng
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers"); gl = ng.nodes.new("CompositorNodeGlare"); out = ng.nodes.new("NodeGroupOutput")
    for inp in gl.inputs:
        if inp.name == "Type": inp.default_value = "Bloom"
        elif inp.name == "Threshold": inp.default_value = 0.6
        elif inp.name == "Strength": inp.default_value = 0.9
        elif inp.name == "Size": inp.default_value = 0.7
    ng.links.new(rl.outputs["Image"], gl.inputs["Image"]); ng.links.new(gl.outputs["Image"], out.inputs[0])
except Exception as e:
    print("glare skipped", e)
cam_d = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.lens = 45; cam_d.clip_end = 10000
views = {"persp": (0.62, -0.62, 0.45), "front": (0, -1, 0.15), "left": (-1, 0, 0.12), "right": (1, 0, 0.12),
         "back": (0, 1, 0.3), "top": (0, 0.001, 1)}
sc.render.resolution_x, sc.render.resolution_y = 640, 520
def fit(dirv):
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    pts = [ev.matrix_world @ v.co for v in list(ev.data.vertices)[::4]]
    lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
    c = (lo + hi) / 2; dist = (hi - lo).length * 2
    cam.rotation_euler = (-dirv).to_track_quat("-Z", "Y").to_euler()
    for _ in range(4):
        cam.location = c + dirv * dist; bpy.context.view_layer.update()
        pp = [world_to_camera_view(sc, cam, p) for p in pts]
        ext = max(max(q.x for q in pp) - min(q.x for q in pp), max(q.y for q in pp) - min(q.y for q in pp))
        dist *= ext / 0.9
    cam.location = c + dirv * dist
for f in FRAMES:
    sc.frame_set(f)
    for name, d in views.items():
        if VIEWS and name not in VIEWS: continue
        fit(Vector(d).normalized())
        sc.render.filepath = os.path.join(OUT, f"{name}{'_' + ACTION + '_' + str(f) if ACTION else ''}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", sc.render.filepath)
