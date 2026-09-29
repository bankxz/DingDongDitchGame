"""Lava Horse design, measured from the reference sheet (ref px; 1 px = 1 unit until export).

Axes: X = horse's left (+) / right (-), Y = back (+) / front (-), Z = up; ground Z = 0.
Side panel (horse faces image-left): Y = u - 270, Z = 440 - v.   Front panel: X = x - 122, Z = 440 - v.
Every piece is a chamfered, optionally tapered box ("chunk") assigned to ONE material object and ONE bone.
"""
import math
import numpy as np
from cube import C, seg, rot

S = 7.0 / 444.0          # studs per ref px (horse ~7 studs tall to the ear tips)

BODY, CRACKS, MANE, TAIL, HOOVES, ARMOUR, EYES = ('Body_Lava', 'Lava_Cracks_Neon', 'Mane_Neon', 'Tail_Neon',
                                                  'Hooves_Dark', 'Armour_Volcanic', 'Eyes')
OBJECTS = [BODY, CRACKS, MANE, TAIL, HOOVES, ARMOUR, EYES]
MUZZLE_OBJ = BODY


def ck(obj, *a, **k):
    c = C(*a, **k)
    c['obj'] = obj
    return c


def sk(obj, *a, **k):
    c = seg(*a, **k)
    c['obj'] = obj
    return c


# ------------------------------------------------------------------ centre-line body
CENTRE = [
    ck(BODY, 'chest', (0, -110, 196), (68, 54, 60), 'Chest', 'body'),
    # barrel ends are buried in the chest / rump: chamfer only its long (Y) edges
    ck(BODY, 'barrel', (0, -14, 194), (70, 44, 57), 'Spine', 'body', cax=1),
    ck(BODY, 'rump', (0, 92, 191), (74, 60, 61), 'Hips', 'body', taper=(0.96, 0.95)),
    ck(BODY, 'neck', (0, -126, 292), (32, 38, 70), 'Neck', 'body', taper=(0.95, 0.85), cax=2),
    # head = skull + snout + jaw. The snout and jaw run 20+ px back INSIDE the skull and share its underside
    # line, so there is no gap or notch between nose and head at any angle (was: tilted snout wedge + loose muzzle).
    ck(BODY, 'head', (0, -184, 350), (42, 48, 52), 'Head', 'body', ch=7.0),
    ck(BODY, 'snout', (0, -248, 345), (34, 36, 25), 'Head', 'snout', ch=6.0),
    ck(MUZZLE_OBJ, 'muzzle', (0, -242, 309), (32, 36, 15), 'Jaw', 'muzzle', ch=5.0),
]

# ------------------------------------------------------------------ one side (+X = horse's left); mirrored to -X
SIDE = [
    # front leg (caps buried in the body / next segment -> long-edge chamfer only)
    ck(BODY, 'fl_upper', (54, -100, 128), (37, 38, 36), 'FrontLeg_Upper', 'body', cax=2),
    ck(BODY, 'fl_lower', (54, -100, 74), (35, 35, 26), 'FrontLeg_Lower', 'body', cax=2),
    ck(HOOVES, 'fl_hoof', (54, -98, 27), (41, 44, 27), 'FrontHoof', 'hoof', taper=(0.93, 0.93), ch=5.0),
    # back leg (thigh blends into the rump)
    ck(BODY, 'bl_upper', (54, 112, 138), (38, 44, 44), 'BackLeg_Upper', 'body', cax=2),
    ck(BODY, 'bl_lower', (54, 116, 76), (35, 36, 26), 'BackLeg_Lower', 'body', cax=2),
    ck(HOOVES, 'bl_hoof', (54, 118, 27), (41, 44, 27), 'BackHoof', 'hoof', taper=(0.93, 0.93), ch=5.0),
]

# armour: dark volcanic rock cubes (centre, half size, tilt, yaw, roll)
SHOULDER_ROCKS = [((86, -112, 214), 23, 12, -10, 18), ((92, -80, 190), 22, -14, 16, 10), ((80, -124, 172), 18, 20, 8, -12),
                  ((76, -62, 236), 18, -8, 22, 24), ((62, -104, 254), 18, 14, -18, 30), ((46, -70, 264), 15, -20, 10, 20),
                  ((88, -96, 238), 16, 25, 30, 5)]
HIP_ROCKS = [((62, 66, 262), 19, -12, 14, 22), ((40, 108, 272), 17, 16, -20, 12), ((80, 94, 228), 23, 10, 18, 14),
             ((84, 126, 196), 20, -16, -10, 8), ((78, 58, 198), 18, 18, 12, -10), ((74, 140, 160), 17, -10, 25, 16),
             ((22, 140, 270), 13, 22, 8, 10), ((30, 40, 268), 18, 12, -14, 8), ((16, 88, 282), 16, -18, 20, 12),
             ((44, 18, 258), 15, 20, 10, -8)]
for i, (c, h, t, y, r) in enumerate(SHOULDER_ROCKS):
    SIDE.append(ck(ARMOUR, f'rock_sh{i}', c, (h, h * 1.05, h * 0.95), 'Chest', 'armour', tilt=t, yaw=y, roll=r, ch=4.0))
for i, (c, h, t, y, r) in enumerate(HIP_ROCKS):
    SIDE.append(ck(ARMOUR, f'rock_hp{i}', c, (h, h * 1.05, h * 0.95), 'Hips', 'armour', tilt=t, yaw=y, roll=r, ch=4.0))


# ------------------------------------------------------------------ ears + eyes (custom meshes, built per side)
def _custom(obj, name, faces, bone, style, c, h):
    return dict(name=name, c=np.array(c, float), h=np.array(h, float), bone=bone, style=style, R=np.eye(3),
                taper=(0.15, 0.15), ch=1.0, cax=None, custom=faces, obj=obj)


def ear(sx):
    """Pointed square pyramid leaning slightly out and back, with a recessed inner ear on the front face
    (3 rim quads + inner tri + 3 back/side tris + base quad = 12 tris). Base is sunk 5 px into the skull."""
    bx, by, bz = 25.0 * sx, -150.0, 397.0
    hx, hy = 13.0, 11.0
    tip = np.array((30.0 * sx, -144.0, 440.0))
    B0 = np.array((bx + hx * sx, by - hy, bz))     # front-outer
    B1 = np.array((bx - hx * sx, by - hy, bz))     # front-inner
    B2 = np.array((bx - hx * sx, by + hy, bz))     # back-inner
    B3 = np.array((bx + hx * sx, by + hy, bz))     # back-outer
    cen = (B0 + B1 + tip) / 3
    back = np.array((0, 1.0, 0)) * 3.0
    t = 0.32
    I0, I1, IT = [p + (cen - p) * t + back for p in (B0, B1, tip)]
    I0[2] = I1[2] = bz + 9.0                        # inner ear starts above the skull surface
    faces = [('main', [B0, B1, I1, I0]), ('main', [B1, tip, IT, I1]), ('main', [tip, B0, I0, IT]),
             ('ear_in', [I0, I1, IT]),
             ('main', [B1, B2, tip]), ('main', [B2, B3, tip]), ('main', [B3, B0, tip]),
             ('cap', [B0, B3, B2, B1])]
    c = (B0 + B1 + B2 + B3) / 4 * 0.75 + tip * 0.25
    return _custom(BODY, 'ear_' + ('L' if sx > 0 else 'R'), faces, 'Head', 'ear', c, (hx, hy, 21.0))


def _plate(centre, half_y, half_z, depth, sx):
    """thin box on the +-X side of the head: outer face + 4 rims (back face buried, not built)"""
    x0, x1 = centre[0] - depth * sx, centre[0] + depth * sx
    y, z = centre[1], centre[2]
    def P(xx, sy, sz):
        return np.array((xx, y + sy * half_y, z + sz * half_z))
    return [('main', [P(x1, -1, -1), P(x1, 1, -1), P(x1, 1, 1), P(x1, -1, 1)]),
            ('edge', [P(x0, -1, 1), P(x0, 1, 1), P(x1, 1, 1), P(x1, -1, 1)]),
            ('edge', [P(x0, -1, -1), P(x1, -1, -1), P(x1, 1, -1), P(x0, 1, -1)]),
            ('edge', [P(x0, -1, -1), P(x0, -1, 1), P(x1, -1, 1), P(x1, -1, -1)]),
            ('edge', [P(x0, 1, -1), P(x1, 1, -1), P(x1, 1, 1), P(x0, 1, 1)]),
            ('cap', [P(x0, -1, -1), P(x0, -1, 1), P(x0, 1, 1), P(x0, 1, -1)])]     # back (closes the plate)


def eyes(sx):
    """White square eye flush on the skull side just behind its front edge, with a big black square pupil set
    toward the front / top (reference: thin white rim front + top, wider rim back + bottom). Separate plates keep
    the edges razor sharp at any texture resolution."""
    side = 'L' if sx > 0 else 'R'
    white_c = (42.0 * sx, -204.0, 378.0)
    pupil_c = (43.6 * sx, -207.0, 380.0)
    return [_custom(EYES, f'eye_{side}', _plate(white_c, 13.0, 12.0, 1.4, sx), 'Head', 'eye', white_c, (1.4, 13, 12)),
            _custom(EYES, f'pupil_{side}', _plate(pupil_c, 8.5, 8.0, 0.6, sx), 'Head', 'pupil', pupil_c, (0.6, 8.5, 8))]


def shard(obj, name, root, direction, length, width, thick, bone, style, roll=0.0, embed=6.0):
    """Flame / crystal blade: chunk from root along direction, wide in-plane, thin across, tapering to a tip."""
    d = np.array(direction, float)
    d /= np.linalg.norm(d)
    p0 = np.array(root, float) - d * embed
    p1 = np.array(root, float) + d * length
    up = np.array((math.cos(math.radians(roll)), 0, math.sin(math.radians(roll))))   # thin axis ~ X, rolled
    c = sk(obj, name, p0, p1, thick, width, bone, style, taper=(0.55, 0.18), ch=2.5, up=up, cax=2)
    return c


def mane_shards():
    out = []
    # root line along the back of the neck: top (behind the ears) -> withers
    top, bot = np.array((0, -130, 402.0)), np.array((0, -58, 258.0))
    n = 7
    for i in range(n):
        t = i / (n - 1)
        r = top + (bot - top) * t
        ang = math.radians(72 - 40 * t)                       # up-back near the head, flatter at the withers
        d = (0, math.cos(ang), math.sin(ang))
        L = 78 - 18 * abs(t - 0.3)
        bone = 'Mane_1' if t < 0.34 else ('Mane_2' if t < 0.67 else 'Mane_3')
        out.append(shard(MANE, f'mane_c{i}', r + np.array((0, 8, 0)), d, L, 38, 13, bone, 'mane'))
        for sx in (1, -1):
            side = 'L' if sx > 0 else 'R'
            spread = 0.16 + 0.3 * max(0.0, 0.4 - t)
            dd = np.array((spread * sx, math.cos(ang) * 0.95, math.sin(ang) * 0.95))
            out.append(shard(MANE, f'mane_{side}{i}', r + np.array(((17 + 20 * max(0.0, 0.4 - t)) * sx, -4, -10)), dd, L * 0.78, 34, 11, bone,
                             'mane', roll=8 * sx))
    # crest between the ears
    for j, (y, h) in enumerate(((-196, 26), (-182, 34), (-168, 28))):
        out.append(shard(MANE, f'crest{j}', (0, y, 392), (0, 0.35, 1), h, 12, 6, 'Head', 'mane'))
    return out


TAIL_CURVE = [np.array(p, float) for p in ((0, 140, 262), (0, 188, 244), (0, 216, 184), (0, 230, 118))]


def tail_point(t):
    """piecewise-linear point on the tail's centre curve (t 0..1) and the tail bone at t"""
    k = min(int(t * 3), 2)
    f = t * 3 - k
    p = TAIL_CURVE[k] + (TAIL_CURVE[k + 1] - TAIL_CURVE[k]) * f
    return p, (TAIL_CURVE[k + 1] - TAIL_CURVE[k]), f'Tail_{k + 1}'


def tail_shards():
    out = []
    # core: three tapered blocks down the curve
    for k in range(3):
        a, b = TAIL_CURVE[k], TAIL_CURVE[k + 1]
        hw = (26, 22, 15)[k]
        out.append(sk(TAIL, f'tail_core{k}', a, b, hw * 0.8, hw, f'Tail_{k + 1}', 'tail', taper=(0.8, 0.75),
                      ext=6, ch=3.0, cax=2))
    # fan of blades off the core: up/back at the root, back/down further along, tip blade at the end
    n = 9
    for i in range(n):
        t = 0.06 + 0.88 * i / (n - 1)
        p, tan, bone = tail_point(t)
        tan = tan / np.linalg.norm(tan)
        back = np.array((0, 1.0, 0.25))
        d = tan * 0.45 + back * (1.0 - t) * 0.9 + np.array((0, 0.2, 0.9)) * max(0, 0.35 - t) * 2.2
        L = 62 + 26 * math.sin(math.pi * t)
        out.append(shard(TAIL, f'tail_c{i}', p, d, L, 36, 13, bone, 'tail'))
        for sx in (1, -1):
            side = 'L' if sx > 0 else 'R'
            dd = d / np.linalg.norm(d) + np.array((0.22 * sx, 0, 0))
            out.append(shard(TAIL, f'tail_{side}{i}', p + np.array((18 * sx, -4, 4)), dd, L * 0.74, 32, 11, bone,
                             'tail', roll=6 * sx))
    out.append(shard(TAIL, 'tail_tip', TAIL_CURVE[3], (0, 0.3, -1), 34, 18, 9, 'Tail_3', 'tail'))
    return out


def mirror(parts):
    out = []
    M = np.diag([-1.0, 1, 1])
    for side, sx in (('L', 1), ('R', -1)):
        for p in parts:
            q = dict(p)
            q['name'] = f"{p['name']}_{side}"
            q['c'] = p['c'] * np.array((sx, 1, 1))
            q['R'] = p['R'] if sx > 0 else M @ p['R'] @ M
            b = p['bone']
            q['bone'] = b if b in ('Chest', 'Spine', 'Hips', 'Neck', 'Head', 'Jaw') else f'{b}_{side}'
            out.append(q)
    return out


def all_chunks():
    return (CENTRE + mirror(SIDE) + [ear(1), ear(-1)] + eyes(1) + eyes(-1) + mane_shards() + tail_shards())


# ------------------------------------------------------------------ bones: (name, head, tail, parent)
def bones():
    B = [('Root', (0, 0, 0), (0, -40, 0), None),
         ('Hips', (0, 110, 195), (0, 30, 195), 'Root'),
         ('Spine', (0, 30, 195), (0, -48, 198), 'Hips'),
         ('Chest', (0, -48, 198), (0, -120, 215), 'Spine'),
         ('Neck', (0, -120, 236), (0, -132, 340), 'Chest'),
         ('Head', (0, -140, 340), (0, -222, 340), 'Neck'),
         ('Jaw', (0, -216, 308), (0, -276, 306), 'Head'),
         ('Mane_1', (0, -120, 385), (0, -95, 430), 'Neck'),
         ('Mane_2', (0, -95, 330), (0, -60, 368), 'Neck'),
         ('Mane_3', (0, -62, 282), (0, -20, 305), 'Chest'),
         ('Tail_1', tuple(TAIL_CURVE[0]), tuple(TAIL_CURVE[1]), 'Hips'),
         ('Tail_2', tuple(TAIL_CURVE[1]), tuple(TAIL_CURVE[2]), 'Tail_1'),
         ('Tail_3', tuple(TAIL_CURVE[2]), tuple(TAIL_CURVE[3]), 'Tail_2')]
    for side, sx in (('L', 1), ('R', -1)):
        for leg, y, top, knee in (('Front', -100, 160, 100), ('Back', 115, 176, 102)):
            B += [(f'{leg}Leg_Upper_{side}', (54 * sx, y, top), (54 * sx, y, knee), 'Chest' if leg == 'Front' else 'Hips'),
                  (f'{leg}Leg_Lower_{side}', (54 * sx, y, knee), (54 * sx, y, 54), f'{leg}Leg_Upper_{side}'),
                  (f'{leg}Hoof_{side}', (54 * sx, y, 54), (54 * sx, y - 30, 8), f'{leg}Leg_Lower_{side}')]
    return B


# ------------------------------------------------------------------ lava cracks: polylines on chunk faces
# (chunk name, world direction of the face, [(u, v), ...]) with u, v in -1..1 across the face:
# u runs along the face's in-plane axis closest to world X (Y for side faces), v along the one closest to world Z
# (Y for top / bottom faces).
ZIG = [(0.1, 1.0), (-0.25, 0.45), (0.2, -0.05), (-0.12, -0.55), (0.12, -1.0)]
ZIG2 = [(-0.1, 1.0), (0.22, 0.5), (-0.18, 0.0), (0.15, -0.5), (-0.1, -1.0)]


def crack_paths():
    P = []
    F, B, UP = (0, -1, 0), (0, 1, 0), (0, 0, 1)
    for s in (1, -1):
        P += [('neck', F, [(0.8 * s, -1.0), (0.8 * s, 0.9)])]
        P += [('chest', F, [(0.37 * s, 1.0), (0.37 * s, -0.25), (0.0, -0.5)])]
        # rump back: same Y shape as the chest
        P += [('rump', B, [(0.3 * s, 0.7), (0.3 * s, -0.2), (0.0, -0.45)])]
    P += [('chest', F, [(0.0, -0.5), (0.0, -1.0)]), ('rump', B, [(0.0, -0.45), (0.0, -1.0)])]
    for side, s in (('L', 1), ('R', -1)):
        out = (s, 0, 0)
        P += [(f'fl_upper_{side}', out, ZIG), (f'fl_lower_{side}', out, ZIG2),
              (f'bl_upper_{side}', out, ZIG2), (f'bl_lower_{side}', out, ZIG),
              (f'fl_upper_{side}', out, [(-1.0, -0.92), (1.0, -0.92)]),        # knee band
              (f'bl_upper_{side}', out, [(-1.0, -0.92), (1.0, -0.92)]),
              (f'fl_upper_{side}', F, [(0.85, 1.0), (0.85, -1.0)]), (f'fl_lower_{side}', F, [(0.85, 1.0), (0.85, -1.0)]),
              (f'fl_upper_{side}', F, [(-0.85, 1.0), (-0.85, -1.0)]), (f'fl_lower_{side}', F, [(-0.85, 1.0), (-0.85, -1.0)]),
              (f'bl_lower_{side}', B, [(0.0, 1.0), (0.15, 0.0), (-0.1, -1.0)]),
              # block seams on the body sides (front of the barrel, back of the barrel) + belly edge
              ('barrel', out, [(-0.93, 1.0), (-0.85, 0.35), (-0.95, -0.2), (-0.88, -1.0)]),
              ('barrel', out, [(0.93, 1.0), (0.93, -1.0)]),
              ('chest', out, [(-1.0, -0.88), (1.0, -0.88)]), ('barrel', out, [(-1.0, -0.88), (1.0, -0.88)]),
              ('rump', out, [(-1.0, -0.7), (-0.3, -0.62), (0.15, -0.8)]),
              ('rump', out, [(-0.55, 0.9), (-0.35, 0.2), (-0.6, -0.4)]),
              # head: seam between skull and snout + cheek line
              ('head', out, [(-0.93, 1.0), (-0.95, 0.25), (-0.62, -0.3), (0.15, -0.62), (0.5, -1.0)]),
              ('head', out, [(0.62, 1.0), (0.55, 0.35), (0.7, -0.2)]),
              ('neck', out, [(-0.85, -1.0), (-0.8, 0.2), (-0.9, 0.95)])]
    # seams across the top of the body (visible from above)
    P += [('barrel', UP, [(-1.0, -0.93), (1.0, -0.93)]), ('barrel', UP, [(-1.0, 0.93), (1.0, 0.93)])]
    return P


# ------------------------------------------------------------------ painted-only veins (texture, no geometry)
# thinner branching cracks like the reference's secondary lava veins; same (chunk, face dir, uv path) format
def vein_paths():
    P = []
    F, B = (0, -1, 0), (0, 1, 0)
    for side, s in (('L', 1), ('R', -1)):
        out = (s, 0, 0)
        P += [('chest', out, [(-0.2, 1.0), (0.1, 0.4), (-0.15, -0.2), (0.2, -0.88)]),
              ('chest', out, [(0.1, 0.4), (0.55, 0.15), (0.8, 0.3)]),
              ('rump', out, [(0.35, 1.0), (0.55, 0.3), (0.35, -0.3), (0.6, -0.7)]),
              ('rump', out, [(0.55, 0.3), (0.9, 0.1)]),
              ('barrel', out, [(-0.88, -0.2), (-0.4, -0.45), (-0.1, -0.35)]),
              ('neck', out, [(0.4, 1.0), (0.15, 0.25), (0.4, -0.45), (0.2, -1.0)]),
              ('fl_upper_' + side, B, ZIG), ('bl_upper_' + side, F, ZIG2),
              ('fl_lower_' + side, out, [(0.2, -0.1), (0.7, -0.4), (0.9, -0.9)]),
              ('bl_lower_' + side, out, [(0.2, -0.05), (-0.5, -0.5), (-0.8, -1.0)]),
              ('bl_upper_' + side, out, [(0.2, 0.45), (0.7, 0.2), (0.85, -0.3)])]
    return P
