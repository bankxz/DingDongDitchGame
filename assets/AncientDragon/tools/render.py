"""Render validation views (front/back/left/right/top/bottom/3-4) from the saved .blend."""
import bpy, math, os, sys
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..'))
OUT = os.path.join(ROOT, 'validation')
action = sys.argv[sys.argv.index('--action') + 1] if '--action' in sys.argv else 'Idle'
frames = [int(f) for f in sys.argv[sys.argv.index('--frames') + 1].split(',')] if '--frames' in sys.argv else [1]
views = sys.argv[sys.argv.index('--views') + 1].split(',') if '--views' in sys.argv else ['front', 'back', 'left', 'right', 'top', 'bottom', 'persp']
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, 'AncientDragon.blend'))
sc = bpy.context.scene
rig = bpy.data.objects['DragonRig']
rig.animation_data.action = bpy.data.actions[action]
sc.render.engine = 'CYCLES'; sc.cycles.samples = 24; sc.cycles.use_denoising = True
sc.cycles.device = 'CPU'
sc.render.resolution_x, sc.render.resolution_y = 720, 540
sc.view_settings.view_transform = 'Standard'
w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes['Background']; bg.inputs[0].default_value = (0.35, 0.62, 0.95, 1); bg.inputs[1].default_value = 0.9
sun = bpy.data.objects.new('Sun', bpy.data.lights.new('Sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.2; sun.rotation_euler = (math.radians(50), 0, math.radians(-35)); sun.data.angle = math.radians(8)
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
g = bpy.context.object; gm = bpy.data.materials.new('G'); gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.05, 0.05, 0.08, 1)
gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.6
g.data.materials.append(gm)
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam')); sc.collection.objects.link(cam); sc.camera = cam
ctr = Vector((0, 0.9, 1.6))
V = {  # direction from target to camera, ortho?
    'front': (Vector((0, -1, 0.06)), True), 'back': (Vector((0, 1, 0.12)), True),
    'left': (Vector((1, 0, 0.03)), True), 'right': (Vector((-1, 0, 0.03)), True),
    'top': (Vector((0, 0.001, 1)), True), 'bottom': (Vector((0, 0.001, -1)), True),
    'persp': (Vector((0.8, -1.0, 0.22)), False),
}
for fr in frames:
    sc.frame_set(fr)
    for name in views:
        d, ortho = V[name]
        d = d.normalized()
        g.hide_render = name in ('bottom',)
        cam.location = ctr + d * 30
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y' if name not in ('top', 'bottom') else 'Y').to_euler()
        if name in ('top', 'bottom'):
            cam.rotation_euler = (0, 0, 0) if name == 'top' else (math.pi, 0, 0)
            cam.rotation_euler.z = math.radians(90 if name == 'top' else -90)
        cam.data.type = 'ORTHO' if ortho else 'PERSP'
        cam.data.ortho_scale = {'front': 7.2, 'back': 7.2, 'left': 10.0, 'right': 10.0, 'top': 10.5, 'bottom': 10.5}.get(name, 8)
        cam.data.lens = 50
        if not ortho:
            tgt = Vector((0, -0.2, 1.8)); cam.location = tgt + d * 8.6; cam.data.lens = 35
            cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        sc.render.filepath = os.path.join(OUT, f'{action}_{fr:03d}_{name}.png')
        bpy.ops.render.render(write_still=True)
print('done')
