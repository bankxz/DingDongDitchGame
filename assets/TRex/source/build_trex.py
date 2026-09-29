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
         'TEETH', 'EYE', 'LAVA', 'BONE_DARK']
TILES_PER_ROW = 4
STUDS_PER_TILE = 8
ATLAS_STUDS = STUDS_PER_TILE * TILES_PER_ROW

rng = random.Random(1234)
PARTS = []   # (bmesh-ready verts, faces, uvs, bone)


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
    PARTS.append((verts, fl, uvl, bone))


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
    PARTS.append((verts, faces, uvs, bone))


def mirror_x(fn, center, *a, bone='', rot=(0, 0, 0), **kw):
    """Create a part on the left (+X, .L bone) and its mirror on the right (-X, .R bone)."""
    for sgn, suf in ((1, '.L'), (-1, '.R')):
        c = (center[0] * sgn, center[1], center[2])
        r = (rot[0], rot[1] * sgn, rot[2] * sgn)
        b = bone + suf if bone.endswith(('Thigh', 'Shin', 'Foot', 'UpperArm', 'Forearm')) else bone
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


# --------------------------------------------------------------------------- the model

JAW_PIVOT = (0, -15.6, 10.4)
JAW_OPEN = (36, 0, 0)          # mouth held open like the reference (bind pose)


def build_head():
    H = 'Head'
    # upper snout (bone), stepped like the reference
    box((0, -20.4, 12.0), (6.2, 5.2, 2.2), 'BONE', H)
    box((0, -23.3, 11.8), (5.2, 1.2, 1.9), 'BONE', H)                 # snout front plate
    box((0, -23.6, 12.6), (3.2, 0.8, 1.0), 'BONE_LIGHT', H)           # nose tip
    mbox((1.2, -23.3, 13.1), (1.1, 1.0, 0.7), 'BONE_LIGHT', H)        # nostrils
    box((0, -19.8, 13.35), (3.6, 3.4, 0.6), 'CHARCOAL', H)            # dark ridge on snout
    mbox((3.35, -20.6, 11.4), (0.7, 5.0, 1.1), 'BONE_DARK', H)        # upper lip edge
    mbox((2.9, -22.2, 13.2), (1.2, 1.4, 0.6), 'BONE', H)              # snout bumps
    # forehead / brow
    box((0, -16.9, 13.7), (7.0, 3.6, 2.6), 'BONE', H)
    mbox((3.2, -18.4, 14.0), (1.6, 2.0, 1.6), 'BONE_LIGHT', H)        # brow ridge over the eye
    mbox((3.35, -17.9, 12.5), (1.0, 2.0, 1.4), 'CHARCOAL', H)         # eye socket
    mbox((3.75, -18.2, 12.55), (0.4, 0.7, 0.6), 'EYE', H)             # glowing red eyes
    # dark crown + horns on top (front-head view)
    box((0, -15.6, 15.3), (6.0, 3.4, 1.2), 'CHARCOAL', H)
    mbox((2.4, -15.8, 16.5), (1.4, 1.4, 1.6), 'CHARCOAL', H)
    mbox((1.2, -16.9, 15.9), (1.2, 1.2, 0.9), 'CHARCOAL', H)
    box((0, -16.8, 16.4), (1.2, 1.2, 1.6), 'BONE_LIGHT', H)           # centre bone horn
    mbox((3.4, -15.2, 14.6), (1.2, 2.2, 1.4), 'BONE', H)              # side crest
    # cheeks + back of skull
    mbox((3.35, -15.4, 11.6), (1.4, 3.4, 3.2), 'BONE', H)
    mbox((3.8, -14.6, 12.9), (0.8, 1.6, 1.4), 'BONE_DARK', H)
    box((0, -13.9, 12.6), (6.4, 2.6, 4.4), 'MIX', H)
    # mouth roof + throat cavity
    box((0, -19.6, 10.7), (5.4, 6.2, 0.4), 'MOUTH', H)
    box((0, -16.3, 10.0), (4.6, 1.6, 1.8), 'MOUTH', H)
    # upper teeth: front row + side rows, big fangs at the corners
    for x, ln in ((-1.9, 1.6), (-0.95, 1.1), (0.0, 1.3), (0.95, 1.1), (1.9, 1.6)):
        spike((x, -23.35, 10.85), (0.62, 0.6), (0, 0, -ln), 'TEETH', H)
    for y, ln in ((-22.2, 1.9), (-21.0, 1.2), (-19.8, 1.5), (-18.6, 1.0), (-17.5, 1.2)):
        mspike((2.75, y, 10.8), (0.62, 0.7), (0, 0, -ln), 'TEETH', H)


def build_jaw():
    J = 'Jaw'
    kw = dict(pivot=JAW_PIVOT, pivot_rot=JAW_OPEN)
    box((0, -19.6, 9.2), (5.8, 7.2, 1.7), 'BONE', J, **kw)
    box((0, -23.2, 9.5), (5.2, 1.2, 2.1), 'BONE', J, **kw)            # chin plate
    box((0, -21.2, 8.2), (3.6, 3.2, 0.6), 'BONE_DARK', J, **kw)       # under-chin block
    mbox((3.1, -20.5, 9.6), (0.6, 5.0, 1.2), 'BONE_DARK', J, **kw)    # jaw side edge
    mbox((2.9, -17.2, 9.4), (1.0, 2.4, 2.2), 'BONE', J, **kw)         # jaw corner plate
    box((0, -16.3, 9.3), (5.2, 2.2, 2.0), 'CHARCOAL', J, **kw)        # jaw root
    box((0, -19.5, 10.15), (4.6, 6.6, 0.3), 'MOUTH', J, **kw)
    box((0, -18.9, 10.45), (2.6, 5.4, 0.5), 'TONGUE', J, **kw)
    for x, ln in ((-1.6, 1.3), (0.0, 1.1), (1.6, 1.3)):
        spike((x, -23.2, 10.5), (0.6, 0.6), (0, 0, ln), 'TEETH', J, **kw)
    for y, ln in ((-22.0, 1.5), (-20.7, 1.0), (-19.4, 1.3), (-18.1, 0.9)):
        mspike((2.55, y, 10.2), (0.6, 0.7), (0, 0, ln), 'TEETH', J, **kw)


def build_neck_torso():
    box((0, -12.6, 10.6), (7.2, 3.2, 6.0), 'MIX', 'Neck')
    box((0, -13.2, 7.8), (3.4, 3.0, 0.8), 'BONE_DARK', 'Neck')        # throat plate
    mbox((3.3, -12.6, 13.2), (1.4, 2.4, 1.4), 'CHARCOAL', 'Neck')
    box((0, -12.4, 13.9), (4.0, 2.2, 1.0), 'CHARCOAL', 'Neck')

    box((0, -9.4, 9.6), (11.0, 5.0, 6.6), 'MIX', 'Chest')             # chest
    box((0, -11.6, 7.6), (8.0, 1.8, 3.0), 'MAROON', 'Chest')          # pec
    box((0, -9.4, 13.2), (8.4, 4.6, 1.0), 'CHARCOAL', 'Chest')
    box((0, -4.3, 9.3), (12.6, 6.2, 7.4), 'MIX', 'Spine')             # belly barrel
    box((0, -4.3, 13.3), (9.4, 5.8, 1.0), 'CHARCOAL', 'Spine')
    box((0, 2.0, 9.4), (11.4, 6.6, 6.6), 'MIX', 'Hips')               # hips
    box((0, 2.0, 13.0), (8.4, 6.0, 1.0), 'CHARCOAL', 'Hips')
    # bone belly strip (bottom view)
    box((0, -9.4, 6.2), (4.0, 4.6, 0.5), 'BONE', 'Chest')
    box((0, -4.3, 5.5), (4.6, 5.8, 0.5), 'BONE', 'Spine')
    box((0, 2.0, 6.0), (4.0, 6.0, 0.5), 'BONE', 'Hips')

    # big bone ribs wrapping the flanks in front of the thigh, curving like "(" (hero view)
    for y in (-13.0, -10.8, -8.6, -6.4):
        b = 'Chest' if y < -7.2 else 'Spine'
        mbox((5.5, y, 12.3), (1.8, 0.95, 1.1), 'BONE', b, rot=(0, 35, 0))
        mbox((6.5, y + 0.1, 10.9), (1.2, 0.95, 2.8), 'BONE', b, rot=(-6, 12, 0))
        mbox((6.85, y + 0.4, 8.4), (1.1, 0.95, 2.6), 'BONE', b, rot=(-12, 0, 0))
        mbox((6.4, y + 0.9, 6.3), (1.1, 0.9, 1.8), 'BONE_DARK', b, rot=(-22, -22, 0))
    # shoulder bone plates
    mbox((5.4, -13.2, 9.6), (1.2, 1.4, 2.6), 'BONE', 'Chest', rot=(0, 15, 0))

    # chunky voxel bumps on the flanks and back (silhouette roughness of the reference)
    tiles = ['MIX', 'CHARCOAL', 'MAROON', 'MIX', 'DARK']
    for i in range(64):
        y = rng.uniform(-13.0, 5.2)
        z = rng.uniform(6.2, 12.8)
        s = rng.choice((0.8, 1.0, 1.0, 1.2, 1.5))
        half = 6.3 if -7.4 < y < -1.2 else (5.5 if y < -7.4 else 5.7)
        side = 1 if i % 2 else -1
        bone = 'Chest' if y < -7.2 else ('Spine' if y < -1.2 else 'Hips')
        box((side * (half + rng.uniform(0.0, 0.35)), y, z), (s, s, s), rng.choice(tiles), bone)
    for i in range(22):
        y = rng.uniform(-12.5, 5.0)
        x = rng.choice((-1, 1)) * rng.uniform(1.2, 4.6)
        s = rng.choice((0.8, 1.0, 1.2, 1.5))
        bone = 'Chest' if y < -7.2 else ('Spine' if y < -1.2 else 'Hips')
        box((x, y, 13.5 + s * 0.2), (s, s, s), rng.choice(tiles), bone)
    for i in range(12):                                   # neck bumps
        y = rng.uniform(-14.2, -11.2)
        side = rng.choice((-1, 1))
        z = rng.uniform(8.2, 13.4)
        box((side * 3.7, y, z), (0.9, 1.0, 1.0), rng.choice(tiles), 'Neck')


# spine plates: (y, height, bone) -- big bone plates down the back like the reference
BACK_SPIKES = [(-15.3, 2.0, 'Head'), (-12.6, 4.0, 'Neck'), (-9.6, 7.0, 'Chest'), (-5.9, 6.6, 'Spine'),
               (-2.3, 5.8, 'Spine'), (1.2, 4.8, 'Hips'), (4.4, 3.8, 'Hips')]


def build_back_spikes():
    """Big chunky bone slabs down the back, leaning backwards, with gaps between (side views)."""
    for y, h, bone in BACK_SPIKES:
        base = {'Head': 15.6, 'Neck': 14.2}.get(bone, 13.4)
        box((0, y, base + h * 0.28), (1.7, 2.8, h * 0.6), 'BONE_LIGHT', bone, rot=(-18, 0, 0))
        box((0, y + 0.7, base + h * 0.72), (1.3, 1.9, h * 0.42), 'BONE_LIGHT', bone, rot=(-26, 0, 0))
        box((0, y - 0.9, base + h * 0.2), (1.4, 1.0, h * 0.35), 'BONE', bone, rot=(-18, 0, 0))
        # lateral bone spikes flanking the spine at the shoulders and hips (top/back views)
        if bone in ('Chest', 'Hips'):
            mbox((3.0, y + 0.6, 13.9 + h * 0.15), (1.2, 1.6, 1.4 + h * 0.3), 'BONE', bone, rot=(-15, 12, 0))


TAIL_PTS = [(0, 4.6, 10.0), (0, 9.0, 9.4), (0, 13.4, 8.2), (0, 17.4, 6.8),
            (0, 21.0, 5.4), (0, 24.2, 4.2), (0, 27.0, 3.3)]
TAIL_W = [9.6, 7.4, 5.8, 4.4, 3.2, 2.2, 1.2]
TAIL_H = [6.0, 5.0, 4.0, 3.2, 2.4, 1.7, 1.0]


def build_tail():
    for i in range(6):
        a, b = Vector(TAIL_PTS[i]), Vector(TAIL_PTS[i + 1])
        mid = (a + b) / 2
        ln = (b - a).length
        pitch = math.degrees(math.atan2(b.z - a.z, b.y - a.y))
        w = (TAIL_W[i] + TAIL_W[i + 1]) / 2
        h = (TAIL_H[i] + TAIL_H[i + 1]) / 2
        bone = f'Tail{i + 1}'
        rot = (pitch, 0, 0)
        box(tuple(mid), (w, ln + 0.6, h), 'MIX', bone, rot=rot)
        # stepped voxel ring (slightly wider, shorter block) for the chunky outline
        box(tuple(mid + Vector((0, 0.3, 0.1))), (w + 0.6, ln * 0.45, h * 0.7), 'MAROON' if i % 2 else 'CHARCOAL', bone, rot=rot)
        # bone plates along the lower flank (side views)
        mbox((w / 2 + 0.05, mid.y, mid.z - h * 0.28), (0.5, ln * 0.8, h * 0.3), 'BONE_DARK', bone, rot=rot)
        # bone vertebra strip down the top of the tail (back/top views)
        box((0, mid.y, mid.z + h / 2 + 0.15), (max(w * 0.22, 0.6), ln * 0.9, 0.5), 'BONE_LIGHT', bone, rot=rot)
        # belly strip
        box((0, mid.y, mid.z - h / 2 - 0.1), (max(w * 0.4, 0.8), ln, 0.4), 'BONE', bone, rot=rot)
        # dorsal bone spikes, two per segment, shrinking toward the tip
        for t in (0.5,):
            p = a.lerp(b, t)
            hh = h * 0.5 + 0.6
            ztop = p.z + (TAIL_H[i] * (1 - t) + TAIL_H[i + 1] * t) / 2
            box((0, p.y, ztop + hh * 0.4), (max(0.6, w * 0.17), 1.5, hh * 0.8), 'BONE_LIGHT', bone, rot=(pitch - 18, 0, 0))
            box((0, p.y + 0.35, ztop + hh * 0.95), (max(0.45, w * 0.12), 0.9, hh * 0.45), 'BONE_LIGHT', bone, rot=(pitch - 28, 0, 0))
    spike((0, 27.3, 3.3), (1.0, 0.8), (0, 1.8, -0.2), 'BONE', 'Tail6', rot=(0, 0, 0))


def build_leg():
    # thigh: the big chunky block on the flank
    mbox((6.6, -2.2, 9.2), (3.0, 6.6, 6.4), 'MIX', 'Thigh')
    mbox((6.8, -2.0, 12.3), (2.6, 4.8, 1.0), 'CHARCOAL', 'Thigh')
    mbox((8.2, -2.4, 8.8), (0.6, 4.2, 4.6), 'CHARCOAL', 'Thigh')
    mbox((6.5, -2.8, 5.6), (2.5, 3.8, 1.6), 'MAROON', 'Thigh')
    for i in range(8):
        y = rng.uniform(-5.2, 0.8)
        z = rng.uniform(6.4, 11.8)
        mbox((8.4, y, z), (0.7, 1.0, 1.0), rng.choice(['MIX', 'CHARCOAL', 'MAROON']), 'Thigh')
    # shin + ankle
    mbox((6.4, -1.9, 3.3), (2.8, 2.8, 4.4), 'DARK', 'Shin', rot=(-12, 0, 0))
    mbox((6.4, -0.8, 4.0), (1.7, 1.0, 1.8), 'MAROON', 'Shin', rot=(-12, 0, 0))
    # foot + big bone toes (front/hero views)
    mbox((6.4, -3.0, 0.7), (3.8, 4.4, 1.4), 'DARK', 'Foot')
    for dx in (-1.3, 0.0, 1.3):
        mbox((6.4 + dx, -5.7, 0.8), (1.15, 1.8, 1.6), 'BONE', 'Foot')
        mspike((6.4 + dx, -6.55, 0.55), (0.9, 0.6), (0, -1.1, -0.45), 'TEETH', 'Foot')
    mbox((6.4, -0.6, 0.5), (1.0, 1.0, 1.0), 'BONE', 'Foot')          # dew claw


def build_arm():
    mbox((4.9, -12.9, 7.4), (1.6, 1.8, 2.8), 'DARK', 'UpperArm', rot=(20, 0, 0))
    mbox((5.1, -12.4, 8.5), (0.6, 1.0, 1.0), 'BONE', 'UpperArm')        # elbow knob
    mbox((5.0, -14.5, 5.2), (1.4, 1.4, 2.8), 'CHARCOAL', 'Forearm', rot=(-25, 0, 0))
    mbox((5.0, -15.4, 3.7), (1.6, 1.8, 1.0), 'DARK', 'Forearm')
    for dx in (-0.5, 0.0, 0.5):
        mspike((5.0 + dx, -16.0, 3.3), (0.45, 0.6), (0, -0.5, -1.1), 'TEETH', 'Forearm')


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
    BONES[f'UpperArm.{s}'] = ((4.8 * sgn, -12.2, 8.6), (5.0 * sgn, -13.8, 6.4), 'Chest')
    BONES[f'Forearm.{s}'] = ((5.0 * sgn, -13.8, 6.4), (5.0 * sgn, -15.6, 3.4), f'UpperArm.{s}')


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
    bsdf.inputs['Emission Strength'].default_value = 4.0
    bsdf.inputs['Roughness'].default_value = 0.65
    return mat


def make_mesh(arm):
    me = bpy.data.meshes.new('TRexMesh')
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new('UVMap')
    deform = bm.verts.layers.deform.verify()
    bone_index = {name: i for i, name in enumerate(BONES)}
    for verts, faces, uvs, bone in PARTS:
        bv = [bm.verts.new(widen(v, bone)) for v in verts]
        for v in bv:
            v[deform][bone_index[bone]] = 1.0
        for f, fuv in zip(faces, uvs):
            face = bm.faces.new([bv[i] for i in f])
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
    for p in me.polygons:
        p.use_smooth = False
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
    build_neck_torso()
    build_back_spikes()
    build_tail()
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
