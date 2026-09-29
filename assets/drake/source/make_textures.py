"""Tileable square-stud textures for the sea drake (colour + height).

The reference uses square raised studs on block panels. Body panels mix navy /
royal blue, belly is cream, fins run cyan/teal at the base to mint at the tip.
Outputs into ../textures/tiles/.
"""
import os

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "textures", "tiles")
os.makedirs(OUT, exist_ok=True)


def c(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)]) / 255


NAVY, ROYAL, CYAN, TEAL, MINT, CREAM = map(c, ["#09236F", "#0542DF", "#14C7FA", "#0FBCAF", "#9CF3E4", "#FEF7EE"])


def box_blur(a, r):
    k = 2 * r + 1
    out = a.copy()
    for ax in (0, 1):
        pad = [(r + 1, r) if i == ax else (0, 0) for i in range(2)]
        cs = np.cumsum(np.pad(out, pad, mode="wrap"), axis=ax)
        out = (cs[k:] - cs[:-k]) / k if ax == 0 else (cs[:, k:] - cs[:, :-k]) / k
    return out


def shade(h, s):
    gx = np.roll(h, -1, 1) - np.roll(h, 1, 1)
    gy = np.roll(h, -1, 0) - np.roll(h, 1, 0)
    return np.clip((gx + gy) * s, -1, 1)


def panel_tile(size, cells, colour_fn, seed, stud_p=0.7, stud_lift=0.18):
    """Grid of block panels (colour per cell from colour_fn) with raised square studs."""
    rng = np.random.default_rng(seed)
    h = np.zeros((size, size))
    col = np.zeros((size, size, 3))
    cs = size // cells
    gap = max(2, size // 170)
    for iy in range(cells):
        for ix in range(cells):
            y0, x0 = iy * cs, ix * cs
            base = colour_fn(rng, iy / cells, ix / cells)
            col[y0:y0 + cs, x0:x0 + cs] = base
            h[y0 + gap:y0 + cs - gap, x0 + gap:x0 + cs - gap] = 0.35
            if rng.random() < stud_p:
                s = int(cs * rng.uniform(0.26, 0.42))
                ox = x0 + int(rng.uniform(0.15, 0.85 - s / cs) * cs)
                oy = y0 + int(rng.uniform(0.15, 0.85 - s / cs) * cs)
                h[oy:oy + s, ox:ox + s] = 1.0
                col[oy:oy + s, ox:ox + s] = np.clip(base * (1 + stud_lift), 0, 1)
    hb = box_blur(h, max(1, size // 256))
    lit = shade(hb, 9.0)
    groove = (hb < 0.18).astype(float)
    col = col * (1 + 0.35 * lit[..., None]) * (1 - 0.35 * groove[..., None])
    return np.clip(col, 0, 1), hb


def body_col(rng, v, u):
    r = rng.random()
    if r < 0.25:
        return NAVY * rng.uniform(1.1, 1.4)
    if r < 0.9:
        return ROYAL * rng.uniform(0.85, 1.05)
    return (ROYAL * 0.6 + NAVY * 0.4)


def belly_col(rng, v, u):
    return CREAM * rng.uniform(0.9, 1.0)


def teal_col(rng, v, u):
    return (TEAL if rng.random() < 0.6 else CYAN * 0.9) * rng.uniform(0.9, 1.05)


def fin_col(rng, v, u):
    # rows are v (0 = top of image = UV v 1 -> tip). tip mint, body cyan
    tip = 1 - v
    r = rng.random()
    if tip < 0.55:
        return CYAN * rng.uniform(0.92, 1.05) if r < 0.8 else TEAL * 1.15
    if tip < 0.75:
        return (CYAN * 0.35 + MINT * 0.65) if r < 0.6 else CYAN
    return MINT * rng.uniform(0.95, 1.02) if r < 0.85 else CYAN * 0.3 + MINT * 0.7


def eye_tex(size=256):
    yy, xx = np.mgrid[0:size, 0:size] / size
    v = 1 - yy
    col = np.zeros((size, size, 3))
    col[:] = (0.99, 0.98, 1.0)
    glow = (xx > 0.66) & (xx < 0.86) & (v > 0.10) & (v < 0.78)
    col[glow] = (0.72, 0.62, 1.0)
    pupil = (xx > 0.71) & (xx < 0.81) & (v > 0.14) & (v < 0.72)
    col[pupil] = (0.16, 0.05, 0.45)
    rim = (xx < 0.05) | (xx > 0.95) | (v < 0.06) | (v > 0.94)
    col[rim] = NAVY * 0.8
    return col


def save(name, arr, gray=False):
    a = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(a, "L" if gray else "RGB").save(os.path.join(OUT, name))


for name, fn, cells, seed, lift in (("body", body_col, 4, 3, 0.25), ("belly", belly_col, 4, 5, -0.06),
                                    ("teal", teal_col, 4, 9, 0.12), ("fin", fin_col, 6, 11, 0.10)):
    col, h = panel_tile(512, cells, fn, seed, stud_lift=lift)
    save(f"{name}_color.png", col)
    save(f"{name}_height.png", h, True)
save("eye_color.png", eye_tex())
print("tiles ->", os.path.abspath(OUT))
