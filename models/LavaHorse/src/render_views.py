# Shared render helpers: studio lighting + the reference sheet's six views.
import bpy, math
from mathutils import Vector

LENS = {'front': 68, 'back': 68, 'left': 72, 'right': 72, 'three_quarter': 62, 'top': 62}
VIEWS = {   # name: (camera location, look-at, ortho?)
    'front':  ((0, -28, 4.5), (0, 0, 3.7), False),
    'back':   ((0, 28, 5.0), (0, 0, 3.7), False),
    'left':   ((28, 0.0, 4.7), (0, 0.3, 3.5), False),
    'right':  ((-28, 0.0, 4.7), (0, 0.3, 3.5), False),
    'three_quarter': ((18, -19, 8.0), (0, 0.4, 3.4), False),
    'top':    ((0, 0.3, 30), (0, 0.3, 0), False),
}


def setup_world(samples=24, res=(640, 480)):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.get('World') or bpy.data.worlds.new('World')
    sc.world = w
    bg = w.node_tree.nodes.get('Background')
    bg.inputs[0].default_value = (0.035, 0.04, 0.055, 1)
    bg.inputs[1].default_value = 2.0
    for n, loc, en, size in (('Key', (12, -14, 18), 2600, 8), ('Fill', (-14, -6, 8), 1000, 10),
                             ('Rim', (0, 16, 12), 1500, 8), ('Fill2', (14, 8, 6), 900, 10)):
        if n in bpy.data.objects:
            continue
        ld = bpy.data.lights.new(n, 'AREA'); ld.energy = en; ld.size = size
        lo = bpy.data.objects.new(n, ld); lo.location = loc
        bpy.context.scene.collection.objects.link(lo)
        d = Vector((0, 0, 3)) - lo.location
        lo.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if 'Floor' not in bpy.data.objects:
        me = bpy.data.meshes.new('Floor')
        s = 60
        me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        fl = bpy.data.objects.new('Floor', me)
        m = bpy.data.materials.new('FloorMat')
        m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.03, 0.035, 0.05, 1)
        m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.8
        me.materials.append(m)
        bpy.context.scene.collection.objects.link(fl)


def render_view(name, path, lens=None):
    loc, tgt, ortho = VIEWS[name]
    cd = bpy.data.cameras.get('Cam') or bpy.data.cameras.new('Cam')
    cam = bpy.data.objects.get('Cam') or bpy.data.objects.new('Cam', cd)
    if cam.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(cam)
    cd.lens = lens or LENS.get(name, 80)
    cam.location = loc
    cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    if name == 'top':   # reference sheet shows the head at the top of the frame
        cam.rotation_euler = (0, 0, math.pi)
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def add_glow():
    """Fog-glow compositor pass to mimic the reference sheet's bloom (preview renders only)."""
    sc = bpy.context.scene
    try:
        ng = bpy.data.node_groups.new('GlowComp', 'CompositorNodeTree')
        sc.compositing_node_group = ng
        rl = ng.nodes.new('CompositorNodeRLayers')
        gl = ng.nodes.new('CompositorNodeGlare')
        out = ng.nodes.new('NodeGroupOutput')
        ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        for k, v in (('Type', 'Fog Glow'), ('Threshold', 0.75), ('Strength', 0.6), ('Size', 0.6), ('Quality', 'Medium')):
            if k in gl.inputs:
                gl.inputs[k].default_value = v
        ng.links.new(rl.outputs['Image'], gl.inputs['Image'])
        ng.links.new(gl.outputs['Image'], out.inputs[0])
        print('GLOW_OK')
    except Exception as e:
        print('GLOW_FAIL', e)
