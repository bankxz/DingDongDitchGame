"""Generate the tileable square-stud textures used to bake the octopus atlas.

The reference shows square (not round) raised studs: a grid of slightly
uneven block panels with smaller raised square studs on top, and on the
tentacle underside pale square suckers with a sunken square centre.
Outputs colour + height tiles into ../textures/tiles/.
"""
import os
import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "textures", "tiles")
os.makedirs(OUT, exist_ok=True)

PAL = {
    "deep": np.array([25, 24, 86]) / 255,      # #191856
    "main": np.array([51, 33, 155]) / 255,     # #33219B
    "mid": np.array([132, 81, 239]) / 255,     # #8451EF
    "lilac": np.array([212, 169, 251]) / 255,  # #D4A9FB
    "cream": np.array([254, 236, 235]) / 255,  # #FEECEB
}


def box_blur(a, r):
    if r <= 0:
        return a
    k = 2 * r + 1
    out = a.copy()
    for ax in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if i == ax else (0, 0) for i in range(2)], mode="wrap"), axis=ax)
        if ax == 0:
            out = (c[k:] - c[:-k]) / k
        else:
            out = (c[:, k:] - c[:, :-k]) / k
    return out


def shade(height, strength=6.0):
    """Stylised baked lighting from the height field (light from top-left)."""
    gx = np.roll(height, -1, 1) - np.roll(height, 1, 1)
    gy = np.roll(height, -1, 0) - np.roll(height, 1, 0)
    return np.clip((gx + gy) * strength, -1, 1)


def stud_tile(size=512, cells=4, seed=1, base=None, top=None):
    rng = np.random.default_rng(seed)
    base = PAL["main"] if base is None else base
    top = PAL["main"] * 1.3 if top is None else top
    h = np.zeros((size, size))
    col = np.zeros((size, size, 3))
    tint = np.zeros((size, size))
    c = size // cells
    gap = max(2, size // 170)
    for iy in range(cells):
        for ix in range(cells):
            y0, x0 = iy * c, ix * c
            h[y0 + gap:y0 + c - gap, x0 + gap:x0 + c - gap] = 0.35
            tint[y0:y0 + c, x0:x0 + c] = rng.uniform(-0.06, 0.06)
            if rng.random() < 0.72:  # raised square stud on this block
                s = int(c * rng.uniform(0.28, 0.48))
                ox = x0 + int(rng.uniform(0.12, 0.88 - s / c) * c)
                oy = y0 + int(rng.uniform(0.12, 0.88 - s / c) * c)
                h[oy:oy + s, ox:ox + s] = 1.0
    hb = box_blur(h, max(1, size // 256))
    lit = shade(hb, 9.0)
    groove = (hb < 0.18).astype(float)
    for i in range(3):
        col[..., i] = base[i] * (1 + tint) + (top[i] - base[i]) * np.clip(hb - 0.35, 0, 1) / 0.65
    col = col * (1 + 0.35 * lit[..., None]) * (1 - 0.35 * groove[..., None])
    return np.clip(col, 0, 1), hb


def sucker_tile(size=256):
    """One square sucker per tile, centred, on the lilac underside."""
    h = np.zeros((size, size))
    yy, xx = np.mgrid[0:size, 0:size] / size
    outer = (np.abs(xx - 0.5) < 0.36) & (np.abs(yy - 0.5) < 0.36)
    inner = (np.abs(xx - 0.5) < 0.14) & (np.abs(yy - 0.5) < 0.14)
    h[outer] = 1.0
    h[inner] = 0.35
    hb = box_blur(h, 3)
    lit = shade(hb, 4.0)
    col = np.zeros((size, size, 3))
    col[:] = PAL["lilac"] * 0.92
    col[outer] = PAL["cream"] * 0.97
    col[inner] = PAL["lilac"] * 0.82
    col = col * (1 + 0.30 * lit[..., None])
    return np.clip(col, 0, 1), hb


def eye_tex(size=256):
    """Eye decal: glowing white with a purple iris at the inner-lower corner."""
    yy, xx = np.mgrid[0:size, 0:size] / size
    v = 1 - yy  # v up
    col = np.zeros((size, size, 3))
    col[:] = np.array([0.99, 0.97, 1.0])
    # iris sits at the inner (u=1 -> towards nose) lower corner
    iris = (xx > 0.60) & (xx < 0.92) & (v > 0.10) & (v < 0.62)
    glow = (xx > 0.52) & (xx < 0.97) & (v > 0.04) & (v < 0.72)
    col[glow] = PAL["lilac"]
    col[iris] = PAL["mid"] * 0.85
    pupil = (xx > 0.70) & (xx < 0.86) & (v > 0.18) & (v < 0.48)
    col[pupil] = PAL["deep"] * 1.6
    # dark rim
    rim = (xx < 0.04) | (xx > 0.96) | (v < 0.05) | (v > 0.95)
    col[rim] = PAL["deep"]
    return np.clip(col, 0, 1)


def save(name, arr, gray=False):
    a = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(a, "L" if gray else "RGB").save(os.path.join(OUT, name))


c, h = stud_tile(512, 4, seed=7)
save("stud_body_color.png", c)
save("stud_body_height.png", h, True)
c, h = stud_tile(512, 4, seed=21, base=PAL["main"] * 1.05, top=PAL["main"] * 1.4)
save("stud_arm_color.png", c)
save("stud_arm_height.png", h, True)
c, h = sucker_tile(256)
save("sucker_color.png", c)
save("sucker_height.png", h, True)
save("eye_color.png", eye_tex(256))
print("tiles written to", os.path.abspath(OUT))
