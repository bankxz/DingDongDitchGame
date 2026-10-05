"""Auto-framed Cycles validation renders.  python3 render_views.py model.blend out_dir
Env: VIEWS=front,left,back,top,persp34  ACTION=<name> FRAME=<n>  RES=700  SAMPLES=24
CAM='name:x,y,z:tx,ty,tz:lens' adds a custom perspective close-up (match a reference panel)."""
import bpy, os, sys, math
from mathutils import Vector as V
blend, out = sys.argv[-2], sys.argv[-1]; os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend); sc = bpy.context.scene
arm = next((o for o in bpy.data.objects if o.type == 'ARMATURE'), None)
if arm and arm.animation_data:
    act = os.environ.get('ACTION'); arm.animation_data.action = bpy.data.actions[act] if act else None
    if not act:
        for pb in arm.pose.bones: pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0)
sc.frame_set(int(os.environ.get('FRAME', '0')))
dg = bpy.context.evaluated_depsgraph_get()
pts = [o.matrix_world @ v.co for o in bpy.data.objects if o.type == 'MESH' for v in o.evaluated_get(dg).to_mesh().vertices]
lo = V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))); hi = V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
C = (lo + hi) / 2; size = max(hi - lo) * 1.1
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = int(os.environ.get('SAMPLES', '24'))
sc.render.film_transparent = True; sc.render.image_settings.color_mode = 'RGBA'; sc.render.resolution_x = sc.render.resolution_y = int(os.environ.get('RES', '700')); sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (.42, .42, .45, 1)
for nm, rot, e in (('key', (50, 0, -35), 1.7), ('fill', (60, 0, 150), .7), ('rim', (-60, 0, 180), .5), ('top', (0, 0, 0), .5)):
    l = bpy.data.lights.new(nm, 'SUN'); l.energy = e; o = bpy.data.objects.new(nm, l); sc.collection.objects.link(o)
    o.rotation_euler = [math.radians(a) for a in rot]
bpy.ops.mesh.primitive_plane_add(size=size * 6, location=(C.x, C.y, 0)); g = bpy.context.object
m = bpy.data.materials.new('G'); m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.92, .92, .94, 1); g.data.materials.append(m)
cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
D = size * 3
views = {'front': (C + V((0, -D, 0)), 'ORTHO'), 'left': (C + V((D, 0, 0)), 'ORTHO'), 'back': (C + V((0, D, 0)), 'ORTHO'),
         'top': (C + V((0, 0, D)), 'ORTHO'), 'right': (C + V((-D, 0, 0)), 'ORTHO'), 'persp34': (C + V((size * 1.0, -size * 1.3, size * .45)), 'PERSP')}
custom = {}
if os.environ.get('CAM'):
    for spec in os.environ['CAM'].split(';'):
        nm, p, t, lens = spec.split(':'); custom[nm] = (V(map(float, p.split(','))), V(map(float, t.split(','))), float(lens))
only = os.environ.get('VIEWS', 'front,left,back,top,persp34').split(',') + list(custom)
for nm in only:
    if nm in custom:
        loc, tgt, lens = custom[nm]; cd.type = 'PERSP'; cd.lens = lens
    elif nm in views:
        loc, typ = views[nm]; tgt = C; cd.type = typ; cd.ortho_scale = size; cd.lens = 35
    else: continue
    cam.location = loc
    cam.rotation_euler = (0, 0, 0) if nm == 'top' else (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
    g.hide_render = True; sc.render.filepath = os.path.join(out, nm + '.png'); bpy.ops.render.render(write_still=True)
print('rendered', only)
