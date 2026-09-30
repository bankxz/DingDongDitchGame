"""
Shared sculpted-fur definition.

The same lock field drives both the geometry sculpt (kitsune_sculpt.py
displaces the remeshed body along its normals) and the painted shading
(kitsune_paint.py), so painted ridges / crevices line up with the sculpted
fur locks.

Surface coordinates come from the source lofts: t (0..1 along the part) and
th (angle around it).  Each part maps them to metric coordinates:
    a = distance ALONG the fur flow (lock tips point toward +a)
    b = distance ACROSS the flow
"""
import numpy as np

# L: part length, R: mean radius, flip: a = (1 - t) * L (flow toward loft start)
# ca / cb: lock length / width, chev: (centre angle, shear) for V-shaped rows
FUR = {
    'torso': dict(L=1.40, R=0.30, flip=True, ca=0.20, cb=0.16, chev=(0.0, 0.55), seed=1.0),       # flows to the rear, V along the spine
    'neck': dict(L=0.60, R=0.22, flip=True, ca=0.16, cb=0.13, chev=(np.pi, 0.75), seed=2.0),     # flows down to the chest, V down the chest
    'head': dict(L=0.50, R=0.16, flip=True, ca=0.11, cb=0.09, chev=None, seed=3.0),              # flows back from the face
    'leg_f': dict(L=0.80, R=0.09, flip=False, ca=0.12, cb=0.085, chev=None, seed=5.0),           # flows down
    'leg_h': dict(L=0.90, R=0.10, flip=False, ca=0.13, cb=0.095, chev=None, seed=6.0),
    'ear': dict(L=0.30, R=0.06, flip=False, ca=0.08, cb=0.05, chev=None, seed=4.0),
}
LEG_BOUNDARY = {'leg_f': 0.53, 'leg_h': 0.50}      # purple -> cyan transition (loft t)


def _hash2(ix, iy, seed=0.0):
    return np.modf(np.abs(np.sin(ix * 127.1 + iy * 311.7 + seed * 74.7)) * 43758.5453)[0]


def wrap_pi(x):
    return (x + np.pi) % (2 * np.pi) - np.pi


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def fur_coords(part, t, th):
    f = FUR[part]
    a = ((1.0 - t) if f['flip'] else t) * f['L']
    b = th * f['R']
    if f['chev'] is not None:
        c0, k = f['chev']
        a = a - k * f['R'] * np.abs(wrap_pi(th - c0))
    return a, b


def lock_field(a, b, ca, cb, seed=0.0):
    """Layered, pointed fur locks (shingles).  Returns
    h     0..1 sculpt height (0 at the lock root, max near the pointed tip)
    ridge 0..1 across-lock profile (1 on the lock's centre line)
    v     0..1 position along the lock (root -> tip)
    """
    A = a / ca
    row = np.floor(A)
    v = A - row
    Bc = b / cb + 0.5 * np.mod(row, 2) + 0.3 * _hash2(row, 0.0, seed)
    col = np.floor(Bc)
    u = 2 * (Bc - col) - 1
    size = 0.75 + 0.45 * _hash2(row, col, seed + 1)
    w = np.maximum((1.0 - v) ** 0.6, 1e-3)
    ridge = np.clip(1.0 - (u / w) ** 2, 0, 1)
    h = np.sqrt(ridge) * (v ** 0.65) * size
    return np.clip(h, 0, 1.2), ridge, v


def amplitude(part, t, th):
    """Sculpt depth (shoulder-height units) per part / region."""
    c = np.cos(th)
    s = np.abs(np.sin(th))
    if part == 'torso':
        return (0.026 + 0.030 * smoothstep(0.45, 0.90, c) + 0.042 * smoothstep(-0.50, -0.85, c)
                + 0.016 * smoothstep(0.70, 0.90, t) * smoothstep(0.5, 0.8, s))
    if part == 'neck':
        return 0.050 + 0.024 * smoothstep(0.4, 0.9, c) + 0.020 * smoothstep(-0.5, -0.9, c)
    if part == 'head':
        back = 0.026 * smoothstep(0.55, 0.28, t)
        cheek = 0.034 * smoothstep(0.55, 0.80, s) * smoothstep(0.55, 0.35, t) * smoothstep(0.08, 0.2, t) * (c < 0.35)
        return back + cheek
    if part in LEG_BOUNDARY:
        tb = LEG_BOUNDARY[part]
        upper = 0.038 * (1.0 - smoothstep(tb - 0.14, tb + 0.01, t))
        return upper + 0.004
    return np.zeros_like(t)


def sculpt_height(part, t, th):
    """Displacement (units) for one part's samples."""
    if part not in FUR:
        return np.zeros_like(t)
    f = FUR[part]
    a, b = fur_coords(part, t, th)
    h, ridge, v = lock_field(a, b, f['ca'], f['cb'], f['seed'])
    return h * amplitude(part, t, th)
