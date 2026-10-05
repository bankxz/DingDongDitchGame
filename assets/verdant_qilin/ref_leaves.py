"""Leaves placed one-by-one from the LEFT VIEW of the reference sheet.
Each row: (base_px, base_py, tip_px, tip_py, width_px, colour, x_base, x_tip)
px/py are pixels in the 365x290 left-view crop; converted to model units below (24.2 px per stud,
ground at py 277, nose at px 10 -> y -9.7).  Each leaf is mirrored to the other side (x -> -x)."""
import math
from mathutils import Vector as V

PXU = 24.2
def to_y(px): return -9.7 + (px - 10) / PXU
def to_z(py): return (277 - py) / PXU
SLOT = {'L': 'limeBright', 'l': 'lime', 'm': 'mid', 'd': 'dark', 'D': 'deep'}

# (bx, by, tx, ty, w, col, xb, xt)
HEAD = [
    (14, 97, 21, 73, 8, 'l', 0.8, 0.9), (26, 88, 31, 62, 6, 'm', 0.0, 0.0), (34, 93, 21, 101, 7, 'L', 0.9, 1.0),
    (45, 96, 64, 84, 10, 'L', 1.1, 1.3), (52, 102, 66, 118, 8, 'l', 1.1, 1.3),
]
MANE = [
    (80, 90, 134, 99, 14, 'L', 1.3, 1.8), (88, 103, 114, 118, 9, 'L', 1.3, 1.6), (62, 86, 99, 95, 10, 'l', 1.4, 1.7),
    (70, 71, 117, 79, 9, 'd', 1.2, 1.5), (82, 70, 100, 62, 7, 'L', 1.1, 1.3), (80, 132, 76, 114, 8, 'L', 1.2, 1.3),
    (60, 108, 75, 128, 8, 'd', 1.0, 1.1), (100, 112, 125, 128, 9, 'd', 1.3, 1.5), (90, 98, 110, 113, 8, 'm', 1.2, 1.4),
    (105, 76, 128, 92, 8, 'd', 1.4, 1.7), (60, 76, 75, 98, 9, 'd', 1.0, 1.1), (100, 142, 127, 126, 10, 'L', 1.4, 1.7),
]
MANE += [
    (55, 100, 85, 112, 9, 'd', 1.1, 1.2), (98, 106, 128, 117, 9, 'l', 1.3, 1.5), (100, 118, 138, 130, 9, 'm', 1.3, 1.5),
    (112, 140, 146, 124, 9, 'L', 1.5, 1.7), (45, 140, 35, 118, 8, 'd', 1.0, 1.0), (50, 135, 60, 115, 8, 'd', 1.0, 1.1),
    (40, 112, 60, 104, 8, 'm', 1.0, 1.1), (66, 118, 90, 108, 9, 'D', 1.1, 1.2), (75, 70, 96, 82, 9, 'D', 1.0, 1.1),
    (50, 70, 70, 85, 8, 'm', 0.9, 1.0), (72, 100, 78, 125, 8, 'D', 1.0, 1.0),
]
BODY = [
    (56, 180, 101, 142, 22, 'L', 1.9, 2.0), (100, 156, 126, 128, 13, 'l', 1.8, 1.9), (117, 148, 147, 155, 12, 'l', 1.7, 1.8),
    (125, 145, 158, 128, 9, 'l', 1.5, 1.6), (160, 142, 190, 126, 9, 'L', 1.3, 1.4), (188, 141, 204, 137, 5, 'L', 1.0, 1.0),
    (130, 140, 155, 132, 8, 'd', 1.2, 1.3), (140, 142, 175, 135, 8, 'm', 1.1, 1.2), (170, 145, 198, 140, 7, 'd', 1.0, 1.1),
    (74, 194, 103, 170, 14, 'm', 1.8, 1.9), (92, 188, 110, 160, 9, 'm', 1.7, 1.8), (70, 208, 90, 188, 12, 'd', 1.7, 1.8),
    (95, 214, 105, 192, 10, 'D', 1.6, 1.7), (118, 181, 126, 176, 3, 'L', 1.6, 1.6),
    (40, 165, 32, 138, 8, 'l', 1.2, 1.4), (36, 172, 28, 150, 7, 'L', 1.1, 1.3), (44, 178, 52, 160, 7, 'l', 1.3, 1.5),
    (40, 185, 36, 203, 6, 'L', 1.0, 1.1),
]
BODY += [
    (60, 148, 85, 132, 9, 'd', 1.6, 1.6), (80, 140, 100, 128, 9, 'm', 1.5, 1.6), (100, 212, 120, 198, 10, 'D', 1.5, 1.5),
    (45, 205, 60, 185, 9, 'd', 1.6, 1.7), (118, 172, 135, 160, 8, 'd', 1.6, 1.7), (110, 168, 130, 150, 9, 'D', 1.5, 1.6),
    (140, 150, 170, 138, 8, 'd', 1.1, 1.2), (150, 143, 185, 133, 8, 'D', 1.0, 1.1), (165, 140, 196, 134, 7, 'm', 0.9, 1.0),
    (120, 135, 142, 126, 8, 'm', 1.3, 1.4), (76, 160, 96, 150, 9, 'D', 1.8, 1.8), (62, 196, 80, 176, 11, 'm', 1.7, 1.8),
]
LEGS = [
    (42, 254, 58, 226, 13, 'L', 2.0, 2.0), (24, 250, 40, 222, 8, 'l', 2.7, 2.7), (70, 260, 91, 249, 7, 'L', 1.1, 1.1),
    (62, 248, 95, 228, 9, 'd', 1.1, 1.1), (88, 222, 95, 212, 4, 'L', 1.1, 1.1),
    (145, 255, 155, 235, 6, 'd', 1.3, 1.3), (175, 248, 188, 222, 7, 'd', 1.3, 1.3), (142, 262, 150, 244, 5, 'L', 1.3, 1.3),
    (210, 258, 230, 218, 12, 'L', 1.5, 1.5), (192, 250, 200, 235, 6, 'd', 1.5, 1.5),
]
TAIL = [
    (244, 152, 260, 126, 8, 'l', 0.5, 0.6), (236, 164, 249, 188, 8, 'L', 0.5, 0.7), (258, 140, 296, 125, 14, 'l', 0.6, 0.9),
    (280, 142, 324, 149, 12, 'm', 0.7, 1.0), (255, 152, 300, 145, 14, 'd', 0.6, 0.9), (262, 157, 290, 172, 12, 'L', 0.7, 0.9),
    (285, 160, 333, 191, 20, 'm', 0.7, 1.2), (268, 172, 271, 209, 10, 'D', 0.6, 0.8), (280, 172, 292, 223, 10, 'd', 0.6, 0.9),
    (292, 172, 318, 227, 22, 'L', 0.7, 1.0), (310, 175, 335, 190, 12, 'l', 0.8, 1.2),
]
TAIL += [
    (232, 152, 262, 156, 6, 'D', 0.4, 0.5), (300, 185, 325, 215, 16, 'l', 0.8, 1.1), (275, 190, 282, 218, 8, 'D', 0.6, 0.7),
    (296, 160, 330, 170, 10, 'm', 0.9, 1.2), (250, 145, 285, 138, 9, 'D', 0.5, 0.7), (270, 150, 305, 158, 12, 'd', 0.7, 1.0),
    (290, 185, 300, 222, 9, 'm', 0.7, 0.9),
]
# FRONT view rows: (bx, bpy, tx, tpy, w, col, y_base, y_tip) - px in the 360x460 front crop, 39.4 px/stud, centre px 178, ground py 443
FRONT = [
    (178, 100, 178, 52, 34, 'l', -8.7, -8.4), (165, 262, 140, 232, 24, 'l', -8.9, -8.6), (178, 262, 178, 224, 30, 'L', -9.0, -8.7),
    (150, 275, 108, 262, 24, 'l', -8.9, -8.5), (148, 288, 118, 322, 22, 'l', -9.0, -8.7), (155, 300, 140, 335, 18, 'L', -9.0, -8.9),
    (115, 240, 62, 255, 30, 'l', -7.2, -6.2), (110, 255, 62, 288, 32, 'L', -7.0, -6.0), (112, 268, 80, 298, 26, 'l', -7.2, -6.4),
    (100, 272, 70, 322, 30, 'd', -6.8, -6.0), (95, 300, 72, 330, 24, 'D', -6.6, -6.0),
    (130, 135, 95, 125, 24, 'L', -7.4, -6.6), (125, 150, 90, 182, 24, 'l', -7.2, -6.6), (118, 188, 92, 216, 22, 'm', -7.0, -6.4),
    (140, 205, 120, 235, 20, 'd', -8.0, -7.6), (178, 205, 150, 232, 20, 'D', -8.4, -8.2), (88, 200, 92, 212, 12, 'L', -6.8, -6.8),
    (148, 160, 120, 140, 18, 'L', -8.3, -7.8), (140, 185, 118, 205, 20, 'l', -8.0, -7.4),
]
ANTLER = [(120, 55, 137, 45, 8, 'L', 3.0, 3.2), (111, 52, 125, 47, 5, 'L', 2.6, 2.8)]


def auto_rows(manual):
    """Leaves auto-extracted from the left view (tools/extract_leaves.py), skipping ones that overlap a hand-placed leaf."""
    import json, os
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'leaves_left.json')
    if not os.path.exists(p): return []
    def seg_dist(px, py, ax, ay, bx, by):
        vx, vy = bx - ax, by - ay; t = max(0, min(1, ((px - ax) * vx + (py - ay) * vy) / max(vx * vx + vy * vy, 1e-6)))
        return math.hypot(px - ax - t * vx, py - ay - t * vy)
    rows = []
    for a in json.load(open(p)):
        mx, my = (a['bx'] + a['tx']) / 2, (a['by'] + a['ty']) / 2
        if any(seg_dist(mx, my, m[0], m[1], m[2], m[3]) < 0.6 * max(a['w'], m[4] * 1.0) for m in manual): continue
        L = math.hypot(a['tx'] - a['bx'], a['ty'] - a['by'])
        if L < 5: continue
        ux, uy = (a['tx'] - a['bx']) / L, (a['ty'] - a['by']) / L
        bx, by = a['bx'] - ux * 0.12 * L, a['by'] - uy * 0.12 * L          # tuck the root under its neighbours
        k = a['lum'] / 255.0
        c = 'L' if a['lum'] > 190 else 'l' if a['lum'] > 150 else 'm' if a['lum'] > 105 else 'd' if a['lum'] > 70 else 'D'
        if a['bx'] > 230: xb = 0.35 + 0.8 * k
        elif a['by'] > 205: xb = 1.2 + 0.3 * k
        elif a['bx'] < 150 and a['by'] < 150: xb = 0.9 + 1.0 * k
        else: xb = 1.55 + 0.5 * k
        rows.append((bx, by, a['tx'], a['ty'], a['w'], c, xb, xb + 0.12))
    return rows


def place(g):
    leaf, BODYACC, WH, wpos, interp_w, W, Z = g['leaf'], g['BODY'], g['WH'], g['wpos'], g['interp_w'], g['W'], g['Z']
    def weight(sec, p, sx, bx):
        if sec in ('HEAD',): return WH
        if sec == 'MANE': return interp_w([(4.9, 'Chest'), (5.8, 'Neck1'), (6.6, 'Neck2'), (7.4, 'Head')], p.z)
        if sec == 'ANTLER': return WH
        if sec == 'AUTO':
            if bx > 230: return interp_w([(0.4, 'Tail1'), (1.0, 'Tail2'), (2.4, 'Tail3'), (3.4, 'Tail4')], p.y)
            if p.z < 2.4 and p.y < -5.5: return W(('FrontLower.' if bx < 125 else 'HindLower.') + ('L' if sx > 0 else 'R'))
            if p.z < 2.4: return W('HindLower.' + ('L' if sx > 0 else 'R'))
            if bx < 150 and p.z > 4.9 and p.y < -5.5: return interp_w([(4.9, 'Chest'), (5.8, 'Neck1'), (6.6, 'Neck2'), (7.4, 'Head')], p.z)
            return wpos(p)
        if sec == 'TAIL': return interp_w([(0.4, 'Tail1'), (1.0, 'Tail2'), (2.4, 'Tail3'), (3.4, 'Tail4')], p.y)
        if sec == 'LEGS':
            sd = 'L' if sx > 0 else 'R'
            return W(('FrontLower.' if bx < 125 else 'HindLower.') + sd)
        return wpos(p)
    for bx, bz, tx, tz, w, c, yb, yt in FRONT:
        for sx in (1, -1):
            xb, xt = (bx - 178) / 39.4, (tx - 178) / 39.4
            b = V((sx * xb, yb, (443 - bz) / 39.4)); t = V((sx * xt, yt, (443 - tz) / 39.4))
            d = t - b
            if d.length < 1e-3 or (abs(xb) < 0.02 and sx < 0): continue
            n = V((sx * (xb or 1), -1.2, 0.2)).normalized()
            leaf(BODYACC, b, d, d.length * 1.04, w * 1.85 / 39.4, interp_w([(4.9, 'Chest'), (5.8, 'Neck1'), (6.6, 'Neck2'), (7.4, 'Head')], b.z) if b.z > 4.6 else wpos(b),
                 SLOT[c], n=n, closed=True, ridge=0.1, droop=0.0)
    manual = HEAD + MANE + BODY + LEGS + TAIL
    AUTO = auto_rows(manual)
    for sec, rows in (('HEAD', HEAD), ('MANE', MANE), ('BODY', BODY), ('LEGS', LEGS), ('TAIL', TAIL), ('ANTLER', ANTLER), ('AUTO', AUTO)):
        for bx, by, tx, ty, w, c, xb, xt in rows:
            if sec == 'LEGS' or (sec == 'AUTO' and by > 205):
                sides = (-1,) if 125 < bx < 190 else ((1,) if bx >= 190 else (1, -1))      # far hind leg / near hind leg / front pair
            else:
                sides = (1, -1) if (xb or xt) else (1,)
            for sx in sides:
                b = V((sx * xb, to_y(bx), to_z(by))); t = V((sx * xt, to_y(tx), to_z(ty)))
                d = t - b; L = d.length
                if L < 1e-3: continue
                n = V((sx, 0, 0)) if (xb or xt) else V((1, 0, 0))
                leaf(BODYACC, b, d, L * 1.04, w * 2.3 / PXU, weight(sec, b, sx, bx), SLOT[c], n=n, closed=(sec not in ('BODY', 'AUTO')), ridge=0.1, droop=0.0)
