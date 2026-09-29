# Lava Horse - geometry builder (Blender 5.x, run via bpy).
# Coordinates: Blender units, Z up, horse faces -Y (Blender "front"), its left side is +X.
# Every part is built in its own local frame so a per-part "StudUV" can be projected
# along the part's own axes (keeps painted studs square on rotated parts).
import bpy, bmesh, math, random
from mathutils import Vector, Matrix, Euler

STUD_TILE = 2.0          # world units covered by one 4x4 stud tile (stud pitch 0.5)

# Height: everything is authored at the original proportions, then legs are lengthened by LIFT.
# Vertices above LEG_TOP move up by LIFT, the lower-leg band [HOOF_TOP, LEG_TOP] is stretched,
# hooves stay on the ground. Rigid parts (rocks, head, mane, tail...) just translate.
LIFT = 1.0
HOOF_TOP, LEG_TOP = 0.9, 1.9


HEAD_SCALE = 1.18                      # head scaled about the neck joint
HEAD_PIVOT = Vector((0, -2.95, 5.0))


def remap_z(z):
    if z >= LEG_TOP:
        return z + LIFT
    if z <= HOOF_TOP:
        return z
    return HOOF_TOP + (z - HOOF_TOP) * (LEG_TOP - HOOF_TOP + LIFT) / (LEG_TOP - HOOF_TOP)

PARTS = []               # (obj, category, bone)


def clear_scene():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.armatures, bpy.data.actions, bpy.data.images):
        for d in list(coll):
            coll.remove(d)


def _hexa_bm(pts):
    """pts: 8 local corners, order: bottom (-x-y, +x-y, +x+y, -x+y) then top same order."""
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in pts]
    for f in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        bm.faces.new([v[i] for i in f])
    bm.normal_update()
    return bm


def box_pts(sx, sy, sz, top_scale=(1, 1), top_off=(0, 0)):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    tx, ty = hx * top_scale[0], hy * top_scale[1]
    ox, oy = top_off
    return [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
            (-tx + ox, -ty + oy, hz), (tx + ox, -ty + oy, hz), (tx + ox, ty + oy, hz), (-tx + ox, ty + oy, hz)]


def finish_part(name, bm, matrix, category, bone, chamfer=0.0, cuts=None, grad_axis=None,
                weights=None, rigid=True):
    """Chamfer, loop cuts, StudUV (local projection), rest/grad attributes, transform, link."""
    if cuts:
        # cuts: list of (axis_index, local_coordinate) planes
        for ax, c in cuts:
            no = [0, 0, 0]; no[ax] = 1
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=[c if i == ax else 0 for i in range(3)],
                                   plane_no=no)
    if chamfer > 0:
        sharp = [e for e in bm.edges if len(e.link_faces) == 2 and
                 e.link_faces[0].normal.angle(e.link_faces[1].normal) > math.radians(35)]
        bmesh.ops.bevel(bm, geom=sharp, offset=chamfer, segments=1, profile=0.5,
                        affect='EDGES', clamp_overlap=True)
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    uv0 = me.uv_layers.new(name='UVMap')
    uvs = me.uv_layers.new(name='StudUV')
    # local-axis projection per face; 'axisid' records which projection each face used
    axid = me.attributes.new('axisid', 'FLOAT', 'FACE')
    for p in me.polygons:
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        axid.data[p.index].value = ax * 2 + (1 if n[ax] >= 0 else 0)
        a, b = [(1, 2), (0, 2), (0, 1)][ax]
        # keep studs upright on side faces
        sign = 1 if n[ax] >= 0 else -1
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            u = co[a] * (sign if ax != 2 else 1)
            if ax == 0:
                u = co[1] * -sign
            if ax == 1:
                u = co[0] * sign
            uvs.data[li].uv = (u / STUD_TILE + 0.13, co[b] / STUD_TILE + 0.37)
    # gradient attribute along local axis (mane/tail base->tip)
    ga = me.attributes.new('grad', 'FLOAT', 'POINT')
    if grad_axis is not None:
        vals = [v.co[grad_axis] for v in me.vertices]
        lo, hi = min(vals), max(vals)
        for i, v in enumerate(me.vertices):
            ga.data[i].value = (v.co[grad_axis] - lo) / max(hi - lo, 1e-6)
    me.transform(matrix)
    me.update()
    pre = [v.co.copy() for v in me.vertices]        # authored coords (weights are defined on these)
    if rigid:
        cz = sum(c.z for c in pre) / len(pre)
        dz = remap_z(cz) - cz
        for v in me.vertices:
            v.co.z += dz
    else:
        for v in me.vertices:
            v.co.z = remap_z(v.co.z)
    me.update()
    rest = me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT')
    for i, v in enumerate(me.vertices):
        rest.data[i].vector = v.co
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    # weights: rigid to bone, or callable(authored_co) -> {bone: w}
    groups = {}
    for i, v in enumerate(me.vertices):
        w = weights(pre[i]) if weights else {bone: 1.0}
        for bname, val in w.items():
            if val <= 0:
                continue
            g = groups.get(bname) or ob.vertex_groups.new(name=bname)
            groups[bname] = g
            g.add([i], val, 'REPLACE')
    ob['category'] = category
    PARTS.append((ob, category, bone))
    return ob


def M(loc=(0, 0, 0), rot=(0, 0, 0), parent=None):
    m = Matrix.Translation(Vector(loc)) @ Euler([math.radians(r) for r in rot], 'XYZ').to_matrix().to_4x4()
    return parent @ m if parent is not None else m


def boxpart(name, center, size, category, bone, rot=(0, 0, 0), chamfer=0.06, parent=None,
            top_scale=(1, 1), top_off=(0, 0), cuts=None, weights=None, grad_axis=None, rigid=True):
    bm = _hexa_bm(box_pts(*size, top_scale=top_scale, top_off=top_off))
    return finish_part(name, bm, M(center, rot, parent), category, bone, chamfer, cuts,
                       grad_axis=grad_axis, weights=weights, rigid=rigid)


def lerp_w(a, b, t):
    t = max(0.0, min(1.0, t))
    return {a: 1 - t, b: t}


# ---------------------------------------------------------------- body parts
def build_body():
    # torso: lofted rounded-box (superellipse) sections - deep ribcage, slimmer waist, round rump
    #          y      half-width  half-height  centre-z
    secs = [(-2.8, 1.02, 0.8, 3.12), (-2.2, 1.3, 1.0, 2.98), (-1.0, 1.46, 1.1, 2.88),
            (0.2, 1.38, 0.98, 2.98), (1.1, 1.3, 0.86, 3.08), (2.2, 1.4, 0.97, 3.06),
            (3.0, 1.16, 0.84, 3.16), (3.38, 0.7, 0.5, 3.2)]
    N = 16
    bm = bmesh.new()
    rings = []
    for y, hw, hh, zc in secs:
        ring = []
        for k in range(N):
            a = 2 * math.pi * (k + 0.5) / N
            ca, sa = math.cos(a), math.sin(a)
            x = hw * math.copysign(abs(ca) ** 0.62, ca)         # rounded-box superellipse
            z = hh * math.copysign(abs(sa) ** 0.62, sa)
            if z < 0:
                z *= 0.92                                          # slightly flatter belly curve
            ring.append(bm.verts.new((x, y, zc + z)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(N):
            j = (k + 1) % N
            bm.faces.new([r0[k], r0[j], r1[j], r1[k]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    body = finish_part('Body', bm, Matrix(), 'lava', 'Torso', chamfer=0.0, rigid=False,
                       weights=lambda c: lerp_w('Chest', 'Hips', (c.y + 1.4) / 2.8))
    # smooth-shade the barrel (not the end caps) so it reads round instead of faceted
    for p in body.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    # neck / chest: slanted frustum from chest up to head
    pts = [(-1.18, -2.95, 2.25), (1.18, -2.95, 2.25), (1.18, -1.05, 3.65), (-1.18, -1.05, 3.65),
           (-0.8, -3.2, 5.05), (0.8, -3.2, 5.05), (0.8, -2.05, 5.45), (-0.8, -2.05, 5.45)]
    bm = _hexa_bm(pts)
    finish_part('Neck', bm, Matrix(), 'lava', 'Neck', chamfer=0.18, cuts=[(2, 4.0)], rigid=False,
                weights=lambda c: lerp_w('Chest', 'Neck', (c.z - 3.2) / 1.2))


def build_head():
    """Measured from the reference side/front/eye close-ups:
    - flat-topped cranium with a brow ledge overhanging deep-set eyes at its front corners,
    - long narrower snout sloping nose-down, dark maroon nose block on its front/bottom,
    - separate dark lower jaw whose underside rises back toward the throat,
    - tall dark pyramid ears on the back of the cranium."""
    hs = HEAD_SCALE
    Hs = Matrix.Translation(HEAD_PIVOT) @ Matrix.Diagonal((hs, hs, hs, 1)) @ Matrix.Translation(-HEAD_PIVOT)

    def hbox(*a, **k):
        return boxpart(*a, parent=Hs, **k)
    # main head: one long tapered wedge, forehead flowing into the snout, nose-down like the reference
    # (back section at the poll: 1.54 wide x 1.45 tall; nose section: 1.34 wide x 1.24 tall)
    head_pts = [(-0.77, -2.45, 4.4), (0.77, -2.45, 4.4), (0.67, -4.62, 3.86), (-0.67, -4.62, 3.86),
                (-0.77, -2.45, 5.85), (0.77, -2.45, 5.85), (0.67, -4.62, 5.1), (-0.67, -4.62, 5.1)]
    # _hexa_bm expects bottom (-x-y,+x-y,+x+y,-x+y) then top; reorder to that winding
    order = [3, 2, 1, 0, 7, 6, 5, 4]
    finish_part('Head', _hexa_bm([head_pts[k] for k in order]), Hs, 'lava', 'Head', chamfer=0.08)
    # brow ledge overhanging the deep-set eyes
    hbox('Brow', (0, -3.74, 5.43), (1.58, 0.58, 0.17), 'lava', 'Head', rot=(-10, 0, 0), chamfer=0.05)
    # dark nose block on the front/bottom of the snout
    hbox('Muzzle', (0, -4.6, 4.24), (1.28, 0.64, 0.84), 'muzzle', 'Head', rot=(-10, 0, 0), chamfer=0.07)
    # lower jaw, underside rising back toward the throat
    hbox('Jaw', (0, -3.95, 3.98), (1.04, 1.3, 0.42), 'muzzle', 'Head', rot=(12, 0, 0), chamfer=0.05)
    for s in (1, -1):
        sd = 'L' if s > 0 else 'R'
        # deep-set eye: white shows along the front and lower edges, black pupil behind/above it
        hbox('EyeWhite' + sd, (s * 0.67, -3.8, 5.0), (0.16, 0.56, 0.46), 'eye_white', 'Head',
                rot=(-10, 0, 0), chamfer=0.0)
        hbox('EyeBlack' + sd, (s * 0.69, -3.74, 5.04), (0.16, 0.46, 0.38), 'eye_black', 'Head',
                rot=(-10, 0, 0), chamfer=0.0)
        # ears: tall dark pyramids, leaning slightly back and out
        hbox('Ear' + sd, (s * 0.47, -3.0, 6.02), (0.52, 0.55, 0.95), 'rock', 'Ear.' + sd,
                rot=(8, s * 8, 0), chamfer=0.03, top_scale=(0.34, 0.36), top_off=(s * 0.02, 0.06))


def build_legs():
    for s, side in ((1, 'L'), (-1, 'R')):
        x = s * 1.15
        # front leg
        boxpart('FUpper' + side, (x, -1.9, 2.55), (1.2, 1.42, 1.7), 'lava', 'FrontUpper.' + side,
                chamfer=0.1, top_scale=(1.05, 1.08), rigid=False)
        boxpart('FLower' + side, (x, -1.9, 1.3), (1.1, 1.25, 1.15), 'lava', 'FrontLower.' + side,
                chamfer=0.09, rigid=False)
        boxpart('FHoof' + side, (x, -1.95, 0.43), (1.5, 1.72, 0.86), 'hoof', 'FrontHoof.' + side,
                chamfer=0.06, top_scale=(0.82, 0.76))
        # hind leg: thigh, angled cannon, hoof
        boxpart('HThigh' + side, (x, 2.55, 2.55), (1.25, 1.7, 1.8), 'lava', 'HindUpper.' + side,
                chamfer=0.12, rot=(-8, 0, 0), top_scale=(1.05, 1.1), rigid=False)
        boxpart('HLower' + side, (x, 2.8, 1.3), (1.1, 1.25, 1.2), 'lava', 'HindLower.' + side,
                chamfer=0.09, rot=(6, 0, 0), rigid=False)
        boxpart('HHoof' + side, (x, 2.88, 0.43), (1.5, 1.72, 0.86), 'hoof', 'HindHoof.' + side,
                chamfer=0.06, top_scale=(0.82, 0.76))


# ---------------------------------------------------------------- volcanic armour
def rock(name, c, size, bone, rng):
    rot = (rng.uniform(-35, 35), rng.uniform(-35, 35), rng.uniform(-40, 40))
    size *= 1.45
    sx = size * rng.uniform(0.85, 1.15); sy = size * rng.uniform(0.85, 1.2); sz = size * rng.uniform(0.75, 1.0)
    boxpart(name, c, (sx, sy, sz), 'rock', bone, rot=rot, chamfer=size * 0.13)


def build_armour():
    rng = random.Random(11)
    # hand-placed so the clusters read like the reference (shoulder boulder, hip boulder, rump ridge)
    shoulder = [  # (x_out, y, z, size, bone)
        (1.42, -2.35, 3.75, 0.82, 'Chest'), (1.5, -1.55, 3.65, 0.78, 'Chest'),
        (1.62, -2.1, 3.05, 0.9, 'Chest'), (1.55, -1.3, 2.95, 0.7, 'Chest'),
        (1.5, -2.75, 2.75, 0.62, 'FrontUpper'), (1.6, -1.95, 2.35, 0.72, 'FrontUpper'),
        (1.3, -2.9, 3.55, 0.55, 'Chest'), (1.12, -1.95, 4.1, 0.6, 'Chest'),
        (1.35, -1.0, 3.55, 0.5, 'Chest'),
    ]
    hip = [
        (1.45, 2.0, 3.7, 0.85, 'Hips'), (1.5, 2.85, 3.55, 0.8, 'Hips'),
        (1.62, 2.4, 2.9, 0.92, 'HindUpper'), (1.55, 1.55, 3.0, 0.7, 'Hips'),
        (1.55, 3.3, 2.75, 0.7, 'HindUpper'), (1.45, 2.7, 2.1, 0.68, 'HindUpper'),
        (1.2, 1.5, 4.05, 0.62, 'Hips'), (1.25, 3.25, 3.95, 0.55, 'Hips'),
        (1.5, 1.2, 2.35, 0.5, 'Hips'),
    ]
    ridge = [(0.35, 1.25, 4.25, 0.75), (-0.35, 1.3, 4.2, 0.72), (0.2, 2.05, 4.5, 0.78),
             (-0.25, 2.25, 4.45, 0.7), (0.0, 0.6, 4.0, 0.6), (0.3, 2.75, 4.25, 0.55),
             (-0.35, 2.8, 4.2, 0.55)]
    for s, side in ((1, 'L'), (-1, 'R')):
        for i, (x, y, z, sz, b) in enumerate(shoulder):
            bone = 'FrontUpper.' + side if b == 'FrontUpper' else b
            rock(f'RockS{side}{i}', (s * (x + 0.1), y, z + 0.2), sz, bone, rng)
        for i, (x, y, z, sz, b) in enumerate(hip):
            bone = 'HindUpper.' + side if b == 'HindUpper' else b
            rock(f'RockH{side}{i}', (s * (x + 0.15), y, z), sz, bone, rng)
    for i, (x, y, z, sz) in enumerate(ridge):
        rock(f'RockR{i}', (x, y, z), sz, 'Hips', rng)


# ---------------------------------------------------------------- flame mane / tail shards
def shard(name, base, direction_deg, length, width, thick, bone, roll=0.0, yaw=0.0, weights=None):
    """Flat stud-covered plate with an angled, pointed tip. Built along local +Z (grad axis)."""
    L, W, T = length, width * 1.3, thick * 1.8
    prof = [(-W / 2, 0), (W / 2, 0), (W / 2, L * 0.62), (W * 0.1, L), (-W / 2, L * 0.8)]
    bm = bmesh.new()
    front = [bm.verts.new((T / 2, x, z)) for x, z in prof]
    back = [bm.verts.new((-T / 2, x, z)) for x, z in prof]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    n = len(prof)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new([front[j], front[i], back[i], back[j]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    # direction_deg: angle in the YZ plane measured from +Y (backwards) toward +Z (up)
    rot_x = -(90 - direction_deg)          # local +Z -> rotate about X
    # roll = outward splay (about the plate's width axis), yaw = turn about world Z
    m = M(base, (0, 0, 0)) @ Matrix.Rotation(math.radians(yaw), 4, 'Z') @ \
        Matrix.Rotation(math.radians(rot_x), 4, 'X') @ Matrix.Rotation(math.radians(roll), 4, 'Y')
    return finish_part(name, bm, m, 'flame', bone, chamfer=0.0, grad_axis=2, weights=weights)


def build_mane():
    # stations along the crest of head+neck: (y, z, dir_deg, length)
    st = [(-2.75, 5.95, 72, 1.2), (-2.45, 5.72, 58, 1.45), (-2.15, 5.45, 50, 1.6), (-1.85, 5.15, 44, 1.65),
          (-1.55, 4.85, 39, 1.6), (-1.25, 4.55, 35, 1.5), (-0.95, 4.25, 31, 1.4), (-0.65, 4.0, 27, 1.2),
          (-0.35, 3.85, 24, 1.0)]
    k = 0
    for i, (y, z, d, L) in enumerate(st):
        bone = 'Head' if y < -3.0 else ('Neck' if y < -1.0 else 'Chest')
        shard(f'Mane{k}', (0, y, z), d, L, 0.78, 0.16, bone); k += 1
        for s in (1, -1):
            shard(f'Mane{k}', (s * 0.34, y + 0.18, z - 0.12), d - 8, L * 0.85, 0.6, 0.15, bone,
                  roll=s * 26, yaw=s * 10); k += 1
            if 2 <= i <= 7:
                shard(f'Mane{k}', (s * 0.6, y + 0.3, z - 0.35), d - 15, L * 0.72, 0.55, 0.14, bone,
                      roll=s * 48, yaw=s * 22); k += 1
    # forelock crest between the ears
    for s in (0.18, -0.18):
        shard(f'Mane{k}', (s, -3.2, 5.75), 96, 0.8, 0.42, 0.14, 'Head', roll=s * 60); k += 1


def build_tail():
    # fan of layered flame plates radiating from the tail root (matches the reference side silhouette:
    # tall flare behind the rump, long pointed tip sweeping back and down)
    root = Vector((0, 2.9, 3.85))
    rays = [(72, 1.8), (50, 2.5), (28, 2.9), (6, 3.1), (-16, 3.3), (-36, 3.6), (-50, 3.9), (-66, 2.3)]
    k = 0

    def tw(c):
        return lerp_w('Tail1', 'Tail2', (c.y - 3.3) / 1.8)
    for ri, (d, total) in enumerate(rays):
        dv = Vector((0, math.cos(math.radians(d)), math.sin(math.radians(d))))
        seg = 1.7
        n = max(1, round(total / 1.25))
        for si in range(n):
            off = 0 if n == 1 else (total - seg) * si / (n - 1)
            L = seg if not (si == n - 1 and ri == 6) else seg * 1.25
            W = 0.8 if si < n - 1 else 0.62
            for s in (1, -1):
                base = root + dv * off + Vector((s * 0.32 * (1 - 0.5 * off / total), 0, 0))
                shard(f'Tail{k}', tuple(base), d + (4 if s > 0 else -4), L, W, 0.16, 'Tail1',
                      roll=s * (14 + 3 * si), weights=tw); k += 1
            if si == 0 and ri % 2 == 0 or si == n - 1:
                shard(f'Tail{k}', tuple(root + dv * (off + 0.2)), d, L, W * 0.9, 0.16, 'Tail1', roll=(10 if ri % 2 else -10), weights=tw); k += 1


def build_all():
    clear_scene()
    PARTS.clear()
    build_body(); build_head(); build_legs(); build_armour(); build_mane(); build_tail()
    return PARTS
