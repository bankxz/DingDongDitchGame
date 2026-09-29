"""Generate the stud textures for the Ancient Dragon model.

Every colour gets a seamless 256x256 tile of 4x4 studs in the Roblox stud style of
the supplied examples: a smooth flat surface (no block seams) with small square
studs recessed into it (dark top/left inner walls, lit bottom/right walls).  The wing membrane and glow textures are
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
    "Mouth": (118, 30, 40),
}


def clamp(v):
    return max(0, min(255, int(v)))


def shade(c, f):
    return tuple(clamp(x * f) for x in c)


STUD_FRAC = 0.42  # stud square size relative to the stud pitch


def draw_stud_cell(d, x0, y0, size, base, rnd=None, stud_frac=STUD_FRAC):
    """Roblox stud style (per the stud examples): smooth flat surface, no block seams, with a small
    square stud recessed into it - dark top/left inner walls, light bottom/right inner walls."""
    d.rectangle([x0, y0, x0 + size - 1, y0 + size - 1], fill=base)
    s = int(size * stud_frac)
    sx = x0 + (size - s) // 2
    sy = y0 + (size - s) // 2
    e = max(2, s // 6)
    d.rectangle([sx, sy, sx + s, sy + s], fill=shade(base, 0.94))                       # pocket floor
    d.polygon([(sx, sy), (sx + s, sy), (sx + s - e, sy + e), (sx + e, sy + e)], fill=shade(base, 0.66))  # top wall
    d.polygon([(sx, sy), (sx + e, sy + e), (sx + e, sy + s - e), (sx, sy + s)], fill=shade(base, 0.74))  # left wall
    d.polygon([(sx, sy + s), (sx + e, sy + s - e), (sx + s - e, sy + s - e), (sx + s, sy + s)],
              fill=shade(base, 1.14))                                                   # bottom wall (lit)
    d.polygon([(sx + s, sy), (sx + s, sy + s), (sx + s - e, sy + s - e), (sx + s - e, sy + e)],
              fill=shade(base, 1.08))                                                   # right wall (lit)


def stud_tile(base, seed=0):
    im = Image.new("RGB", (TILE, TILE), base)
    d = ImageDraw.Draw(im)
    for cy in range(CELLS):
        for cx in range(CELLS):
            draw_stud_cell(d, cx * CELL, cy * CELL, CELL, base)
    return im.filter(ImageFilter.SMOOTH)


def stud_normal(strength=5.0):
    """tangent-space normal map of the recessed studs (Roblox SurfaceAppearance NormalMap)"""
    import numpy as np
    h = np.ones((TILE, TILE), np.float32)
    s = int(CELL * STUD_FRAC)
    e = max(2, s // 6)
    yy, xx = np.mgrid[0:CELL, 0:CELL]
    sx0 = (CELL - s) // 2
    inside = np.minimum(np.minimum(xx - sx0, sx0 + s - xx), np.minimum(yy - sx0, sx0 + s - yy)).astype(np.float32)
    cell = 1.0 - np.clip(inside / e, 0, 1) * np.where(inside >= 0, 1.0, 0.0)   # pocket depth ramps down the walls
    for cy in range(CELLS):
        for cx in range(CELLS):
            h[cy * CELL:(cy + 1) * CELL, cx * CELL:(cx + 1) * CELL] = cell
    gy, gx = np.gradient(h)
    nx, ny, nz = -gx * strength, gy * strength, np.ones_like(h)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    rgb = np.stack([(nx / ln + 1) * 127.5, (ny / ln + 1) * 127.5, (nz / ln + 1) * 127.5], -1).astype(np.uint8)
    return Image.fromarray(rgb)


NORMAL = stud_normal()
NORMAL.save(os.path.join(OUT, "Dragon_Stud_Normal.png"))  # one normal map shared by every stud material
for i, (name, col) in enumerate(PALETTE.items()):
    stud_tile(col, i).save(os.path.join(OUT, f"Dragon_{name}_Stud.png"))



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
        col = tuple(clamp(deep[k] + (bright[k] - deep[k]) * t) for k in range(3))
        draw_stud_cell(d, i * cs, j * cs, cs, col)


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
M = M.filter(ImageFilter.SMOOTH).resize((512, 512), Image.LANCZOS)
M.save(os.path.join(OUT, "Dragon_WingMembrane.png"))

# ---------------------------------------------------------------- eyeball: glowing cyan iris, dark slit pupil, highlight
E = Image.new("RGB", (256, 256), (0, 0, 0))
for y in range(256):
    for x in range(256):
        dx, dy = (x - 128) / 128.0, (y - 128) / 128.0
        r = (dx * dx + dy * dy) ** 0.5
        if r > 0.93:
            c = (6, 40, 52)                                   # dark limbal ring / back of the eye
        else:
            k = r / 0.93
            c = (clamp(150 - 130 * k), clamp(255 - 60 * k), clamp(255 - 25 * k))
        E.putpixel((x, y), c)
de = ImageDraw.Draw(E)
de.ellipse([128 - 9, 128 - 112, 128 + 9, 128 + 112], fill=(8, 16, 22))      # vertical slit pupil (thin: eyeball is stretched 1.75x wide)
de.ellipse([128 - 4, 128 - 98, 128 + 4, 128 + 98], fill=(0, 0, 0))
de.ellipse([74, 60, 104, 90], fill=(235, 255, 255))                          # specular highlight
E = E.filter(ImageFilter.SMOOTH)
E.save(os.path.join(OUT, "Dragon_Eye.png"))
print("textures written to", OUT)
