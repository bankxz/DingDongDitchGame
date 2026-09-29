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
