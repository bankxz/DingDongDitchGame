"""Preview / validation rendering helpers (Cycles CPU, works headless)."""
import math
import bpy
from mathutils import Vector

VIEW_DIRS = {
    # name: (camera direction FROM target, ortho?)  creature faces -Y, left = +X
    'front': (Vector((0, -1, 0.27)), True),
    'back': (Vector((0, 1, 0.27)), True),
    'side_left': (Vector((1, 0, 0)), True),       # sees the creature's left flank, head to the right
    'side_right': (Vector((-1, 0, 0)), True),     # head to the left (matches reference sheet panel 2)
    'top': (Vector((0, -0.6, 1)), True),
    'top_ortho': (Vector((0, 0.0001, 1)), True),
    'q34_front_right': (Vector((-1.0, -0.75, 0.30)), False),
    'q34_back_left': (Vector((-1.25, 0.55, 0.25)), False),
    'q34_front_left': (Vector((1.0, -1.1, 0.45)), False),
    'head_close': (Vector((0, -1, 0.15)), False),
}


def setup_scene(res=(900, 650), samples=48):
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    world = bpy.data.worlds.get('WLD-preview') or bpy.data.worlds.new('WLD-preview')
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.24, 0.24, 0.26, 1)
    bg.inputs['Strength'].default_value = 0.9
    sc.world = world
    # lights (created once)
    if 'LGT-key' not in bpy.data.objects:
        for name, rot, energy, col in (('LGT-key', (50, 10, -35), 3.2, (1, 0.98, 0.95)),
                                       ('LGT-fill', (60, -10, 140), 1.2, (0.85, 0.9, 1.0)),
                                       ('LGT-rim', (35, 0, 180), 1.6, (0.9, 0.95, 1.0))):
            ld = bpy.data.lights.new(name, 'SUN')
            ld.energy = energy
            ld.color = col
            ld.angle = math.radians(8)
            ob = bpy.data.objects.new(name, ld)
            ob.rotation_euler = [math.radians(a) for a in rot]
            sc.collection.objects.link(ob)
    if 'GEO-ground' not in bpy.data.objects:
        me = bpy.data.meshes.new('GEO-ground')
        s = 400
        me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
        ob = bpy.data.objects.new('GEO-ground', me)
        mat = bpy.data.materials.new('MAT-ground')
        mat.use_nodes = True
        b = mat.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (0.2, 0.2, 0.21, 1)
        b.inputs['Roughness'].default_value = 0.9
        me.materials.append(mat)
        ob.is_shadow_catcher = False
        sc.collection.objects.link(ob)
    return sc


def get_camera():
    sc = bpy.context.scene
    cam = bpy.data.objects.get('CAM-preview')
    if cam is None:
        cd = bpy.data.cameras.new('CAM-preview')
        cam = bpy.data.objects.new('CAM-preview', cd)
        sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def aim(cam, target, direction, dist):
    d = direction.normalized()
    cam.location = target + d * dist
    q = (-d).to_track_quat('-Z', 'Y' if abs(d.z) < 0.99 else 'Y')
    cam.rotation_euler = q.to_euler()


def render_view(name, path, target, extent, ortho_scale=None, lens=50, res=None, samples=None):
    sc = bpy.context.scene
    if res:
        sc.render.resolution_x, sc.render.resolution_y = res
    if samples:
        sc.cycles.samples = samples
    cam = get_camera()
    d, ortho = VIEW_DIRS[name]
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = ortho_scale or extent
        aim(cam, target, d, extent * 4)
    else:
        cam.data.type = 'PERSP'
        cam.data.lens = lens
        aim(cam, target, d, extent * (lens / 50.0) * 1.35)
    cam.data.clip_end = extent * 50
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    return path
