"""Build the red stud-textured T-rex in Blender (rigged + idle/walk actions).

Run with the bpy module (Blender 4.2):  python3 build_trex.py <out_dir>

Modelling units: 1 Blender unit = 1 stud cell of the texture.
Axes: -Y is the front (head), +X is the rex's left side, Z is up.
At the very end the rig is scaled to metres (1 stud = 0.28 m) so Roblox's
3D importer brings it in at the intended stud size.
"""
import math
import os
import random
import sys

import bpy  # noqa: I001  (bpy must be imported before bmesh)
import bmesh
from mathutils import Euler, Matrix, Vector

OUT = sys.argv[-1] if len(sys.argv) > 1 else os.getcwd()
TEX_DIR = os.path.join(OUT, 'textures')
STUD_TO_M = 0.28

TILES = ['BONE', 'BONE_LIGHT', 'CHARCOAL', 'MAROON', 'MIX', 'DARK', 'MOUTH', 'TONGUE',
         'TEETH', 'EYE', 'LAVA', 'BONE_DARK', 'PUPIL']
TILES_PER_ROW = 4
STUDS_PER_TILE = 8
ATLAS_STUDS = STUDS_PER_TILE * TILES_PER_ROW

rng = random.Random(1234)
PARTS = []   # (verts, faces, per-face uvs, per-vertex {bone: weight}, smooth)


# --------------------------------------------------------------------------- geometry helpers

def tile_origin(tile):
    i = TILES.index(tile)
    col, row = i % TILES_PER_ROW, i // TILES_PER_ROW
    return col * STUDS_PER_TILE, (TILES_PER_ROW - 1 - row) * STUDS_PER_TILE


def quad_uv(tile, a, b):
    """UVs for a quad of a x b studs placed inside a tile (studs stay 1:1 up to 8)."""
    tu, tv = tile_origin(tile)
    ka = min(1.0, (STUDS_PER_TILE - 0.1) / max(a, 1e-4))
    kb = min(1.0, (STUDS_PER_TILE - 0.1) / max(b, 1e-4))
    ox = rng.randint(0, max(0, int(STUDS_PER_TILE - a * ka - 0.05)))
    oy = rng.randint(0, max(0, int(STUDS_PER_TILE - b * kb - 0.05)))
    u0, v0 = tu + ox + 0.02, tv + oy + 0.02
    u1, v1 = u0 + a * ka - 0.04, v0 + b * kb - 0.04
    s = 1.0 / ATLAS_STUDS
    return [(u0 * s, v0 * s), (u1 * s, v0 * s), (u1 * s, v1 * s), (u0 * s, v1 * s)]


def xform(points, center, rot, pivot=None, pivot_rot=None):
    m = Euler([math.radians(r) for r in rot], 'XYZ').to_matrix()
    out = [m @ Vector(p) + Vector(center) for p in points]
    if pivot is not None:
        pm = Euler([math.radians(r) for r in pivot_rot], 'XYZ').to_matrix()
        out = [pm @ (p - Vector(pivot)) + Vector(pivot) for p in out]
    return out


def box(center, size, tile, bone, rot=(0, 0, 0), side_tile=None, bottom_tile=None, **kw):
    eps = 0.006 * (len(PARTS) % 17 + 1)
    sx, sy, sz = (s / 2 + eps for s in size)
    corners = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz), (-sx, sy, -sz),
               (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    verts = xform(corners, center, rot, kw.get('pivot'), kw.get('pivot_rot'))
    faces = [
        ((4, 5, 6, 7), size[0], size[1], tile),                       # top
        ((3, 2, 1, 0), size[0], size[1], bottom_tile or side_tile or tile),  # bottom
        ((0, 1, 5, 4), size[0], size[2], side_tile or tile),          # front (-Y)
        ((2, 3, 7, 6), size[0], size[2], side_tile or tile),          # back (+Y)
        ((1, 2, 6, 5), size[1], size[2], side_tile or tile),          # +X
        ((3, 0, 4, 7), size[1], size[2], side_tile or tile),          # -X
    ]
    fl, uvl = [], []
    for idx, a, b, t in faces:
        fl.append(idx)
        uvl.append(quad_uv(t, a, b))
    PARTS.append((verts, fl, uvl, [{bone: 1}] * len(verts), False))


def spike(base_center, base_size, tip, tile, bone, rot=(0, 0, 0), **kw):
    """Four-sided pyramid (teeth, claws, spike tips). tip is relative to base centre."""
    w, d = base_size[0] / 2, base_size[1] / 2
    pts = [(-w, -d, 0), (w, -d, 0), (w, d, 0), (-w, d, 0), tuple(tip)]
    verts = xform(pts, base_center, rot, kw.get('pivot'), kw.get('pivot_rot'))
    faces = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (3, 2, 1, 0)]
    tu, tv = tile_origin(tile)
    s = 1.0 / ATLAS_STUDS
    tri = [((tu + 1) * s, (tv + 1) * s), ((tu + 3) * s, (tv + 1) * s), ((tu + 2) * s, (tv + 4) * s)]
    uvs = [tri, tri, tri, tri, quad_uv(tile, base_size[0], base_size[1])]
    PARTS.append((verts, faces, uvs, [{bone: 1}] * len(verts), False))


def mirror_x(fn, center, *a, bone='', rot=(0, 0, 0), **kw):
    """Create a part on the left (+X, .L bone) and its mirror on the right (-X, .R bone)."""
    for sgn, suf in ((1, '.L'), (-1, '.R')):
        c = (center[0] * sgn, center[1], center[2])
        r = (rot[0], rot[1] * sgn, rot[2] * sgn)
        b = bone + suf if bone.endswith(('Thigh', 'Shin', 'Foot', 'UpperArm', 'Forearm', 'Hand')) else bone
        extra = dict(kw)
        if 'tip' in extra:
            t = extra['tip']
            extra['tip'] = (t[0] * sgn, t[1], t[2])
        if 'pivot' in extra:
            p = extra['pivot']
            extra['pivot'] = (p[0] * sgn, p[1], p[2])
        fn(c, *a, bone=b, rot=r, **extra)


def mbox(center, size, tile, bone, rot=(0, 0, 0), **kw):
    mirror_x(box, center, size, tile, bone=bone, rot=rot, **kw)


def mspike(center, base, tip, tile, bone, rot=(0, 0, 0), **kw):
    mirror_x(spike, center, base, tile=tile, bone=bone, rot=rot, tip=tip, **kw)


# --------------------------------------------------------------------------- smooth lofted shapes

def section(n, p=2.6):
    """Unit rounded-rectangle (squircle) cross-section with n points; p=2 is an ellipse,
    larger p is boxier. Returns (x, z) pairs in [-0.5, 0.5]."""
    pts = []
    for k in range(n):
        t = 2 * math.pi * (k + 0.5) / n
        c, s_ = math.cos(t), math.sin(t)
        pts.append((0.5 * math.copysign(abs(c) ** (2 / p), c), 0.5 * math.copysign(abs(s_) ** (2 / p), s_)))
    return pts


def cap_uv(tile, pts2d):
    """Planar UVs for an end cap, kept at stud scale inside the tile."""
    xs_, ys_ = [p[0] for p in pts2d], [p[1] for p in pts2d]
    w, h = max(xs_) - min(xs_), max(ys_) - min(ys_)
    k = min(1.0, (STUDS_PER_TILE - 0.2) / max(w, h, 1e-4))
    tu, tv = tile_origin(tile)
    s = 1.0 / ATLAS_STUDS
    return [((tu + 0.1 + (x - min(xs_)) * k) * s, (tv + 0.1 + (y - min(ys_)) * k) * s) for x, y in pts2d]


def loft(path, sizes, tile, weights, sides=8, p=2.6, up=(0, 0, 1), caps=(True, True),
         pivot=None, pivot_rot=None, smooth=True, cap_tile=None, seg_tiles=None):
    """Sweep a rounded cross-section along a polyline.

    path    : list of centre points
    sizes   : list of (width, height) per ring; width runs along the 'side' axis
    weights : list of {bone: weight} per ring (blends at joints = smooth bending)
    seg_tiles: optional tile per segment between rings (one mesh, several materials-in-atlas)
    up      : hint for the section's height axis
    """
    path = [Vector(c) for c in path]
    sec = section(sides, p)
    rings = []
    for i, c in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        v = Vector(up) - Vector(up).dot(t) * t
        if v.length < 1e-4:
            v = Vector((0, 1, 0)) - Vector((0, 1, 0)).dot(t) * t
        v.normalize()
        u = t.cross(v).normalized()
        w, h = sizes[i]
        rings.append([c + u * (x * w) + v * (z * h) for x, z in sec])
    verts = [q for r in rings for q in r]
    if pivot is not None:
        pm = Euler([math.radians(r) for r in pivot_rot], 'XYZ').to_matrix()
        verts = [pm @ (q - Vector(pivot)) + Vector(pivot) for q in verts]
    vw = [weights[i] for i in range(len(rings)) for _ in range(sides)]
    faces, uvs = [], []
    for i in range(len(rings) - 1):
        for k in range(sides):
            a, b = i * sides + k, i * sides + (k + 1) % sides
            c, d = b + sides, a + sides
            ea = (verts[b] - verts[a]).length
            eb = ((verts[d] - verts[a]).length + (verts[c] - verts[b]).length) / 2
            faces.append((a, b, c, d))
            uvs.append(quad_uv(seg_tiles[i] if seg_tiles else tile, ea, eb))
    for end, on in ((0, caps[0]), (len(rings) - 1, caps[1])):
        if not on:
            continue
        idx = [end * sides + k for k in range(sides)]
        if end == 0:
            idx = idx[::-1]
        w, h = sizes[end]
        faces.append(tuple(idx))
        pts = [sec[i % sides] for i in (range(sides) if end else range(sides - 1, -1, -1))]
        uvs.append(cap_uv(cap_tile or tile, [(x * w, z * h) for x, z in pts]))
    PARTS.append((verts, faces, uvs, vw, smooth))


def mloft(path, sizes, tile, weights, **kw):
    """Mirrored loft: path given for the left side (+X); bones ending in .L/.R get swapped."""
    for sgn, suf in ((1, 'L'), (-1, 'R')):
        pth = [(c[0] * sgn, c[1], c[2]) for c in path]
        wts = [{(b + suf if b.endswith('.') else b): v for b, v in w.items()} for w in weights]
        kw2 = dict(kw)
        if 'up' in kw2:
            kw2['up'] = (kw2['up'][0] * sgn, kw2['up'][1], kw2['up'][2])
        loft(pth, sizes, tile, wts, **kw2)


def horn(base, top, bw, bd, tw, td, tile, bone, sides=4, p=6.0, **kw):
    """Tapered plate / horn / spike: rounded frustum from base to top (width along X)."""
    loft([base, top], [(bw, bd), (tw, td)], tile, [{bone: 1}, {bone: 1}], sides=sides, p=p,
         up=(0, 1, 0), **kw)


def mhorn(base, top, bw, bd, tw, td, tile, bone, **kw):
    for sgn, suf in ((1, '.L'), (-1, '.R')):
        b = bone + suf if bone.endswith(('Thigh', 'Shin', 'Foot', 'UpperArm', 'Forearm', 'Hand')) else bone
        horn((base[0] * sgn, base[1], base[2]), (top[0] * sgn, top[1], top[2]), bw, bd, tw, td, tile, b, **kw)


def digit(root, end, root_size, end_size, claw_dir, claw_len, hook, claw_w, claw_h, bone, tile,
          up=(0, 0, 1)):
    """A toe/finger and its claw as ONE continuous mesh: the digit runs root -> end, then the
    same tube carries on as a curved talon that hooks down (-up) and tapers to a sharp tip."""
    r, e = Vector(root), Vector(end)
    d, u = Vector(claw_dir).normalized(), Vector(up).normalized()
    p0, p1, p2 = e, e + d * (claw_len * 0.55) + u * (claw_len * 0.1), e + d * claw_len - u * hook
    bez = lambda t: (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t * t * p2  # noqa: E731
    path = [r, e] + [bez(t) for t in (0.12, 0.45, 0.78, 1.0)]
    sizes = [root_size, end_size, (claw_w, claw_h), (claw_w * 0.72, claw_h * 0.72),
             (claw_w * 0.4, claw_h * 0.4), (claw_w * 0.05, claw_h * 0.05)]
    seg = [tile, 'TEETH', 'TEETH', 'TEETH', 'TEETH']
    loft(path, sizes, tile, [{bone: 1}] * len(path), sides=5, p=2.4, up=tuple(u), seg_tiles=seg,
         cap_tile=tile)


def mdigit(root, end, root_size, end_size, claw_dir, claw_len, hook, claw_w, claw_h, bone, tile, up=(0, 0, 1)):
    for sgn, suf in ((1, '.L'), (-1, '.R')):
        m = lambda c: (c[0] * sgn, c[1], c[2])  # noqa: E731
        digit(m(root), m(end), root_size, end_size, m(claw_dir), claw_len, hook, claw_w, claw_h, bone + suf,
              tile, up=m(up))


def W(**kw):
    return dict(kw)


def ellipsoid(center, axis, r_axis, r_side, r_up, tile, bone, rings=7, sides=12):
    """Closed ellipsoid built as a loft along `axis` (eyeballs, socket cutters)."""
    d = Vector(axis).normalized()
    ts = [-0.96 + 1.92 * i / (rings - 1) for i in range(rings)]
    path = [Vector(center) + d * (t * r_axis) for t in ts]
    sizes = [(2 * r_side * math.sqrt(1 - t * t), 2 * r_up * math.sqrt(1 - t * t)) for t in ts]
    loft(path, sizes, tile, [{bone: 1}] * rings, sides=sides, p=2.0)


def _part_object(part, name):
    verts, faces, uvs, _, _ = part
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new('UVMap')
    bv = [bm.verts.new(v) for v in verts]
    for f, fuv in zip(faces, uvs):
        face = bm.faces.new([bv[i] for i in f])
        for loop, c in zip(face.loops, fuv):
            loop[uvl].uv = c
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    return obj


def carve(part, cutters, bone):
    """Boolean-subtract cutter parts (e.g. eye sockets) from a closed part. The cavity walls
    keep the cutters' UVs, so the inside of a socket gets the cutter's tile."""
    target = _part_object(part, 'CARVE_target')
    for i, c in enumerate(cutters):
        cobj = _part_object(c, f'CARVE_cutter{i}')
        mod = target.modifiers.new(f'bool{i}', 'BOOLEAN')
        mod.operation, mod.solver, mod.object = 'DIFFERENCE', 'EXACT', cobj
        bpy.context.view_layer.objects.active = target
        bpy.ops.object.modifier_apply(modifier=mod.name)
        bpy.data.objects.remove(cobj)
    me = target.data
    uvl = me.uv_layers['UVMap'].data
    verts = [v.co.copy() for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    uvs = [[tuple(uvl[li].uv) for li in p.loop_indices] for p in me.polygons]
    bpy.data.objects.remove(target)
    PARTS.append((verts, faces, uvs, [{bone: 1}] * len(verts), True))


# --------------------------------------------------------------------------- the model

JAW_PIVOT = (0, -15.6, 10.4)
JAW_OPEN = (36, 0, 0)          # mouth held open like the reference (bind pose)


EYE_SOCKET = (3.3, -17.7, 12.9)   # where the socket opens on the skull side (left eye)
EYE_FWD = 0.55                   # how far the eyes turn toward the front


def build_head():
    H = W(Head=1)
    # skull: one smooth loft from the snout tip back to the neck
    loft([(0, -24.0, 11.9), (0, -22.2, 12.0), (0, -19.0, 12.3), (0, -16.4, 13.0), (0, -14.0, 12.5)],
         [(4.4, 1.8), (6.0, 2.3), (6.6, 2.7), (7.2, 4.2), (6.6, 5.2)], 'BONE', [H] * 5,
         sides=12, p=3.0, cap_tile='BONE_LIGHT')
    skull = PARTS.pop()
    # eye sockets: carve a real cavity into each side of the skull (dark inner walls)
    cutters = []
    for sgn in (1, -1):
        ellipsoid((EYE_SOCKET[0] * sgn, EYE_SOCKET[1], EYE_SOCKET[2]), (sgn, -EYE_FWD, 0.08),
                  1.0, 1.05, 0.85, 'CHARCOAL', 'Head', rings=7, sides=12)
        cutters.append(PARTS.pop())
    carve(skull, cutters, 'Head')
    # eyeballs sitting in the sockets: glowing red iris ball with a black slit pupil
    for sgn in (1, -1):
        axis = Vector((sgn, -EYE_FWD, 0.08)).normalized()
        c = Vector((EYE_SOCKET[0] * sgn, EYE_SOCKET[1], EYE_SOCKET[2])) - axis * 0.62
        ellipsoid(c, axis, 0.62, 0.62, 0.5, 'EYE', 'Head', rings=7, sides=12)
        ellipsoid(c + axis * 0.55, axis, 0.1, 0.18, 0.42, 'PUPIL', 'Head', rings=3, sides=8)
    loft([(0, -21.5, 13.1), (0, -18.4, 13.6)], [(3.2, 0.7), (3.8, 0.9)], 'CHARCOAL', [H] * 2, sides=6)  # snout ridge
    for x in (1.2, -1.2):                                                                 # nostrils
        horn((x, -23.4, 12.6), (x, -23.6, 13.3), 1.0, 0.9, 0.6, 0.5, 'BONE_LIGHT', 'Head')
    # brow ridges overhanging the eye sockets
    mhorn((2.8, -17.0, 13.3), (3.3, -18.9, 14.6), 1.8, 1.4, 1.0, 0.8, 'BONE_LIGHT', 'Head', sides=6, p=3.0)
    # dark crown with horns (front-head view)
    loft([(0, -17.0, 15.0), (0, -14.4, 14.9)], [(5.0, 1.0), (5.4, 1.3)], 'CHARCOAL', [H] * 2, sides=8)
    mhorn((2.3, -15.6, 15.2), (2.6, -14.9, 17.1), 1.5, 1.6, 0.5, 0.6, 'CHARCOAL', 'Head')
    mhorn((1.2, -16.8, 15.3), (1.3, -16.5, 16.2), 1.2, 1.2, 0.5, 0.5, 'CHARCOAL', 'Head')
    horn((0, -16.6, 15.3), (0, -16.2, 16.4), 1.3, 1.3, 0.6, 0.7, 'BONE_LIGHT', 'Head')
    mhorn((3.3, -15.4, 13.9), (3.9, -14.4, 15.3), 1.3, 2.0, 0.6, 0.8, 'BONE', 'Head')      # side crest
    mhorn((3.2, -15.2, 11.0), (3.6, -15.0, 12.6), 1.4, 3.0, 1.1, 2.4, 'BONE', 'Head', sides=6, p=3.0)  # cheek
    # mouth roof + throat cavity
    box((0, -19.6, 10.9), (5.2, 6.4, 0.4), 'MOUTH', 'Head')
    box((0, -16.3, 10.2), (4.4, 1.6, 1.8), 'MOUTH', 'Head')
    # upper teeth
    for x, ln in ((-1.8, 1.6), (-0.9, 1.1), (0.0, 1.3), (0.9, 1.1), (1.8, 1.6)):
        spike((x, -23.2, 11.45), (0.62, 0.6), (0, 0, -ln - 0.45), 'TEETH', 'Head')
    for y, ln in ((-22.2, 1.9), (-21.0, 1.2), (-19.8, 1.5), (-18.6, 1.0), (-17.5, 1.2)):
        mspike((2.6, y, 11.45), (0.62, 0.7), (0, 0, -ln - 0.45), 'TEETH', 'Head')


def build_jaw():
    J = W(Jaw=1)
    kw = dict(pivot=JAW_PIVOT, pivot_rot=JAW_OPEN)
    loft([(0, -23.9, 9.6), (0, -22.0, 9.3), (0, -18.5, 9.3), (0, -15.6, 9.6)],
         [(4.4, 2.0), (5.6, 2.2), (5.9, 2.4), (5.2, 2.4)], 'BONE', [J] * 4, sides=10, p=3.0, **kw)
    loft([(0, -21.5, 8.2), (0, -17.0, 8.3)], [(3.4, 0.6), (3.8, 0.7)], 'BONE_DARK', [J] * 2, sides=6, **kw)
    box((0, -19.5, 10.45), (4.4, 6.8, 0.3), 'MOUTH', 'Jaw', **kw)
    loft([(0, -22.2, 10.5), (0, -19.0, 10.75), (0, -16.4, 10.6)], [(2.2, 0.5), (2.6, 0.7), (2.2, 0.5)],
         'TONGUE', [J] * 3, sides=8, p=2.2, **kw)
    for x, ln in ((-1.6, 1.3), (0.0, 1.1), (1.6, 1.3)):
        spike((x, -23.1, 10.0), (0.6, 0.6), (0, 0, ln + 0.45), 'TEETH', 'Jaw', **kw)
    for y, ln in ((-22.0, 1.5), (-20.7, 1.0), (-19.4, 1.3), (-18.1, 0.9)):
        mspike((2.4, y, 9.95), (0.6, 0.7), (0, 0, ln + 0.45), 'TEETH', 'Jaw', **kw)


# body + tail as ONE continuous smooth tube: (y, centre z, width, height, bone weights)
BODY_RINGS = [
    (-14.8, 11.3, 6.2, 5.0, W(Neck=1)),
    (-12.8, 10.9, 8.2, 6.6, W(Neck=0.6, Chest=0.4)),
    (-10.4, 10.1, 11.0, 7.8, W(Chest=1)),
    (-7.4, 9.7, 12.6, 8.2, W(Chest=0.5, Spine=0.5)),
    (-4.2, 9.5, 13.0, 8.2, W(Spine=1)),
    (-1.2, 9.6, 12.4, 7.6, W(Spine=0.5, Hips=0.5)),
    (2.0, 9.7, 11.2, 7.0, W(Hips=1)),
]
TAIL_PTS = [(0, 4.6, 10.0), (0, 9.0, 9.4), (0, 13.4, 8.2), (0, 17.4, 6.8),
            (0, 21.0, 5.4), (0, 24.2, 4.2), (0, 27.0, 3.3)]
TAIL_W = [9.6, 7.4, 5.8, 4.4, 3.2, 2.2, 1.2]
TAIL_H = [6.0, 5.0, 4.0, 3.2, 2.4, 1.7, 1.0]


def tail_rings():
    rings = []
    for i in range(len(TAIL_PTS)):
        wt = W(**{f'Tail{i}': 0.5, f'Tail{i + 1}': 0.5}) if 0 < i < 6 else (
            W(Hips=0.5, Tail1=0.5) if i == 0 else W(Tail6=1))
        y, z = TAIL_PTS[i][1], TAIL_PTS[i][2]
        rings.append((y, z, TAIL_W[i], TAIL_H[i], wt))
        if i < 6:                                     # mid-segment ring, single bone
            a, b = Vector(TAIL_PTS[i]), Vector(TAIL_PTS[i + 1])
            m = (a + b) / 2
            rings.append((m.y, m.z, (TAIL_W[i] + TAIL_W[i + 1]) / 2 * 0.98,
                          (TAIL_H[i] + TAIL_H[i + 1]) / 2 * 0.98, W(**{f'Tail{i + 1}': 1})))
    rings.append((28.6, 2.9, 0.35, 0.35, W(Tail6=1)))  # pointed tail tip
    return rings


def _ring_at(y):
    """Interpolated body/tail cross-section at y: (centre z, half width, half height)."""
    rings = BODY_RINGS + tail_rings()
    for (y0, z0, w0, h0, _), (y1, z1, w1, h1, _) in zip(rings, rings[1:]):
        if y0 <= y <= y1:
            t = (y - y0) / (y1 - y0)
            return z0 + (z1 - z0) * t, (w0 + (w1 - w0) * t) / 2, (h0 + (h1 - h0) * t) / 2
    y0, z0, w0, h0, _ = rings[0] if y < rings[0][0] else rings[-1]
    return z0, w0 / 2, h0 / 2


BODY_P = 2.6


def flank_x(y, z):
    """Body surface x (left side) at height z; used to sit parts ON the body."""
    cz, a, b = _ring_at(y)
    t = min(abs(z - cz) / b, 0.999)
    return a * (1 - t ** BODY_P) ** (1 / BODY_P)


def back_z(y, x=0.0):
    """Body surface z on top of the back at lateral offset x."""
    cz, a, b = _ring_at(y)
    t = min(abs(x) / a, 0.999)
    return cz + b * (1 - t ** BODY_P) ** (1 / BODY_P)


def build_body():
    rings = BODY_RINGS + tail_rings()
    loft([(0, y, z) for y, z, _, _, _ in rings], [(w, h) for _, _, w, h, _ in rings], 'MIX',
         [wt for *_, wt in rings], sides=12, p=2.6, cap_tile='CHARCOAL')
    # bone belly plate running from the throat down the whole tail (bottom view)
    belly = [(y, z - h / 2 - 0.12, max(w * 0.34, 0.3), wt) for y, z, w, h, wt in rings[1:-1]]
    loft([(0, y, z) for y, z, _, _ in belly], [(w, 0.5) for _, _, w, _ in belly], 'BONE',
         [wt for *_, wt in belly], sides=6, p=4.0)
    # dark ridge + bone vertebra strip along the top of the tail (back/top views)
    top = [(y, z + h / 2 + 0.1, max(w * 0.16, 0.3), wt) for y, z, w, h, wt in rings[7:-1]]
    loft([(0, y, z) for y, z, _, _ in top], [(w, 0.5) for _, _, w, _ in top], 'BONE_LIGHT',
         [wt for *_, wt in top], sides=6, p=4.0)
    # throat
    loft([(0, -14.6, 8.3), (0, -11.4, 7.3)], [(3.4, 0.8), (4.0, 0.9)], 'BONE_DARK',
         [W(Neck=1), W(Chest=1)], sides=6)

    # big curved bone ribs wrapping the flanks in front of the thigh (hero/side views)
    for y in (-13.0, -10.8, -8.6, -6.4):
        b = 'Chest' if y < -7.2 else 'Spine'
        pts = []
        for dy, z, inset in ((-0.3, back_z(y - 0.3, 3.8) - 0.1, 0.6), (0.0, 12.0, 0.25), (0.3, 9.6, 0.2),
                             (0.8, 7.2, 0.25), (1.2, _ring_at(y + 1.2)[0] - _ring_at(y + 1.2)[2] + 0.5, 0.5)):
            pts.append((flank_x(y + dy, z) - inset + 0.45, y + dy, z))
        mloft(pts, [(0.8, 1.3), (0.9, 1.5), (0.9, 1.5), (0.8, 1.3), (0.6, 0.9)], 'BONE',
              [W(**{b: 1})] * 5, sides=6, p=4.0, up=(0, 1, 0))
    # shoulder plate, sunk into the front of the chest
    mloft([(flank_x(-13.9, 11.0) - 0.1, -13.9, 11.0), (flank_x(-13.6, 8.6) - 0.1, -13.6, 8.6)],
          [(1.2, 1.4), (1.0, 1.1)], 'BONE', [W(Chest=1)] * 2, sides=6, up=(0, 1, 0))


# spine plates: (y, height, bone) -- big bone plates down the back like the reference
BACK_SPIKES = [(-15.3, 2.0, 'Head'), (-12.6, 4.0, 'Neck'), (-9.6, 7.0, 'Chest'), (-5.9, 6.6, 'Spine'),
               (-2.3, 5.8, 'Spine'), (1.2, 4.8, 'Hips'), (4.4, 3.8, 'Hips')]


def build_back_spikes():
    """Tapered bone plates down the back, leaning backwards, with gaps between (side views)."""
    for y, h, bone in BACK_SPIKES:
        base = 14.8 if bone == 'Head' else back_z(y) - 0.6
        horn((0, y, base), (0, y + h * 0.4, base + h), 1.6, 3.2, 0.8, 1.7, 'BONE_LIGHT', bone, sides=6, p=4.0)
        if bone in ('Chest', 'Hips'):     # lateral spikes at the shoulders and hips (top/back views)
            lz = back_z(y + 0.4, 3.2) - 0.5
            mhorn((3.2, y + 0.4, lz), (3.9, y + 1.4, lz + 0.5 + h * 0.45), 1.3, 1.8, 0.35, 0.5, 'BONE', bone,
                  sides=6, p=3.0)
    # dorsal spikes down the tail, shrinking toward the tip
    for i in range(6):
        a, b = Vector(TAIL_PTS[i]), Vector(TAIL_PTS[i + 1])
        m = (a + b) / 2
        hh = (TAIL_H[i] + TAIL_H[i + 1]) / 2
        base = m.z + hh / 2 - 0.5
        horn((0, m.y, base), (0, m.y + 1.2, base + hh * 0.55 + 0.6), max(0.5, TAIL_W[i] * 0.15), 1.6,
             0.3, 0.7, 'BONE_LIGHT', f'Tail{i + 1}', sides=6, p=4.0)


def build_leg():
    T, S, F = W(**{'Thigh.': 1}), W(**{'Shin.': 1}), W(**{'Foot.': 1})
    # big rounded thigh
    mloft([(6.6, -1.9, 12.9), (6.7, -2.2, 11.4), (6.8, -2.3, 8.6), (6.6, -2.7, 6.2), (6.5, -2.9, 4.9)],
          [(2.4, 4.4), (3.4, 6.8), (3.6, 6.8), (2.9, 4.6), (2.3, 3.2)], 'MIX', [T] * 5, sides=10, p=2.8,
          up=(0, 1, 0), cap_tile='CHARCOAL')
    # shin (knee blends between thigh and shin so the leg bends smoothly)
    mloft([(6.5, -2.9, 5.8), (6.45, -2.2, 3.6), (6.4, -1.5, 1.4)], [(3.0, 3.3), (2.8, 3.0), (2.6, 2.7)],
          'DARK', [W(**{'Thigh.': 0.5, 'Shin.': 0.5}), S, W(**{'Shin.': 0.5, 'Foot.': 0.5})],
          sides=8, p=2.6, up=(0, 1, 0))
    # foot
    mloft([(6.4, -0.3, 0.75), (6.4, -2.6, 0.8), (6.4, -4.9, 0.7)], [(2.6, 1.3), (3.8, 1.6), (3.9, 1.3)],
          'DARK', [F] * 3, sides=8, p=3.0)
    # three big bone toes with claws + dew claw
    for dx in (-1.3, 0.0, 1.3):                         # toe and claw are one fused mesh
        mdigit((6.4 + dx, -4.4, 0.8), (6.4 + dx * 1.05, -6.3, 0.75), (1.25, 1.6), (0.95, 1.15),
               (dx * 0.1, -1, -0.1), 1.9, 0.7, 0.72, 0.95, 'Foot', 'BONE')
    mdigit((6.4, -1.2, 0.8), (6.4, -0.2, 0.7), (0.9, 1.0), (0.75, 0.85), (0, 1, -0.15), 1.1, 0.4,
           0.55, 0.7, 'Foot', 'BONE')                                                  # dew claw


SHOULDER, ELBOW, WRIST, KNUCKLE = (5.0, -13.7, 8.9), (5.9, -14.0, 5.9), (5.9, -16.5, 4.8), (5.9, -17.7, 4.0)
HAND_TIP = (5.9, -18.5, 3.1)


def _off(p, dx=0.0, dy=0.0, dz=0.0):
    return (p[0] + dx, p[1] + dy, p[2] + dz)


def build_arm():
    """Muscular two-part arm hanging in front of the ribs: bicep, a visible elbow joint cap,
    forearm angled forward, wrist, and a clawed three-fingered hand."""
    U, Fo, Ha = W(**{'UpperArm.': 1}), W(**{'Forearm.': 1}), W(**{'Hand.': 1})
    UF, FH = W(**{'UpperArm.': 0.5, 'Forearm.': 0.5}), W(**{'Forearm.': 0.5, 'Hand.': 0.5})
    # upper arm: thick shoulder, bulging bicep, narrowing into the elbow
    mloft([SHOULDER, _off(SHOULDER, 0.4, -0.1, -1.1), _off(ELBOW, -0.1, 0.1, 1.0), ELBOW],
          [(2.9, 3.1), (3.0, 3.2), (2.5, 2.6), (2.0, 2.1)], 'DARK', [U, U, U, UF], sides=10, p=2.4,
          up=(0, -1, 0), caps=(False, False))
    # elbow joint: rounded cap across the bend + a bone spur pointing back
    ex, ey, ez = ELBOW
    mloft([(ex - 1.3, ey, ez), (ex - 0.8, ey, ez), (ex + 0.8, ey, ez), (ex + 1.3, ey, ez)],
          [(1.4, 1.4), (2.5, 2.5), (2.5, 2.5), (1.4, 1.4)], 'MAROON', [UF] * 4, sides=10, p=2.0)
    mhorn(_off(ELBOW, 0, 0.8, 0.1), _off(ELBOW, 0, 2.0, 0.5), 1.0, 1.0, 0.25, 0.3, 'BONE', 'Forearm', sides=6, p=3.0)
    # forearm: angles forward from the elbow to the wrist, with a bone guard plate on top
    mloft([ELBOW, _off(WRIST, 0, 1.2, 0.5), WRIST], [(2.0, 2.1), (1.9, 2.0), (1.6, 1.6)], 'DARK',
          [UF, Fo, FH], sides=10, p=2.4, caps=(False, False))
    mloft([_off(ELBOW, 0, -0.6, 0.9), _off(WRIST, 0, 0.4, 0.8)], [(1.3, 0.45), (1.0, 0.4)], 'BONE',
          [Fo] * 2, sides=6, p=4.0)
    # wrist joint ring + hand
    mloft([_off(WRIST, -0.9), _off(WRIST, 0.9)], [(1.9, 1.9), (1.9, 1.9)], 'CHARCOAL', [FH] * 2, sides=8, p=2.0)
    mloft([WRIST, _off(KNUCKLE, 0, 0.5, 0.3), KNUCKLE], [(1.6, 1.6), (2.4, 1.5), (2.3, 1.3)], 'CHARCOAL',
          [FH, Ha, Ha], sides=8, p=2.8)
    for dx in (-0.75, 0.0, 0.75):                       # finger and claw are one fused mesh
        mdigit(_off(KNUCKLE, dx * 0.85, 0.8, 0.15), _off(HAND_TIP, dx * 1.1, 0.25, 0.3), (0.85, 0.85),
               (0.68, 0.68), (dx * 0.1, -1, -0.35), 1.5, 0.75, 0.52, 0.66, 'Hand', 'DARK')


# --------------------------------------------------------------------------- armature

BONES = {
    # name: (head, tail, parent)
    'Root': ((0, 0, 0), (0, -2, 0), None),
    'Hips': ((0, 4.6, 10.0), (0, -1.4, 10.2), 'Root'),
    'Spine': ((0, -1.4, 10.2), (0, -7.2, 10.6), 'Hips'),
    'Chest': ((0, -7.2, 10.6), (0, -11.4, 11.0), 'Spine'),
    'Neck': ((0, -11.4, 11.0), (0, -14.6, 11.8), 'Chest'),
    'Head': ((0, -14.6, 11.8), (0, -23.5, 12.2), 'Neck'),
    'Jaw': (JAW_PIVOT, (0, -21.5, 6.9), 'Head'),
}
for i in range(6):
    BONES[f'Tail{i + 1}'] = (TAIL_PTS[i], TAIL_PTS[i + 1], 'Hips' if i == 0 else f'Tail{i}')
for s, sgn in (('L', 1), ('R', -1)):
    BONES[f'Thigh.{s}'] = ((6.2 * sgn, -2.2, 10.2), (6.4 * sgn, -2.6, 5.4), 'Hips')
    BONES[f'Shin.{s}'] = ((6.4 * sgn, -2.6, 5.4), (6.4 * sgn, -1.6, 1.2), f'Thigh.{s}')
    BONES[f'Foot.{s}'] = ((6.4 * sgn, -1.6, 1.2), (6.4 * sgn, -6.6, 0.6), f'Shin.{s}')
    mx = lambda c: (c[0] * sgn, c[1], c[2])  # noqa: E731
    BONES[f'UpperArm.{s}'] = (mx(SHOULDER), mx(ELBOW), 'Chest')
    BONES[f'Forearm.{s}'] = (mx(ELBOW), mx(WRIST), f'UpperArm.{s}')
    BONES[f'Hand.{s}'] = (mx(WRIST), mx(HAND_TIP), f'Forearm.{s}')


XSCALE = {'Head': 1.05, 'Jaw': 1.05, 'Neck': 1.2, 'Chest': 1.25, 'Spine': 1.25, 'Hips': 1.25,
          'Tail1': 1.2, 'Tail2': 1.15, 'Tail3': 1.1, 'Tail4': 1.1, 'Tail5': 1.1, 'Tail6': 1.1, 'Root': 1.0}


def xs(bone):
    if bone in XSCALE:
        return XSCALE[bone]
    return 1.3 if bone.split('.')[0] in ('Thigh', 'Shin', 'Foot') else 1.25


HEAD_TILT = -10
LIFT = 1.5   # the reference stands taller on its legs than the first block-out


def widen(co, bone):
    """Per-bone reshape: lateral widening + lifting the body onto longer legs."""
    base = bone.split('.')[0]
    z = co[2]
    if base in ('Thigh', 'Shin'):
        z = z * (1 + LIFT / 12.4)
    elif base.startswith('Tail'):
        z = z + LIFT * (1 - (co[1] - 4.6) / 30)
    elif base not in ('Foot', 'Root'):
        z = z + LIFT
    v = Vector((co[0] * xs(bone), co[1], z))
    if base in ('Head', 'Jaw'):                  # head held high, snout tilted up (hero view)
        pivot = Vector((0, -14.6, 11.8 + LIFT))
        v = Euler((math.radians(HEAD_TILT), 0, 0)).to_matrix() @ (v - pivot) + pivot
    return v


def make_armature():
    arm_data = bpy.data.armatures.new('TRexArmature')
    arm = bpy.data.objects.new('TRexRig', arm_data)
    bpy.context.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    for name, (h, t, parent) in BONES.items():
        eb = arm_data.edit_bones.new(name)
        eb.head, eb.tail = widen(h, name), widen(t, name)
        eb.roll = 0
        if parent:
            eb.parent = arm_data.edit_bones[parent]
            eb.use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    arm_data.display_type = 'STICK'
    return arm


# --------------------------------------------------------------------------- mesh assembly

def make_material():
    mat = bpy.data.materials.new('TRex_Studs')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    img = bpy.data.images.load(os.path.join(TEX_DIR, 'TRex_Studs_Albedo.png'))
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    tex.interpolation = 'Closest'
    nt.links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])
    nimg = bpy.data.images.load(os.path.join(TEX_DIR, 'TRex_Studs_Normal.png'))
    nimg.colorspace_settings.name = 'Non-Color'
    ntex = nt.nodes.new('ShaderNodeTexImage')
    ntex.image = nimg
    nmap = nt.nodes.new('ShaderNodeNormalMap')
    nmap.inputs['Strength'].default_value = 0.6
    nt.links.new(ntex.outputs['Color'], nmap.inputs['Color'])
    nt.links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    eimg = bpy.data.images.load(os.path.join(TEX_DIR, 'TRex_Studs_Emissive.png'))
    etex = nt.nodes.new('ShaderNodeTexImage')
    etex.image = eimg
    nt.links.new(etex.outputs['Color'], bsdf.inputs['Emission Color'])
    bsdf.inputs['Emission Strength'].default_value = 2.0
    bsdf.inputs['Roughness'].default_value = 0.65
    return mat


def make_mesh(arm):
    me = bpy.data.meshes.new('TRexMesh')
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    deform = bm.verts.layers.deform.verify()
    bone_index = {name: i for i, name in enumerate(BONES)}
    for verts, faces, uvs, vweights, smooth in PARTS:
        bv = []
        for v, wts in zip(verts, vweights):
            main = max(wts, key=wts.get)
            nv = bm.verts.new(widen(v, main))
            for name, wgt in wts.items():
                nv[deform][bone_index[name]] = wgt
            bv.append(nv)
        for f, fuv in zip(faces, uvs):
            face = bm.faces.new([bv[i] for i in f])
            face.smooth = smooth
            for loop, c in zip(face.loops, fuv):
                loop[uv].uv = c
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)   # teeth pointing down were wound inward
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new('TRex', me)
    bpy.context.collection.objects.link(obj)
    for name in BONES:
        obj.vertex_groups.new(name=name)
    obj.data.materials.append(make_material())
    obj.parent = arm
    mod = obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = arm
    return obj


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


# --------------------------------------------------------------------------- animation

def pose_key(arm, frame, rots, locs=None):
    for name, r in rots.items():
        pb = arm.pose.bones[name]
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = Euler([math.radians(v) for v in r], 'XYZ')
        pb.keyframe_insert('rotation_euler', frame=frame)
    for name, l in (locs or {}).items():
        pb = arm.pose.bones[name]
        pb.location = Vector(l)
        pb.keyframe_insert('location', frame=frame)


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
        pb.location = (0, 0, 0)
        pb.scale = (1, 1, 1)


def all_bones_key(arm, frame):
    for pb in arm.pose.bones:
        pb.keyframe_insert('rotation_euler', frame=frame)
        pb.keyframe_insert('location', frame=frame)


def make_idle(arm):
    """60-frame breathing idle: chest heave, head bob + jaw chomp, lazy tail sway."""
    act = bpy.data.actions.new('Idle')
    arm.animation_data_create().action = act
    n = 60
    for f in range(0, n + 1, 5):
        reset_pose(arm)
        ph = 2 * math.pi * f / n
        s, c = math.sin(ph), math.cos(ph)
        rots = {
            'Hips': (0.6 * s, 0, 0),
            'Spine': (-1.0 * s, 0, 0),
            'Chest': (-1.2 * s, 0, 0),
            'Neck': (2.0 * s, 1.5 * math.sin(ph / 1), 0),
            'Head': (-3.0 * s, 0, 2.5 * math.sin(ph)),
            'Jaw': (-4.0 - 4.0 * c, 0, 0),
            'UpperArm.L': (5 * s, 0, 0), 'UpperArm.R': (5 * s, 0, 0),
            'Forearm.L': (-6 * c, 0, 0), 'Forearm.R': (-6 * c, 0, 0),
            'Hand.L': (8 * math.sin(ph - 0.8), 0, 0), 'Hand.R': (8 * math.sin(ph - 0.8), 0, 0),
        }
        for i in range(6):
            rots[f'Tail{i + 1}'] = (1.2 * math.sin(ph - i * 0.5), 0, 3.0 * math.sin(ph - i * 0.6))
        locs = {'Root': (0, 0, -0.05 * (1 - c) / 2)}
        pose_key(arm, f + 1, rots, locs)
        all_bones_key(arm, f + 1)
    return act


def make_walk(arm):
    """40-frame in-place stomp walk cycle (Roblox moves the root, the rig walks in place)."""
    act = bpy.data.actions.new('Walk')
    arm.animation_data.action = act
    n = 40
    for f in range(0, n + 1, 2):
        reset_pose(arm)
        ph = 2 * math.pi * f / n
        rots, locs = {}, {}
        for side, off in (('L', 0.0), ('R', math.pi)):
            p = ph + off
            swing = math.sin(p)                         # + = leg forward
            rots[f'UpperArm.{side}'] = (-10 * swing, 0, 0)
            rots[f'Forearm.{side}'] = (8 * math.cos(p), 0, 0)
            rots[f'Hand.{side}'] = (10 * math.cos(p - 0.6), 0, 0)
        locs['Root'] = (0, 0, -0.14 - 0.06 * math.cos(2 * ph))       # dips at each footfall
        rots['Hips'] = (1.5 * math.cos(2 * ph), 0, 5 * math.sin(ph))
        rots['Spine'] = (-1.0 * math.cos(2 * ph), 0, -2.5 * math.sin(ph))
        rots['Chest'] = (-1.0 * math.cos(2 * ph), 0, -2.5 * math.sin(ph))
        rots['Neck'] = (3 * math.cos(2 * ph), 0, -3 * math.sin(ph))
        rots['Head'] = (-3 * math.cos(2 * ph), 0, -2 * math.sin(ph))
        rots['Jaw'] = (-3 - 3 * math.cos(2 * ph), 0, 0)
        for i in range(6):
            rots[f'Tail{i + 1}'] = (1.5 * math.cos(2 * ph - i * 0.4), 0, -6 * math.sin(ph - (i + 1) * 0.45))
        pose_key(arm, f + 1, rots, locs)
        all_bones_key(arm, f + 1)
    return act


LEG_BONES = [f'{b}.{s}' for s in 'LR' for b in ('Thigh', 'Shin', 'Foot')]


def bake_leg_ik(arm, frames, target_fn):
    """Drive the legs with 2-bone IK toward per-frame foot targets, then bake the result
    into plain FK rotation keys (Roblox only imports bone transforms, not constraints)."""
    scene = bpy.context.scene
    rest = {s: arm.matrix_world @ arm.data.bones[f'Foot.{s}'].head_local for s in 'LR'}
    rest_rot = {s: (arm.matrix_world @ arm.data.bones[f'Foot.{s}'].matrix_local).to_3x3() for s in 'LR'}
    empties = []
    for s in 'LR':
        tgt = bpy.data.objects.new(f'IK_{s}', None)
        pole = bpy.data.objects.new(f'Pole_{s}', None)
        for o in (tgt, pole):
            scene.collection.objects.link(o)
            empties.append(o)
        pole.location = rest[s] + Vector((0, -4.0 * STUD_TO_M * 3, 5 * STUD_TO_M))
        ik = arm.pose.bones[f'Shin.{s}'].constraints.new('IK')
        ik.target, ik.pole_target, ik.chain_count = tgt, pole, 2
        ik.pole_angle = math.radians(-90)
        cr = arm.pose.bones[f'Foot.{s}'].constraints.new('COPY_ROTATION')
        cr.target = tgt
        for f in frames:
            dy, dz, pitch = target_fn(s, f)
            tgt.location = rest[s] + Vector((0, dy * STUD_TO_M, dz * STUD_TO_M))
            tgt.rotation_mode = 'QUATERNION'
            tgt.rotation_quaternion = (Euler((math.radians(pitch), 0, 0)).to_matrix() @ rest_rot[s]).to_quaternion()
            tgt.keyframe_insert('location', frame=f)
            tgt.keyframe_insert('rotation_quaternion', frame=f)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='POSE')
    for pb in arm.pose.bones:
        pb.bone.select = pb.name in LEG_BONES
    bpy.ops.nla.bake(frame_start=frames[0], frame_end=frames[-1], step=1, only_selected=True,
                     visual_keying=True, clear_constraints=True, use_current_action=True,
                     bake_types={'POSE'})
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in empties:
        bpy.data.objects.remove(o)


def walk_feet(side, f, n=40, stride=5.0, lift=2.0):
    p = ((f - 1) / n + (0.5 if side == 'R' else 0.0)) % 1.0
    if p < 0.5:                                   # stance: planted foot slides back
        q = p / 0.5
        return (-stride / 2 + stride * q, 0.0, 0.0)
    q = (p - 0.5) / 0.5                           # swing: lift and carry forward
    return (stride / 2 - stride * (0.5 - 0.5 * math.cos(math.pi * q)), lift * math.sin(math.pi * q),
            8 * math.sin(math.pi * q))        # toes tip down while the foot is carried


def make_cyclic(act):
    fcs = act.fcurves if hasattr(act, 'fcurves') else []
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.interpolation = 'BEZIER'
        fc.modifiers.new('CYCLES')


# --------------------------------------------------------------------------- main

def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = 30

    build_head()
    build_jaw()
    build_body()
    build_back_spikes()
    build_leg()
    build_arm()

    arm = make_armature()
    rex = make_mesh(arm)
    tris = tri_count(rex)
    print(f'VALIDATE tris={tris} parts={len(PARTS)} bones={len(BONES)}')
    if tris >= 5000:
        raise RuntimeError(f'Triangle budget exceeded: {tris}')

    # to metres: 1 stud = 0.28 m so the Roblox importer lands on stud scale
    arm.scale = (STUD_TO_M,) * 3
    bpy.ops.object.select_all(action='DESELECT')
    arm.select_set(True)
    rex.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    idle = make_idle(arm)
    bake_leg_ik(arm, list(range(1, 62)), lambda side, f: (0.0, 0.0, 0.0))
    walk = make_walk(arm)
    bake_leg_ik(arm, list(range(1, 42)), walk_feet)
    for act in (idle, walk):
        make_cyclic(act)
        act.use_fake_user = True
    arm.animation_data.action = idle
    scene.frame_start, scene.frame_end = 1, 61

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, 'TRex.blend'))
    print('saved', os.path.join(OUT, 'TRex.blend'))


if __name__ == '__main__':
    main()
