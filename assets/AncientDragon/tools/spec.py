"""Shared spec for the Ancient Dragon: palette, atlas layout, wing landmarks.

Design units ("u"): 1u = 10px of the LEFT SIDE reference panel.
Design coords: X lateral (+X = dragon's left), L = length from snout (0) to tail (36),
Z = height above ground. Blender: x=X, y=L-L0, z=Z (dragon faces -Y).
"""
import math

ATLAS = 2048
SW = 512            # swatch size in px
CELL_PX = 30        # one stud/cube cell in px
MARGIN = 16         # px margin inside each swatch (bleed guard)
CELLS = (SW - 2 * MARGIN) // CELL_PX   # 16 cells usable per swatch
CELL_U = 0.55       # world size (design units) of one stud cell

PALETTE = {
    'charcoal': (56, 58, 72),
    'gold':     (236, 164, 44),
    'cream':    (228, 200, 150),
    'horn':     (240, 216, 166),
    'glow':     (70, 250, 245),
    'teal':     (22, 80, 94),
    'dark':     (36, 38, 50),
    'belly':    (214, 188, 140),
}
SWATCH = {
    'charcoal': (0, 0), 'gold': (1, 0), 'cream': (2, 0), 'horn': (3, 0),
    'glow': (0, 1), 'teal': (1, 1), 'dark': (2, 1), 'belly': (3, 1),
    'rune_chest': (0, 2), 'rune_disc': (1, 2),
    'rune_tail': (0, 3), 'rune_knee': (1, 3),
}
WING_REGION = (1024, 1024, 1024, 1024)   # x, y (top-left px), w, h

# chest shield outline (x, z) in design units, pointing down
SHIELD = [(-1.75, 6.0), (1.75, 6.0), (1.95, 4.3), (0.0, 2.2), (-1.95, 4.3)]

# ---------------- wing landmarks (left wing, design coords X, L, Z) ----------------
W_ROOT = (2.4, 11.6, 8.1)
W_WRIST = (4.6, 10.4, 13.7)
W_LEAD = [W_WRIST, (5.4, 12.9, 14.5), (6.4, 16.4, 14.3), (7.5, 20.3, 12.9), (8.5, 23.9, 10.3),
          (9.3, 26.7, 6.0), (9.8, 28.6, 2.8)]
W_TIPS = [(4.6, 14.6, 7.8), (6.4, 18.6, 6.6), (8.2, 23.0, 5.2), W_LEAD[-1]]
# spread the wing outward about the root (front view reads wider than the side-solved plane)
_SPREAD = 1.3
W_WRIST = (W_ROOT[0] + (W_WRIST[0] - W_ROOT[0]) * _SPREAD,) + W_WRIST[1:]
W_LEAD = [(W_ROOT[0] + (p[0] - W_ROOT[0]) * _SPREAD,) + p[1:] for p in W_LEAD]
W_TIPS = [(W_ROOT[0] + (p[0] - W_ROOT[0]) * _SPREAD,) + p[1:] for p in W_TIPS]
W_LEAD[0] = W_WRIST; W_TIPS[3] = W_LEAD[-1]
# overall wing enlargement about the root (reference wing reads larger in the hero view)
_G = 1.1
def _grow(p): return tuple(r + (x - r) * _G for x, r in zip(p, W_ROOT))
W_WRIST = _grow(W_WRIST); W_LEAD = [_grow(p) for p in W_LEAD]; W_TIPS = [_grow(p) for p in W_TIPS]


def _sub(a, b): return tuple(x - y for x, y in zip(a, b))
def _add(a, b): return tuple(x + y for x, y in zip(a, b))
def _mul(a, s): return tuple(x * s for x in a)
def _dot(a, b): return sum(x * y for x, y in zip(a, b))
def _norm(a):
    l = math.sqrt(_dot(a, a)); return _mul(a, 1.0 / l)
def lerp(a, b, t): return _add(a, _mul(_sub(b, a), t))


def bezier(p0, c, p1, n):
    return [_add(_add(_mul(p0, (1 - t) ** 2), _mul(c, 2 * (1 - t) * t)), _mul(p1, t * t))
            for t in [i / (n - 1) for i in range(n)]]


def spar_path(i, n=5):
    """curved spar from the wrist to tip i (0..2), bowing up/out."""
    tip = W_TIPS[i]
    mid = lerp(W_WRIST, tip, 0.5)
    ctrl = _add(mid, (0.55, 0.3, 1.1))
    return bezier(W_WRIST, ctrl, tip, n)


def resample(poly, n):
    """resample polyline to n points evenly by arc length."""
    d = [0.0]
    for a, b in zip(poly, poly[1:]):
        d.append(d[-1] + math.sqrt(_dot(_sub(b, a), _sub(b, a))))
    out = []
    for k in range(n):
        s = d[-1] * k / (n - 1)
        for i in range(len(poly) - 1):
            if d[i + 1] >= s - 1e-9:
                t = (s - d[i]) / max(d[i + 1] - d[i], 1e-9)
                out.append(lerp(poly[i], poly[i + 1], t)); break
    return out


def scallop(i):
    """trailing-edge point between tip i and tip i+1 (pulled toward the wrist)."""
    m = lerp(W_TIPS[i], W_TIPS[i + 1], 0.5)
    return lerp(m, W_WRIST, 0.2)


def inner_edge(n):
    """trailing edge from the body root to the first tip (slightly scalloped)."""
    m = lerp(W_ROOT, W_TIPS[0], 0.5)
    m = lerp(m, W_WRIST, 0.12)
    return resample([W_ROOT, m, W_TIPS[0]], n)


# 2D wing frame (for texture painting): origin root, a toward outer tip, b toward wrist
_EA = _norm(_sub(W_TIPS[3], W_ROOT))
_wr = _sub(W_WRIST, W_ROOT)
_EB = _norm(_sub(_wr, _mul(_EA, _dot(_wr, _EA))))


def wing2d(p):
    v = _sub(p, W_ROOT)
    return (_dot(v, _EA), _dot(v, _EB))


def wing_trailing_2d():
    """trailing edge polyline in 2D from root to outer tip."""
    pts = inner_edge(4)
    for i in range(3):
        pts += [scallop(i), W_TIPS[i + 1]]
    return [wing2d(p) for p in pts]


def wing_outline_2d():
    lead = [wing2d(p) for p in W_LEAD]
    return [wing2d(W_ROOT)] + lead + wing_trailing_2d()[::-1][1:]


def wing_bounds():
    pts = wing_outline_2d()
    a0 = min(p[0] for p in pts) - 1.0; a1 = max(p[0] for p in pts) + 1.0
    b0 = min(p[1] for p in pts) - 1.0; b1 = max(p[1] for p in pts) + 1.0
    s = min(WING_REGION[2] / (a1 - a0), WING_REGION[3] / (b1 - b0))
    return a0, b1, s


def wing_uv(p):
    a, b = wing2d(p)
    a0, b1, s = wing_bounds()
    x = WING_REGION[0] + (a - a0) * s
    y = WING_REGION[1] + (b1 - b) * s
    return x / ATLAS, 1 - y / ATLAS


def wing_glyph_anchors():
    """2D anchor points for membrane runes: one per panel between spars."""
    out = []
    for i in range(3):
        c = lerp(W_WRIST, scallop(i), 0.62)
        out.append(wing2d(c))
    out.append(wing2d(lerp(W_WRIST, lerp(W_ROOT, W_TIPS[0], 0.5), 0.55)))
    return out


# ---------------- final voxel palette (4x4 swatch grid of 512px, one stud cube per cell) ----------------
VOX_CELL_U = 0.62          # voxel (cube) size in design units = one stud
VOX = [  # key, rgb, emissive, per-cube brightness variation
    ('charcoal', (56, 58, 72), 0.0, 0.12), ('dark', (38, 40, 52), 0.0, 0.10),
    ('gold', (236, 164, 44), 0.0, 0.08), ('cream', (228, 200, 150), 0.0, 0.07),
    ('horn', (240, 216, 166), 0.0, 0.06), ('belly', (214, 188, 140), 0.0, 0.07),
    ('teal', (22, 80, 94), 0.0, 0.08), ('teal_mid', (28, 118, 130), 0.1, 0.08),
    ('teal_light', (34, 160, 170), 0.3, 0.07), ('glow_edge', (66, 214, 214), 0.7, 0.05),
    ('glow', (80, 252, 246), 1.0, 0.04), ('slate', (74, 80, 98), 0.0, 0.10),
]
VOX_SWATCH = {k: (i % 4, i // 4) for i, (k, *_) in enumerate(VOX)}


# ---------------- stepped wing membrane grid (painted in atlas row 3) ----------------
WING_ROW_Y = 3 * SW          # atlas pixel row where the membrane painting starts
_N3 = (_EA[1] * _EB[2] - _EA[2] * _EB[1], _EA[2] * _EB[0] - _EA[0] * _EB[2], _EA[0] * _EB[1] - _EA[1] * _EB[0])


def wing_plane_pt(a, b):
    """3D point (left wing, design coords) on the wing plane."""
    return _add(_add(W_ROOT, _mul(_EA, a)), _mul(_EB, b))


def wing_plane_normal():
    return _N3


def wing_grid():
    """cell grid of the membrane in the wing plane: (a0, b0, NA, NB, cell)."""
    c = VOX_CELL_U
    pts = wing_outline_2d()
    a0 = min(p[0] for p in pts) - c; b0 = min(p[1] for p in pts) - c
    NA = int((max(p[0] for p in pts) - a0) / c) + 2
    NB = int((max(p[1] for p in pts) - b0) / c) + 2
    return a0, b0, NA, NB, c


def point_in_poly(poly, x, y):
    inside = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            inside = not inside
    return inside


def wing_cells():
    """set of (ia, ib) membrane cells inside the outline."""
    a0, b0, NA, NB, c = wing_grid()
    poly = wing_outline_2d()
    return {(i, j) for i in range(NA) for j in range(NB)
            if point_in_poly(poly, a0 + (i + 0.5) * c, b0 + (j + 0.5) * c)}


# ---------------- pixel-art rune plates (painted cell-exact in atlas row 3, right of the wing) ----------------
# G gold, D dark, C glow, T teal, S slate, K charcoal
RUNE_ART = {
    'disc': ["..GGGG..",
             ".GGDDGG.",
             "GGDCCDGG",
             "GDCDDCDG",
             "GDCDDCDG",
             "GGDCCDGG",
             ".GGDDGG.",
             "..GGGG.."],
    'chest': ["GGGGGGG",
              "GTTCTTG",
              "GTCTCTG",
              "GCTTTCG",
              "GTCTCTG",
              "GGTCTGG",
              ".GGTGG.",
              "..GGG.."],
    'tail': ["CCCC",
             "CTTC",
             "CCCC"],
    'knee': ["GGGG",
             "GCTG",
             "GTCG",
             "GGGG"],
}
RUNE_ORIGIN = {'disc': (1290, WING_ROW_Y + 16), 'chest': (1560, WING_ROW_Y + 16),
               'tail': (1800, WING_ROW_Y + 16), 'knee': (1800, WING_ROW_Y + 150)}
ART_COLORS = {'G': 'gold', 'D': 'dark', 'C': 'glow', 'T': 'teal', 'S': 'slate', 'K': 'charcoal'}
