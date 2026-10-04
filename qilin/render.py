"""Render the reference-style turnaround.  blender-python: python3 render.py [views] (env RES, SAMPLES, OUTD)
views: hero front back left right top bottom"""
import bpy, os, sys, math
from mathutils import Vector as V, Matrix
HERE = os.path.dirname(os.path.abspath(__file__))
OUTD = os.environ.get('OUTD', os.path.join(HERE, 'renders')); os.makedirs(OUTD, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, 'out', 'Qilin.blend')); sc = bpy.context.scene
RES = int(os.environ.get('RES', '800')); sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
sc.cycles.samples = int(os.environ.get('SAMPLES', '48')); sc.cycles.use_denoising = True
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x = RES; sc.render.resolution_y = RES
dg = bpy.context.evaluated_depsgraph_get()
pts = [o.matrix_world @ v.co for o in bpy.data.objects if o.type == 'MESH' for v in o.evaluated_get(dg).to_mesh().vertices]
lo = V((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))); hi = V((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
C = (lo + hi) / 2; size = max(hi - lo)
print('bbox', tuple(round(x, 2) for x in lo), tuple(round(x, 2) for x in hi))

DOWN = False
def setup(bg):
    w = bpy.data.worlds.new('W'); sc.world = w; w.use_nodes = True
    bgn = w.node_tree.nodes['Background']; bgn.inputs[0].default_value = bg + (1,); bgn.inputs[1].default_value = 1.0
    for l in [o for o in bpy.data.objects if o.type == 'LIGHT']: bpy.data.objects.remove(l)
    for nm, rot, e, col in (('key', (52, 0, -40), 2.6, (1, .96, .88)), ('fill', (65, 0, 140), 1.2, (.85, .92, 1)),
                            ('rim', (-55, 0, 175), 1.0, (.9, 1, .9)), ('top', (0, 0, 0), .5, (1, 1, 1))):
        l = bpy.data.lights.new(nm, 'SUN'); l.energy = e; l.color = col; o = bpy.data.objects.new(nm, l); sc.collection.objects.link(o)
        o.rotation_euler = [math.radians(a) for a in rot]
    if bg[0] < .05 and DOWN:
        l = bpy.data.lights.new('under', 'SUN'); l.energy = 2.2; o = bpy.data.objects.new('under', l); sc.collection.objects.link(o); o.rotation_euler = (math.radians(180), 0, 0)
    sc.use_nodes = True; nt = sc.node_tree; nt.nodes.clear()
    rl = nt.nodes.new('CompositorNodeRLayers'); gl = nt.nodes.new('CompositorNodeGlare'); co = nt.nodes.new('CompositorNodeComposite')
    gl.glare_type = 'FOG_GLOW'; gl.threshold = 1.0; gl.size = 7; gl.quality = 'MEDIUM'; gl.mix = -0.35
    nt.links.new(rl.outputs['Image'], gl.inputs['Image']); nt.links.new(gl.outputs['Image'], co.inputs['Image'])

cd = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam

def look(loc, tgt, upv=V((0, 0, 1))):
    f = (tgt - loc).normalized(); r = f.cross(upv).normalized(); u = r.cross(f)
    cam.matrix_world = Matrix(((r.x, u.x, -f.x, loc.x), (r.y, u.y, -f.y, loc.y), (r.z, u.z, -f.z, loc.z), (0, 0, 0, 1)))

Z0 = 8.0   # look-at height centre
D = 60
VIEWS = {  # name: (loc, tgt, up, ortho_scale|None, lens, bg)
    'front': (V((0, -D, 8.1)), V((0, 0, 8.1)), V((0, 0, 1)), 17.0, 0, (.009, .017, .035)),
    'back':  (V((0, D, 8.1)), V((0, 0, 8.1)), V((0, 0, 1)), 17.0, 0, (.009, .017, .035)),
    'left':  (V((D, 2.0, 7.6)), V((0, 2.0, 7.6)), V((0, 0, 1)), 23.5, 0, (.009, .017, .035)),
    'right': (V((-D, 2.0, 7.6)), V((0, 2.0, 7.6)), V((0, 0, 1)), 23.5, 0, (.009, .017, .035)),
    'top':   (V((0, 1.5, D)), V((0, 1.5, 0)), V((-1, 0, 0)), 22.5, 0, (.009, .017, .035)),
    'bottom': (V((0, 1.5, -D)), V((0, 1.5, 0)), V((1, 0, 0)), 22.5, 0, (.009, .017, .035)),
    'hero':  (V((-21, -24, 9.5)), V((0.6, 0.8, 7.3)), V((0, 0, 1)), None, 42, (.2, .62, .95)),
}
want = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else list(VIEWS)
for nm in want:
    loc, tgt, upv, osc, lens, bg = VIEWS[nm]; DOWN = (nm == 'bottom'); setup(bg)
    if osc: cd.type = 'ORTHO'; cd.ortho_scale = osc
    else: cd.type = 'PERSP'; cd.lens = lens; cd.sensor_width = 36
    sc.render.resolution_x = int(RES * .78) if nm == 'hero' else RES; sc.render.resolution_y = int(RES * 1.05) if nm == 'hero' else RES
    look(loc, tgt, upv)
    # ground only for hero
    for o in [o for o in bpy.data.objects if o.name == 'ground']: bpy.data.objects.remove(o)
    if nm == 'hero':
        bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, -0.02)); g = bpy.context.object; g.name = 'ground'
        m = bpy.data.materials.new('G'); m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.12, .5, .8, 1); g.data.materials.append(m)
    sc.render.filepath = os.path.join(OUTD, nm + '.png'); bpy.ops.render.render(write_still=True)
print('rendered', want)
