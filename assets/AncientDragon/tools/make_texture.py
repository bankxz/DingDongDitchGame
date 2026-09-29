"""Generate the stud-texture atlas (color, normal, emission mask) for the Ancient Dragon."""
import os, sys
import numpy as np
from PIL import Image, ImageFilter
sys.path.insert(0, os.path.dirname(__file__))
from spec import *

OUT = os.path.join(os.path.dirname(__file__), '..', 'textures')
rng = np.random.default_rng(7)
col = np.zeros((ATLAS, ATLAS, 3), np.float32)
hgt = np.zeros((ATLAS, ATLAS), np.float32)
emi = np.zeros((ATLAS, ATLAS), np.float32)

def stud_cell(x, y, c, var=0.07, emissive=0.0, cp=CELL_PX):
    """Paint one cube cell with a raised square stud (engraved/embossed look)."""
    x, y = int(round(x)), int(round(y))
    if x < 0 or y < 0 or x + cp > ATLAS or y + cp > ATLAS:
        return
    k = 1.0 + rng.uniform(-var, var)
    base = np.array(c, np.float32) * k
    blk = np.ones((cp, cp), np.float32)
    h = np.full((cp, cp), 0.45, np.float32)
    # cube face bevel: light top/left, dark bottom/right, dark seam
    blk[:2, :] *= 1.10; blk[:, :2] *= 1.10
    blk[-3:, :] *= 0.82; blk[:, -3:] *= 0.82
    blk[-1:, :] *= 0.7; blk[:, -1:] *= 0.7
    h[0, :] = h[:, 0] = h[-1, :] = h[:, -1] = 0.0
    h[1, :] = h[:, 1] = h[-2, :] = h[:, -2] = 0.25
    # square stud
    s0, s1 = int(cp * 0.3), int(cp * 0.7)
    blk[s0:s1, s0:s1] *= 1.05
    blk[s0:s0 + 2, s0:s1] *= 1.16; blk[s0:s1, s0:s0 + 2] *= 1.16
    blk[s1 - 2:s1, s0:s1] *= 0.76; blk[s0:s1, s1 - 2:s1] *= 0.76
    h[s0:s1, s0:s1] = 1.0
    h[s0:s1, s0] = h[s0:s1, s1 - 1] = h[s0, s0:s1] = h[s1 - 1, s0:s1] = 0.75
    col[y:y + cp, x:x + cp] = np.clip(base[None, None, :] * blk[..., None], 0, 255)
    hgt[y:y + cp, x:x + cp] = h
    emi[y:y + cp, x:x + cp] = emissive

def swatch_origin(key):
    cx, cy = SWATCH[key]
    return cx * SW, cy * SW

def fill_swatch(key, c, var=0.07, emissive=0.0):
    ox, oy = swatch_origin(key)
    # cells start at MARGIN; extend one cell into the margins for bleed
    for j in range(-1, CELLS + 1):
        for i in range(-1, CELLS + 1):
            x = ox + MARGIN + i * CELL_PX; y = oy + MARGIN + j * CELL_PX
            if x < ox or y < oy:
                x = max(x, ox); y = max(y, oy)
            stud_cell(min(x, ox + SW - CELL_PX), min(y, oy + SW - CELL_PX), c, var, emissive)

for k in ('charcoal', 'gold', 'cream', 'horn', 'teal', 'dark', 'belly'):
    fill_swatch(k, PALETTE[k])
fill_swatch('glow', PALETTE['glow'], 0.04, 1.0)

def glyph_rows(s):
    return [r for r in s.strip('\n').split('\n')]

G = PALETTE['gold']; T = PALETTE['teal']; C = PALETTE['glow']; D = PALETTE['charcoal']; K = PALETTE['dark']

def paint_grid(key, fn):
    """fn(i,j) -> (color, emissive) for each of the CELLS x CELLS cells of a decal swatch."""
    ox, oy = swatch_origin(key)
    for j in range(-1, CELLS + 1):
        for i in range(-1, CELLS + 1):
            ii, jj = min(max(i, 0), CELLS - 1), min(max(j, 0), CELLS - 1)
            c, e = fn(ii, jj)
            x = ox + MARGIN + i * CELL_PX; y = oy + MARGIN + j * CELL_PX
            stud_cell(min(max(x, ox), ox + SW - CELL_PX), min(max(y, oy), oy + SW - CELL_PX), c, 0.05, e)

def glyph_fn(glyph, gx, gy, inner, border=None, border_w=2, shape=None):
    rows = glyph_rows(glyph)
    def fn(i, j):
        if shape is not None and not shape(i, j):
            return border, 0.0
        if border is not None and (i < border_w or j < border_w or i >= CELLS - border_w or j >= CELLS - border_w):
            return border, 0.0
        r, c_ = j - gy, i - gx
        if 0 <= r < len(rows) and 0 <= c_ < len(rows[r]) and rows[r][c_] == 'C':
            return C, 1.0
        return inner, 0.0
    return fn

CHEST = """
.....CC.....
....C..C....
.....CC.....
............
.....CC.....
....C..C....
...C.CC.C...
..C.C..C.C..
...C.CC.C...
....C..C....
.....CC.....
"""
paint_grid('rune_chest', glyph_fn(CHEST, 2, 3, T, G, 2))

DISC = """
..CCCC..
.C....C.
.C.CC.C.
.C.CC.C.
.C.CC.C.
.C....C.
..CCCC..
...CC...
"""
def disc_fn(i, j):
    d = ((i + 0.5 - CELLS / 2) ** 2 + (j + 0.5 - CELLS / 2) ** 2) ** 0.5
    if d > 5.6:
        return G, 0.0
    rows = glyph_rows(DISC); r, c_ = j - 3, i - 4
    if 0 <= r < len(rows) and 0 <= c_ < len(rows[r]) and rows[r][c_] == 'C':
        return C, 1.0
    return (K if d < 5.0 else D), 0.0
paint_grid('rune_disc', disc_fn)

TAIL = """
CCCCCCCC
C......C
C.C..C.C
C.C..C.C
C.C..C.C
C.C..C.C
C......C
CCCCCCCC
"""
def tail_fn(i, j):
    rows = glyph_rows(TAIL); r, c_ = j - 4, i - 4
    if 0 <= r < 8 and 0 <= c_ < 8:
        return (C, 1.0) if rows[r][c_] == 'C' else (T, 0.0)
    if 3 <= j <= 12 and 3 <= i <= 12:
        return T, 0.0
    return D, 0.0
paint_grid('rune_tail', tail_fn)

KNEE = """
CCCC
C..C
C..C
CCCC
"""
paint_grid('rune_knee', glyph_fn(KNEE, 6, 6, T, G, 4))

# ---------------- wing membrane region -----------------
wx, wy, ww, wh = WING_REGION
S = ww / (WING_A1 - WING_A0)          # px per design unit (uniform)
def w2px(a, b):
    return wx + (a - WING_A0) * S, wy + (WING_B1 - b) * S
outline = membrane_outline()
# trailing edge polyline from outer tip back to body (bottom part of outline)
trail = [p for p in outline[len(LEADING) + 1:]] + []
trail = sorted([TIPS[3]] + trail, key=lambda p: p[0])
def trail_b(a):
    for (a0, b0), (a1, b1) in zip(trail, trail[1:]):
        if a0 <= a <= a1:
            return b0 + (b1 - b0) * (a - a0) / max(a1 - a0, 1e-6)
    return trail[0][1] if a < trail[0][0] else trail[-1][1]

WGLYPHS = [  # (a, b, glyph)  cell-art placed centred at wing coords
    (14.4, 1.2, """
..CC..
..CC..
CCCCCC
C....C
C.CC.C
C....C
CCCCCC
"""),
    (10.0, 1.8, """
..C..
..C..
CCCCC
..C..
.C.C.
..C..
"""),
    (5.6, 2.8, """
.C.
CCC
.C.
.C.
C.C
"""),
    (16.8, -0.6, """
C.
.C
C.
"""),
    (12.2, 0.2, """
.C
C.
"""),
]
WCELL = 0.45
cellpx = WCELL * S
nx = int((WING_A1 - WING_A0) / WCELL) + 1
ny = int((WING_B1 - WING_B0) / WCELL) + 1
glow_cells = set()
for a, b, g in WGLYPHS:
    rows = glyph_rows(g)
    ci0 = int((a - WING_A0) / WCELL) - len(rows[0]) // 2
    cj0 = int((WING_B1 - b) / WCELL) - len(rows) // 2
    for r, row in enumerate(rows):
        for c_, ch in enumerate(row):
            if ch == 'C':
                glow_cells.add((ci0 + c_, cj0 + r))
for j in range(ny):
    for i in range(nx):
        a = WING_A0 + (i + 0.5) * WCELL
        b = WING_B1 - (j + 0.5) * WCELL
        d = b - trail_b(a)                 # distance above trailing edge
        t = float(np.clip(1.0 - d / 2.6, 0, 1)) ** 1.8
        base = np.array(T) * (1 - t) + np.array((34, 150, 160)) * t
        e = 0.12 * t
        if d < 0.55:
            base = np.array((60, 200, 205)); e = 0.5
        if b > 4.6 and a < 8:               # darker upper band near the wrist
            base = np.array(K) * 1.1
        if (i, j) in glow_cells:
            base, e = np.array(C), 1.0
        x, y = wx + i * cellpx, wy + j * cellpx
        stud_cell(x, y, base, 0.08, e, cp=int(round(cellpx)))

# glow halo around emissive cyan cells
em_img = Image.fromarray((emi * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10))
halo = np.asarray(em_img, np.float32)[..., None] / 255.0
col = np.clip(col + halo * np.array((10, 90, 90), np.float32), 0, 255)

os.makedirs(OUT, exist_ok=True)
Image.fromarray(col.astype(np.uint8)).save(os.path.join(OUT, 'AncientDragon_Color_2048.png'))
Image.fromarray(col.astype(np.uint8)).resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, 'AncientDragon_Color.png'))
# normal map (OpenGL / +Y) from height
hs = np.asarray(Image.fromarray((hgt * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255.0
dx = np.zeros_like(hs); dy = np.zeros_like(hs)
dx[:, 1:-1] = (hs[:, 2:] - hs[:, :-2]) * 0.5
dy[1:-1, :] = (hs[2:, :] - hs[:-2, :]) * 0.5
k = 3.0
n = np.dstack((-dx * k, dy * k, np.ones_like(hs)))
n /= np.linalg.norm(n, axis=2, keepdims=True)
nimg = ((n * 0.5 + 0.5) * 255).astype(np.uint8)
Image.fromarray(nimg).save(os.path.join(OUT, 'AncientDragon_Normal_2048.png'))
Image.fromarray(nimg).resize((1024, 1024), Image.LANCZOS).save(os.path.join(OUT, 'AncientDragon_Normal.png'))
Image.fromarray((np.clip(emi + halo[..., 0] * 0.3, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, 'AncientDragon_Emission_2048.png'))
print('textures written', OUT)
