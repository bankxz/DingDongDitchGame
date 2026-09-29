"""Render validation views matching the reference sheet panels (Cycles CPU, headless)."""
import math, os, sys
import bpy
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.abspath(os.path.join(HERE, '..'))
VAL = os.path.join(OUT, 'validation')
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
action = argv[0] if argv and argv[0] else None
frames = [int(x) for x in argv[1].split(',')] if len(argv) > 1 and argv[1] else [None]
views = argv[2].split(',') if len(argv) > 2 else None
res = int(argv[3]) if len(argv) > 3 else 640

bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, 'GreenDino.blend'))
sc = bpy.context.scene
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = int(argv[4]) if len(argv) > 4 else 24
sc.cycles.use_denoising = True
try: sc.cycles.denoiser = 'OPENIMAGEDENOISE'
except Exception: pass
sc.view_settings.view_transform = 'Standard'
rig = bpy.data.objects['GreenDinoRig']
if action:
  rig.animation_data.action = bpy.data.actions[action]
  for tr in rig.animation_data.nla_tracks: tr.mute = True

# sky + ground like the reference sheet
w = bpy.data.worlds.new('Sky'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.45, 0.68, 0.95, 1); bg.inputs[1].default_value = 0.9
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
g = bpy.context.object; gm = bpy.data.materials.new('Ground'); gm.use_nodes = True
gb = gm.node_tree.nodes['Principled BSDF']
chk = gm.node_tree.nodes.new('ShaderNodeTexChecker'); chk.inputs['Scale'].default_value = 40
chk.inputs['Color1'].default_value = (0.13, 0.14, 0.22, 1); chk.inputs['Color2'].default_value = (0.15, 0.16, 0.25, 1)
gm.node_tree.links.new(chk.outputs['Color'], gb.inputs['Base Color']); gb.inputs['Roughness'].default_value = 0.9
g.data.materials.append(gm)
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.2; sun.data.angle = math.radians(8)
sun.rotation_euler = (math.radians(50), math.radians(-15), math.radians(30))

cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
C = Vector((0, 0.3, 2.0))
VIEWS = {  # name: (location, target, lens, ortho_scale or None, aspect)
  'left':   (Vector((30, -10.0, 3.0)), Vector((0, 0.3, 1.5)), 62, None, (16, 9)),
  'right':  (Vector((-30, 10.0, 3.0)), Vector((0, -0.3, 1.5)), 62, None, (16, 9)),
  'front':  (Vector((0, -17, 3.6)), Vector((0, 0, 1.6)), 50, None, (9, 10)),
  'back':   (Vector((0, 17, 4.5)), Vector((0, 0, 2.2)), 50, None, (9, 10)),
  'top':    (Vector((0, 0.3, 22)), Vector((0, 0.6, 0)), 50, None, (6, 10)),
  'bottom': (Vector((0, 0.3, -22)), Vector((0, 0.6, 0)), 50, None, (6, 10)),
  'hero':   (Vector((11, -11, 3.6)), Vector((0, -0.5, 1.8)), 42, None, (16, 9)),
  'idle34': (Vector((12, -9, 4.0)), Vector((0, 0.3, 1.8)), 45, None, (4, 3)),
  'legzoom': (Vector((9, -3.6, 1.6)), Vector((2.2, -2.0, 1.2)), 40, None, (4, 3)),
  'mouthlow': (Vector((4.5, -9.5, 1.2)), Vector((0, -4.5, 1.6)), 45, None, (4, 3)),
  'headside': (Vector((6.5, -5.0, 3.6)), Vector((0, -4.8, 3.0)), 50, None, (3, 4)),
  'headfront': (Vector((1.2, -12.0, 3.6)), Vector((0, -5, 3.2)), 60, None, (3, 4)),
}
if 'bottom' in (views or VIEWS): pass
for f in frames:
  if f is not None: sc.frame_set(f)
  for name in (views or VIEWS):
    loc, tgt, lens, ortho, asp = VIEWS[name]
    g.hide_render = (name == 'bottom')
    cam.location = loc
    d = (tgt - loc); cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if name == 'top': cam.rotation_euler.z += math.pi
    cam.data.lens = lens; cam.data.clip_end = 200
    sc.render.resolution_x = res; sc.render.resolution_y = int(res * asp[1] / asp[0])
    sc.render.filepath = os.path.join(VAL, f"{name}{'' if f is None else '_' + (action or '') + '_%03d' % f}.png")
    bpy.ops.render.render(write_still=True)
    print('RENDERED', sc.render.filepath)
