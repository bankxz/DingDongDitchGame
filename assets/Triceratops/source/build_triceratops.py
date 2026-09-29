"""
Build the Roblox-ready blocky Triceratops from scratch.

Run with Blender as a Python module (pip install bpy==4.2.0) or inside Blender:
    python3 build_triceratops.py [--stud-tile path/to/height_tile.png] [--stud-pitch 1.0]

Outputs (relative to the asset folder, one level above this script):
    Triceratops.blend                 source scene (mesh + rig + 4 actions)
    Triceratops.fbx                   rigged + skinned mesh, textures embedded, no animation
    animations/Triceratops_<Anim>.fbx one FBX per animation (Idle, Walk, Run, Attack)
    textures/Triceratops_{Color,Normal,Roughness}.png  1024x1024 SurfaceAppearance maps
    textures/StudTile_Height.png      the stud height tile the atlas was painted from
    validation/build_report.json      geometry / rig / weight checks

Modeling is done in "stud units" (1 unit = 1 Roblox stud) and scaled by STUD_M (0.28 m) when
the mesh and bones are created, so the FBX is in real metres and the Roblox 3D Importer's
default metre conversion (1 stud = 0.28 m) brings it in at ~17 studs long.

The model faces -Y in Blender (Roblox convention) and is exported with forward -Z / up Y.
"""
import argparse
import json
import math
import os
import sys

import bpy  # must precede bmesh when running as a Python module
import bmesh
import numpy as np
from mathutils import Matrix, Quaternion, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ASSET = os.path.dirname(HERE)

STUD_M = 0.28          # metres per Roblox stud
ATLAS = 1024           # Roblox caps uploaded images at 1024x1024
PAD = 3                # px gutter around each UV island

# ---------------------------------------------------------------- palette (sRGB, sampled
# from the reference sheet with k-means over the front view)
PALETTE = {
    'body':        (92, 178, 58),    # bright medium green
    'body_edge':   (66, 142, 42),    # bevel strips on green blocks
    'foot':        (44, 98, 29),     # darker green feet
    'foot_edge':   (32, 74, 21),
    'belly':       (178, 222, 184),  # pale green underside / jaw
    'belly_edge':  (150, 202, 156),
    'frill_panel': (173, 225, 181),  # pale mint frill interior
    'frill_dark':  (57, 132, 38),    # frill ribs, inner ring, rim
    'horn':        (246, 240, 226),  # cream horns + spikes
    'eye':         (250, 250, 250),
    'pupil':       (24, 22, 24),
}
ROUGHNESS = {'horn': 0.35, 'eye': 0.25, 'pupil': 0.2}
STUDDED = {'body'}     # classes that receive the raised stud pattern


# ============================================================================ stud tile
def default_stud_tile(n=128):
    """Raised square stud with bevelled, slightly rounded edges, one stud per tile.
    Placeholder until the dedicated stud reference is supplied (see README)."""
    c = (np.arange(n) + 0.5) / n - 0.5
    x, y = np.meshgrid(c, c)
    half, rad, bevel = 0.36, 0.07, 0.075
    qx, qy = np.abs(x) - (half - rad), np.abs(y) - (half - rad)
    outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
    inside = np.minimum(np.maximum(qx, qy), 0)
    d = outside + inside - rad                      # signed distance, <0 inside
    t = np.clip(-d / bevel, 0, 1)
    return t * t * (3 - 2 * t)                      # smoothstep bevel profile


def load_tile(path):
    from PIL import Image
    im = np.asarray(Image.open(path).convert('L'), dtype=np.float32) / 255.0
    return im[::-1].copy()                          # row 0 = bottom (UV v = 0)


def sample_wrap(tile, s, t):
    """Bilinear sample of a tiling height map at stud coordinates (s, t)."""
    n_y, n_x = tile.shape
    fx = (s % 1.0) * n_x - 0.5
    fy = (t % 1.0) * n_y - 0.5
    x0 = np.floor(fx).astype(int); y0 = np.floor(fy).astype(int)
    ax = fx - x0; ay = fy - y0
    x0 %= n_x; y0 %= n_y
    x1 = (x0 + 1) % n_x; y1 = (y0 + 1) % n_y
    return ((tile[y0, x0] * (1 - ax) + tile[y0, x1] * ax) * (1 - ay)
            + (tile[y1, x0] * (1 - ax) + tile[y1, x1] * ax) * ay)


# ============================================================================ geometry
class Builder:
    """Collects closed, individually-normalised pieces into one mesh description."""

    def __init__(self):
        self.verts, self.faces, self.fclass, self.fmode, self.vweights = [], [], [], [], []
        self.pieces = []

    def add_bm(self, bm, name, weights, face_classes, mode):
        """weights: bone name (rigid) or callable(co)->{bone: w}.
        face_classes: dict face.index -> class; mode: 'center' or 'world' stud anchoring."""
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.verts.index_update()
        base = len(self.verts)
        for v in bm.verts:
            co = tuple(v.co)
            self.verts.append(co)
            self.vweights.append({weights: 1.0} if isinstance(weights, str) else weights(v.co))
        for f in bm.faces:
            self.faces.append(tuple(base + v.index for v in f.verts))
            self.fclass.append(face_classes[f.index])
            self.fmode.append(mode)
        self.pieces.append((name, len(bm.verts), len(bm.faces)))
        bm.free()


def hull_bm(corners):
    """8 corners: bottom (x-,y-),(x+,y-),(x+,y+),(x-,y+) then top in same order."""
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in corners]
    for q in [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]:
        bm.faces.new([vs[i] for i in q])
    return bm


def frustum(x0, x1, y0, y1, z0, z1, top_inset=(0, 0, 0, 0)):
    """Box with optional top inset (dx0, dx1, dy0, dy1) for chunky tapering."""
    a, b, c, d = top_inset
    return [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0 + a, y0 + c, z1), (x1 - b, y0 + c, z1), (x1 - b, y1 - d, z1), (x0 + a, y1 - d, z1)]


def add_block(B, name, corners, bone, cls, edge_cls, bevel=0.1, mode='center', xform=None):
    bm = hull_bm(corners)
    if xform is not None:
        bmesh.ops.transform(bm, matrix=xform, verts=bm.verts)
    lay = bm.faces.layers.int.new('c')
    if bevel > 0:
        res = bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, offset_type='OFFSET',
                              segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)
        for f in res['faces']:
            f[lay] = 1
    bm.faces.index_update()
    classes = {f.index: (edge_cls if f[lay] == 1 else cls) for f in bm.faces}
    B.add_bm(bm, name, bone, classes, mode)


def mirror_x(corners):
    """Mirror a corner list across X keeping the (x-, x+) ordering convention."""
    m = [(-x, y, z) for (x, y, z) in corners]
    return [m[1], m[0], m[3], m[2], m[5], m[4], m[7], m[6]]


def add_cone(B, name, base, length, radius, tilt_x, bone, cls, sides=6, bend=0.12, tilt_y=0.0):
    """Low-poly horn/spike: ring -> slightly offset mid ring -> single tip vertex."""
    bm = bmesh.new()
    ring0 = [bm.verts.new((radius * math.cos(2 * math.pi * i / sides + math.pi / sides),
                           radius * math.sin(2 * math.pi * i / sides + math.pi / sides), 0))
             for i in range(sides)]
    ring1 = [bm.verts.new((0.55 * radius * math.cos(2 * math.pi * i / sides + math.pi / sides),
                           0.55 * radius * math.sin(2 * math.pi * i / sides + math.pi / sides) - bend * length,
                           0.55 * length)) for i in range(sides)]
    tip = bm.verts.new((0, -bend * length * 1.6, length))
    bm.faces.new(list(reversed(ring0)))
    for i in range(sides):
        j = (i + 1) % sides
        bm.faces.new([ring0[i], ring0[j], ring1[j], ring1[i]])
        bm.faces.new([ring1[i], ring1[j], tip])
    m = Matrix.Translation(base) @ Matrix.Rotation(tilt_y, 4, 'Y') @ Matrix.Rotation(tilt_x, 4, 'X')
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    bm.faces.index_update()
    B.add_bm(bm, name, bone, {f.index: cls for f in bm.faces}, 'center')


# ---------------------------------------------------------------- torso + tail loft
# (y, half-width, z_bottom, z_side_top, z_ridge, ridge_half_width, weights)
SECTIONS = [
    (-4.3, 2.2, 3.0, 5.0, 5.8, 0.55, {'Chest': 1.0}),
    (-2.6, 2.6, 2.75, 5.15, 6.15, 0.65, {'Chest': 1.0}),
    (0.3,  2.75, 2.7, 5.25, 6.25, 0.65, {'Chest': 0.5, 'Hips': 0.5}),
    (2.6,  2.65, 2.8, 5.15, 6.1, 0.6, {'Hips': 1.0}),
    (3.8,  2.1, 3.25, 5.0, 5.75, 0.5, {'Hips': 0.5, 'Tail_01': 0.5}),
    (5.3,  1.65, 3.6, 5.0, 5.6, 0.42, {'Tail_01': 0.5, 'Tail_02': 0.5}),
    (6.8,  1.2, 3.95, 5.0, 5.45, 0.32, {'Tail_02': 0.5, 'Tail_03': 0.5}),
    (8.1,  0.8, 4.25, 5.0, 5.3, 0.22, {'Tail_03': 0.5, 'Tail_04': 0.5}),
    (9.3,  0.42, 4.5, 5.05, 5.2, 0.12, {'Tail_04': 1.0}),
]
# profile edge -> class (bottom, chamfer, side, roof, top, roof, side, chamfer)
PROFILE_CLASS = ['belly', 'body_edge', 'body', 'body', 'body', 'body', 'body', 'body_edge']


def profile(hw, zb, zs, zr, rw):
    c = min(0.28, 0.3 * hw)
    return [(-hw + c, zb), (hw - c, zb), (hw, zb + c), (hw, zs), (rw, zr), (-rw, zr), (-hw, zs), (-hw, zb + c)]


def ridge_at(y):
    ys = [s[0] for s in SECTIONS]
    return float(np.interp(y, ys, [s[4] for s in SECTIONS]))


def dominant_bone_at(y):
    ys = [s[0] for s in SECTIONS]
    i = int(np.clip(np.searchsorted(ys, y), 1, len(ys) - 1))
    t = (y - ys[i - 1]) / (ys[i] - ys[i - 1])
    w = {}
    for k, v in SECTIONS[i - 1][6].items():
        w[k] = w.get(k, 0) + v * (1 - t)
    for k, v in SECTIONS[i][6].items():
        w[k] = w.get(k, 0) + v * t
    return max(w, key=w.get)


def add_loft(B):
    bm = bmesh.new()
    rings = []
    wmap = {}
    for (y, hw, zb, zs, zr, rw, w) in SECTIONS:
        ring = []
        for (x, z) in profile(hw, zb, zs, zr, rw):
            v = bm.verts.new((x, y, z))
            ring.append(v)
            wmap[v] = w
        rings.append(ring)
    n = len(rings[0])
    lay = bm.faces.layers.int.new('c')
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new([a[i], a[j], b[j], b[i]])
            f[lay] = i
    fcap = bm.faces.new(list(reversed(rings[0])))
    fcap[lay] = 100
    tcap = bm.faces.new(rings[-1])
    tcap[lay] = 101
    bm.faces.index_update()
    bm.verts.index_update()
    cls = {}
    for f in bm.faces:
        k = f[lay]
        cls[f.index] = 'body' if k >= 100 else PROFILE_CLASS[k]
    wlist = {v.index: wmap[v] for v in bm.verts}
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    base = len(B.verts)
    for v in bm.verts:
        B.verts.append(tuple(v.co))
        B.vweights.append(dict(wlist[v.index]))
    for f in bm.faces:
        B.faces.append(tuple(base + v.index for v in f.verts))
        B.fclass.append(cls[f.index])
        B.fmode.append('world')          # continuous stud rows along body + tail
    B.pieces.append(('TorsoTail', len(bm.verts), len(bm.faces)))
    bm.free()


# ---------------------------------------------------------------- frill
FRILL_CENTER = Vector((0.0, -3.9, 5.4))
FRILL_R = 1.32                        # radial scale vs the base design
FRILL_TILT = math.radians(-12)       # top leans back
FRILL_T = 0.36


def frill_matrix():
    return Matrix.Translation(FRILL_CENTER) @ Matrix.Rotation(FRILL_TILT, 4, 'X')


def add_frill(B):
    n = 20
    ang = [math.radians(90 + 18 * k) for k in range(n)]
    outer = [FRILL_R * (3.55 if k % 2 == 0 else 3.05) for k in range(n)]
    radii = lambda k: [1.0, 2.3, outer[k] - 0.26, outer[k]]
    bm = bmesh.new()
    lay = bm.faces.layers.int.new('c')
    grid = {}
    for side, y in (('f', -FRILL_T / 2), ('b', FRILL_T / 2)):
        for k in range(n):
            for r_i, r in enumerate(radii(k)):
                grid[side, k, r_i] = bm.verts.new((r * math.cos(ang[k]), y, r * math.sin(ang[k])))
    band_cls = ['frill_dark', 'frill_panel', 'frill_dark']
    for k in range(n):
        k2 = (k + 1) % n
        for r_i in range(3):
            f = bm.faces.new([grid['f', k, r_i], grid['f', k2, r_i], grid['f', k2, r_i + 1], grid['f', k, r_i + 1]])
            f[lay] = r_i
            f = bm.faces.new([grid['b', k, r_i + 1], grid['b', k2, r_i + 1], grid['b', k2, r_i], grid['b', k, r_i]])
            f[lay] = r_i
        f = bm.faces.new([grid['f', k, 3], grid['f', k2, 3], grid['b', k2, 3], grid['b', k, 3]])
        f[lay] = 0
        f = bm.faces.new([grid['b', k, 0], grid['b', k2, 0], grid['f', k2, 0], grid['f', k, 0]])
        f[lay] = 0
    bmesh.ops.transform(bm, matrix=frill_matrix(), verts=bm.verts)
    bm.faces.index_update()
    classes = {f.index: band_cls[f[lay]] for f in bm.faces}
    B.add_bm(bm, 'FrillPlate', 'Frill', classes, 'center')
    # ribs on every tip
    for k in range(0, n, 2):
        a = ang[k]
        if math.sin(a) < -0.6:           # the bottom ribs are buried in the chest
            continue
        r0, r1, hwid, hy = 2.1, FRILL_R * 3.62, 0.2, 0.33
        radial = Vector((math.cos(a), 0, math.sin(a)))
        tang = Vector((-math.sin(a), 0, math.cos(a)))
        pts = []
        for (r, s, yy) in [(r0, -1, -hy), (r0, 1, -hy), (r0, 1, hy), (r0, -1, hy),
                           (r1, -1, -hy), (r1, 1, -hy), (r1, 1, hy), (r1, -1, hy)]:
            p = radial * r + tang * (s * hwid) + Vector((0, yy, 0))
            pts.append(tuple(frill_matrix() @ p))
        add_block(B, f'FrillRib{k // 2}', pts, 'Frill', 'frill_dark', 'frill_dark', bevel=0.06)


# ---------------------------------------------------------------- whole creature
def build_geometry():
    B = Builder()
    add_loft(B)

    # belly slab (pale underside visible from the sides)
    add_block(B, 'Belly', frustum(-1.85, 1.85, -2.9, 2.5, 2.55, 3.05),
              lambda co: ({'Chest': 1.0} if co.y < -0.5 else {'Hips': 1.0}),
              'belly', 'belly_edge', bevel=0.12)

    # neck
    add_block(B, 'Neck', frustum(-1.45, 1.45, -4.75, -2.8, 3.2, 6.0),
              lambda co: ({'Neck': 1.0} if co.y < -3.8 else {'Chest': 1.0}),
              'body', 'body_edge', bevel=0.12)

    # head: cranium, snout, jaw (modelled at base size, scaled by HEAD_SCALE below)
    head_start = len(B.verts)
    add_block(B, 'Cranium', frustum(-1.5, 1.5, -6.8, -3.95, 3.9, 6.9, (0.2, 0.2, 0.15, 0.0)),
              'Head', 'body', 'body_edge', bevel=0.14)
    snout = [(-1.25, -8.0, 4.25), (1.25, -8.0, 4.25), (1.3, -6.5, 4.2), (-1.3, -6.5, 4.2),
             (-1.1, -7.9, 5.3), (1.1, -7.9, 5.3), (1.2, -6.5, 5.75), (-1.2, -6.5, 5.75)]
    add_block(B, 'Snout', snout, 'Head', 'body', 'body_edge', bevel=0.13)
    jaw = frustum(-1.12, 1.12, -7.75, -4.6, 3.45, 4.3, (0.05, 0.05, 0.1, 0.0))
    add_block(B, 'Jaw', jaw, 'Jaw', 'belly', 'belly_edge', bevel=0.1)

    # eyes: white block wrapping the front/side corner + square pupils front and side
    for sx in (1, -1):
        ex = [(0.35, -6.92, 5.72), (1.58, -6.92, 5.72), (1.58, -5.95, 5.72), (0.35, -5.95, 5.72),
              (0.35, -6.92, 6.68), (1.58, -6.92, 6.68), (1.58, -5.95, 6.68), (0.35, -5.95, 6.68)]
        ex = ex if sx > 0 else mirror_x(ex)
        add_block(B, f'EyeWhite{sx}', ex, 'Head', 'eye', 'eye', bevel=0.04)
        pf = frustum(0.52, 1.4, -6.97, -6.9, 5.84, 6.56)
        add_block(B, f'PupilFront{sx}', pf if sx > 0 else mirror_x(pf), 'Head', 'pupil', 'pupil', bevel=0.0)
        ps = frustum(1.57, 1.63, -6.8, -6.1, 5.84, 6.56)
        add_block(B, f'PupilSide{sx}', ps if sx > 0 else mirror_x(ps), 'Head', 'pupil', 'pupil', bevel=0.0)
        # small angular green "ears" beside the brow horns
        ear = [(1.05, -5.6, 6.6), (1.62, -5.6, 6.6), (1.62, -4.7, 6.6), (1.05, -4.7, 6.6),
               (1.35, -5.35, 7.35), (1.7, -5.35, 7.35), (1.7, -5.0, 7.35), (1.35, -5.0, 7.35)]
        add_block(B, f'Ear{sx}', ear if sx > 0 else mirror_x(ear), 'Head', 'body', 'body_edge', bevel=0.06)
        # brow horn
        add_cone(B, f'BrowHorn{sx}', Vector((0.85 * sx, -6.05, 6.75)), 1.75, 0.4,
                 math.radians(22), 'Head', 'horn', sides=6, bend=0.18, tilt_y=math.radians(-8 * sx))
    add_cone(B, 'NoseHorn', Vector((0, -7.35, 5.3)), 0.95, 0.32, math.radians(18), 'Head', 'horn', sides=6)
    for i in range(head_start, len(B.verts)):
        B.verts[i] = head_xf(B.verts[i])

    add_frill(B)

    # legs (L = +X, the creature's left because it faces -Y)
    def leg(prefix, x0, x1, y0, y1, up_z, lower, foot, toes):
        for sx, side in ((1, 'L'), (-1, 'R')):
            def m(c):
                return c if sx > 0 else mirror_x(c)
            add_block(B, f'{prefix}_{side}_Upper', m(frustum(x0, x1, y0, y1, 2.2, up_z, (0.08, 0.0, 0.1, 0.1))),
                      f'{prefix}_{side}_Upper', 'body', 'body_edge', bevel=0.12)
            add_block(B, f'{prefix}_{side}_Lower', m(frustum(*lower)), f'{prefix}_{side}_Lower',
                      'body', 'body_edge', bevel=0.11)
            add_block(B, f'{prefix}_{side}_Foot', m(frustum(*foot, (0.05, 0.05, 0.12, 0.05))),
                      f'{prefix}_{side}_Foot', 'foot', 'foot_edge', bevel=0.09)
            for ti, (tx0, tx1) in enumerate(toes):
                add_block(B, f'{prefix}_{side}_Toe{ti}', m(frustum(tx0, tx1, foot[2] - 0.5, foot[2] + 0.4, 0.0, 0.5,
                                                                    (0.03, 0.03, 0.12, 0.0))),
                          f'{prefix}_{side}_Foot', 'foot', 'foot_edge', bevel=0.07)

    leg('FrontLeg', 1.9, 3.8, -3.1, -0.8, 4.9,
        (2.05, 3.65, -2.85, -1.05, 0.4, 2.8), (1.85, 3.95, -3.05, -0.85, 0.0, 0.75),
        [(1.88, 2.87), (2.93, 3.92)])
    leg('BackLeg', 2.0, 4.0, 0.0, 3.1, 5.2,
        (2.15, 3.85, 0.45, 2.65, 0.4, 2.6), (1.95, 4.05, 0.2, 2.9, 0.0, 0.78),
        [(1.98, 2.97), (3.03, 4.02)])

    # back spikes: cream cones on the ridge, shrinking toward the tail
    spikes = [(-2.3, 1.15), (-0.7, 1.2), (0.9, 1.15), (2.5, 1.05),
              (4.1, 0.95), (5.5, 0.8), (6.9, 0.65), (8.2, 0.5)]
    for i, (y, h) in enumerate(spikes):
        add_cone(B, f'Spike{i}', Vector((0, y, ridge_at(y) - 0.05)), h, 0.28 + 0.14 * h,
                 math.radians(-14), dominant_bone_at(y), 'horn', sides=6, bend=-0.05)

    # fan-triangulate convex n-gons (caps, cone bases) so tangents export for the normal map
    faces, fclass, fmode = [], [], []
    for f, c, m in zip(B.faces, B.fclass, B.fmode):
        tris = [f] if len(f) <= 4 else [(f[0], f[i], f[i + 1]) for i in range(1, len(f) - 1)]
        faces += tris; fclass += [c] * len(tris); fmode += [m] * len(tris)
    B.faces, B.fclass, B.fmode = faces, fclass, fmode
    return B


HEAD_SCALE = 1.25
HEAD_PIVOT = Vector((0.0, -4.2, 4.3))


def head_xf(co):
    return tuple(HEAD_PIVOT + (Vector(co) - HEAD_PIVOT) * HEAD_SCALE)


# ============================================================================ rig
BONES = [
    # name, head, tail, parent, connected, roll-target (bone local Z)
    ('Root', (0, 0, 0), (0, -2.0, 0), None, False, (0, 0, 1)),
    ('Hips', (0, 2.4, 4.4), (0, 0.3, 4.4), 'Root', False, (0, 0, 1)),
    ('Chest', (0, 0.3, 4.4), (0, -3.6, 4.6), 'Hips', True, (0, 0, 1)),
    ('Neck', (0, -3.6, 4.8), (0, -4.6, 5.2), 'Chest', False, (0, 0, 1)),
    ('Head', (0, -4.6, 5.2), head_xf((0, -7.4, 5.6)), 'Neck', False, (0, 0, 1)),
    ('Jaw', head_xf((0, -4.9, 4.0)), head_xf((0, -7.6, 3.9)), 'Head', False, (0, 0, 1)),
    ('Frill', (0, -3.9, 5.4), (0, -2.9, 10.0), 'Head', False, (0, -1, 0)),
    ('Tail_01', (0, 3.8, 4.5), (0, 5.3, 4.5), 'Hips', False, (0, 0, 1)),
    ('Tail_02', (0, 5.3, 4.5), (0, 6.8, 4.55), 'Tail_01', True, (0, 0, 1)),
    ('Tail_03', (0, 6.8, 4.55), (0, 8.1, 4.65), 'Tail_02', True, (0, 0, 1)),
    ('Tail_04', (0, 8.1, 4.65), (0, 9.3, 4.8), 'Tail_03', True, (0, 0, 1)),
]
for prefix, x, y, top, parent in (('FrontLeg', 2.85, -1.95, 4.4, 'Chest'), ('BackLeg', 3.0, 1.55, 4.5, 'Hips')):
    for sx, side in ((1, 'L'), (-1, 'R')):
        X = x * sx
        BONES += [
            (f'{prefix}_{side}_Upper', (X, y, top), (X, y, 2.3), parent, False, (0, -1, 0)),
            (f'{prefix}_{side}_Lower', (X, y, 2.3), (X, y - 0.05, 0.7), f'{prefix}_{side}_Upper', True, (0, -1, 0)),
            (f'{prefix}_{side}_Foot', (X, y - 0.05, 0.7), (X, y - 1.3, 0.3), f'{prefix}_{side}_Lower', True, (0, 0, 1)),
        ]


def build_rig():
    arm = bpy.data.armatures.new('TriceratopsRig')
    arm.display_type = 'OCTAHEDRAL'
    rig = bpy.data.objects.new('Triceratops', arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones
    for name, h, t, parent, conn, roll in BONES:
        b = eb.new(name)
        b.head = Vector(h) * STUD_M
        b.tail = Vector(t) * STUD_M
        b.align_roll(Vector(roll))
        if parent:
            b.parent = eb[parent]
            b.use_connect = conn
        b.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


# ============================================================================ UV atlas + textures
def face_basis(n):
    n = Vector(n).normalized()
    if abs(n.z) < 0.75:
        v = (Vector((0, 0, 1)) - n * n.z).normalized()
    else:
        v = (Vector((0, -1, 0)) - n * (-n.y)).normalized()
    u = v.cross(n).normalized()
    return u, v, n


def shelf_pack(sizes, width):
    order = sorted(range(len(sizes)), key=lambda i: -sizes[i][1])
    pos = [None] * len(sizes)
    x = y = shelf = 0
    for i in order:
        w, h = sizes[i]
        if x + w > width:
            y += shelf
            x = shelf = 0
        pos[i] = (x, y)
        x += w
        shelf = max(shelf, h)
    return pos, y + shelf


def build_uvs_and_textures(B, tile, pitch, stud_height):
    verts = [Vector(v) for v in B.verts]
    swatch_classes = list(PALETTE.keys())
    SW = 24                                   # swatch cell size (px), top row of atlas
    avail_h = ATLAS - SW - 4

    islands = []                              # (face index, 2D coords, umin, vmin, du, dv, basis)
    for fi, f in enumerate(B.faces):
        pts = [verts[i] for i in f]
        n = Vector((0, 0, 0))
        for i in range(len(pts)):           # Newell normal
            a, b = pts[i], pts[(i + 1) % len(pts)]
            n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
        u, v, n = face_basis(n)
        uv2 = [(p.dot(u), p.dot(v)) for p in pts]
        us = [q[0] for q in uv2]; vs = [q[1] for q in uv2]
        islands.append(dict(fi=fi, uv2=uv2, umin=min(us), vmin=min(vs), du=max(us) - min(us),
                            dv=max(vs) - min(vs), basis=(u, v, n), center=sum(pts, Vector()) / len(pts)))

    studded = [isl for isl in islands if B.fclass[isl['fi']] in STUDDED]
    lo, hi = 5.0, 400.0
    for _ in range(40):                       # largest uniform texel density that fits
        D = (lo + hi) / 2
        sizes = [(int(math.ceil(isl['du'] * D)) + 2 * PAD, int(math.ceil(isl['dv'] * D)) + 2 * PAD) for isl in studded]
        _, used = shelf_pack(sizes, ATLAS)
        if used <= avail_h:
            lo = D
        else:
            hi = D
    D = lo
    sizes = [(int(math.ceil(isl['du'] * D)) + 2 * PAD, int(math.ceil(isl['dv'] * D)) + 2 * PAD) for isl in studded]
    pos, used = shelf_pack(sizes, ATLAS)

    color = np.zeros((ATLAS, ATLAS, 3), np.float32)
    normal = np.zeros((ATLAS, ATLAS, 3), np.float32); normal[..., 2] = 1.0
    rough = np.full((ATLAS, ATLAS), 0.5, np.float32)
    filled = np.zeros((ATLAS, ATLAS), bool)
    srgb = {k: np.array(c, np.float32) / 255.0 for k, c in PALETTE.items()}

    # swatches for flat colours
    swatch_rect = {}
    for i, k in enumerate(swatch_classes):
        x0, y0 = i * SW, ATLAS - SW
        color[y0:y0 + SW, x0:x0 + SW] = srgb[k]
        rough[y0:y0 + SW, x0:x0 + SW] = ROUGHNESS.get(k, 0.55)
        filled[y0:y0 + SW, x0:x0 + SW] = True
        swatch_rect[k] = (x0, y0)

    face_uvs = {}
    eps = 0.5 / D
    for isl, (w, h), (x0, y0) in zip(studded, sizes, pos):
        fi = isl['fi']
        face_uvs[fi] = [((x0 + PAD + (a - isl['umin']) * D) / ATLAS, (y0 + PAD + (b - isl['vmin']) * D) / ATLAS)
                        for a, b in isl['uv2']]
        cols = np.arange(x0, x0 + w); rows = np.arange(y0, y0 + h)
        cc, rr = np.meshgrid(cols, rows)
        uu = isl['umin'] + (cc + 0.5 - x0 - PAD) / D
        vv = isl['vmin'] + (rr + 0.5 - y0 - PAD) / D
        if B.fmode[fi] == 'center':
            u, v, _ = isl['basis']
            au, av = isl['center'].dot(u), isl['center'].dot(v)
            s = (uu - au) / pitch + 0.5; t = (vv - av) / pitch + 0.5
        else:
            s = uu / pitch; t = vv / pitch
        hgt = sample_wrap(tile, s, t)
        dhds = (sample_wrap(tile, s + eps / pitch, t) - sample_wrap(tile, s - eps / pitch, t)) / (2 * eps)
        dhdt = (sample_wrap(tile, s, t + eps / pitch) - sample_wrap(tile, s, t - eps / pitch)) / (2 * eps)
        nx, ny = -dhds * stud_height, -dhdt * stud_height
        inv = 1.0 / np.sqrt(nx * nx + ny * ny + 1)
        k = B.fclass[fi]
        color[y0:y0 + h, x0:x0 + w] = srgb[k] * (0.9 + 0.1 * hgt)[..., None]
        normal[y0:y0 + h, x0:x0 + w] = np.stack([nx * inv, ny * inv, inv], -1)
        rough[y0:y0 + h, x0:x0 + w] = 0.5 - 0.05 * hgt
        filled[y0:y0 + h, x0:x0 + w] = True

    # flat faces: projection shrunk into the middle of their colour swatch
    for isl in islands:
        fi = isl['fi']
        if fi in face_uvs:
            continue
        x0, y0 = swatch_rect[B.fclass[fi]]
        span = max(isl['du'], isl['dv'], 1e-6)
        sc = (SW - 8) / span
        face_uvs[fi] = [((x0 + 4 + (a - isl['umin']) * sc) / ATLAS, (y0 + 4 + (b - isl['vmin']) * sc) / ATLAS)
                        for a, b in isl['uv2']]

    # dilate into the unused gutter so mips never bleed black
    for _ in range(12):
        if filled.all():
            break
        shifted = []
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            shifted.append((np.roll(filled, (dy, dx), (0, 1)), np.roll(color, (dy, dx), (0, 1)),
                            np.roll(normal, (dy, dx), (0, 1)), np.roll(rough, (dy, dx), (0, 1))))
        grow = np.zeros_like(filled)
        for f2, c2, n2, r2 in shifted:
            m = f2 & ~filled & ~grow
            color[m] = c2[m]; normal[m] = n2[m]; rough[m] = r2[m]
            grow |= m
        filled |= grow
    color[~filled] = srgb['body']

    stats = dict(texel_density_px_per_stud=round(D, 2), studded_islands=len(studded),
                 atlas_rows_used=int(used), atlas=ATLAS, stud_pitch_studs=pitch)
    return face_uvs, color, normal, rough, stats


def save_png(arr, path, mode):
    from PIL import Image
    a = np.clip(arr[::-1] * 255 + 0.5, 0, 255).astype(np.uint8)   # row 0 = top in PNG
    Image.fromarray(a, mode).save(path)


# ============================================================================ mesh object
def build_mesh_object(B, face_uvs, rig, tex_paths):
    me = bpy.data.meshes.new('TriceratopsMesh')
    me.from_pydata([tuple(Vector(v) * STUD_M) for v in B.verts], [], B.faces)
    me.update()
    uv = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li, uvco in zip(poly.loop_indices, face_uvs[poly.index]):
            uv.data[li].uv = uvco
        poly.use_smooth = False
    obj = bpy.data.objects.new('TriceratopsMesh', me)
    bpy.context.scene.collection.objects.link(obj)

    for name, *_ in BONES:
        obj.vertex_groups.new(name=name)
    for vi, w in enumerate(B.vweights):
        tot = sum(w.values())
        for bone, val in w.items():
            obj.vertex_groups[bone].add([vi], val / tot, 'REPLACE')

    obj.parent = rig
    mod = obj.modifiers.new('Armature', 'ARMATURE')
    mod.object = rig

    mat = bpy.data.materials.new('MAT-Triceratops')
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes['Principled BSDF']
    bsdf.inputs['Metallic'].default_value = 0.0

    def tex(path, colorspace, loc):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = bpy.data.images.load(path, check_existing=True)
        n.image.colorspace_settings.name = colorspace
        n.location = loc
        return n
    c = tex(tex_paths['color'], 'sRGB', (-600, 300))
    r = tex(tex_paths['roughness'], 'Non-Color', (-600, 0))
    nm = tex(tex_paths['normal'], 'Non-Color', (-600, -300))
    nmap = nt.nodes.new('ShaderNodeNormalMap'); nmap.location = (-300, -300)
    nt.links.new(c.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(r.outputs['Color'], bsdf.inputs['Roughness'])
    nt.links.new(nm.outputs['Color'], nmap.inputs['Color'])
    nt.links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])
    me.materials.append(mat)
    return obj


# ============================================================================ animation
FPS = 30


def world_axis_quat(pb, axis, angle):
    """Rotation about a world axis expressed in the bone's rest-local frame."""
    local = pb.bone.matrix_local.to_3x3().inverted() @ Vector(axis)
    return Quaternion(local.normalized(), angle)


def pose(rig, frame, rots, locs=None):
    """rots: {bone: [(axis, angle), ...]} world axes; locs: {bone: world offset in studs}."""
    for pb in rig.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        q = Quaternion()
        for axis, ang in rots.get(pb.name, []):
            q = world_axis_quat(pb, axis, ang) @ q
        pb.rotation_quaternion = q
        off = (locs or {}).get(pb.name)
        pb.location = (pb.bone.matrix_local.to_3x3().inverted() @ (Vector(off) * STUD_M)) if off else Vector()
        pb.keyframe_insert('rotation_quaternion', frame=frame)
        pb.keyframe_insert('location', frame=frame)


X, Z, Y = (1, 0, 0), (0, 0, 1), (0, 1, 0)
LEGS = ['FrontLeg_L', 'FrontLeg_R', 'BackLeg_L', 'BackLeg_R']


def leg_rots(r, prefix, swing, bend):
    """swing > 0 swings the foot backward; bend lifts the foot; foot stays roughly flat."""
    r[f'{prefix}_Upper'] = [(X, swing)]
    r[f'{prefix}_Lower'] = [(X, bend)]
    r[f'{prefix}_Foot'] = [(X, -(swing + bend) * 0.85)]


def gait_frame(ph, amp, lift, phases, bob, tail_amp, head_pitch, head_amp, chest_rock):
    r, l = {}, {}
    for leg in LEGS:
        a = ph + phases[leg]
        swing = amp * math.sin(a)
        bend = lift * max(0.0, -math.cos(a))        # lift during the forward swing
        leg_rots(r, leg, swing, bend)
    l['Hips'] = (0, 0, bob * math.cos(2 * ph))
    r['Hips'] = [(X, chest_rock * math.sin(ph))]
    r['Chest'] = [(Z, 0.03 * math.sin(ph))]
    r['Neck'] = [(X, head_pitch * 0.4)]
    r['Head'] = [(X, head_pitch + head_amp * math.sin(2 * ph + 0.6))]
    for i in range(4):
        r[f'Tail_0{i + 1}'] = [(Z, tail_amp * math.sin(ph - 0.7 * (i + 1))), (X, -0.02 * (i + 1))]
    return r, l


def make_action(rig, name, frames, fn, cyclic=True, step=2):
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    rig.animation_data_create()
    rig.animation_data.action = act
    keys = list(range(0, frames + 1, step))
    if keys[-1] != frames:
        keys.append(frames)
    for f in keys:
        r, l = fn(f, frames)
        pose(rig, f + 1, r, l)
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR' if cyclic else 'BEZIER'
    act.frame_range = (1, frames + 1)
    act.use_frame_range = True
    act.use_cyclic = cyclic
    return act


def build_animations(rig):
    acts = {}

    def idle(f, n):
        ph = 2 * math.pi * f / n
        r = {
            'Chest': [(X, 0.02 * math.sin(ph))],
            'Neck': [(X, -0.03 * math.sin(ph))],
            'Head': [(Z, 0.14 * math.sin(ph)), (X, 0.04 * math.sin(2 * ph))],
            'Jaw': [(X, -0.06 * max(0.0, math.sin(2 * ph + 1.0)) ** 4)],
        }
        for i in range(4):
            r[f'Tail_0{i + 1}'] = [(Z, 0.07 * math.sin(ph - 0.6 * (i + 1)))]
        for leg in LEGS:
            leg_rots(r, leg, 0.0, 0.0)
        return r, {'Hips': (0, 0, -0.03 * (1 - math.cos(2 * ph)) / 2)}
    acts['Idle'] = make_action(rig, 'Idle', 90, idle)

    walk_ph = {'FrontLeg_L': 0.0, 'BackLeg_R': 0.0, 'FrontLeg_R': math.pi, 'BackLeg_L': math.pi}
    acts['Walk'] = make_action(rig, 'Walk', 36, lambda f, n: gait_frame(
        2 * math.pi * f / n, 0.38, 0.55, walk_ph, 0.07, 0.12, 0.05, 0.03, 0.015))

    run_ph = {'FrontLeg_L': 0.0, 'FrontLeg_R': 0.45, 'BackLeg_L': math.pi, 'BackLeg_R': math.pi + 0.45}
    acts['Run'] = make_action(rig, 'Run', 20, lambda f, n: gait_frame(
        2 * math.pi * f / n, 0.62, 0.9, run_ph, 0.16, 0.08, 0.16, 0.05, 0.06))

    # attack: brace -> lower horns and charge -> upward gore -> recover
    KEYS = [  # frame, hips offset (y,z), hips pitch, head pitch, neck pitch, jaw, front swing, back swing, tail
        (0, (0.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        (10, (0.45, -0.12), -0.06, -0.25, -0.1, -0.12, -0.15, 0.2, 0.15),
        (18, (-0.7, -0.2), 0.08, 0.45, 0.15, 0.0, 0.35, -0.3, -0.1),
        (23, (-0.9, -0.05), 0.02, -0.35, -0.12, -0.3, 0.2, -0.35, 0.1),
        (31, (-0.3, 0.0), 0.0, -0.08, 0.0, -0.05, 0.05, -0.1, 0.0),
        (40, (0.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
    ]
    act = bpy.data.actions.new('Attack')
    act.use_fake_user = True
    rig.animation_data.action = act
    for fr, (hy, hz), hp, hd, nk, jw, fs, bs, tl in KEYS:
        r = {'Hips': [(X, hp)], 'Head': [(X, hd)], 'Neck': [(X, nk)], 'Jaw': [(X, jw)]}
        for side in 'LR':
            leg_rots(r, f'FrontLeg_{side}', fs, 0.0)
            leg_rots(r, f'BackLeg_{side}', bs, 0.0)
        for i in range(4):
            r[f'Tail_0{i + 1}'] = [(X, -tl * 0.5)]
        pose(rig, fr + 1, r, {'Hips': (0, hy, hz)})
    act.frame_range = (1, 41)
    act.use_frame_range = True
    acts['Attack'] = act

    rig.animation_data.action = None
    for pb in rig.pose.bones:
        pb.rotation_quaternion = Quaternion(); pb.location = Vector()
    return acts


# ============================================================================ checks
def validate(B, obj, rig, stats):
    me = obj.data
    tris = sum(len(p.vertices) - 2 for p in me.polygons)
    # every piece was built closed and normal-recalculated; verify no degenerate faces
    degenerate = sum(1 for p in me.polygons if p.area < 1e-9)
    groups = {g.index: g.name for g in obj.vertex_groups}
    used = set()
    max_infl = 0
    bad_sum = 0
    for v in me.vertices:
        ws = [g for g in v.groups if g.weight > 0]
        max_infl = max(max_infl, len(ws))
        if abs(sum(g.weight for g in ws) - 1) > 1e-4:
            bad_sum += 1
        used.update(groups[g.group] for g in ws)
    unused = [b.name for b in rig.data.bones if b.name not in used and b.name != 'Root']
    dims = [round(d / STUD_M, 2) for d in obj.dimensions]
    head_front = min(v.co.y for v in me.vertices) / STUD_M
    tail_back = max(v.co.y for v in me.vertices) / STUD_M
    report = dict(
        triangles=tris, vertices=len(me.vertices), polygons=len(me.polygons), degenerate_faces=degenerate,
        pieces=len(B.pieces), bones=len(rig.data.bones), max_influences=max_infl,
        vertices_with_unnormalised_weights=bad_sum, unused_bones=unused,
        size_studs_xyz=dims, size_m_xyz=[round(d, 3) for d in obj.dimensions],
        faces_minus_y=head_front < 0 < tail_back, min_z=round(min(v.co.z for v in me.vertices), 4),
        texture=stats,
    )
    assert tris <= 20000, tris
    assert degenerate == 0 and max_infl <= 4 and bad_sum == 0 and not unused, report
    return report


# ============================================================================ main
def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument('--stud-tile', help='grayscale tiling height map (white = raised), one stud per tile')
    ap.add_argument('--stud-pitch', type=float, default=1.4, help='stud spacing in Roblox studs')
    ap.add_argument('--stud-height', type=float, default=0.045, help='stud relief height in studs (normal strength)')
    args = ap.parse_args(argv)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0

    tile = load_tile(args.stud_tile) if args.stud_tile else default_stud_tile()
    tex_dir = os.path.join(ASSET, 'textures')
    save_png(np.repeat(tile[..., None], 3, -1), os.path.join(tex_dir, 'StudTile_Height.png'), 'RGB')

    B = build_geometry()
    face_uvs, color, normal, rough, stats = build_uvs_and_textures(B, tile, args.stud_pitch, args.stud_height)
    paths = {k: os.path.join(tex_dir, f'Triceratops_{k.capitalize()}.png') for k in ('color', 'normal', 'roughness')}
    save_png(color, paths['color'], 'RGB')
    save_png(normal * 0.5 + 0.5, paths['normal'], 'RGB')
    save_png(np.repeat(rough[..., None], 3, -1), paths['roughness'], 'RGB')

    rig = build_rig()
    obj = build_mesh_object(B, face_uvs, rig, paths)
    report = validate(B, obj, rig, stats)
    acts = build_animations(rig)
    report['animations'] = {k: [int(a.frame_range[0]), int(a.frame_range[1])] for k, a in acts.items()}
    report['fps'] = FPS
    scene.frame_start, scene.frame_end = 1, 91

    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ASSET, 'Triceratops.blend'), relative_remap=True)

    def export(path, action=None, embed=True):
        for o in bpy.context.scene.objects:
            o.select_set(True)
        rig.animation_data.action = action
        if action is not None:           # bake exactly the action's frames; take is named after it
            scene.frame_start, scene.frame_end = (int(f) for f in action.frame_range)
            scene.name = action.name
        bpy.ops.export_scene.fbx(
            filepath=path, use_selection=False, object_types={'ARMATURE', 'MESH'},
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', global_scale=1.0,
            axis_forward='-Z', axis_up='Y', bake_space_transform=False,
            use_mesh_modifiers=False, mesh_smooth_type='FACE', use_tspace=True,
            add_leaf_bones=False, primary_bone_axis='Y', secondary_bone_axis='X',
            use_armature_deform_only=False, armature_nodetype='NULL',
            bake_anim=action is not None, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
            bake_anim_step=1.0, bake_anim_simplify_factor=0.0,
            embed_textures=embed, path_mode='COPY' if embed else 'STRIP')
        rig.animation_data.action = None
        scene.name, scene.frame_start, scene.frame_end = 'Scene', 1, 91

    export(os.path.join(ASSET, 'Triceratops.fbx'))
    for name, act in acts.items():
        export(os.path.join(ASSET, 'animations', f'Triceratops_{name}.fbx'), act, embed=False)

    with open(os.path.join(ASSET, 'validation', 'build_report.json'), 'w') as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
