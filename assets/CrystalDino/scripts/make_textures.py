"""Generate the CrystalDino texture atlas (1024x1024).

Layout (pixels, origin top-left):
  navy blocks  x 0..640,    y 0..1024  (10 x 16 cells, 64 px per block)
  tan blocks   x 640..1024, y 0..576   (6 x 9 cells)
  crystal      x 640..1024, y 576..832 (6 facet columns, gradient base->tip)
  glow         x 640..768,  y 832..1024
  bone/teeth   x 768..896,  y 832..1024
  mouth glow   x 896..1024, y 832..1024

Every block cell carries a Roblox-style raised stud. The stud contact shadow
is taken from the MIT-licensed "Roblox-HD-Studs" set by dudeax
(https://github.com/dudeax/Roblox-HD-Studs); stud relief is rebuilt as a
height field so it can be scaled to the reference's small stud size.

Outputs: CrystalDino_Color.png, CrystalDino_Normal.png, CrystalDino_Emission.png,
CrystalDino_Roughness.png
"""
import os
import sys
import numpy as np
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "textures")
STUD_AO = sys.argv[2] if len(sys.argv) > 2 else None
S = 1024
CELL = 64
rng = np.random.default_rng(7)

col = np.zeros((S, S, 3))
height = np.zeros((S, S))
emis = np.zeros((S, S, 3))
rough = np.full((S, S), 0.75)

NAVY = np.array([60, 57, 100]) / 255.0
NAVY_ALT = [np.array(c) / 255.0 for c in ([54, 52, 92], [66, 60, 104], [48, 47, 84], [72, 64, 100])]
TAN = np.array([214, 178, 138]) / 255.0
TAN_ALT = [np.array(c) / 255.0 for c in ([204, 166, 128], [222, 188, 148], [196, 158, 122])]
GLOW = np.array([30, 110, 255]) / 255.0

# stud contact-shadow patch from the downloaded HD stud AO map (one stud quadrant)
ao_patch = None
if STUD_AO and os.path.exists(STUD_AO):
    a = np.array(Image.open(STUD_AO).convert("L")).astype(float)[:512, :512] / 255.0
    ao_patch = a


def stud_field(size, stud):
    """Height + AO for one cell with a raised rounded-square stud of side `stud` px."""
    yy, xx = np.mgrid[0:size, 0:size] + 0.5
    return yy, xx


def draw_cell(x0, y0, base, glow_edges=False, n_studs=1):
    c = CELL
    yy, xx = np.mgrid[0:c, 0:c] + 0.5
    # bevelled block: height falls off near the edges
    d = np.minimum(np.minimum(xx, c - xx), np.minimum(yy, c - yy))
    h = np.clip(d / 3.0, 0, 1) ** 0.6 * 0.6
    tint = base * (1 + rng.uniform(-0.06, 0.05))
    cc = np.ones((c, c, 3)) * tint
    # subtle large-scale mottling
    cc *= (1 + 0.04 * np.sin(xx / 9 + rng.uniform(0, 6)) * np.cos(yy / 11 + rng.uniform(0, 6)))[..., None]
    ao = np.ones((c, c))
    for _ in range(n_studs):
        st = rng.uniform(13, 17)
        if n_studs == 1 and rng.random() < 0.65:
            cx, cy = c / 2 + rng.uniform(-4, 4), c / 2 + rng.uniform(-4, 4)
        else:
            q = [(0.3, 0.3), (0.7, 0.7), (0.3, 0.7), (0.7, 0.3)][(_ * 2 + int(rng.integers(0, 2))) % 4]
            cx, cy = c * q[0] + rng.uniform(-3, 3), c * q[1] + rng.uniform(-3, 3)
        sx = np.abs(xx - cx) - st / 2
        sy = np.abs(yy - cy) - st / 2
        sd = np.maximum(sx, sy)  # signed distance to square
        stud_h = np.clip(-sd / 2.2, 0, 1)
        h = np.maximum(h, 0.6 + stud_h * 0.35)
        if ao_patch is not None:
            # map HD AO quadrant so its stud (~112..399 of 512) covers our stud
            scale = 287.0 / st
            u = np.clip(((xx - cx) * scale + 256).astype(int), 0, 511)
            v = np.clip(((yy - cy) * scale + 256).astype(int), 0, 511)
            ao *= 0.55 + 0.45 * ao_patch[v, u]
        else:
            ao *= 1 - 0.25 * np.clip(1 - np.maximum(sd, 0) / 4, 0, 1) * (sd > 0)
    # dark seam line on the outermost pixels
    seam = (d < 1.2)
    cc[seam] *= 0.82
    cc *= (0.94 + 0.06 * np.clip(d / 6.0, 0, 1))[..., None]
    cc *= ao[..., None]
    col[y0:y0 + c, x0:x0 + c] = cc
    height[y0:y0 + c, x0:x0 + c] = h
    if glow_edges:
        side = rng.integers(0, 4)
        m = [(xx < 5.5), (xx > c - 5.5), (yy < 5.5), (yy > c - 5.5)][side]
        g = GLOW * 1.0
        col[y0:y0 + c, x0:x0 + c][m] = g
        emis[y0:y0 + c, x0:x0 + c][m] = g
        height[y0:y0 + c, x0:x0 + c][m] = 0.0


# navy region
for j in range(16):
    for i in range(10):
        base = NAVY if rng.random() < 0.55 else NAVY_ALT[rng.integers(0, len(NAVY_ALT))]
        n = 1 if rng.random() < 0.8 else 2
        draw_cell(i * CELL, j * CELL, base, glow_edges=rng.random() < 0.025, n_studs=n)
# tan region
for j in range(9):
    for i in range(6):
        base = TAN if rng.random() < 0.5 else TAN_ALT[rng.integers(0, len(TAN_ALT))]
        n = 1 if rng.random() < 0.8 else 2
        draw_cell(640 + i * CELL, j * CELL, base, n_studs=n)

# crystal region: 6 facet columns, vertical gradient (bottom = base, top = tip)
y0, y1 = 576, 832
t = np.linspace(1, 0, y1 - y0)[:, None]  # 1 at top (tip) -> 0 at bottom (base)
base_c = np.array([20, 120, 255]) / 255.0
mid_c = np.array([40, 200, 255]) / 255.0
tip_c = np.array([160, 240, 255]) / 255.0
facet_mul = [1.0, 0.82, 1.12, 0.9, 1.05, 0.78]
for k in range(6):
    x0 = 640 + k * 64
    tt = np.repeat(t, 64, axis=1)
    g = np.where(tt[..., None] < 0.5, base_c + (mid_c - base_c) * (tt[..., None] / 0.5),
                 mid_c + (tip_c - mid_c) * ((tt[..., None] - 0.5) / 0.5))
    xx = np.arange(64)[None, :]
    streak = 1 + 0.08 * np.sin(xx / 5.0 + k) + 0.06 * np.sin(np.arange(y1 - y0)[:, None] / 13.0 + k * 2)
    edge = np.clip(np.minimum(xx, 63 - xx) / 4.0, 0, 1) * 0.15 + 0.85
    g = np.clip(g * facet_mul[k] * streak[..., None] * edge[..., None] + (1 - edge[..., None]) * 0.5, 0, 1)
    col[y0:y1, x0:x0 + 64] = g
    emis[y0:y1, x0:x0 + 64] = g * 0.6
    rough[y0:y1, x0:x0 + 64] = 0.15
    height[y0:y1, x0:x0 + 64] = 0.5

# glow (eyes)
yy, xx = np.mgrid[0:192, 0:128]
r = np.sqrt(((xx - 64) / 64.0) ** 2 + ((yy - 96) / 96.0) ** 2)
g = np.clip(np.array([90, 210, 255]) / 255.0 + (np.array([20, 90, 255]) / 255.0 - np.array([90, 210, 255]) / 255.0) * np.clip(r, 0, 1)[..., None], 0, 1)
col[832:1024, 640:768] = g
emis[832:1024, 640:768] = g
rough[832:1024, 640:768] = 0.3
height[832:1024, 640:768] = 0.5
# bone / teeth / claws (tip = top lighter)
tt = np.linspace(1, 0, 192)[:, None, None]
bone = (np.array([200, 165, 128]) / 255.0) * (1 - tt) + (np.array([238, 214, 180]) / 255.0) * tt
col[832:1024, 768:896] = np.repeat(bone, 128, axis=1)
height[832:1024, 768:896] = 0.5
rough[832:1024, 768:896] = 0.6
# mouth interior glow (deep blue -> cyan)
tt = np.linspace(0, 1, 128)[None, :, None]
mg = (np.array([10, 60, 220]) / 255.0) * (1 - tt) + (np.array([50, 190, 255]) / 255.0) * tt
col[832:1024, 896:1024] = np.repeat(mg, 192, axis=0)
emis[832:1024, 896:1024] = np.repeat(mg, 192, axis=0)
height[832:1024, 896:1024] = 0.5

# normal map from height (OpenGL / +Y up, as Roblox expects)
k = 6.0
gy, gx = np.gradient(height)
nx, ny, nz = -gx * k, gy * k, np.ones_like(height)
ln = np.sqrt(nx * nx + ny * ny + nz * nz)
nrm = np.stack([nx / ln, ny / ln, nz / ln], -1) * 0.5 + 0.5

# bake a gentle top-left light into the color so studs read even without a normal map
light = np.clip(1 + (nrm[..., 0] - 0.5) * -0.9 + (nrm[..., 1] - 0.5) * 0.9, 0.6, 1.4)
mask_blocks = np.zeros((S, S), bool)
mask_blocks[:, :640] = True
mask_blocks[:576, 640:] = True
col[mask_blocks] *= light[mask_blocks][:, None]

os.makedirs(OUT, exist_ok=True)
save = lambda a, n: Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, n))
save(col, "CrystalDino_Color.png")
save(nrm, "CrystalDino_Normal.png")
save(emis, "CrystalDino_Emission.png")
save(rough, "CrystalDino_Roughness.png")
print("textures written to", OUT)
