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
flat = np.zeros((ATLAS, ATLAS, 3), np.float32)

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
    flat[y:y + cp, x:x + cp] = np.clip(base, 0, 255)
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
....CC....
...C..C...
....CC....
..........
....CC....
...C..C...
..C....C..
.C..CC..C.
..C....C..
...C..C...
....CC....
"""
def _inside(poly, x, y):
    c = False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c
_xs = [p[0] for p in SHIELD]; _zs = [p[1] for p in SHIELD]
def _shield_cell(i, j):
    """map cell centre -> shield design coords (x, z)."""
    x = min(_xs) + (i + 0.5) / CELLS * (max(_xs) - min(_xs))
    z = max(_zs) - (j + 0.5) / CELLS * (max(_zs) - min(_zs))
    return x, z
_cx = sum(_xs) / len(_xs); _cz = sum(_zs) / len(_zs)
_inner = [(_cx + (x - _cx) * 0.68, _cz + (z - _cz) * 0.68) for x, z in SHIELD]
_crow = glyph_rows(CHEST)
def chest_fn(i, j):
    x, z = _shield_cell(i, j)
    if not _inside(_inner, x, z):
        return G, 0.0
    r, c_ = j - 2, i - 3
    if 0 <= r < len(_crow) and 0 <= c_ < len(_crow[r]) and _crow[r][c_] == 'C':
        return C, 1.0
    return T, 0.0
paint_grid('rune_chest', chest_fn)

DISC = """
........
.CCCCCC.
.CC..CC.
.CC..CC.
.CC..CC.
.CC..CC.
.CCCCCC.
........
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
........
.CCCCCC.
.CCCCCC.
.CC..CC.
.CC..CC.
.CCCCCC.
.CCCCCC.
........
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
a0, b1, S = wing_bounds()
trail = sorted(wing_trailing_2d(), key=lambda p: p[0])
lead = sorted([wing2d(p) for p in W_LEAD], key=lambda p: p[0])
def _interp(poly, a):
    if a <= poly[0][0]: return poly[0][1]
    for (x0, y0), (x1, y1) in zip(poly, poly[1:]):
        if x0 <= a <= x1:
            return y0 + (y1 - y0) * (a - x0) / max(x1 - x0, 1e-6)
    return poly[-1][1]
WCELL = 0.42
cellpx = WCELL * S
G_BIG = """
...CC...
...CC...
CCCCCCCC
C......C
C.CCCC.C
C.C..C.C
C.CCCC.C
C......C
CCCCCCCC
"""
G_MED = """
..C..
.CCC.
..C..
C.C.C
.CCC.
..C..
.C.C.
"""
G_SML = """
CC.
.C.
.CC
.C.
"""
G_TINY = """
C.
.C
"""
anch = wing_glyph_anchors()
glyphs = [(anch[2], G_BIG), (anch[1], G_MED), (anch[0], G_SML), (anch[3], G_TINY)]
glow_cells = set()
for (a, b), g in glyphs:
    rows = glyph_rows(g)
    ci0 = int((a - a0) / WCELL) - len(rows[0]) // 2
    cj0 = int((b1 - b) / WCELL) - len(rows) // 2
    for r, row in enumerate(rows):
        for c_, ch in enumerate(row):
            if ch == 'C':
                glow_cells.add((ci0 + c_, cj0 + r))
nx = int(ww / cellpx) + 1; ny = int(wh / cellpx) + 1
for j in range(ny):
    for i in range(nx):
        a = a0 + (i + 0.5) * WCELL
        b = b1 - (j + 0.5) * WCELL
        d = b - _interp(trail, a)            # height above trailing edge
        u = _interp(lead, a) - b             # depth below leading edge
        t = float(np.clip(1.0 - d / 2.4, 0, 1)) ** 1.5
        base = np.array(T, float) * (1 - t) + np.array((32, 150, 162)) * t
        e = 0.15 * t
        if d < 0.45:
            base = np.array((66, 214, 214)); e = 0.6
        if u < 1.3:
            base = np.array(K, float) * 1.05; e = 0.0
        if (i, j) in glow_cells:
            base, e = np.array(C), 1.0
        stud_cell(wx + i * cellpx, wy + j * cellpx, base, 0.08, e, cp=int(round(cellpx)))

# ---- the painted sculpt atlas is only used to colour voxels (runes / wing glyphs) ----

# ---------------- final voxel atlas: one studded swatch per palette colour ----------------
col[:] = 0; hgt[:] = 0; emi[:] = 0
for key, rgb, e, var in VOX:
    cx, cy = VOX_SWATCH[key]
    ox, oy = cx * SW, cy * SW
    for j in range(-1, CELLS + 1):
        for i in range(-1, CELLS + 1):
            x = ox + MARGIN + i * CELL_PX; y = oy + MARGIN + j * CELL_PX
            stud_cell(min(max(x, ox), ox + SW - CELL_PX), min(max(y, oy), oy + SW - CELL_PX), rgb, var, e)
halo = np.zeros((ATLAS, ATLAS, 1), np.float32)

# ---------------- stepped wing membrane painting (row 3), one cube per wing cell ----------------
VC = {k: (rgb, e) for k, rgb, e, _ in VOX}
wa0, wb0, NA, NB, wc = wing_grid()
cells = wing_cells()
paint = {(i + di, j + dj) for i, j in cells for di in (-1, 0, 1) for dj in (-1, 0, 1)
         if 0 <= i + di < NA and 0 <= j + dj < NB}
wglow = set()
for (ga, gb), g in [(anch[2], G_BIG), (anch[1], G_MED), (anch[0], G_SML), (anch[3], G_TINY)]:
    rows = glyph_rows(g)
    ci0 = int((ga - wa0) / wc) - len(rows[0]) // 2
    cj0 = int((gb - wb0) / wc) + len(rows) // 2      # row 0 of the glyph is its top (highest b)
    for r, row in enumerate(rows):
        for c_, ch in enumerate(row):
            if ch == 'C':
                wglow.add((ci0 + c_, cj0 - r))
for (i, j) in paint:
    a = wa0 + (i + 0.5) * wc; b = wb0 + (j + 0.5) * wc
    d = b - _interp(trail, a); u = _interp(lead, a) - b
    k = 'teal'
    if d < 2.4: k = 'teal_mid'
    if d < 1.3: k = 'teal_light'
    if (i, j - 1) not in cells or d < 0.5: k = 'glow_edge'
    if u < 1.1: k = 'dark'
    if (i, j) in wglow: k = 'glow'
    rgb, e = VC[k]
    stud_cell(i * CELL_PX, WING_ROW_Y + (NB - 1 - j) * CELL_PX, rgb, 0.08, e)
# eyeball: pale glowing sclera, bright cyan iris, dark vertical slit pupil
ex, ey, ew, eh = EYE_REGION
yy, xx = np.mgrid[0:eh, 0:ew]
dx = (xx + 0.5 - ew / 2) / (ew / 2); dy = (yy + 0.5 - eh / 2) / (eh / 2)
d = np.sqrt(dx ** 2 + dy ** 2)
eye = np.zeros((eh, ew, 3), np.float32); eem = np.zeros((eh, ew), np.float32)
eye[:] = (150, 238, 236); eem[:] = 0.55
iris = d < 0.62
eye[iris] = (60, 250, 244); eem[iris] = 1.0
ring = (d >= 0.56) & (d < 0.64)
eye[ring] = (20, 120, 130); eem[ring] = 0.2
pupil = (np.abs(dx) < 0.13 * np.sqrt(np.clip(1 - (dy / 0.5) ** 2, 0, 1))) & (np.abs(dy) < 0.5)
eye[pupil] = (8, 16, 22); eem[pupil] = 0.0
glint = ((dx + 0.25) ** 2 + (dy + 0.3) ** 2) < 0.012
eye[glint] = (255, 255, 255); eem[glint] = 1.0
col[ey:ey + eh, ex:ex + ew] = eye; emi[ey:ey + eh, ex:ex + ew] = eem; hgt[ey:ey + eh, ex:ex + ew] = 0.5

for name, art in RUNE_ART.items():
    ox_, oy_ = RUNE_ORIGIN[name]
    for r, row in enumerate(art):
        for q, ch in enumerate(row):
            k = ART_COLORS.get(ch, 'gold')          # '.' cells: gold (geometry crops them)
            rgb, e = VC[k]
            stud_cell(ox_ + q * CELL_PX, oy_ + r * CELL_PX, rgb, 0.06, e)

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
