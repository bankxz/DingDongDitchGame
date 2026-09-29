"""
Render validation previews of Triceratops.blend (Cycles CPU, headless).

    python3 render_previews.py views      # front/right/left/back/top + silhouette masks
    python3 render_previews.py anims      # contact sheets for every action
    python3 render_previews.py pose       # extreme-pose deformation check

Writes into ../previews and ../validation.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = os.path.dirname(HERE)
PREV = os.path.join(ASSET, 'previews')
os.makedirs(PREV, exist_ok=True)

# name -> (azimuth deg around Z measured from -Y (front), elevation deg, distance scale)
VIEWS = {
    'front': (0, 12, 0.75),
    'right': (68, 12, 0.8),         # framed like the reference sheet: head toward image left
    'left': (-68, 12, 0.8),         # true opposite side (head toward image right)
    'back': (180, 16, 0.8),
    'top': (0, 62, 0.85),
    'right_ortho': (-90, 0, 1.0),
    'front_ortho': (0, 0, 1.0),
    'top_ortho': (0, 90, 1.0),
}


def setup(res=(768, 576), samples=40):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ASSET, 'Triceratops.blend'))
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    except TypeError:
        sc.cycles.use_denoising = False
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.view_settings.view_transform = 'Standard'
    sc.render.image_settings.file_format = 'PNG'

    world = sc.world or bpy.data.worlds.new('World')
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputWorld')
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Color'].default_value = (0.19, 0.19, 0.2, 1)
    bg.inputs['Strength'].default_value = 1.0
    nt.links.new(bg.outputs[0], out.inputs[0])

    sun = bpy.data.objects.new('LGT-key', bpy.data.lights.new('LGT-key', 'SUN'))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(8)
    sun.rotation_euler = (math.radians(40), math.radians(-18), math.radians(-35))
    sc.collection.objects.link(sun)
    fill = bpy.data.objects.new('LGT-fill', bpy.data.lights.new('LGT-fill', 'SUN'))
    fill.data.energy = 0.9
    fill.rotation_euler = (math.radians(60), math.radians(20), math.radians(150))
    sc.collection.objects.link(fill)

    floor = bpy.data.meshes.new('floor')
    floor.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
    fo = bpy.data.objects.new('REF-floor', floor)
    fo.is_shadow_catcher = True
    sc.collection.objects.link(fo)
    sc.render.film_transparent = True

    cam = bpy.data.objects.new('CAM-main', bpy.data.cameras.new('CAM-main'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam


def bbox():
    mesh = bpy.data.objects['TriceratopsMesh']
    dg = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(dg)
    pts = [mesh.matrix_world @ v.co for v in ev.data.vertices]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def aim(cam, az, el, dist_scale, ortho=False):
    lo, hi = bbox()
    c = (lo + hi) / 2
    size = (hi - lo).length
    a, e = math.radians(az), math.radians(el)
    d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    if ortho:
        cam.data.type = 'ORTHO'
        cam.data.ortho_scale = size * 1.05 * dist_scale
        cam.location = c + d * size * 3
    else:
        cam.data.type = 'PERSP'
        cam.data.lens = 85
        cam.location = c + d * size * 2.6 * dist_scale
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cam.data.clip_end = 200


def render(path):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print('rendered', path)


def views():
    sc, cam = setup()
    for name, (az, el, ds) in VIEWS.items():
        aim(cam, az, el, ds, ortho=name.endswith('ortho'))
        render(os.path.join(PREV, f'view_{name}.png'))


def anims(frames_per_sheet=8):
    sc, cam = setup(res=(480, 360), samples=16)
    rig = bpy.data.objects['Triceratops']
    for act in bpy.data.actions:
        rig.animation_data.action = act
        f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
        for i in range(frames_per_sheet):
            f = f0 + round(i * (f1 - f0) / frames_per_sheet)
            sc.frame_set(f)
            aim(cam, -80, 10, 1.0)
            render(os.path.join(PREV, 'frames', f'{act.name}_{i:02d}_f{f:03d}.png'))


def pose_test():
    """Extreme pose: stresses every joint to expose weight problems."""
    from mathutils import Quaternion
    sc, cam = setup(res=(768, 576), samples=32)
    rig = bpy.data.objects['Triceratops']
    rig.animation_data.action = None

    def rot(name, axis, ang):
        pb = rig.pose.bones[name]
        pb.rotation_mode = 'QUATERNION'
        local = pb.bone.matrix_local.to_3x3().inverted() @ Vector(axis)
        pb.rotation_quaternion = Quaternion(local, ang)
    rot('Head', (0, 0, 1), 0.5)
    rot('Neck', (1, 0, 0), -0.3)
    rot('Jaw', (1, 0, 0), -0.4)
    rot('Chest', (0, 0, 1), 0.15)
    for i in range(1, 5):
        rot(f'Tail_0{i}', (0, 0, 1), 0.25)
    rot('FrontLeg_L_Upper', (1, 0, 0), -0.6)
    rot('FrontLeg_L_Lower', (1, 0, 0), 0.9)
    rot('BackLeg_R_Upper', (1, 0, 0), 0.6)
    rot('BackLeg_R_Lower', (1, 0, 0), 0.7)
    for name, (az, el) in {'pose_right': (-60, 18), 'pose_top': (20, 70)}.items():
        aim(cam, az, el, 1.0)
        render(os.path.join(PREV, f'{name}.png'))


if __name__ == '__main__':
    what = sys.argv[-1]
    {'views': views, 'anims': anims, 'pose': pose_test}[what]()
