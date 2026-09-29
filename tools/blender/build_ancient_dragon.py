"""Ancient Dragon (Roblox-ready) - v2, rebuilt from the reference measurements.

The model is assembled the way the reference is: dark low-poly body masses covered in
separate studded bricks (gold armour, cream horns/claws/spikes, tan throat/belly plates),
glowing cyan runes, and stepped teal wing membranes.

Run:  python3 tools/blender/build_ancient_dragon.py [--no-rig]
Coordinates: Z up, dragon faces -Y, dragon's left = +X (bones *_L). 1 BU = 1 stud.
"""
import math
import os
import sys

import bpy  # noqa: I001 (bpy must be imported before bmesh/mathutils)
import bmesh
from mathutils import Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "models", "AncientDragon")
TEX = os.path.join(OUT, "textures")
STUD_TILE_WORLD = 2.0  # a 4x4-stud tile covers 2x2 BU -> one stud per 0.5 BU

V = Vector
PIECES = {m: [] for m in ("Dark", "Gold", "Tan", "Bone", "Glow", "Membrane", "Eye")}


# ============================================================== primitives
def add_piece(mat, verts, faces, bone, uvmode="stud", uvs=None):
    bones = [[(bone, 1.0)] for _ in verts] if isinstance(bone, str) else bone
    PIECES[mat].append(dict(verts=[V(v) for v in verts], faces=faces, bones=bones, uvmode=uvmode, uvs=uvs))


def frame(direction, up_hint=(0, 0, 1)):
    d = V(direction).normalized()
    up_hint = V(up_hint)
    if abs(d.dot(up_hint.normalized())) > 0.97:
        up_hint = V((0, 1, 0)) if abs(d.z) > 0.5 else V((0, 0, 1))
    side = d.cross(up_hint).normalized()
    up = side.cross(d).normalized()
    return side, d, up


def obox(mat, c, ax, ay, az, bone, uvmode="stud", drop=None):
    """oriented box: centre c, half-axis vectors ax, ay, az. drop: face to omit ('-z' etc.)"""
    c = V(c)
    vs = []
    for sz in (-1, 1):
        for sy in (-1, 1):
            for sx in (-1, 1):
                vs.append(c + V(ax) * sx + V(ay) * sy + V(az) * sz)
    faces = {"-z": (0, 2, 3, 1), "+z": (4, 5, 7, 6), "-y": (0, 1, 5, 4), "+y": (2, 6, 7, 3),
             "-x": (0, 4, 6, 2), "+x": (1, 3, 7, 5)}
    add_piece(mat, vs, [f for k, f in faces.items() if k != drop], bone, uvmode)


def brick(mat, p0, p1, w, h, bone, up=(0, 0, 1), gap=0.06, w1=None, h1=None, uvmode="stud", drop=None, bevel=0.22):
    """bevelled plate spanning p0->p1 (shortened by gap); top face inset by `bevel` for an angular chamfer"""
    p0, p1 = V(p0), V(p1)
    s, d, u = frame(p1 - p0, up)
    L = (p1 - p0).length
    if L > 2 * gap + 0.05:
        p0, p1 = p0 + d * gap, p1 - d * gap
    w1 = w if w1 is None else w1
    h1 = h if h1 is None else h1
    ins = d * min(L * 0.12, 0.12) * (bevel / 0.22)
    tw, tw1 = w * (1 - bevel), w1 * (1 - bevel)
    vs = [p0 - s * w / 2 - u * h / 2, p0 + s * w / 2 - u * h / 2, p0 + s * tw / 2 + u * h / 2 + ins,
          p0 - s * tw / 2 + u * h / 2 + ins,
          p1 - s * w1 / 2 - u * h1 / 2, p1 + s * w1 / 2 - u * h1 / 2, p1 + s * tw1 / 2 + u * h1 / 2 - ins,
          p1 - s * tw1 / 2 + u * h1 / 2 - ins]
    faces = {"start": (0, 3, 2, 1), "end": (4, 5, 6, 7), "down": (0, 1, 5, 4), "right": (1, 2, 6, 5),
             "up": (2, 3, 7, 6), "left": (3, 0, 4, 7)}
    add_piece(mat, vs, [f for k, f in faces.items() if k != drop], bone, uvmode)


def spike(mat, base, tip, w, h=None, bone="Root", up=(0, 0, 1), cap=False):
    base, tip = V(base), V(tip)
    h = w if h is None else h
    s, d, u = frame(tip - base, up)
    vs = [base - u * h / 2, base + s * w / 2, base + u * h / 2, base - s * w / 2, tip]
    faces = [(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)] + ([(0, 3, 2, 1)] if cap else [])
    add_piece(mat, vs, faces, bone)


def blade(mat, pts, w, h, bone, up=(0, 0, 1), taper_to=0.0, tip_mat=None, tip_frac=0.35, curve_up=None):
    """continuous sleek blade: diamond cross-section lofted along pts, tapering to a sharp point.
    bone: str or per-point list. tip_mat colours the last tip_frac of the length (e.g. cream horn tips)."""
    pts = [V(p) for p in pts]
    n = len(pts)
    bones = [bone] * n if isinstance(bone, str) else list(bone) + [bone[-1]] * (n - len(bone))
    rings = []
    for i, p in enumerate(pts[:-1]):
        d = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        sd, dd, u = frame(d, up)
        f = i / (n - 1)
        ww, hh = w + (taper_to - w) * f, h + (taper_to * h / max(w, 1e-6) - h) * f
        rings.append([p - u * hh / 2, p + sd * ww / 2, p + u * hh / 2, p - sd * ww / 2])
    split = max(1, min(len(rings) - 1, int(round(len(rings) * (1 - tip_frac))))) if tip_mat else len(rings)

    def emit(mat_, r0, r1, with_tip, start_cap):
        verts, faces, bw = [], [], []
        for i in range(r0, r1):
            verts += rings[i]
            bw += [[(bones[i], 1.0)]] * 4
        m = r1 - r0
        for i in range(m - 1):
            for k in range(4):
                a, b = i * 4 + k, i * 4 + (k + 1) % 4
                faces.append((a, b, b + 4, a + 4))
        if start_cap:
            faces.append((3, 2, 1, 0))
        if with_tip:
            verts.append(pts[-1])
            bw.append([(bones[-1], 1.0)])
            t = len(verts) - 1
            last = (m - 1) * 4
            for k in range(4):
                faces.append((last + k, last + (k + 1) % 4, t))
        else:
            last = (m - 1) * 4
            faces.append((last, last + 1, last + 2, last + 3))
        add_piece(mat_, verts, faces, bw)

    if split >= len(rings):
        emit(mat, 0, len(rings), True, True)
    else:
        emit(mat, 0, split + 1, False, True)
        emit(tip_mat, split, len(rings), True, True)


def eyeball(c, r, fwd, up, bone, seg=8, rings=5):
    """low-poly eyeball whose pole faces `fwd`; UVs planar-projected from the front so the painted
    iris + slit pupil sit on the visible cap (Eye material)"""
    c, fwd = V(c), V(fwd).normalized()
    rt = fwd.cross(V(up)).normalized()
    upv = rt.cross(fwd).normalized()
    verts, uvs_v = [c + fwd * r], []
    for i in range(1, rings):
        th = math.pi * i / rings
        for k in range(seg):
            ph = 2 * math.pi * k / seg
            verts.append(c + fwd * (r * math.cos(th)) + (rt * math.cos(ph) + upv * math.sin(ph)) * (r * math.sin(th)))
    verts.append(c - fwd * r)
    uv = [(0.5 + (v - c).dot(rt) / (2.1 * r), 0.5 + (v - c).dot(upv) / (2.1 * r)) for v in verts]
    faces = []
    last = len(verts) - 1
    for k in range(seg):
        faces.append((0, 1 + k, 1 + (k + 1) % seg))
    for i in range(rings - 2):
        a0, b0 = 1 + i * seg, 1 + (i + 1) * seg
        for k in range(seg):
            k1 = (k + 1) % seg
            faces.append((a0 + k, b0 + k, b0 + k1, a0 + k1))
    lb = 1 + (rings - 2) * seg
    for k in range(seg):
        faces.append((lb + k, last, lb + (k + 1) % seg))
    add_piece("Eye", verts, faces, bone, uvmode="given", uvs=[[uv[i] for i in f] for f in faces])


def strip(mat, pts, w, h, bone, up=(0, 0, 1), gap=0.05, taper_to=None, tip_mat=None, tip=False, drop=None):
    """row of separate bricks along a polyline; optional pointed last segment"""
    pts = [V(p) for p in pts]
    n = len(pts) - 1
    for i in range(n):
        f0, f1 = i / n, (i + 1) / n
        wa = w if taper_to is None else w + (taper_to - w) * f0
        wb = w if taper_to is None else w + (taper_to - w) * f1
        ha = h if taper_to is None else h + (taper_to * h / w - h) * f0
        hb = h if taper_to is None else h + (taper_to * h / w - h) * f1
        b = bone if isinstance(bone, str) else bone[i]
        m = tip_mat if (tip_mat and i >= n - 2) else mat
        if tip and i == n - 1:
            spike(m, pts[i] + (pts[i + 1] - pts[i]).normalized() * gap, pts[i + 1], wa, ha, bone=b, up=up)
        else:
            brick(m, pts[i], pts[i + 1], wa, ha, b, up=up, gap=gap, w1=wb, h1=hb, drop=drop)


def tube(mat, rings, bone, up=(0, 0, 1), chamfer=0.3, caps=(True, True)):
    """low-poly lofted body mass. rings = [(centre, half_w, half_h), ...]; bone str or per-ring list"""
    k = 1 - chamfer
    prof = [(1, k), (k, 1), (-k, 1), (-1, k), (-1, -k), (-k, -1), (k, -1), (1, -k)]
    verts, bones = [], []
    cs = [V(r[0]) for r in rings]
    for i, (c, hw, hh) in enumerate(rings):
        c = V(c)
        d = cs[min(i + 1, len(cs) - 1)] - cs[max(i - 1, 0)]
        s, _, u = frame(d, up)
        b = bone if isinstance(bone, str) else bone[i]
        for px, pz in prof:
            verts.append(c + s * px * hw + u * pz * hh)
            bones.append([(b, 1.0)])
    n = len(prof)
    faces = []
    for i in range(len(rings) - 1):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            faces.append((a, b, b + n, a + n))
    if caps[0]:
        faces.append(tuple(reversed(range(n))))
    if caps[1]:
        last = (len(rings) - 1) * n
        faces.append(tuple(last + j for j in range(n)))
    add_piece(mat, verts, faces, bones)


def ring_of_bricks(center, normal, radius, bone, up=(0, 0, 1), n=8, bw=0.5, bh=0.5, rune="square"):
    """gold octagon ring framing a glowing rune (shoulder/hip rune)"""
    nrm = V(normal).normalized()
    a = V(up).cross(nrm).normalized()
    b = nrm.cross(a).normalized()
    c = V(center)
    for k in range(n):
        t0 = k * 2 * math.pi / n + math.pi / n
        t1 = t0 + 2 * math.pi / n
        p0 = c + (a * math.cos(t0) + b * math.sin(t0)) * radius
        p1 = c + (a * math.cos(t1) + b * math.sin(t1)) * radius
        brick("Gold", p0 - (p1 - p0) * 0.1, p1 + (p1 - p0) * 0.1, bw, bh, bone, up=nrm, gap=0.04, drop="down")
    obox("Dark", c - nrm * 0.02, a * radius * 0.78, b * radius * 0.78, nrm * 0.14, bone)
    if rune == "diamond":
        a2, b2 = (a + b).normalized(), (b - a).normalized()
        obox("Glow", c + nrm * 0.1, a2 * radius * 0.52, b2 * radius * 0.52, nrm * 0.08, bone, uvmode="rune")
    else:
        obox("Glow", c + nrm * 0.1, a * radius * 0.55, b * radius * 0.55, nrm * 0.08, bone, uvmode="rune")


# rest-pose adjustments per bone region (applied after building, to geometry and joints alike)
OFFSETS = {"Head": V((0, -0.25, 0.6)), "Jaw": V((0, -0.25, 0.6)), "Neck3": V((0, -0.15, 0.45)),
           "Neck2": V((0, -0.08, 0.28)), "Neck1": V((0, 0, 0.12))}


JAW_CLOSE_DEG = 16  # rest pose: mouth slightly open (reference front view), idle anim opens it wider


def apply_offsets():
    from mathutils import Matrix
    pivot = J["Jaw"]
    R = Matrix.Rotation(math.radians(-JAW_CLOSE_DEG), 3, "X")
    for pieces in PIECES.values():
        for pc in pieces:
            if all(bw[0][0] == "Jaw" for bw in pc["bones"]):
                for v in pc["verts"]:
                    v[:] = pivot + R @ (v - pivot)
            for v, bw in zip(pc["verts"], pc["bones"]):
                off = V((0, 0, 0))
                for bn, w in bw:
                    off += OFFSETS.get(bn, V((0, 0, 0))) * w
                v += off


def mirror(fn):
    fn(1, "_L")
    fn(-1, "_R")


def X(s, p):
    return V((p[0] * s, p[1], p[2]))


# ============================================================== skeleton / landmarks (rest pose)
J = {
    "Root": V((0, 2.0, 0.0)),
    "Hips": V((0, 4.6, 3.8)),
    "Spine": V((0, 2.2, 4.2)),
    "Chest": V((0, 0.0, 4.3)),
    "Neck1": V((0, -2.2, 5.0)),
    "Neck2": V((0, -2.9, 6.0)),
    "Neck3": V((0, -3.4, 6.8)),
    "Head": V((0, -3.8, 7.35)),
    "HeadEnd": V((0, -6.7, 6.9)),
    "Jaw": V((0, -4.0, 6.55)),
    "JawEnd": V((0, -5.8, 5.15)),
}
TAIL = [V((0, 6.2, 3.4)), V((0, 8.0, 2.05)), V((-0.1, 9.8, 1.3)), V((-0.4, 11.6, 1.0)), V((-0.9, 13.3, 1.05)),
        V((-1.6, 14.8, 1.5)), V((-2.4, 16.0, 2.4)), V((-3.1, 16.8, 3.6))]
TAIL_HW = [1.4, 1.15, 1.0, 0.85, 0.72, 0.6, 0.46, 0.32]
TAIL_HH = [1.1, 0.95, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]


def leg_joints(s):
    return dict(
        UpperArm=X(s, (2.1, 0.1, 4.25)), Forearm=X(s, (2.6, 0.55, 2.45)), Hand=X(s, (2.75, -1.55, 0.95)),
        HandEnd=X(s, (2.75, -3.6, 0.5)),
        Thigh=X(s, (2.1, 4.8, 3.5)), Shin=X(s, (2.5, 4.0, 1.9)), Foot=X(s, (2.6, 5.5, 0.95)),
        FootEnd=X(s, (2.6, 3.4, 0.5)),
    )


def wing_joints(s):
    return dict(
        Wing1=X(s, (1.7, 0.8, 5.9)), Wing2=X(s, (3.2, 1.3, 8.5)), WingHand=X(s, (3.9, 1.8, 10.4)),
        F1=[X(s, p) for p in ((3.9, 1.8, 10.4), (5.4, 4.6, 10.35), (7.4, 8.0, 9.5), (9.6, 11.0, 7.9),
                              (11.3, 13.0, 5.6), (12.2, 14.0, 3.0))],
        F2Tip=X(s, (10.0, 11.6, 3.6)), F3Tip=X(s, (8.0, 9.2, 4.6)), F4Tip=X(s, (5.9, 6.4, 5.6)),
        Body=X(s, (1.5, 3.2, 5.8)),
    )


SPINE_PTS = []  # (point, bone) along the dorsal line, filled by torso/neck/tail builders


def build_spine_ridge():
    """one continuous gold ridge from the back of the skull to the tail tip that all dorsal spikes sit on"""
    body_y = min(p[1] for p, b in SPINE_PTS if b in ("Chest", "Spine", "Hips"))
    pts = [(V(p), b) for p, b in SPINE_PTS if not (b.startswith("Neck") and p[1] > body_y - 0.4)]
    pts = sorted(pts, key=lambda pb: pb[0][1])
    blade("Gold", [p for p, _ in pts], 0.5, 0.42, [b for _, b in pts], up=(0, 0, 1), taper_to=0.12)


# ============================================================== torso
def build_torso():
    rings = [((0, -2.75, 3.95), 1.25, 1.2), ((0, -1.6, 3.95), 1.75, 1.5), ((0, 0.4, 3.95), 1.95, 1.55),
             ((0, 2.4, 3.8), 1.9, 1.45), ((0, 4.4, 3.6), 1.75, 1.3), ((0, 6.3, 3.35), 1.35, 1.05)]
    tube("Dark", rings, ["Chest", "Chest", "Chest", "Spine", "Hips", "Hips"], chamfer=0.48)

    # tan throat-to-belly plate column (front + underside)
    belly = [(-2.95, 5.2), (-3.05, 4.3), (-3.0, 3.4), (-2.6, 2.6), (-1.2, 2.35), (0.8, 2.35), (2.8, 2.4),
             (4.8, 2.45), (6.8, 2.6)]
    for i in range(len(belly) - 1):
        (y0, z0), (y1, z1) = belly[i], belly[i + 1]
        t = i / (len(belly) - 1)
        w = 1.9 if i < 3 else 2.6 - 1.6 * max(0.0, t - 0.4)
        bn = "Chest" if y0 < 1.2 else ("Spine" if y0 < 3.4 else "Hips")
        brick("Tan", (0, y0, z0), (0, y1, z1), w, 0.34, bn, up=(0, 1, 0) if i < 3 else (0, 0, -1), gap=0.04)

    # chest shield (gold frame) + diamond rune (chest rune detail)
    cy = -3.55
    frame_pts = [(-1.25, 5.0), (1.25, 5.0), (1.35, 3.6), (0.0, 2.35), (-1.35, 3.6), (-1.25, 5.0)]
    for i in range(len(frame_pts) - 1):
        (x0, z0), (x1, z1) = frame_pts[i], frame_pts[i + 1]
        brick("Gold", (x0, cy, z0), (x1, cy, z1), 0.42, 0.42, "Chest", up=(0, -1, 0), gap=0.02)
    obox("Dark", (0, cy + 0.2, 3.85), (1.05, 0, 0), (0, 0.3, 0), (0, 0, 0.95), "Chest")
    obox("Glow", (0, cy - 0.12, 3.9), (0.6, 0, 0.6), (0, 0.08, 0), (-0.6, 0, 0.6), "Chest", uvmode="rune")
    spike("Tan", (0, -2.95, 2.6), (0, -2.8, 1.75), 1.0, 0.3, bone="Chest", up=(0, -1, 0))

    # dorsal armour: gold bands across the back wrapping down the flanks, dark raised blocks, spine spikes
    bands = [(-1.9, "Chest", 1.0), (-1.0, "Chest", 1.0), (-0.1, "Chest", 1.0), (0.8, "Chest", 1.0),
             (1.7, "Spine", 1.0), (2.6, "Spine", 0.95), (3.5, "Hips", 0.9), (4.4, "Hips", 0.85),
             (5.3, "Hips", 0.75), (6.1, "Hips", 0.7)]
    for i, (y, bn, sc) in enumerate(bands):
        zc, hw, hh = 4.1, 2.2 * sc, 1.7 * sc
        for rr in range(len(rings) - 1):
            (ca, wa, ha), (cb, wb, hb) = rings[rr], rings[rr + 1]
            if ca[1] <= y <= cb[1]:
                t = (y - ca[1]) / (cb[1] - ca[1])
                zc, hw, hh = ca[2] + (cb[2] - ca[2]) * t, wa + (wb - wa) * t, ha + (hb - ha) * t
        top = zc + hh
        arc = [(-hw * 0.6, top + 0.05), (0, top + 0.18), (hw * 0.6, top + 0.05)]
        if i % 2 == 0:
            arc = [(-hw * 0.92, zc + hh * 0.35)] + arc + [(hw * 0.92, zc + hh * 0.35)]
        if i % 4 == 0:
            arc = [(-hw * 0.8, zc - hh * 0.85), (-hw - 0.1, zc - hh * 0.2)] + arc + [(hw + 0.1, zc - hh * 0.2),
                                                                                 (hw * 0.8, zc - hh * 0.85)]
        for k in range(len(arc) - 1):
            (x0, z0), (x1, z1) = arc[k], arc[k + 1]
            brick("Gold", (x0, y, z0), (x1, y, z1), 0.62, 0.42, bn, up=(x0 + x1, 0, (z0 + z1 - 2 * zc) * 2), gap=0.05,
                  drop="down")
        h = (1.45 if i < 8 else 1.1) * (1.0 if i % 2 == 0 else 0.68)
        spike("Gold" if i % 2 == 0 else "Bone", (0, y + 0.05, top + 0.05), (0, y + 0.85, top + 0.3 + h), 0.36, 0.8,
              bone=bn, up=(0, -1, 0), cap=True)
        SPINE_PTS.append(((0, y, top + 0.28), bn))


# ============================================================== neck + head
def build_neck_head():
    nrings = [((0, -2.0, 5.0), 1.2, 1.15), ((0, -2.8, 5.7), 1.2, 1.15), ((0, -3.35, 6.55), 1.05, 1.0),
              ((0, -3.7, 7.2), 0.95, 0.9)]
    tube("Dark", nrings, ["Chest", "Neck1", "Neck2", "Neck3"], up=(0, 1, 0), chamfer=0.48)
    throat = [(-3.3, 5.05), (-3.75, 5.65), (-4.1, 6.25), (-4.4, 6.8), (-4.6, 7.2)]
    for i in range(len(throat) - 1):
        (y0, z0), (y1, z1) = throat[i], throat[i + 1]
        brick("Tan", (0, y0, z0), (0, y1, z1), 1.7 - 0.12 * i, 0.45, ["Neck1", "Neck2", "Neck3", "Neck3"][i],
              up=(0, -1, -0.5), gap=0.05)
    for i, (c, hw, hh) in enumerate(nrings[:3]):
        bn = ["Neck1", "Neck2", "Neck3"][i]
        c = V(c)
        for s in (1, -1):
            obox("Gold", c + V((s * (hw + 0.05), 0.2, 0.25)), (0.18, 0, 0), (0, 0.4, -0.2), (0, 0.2, 0.4), bn)
        root = c + V((0, hh * 0.62, hh * 0.62))
        spike("Gold", root - V((0, 0.1, 0.1)), root + V((0, 1.4, 1.1)), 0.34, 0.7, bone=bn, up=(0, -1, 1), cap=True)
        SPINE_PTS.append((root + V((0, 0.08, 0.08)), bn))
    for s in (1, -1):
        strip("Gold", [X(s, (1.3, -2.6, 5.3)), X(s, (1.9, -2.4, 4.9)), X(s, (2.45, -2.0, 4.2)),
                       X(s, (2.6, -1.8, 3.3))], 0.7, 0.4, "Chest", up=X(s, (0.3, -1, 0.3)))

    H = "Head"
    HEAD_RINGS = [((0, -2.85, 7.6), 0.9, 0.8), ((0, -3.55, 7.6), 1.05, 0.9), ((0, -4.6, 7.45), 1.0, 0.82),
                  ((0, -5.6, 7.1), 0.8, 0.62), ((0, -6.55, 6.8), 0.5, 0.42)]
    tube("Dark", HEAD_RINGS, H, chamfer=0.4)
    # gold crown plate on the back of the skull that every horn root plugs into
    blade("Gold", [(0, -4.3, 8.5), (0, -3.5, 8.62), (0, -2.75, 8.45), (0, -2.35, 8.0)], 1.7, 0.5, H,
          up=(0, 0.2, 1), taper_to=0.9)

    def head_at(y):
        rs = HEAD_RINGS
        for a, b in zip(rs, rs[1:]):
            if b[0][1] <= y <= a[0][1]:
                t = (y - a[0][1]) / (b[0][1] - a[0][1])
                return a[0][2] + (b[0][2] - a[0][2]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t
        r = rs[0] if y > rs[0][0][1] else rs[-1]
        return r[0][2], r[1], r[2]
    obox("Glow", (0, -5.0, 6.5), (0.52, 0, 0), (0, 1.1, 0.16), (0, -0.05, 0.08), H, uvmode="throat")
    blade("Dark", [(0, -4.1, 8.3), (0, -5.2, 7.98), (0, -6.4, 7.45), (0, -7.0, 7.05)], 1.15, 0.4, H,
          up=(0, -0.3, 1), taper_to=0.55)
    blade("Gold", [(0, -6.35, 7.55), (0, -6.75, 7.85), (0, -6.95, 8.35)], 0.34, 0.34, H, up=(0, -1, 0.3))
    blade("Gold", [(0, -5.8, 7.95), (0, -5.0, 8.32), (0, -4.2, 8.62), (0, -3.5, 9.05), (0, -2.9, 10.1)], 0.6, 0.42,
          H, up=(0, 0.3, 1), tip_mat="Bone", tip_frac=0.3)
    for s in (1, -1):
        brick("Dark", X(s, (0.55, -4.1, 8.25)), X(s, (0.8, -5.45, 7.7)), 0.5, 0.42, H, up=X(s, (0.5, 0, 1)))
        blade("Gold", [X(s, (0.95, -5.45, 8.05)), X(s, (0.95, -4.5, 8.45)), X(s, (1.0, -3.4, 8.7)),
                       X(s, (1.1, -2.3, 8.8))], 0.42, 0.34, H, up=X(s, (0.4, 0, 1)))
        # eye: recessed dark socket rim around a real eyeball (glowing iris + slit pupil), facing out/forward
        en = X(s, (0.82, -0.55, 0.12)).normalized()
        ec = X(s, (0.8, -5.05, 7.62))
        eyeball(ec, 0.34, en, (0, 0, 1), H, seg=8, rings=4)
        et = en.cross(V((0, 0, 1))).normalized()
        eu = et.cross(en).normalized()
        rim = [ec + en * 0.12 + (et * math.cos(a) * 0.52 + eu * math.sin(a) * 0.4)
               for a in [math.radians(d) for d in (0, 60, 120, 180, 240, 300, 360)]]
        for k in range(6):
            brick("Dark", rim[k], rim[k + 1], 0.2, 0.26, H, up=en, gap=0.0, bevel=0.35)
        obox("Dark", X(s, (0.95, -4.3, 7.15)), (0.25, 0, 0), (0, 0.55, 0), (0, 0, 0.45), H)
        brick("Gold", X(s, (1.02, -4.0, 6.95)), X(s, (0.86, -5.7, 6.8)), 0.32, 0.36, H, up=X(s, (1, 0, 0.2)))
        brick("Gold", X(s, (0.95, -3.7, 8.05)), X(s, (1.05, -4.5, 7.95)), 0.35, 0.45, H, up=X(s, (1, 0, 0.3)))
        obox("Gold", X(s, (1.15, -3.75, 7.1)), X(s, (0.25, 0.08, 0)), (0, 0.5, 0), (0, 0, 0.7), H)
        blade("Gold", [X(s, (0.85, -3.7, 7.35)), X(s, (1.5, -2.8, 7.5)), X(s, (2.0, -1.9, 7.75))], 0.42, 0.3, H)
        blade("Gold", [X(s, (0.85, -3.8, 6.85)), X(s, (1.6, -2.9, 6.65)), X(s, (2.15, -2.1, 6.55))], 0.42, 0.3, H)
        for k in range(6):
            y = -4.45 - k * 0.38
            zc, hw, hh = head_at(y)
            bottom = zc - hh
            L = 0.34 + 0.03 * k if k < 5 else 0.62
            x = hw * 0.62
            spike("Bone", X(s, (x, y, bottom + 0.12)), X(s, (x * 0.97, y - 0.08, bottom - L)), 0.13,
                  0.3 if k < 5 else 0.36, bone=H, up=(0, -1, 0))
        blade("Gold", [X(s, (0.45, -3.75, 8.2)), X(s, (1.15, -3.45, 9.0)), X(s, (1.45, -2.75, 9.85)),
                       X(s, (1.45, -1.9, 10.55)), X(s, (1.15, -0.9, 11.15)), X(s, (0.8, 0.0, 11.5))], 0.98, 0.86, H,
              up=(0, -1, 0), tip_mat="Bone", tip_frac=0.4)
        blade("Gold", [X(s, (0.55, -3.3, 8.05)), X(s, (1.5, -2.9, 8.5)), X(s, (1.95, -2.0, 8.95)),
                       X(s, (2.15, -0.9, 9.25)), X(s, (2.1, 0.2, 9.45))], 0.8, 0.68, H, up=(0, -1, 0),
              tip_mat="Bone", tip_frac=0.4)
        blade("Gold", [X(s, (0.7, -3.1, 7.6)), X(s, (1.85, -2.7, 7.85)), X(s, (2.55, -1.9, 8.15)),
                       X(s, (3.0, -0.9, 8.3)), X(s, (3.2, 0.1, 8.35))], 0.7, 0.56, H, up=(0, 0, 1),
              tip_mat="Bone", tip_frac=0.4)
        blade("Gold", [X(s, (0.3, -2.95, 8.1)), X(s, (0.8, -2.55, 8.45)), X(s, (0.95, -1.6, 8.95)),
                       X(s, (0.95, -0.6, 9.3))], 0.6, 0.5, H, up=(0, 0, 1), tip_mat="Bone", tip_frac=0.4)

    Jb = "Jaw"
    tube("Dark", [((0, -4.05, 6.35), 0.88, 0.36), ((0, -4.9, 5.8), 0.75, 0.32), ((0, -5.7, 5.25), 0.6, 0.26)], Jb,
         up=(0, -0.55, 0.85), chamfer=0.42)
    obox("Glow", (0, -4.8, 6.02), (0.45, 0, 0), (0, 0.8, -0.52), (0, 0.03, 0.05), Jb, uvmode="throat")
    strip("Tan", [(0, -4.1, 5.95), (0, -4.9, 5.42), (0, -5.7, 4.9)], 1.25, 0.32, Jb, up=(0, 0.55, -0.85),
          taper_to=0.9)
    for s in (1, -1):
        jup = V((0, -0.55, 0.85)).normalized()
        jr = [((0, -4.05, 6.35), 0.88, 0.36), ((0, -4.9, 5.8), 0.75, 0.32), ((0, -5.7, 5.25), 0.6, 0.26)]
        for k in range(5):
            t = 0.1 + 0.85 * k / 4
            seg_i = min(int(t * 2), 1)
            u = t * 2 - seg_i
            (c0, w0, h0), (c1, w1_, h1_) = jr[seg_i], jr[seg_i + 1]
            c = V(c0).lerp(V(c1), u)
            hw, hh = w0 + (w1_ - w0) * u, h0 + (h1_ - h0) * u
            base = c + V((s * hw * 0.6, 0, 0)) + jup * (hh - 0.1)
            L = 0.3 if k < 4 else 0.5
            spike("Bone", base, base + jup * L + V((0, -0.06, 0)), 0.12, 0.28 if k < 4 else 0.34, bone=Jb,
                  up=(0, -1, 0))
        spike("Gold", X(s, (0.75, -4.2, 5.9)), X(s, (1.25, -3.3, 5.3)), 0.4, 0.35, bone=Jb)


# ============================================================== legs
def claw(p, fwd, size, bone):
    """reference claw/foot detail: a dark toe knuckle with a thick cream claw that arches forward and hooks down"""
    fwd = V(fwd).normalized()
    p = V(p)
    z = V((0, 0, 1))
    brick("Dark", p - fwd * size * 0.7 + z * size * 0.3, p + fwd * size * 0.25 + z * size * 0.2, size * 0.95,
          size * 0.95, bone, gap=0.0, w1=size * 0.9, h1=size * 0.8, bevel=0.3, drop="start")
    blade("Bone", [p + fwd * size * 0.05 + z * size * 0.25, p + fwd * size * 0.95 + z * size * 0.3,
                   p + fwd * size * 1.65 - z * size * 0.15, p + fwd * size * 1.9 - z * size * 0.85],
          size * 0.9, size * 1.0, bone, up=(0, 0, 1), taper_to=size * 0.35)


def build_legs():
    def front(s, sfx):
        L = leg_joints(s)
        ua, fa, ha = "UpperArm" + sfx, "Forearm" + sfx, "Hand" + sfx
        ua_mid = L["UpperArm"].lerp(L["Forearm"], 0.5) + V((0, -0.25, 0))
        tube("Dark", [(L["UpperArm"] + V((0, 0, 0.35)), 1.3, 1.35), (ua_mid, 1.3, 1.35), (L["Forearm"], 0.95, 0.95)],
             ua, up=(0, -1, 0), chamfer=0.5, caps=(False, False))
        fa_mid = L["Forearm"].lerp(L["Hand"], 0.4) + V((0, 0, 0.1))
        tube("Dark", [(L["Forearm"], 1.0, 1.0), (fa_mid, 1.08, 1.02), (L["Hand"] + V((0, 0, 0.25)), 0.82, 0.8)],
             fa, up=(0, 0, 1), chamfer=0.5, caps=(False, False))
        # elbow blade spike pointing back
        blade("Gold", [L["Forearm"] + V((0, 0.4, 0.2)), L["Forearm"] + V((0, 1.2, 0.35)),
                       L["Forearm"] + V((0, 1.9, 0.75))], 0.5, 0.45, fa, up=(0, 0, 1))
        ring_of_bricks(L["UpperArm"] + X(s, (1.42, -0.1, -0.1)), X(s, (1, -0.15, 0)), 1.3, ua, n=6, bw=0.6, bh=0.5)
        # angular forearm armour: bevelled front plates following the forearm angle + outer plate
        fdir = (L["Hand"] - L["Forearm"]).normalized()
        fnrm = V((0, -fdir.z, fdir.y)).normalized()
        if fnrm.y > 0:
            fnrm = -fnrm
        for a0, a1 in ((0.08, 0.45), (0.5, 0.85)):
            brick("Gold", L["Forearm"].lerp(L["Hand"], a0) + fnrm * 1.0, L["Forearm"].lerp(L["Hand"], a1) + fnrm * 0.9,
                  1.5, 0.32, fa, up=fnrm, gap=0.04, w1=1.3, drop="down", bevel=0.3)
        strip("Gold", [L["Forearm"] + X(s, (1.05, -0.2, -0.1)), L["Forearm"].lerp(L["Hand"], 0.45) + X(s, (1.1, 0, 0.1)),
                       L["Forearm"].lerp(L["Hand"], 0.85) + X(s, (0.9, 0, 0.2))], 0.8, 0.32, fa, up=(1, 0, 0), gap=0.05,
              drop="down")
        strip("Gold", [L["UpperArm"] + X(s, (-0.2, -1.35, -0.9)), L["UpperArm"] + X(s, (0.7, -1.3, -0.95)),
                       L["UpperArm"] + X(s, (1.4, -0.6, -1.1)), L["UpperArm"] + X(s, (1.45, 0.5, -1.3))], 0.55, 0.42, ua,
              up=X(s, (0.5, -0.7, 0)), gap=0.05, drop="down")
        strip("Gold", [L["Hand"] + X(s, (-1.0, 0.1, 0.55)), L["Hand"] + X(s, (0.0, 0.1, 0.6)),
                       L["Hand"] + X(s, (1.0, 0.1, 0.55))], 0.5, 0.4, fa, up=(0, 0, 1), gap=0.04)
        brick("Dark", L["Hand"] + V((0, 0.6, -0.35)), L["Hand"] + V((0, -1.3, -0.4)), 2.5, 1.15, ha, gap=0.0,
              w1=2.4, h1=0.6, bevel=0.3)
        for k in range(4):
            x = (k - 1.5) * 0.62
            claw(L["Hand"] + V((x, -1.2, -0.3)), (0, -1, 0), 0.6, ha)

    def rear(s, sfx):
        L = leg_joints(s)
        th, sh, ft = "Thigh" + sfx, "Shin" + sfx, "Foot" + sfx
        th_mid = L["Thigh"].lerp(L["Shin"], 0.45) + V((0, 0.3, 0))
        tube("Dark", [(L["Thigh"] + V((0, 0.2, 0.45)), 1.35, 1.4), (th_mid, 1.4, 1.35), (L["Shin"], 0.95, 0.9)], th,
             up=(0, -1, 0), chamfer=0.5, caps=(False, False))
        tube("Dark", [(L["Shin"], 0.95, 0.9), (L["Foot"] + V((0, 0, 0.25)), 0.75, 0.72)], sh, up=(0, -1, 0),
             chamfer=0.5, caps=(False, False))
        ring_of_bricks(L["Thigh"] + X(s, (1.45, -0.1, -0.25)), X(s, (1, 0, 0)), 1.15, th, n=6, bw=0.55, bh=0.45)
        spike("Gold", L["Shin"] + X(s, (0.2, -0.6, 0.2)), L["Shin"] + X(s, (0.3, -1.4, 0.35)), 0.5, 0.5, bone=sh)
        strip("Gold", [L["Thigh"] + X(s, (-0.3, -1.3, -0.9)), L["Thigh"] + X(s, (0.7, -1.3, -1.0)),
                       L["Thigh"] + X(s, (1.45, -0.7, -1.35))], 0.55, 0.42, th, up=X(s, (0.5, -0.7, 0)), gap=0.05,
              drop="down")
        strip("Gold", [L["Shin"] + X(s, (-0.7, -0.95, -0.45)), L["Shin"] + X(s, (0.3, -1.05, -0.5)),
                       L["Shin"] + X(s, (1.05, -0.4, -0.55))], 0.5, 0.4, sh, up=X(s, (0.4, -0.8, 0)), gap=0.05,
              drop="down")
        strip("Gold", [L["Foot"] + X(s, (-0.95, 0.0, 0.55)), L["Foot"] + X(s, (0.0, 0.0, 0.6)),
                       L["Foot"] + X(s, (0.95, 0.0, 0.55))], 0.5, 0.4, sh, up=(0, 0, 1), gap=0.04)
        brick("Dark", L["Foot"] + V((0, 0.45, -0.35)), L["Foot"] + V((0, -1.25, -0.4)), 2.0, 1.05, ft, gap=0.0,
              w1=1.95, h1=0.55, bevel=0.3)
        for k in range(3):
            x = (k - 1) * 0.6
            claw(L["Foot"] + V((x, -1.2, -0.3)), (0, -1, 0), 0.55, ft)

    mirror(front)
    mirror(rear)


# ============================================================== tail
def build_tail():
    rings = [(TAIL[i], TAIL_HW[i], TAIL_HH[i]) for i in range(len(TAIL))]
    tube("Dark", rings, ["Tail%d" % min(i + 1, 7) for i in range(len(TAIL))], chamfer=0.45)
    n = len(TAIL) - 1
    for i in range(n):
        b = "Tail%d" % (i + 1)
        p0, p1 = TAIL[i], TAIL[i + 1]
        side, d, up = frame(p1 - p0)
        hw = (TAIL_HW[i] + TAIL_HW[i + 1]) / 2
        hh = (TAIL_HH[i] + TAIL_HH[i + 1]) / 2
        mid = (p0 + p1) / 2
        L = (p1 - p0).length
        brick("Gold", mid - d * L * 0.42 + up * hh * 0.95, mid + d * L * 0.1 + up * hh * 0.95, hw * 1.3, 0.34, b,
              up=up, gap=0.02, drop="down")
        sh = 1.6 - 0.12 * i
        spike("Gold", mid - d * L * 0.1 + up * (hh - 0.12), mid + d * L * 0.55 + up * (hh + sh), max(0.3, hw * 0.5),
              L * 0.8, bone=b, up=-d, cap=True)
        SPINE_PTS.append((p0 + up * (TAIL_HH[i] + 0.12), b))
        for s in (1, -1):
            c = mid + side * s * hw * 0.98
            obox("Glow", c + side * s * 0.1, side * s * 0.05, d * hh * 0.42, up * hh * 0.42, b, uvmode="rune")
            brick("Gold", mid - d * L * 0.45 + side * s * hw * 0.8 - up * hh * 0.7,
                  mid + d * L * 0.05 + side * s * hw * 0.8 - up * hh * 0.7, 0.35, hh * 0.55, b, up=side * s, gap=0.02,
                  drop="down")
    tip_dir = (TAIL[-1] - TAIL[-2]).normalized()
    SPINE_PTS.append((TAIL[-1] + tip_dir * 1.9, "Tail7"))


# ============================================================== wings
def build_wings():
    def wing(s, sfx):
        W = wing_joints(s)
        w1, w2, wh = "Wing1" + sfx, "Wing2" + sfx, "WingHand" + sfx
        f1, f1b, f2, f3, f4 = ("Finger1" + sfx, "Finger1b" + sfx, "Finger2" + sfx, "Finger3" + sfx, "Finger4" + sfx)
        hand = W["WingHand"]
        nrm = (hand - W["Wing1"]).cross(W["F2Tip"] - hand).normalized()
        if nrm.x * s < 0:
            nrm = -nrm
        tube("Dark", [(W["Wing1"], 0.55, 0.55), (W["Wing2"], 0.48, 0.48)], w1, up=nrm, chamfer=0.42)
        tube("Dark", [(W["Wing2"], 0.48, 0.48), (hand, 0.42, 0.42)], w2, up=nrm, chamfer=0.42)
        out = X(s, (0.45, -0.25, 0))
        blade("Gold", [W["Wing1"] + out, W["Wing2"] + out, hand + out + V((0, 0, 0.3)), hand + out + V((0, -0.3, 1.6))],
              0.7, 0.5, [w1, w2, wh, wh], up=nrm, taper_to=0.35)
        obox("Dark", hand + V((0, 0, 0.1)), (0.5, 0, 0), (0, 0.5, 0), (0, 0, 0.45), wh)
        obox("Gold", hand + X(s, (0.25, -0.2, 0.45)), (0.45, 0, 0), (0, 0.4, 0), (0, 0, 0.25), wh)


        F1 = W["F1"]
        bones_f1 = [f1, f1, f1b, f1b, f1b]
        f1_tip = F1[-1] + (F1[-1] - F1[-2]).normalized() * 1.4
        blade("Gold", F1 + [f1_tip], 0.95, 0.6, bones_f1 + [f1b, f1b], up=nrm, taper_to=0.3)
        for i in range(len(F1) - 1):
            a, c = F1[i], F1[i + 1]
            inward = W["F3Tip"] - (a + c) / 2
            inward = (inward - nrm * inward.dot(nrm)).normalized()
            if i < 2:
                brick("Dark", a + inward * 0.42, c + inward * 0.42, 0.26, 0.45, bones_f1[i], up=nrm, gap=0.1)
        for i in (1, 2, 3):
            p = F1[i]
            spike("Gold", p, p + V((0, 0.7, 1.0)) + X(s, (0.15, 0, 0)), 0.26, 0.5, bone=bones_f1[i], up=nrm)
        for tipk, bn, k in (("F2Tip", f2, 3), ("F3Tip", f3, 3), ("F4Tip", f4, 2)):
            tip = W[tipk]
            pts = [hand.lerp(tip, t / k) for t in range(k + 1)]
            dv = (tip - hand).normalized()
            blade("Gold", pts + [tip + dv * 1.3], 0.8, 0.5, bn, up=nrm, taper_to=0.25)
            sd = nrm.cross(dv).normalized()
            if sd.z > 0:
                sd = -sd
            brick("Dark", hand.lerp(tip, 0.15) + sd * 0.55, tip - dv * 0.3 + sd * 0.5, 0.3, 0.5, bn, up=nrm, gap=0.05)


        # membrane with stair-stepped scalloped trailing edges
        body = W["Body"]
        root = W["Wing1"] + X(s, (-0.3, 0.2, -0.3))
        pts, pbones = [], []

        def P(p, bw):
            pts.append(V(p))
            pbones.append(bw)
            return len(pts) - 1

        iH = P(hand, [(wh, 1.0)])
        iRoot = P(root, [(w1, 1.0)])
        iElbow = P(W["Wing2"], [(w2, 1.0)])
        iBody = P(body, [("Spine", 1.0)])
        f1_idx = [iH] + [P(F1[i], [(bones_f1[i - 1], 1.0)]) for i in range(1, len(F1))]
        fl = {}
        for tipk, bn in (("F2Tip", f2), ("F3Tip", f3), ("F4Tip", f4)):
            fl[tipk] = [iH, P(hand.lerp(W[tipk], 0.5), [(bn, 1.0)]), P(W[tipk], [(bn, 1.0)])]

        def stepped(ia, ib, depth, ba, bb, steps=5):
            a, b = pts[ia], pts[ib]
            out = [ia]
            for k in range(1, steps * 2):
                t = k / (steps * 2)
                base = a.lerp(b, t)
                q = base + (hand - base).normalized() * (math.sin(math.pi * t) * depth)
                w = 1.0 - t
                out.append(P(q, [(ba, w), (bb, 1 - w)] if ba != bb else [(ba, 1.0)]))
            out.append(ib)
            return out

        faces = []

        def fan(center, edge):
            for k in range(len(edge) - 1):
                faces.append((center, edge[k], edge[k + 1]))

        e12 = stepped(f1_idx[-1], fl["F2Tip"][2], 2.0, f1b, f2, steps=3)
        fan(fl["F2Tip"][1], [f1_idx[2], f1_idx[3], f1_idx[4]] + e12)
        faces.append((iH, f1_idx[1], fl["F2Tip"][1]))
        faces.append((f1_idx[1], f1_idx[2], fl["F2Tip"][1]))
        e23 = stepped(fl["F2Tip"][2], fl["F3Tip"][2], 1.7, f2, f3, steps=3)
        fan(fl["F3Tip"][1], [fl["F2Tip"][1]] + e23)
        faces.append((iH, fl["F2Tip"][1], fl["F3Tip"][1]))
        e34 = stepped(fl["F3Tip"][2], fl["F4Tip"][2], 1.35, f3, f4, steps=3)
        fan(fl["F4Tip"][1], [fl["F3Tip"][1]] + e34)
        faces.append((iH, fl["F3Tip"][1], fl["F4Tip"][1]))
        e4b = stepped(fl["F4Tip"][2], iBody, 0.5, f4, "Spine", steps=3)
        fan(iRoot, [fl["F4Tip"][1]] + e4b)
        faces.append((iH, fl["F4Tip"][1], iRoot))
        faces.append((iElbow, iH, iRoot))

        span = F1[-1] - root
        span = (span - nrm * span.dot(nrm)).normalized()
        vert = nrm.cross(span).normalized()
        if vert.z < 0:
            vert = -vert
        co2 = [V(((p - root).dot(span), (p - root).dot(vert))) for p in pts]
        umin, umax = min(c.x for c in co2), max(c.x for c in co2)
        vmin, vmax = min(c.y for c in co2), max(c.y for c in co2)
        uv = [((c.x - umin) / (umax - umin), (c.y - vmin) / (vmax - vmin)) for c in co2]
        th = 0.05
        n = len(pts)
        verts = [p + nrm * th for p in pts] + [p - nrm * th for p in pts]
        ff, fuv = [], []
        for a, b, c in faces:
            ff.append((a, b, c))
            fuv.append([uv[a], uv[b], uv[c]])
            ff.append((a + n, c + n, b + n))
            fuv.append([uv[a], uv[c], uv[b]])
        add_piece("Membrane", verts, ff, pbones + pbones, uvmode="given", uvs=fuv)

    mirror(wing)


# ============================================================== assemble meshes / materials
def face_uvs(verts, face, mode):
    ps = [verts[i] for i in face]
    if mode == "solid":
        return [(0.5, 0.5)] * len(ps)
    if mode == "throat":
        return [(0.70 + 0.25 * (i % 2), 0.85) for i in range(len(ps))]
    e1 = ps[1] - ps[0]
    n = (ps[1] - ps[0]).cross(ps[-1] - ps[0])
    if n.length < 1e-9 or e1.length < 1e-9:
        return [(0.5, 0.5)] * len(ps)
    e1.normalize()
    e2 = n.normalized().cross(e1).normalized()
    co = [((p - ps[0]).dot(e1), (p - ps[0]).dot(e2)) for p in ps]
    if mode == "rune":
        umin, umax = min(c[0] for c in co), max(c[0] for c in co)
        vmin, vmax = min(c[1] for c in co), max(c[1] for c in co)
        du, dv = max(umax - umin, 1e-6), max(vmax - vmin, 1e-6)
        if min(du, dv) < 0.25:
            return [(0.5, 0.5)] * len(ps)
        return [((c[0] - umin) / du * (1 / 3), (c[1] - vmin) / dv) for c in co]
    cu = sum(c[0] for c in co) / len(co)
    cv = sum(c[1] for c in co) / len(co)
    cell = STUD_TILE_WORLD / 4
    return [((c[0] - cu + cell / 2) / STUD_TILE_WORLD, (c[1] - cv + cell / 2) / STUD_TILE_WORLD) for c in co]


MAT_IMAGES = {
    "Dark": ("Dragon_Dark_Stud.png", 0.0), "Gold": ("Dragon_Gold_Stud.png", 0.0),
    "Tan": ("Dragon_Tan_Stud.png", 0.0), "Bone": ("Dragon_Bone_Stud.png", 0.0),
    "Glow": ("Dragon_Glow.png", 1.0), "Membrane": ("Dragon_WingMembrane.png", 0.0),
    "Eye": ("Dragon_Eye.png", 1.2),
}


def make_material(name):
    image, emit = MAT_IMAGES[name]
    mat = bpy.data.materials.new("MAT-Dragon_" + name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(TEX, image), check_existing=True)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6
    if name in ("Membrane", "Glow"):
        bsdf.inputs["Roughness"].default_value = 0.9
        for inp in bsdf.inputs:
            if inp.name in ("Specular IOR Level", "Specular"):
                inp.default_value = 0.05
    nmap_path = os.path.join(TEX, image.replace(".png", "_Normal.png"))
    if os.path.exists(nmap_path):
        ntex = nt.nodes.new("ShaderNodeTexImage")
        ntex.image = bpy.data.images.load(nmap_path, check_existing=True)
        ntex.image.colorspace_settings.name = "Non-Color"
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 1.0
        nt.links.new(ntex.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if emit:
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = emit
    return mat


def build_meshes(arm):
    objs = []
    for mname, pieces in PIECES.items():
        if not pieces:
            continue
        me = bpy.data.meshes.new("Dragon_" + mname)
        bm = bmesh.new()
        uvl = bm.loops.layers.uv.new("UVMap")
        dl = bm.verts.layers.deform.verify()
        groups = {}
        for pc in pieces:
            bv = [bm.verts.new(v) for v in pc["verts"]]
            for v, bw in zip(bv, pc["bones"]):
                for bn, w in bw:
                    v[dl][groups.setdefault(bn, len(groups))] = w
            for fi, f in enumerate(pc["faces"]):
                try:
                    face = bm.faces.new([bv[i] for i in f])
                except ValueError:
                    continue
                uvs = pc["uvs"][fi] if pc["uvmode"] == "given" else face_uvs(pc["verts"], f, pc["uvmode"])
                for loop, uv in zip(face.loops, uvs):
                    loop[uvl].uv = uv
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new("Dragon_" + mname, me)
        bpy.context.scene.collection.objects.link(ob)
        for bn, gi in sorted(groups.items(), key=lambda kv: kv[1]):
            ob.vertex_groups.new(name=bn)
        me.materials.append(make_material(mname))
        if arm:
            ob.parent = arm
            ob.modifiers.new("Armature", "ARMATURE").object = arm
        objs.append(ob)
    return objs


# ============================================================== rig
def build_armature():
    arm_data = bpy.data.armatures.new("DragonRig")
    arm = bpy.data.objects.new("AncientDragon", arm_data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_data.edit_bones

    def bone(name, head, tail, parent=None, connect=False):
        b = eb.new(name)
        b.head, b.tail, b.roll = V(head), V(tail), 0
        if parent:
            b.parent = eb[parent]
            b.use_connect = connect

    bone("Root", J["Root"], J["Root"] + V((0, 0, 1.5)))
    bone("Hips", J["Hips"], J["Spine"], "Root")
    bone("Spine", J["Spine"], J["Chest"], "Hips", True)
    bone("Chest", J["Chest"], J["Neck1"], "Spine", True)
    bone("Neck1", J["Neck1"], J["Neck2"], "Chest", True)
    bone("Neck2", J["Neck2"], J["Neck3"], "Neck1", True)
    bone("Neck3", J["Neck3"], J["Head"], "Neck2", True)
    bone("Head", J["Head"], J["HeadEnd"], "Neck3", True)
    bone("Jaw", J["Jaw"], J["JawEnd"], "Head")
    prev = "Hips"
    for i in range(len(TAIL) - 1):
        n = "Tail%d" % (i + 1)
        bone(n, TAIL[i], TAIL[i + 1], prev, i > 0)
        prev = n
    for s, sfx in ((1, "_L"), (-1, "_R")):
        L = leg_joints(s)
        bone("UpperArm" + sfx, L["UpperArm"], L["Forearm"], "Chest")
        bone("Forearm" + sfx, L["Forearm"], L["Hand"], "UpperArm" + sfx, True)
        bone("Hand" + sfx, L["Hand"], L["HandEnd"], "Forearm" + sfx, True)
        bone("Thigh" + sfx, L["Thigh"], L["Shin"], "Hips")
        bone("Shin" + sfx, L["Shin"], L["Foot"], "Thigh" + sfx, True)
        bone("Foot" + sfx, L["Foot"], L["FootEnd"], "Shin" + sfx, True)
        W = wing_joints(s)
        bone("Wing1" + sfx, W["Wing1"], W["Wing2"], "Chest")
        bone("Wing2" + sfx, W["Wing2"], W["WingHand"], "Wing1" + sfx, True)
        bone("WingHand" + sfx, W["WingHand"], W["WingHand"] + V((0, 0, 0.8)), "Wing2" + sfx, True)
        bone("Finger1" + sfx, W["F1"][0], W["F1"][2], "WingHand" + sfx)
        bone("Finger1b" + sfx, W["F1"][2], W["F1"][5], "Finger1" + sfx, True)
        bone("Finger2" + sfx, W["WingHand"], W["F2Tip"], "WingHand" + sfx)
        bone("Finger3" + sfx, W["WingHand"], W["F3Tip"], "WingHand" + sfx)
        bone("Finger4" + sfx, W["WingHand"], W["F4Tip"], "WingHand" + sfx)
    bpy.ops.object.mode_set(mode="OBJECT")
    return arm


# ============================================================== main
def main(rig=True):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.01
    sc.render.fps = 30
    build_torso()
    build_neck_head()
    build_legs()
    build_tail()
    build_wings()
    build_spine_ridge()
    apply_offsets()
    from mathutils import Matrix
    J["JawEnd"] = J["Jaw"] + Matrix.Rotation(math.radians(-JAW_CLOSE_DEG), 3, "X") @ (J["JawEnd"] - J["Jaw"])
    for k, bn in (("Head", "Head"), ("HeadEnd", "Head"), ("Jaw", "Jaw"), ("JawEnd", "Jaw"), ("Neck3", "Neck3"),
                  ("Neck2", "Neck2"), ("Neck1", "Neck1")):
        J[k] = J[k] + OFFSETS[bn]
    arm = build_armature() if rig else None
    objs = build_meshes(arm)
    per = {}
    for ob in objs:
        ob.data.calc_loop_triangles()
        per[ob.name] = len(ob.data.loop_triangles)
    print("TRIS_TOTAL", sum(per.values()), per)
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "AncientDragon.blend"))


if __name__ == "__main__":
    main(rig="--no-rig" not in sys.argv)
