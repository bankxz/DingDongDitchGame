"""stud_kit - helpers for procedurally building stud-style Roblox models in headless Blender.

Import from a build script run with the `bpy` Python module (pip install bpy==4.2.0, Py3.11):

    import sys; sys.path.insert(0, '<skill>/scripts')
    import stud_kit as K
    K.init('<out>/textures/atlas_regions.json', stud=0.45)
    BODY, GLOW = K.MeshAcc('Model_Body'), K.MeshAcc('Model_Glow', glow=True)
    K.loft(BODY, rings, 8, lambda n, c, i: 'white' if n.z < -0.45 else 'navy', cap0='navy')
    ...
    K.new_scene(); body = K.build_object(BODY, K.make_material('Body', color_png, normal_png))

Conventions: Z up, the model faces -Y, its left side is +X (bones *.L). 1 unit = 1 stud.
Every face carries a slot name from the atlas; studded slots get per-face planar UVs
snapped to whole studs, other slots get UVs that fill the swatch (or explicit UVs).
Every vertex carries {bone: weight}; build_object turns them into vertex groups.
"""
import json, math, os, random
from mathutils import Vector as V, Matrix

ATLAS = None
STUD = 0.45                     # world size of one stud (studs read best at ~1/5 of a head width)


def init(atlas_regions_json, stud=0.45):
    global ATLAS, STUD
    ATLAS = json.load(open(atlas_regions_json)); STUD = stud


class MeshAcc:
    """Accumulates verts, per-vertex bone weights and faces (indices, slot, explicit uvs|None)."""
    def __init__(self, name, glow=False):
        self.name, self.glow = name, glow
        self.v, self.w, self.f = [], [], []

    def add_v(self, p, wt):
        self.v.append(V(p)); self.w.append(dict(wt)); return len(self.v) - 1

    def face(self, idx, slot, uvs=None):
        self.f.append((list(idx), slot, uvs))

    def tris(self):
        return sum(len(i) - 2 for i, _, _ in self.f)


def W(b, b2=None, t=0.0):
    """Rigid weight to b, or a linear blend b -> b2 by t (keeps <= 2 influences)."""
    if b2 is None or t <= 0: return {b: 1.0}
    if t >= 1: return {b2: 1.0}
    return {b: 1 - t, b2: t}


def blend(a, b, t=0.5):
    out = {}
    for ww, k in ((a, 1 - t), (b, t)):
        for n, x in ww.items(): out[n] = out.get(n, 0) + x * k
    return out


def frame(T, up=V((0, 0, 1))):
    """Right-handed (side, up) pair perpendicular to direction T."""
    T = V(T).normalized(); up = V(up)
    if abs(T.dot(up.normalized())) > 0.95: up = V((0, 1, 0)) if abs(T.y) < 0.9 else V((1, 0, 0))
    s = T.cross(up).normalized(); return s, s.cross(T).normalized()


def _uv_rect(slot, px, py):
    x, y, w, h = ATLAS['slots'][slot]; S = ATLAS['size']
    return ((x + px) / S, 1 - (y + py) / S)


# ------------------------------------------------------------------ primitives
def loft(acc, rings, n, color, cap0=None, cap1=None, rot=math.pi / 8):
    """Tube through rings [{c, rx, ry, w, T?, up?}]; color(face_normal, face_centre, ring_i)->slot.
    Use n=8 (rot=pi/8 gives flat top/bottom/sides) for bodies/necks/tails, 6 for thin limbs."""
    cs = [V(r['c']) for r in rings]; ids = []
    for i, r in enumerate(rings):
        T = r.get('T') or (cs[min(i + 1, len(cs) - 1)] - cs[max(i - 1, 0)])
        s, u = frame(V(T), V(r.get('up', (0, 0, 1))))
        ids.append([acc.add_v(cs[i] + s * (r['rx'] * math.cos(rot + 2 * math.pi * k / n))
                              + u * (r['ry'] * math.sin(rot + 2 * math.pi * k / n)), r['w']) for k in range(n)])
    for i in range(len(rings) - 1):
        for k in range(n):
            q = [ids[i][k], ids[i + 1][k], ids[i + 1][(k + 1) % n], ids[i][(k + 1) % n]]
            P = [acc.v[j] for j in q]
            acc.face(q, color((P[2] - P[0]).cross(P[3] - P[1]).normalized(), sum(P, V()) / 4, i))
    def cap(row, flip, slot):
        ci = acc.add_v(sum((acc.v[j] for j in row), V()) / len(row), acc.w[row[0]])
        for k in range(n):
            tri = [row[k], row[(k + 1) % n], ci]
            acc.face(tri[::-1] if flip else tri, slot)
    if cap0: cap(ids[0], False, cap0)
    if cap1: cap(ids[-1], True, cap1)
    return ids


def box(acc, c, size, slot, wt, M=Matrix.Identity(3), taper=1.0, slots=None):
    """Oriented box (12 tris). taper<1 shrinks the top. slots overrides per face:
    0 bottom, 1 top, 2 back(-y), 3 +x, 4 front(+y), 5 -x (in the box's local frame)."""
    c = V(c); sx, sy, sz = (v / 2 for v in size); pts = []
    for z, tp in ((-sz, 1.0), (sz, taper)):
        for x, y in ((-sx, -sy), (sx, -sy), (sx, sy), (-sx, sy)):
            pts.append(c + M @ V((x * tp, y * tp, z)))
    ids = [acc.add_v(p, wt) for p in pts]
    for qi, q in enumerate([(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]):
        acc.face([ids[j] for j in q], (slots or {}).get(qi, slot))


def bevel_prism(acc, xy, z0, z1, slot, wt, to_world, mirror=1):
    """Extrude a convex outline (x side, y forward; counter-clockwise seen from +z, drawn for
    the +x side) between z0..z1. to_world(Vector)->Vector maps local points (e.g. a head frame).
    Cut a corner of the outline to get a big bevel on that edge (brows, cheek plates)."""
    pts = [(x * mirror, y) for x, y in xy]
    if mirror < 0: pts = pts[::-1]
    lo = [acc.add_v(to_world(V((x, y, z0))), wt) for x, y in pts]
    hi = [acc.add_v(to_world(V((x, y, z1))), wt) for x, y in pts]
    for i in range(1, len(pts) - 1):
        acc.face([hi[0], hi[i], hi[i + 1]], slot); acc.face([lo[0], lo[i + 1], lo[i]], slot)
    for i in range(len(pts)):
        j = (i + 1) % len(pts); acc.face([lo[i], lo[j], hi[j], hi[i]], slot)


def shard(acc, base, d, length, width, wt, twist=0.0, hero=False, slot='crystal', widen=1.85, flat=0.5):
    """Ice crystal. Blade (4 tris, default) or hero (12 tris: base ring -> wider shoulder -> tip).
    On a glow mesh the blade is widened and flattened (broad flat ice). Uses the crystal
    swatch whose facet-edge lines match these UV layouts. Faces wind outward."""
    d = V(d).normalized(); base = V(base); s, u = frame(d); u = -u   # ccw around d => outward
    fl = 1.0
    if acc.glow: width *= widen; fl = flat
    x, y, w, h = ATLAS['slots'][slot]; S = ATLAS['size']
    U = lambda uu, vv: ((x + 3 + uu * (w - 6)) / S, 1 - (y + 3 + (1 - vv) * (h - 6)) / S)
    ring = lambda p0, rad: [acc.add_v(p0 + (s * math.cos(twist + k * math.pi / 2) + u * fl * math.sin(twist + k * math.pi / 2)) * rad, wt) for k in range(4)]
    tip = None
    if not hero:
        r0 = ring(base, width * 0.5); tip = acc.add_v(base + d * length, wt)
        for k in range(4): acc.face([r0[k], r0[(k + 1) % 4], tip], slot, [U(0, 0), U(1, 0), U(.5, 1)])
        return
    r0 = ring(base, width * 0.275); r1 = ring(base + d * length * 0.32, width * 0.5)
    tip = acc.add_v(base + d * length, wt)
    for k in range(4):
        k2 = (k + 1) % 4
        acc.face([r0[k], r0[k2], r1[k2], r1[k]], slot, [U(.2, 0), U(.8, 0), U(1, .32), U(0, .32)])
        acc.face([r1[k], r1[k2], tip], slot, [U(0, .32), U(1, .32), U(.5, 1)])


def solid_spike(acc, base, d, length, width, wt, slot):
    """4-tri pyramid filled with a plain swatch (gold horns, toe gems). Sink its base into the
    parent surface by ~0.1 stud so there is never a visible gap."""
    d = V(d).normalized(); s, u = frame(d); u = -u
    ring = [acc.add_v(V(base) + (s * math.cos(.78 + k * math.pi / 2) + u * math.sin(.78 + k * math.pi / 2)) * width * .5, wt) for k in range(4)]
    tip = acc.add_v(V(base) + d * length, wt)
    for k in range(4): acc.face([ring[k], ring[(k + 1) % 4], tip], slot)


def cluster(acc, base, d, spread, count, length, width, wt, seed=0, side=None):
    """Fan of shards; the centre one is a hero shard."""
    rnd = random.Random(seed); d = V(d).normalized(); s, u = frame(d)
    if side is not None: s = V(side).normalized(); u = s.cross(d).normalized()
    for i in range(count):
        a = (i / max(count - 1, 1) - .5) * 2 if count > 1 else 0
        dd = (d + s * (a * spread) + u * rnd.uniform(-.25, .25) * spread).normalized()
        shard(acc, V(base) + s * (a * width * .9), dd, length * (1 - .35 * abs(a)) * rnd.uniform(.85, 1.1),
              width * rnd.uniform(.8, 1.1), wt, twist=rnd.uniform(0, 1.5), hero=abs(a) < .01)


def claw(acc, top, fwd, reach, drop, w, h, wt, slot='tooth'):
    """Chunky chamfered claw: runs forward off a toe, then bends straight down to a flat
    blunt tip. Keep top.z - drop >= 0 so the tip rests ON the ground, not under it."""
    fwd = V(fwd).normalized(); side = fwd.cross(V((0, 0, 1))).normalized(); up = V((0, 0, 1))
    def ring(c, a, b, n):
        k = .62; pts = [(a, b*k), (a*k, b), (-a*k, b), (-a, b*k), (-a, -b*k), (-a*k, -b), (a*k, -b), (a, -b*k)]
        nn = n.cross(side).normalized(); return [acc.add_v(c + side * x + nn * y, wt) for x, y in pts]
    p0 = V(top); p1 = p0 + fwd * reach * .8 - up * drop * .15; p2 = p0 + fwd * reach - up * drop
    rs = [ring(p0, w / 2, h / 2, fwd), ring(p1, w / 2 * .97, h / 2, (fwd - up).normalized()),
          ring(p2, w / 2 * .88, h / 2 * .85, (-up + fwd * .1).normalized())]
    for ra, rb in zip(rs, rs[1:]):
        for i in range(8): acc.face([ra[i], ra[(i + 1) % 8], rb[(i + 1) % 8], rb[i]], slot)
    acc.face(rs[2], slot)


def chevron(acc, c, fwd, w, h, t, wt, slot='gold'):
    """Inverted-V trim (apex up) facing fwd - gold toe/armour accents."""
    fwd = V(fwd).normalized(); side = fwd.cross(V((0, 0, 1))).normalized(); up = side.cross(fwd).normalized()
    th = .42 * h; o = [(-w/2, 0), (0, h), (w/2, 0), (w/2 - th, 0), (0, h - th * 1.2), (-w/2 + th, 0)]
    b = [acc.add_v(V(c) + side * x + up * y, wt) for x, y in o]; f = [acc.add_v(V(c) + side * x + up * y + fwd * t, wt) for x, y in o]
    for tri in ((0, 1, 5), (1, 4, 5), (1, 2, 4), (2, 3, 4)):
        acc.face([f[i] for i in tri], slot); acc.face([b[i] for i in tri][::-1], slot)
    for i in range(6):
        j = (i + 1) % 6; acc.face([b[i], b[j], f[j], f[i]], slot)


def tooth(acc, base, d, length, width, wt, slot='tooth'):
    solid_spike(acc, base, d, length, width, wt, slot)


def gem_plate(acc, c, n, up, w, h, t, wt, slot='gem'):
    """Diamond bipyramid gem (8 tris) facing n."""
    c, n, up = V(c), V(n).normalized(), V(up).normalized(); s = up.cross(n).normalized(); up = n.cross(s)
    ring = [acc.add_v(p, wt) for p in (c + up * h, c + s * w, c - up * h, c - s * w)]
    f, b = acc.add_v(c + n * t, wt), acc.add_v(c - n * t * .3, wt)
    uv = lambda px, py: _uv_rect(slot, px * ATLAS['slots'][slot][2], (1 - py) * ATLAS['slots'][slot][3])
    ur = [uv(.5, 1), uv(0, .5), uv(.5, 0), uv(1, .5)]
    for k in range(4):
        k2 = (k + 1) % 4
        acc.face([ring[k2], ring[k], f], slot, [ur[k2], ur[k], uv(.5, .5)])
        acc.face([ring[k], ring[k2], b], slot, [ur[k], ur[k2], uv(.5, .5)])


ANGRY_EYE = [(-.42, .13), (-.14, .17), (.16, .10), (.42, -.02), (.46, -.09), (.26, -.19), (-.04, -.21), (-.32, -.12)]

def eye_lens(acc, c, n, up, fwd, wt, outline=ANGRY_EYE, scale=1.0, dome=.05, slot='eye'):
    """Domed eye surface in a socket, UV'd across the eye swatch (glow/iris/slit pupil).
    outline is (along fwd, up) - the default is an angry almond whose top edge the brow cuts."""
    n = V(n).normalized(); t = (V(fwd) - n * V(fwd).dot(n)).normalized()
    w = (V(up) - n * V(up).dot(n) - t * V(up).dot(t)).normalized(); c = V(c)
    pts = [c + (t * a + w * b) * scale for a, b in outline]
    ref = n.cross(t); pts.sort(key=lambda p: math.atan2((p - c).dot(ref), (p - c).dot(t)))
    us = [(p - c).dot(t) for p in pts]; vs = [(p - c).dot(w) for p in pts]
    x0, y0, sw, sh = ATLAS['slots'][slot]; S = ATLAS['size']
    uv = lambda uu, vv: ((x0 + 3 + (uu - min(us)) / (max(us) - min(us)) * (sw - 6)) / S,
                         1 - (y0 + 3 + (1 - (vv - min(vs)) / (max(vs) - min(vs))) * (sh - 6)) / S)
    ids = [acc.add_v(p, wt) for p in pts]; ci = acc.add_v(c + n * dome * scale, wt)
    for i in range(len(ids)):
        j = (i + 1) % len(ids); acc.face([ci, ids[i], ids[j]], slot, [uv(0, 0), uv(us[i], vs[i]), uv(us[j], vs[j])])


def two_sided_sheet(acc, tris, sheet_w, slot, side_offset):
    """Wing membranes etc.: each triangle (pts, weights) emitted twice, offset +/- and
    wound opposite, so Roblox backface culling shows it from both sides."""
    for pts, wts in tris:
        for sgn in (1, -1):
            ids = [acc.add_v(V(p) + V(side_offset) * sgn, w) for p, w in zip(pts, wts)]
            acc.face(ids if sgn > 0 else ids[::-1], slot)


# ------------------------------------------------------------------------ UVs
def stud_uvs(acc, idx, slot):
    """Planar projection in world units / STUD, snapped to whole studs so coplanar
    neighbours line up; scaled down only if the face is bigger than its swatch."""
    P = [acc.v[i] for i in idx]; n = V((0, 0, 0))
    for i in range(len(P)): n += P[i].cross(P[(i + 1) % len(P)])
    n = n.normalized() if n.length > 1e-9 else V((0, 0, 1))
    t = V((0, 0, 1)).cross(n)
    if t.length < .3: t = V((1, 0, 0)) - n * n.x
    t.normalize(); b = n.cross(t)
    cu = [p.dot(t) / STUD for p in P]; cv = [-p.dot(b) / STUD for p in P]
    x, y, w, h = ATLAS['slots'][slot]; px = ATLAS['px_per_stud']
    su, sv = math.floor(min(cu)), math.floor(min(cv))
    k = min(1.0, (w / px - .3) / max(max(cu) - su, 1e-6), (h / px - .3) / max(max(cv) - sv, 1e-6))
    return [_uv_rect(slot, 4 + (u - su) * k * px, 4 + (v - sv) * k * px) for u, v in zip(cu, cv)]


def fill_uvs(acc, idx, slot):
    """Planar map that fills the swatch (gradients, gold, flat colours)."""
    P = [acc.v[i] for i in idx]; n = (P[1] - P[0]).cross(P[2] - P[0]).normalized()
    t = V((0, 0, 1)).cross(n)
    if t.length < .3: t = V((1, 0, 0))
    t.normalize(); b = n.cross(t); x, y, w, h = ATLAS['slots'][slot]
    cu = [p.dot(t) for p in P]; cv = [-p.dot(b) for p in P]
    eu = max(max(cu) - min(cu), 1e-6); ev = max(max(cv) - min(cv), 1e-6)
    return [_uv_rect(slot, 4 + (u - min(cu)) / eu * (w - 8), 4 + (v - min(cv)) / ev * (h - 8)) for u, v in zip(cu, cv)]


# ------------------------------------------------------------- Blender objects
def new_scene():
    import bpy
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.scale_length = 1.0
    return bpy.context.scene


def make_material(name, color_png, normal_png=None, glow=False, emission=0.55, emissive_png=None):
    """Principled material on the atlas. Glow materials add emission (Blender preview only -
    in Roblox set that MeshPart to Neon/Glass)."""
    import bpy
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; b = nt.nodes['Principled BSDF']
    t = nt.nodes.new('ShaderNodeTexImage')
    # absolute paths: a relative image path breaks when the .blend is reopened elsewhere, and the
    # FBX exporter then silently embeds NO texture (verify_export shows images [])
    t.image = bpy.data.images.load(os.path.abspath(color_png), check_existing=True)
    nt.links.new(t.outputs['Color'], b.inputs['Base Color'])
    b.inputs['Roughness'].default_value = .15 if glow else .45
    if glow:
        nt.links.new(t.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = emission
    elif normal_png:
        ni = nt.nodes.new('ShaderNodeTexImage'); ni.image = bpy.data.images.load(os.path.abspath(normal_png), check_existing=True)
        ni.image.colorspace_settings.name = 'Non-Color'
        nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = .8
        nt.links.new(ni.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], b.inputs['Normal'])
    if emissive_png:
        ei = nt.nodes.new('ShaderNodeTexImage'); ei.image = bpy.data.images.load(os.path.abspath(emissive_png), check_existing=True)
        ei.image.colorspace_settings.name = 'sRGB'
        nt.links.new(ei.outputs['Color'], b.inputs['Emission Color']); b.inputs['Emission Strength'].default_value = emission
    return m


def build_object(acc, mat):
    """Mesh object with flat shading, atlas UVs, weights as vertex groups; merges doubles."""
    import bpy
    me = bpy.data.meshes.new(acc.name)
    me.from_pydata([tuple(v) for v in acc.v], [], [f[0] for f in acc.f]); me.update()
    uvl = me.uv_layers.new(name='UVMap')
    for poly, (idx, slot, uvs) in zip(me.polygons, acc.f):
        uvs = uvs or (stud_uvs(acc, idx, slot) if slot in ATLAS['studded'] else fill_uvs(acc, idx, slot))
        for li, uv in zip(poly.loop_indices, uvs): uvl.data[li].uv = uv
        poly.use_smooth = False
    me.materials.append(mat)
    ob = bpy.data.objects.new(acc.name, me); bpy.context.scene.collection.objects.link(ob)
    groups = {}
    for vi, wt in enumerate(acc.w):
        for bn, val in wt.items():
            if val > 0:
                groups.setdefault(bn, ob.vertex_groups.new(name=bn)).add([vi], val, 'REPLACE')
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.remove_doubles(threshold=1e-4); bpy.ops.object.mode_set(mode='OBJECT'); ob.select_set(False)
    return ob


def build_armature(name, bones, meshes):
    """bones: {name: (head, tail, parent|None)}. Parents meshes with an Armature modifier."""
    import bpy
    ad = bpy.data.armatures.new(name + 'Rig'); arm = bpy.data.objects.new(name, ad)
    bpy.context.scene.collection.objects.link(arm); bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for n, (h, t, p) in bones.items():
        eb = ad.edit_bones.new(n); eb.head, eb.tail, eb.roll = h, t, 0.0
    for n, (h, t, p) in bones.items():
        if p: ad.edit_bones[n].parent = ad.edit_bones[p]
    bpy.ops.object.mode_set(mode='OBJECT')
    for ob in meshes:
        ob.parent = arm; md = ob.modifiers.new('Armature', 'ARMATURE'); md.object = arm
    return arm
