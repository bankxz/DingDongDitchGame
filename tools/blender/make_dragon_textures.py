"""Generate the stud textures for the Ancient Dragon model.

Every colour gets a seamless 256x256 tile of 4x4 "voxel block" cells, each with a
raised square stud in the middle (the look of the reference model and of the
stud examples: square stud, light top/left bevel, dark bottom/right bevel,
thin darker seams between blocks).  The wing membrane and glow textures are
painted non-tiling sheets.

Run: python3 tools/blender/make_dragon_textures.py <out_dir>
"""
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/models/AncientDragon/textures"
os.makedirs(OUT, exist_ok=True)

TILE = 256
CELLS = 4
CELL = TILE // CELLS

PALETTE = {
    "Dark": (54, 52, 62),
    "Gold": (246, 172, 50),
    "Tan": (216, 178, 136),
    "Bone": (242, 218, 162),
}


def clamp(v):
    return max(0, min(255, int(v)))


def shade(c, f):
    return tuple(clamp(x * f) for x in c)


def draw_stud_cell(d, x0, y0, size, base, rnd, stud_frac=0.40):
    """One voxel cell: slightly varied block face, seam lines, raised square stud."""
    var = 1.0 + rnd.uniform(-0.035, 0.035)
    face = shade(base, var)
    d.rectangle([x0, y0, x0 + size - 1, y0 + size - 1], fill=face)
    # block bevel: light top/left, dark bottom/right, dark seam on the outside
    b = max(2, size // 22)
    d.rectangle([x0, y0, x0 + size - 1, y0 + b - 1], fill=shade(face, 1.14))
    d.rectangle([x0, y0, x0 + b - 1, y0 + size - 1], fill=shade(face, 1.10))
    d.rectangle([x0, y0 + size - b, x0 + size - 1, y0 + size - 1], fill=shade(face, 0.74))
    d.rectangle([x0 + size - b, y0, x0 + size - 1, y0 + size - 1], fill=shade(face, 0.78))
    d.rectangle([x0, y0, x0 + size - 1, y0], fill=shade(face, 0.55))
    d.rectangle([x0, y0, x0, y0 + size - 1], fill=shade(face, 0.55))
    # raised square stud
    s = int(size * stud_frac)
    sx = x0 + (size - s) // 2
    sy = y0 + (size - s) // 2
    e = max(2, s // 6)
    d.rectangle([sx + e // 2, sy + e // 2, sx + s + e // 2, sy + s + e // 2], fill=shade(face, 0.70))  # drop shadow
    d.rectangle([sx, sy, sx + s, sy + s], fill=shade(face, 1.04))
    d.polygon([(sx, sy), (sx + s, sy), (sx + s - e, sy + e), (sx + e, sy + e)], fill=shade(face, 1.22))
    d.polygon([(sx, sy), (sx + e, sy + e), (sx + e, sy + s - e), (sx, sy + s)], fill=shade(face, 1.14))
    d.polygon([(sx, sy + s), (sx + e, sy + s - e), (sx + s - e, sy + s - e), (sx + s, sy + s)], fill=shade(face, 0.80))
    d.polygon([(sx + s, sy), (sx + s, sy + s), (sx + s - e, sy + s - e), (sx + s - e, sy + e)], fill=shade(face, 0.86))


def stud_tile(base, seed):
    rnd = random.Random(seed)
    im = Image.new("RGB", (TILE, TILE), base)
    d = ImageDraw.Draw(im)
    for cy in range(CELLS):
        for cx in range(CELLS):
            draw_stud_cell(d, cx * CELL, cy * CELL, CELL, base, rnd)
    return im.filter(ImageFilter.SMOOTH)


def stud_normal(strength=6.0):
    """tangent-space normal map of the same block/stud layout (Roblox SurfaceAppearance NormalMap)"""
    import numpy as np
    h = np.zeros((TILE, TILE), np.float32)
    s = int(CELL * 0.40)
    for cy in range(CELLS):
        for cx in range(CELLS):
            x0, y0 = cx * CELL, cy * CELL
            yy, xx = np.mgrid[0:CELL, 0:CELL]
            # block face: bevelled edges (height falls off toward the seam)
            edge = np.minimum(np.minimum(xx, CELL - 1 - xx), np.minimum(yy, CELL - 1 - yy)).astype(np.float32)
            block = np.clip(edge / 4.0, 0, 1) * 0.5
            # raised square stud with bevel
            sx0 = (CELL - s) // 2
            sd = np.minimum(np.minimum(xx - sx0, sx0 + s - xx), np.minimum(yy - sx0, sx0 + s - yy)).astype(np.float32)
            stud = np.clip((sd + 1) / 3.0, 0, 1) * 0.5
            h[y0:y0 + CELL, x0:x0 + CELL] = block + stud
    gy, gx = np.gradient(h)
    nx, ny, nz = -gx * strength, gy * strength, np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([(nx / ln + 1) * 127.5, (ny / ln + 1) * 127.5, (nz / ln + 1) * 127.5], -1).astype(np.uint8)
    return Image.fromarray(rgb)


NORMAL = stud_normal()
for i, (name, col) in enumerate(PALETTE.items()):
    stud_tile(col, i).save(os.path.join(OUT, f"Dragon_{name}_Stud.png"))
    NORMAL.save(os.path.join(OUT, f"Dragon_{name}_Stud_Normal.png"))

# stud-only greyscale tile (neutral) for reuse on any colour in Studio
stud_tile((180, 180, 180), 99).save(os.path.join(OUT, "Stud_Tile_Neutral.png"))

# ---------------------------------------------------------------- glow atlas
# 3 regions across a 768x256 sheet:
#   [0,1/3)  rune square (bright frame, dark-teal ring, glowing square-in-square)
#   [1/3,2/3) solid glow (eyes, small glow chips)
#   [2/3,1]  throat gradient (dark mouth -> glowing cyan throat)
G = Image.new("RGB", (768, 256), (0, 0, 0))
d = ImageDraw.Draw(G)
cy_bright = (120, 255, 255)
cy_mid = (40, 225, 240)
cy_deep = (8, 120, 140)
d.rectangle([0, 0, 255, 255], fill=cy_mid)
d.rectangle([22, 22, 233, 233], fill=cy_deep)
d.rectangle([48, 48, 207, 207], fill=cy_bright)
d.rectangle([66, 66, 189, 189], fill=cy_deep)
d.rectangle([96, 96, 159, 159], fill=(210, 255, 255))
d.rectangle([110, 110, 145, 145], fill=cy_mid)
for y in range(256):
    for x in range(256, 512):
        dx, dy = (x - 384) / 128.0, (y - 128) / 128.0
        r = min(1.0, (dx * dx + dy * dy) ** 0.5)
        G.putpixel((x, y), (clamp(110 - 90 * r), clamp(245 - 45 * r), clamp(255 - 20 * r)))
for y in range(256):
    t = y / 255.0  # top (v=1) glowing throat, bottom dark
    c = (clamp(40 * (1 - t) + 34 * t), clamp(215 * (1 - t) + 52 * t), clamp(225 * (1 - t) + 52 * t))
    d.line([(512, y), (767, y)], fill=c)
G = G.filter(ImageFilter.GaussianBlur(1.2))
G.save(os.path.join(OUT, "Dragon_Glow.png"))

# ---------------------------------------------------------------- wing membrane
# UV space: u = along the span (0 = body, 1 = wing tip)
#           v = 1 at the arm / leading edge, 0 at the trailing edge
W = 1024
M = Image.new("RGB", (W, W), (0, 0, 0))
d = ImageDraw.Draw(M)
rnd = random.Random(7)
NC = 32
cs = W // NC
deep = (3, 34, 48)
bright = (14, 168, 190)
for j in range(NC):
    for i in range(NC):
        v = 1.0 - (j + 0.5) / NC           # image row 0 is v=1 (top)
        t = max(0.0, min(1.0, (1.0 - v) ** 0.85))  # brighter toward trailing edge
        t = max(0.0, min(1.0, t + rnd.uniform(-0.12, 0.12)))
        col = tuple(clamp(deep[k] + (bright[k] - deep[k]) * t) for k in range(3))
        draw_stud_cell(d, i * cs, j * cs, cs, col, rnd, stud_frac=0.36)


def rune(cx, cy, s):
    """pixel rune: glowing square outline + dot, like the wing detail"""
    g = (170, 255, 255)
    q = cs
    for k in range(s):
        for (a, b) in ((k, 0), (k, s - 1), (0, k), (s - 1, k)):
            x, y = (cx + a) * q, (cy + b) * q
            d.rectangle([x + 2, y + 2, x + q - 3, y + q - 3], fill=g)
    x, y = (cx + s // 2) * q, (cy + s + 1) * q
    d.rectangle([x + 2, y + 2, x + q - 3, y + q - 3], fill=g)


rune(13, 13, 3)
rune(21, 16, 3)
rune(6, 19, 2)
rune(27, 22, 2)
M = M.filter(ImageFilter.SMOOTH)
M.save(os.path.join(OUT, "Dragon_WingMembrane.png"))
print("textures written to", OUT)
