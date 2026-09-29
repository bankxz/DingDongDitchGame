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


HEAD_SCALE = 1.0                       # head authored 1:1 in reference-sheet units
HEAD_PIVOT = Vector((0, -2.95, 5.0))


def remap_z(z):
    if z >= LEG_TOP:
        return z + LIFT
    if z <= HOOF_TOP:
        return z
    return HOOF_TOP + (z - HOOF_TOP) * (LEG_TOP - HOOF_TOP + LIFT) / (LEG_TOP - HOOF_TOP)

PARTS = []               # (obj, category, bone)
TREES = {}               # part name -> (category, authored-space face planes [(point, normal)])


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


def _stud_uv(me, co):
    """StudUV: per-face projection along the part's local axes (world units / STUD_TILE), from the
    local-space vertex coords `co`. 'axisid' records which projection each face used."""
    uvs = me.uv_layers['StudUV']
    axid = me.attributes.get('axisid') or me.attributes.new('axisid', 'FLOAT', 'FACE')
    for p in me.polygons:
        vs = [co[i] for i in p.vertices]
        n = (vs[1] - vs[0]).cross(vs[2] - vs[0]).normalized() if len(vs) >= 3 else p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        axid.data[p.index].value = ax * 2 + (1 if n[ax] >= 0 else 0)
        b = [2, 2, 1][ax]
        sign = 1 if n[ax] >= 0 else -1          # keep studs upright on side faces
        for li in p.loop_indices:
            c = co[me.loops[li].vertex_index]
            u = c[1] * -sign if ax == 0 else (c[0] * sign if ax == 1 else c[0])
            uvs.data[li].uv = (u / STUD_TILE + 0.13, c[b] / STUD_TILE + 0.37)


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
    _stud_uv(me, [v.co.copy() for v in me.vertices])
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
    TREES[name] = (category, _planes(pre, me))
    if rigid:
        cz = sum(c.z for c in pre) / len(pre)
        # parts hanging off the torso (mane/tail plates, armour) move exactly with it
        dz = LIFT if category in ('flame', 'rock') and bone not in ('Ear.L', 'Ear.R') else remap_z(cz) - cz
        for v in me.vertices:
            v.co.z += dz
    else:
        for v in me.vertices:
            v.co.z = remap_z(v.co.z)
        # the leg band was stretched: redo the stud projection on the stretched shape (in the part's
        # local frame) so studs stay square instead of being pulled tall on the legs
        inv = matrix.inverted()
        _stud_uv(me, [inv @ v.co for v in me.vertices])
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
    # torso: bevelled rounded box, measured from the reference side view:
    # straight back line ~z3.88, straight belly ~z2.02, flat studded side panels, bevelled corners,
    # chest and rump ends slightly narrowed and rounded.
    def rrect(hw, hh, r, seg=2):
        pts = []
        for cx, cz, a0 in ((hw - r, hh - r, 0), (-(hw - r), hh - r, 90), (-(hw - r), -(hh - r), 180),
                           (hw - r, -(hh - r), 270)):
            for k in range(seg + 1):
                a = math.radians(a0 + 90 * k / seg)
                pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
        return pts
    #          y      half-w  half-h  corner-r  centre-z
    secs = [(-2.95, 1.05, 0.72, 0.36, 3.02), (-2.55, 1.3, 0.9, 0.42, 2.96), (2.55, 1.36, 0.93, 0.42, 2.96),
            (3.12, 1.2, 0.84, 0.42, 3.0), (3.42, 0.8, 0.58, 0.3, 3.04)]
    bm = bmesh.new()
    rings = []
    for y, hw, hh, r, zc in secs:
        rings.append([bm.verts.new((x, y, zc + z)) for x, z in rrect(hw, hh, r)])
    N = len(rings[0])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(N):
            j2 = (k + 1) % N
            bm.faces.new([r0[k], r0[j2], r1[j2], r1[k]])
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    finish_part('Body', bm, Matrix(), 'lava', 'Torso', chamfer=0.0, rigid=False,
                weights=lambda c: lerp_w('Chest', 'Hips', (c.y + 1.4) / 2.8))
    # neck / chest: slanted frustum from chest up to head
    # neck: near-vertical front edge from the throat (y-3.0,z4.4) to the chest; back edge runs from
    # behind the head (y-2.4,z5.4) down to the withers (y-1.0,z3.7)
    pts = [(-1.12, -2.9, 2.25), (1.12, -2.9, 2.25), (1.12, -1.0, 3.7), (-1.12, -1.0, 3.7),
           (-0.74, -3.08, 4.55), (0.74, -3.08, 4.55), (0.74, -2.35, 5.45), (-0.74, -2.35, 5.45)]
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
    # cranium (forehead block): eyes sit in its front corners, top ~z5.6-5.7, back at y-2.55
    cran = [(-0.7, -4.12, 4.42), (0.7, -4.12, 4.42), (0.76, -2.55, 4.4), (-0.76, -2.55, 4.4),
            (-0.7, -4.12, 5.58), (0.7, -4.12, 5.58), (0.76, -2.55, 5.72), (-0.76, -2.55, 5.72)]
    finish_part('Cranium', _hexa_bm(cran), Hs, 'lava', 'Head', chamfer=0.07)
    # dark plate across the back of the head where it meets the neck
    hbox('HeadBack', (0, -2.72, 5.1), (1.56, 0.34, 1.22), 'muzzle', 'Head', chamfer=0.05)
    # snout: lower than the forehead; top rises from z4.8 at the nose to z5.05 at the eye
    snout = [(-0.6, -4.62, 4.02), (0.6, -4.62, 4.02), (0.64, -3.85, 4.12), (-0.64, -3.85, 4.12),
             (-0.6, -4.62, 4.8), (0.6, -4.62, 4.8), (0.64, -3.85, 5.06), (-0.64, -3.85, 5.06)]
    finish_part('Snout', _hexa_bm(snout), Hs, 'lava', 'Head', chamfer=0.06)
    # dark maroon nose block: front face at y-4.98, z3.9..4.7 (red snout top shows above it)
    nose = [(-0.58, -4.98, 3.9), (0.58, -4.98, 3.9), (0.6, -4.5, 3.96), (-0.6, -4.5, 3.96),
            (-0.58, -4.98, 4.7), (0.58, -4.98, 4.7), (0.6, -4.5, 4.76), (-0.6, -4.5, 4.76)]
    finish_part('Muzzle', _hexa_bm(nose), Hs, 'muzzle', 'Head', chamfer=0.06)
    # lower jaw: chin (y-4.58,z3.83) rising back to the throat (y-3.1,z4.38)
    jaw = [(-0.52, -4.66, 3.83), (0.52, -4.66, 3.83), (0.56, -3.1, 4.34), (-0.56, -3.1, 4.34),
           (-0.52, -4.66, 4.2), (0.52, -4.66, 4.2), (0.56, -3.1, 4.7), (-0.56, -3.1, 4.7)]
    finish_part('Jaw', _hexa_bm(jaw), Hs, 'muzzle', 'Head', chamfer=0.05)
    for s in (1, -1):
        sd = 'L' if s > 0 else 'R'
        # eye in the forehead's front corner: black pupil, white rim along its back and bottom edges
        # Flush corner patches (no protrusion): the black pupil hugs the forehead's front-side corner
        # 0.005-0.01 proud of the surface, the white rim sits just behind it and shows as a thin
        # L along the back+bottom edges from the side and the inner+bottom edges from the front.
        def eye_box(name, x0, x1, y0, y1, z0, z1, cat):
            hbox(name + sd, (s * (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
                 (x1 - x0, y1 - y0, z1 - z0), cat, 'Head', chamfer=0.0)
        eye_box('EyeWhite', 0.41, 0.715, -4.126, -3.66, 4.85, 5.34, 'eye_white')
        eye_box('EyeBlack', 0.53, 0.722, -4.132, -3.79, 4.95, 5.3, 'eye_black')
        # ears: dark pyramids, base y-3.6..-3.0 at z5.65, tip ~(y-3.4, z6.45)
        hbox('Ear' + sd, (s * 0.45, -3.3, 6.02), (0.46, 0.6, 0.82), 'rock', 'Ear.' + sd,
             rot=(0, s * 6, 0), chamfer=0.03, top_scale=(0.3, 0.3), top_off=(s * 0.02, -0.08))


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
    size *= 1.25
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
        (1.38, 1.2, 2.4, 0.5, 'Hips'),
    ]
    ridge = [(0.35, 1.25, 4.25, 0.75), (-0.35, 1.3, 4.2, 0.72), (0.2, 2.05, 4.5, 0.78),
             (-0.25, 2.25, 4.45, 0.7), (0.0, 0.6, 4.0, 0.6), (0.3, 2.75, 4.25, 0.55),
             (-0.35, 2.8, 4.2, 0.55)]
    for s, side in ((1, 'L'), (-1, 'R')):
        for i, (x, y, z, sz, b) in enumerate(shoulder):
            bone = 'FrontUpper.' + side if b == 'FrontUpper' else b
            rock(f'RockS{side}{i}', (s * (x + 0.1), y + 0.2, z - 0.35), sz, bone, rng)
        for i, (x, y, z, sz, b) in enumerate(hip):
            bone = 'HindUpper.' + side if b == 'HindUpper' else b
            rock(f'RockH{side}{i}', (s * (x + 0.15), y, z), sz, bone, rng)
    for i, (x, y, z, sz) in enumerate(ridge):
        rock(f'RockR{i}', (x, y, z), sz, 'Hips', rng)


# ---------------------------------------------------------------- flame mane / tail shards
def _planes(co, me):
    """Face planes (point, outward normal) of a convex part from vertex coords `co`."""
    out = []
    for p in me.polygons:
        vs = [co[i] for i in p.vertices]
        n = (vs[1] - vs[0]).cross(vs[2] - vs[0])
        if n.length < 1e-9:
            continue
        out.append((vs[0], n.normalized()))
    return out


def _depth(planes, p):
    """Signed depth of p inside a convex part (positive = inside, distance to nearest face)."""
    return min(-(p - c).dot(n) for c, n in planes)


ROOT_DEPTH = 0.15       # every mane/tail plate's base is buried at least this deep in what it grows from


def _embed_depth(p):
    """How deep point p sits inside any finished (non-eye) part; -1 when it is in open air."""
    best = -1.0
    for cat, planes in TREES.values():
        if cat in ('eye_white', 'eye_black'):
            continue
        d = _depth(planes, p)
        if d > 0:
            best = max(best, d)
    return best


def shard(name, base, direction_deg, length, width, thick, bone, roll=0.0, yaw=0.0, weights=None):
    """Flat stud-covered plate with an angled, pointed tip. Built along local +Z (grad axis).
    The plate is rooted: its base is slid back along its own axis (tip fixed, plate lengthened)
    until it is buried ROOT_DEPTH inside the body/neck/head/rocks or an earlier plate, so no piece
    of the mane or tail floats."""
    rot_x = -(90 - direction_deg)
    R = Matrix.Rotation(math.radians(yaw), 4, 'Z') @ Matrix.Rotation(math.radians(rot_x), 4, 'X') @ \
        Matrix.Rotation(math.radians(roll), 4, 'Y')
    axis = (R.to_3x3() @ Vector((0, 0, 1))).normalized()
    base = Vector(base)
    ext = 0.0
    if _embed_depth(base) < ROOT_DEPTH:
        for k in range(1, 81):                      # search up to 3.2 units back along the plate
            p = base - axis * (0.04 * k)
            if _embed_depth(p) >= ROOT_DEPTH:
                ext = 0.04 * k
                break
        else:                                       # fallback: slide the plate onto the nearest part
            from mathutils.bvhtree import BVHTree   # (only spots that really end up buried count)
            best = None
            for o, cat, _ in PARTS:
                if cat in ('eye_white', 'eye_black'):
                    continue
                co = [v.co for v in o.data.vertices]
                loc, nrm, _, dist = BVHTree.FromPolygons(co, [tuple(q.vertices) for q in o.data.polygons]) \
                    .find_nearest(base + Vector((0, 0, LIFT)))
                if loc is None:
                    continue
                for d in (ROOT_DEPTH, 0.12, 0.1):
                    cand = loc - nrm * d - Vector((0, 0, LIFT))
                    if _embed_depth(cand) >= 0.1 and (best is None or dist < best[0]):
                        best = (dist, cand)
                        break
            base = best[1]
    base = base - axis * ext
    L, W, T = length + ext, width * 1.3, thick * 1.8
    tipL = length                                   # keep the visible tip shape unchanged
    prof = [(-W / 2, 0), (W / 2, 0), (W / 2, L - tipL * 0.38), (W * 0.1, L), (-W / 2, L - tipL * 0.2)]
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
    # direction_deg: angle in the YZ plane from +Y (backwards) toward +Z (up); roll = outward splay
    # (about the plate's width axis); yaw = turn about world Z
    m = Matrix.Translation(base) @ R
    ob = finish_part(name, bm, m, 'flame', bone, chamfer=0.0, grad_axis=2, weights=weights)
    # re-map the flame gradient so the colour ramp runs over the visible length only
    g = ob.data.attributes['grad'].data
    if ext > 0:
        f = ext / L
        for d in g:
            d.value = max(0.0, (d.value - f) / (1 - f))
    return ob


def build_mane():
    # stations along the crest of head+neck: (y, z, dir_deg, length)
    st = [(-2.42, 5.9, 70, 1.3), (-2.2, 5.66, 58, 1.5), (-2.0, 5.42, 50, 1.6), (-1.8, 5.15, 44, 1.65),
          (-1.55, 4.85, 39, 1.6), (-1.25, 4.55, 35, 1.5), (-0.95, 4.25, 31, 1.4), (-0.65, 4.0, 27, 1.2),
          (-0.35, 3.85, 24, 1.0)]
    k = 0
    def crest_z(y):   # top-back edge of the neck (y-2.35,z5.45)->(y-1.0,z3.7), then the back line
        return max(5.45 - (y + 2.35) / 1.35 * 1.75, 3.8) - 0.06
    for i, (y, z, d, L) in enumerate(st):
        z = min(z, crest_z(y)) if y > -2.35 else z
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
    TREES.clear()
    build_body(); build_head(); build_legs(); build_armour(); build_mane(); build_tail()
    return PARTS


# ---------------------------------------------------------------- connectivity gate


def floating_parts(parts, anchor='Body'):
    """Return names of parts not connected (by surface overlap or containment, possibly through a
    chain of other parts) to the anchor part. Every mane/tail plate must reach the body."""
    from mathutils.bvhtree import BVHTree
    objs = [p[0] for p in parts]
    trees, verts, planes = {}, {}, {}
    for o in objs:
        me = o.data
        vs = [v.co.copy() for v in me.vertices]
        trees[o.name] = BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in me.polygons])
        verts[o.name] = vs
        planes[o.name] = _planes(vs, me)
    names = [o.name for o in objs]
    adj = {n: set() for n in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ta, tb = trees[a], trees[b]
            touch = bool(ta.overlap(tb)) or any(_depth(planes[b], v) > 0 for v in verts[a]) \
                or any(_depth(planes[a], v) > 0 for v in verts[b])
            if touch:
                adj[a].add(b); adj[b].add(a)
    seen, stack = {anchor}, [anchor]
    while stack:
        n = stack.pop()
        for m in adj[n] - seen:
            seen.add(m); stack.append(m)
    return sorted(set(names) - seen)


def unrooted_flames(parts, depth=0.08):
    """Stricter gate for mane/tail plates: the centre of each plate's base edge (grad == 0) must be
    buried at least `depth` inside the body/neck/head/rocks or inside another plate."""
    trees = {}
    for o, cat, _ in parts:
        trees[o.name] = (cat, _planes([v.co.copy() for v in o.data.vertices], o.data))
    bad = []
    for o, cat, _ in parts:
        if cat != 'flame':
            continue
        g = o.data.attributes['grad'].data
        base = [o.data.vertices[i].co for i in range(len(g)) if g[i].value < 1e-4]
        c = sum(base, Vector()) / len(base)
        best = -1.0
        for name, (ocat, pl) in trees.items():
            if name == o.name or ocat in ('eye_white', 'eye_black'):
                continue
            best = max(best, _depth(pl, c))
        if best < depth:
            bad.append((o.name, round(best, 3)))
    return bad


def weak_rocks(parts, depth=0.1):
    """Armour rocks must sink at least `depth` into the body/legs or a neighbouring rock."""
    pl = {o.name: (c, _planes([v.co.copy() for v in o.data.vertices], o.data)) for o, c, _ in parts}
    weak = []
    for o, c, _ in parts:
        if c != 'rock' or o.name.startswith('Ear'):
            continue
        best = max(_depth(p2, v.co) for n, (c2, p2) in pl.items()
                   if n != o.name and c2 not in ('eye_white', 'eye_black') for v in o.data.vertices)
        if best < depth:
            weak.append((o.name, round(best, 3)))
    return weak


def validate_attachment(parts):
    """Hard gate: nothing floats. Raises before any bake/export if a piece is detached."""
    fl, ur, wr = floating_parts(parts), unrooted_flames(parts, 0.1), weak_rocks(parts)
    print('ATTACH floating=%d unrooted_flames=%d weak_rocks=%d' % (len(fl), len(ur), len(wr)))
    if fl or ur or wr:
        raise RuntimeError(f'detached parts: floating={fl} unrooted={ur} weak_rocks={wr}')


# ---------------------------------------------------------------- hidden-face culling
def _bone_group(bone):
    """Parts in the same group move together in every animation, so a face buried in one stays
    buried. Legs, ears and the tail articulate separately and keep their own groups."""
    if bone in ('Chest', 'Hips', 'Torso', 'Neck'):
        return 'trunk'
    if bone in ('Tail1', 'Tail2'):
        return 'tail'
    return bone


def cull_hidden_faces(parts, margin=0.04):
    """Delete faces that are completely enclosed (every vertex and the face centre at least
    `margin` deep) by another convex part of the same bone group. Invisible from any angle and in
    any pose, so the silhouette/texture are unchanged; returns the number of triangles removed."""
    info = []
    for o, cat, bone in parts:
        vs = [v.co.copy() for v in o.data.vertices]
        info.append((o, cat, _bone_group(bone), _planes(vs, o.data),
                     Vector([min(c[i] for c in vs) for i in range(3)]),
                     Vector([max(c[i] for c in vs) for i in range(3)])))
    removed = 0
    for o, cat, grp, _, _, _ in info:
        if cat in ('eye_white', 'eye_black'):
            continue
        me = o.data
        hosts = [(pl, lo, hi) for o2, c2, g2, pl, lo, hi in info
                 if o2 is not o and g2 == grp and c2 not in ('eye_white', 'eye_black')]
        bm = bmesh.new(); bm.from_mesh(me)
        doomed = []
        for f in bm.faces:
            # dense samples over the face (fan-triangulated barycentric grid, corners included);
            # the face goes only if EVERY sample is buried >= margin in some same-group part
            vs = [v.co for v in f.verts]
            pts = []
            n = 5
            for k in range(1, len(vs) - 1):
                a, b, c = vs[0], vs[k], vs[k + 1]
                for i in range(n + 1):
                    for j in range(n + 1 - i):
                        u, v = i / n, j / n
                        pts.append(a + (b - a) * u + (c - a) * v)
            ok = True
            for p in pts:
                if not any(lo.x - margin <= p.x <= hi.x + margin and lo.y - margin <= p.y <= hi.y + margin
                           and lo.z - margin <= p.z <= hi.z + margin and _depth(pl, p) >= margin
                           for pl, lo, hi in hosts):
                    ok = False
                    break
            if ok:
                doomed.append(f)
        if doomed:
            removed += sum(len(f.verts) - 2 for f in doomed)
            bmesh.ops.delete(bm, geom=doomed, context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            bm.to_mesh(me); me.update()
        bm.free()
    return removed
