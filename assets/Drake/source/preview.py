"""Quick flat-colour preview renders of the drake geometry (validation loop)."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, bmesh
from mathutils import Vector
import importlib
import drake_geo as G
importlib.reload(G)

OUT = sys.argv[-1] if sys.argv[-1].endswith('/') else '/tmp/prev/'
os.makedirs(OUT, exist_ok=True)


def make_mesh(mb, name='GEO-Drake'):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in mb.v], [], mb.f)
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()
    for i, fix in enumerate(mb.fix):
        if fix is not None and bm.faces[i].normal.dot(fix) < 0:
            bm.faces[i].normal_flip()
    bm.to_mesh(me); bm.free()
    return ob


def setup_scene():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.film_transparent = False
    w = bpy.data.worlds.new('W'); sc.world = w
    w.use_nodes = True
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.035, 0.04, 0.055, 1)
    w.node_tree.nodes['Background'].inputs[1].default_value = 1.0
    sc.view_settings.exposure = 0.6
    for name, rot, e in [('Key', (math.radians(50), 0, math.radians(-35)), 4.0),
                         ('Fill', (math.radians(60), 0, math.radians(140)), 1.5),
                         ('Top', (0, 0, 0), 1.5),
                         ('Under', (math.radians(125), 0, math.radians(20)), 1.2)]:
        ld = bpy.data.lights.new(name, 'SUN'); ld.energy = e; ld.angle = 0.3
        lo = bpy.data.objects.new(name, ld); lo.rotation_euler = rot
        sc.collection.objects.link(lo)
    cam = bpy.data.cameras.new('Cam')
    co = bpy.data.objects.new('CAM', cam); sc.collection.objects.link(co); sc.camera = co
    sc.view_settings.view_transform = 'Standard'
    w.node_tree.nodes['Background'].inputs[0].default_value = (0.09, 0.10, 0.13, 1)
    return co


def aim(co, loc, target, ortho=None, lens=50):
    co.location = loc
    d = Vector(target) - Vector(loc)
    co.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    if ortho:
        co.data.type = 'ORTHO'; co.data.ortho_scale = ortho
    else:
        co.data.type = 'PERSP'; co.data.lens = lens


VIEWS = {
    'front': ((0, -14, 0.8), (0, 0, 0.8), 3.4, (640, 640)),
    'back': ((0, 14, 0.8), (0, 0, 0.8), 3.4, (640, 640)),
    'left': ((14, 0.0, 0.9), (0, 0.0, 0.9), 9.0, (1400, 420)),
    'right': ((-14, 0.0, 0.9), (0, 0.0, 0.9), 9.0, (1400, 420)),
    'top': ((0, 0.0, 16), (0, 0.0001, 0), 9.0, (1400, 360)),
    'head': ((3.2, -6.6, 1.9), (0, -3.6, 1.0), None, (800, 600)),
    'q34': ((7.0, -8.5, 3.0), (0, -0.6, 0.7), None, (1200, 700)),
}


def render_views(co, prefix, views=VIEWS):
    sc = bpy.context.scene
    for k, (loc, tgt, ortho, res) in views.items():
        aim(co, loc, tgt, ortho, lens=40)
        if k == 'top':
            co.rotation_euler = (0, 0, math.radians(90))
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.filepath = os.path.join(OUT, f'{prefix}_{k}.png')
        bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mb = G.build_all()
    print('TRIS', mb.tris(), 'VERTS', len(mb.v))
    ob = make_mesh(mb)
    mats = []
    for n in G.PAL_NAMES:
        m = bpy.data.materials.new(n); m.use_nodes = True
        r, g, b = [c / 255 for c in G.PALETTE[n]]
        bs = m.node_tree.nodes['Principled BSDF']
        bs.inputs['Base Color'].default_value = (r ** 2.2, g ** 2.2, b ** 2.2, 1)
        bs.inputs['Roughness'].default_value = 0.5
        ob.data.materials.append(m)
    for p, ci in zip(ob.data.polygons, mb.fc):
        p.material_index = ci
    co = setup_scene()
    render_views(co, 'prev')
